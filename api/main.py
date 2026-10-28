"""FastAPI entry point for read-only robot status and ESP32 telemetry."""

import asyncio
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
THASHU_ROOT = REPO_ROOT / "thashu"
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))


def _default_motor_factory():
    # Import lazily so importing the API does not open hardware or start threads.
    from hardware.motors import MotorController

    return MotorController()


class MoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Literal["forward", "backward", "left", "right"]
    speed: int = Field(default=200, ge=0, le=255)


class CommandResponse(BaseModel):
    request_id: str
    command: str
    status: Literal["dispatched"]


class ApiServices:
    """Small adapter around existing services; injectable for API tests."""

    def __init__(self, motor_factory: Callable = _default_motor_factory):
        self._motor_factory = motor_factory
        self._motor = None
        self._lock = asyncio.Lock()

    async def motor(self):
        async with self._lock:
            if self._motor is None:
                self._motor = await asyncio.to_thread(self._motor_factory)
            return self._motor

    async def dispatch(self, command: str, speed: int | None = None):
        motor = await self.motor()
        action = getattr(motor, command)
        if speed is None:
            return await asyncio.to_thread(action)
        return await asyncio.to_thread(action, speed)

    async def status(self):
        try:
            motor = await self.motor()
            transport = motor.gpio
            connected = bool(await asyncio.to_thread(transport.is_connected))
        except Exception:
            return {
                "api": "ok",
                "esp32_transport": "unavailable",
                "controller_readiness": "unknown",
            }
        return {
            "api": "ok",
            "esp32_transport": "connected" if connected else "disconnected",
            # Serial-open is not proof of EVENT|READY; the transport currently
            # exposes raw messages and has no readiness state tracker.
            "controller_readiness": "unknown",
        }

    async def read_message(self):
        try:
            motor = await self.motor()
            transport = motor.gpio
            line = await asyncio.to_thread(transport.read_line, 0.2)
            return line or None
        except Exception:
            return None


services = ApiServices()
bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    expected_token = os.getenv("THASHU_API_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail={"error": "authentication_not_configured"},
        )
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected_token)
    ):
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    motor = services._motor
    if motor is not None:
        await asyncio.to_thread(motor.gpio.close)


app = FastAPI(
    title="THASHU Raspberry Pi API",
    version="0.1.0",
    description="Robot movement, health, status, and ESP32 telemetry endpoints.",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
async def health():
    """API process liveness; does not claim that robot hardware is ready."""
    return {"status": "ok"}


@app.get("/api/v1/status", tags=["status"])
async def get_status():
    """Report API and serial transport state without implying controller readiness."""
    return await services.status()


@app.post(
    "/api/v1/robot/move",
    response_model=CommandResponse,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
)
async def move(request: MoveRequest):
    """Dispatch a validated movement request through the Pi motor service."""
    request_id = str(uuid4())
    try:
        sequence = await services.dispatch(request.direction, request.speed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_command", "request_id": request_id}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id}) from exc
    if sequence is None:
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id})
    return CommandResponse(request_id=request_id, command=request.direction, status="dispatched")


@app.post(
    "/api/v1/robot/stop",
    response_model=CommandResponse,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
)
async def stop():
    """Dispatch the dedicated high-priority stop through the Pi motor service."""
    request_id = str(uuid4())
    try:
        sequence = await services.dispatch("stop")
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id}) from exc
    if sequence is None:
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id})
    return CommandResponse(request_id=request_id, command="stop", status="dispatched")


@app.websocket("/api/v1/telemetry")
async def telemetry(websocket: WebSocket):
    """Stream raw newline-delimited ESP32 messages in a JSON text frame."""
    expected_token = os.getenv("THASHU_API_TOKEN")
    auth_header = websocket.headers.get("authorization", "")
    scheme, _, provided_token = auth_header.partition(" ")
    if not expected_token:
        await websocket.close(code=1011, reason="authentication not configured")
        return
    if (
        scheme.lower() != "bearer"
        or not provided_token
        or not secrets.compare_digest(provided_token, expected_token)
    ):
        await websocket.close(code=4401, reason="unauthorized")
        return
    await websocket.accept()
    try:
        while True:
            line = await services.read_message()
            if line is None:
                # Avoid a tight loop while preserving a server-to-client-only
                # stream. A disconnected client is detected on the next send.
                await asyncio.sleep(0.05)
                continue
            await websocket.send_json({"type": "esp32_line", "line": line})
    except WebSocketDisconnect:
        return
