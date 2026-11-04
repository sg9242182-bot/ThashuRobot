"""FastAPI entry point for robot status, commands, and ESP32 telemetry."""

import asyncio
import json
import logging
import secrets
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from starlette.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import get_api_token
from pydantic import BaseModel, ConfigDict, Field
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
THASHU_ROOT = REPO_ROOT / "thashu"
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from core.robot_manager import (
    ControlMode,
    ControlModeError,
    ModeSwitchError,
    RobotSafetyError,
)


def _default_robot_manager_factory():
    # Import lazily so importing the API does not open hardware or start threads.
    from core.robot_manager import RobotCommandManager

    return RobotCommandManager()


class MoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Literal["forward", "backward", "left", "right"]
    speed: int = Field(default=200, ge=0, le=255, strict=True)


class CommandResponse(BaseModel):
    command_id: str
    command: str
    status: Literal["dispatched"]
    control_mode: Literal["AUTO", "MANUAL"]


class ModeSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["AUTO", "MANUAL"]


class ModeSwitchResponse(BaseModel):
    mode: Literal["AUTO", "MANUAL"]
    status: Literal["switched"]


class ApiServices:
    """Small adapter around existing services; injectable for API tests."""

    def __init__(self, robot_manager_factory: Callable = _default_robot_manager_factory):
        self._robot_manager_factory = robot_manager_factory
        self._robot_manager = None
        self._owns_robot_manager = True
        self._lock = asyncio.Lock()
        self._command_lock = threading.RLock()
        self._command_results = {}
        self._command_subscribers = set()
        self._command_tasks = set()
        self._result_retention_seconds = 24 * 60 * 60
        self._max_command_results = 1000

    def attach_robot_manager(self, manager):
        """Use the robot process's existing manager and serial connection."""
        if self._robot_manager is not None and self._robot_manager is not manager:
            raise RuntimeError("API is already attached to a different robot manager")
        self._robot_manager = manager
        self._owns_robot_manager = False

    async def robot_manager(self):
        async with self._lock:
            if self._robot_manager is None:
                self._robot_manager = await asyncio.to_thread(self._robot_manager_factory)
            return self._robot_manager

    async def dispatch(self, command: str, speed: int | None = None):
        manager = await self.robot_manager()
        return await asyncio.to_thread(manager.dispatch, command, speed)

    async def dispatch_in_selected_mode(self, command: str, speed: int | None = None):
        manager = await self.robot_manager()
        state_version = manager.state_version
        return await asyncio.to_thread(
            manager.dispatch,
            command,
            speed,
            require_current_mode=True,
            expected_state_version=state_version,
        )

    async def switch_mode(self, mode: str):
        manager = await self.robot_manager()
        return await asyncio.to_thread(manager.switch_mode, mode)

    async def stop_all(self):
        manager = await self.robot_manager()
        return await asyncio.to_thread(manager.stop_all)

    async def safety_stop(self):
        manager = await self.robot_manager()
        return await asyncio.to_thread(manager.safety_stop)

    def _prune_command_results(self):
        now = time.monotonic()
        expired = [
            command_id
            for command_id, record in self._command_results.items()
            if now - record["_created_monotonic"] > self._result_retention_seconds
        ]
        for command_id in expired:
            self._command_results.pop(command_id, None)
        while len(self._command_results) > self._max_command_results:
            oldest = next(iter(self._command_results))
            self._command_results.pop(oldest, None)

    def register_command(self, command_id, command, control_mode):
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with self._command_lock:
            self._prune_command_results()
            self._command_results[command_id] = {
                "command_id": command_id,
                "command": command,
                "status": "dispatched",
                "error_code": None,
                "timestamp": now,
                "control_mode": control_mode,
                "_created_monotonic": time.monotonic(),
            }
            self._prune_command_results()

    def command_result(self, command_id):
        with self._command_lock:
            self._prune_command_results()
            record = self._command_results.get(command_id)
            if record is None:
                return None
            return {
                key: record[key]
                for key in ("command_id", "command", "status", "error_code", "timestamp")
            }

    def subscribe_command_results(self):
        subscriber = asyncio.Queue(maxsize=64)
        self._command_subscribers.add(subscriber)
        return subscriber

    def unsubscribe_command_results(self, subscriber):
        self._command_subscribers.discard(subscriber)

    async def _publish_command_result(self, command_id, status, error_code):
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with self._command_lock:
            record = self._command_results.get(command_id)
            if record is None:
                return
            record.update(status=status, error_code=error_code, timestamp=timestamp)
            event = {
                "type": "command_result",
                "command_id": command_id,
                "status": status,
                "error_code": error_code,
                "timestamp": timestamp,
            }
        for subscriber in tuple(self._command_subscribers):
            if subscriber.full():
                try:
                    subscriber.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def track_command_ack(self, command_id, sequence):
        try:
            manager = await self.robot_manager()
            ack = await asyncio.to_thread(
                manager.motor.gpio.wait_for_ack, sequence, 0.75
            )
        except Exception:
            ack = None

        if ack is None:
            status, error_code = "timed_out", "ACK_TIMEOUT"
        elif ack == "OK":
            status, error_code = "acknowledged", None
        elif ack.startswith("ERROR|"):
            status, error_code = "safety_error", ack.split("|", 1)[1] or "UNKNOWN"
        else:
            status, error_code = "safety_error", "UNEXPECTED_ACK"

        # A motion command that is rejected or loses its ACK may still have
        # reached the controller. Send the dedicated STOP as a fail-safe, but
        # preserve the original command's result for the app. STOP failures do
        # not recursively trigger another STOP.
        if status in {"timed_out", "safety_error"}:
            with self._command_lock:
                record = self._command_results.get(command_id)
                command = record["command"] if record is not None else None
            if command in {"forward", "backward", "left", "right"}:
                try:
                    await self.safety_stop()
                except Exception:
                    logger.exception(
                        "Fail-safe STOP dispatch failed after command %s result %s",
                        command_id,
                        status,
                    )

        await self._publish_command_result(command_id, status, error_code)

    def start_ack_tracking(self, command_id, sequence):
        task = asyncio.create_task(self.track_command_ack(command_id, sequence))
        self._command_tasks.add(task)
        task.add_done_callback(self._command_tasks.discard)

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


class CommandBodySizeLimitMiddleware:
    """Bound request bodies for robot command routes before JSON parsing."""

    _COMMAND_PATHS = frozenset({
        "/api/v1/robot/move",
        "/api/v1/robot/stop",
        "/api/v1/robot/mode",
    })

    def __init__(self, app, max_bytes=4096):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in self._COMMAND_PATHS
        ):
            await self.app(scope, receive, send)
            return

        messages = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": {"error": "request_body_too_large"}},
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        index = 0

        async def replay_body():
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_body, send)


def _log_command_outcome(
    *,
    command_id: str,
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
        "command_id": command_id,
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
    409: {
        "description": "The selected control mode or a Pi-side sensor interlock blocks movement.",
        "content": {
            "application/json": {
                "examples": {
                    "manual_mode_required": {
                        "value": {
                            "detail": {
                                "error": "control_mode_conflict",
                                "error_code": "MANUAL_MODE_REQUIRED",
                            }
                        }
                    },
                    "auto_not_started": {
                        "value": {
                            "detail": {
                                "error": "control_mode_conflict",
                                "error_code": "AUTO_NOT_STARTED",
                            }
                        }
                    },
                    "stop_confirmation_required": {
                        "value": {
                            "detail": {
                                "error": "control_mode_conflict",
                                "error_code": "STOP_CONFIRMATION_REQUIRED",
                            }
                        }
                    },
                    "control_state_changed": {
                        "value": {
                            "detail": {
                                "error": "control_mode_conflict",
                                "error_code": "CONTROL_STATE_CHANGED",
                            }
                        }
                    },
                    "sensor_not_ready": {
                        "value": {
                            "detail": {
                                "error": "safety_blocked",
                                "error_code": "SENSOR_NOT_READY",
                            }
                        }
                    },
                    "obstacle_blocked": {
                        "value": {
                            "detail": {
                                "error": "safety_blocked",
                                "error_code": "OBSTACLE_BLOCKED",
                            }
                        }
                    },
                }
            }
        },
    },
    413: {
        "description": "The request body exceeds the 4 KiB command limit.",
        "content": {
            "application/json": {
                "example": {"detail": {"error": "request_body_too_large"}},
            }
        },
    },
    401: {
        "description": "The Bearer token is missing or incorrect.",
        "content": {
            "application/json": {
                "example": {"detail": {"error": "unauthorized"}},
            }
        },
    },
    503: {
        "description": "Authentication is not configured, the robot is unavailable, or STOP was not acknowledged during a mode switch.",
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
                                "command_id": "<uuid>",
                            }
                        },
                    },
                    "mode_switch_failed": {
                        "summary": "The ESP32 did not confirm STOP",
                        "value": {
                            "detail": {
                                "error": "mode_switch_failed",
                                "error_code": "STOP_ACK_TIMEOUT",
                                "control_mode": "AUTO",
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
    if manager is not None and services._owns_robot_manager:
        await asyncio.to_thread(manager.motor.gpio.close)


app = FastAPI(
    title="THASHU Raspberry Pi API",
    version="0.1.0",
    description="Robot movement, health, status, and ESP32 telemetry endpoints.",
    lifespan=lifespan,
)
app.add_middleware(CommandBodySizeLimitMiddleware)


@app.get("/health", tags=["health"])
async def health():
    """API process liveness; does not claim that robot hardware is ready."""
    return {"status": "ok"}


@app.get("/api/v1/status", tags=["status"])
async def get_status():
    """Report API and serial transport state without implying controller readiness."""
    return await services.status()


@app.get(
    "/api/v1/robot/commands/{command_id}",
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
)
async def get_command_result(command_id: str):
    """Return the latest known Pi/ESP32 result for a dispatched command."""
    result = services.command_result(command_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "command_not_found", "command_id": command_id},
        )
    return result


@app.post(
    "/api/v1/robot/mode",
    response_model=ModeSwitchResponse,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def switch_control_mode(request: ModeSwitchRequest):
    """Stop and confirm before selecting Manual or Auto; never starts motion."""
    request_id = str(uuid4())
    try:
        await services.switch_mode(request.mode)
    except ModeSwitchError as exc:
        manager = await services.robot_manager()
        _log_command_outcome(
            command_id=request_id,
            command=f"mode:{request.mode}",
            outcome="failed",
            http_status=503,
            error_code=exc.error_code,
            control_mode=manager.mode.value,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "mode_switch_failed",
                "error_code": exc.error_code,
                "control_mode": manager.mode.value,
            },
        ) from exc
    except Exception as exc:
        _log_command_outcome(
            command_id=request_id,
            command=f"mode:{request.mode}",
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "robot_unavailable"},
        ) from exc

    manager = await services.robot_manager()
    _log_command_outcome(
        command_id=request_id,
        command=f"mode:{request.mode}",
        outcome="switched",
        http_status=200,
        control_mode=manager.mode.value,
    )
    return ModeSwitchResponse(mode=manager.mode.value, status="switched")


@app.post(
    "/api/v1/robot/move",
    response_model=CommandResponse,
    status_code=202,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def move(request: MoveRequest):
    """Dispatch a movement command and report its later ESP32 result asynchronously."""
    command_id = str(uuid4())
    try:
        sequence = await services.dispatch_in_selected_mode(
            request.direction,
            request.speed,
        )
    except ControlModeError as exc:
        manager = await services.robot_manager()
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="rejected",
            http_status=409,
            error_code=str(exc),
            control_mode=manager.mode.value,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": "control_mode_conflict",
                "error_code": str(exc),
                "command_id": command_id,
            },
        ) from exc
    except RobotSafetyError as exc:
        manager = await services.robot_manager()
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="rejected",
            http_status=409,
            error_code=exc.error_code,
            control_mode=manager.mode.value,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": "safety_blocked",
                "error_code": exc.error_code,
                "command_id": command_id,
            },
        ) from exc
    except ValueError as exc:
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="rejected",
            http_status=422,
            error_code="invalid_command",
        )
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_command", "command_id": command_id},
        ) from exc
    except Exception as exc:
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "robot_unavailable", "command_id": command_id},
        ) from exc
    if sequence is None:
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "robot_unavailable", "command_id": command_id},
        )
    manager = await services.robot_manager()
    services.register_command(command_id, request.direction, manager.mode.value)
    services.start_ack_tracking(command_id, sequence)
    _log_command_outcome(
        command_id=command_id,
        command=request.direction,
        outcome="dispatched",
        http_status=202,
        control_mode=manager.mode.value,
    )
    return CommandResponse(
        command_id=command_id,
        command=request.direction,
        status="dispatched",
        control_mode=manager.mode.value,
    )


@app.post(
    "/api/v1/robot/stop",
    response_model=CommandResponse,
    status_code=202,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def stop():
    """Dispatch STOP and report its later ESP32 result asynchronously."""
    command_id = str(uuid4())
    try:
        sequence = await services.stop_all()
    except Exception as exc:
        _log_command_outcome(
            command_id=command_id,
            command="stop",
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "robot_unavailable", "command_id": command_id},
        ) from exc
    if sequence is None:
        _log_command_outcome(
            command_id=command_id,
            command="stop",
            outcome="failed",
            http_status=503,
            error_code="robot_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "robot_unavailable", "command_id": command_id},
        )
    manager = await services.robot_manager()
    services.register_command(command_id, "stop", manager.mode.value)
    services.start_ack_tracking(command_id, sequence)
    _log_command_outcome(
        command_id=command_id,
        command="stop",
        outcome="dispatched",
        http_status=202,
        control_mode=manager.mode.value,
    )
    return CommandResponse(
        command_id=command_id,
        command="stop",
        status="dispatched",
        control_mode=manager.mode.value,
    )


@app.websocket("/api/v1/telemetry")
async def telemetry(websocket: WebSocket):
    """Stream raw ESP32 lines and asynchronous command_result events."""
    expected_token = get_api_token()
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
    subscriber = services.subscribe_command_results()
    try:
        while True:
            # Check result events before and after the existing serial queue read.
            # That queue has a 200 ms timeout, bounding event delivery latency.
            try:
                event = subscriber.get_nowait()
                await websocket.send_json(event)
                continue
            except asyncio.QueueEmpty:
                pass
            line = await services.read_message()
            if line is not None:
                await websocket.send_json({"type": "esp32_line", "line": line})
            try:
                event = subscriber.get_nowait()
                await websocket.send_json(event)
            except asyncio.QueueEmpty:
                if line is None:
                    await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        return
    finally:
        services.unsubscribe_command_results(subscriber)
