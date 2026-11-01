"""FastAPI entry point for robot status, commands, and ESP32 telemetry."""

import asyncio
import json
import logging
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import get_api_token
from pydantic import BaseModel, ConfigDict, Field
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
THASHU_ROOT = REPO_ROOT / "thashu"
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from core.robot_manager import ControlMode


def _default_robot_manager_factory():
    # Import lazily so importing the API does not open hardware or start threads.
    from core.robot_manager import RobotCommandManager

    return RobotCommandManager()


class MoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Literal["forward", "backward", "left", "right"]
    speed: int = Field(default=200, ge=0, le=255, strict=True)


class CommandResponse(BaseModel):
    request_id: str
    command: str
    status: Literal["dispatched"]
    control_mode: Literal["AUTO", "MANUAL"]


class ApiServices:
    """Small adapter around existing services; injectable for API tests."""

    def __init__(self, robot_manager_factory: Callable = _default_robot_manager_factory):
        self._robot_manager_factory = robot_manager_factory
        self._robot_manager = None
        self._lock = asyncio.Lock()

    async def robot_manager(self):
        async with self._lock:
            if self._robot_manager is None:
                self._robot_manager = await asyncio.to_thread(self._robot_manager_factory)
            return self._robot_manager

    async def dispatch(self, command: str, speed: int | None = None):
        manager = await self.robot_manager()
        return await asyncio.to_thread(manager.dispatch, command, speed)

    async def status(self):
        try:
            manager = await self.robot_manager()
            motor = manager.motor
            transport = motor.gpio
            connected = bool(await asyncio.to_thread(transport.is_connected))
        except Exception:
            return {
                "api": "ok",
                "esp32_transport": "unavailable",
                "controller_readiness": "unknown",
                "control_mode": "unknown",
            }
        return {
            "api": "ok",
            "esp32_transport": "connected" if connected else "disconnected",
            "control_mode": manager.mode.value,
            # Serial-open is not proof of EVENT|READY; the transport currently
            # exposes raw messages and has no readiness state tracker.
            "controller_readiness": "unknown",
        }

    async def read_message(self):
        try:
            manager = await self.robot_manager()
            motor = manager.motor
            transport = motor.gpio
            line = await asyncio.to_thread(transport.read_line, 0.2)
            return line or None
        except Exception:
            return None


services = ApiServices()
bearer_scheme = HTTPBearer(auto_error=False)

# Document common command failures in Swagger without changing runtime behavior.
logger = logging.getLogger("thashu.api")


def _log_command_outcome(
    *,
    request_id: str,
    command: str,
    outcome: str,
    http_status: int,
    error_code: str | None = None,
    control_mode: str | None = None,
):
    """Write one sanitized JSON log record for a move or stop request."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "component": "pi_api",
        "event": "robot_command",
        "request_id": request_id,
        "command": command,
        "outcome": outcome,
        "http_status": http_status,
    }
    if error_code is not None:
        record["error_code"] = error_code
    if control_mode is not None:
        record["control_mode"] = control_mode
    logger.info("%s", json.dumps(record, separators=(",", ":"), sort_keys=True))


ROBOT_COMMAND_ERROR_RESPONSES = {
    401: {
        "description": "The Bearer token is missing or incorrect.",
        "content": {
            "application/json": {
                "example": {"detail": {"error": "unauthorized"}},
            }
        },
    },
    503: {
        "description": "Authentication is not configured, or the Pi cannot dispatch the command.",
        "content": {
            "application/json": {
                "examples": {
                    "authentication_not_configured": {
                        "summary": "The API token is not configured",
                        "value": {"detail": {"error": "authentication_not_configured"}},
                    },
                    "robot_unavailable": {
                        "summary": "The Pi cannot dispatch the command",
                        "value": {
                            "detail": {
                                "error": "robot_unavailable",
                                "request_id": "<uuid>",
                            }
                        },
                    },
                }
            }
        },
    },
}


async def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    expected_token = get_api_token()
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
    manager = services._robot_manager
    if manager is not None:
        await asyncio.to_thread(manager.motor.gpio.close)


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
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def move(request: MoveRequest):
    """Dispatch a validated movement request through the Pi motor service."""
    request_id = str(uuid4())
    try:
        sequence = await services.dispatch(request.direction, request.speed)
    except ValueError as exc:
        _log_command_outcome(
            request_id=request_id,
            command=request.direction,
            outcome="rejected",
            http_status=422,
            error_code="invalid_command",
        )
        raise HTTPException(status_code=422, detail={"error": "invalid_command", "request_id": request_id}) from exc
    except Exception as exc:
        _log_command_outcome(
            request_id=request_id,
            command=request.direction,
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id}) from exc
    if sequence is None:
        _log_command_outcome(
            request_id=request_id,
            command=request.direction,
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id})
    manager = await services.robot_manager()
    _log_command_outcome(
        request_id=request_id,
        command=request.direction,
        outcome="dispatched",
        http_status=200,
        control_mode=manager.mode.value,
    )
    return CommandResponse(
        request_id=request_id,
        command=request.direction,
        status="dispatched",
        control_mode=manager.mode.value,
    )


@app.post(
    "/api/v1/robot/stop",
    response_model=CommandResponse,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def stop():
    """Dispatch the dedicated high-priority stop through the Pi motor service."""
    request_id = str(uuid4())
    try:
        sequence = await services.dispatch("stop")
    except Exception as exc:
        _log_command_outcome(
            request_id=request_id,
            command="stop",
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id}) from exc
    if sequence is None:
        _log_command_outcome(
            request_id=request_id,
            command="stop",
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(status_code=503, detail={"error": "robot_unavailable", "request_id": request_id})
    manager = await services.robot_manager()
    _log_command_outcome(
        request_id=request_id,
        command="stop",
        outcome="dispatched",
        http_status=200,
        control_mode=manager.mode.value,
    )
    return CommandResponse(
        request_id=request_id,
        command="stop",
        status="dispatched",
        control_mode=manager.mode.value,
    )


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
