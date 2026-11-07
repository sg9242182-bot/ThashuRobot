"""FastAPI entry point for robot status, commands, and ESP32 telemetry."""

import asyncio
import json
import logging
from math import ceil
import secrets
import sqlite3
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID, uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
THASHU_ROOT = REPO_ROOT / "thashu"
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from api.config import get_api_state_db_path, get_api_token
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

    request_id: UUID
    direction: Literal["forward", "backward", "left", "right"]
    speed: int = Field(default=200, ge=0, le=255, strict=True)


class CommandResponse(BaseModel):
    request_id: str | None = None
    command_id: str
    command: str
    status: Literal[
        "dispatching", "dispatched", "acknowledged", "safety_error",
        "timed_out", "rejected", "unknown",
    ]
    control_mode: Literal["AUTO", "MANUAL"]
    error_code: str | None = None
    timestamp: str | None = None


class StopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


def _replay_command_request(record, action, request_id):
    if record["action"] != action:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "request_id_conflict",
                "error_code": "REQUEST_ID_REUSED",
                "request_id": request_id,
            },
        )
    if record["error"] is not None and record["status"] != "unknown":
        raise HTTPException(
            status_code=record["http_status"],
            detail=record["error"],
        )
    return CommandResponse(**record["result"])


class ModeSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["AUTO", "MANUAL"]


class ModeSwitchResponse(BaseModel):
    mode: Literal["AUTO", "MANUAL"]
    status: Literal["switched"]


class PriorityCommandQueue:
    """Serialize API commands while letting STOP pass queued non-STOP work."""

    def __init__(self):
        self._locked = False
        self._next_order = 0
        self._waiters = []

    async def acquire(self, priority="normal"):
        if priority not in {"stop", "normal"}:
            raise ValueError("priority must be 'stop' or 'normal'")
        if not self._locked and not self._waiters:
            self._locked = True
            return

        loop = asyncio.get_running_loop()
        waiter = (0 if priority == "stop" else 1, self._next_order, loop.create_future())
        self._next_order += 1
        self._waiters.append(waiter)
        try:
            await waiter[2]
        except BaseException:
            if waiter in self._waiters:
                self._waiters.remove(waiter)
            elif waiter[2].done() and not waiter[2].cancelled():
                # The queue granted the slot as cancellation arrived. Pass it on.
                self.release()
            raise

    def release(self):
        if not self._locked:
            raise RuntimeError("command queue released while not held")
        while self._waiters:
            index = min(
                range(len(self._waiters)),
                key=lambda item: (self._waiters[item][0], self._waiters[item][1]),
            )
            _priority, _order, future = self._waiters.pop(index)
            if future.cancelled():
                continue
            future.set_result(None)
            return
        self._locked = False


class TokenBucketRateLimiter:
    """One in-memory bucket shared by every app using the configured token."""

    def __init__(self, capacity=10, refill_per_second=5.0):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.reset()

    def reset(self, now=None):
        self._tokens = float(self.capacity)
        self._updated_at = time.monotonic() if now is None else now

    def consume(self, now=None):
        """Consume a request token; return retry seconds when exhausted."""
        current = time.monotonic() if now is None else now
        elapsed = max(0.0, current - self._updated_at)
        self._tokens = min(
            float(self.capacity),
            self._tokens + elapsed * self.refill_per_second,
        )
        self._updated_at = current
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return None
        return (1.0 - self._tokens) / self.refill_per_second


class ApiServices:
    """Small adapter around existing services; injectable for API tests."""

    def __init__(
        self,
        robot_manager_factory: Callable = _default_robot_manager_factory,
        state_db_path=None,
    ):
        self._robot_manager_factory = robot_manager_factory
        self._robot_manager = None
        self._owns_robot_manager = True
        self._lock = asyncio.Lock()
        self._command_lock = threading.RLock()
        self._command_queue = PriorityCommandQueue()
        self._state_db_path = str(state_db_path or get_api_state_db_path())
        self._db_connection = None
        self._command_subscribers = set()
        self._command_tasks = set()
        self._result_retention_seconds = 24 * 60 * 60

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

    def _database(self):
        with self._command_lock:
            if self._db_connection is not None:
                return self._db_connection
            if self._state_db_path != ":memory:":
                db_path = Path(self._state_db_path).expanduser()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                target = str(db_path)
            else:
                target = ":memory:"
            connection = sqlite3.connect(
                target,
                timeout=10,
                check_same_thread=False,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS command_requests (
                    request_id TEXT PRIMARY KEY,
                    action_json TEXT NOT NULL,
                    command_id TEXT NOT NULL UNIQUE,
                    result_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    error_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )
            now = time.time()
            connection.execute(
                "DELETE FROM command_requests WHERE created_at < ?",
                (now - self._result_retention_seconds,),
            )
            # A dispatch marker or an outstanding ACK wait means the process
            # may have stopped before saving the outcome. Never replay the
            # command: expose its outcome as unknown instead.
            inflight = connection.execute(
                "SELECT request_id, result_json FROM command_requests "
                "WHERE status IN ('dispatching', 'awaiting_ack')"
            ).fetchall()
            for row in inflight:
                result = json.loads(row["result_json"])
                result.update(
                    status="unknown",
                    error_code="PROCESS_RESTARTED_DURING_DISPATCH",
                    timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                )
                connection.execute(
                    """UPDATE command_requests
                       SET status = 'unknown', result_json = ?, updated_at = ?
                       WHERE request_id = ?""",
                    (json.dumps(result, separators=(",", ":")), now, row["request_id"]),
                )
            self._db_connection = connection
            return connection

    def initialize_command_store(self):
        """Open and recover durable request records during API startup."""
        self._database()

    def close_command_store(self):
        with self._command_lock:
            if self._db_connection is not None:
                self._db_connection.close()
                self._db_connection = None

    @staticmethod
    def _request_row(row):
        if row is None:
            return None
        return {
            "request_id": row["request_id"],
            "action": json.loads(row["action_json"]),
            "command_id": row["command_id"],
            "result": json.loads(row["result_json"]),
            "status": row["status"],
            "http_status": row["http_status"],
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
        }

    def request_record(self, request_id):
        with self._command_lock:
            connection = self._database()
            now = time.time()
            connection.execute(
                "DELETE FROM command_requests WHERE created_at < ?",
                (now - self._result_retention_seconds,),
            )
            row = connection.execute(
                "SELECT * FROM command_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return self._request_row(row)

    def reserve_command_request(
        self, request_id, action, command, control_mode, command_id=None
    ):
        """Persist the action and command ID before any serial dispatch."""
        with self._command_lock:
            connection = self._database()
            now = time.time()
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM command_requests WHERE created_at < ?",
                    (now - self._result_retention_seconds,),
                )
                row = connection.execute(
                    "SELECT * FROM command_requests WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if row is not None:
                    connection.execute("COMMIT")
                    return self._request_row(row), False

                command_id = command_id or str(uuid4())
                timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                result = {
                    "request_id": request_id,
                    "command_id": command_id,
                    "command": command,
                    "status": "dispatching",
                    "error_code": None,
                    "timestamp": timestamp,
                    "control_mode": control_mode,
                }
                connection.execute(
                    """INSERT INTO command_requests
                       (request_id, action_json, command_id, result_json, status,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, 'dispatching', ?, ?)""",
                    (
                        request_id,
                        json.dumps(action, separators=(",", ":"), sort_keys=True),
                        command_id,
                        json.dumps(result, separators=(",", ":")),
                        now,
                        now,
                    ),
                )
                connection.execute("COMMIT")
                return self.request_record(request_id), True
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def update_command_request(
        self,
        request_id,
        status,
        error_code=None,
        http_status=None,
        error=None,
        control_mode=None,
        persist_status=None,
    ):
        with self._command_lock:
            connection = self._database()
            row = connection.execute(
                "SELECT result_json FROM command_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                return None
            result = json.loads(row["result_json"])
            result.update(
                status=status,
                error_code=error_code,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            )
            if control_mode is not None:
                result["control_mode"] = control_mode
            connection.execute(
                """UPDATE command_requests
                   SET result_json = ?, status = ?, http_status = ?, error_json = ?, updated_at = ?
                   WHERE request_id = ?""",
                (
                    json.dumps(result, separators=(",", ":")),
                    persist_status or status,
                    http_status,
                    json.dumps(error, separators=(",", ":")) if error is not None else None,
                    time.time(),
                    request_id,
                ),
            )
            return result

    def register_command(self, command_id, command, control_mode, request_id=None):
        request_id = request_id or f"internal:{command_id}"
        action = {"command": command}
        record, created = self.reserve_command_request(
            request_id, action, command, control_mode, command_id=command_id
        )
        if not created and record["command_id"] != command_id:
            return record["result"]
        return self.update_command_request(
            request_id,
            "dispatched",
            control_mode=control_mode,
            persist_status="awaiting_ack",
        )

    def command_result(self, command_id):
        with self._command_lock:
            connection = self._database()
            connection.execute(
                "DELETE FROM command_requests WHERE created_at < ?",
                (time.time() - self._result_retention_seconds,),
            )
            row = connection.execute(
                "SELECT result_json FROM command_requests WHERE command_id = ?",
                (command_id,),
            ).fetchone()
            return json.loads(row["result_json"]) if row is not None else None

    def subscribe_command_results(self):
        subscriber = asyncio.Queue(maxsize=64)
        self._command_subscribers.add(subscriber)
        return subscriber

    def unsubscribe_command_results(self, subscriber):
        self._command_subscribers.discard(subscriber)

    async def _publish_command_result(self, command_id, status, error_code):
        result = self.command_result(command_id)
        if result is None or result.get("request_id") is None:
            return
        result = self.update_command_request(
            result["request_id"], status, error_code=error_code
        )
        if result is None:
            return
        event = {
            "type": "command_result",
            "command_id": command_id,
            "request_id": result["request_id"],
            "status": status,
            "error_code": error_code,
            "timestamp": result["timestamp"],
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
            record = self.command_result(command_id)
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
move_mode_rate_limiter = TokenBucketRateLimiter(capacity=10, refill_per_second=5.0)

API_COMMAND_QUEUE_TIMEOUT_SECONDS = 2.0


@asynccontextmanager
async def command_request_slot(priority="normal"):
    """Bound queueing; prefer STOP and never cancel dispatched hardware work."""
    if priority == "stop":
        # A safety STOP waits for the active operation and jumps ahead of
        # queued movement/mode work instead of being rejected as API_BUSY.
        await services._command_queue.acquire("stop")
    else:
        try:
            await asyncio.wait_for(
                services._command_queue.acquire(priority),
                timeout=API_COMMAND_QUEUE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "command_queue_busy",
                    "error_code": "API_BUSY",
                    "retryable": True,
                },
            ) from exc
    try:
        yield
    finally:
        services._command_queue.release()
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

        content_type = next(
            (value.decode("latin-1") for key, value in scope.get("headers", [])
             if key.lower() == b"content-type"),
            "",
        )
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            response = JSONResponse(
                status_code=415,
                content={
                    "detail": {
                        "error": "unsupported_media_type",
                        "error_code": "UNSUPPORTED_MEDIA_TYPE",
                        "supported": ["application/json"],
                    }
                },
            )
            await response(scope, receive, send)
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
                    content={
                        "detail": {
                            "error": "request_body_too_large",
                            "error_code": "PAYLOAD_TOO_LARGE",
                        }
                    },
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
    500: {
        "description": "An unexpected server error occurred.",
        "content": {
            "application/json": {
                "example": {"detail": {
                    "error": "internal_error",
                    "error_code": "INTERNAL_ERROR",
                }},
            }
        },
    },
    404: {
        "description": "The command result is not available.",
        "content": {
            "application/json": {
                "example": {"detail": {
                    "error": "command_not_found",
                    "error_code": "COMMAND_NOT_FOUND",
                    "command_id": "<command_id>",
                }},
            }
        },
    },
    422: {
        "description": "The request body is invalid.",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "error": "validation_error",
                        "error_code": "VALIDATION_ERROR",
                        "issues": [{"loc": ["body", "direction"], "msg": "Input should be a valid direction"}],
                    }
                },
            }
        },
    },
    415: {
        "description": "Command bodies must use application/json.",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "error": "unsupported_media_type",
                        "error_code": "UNSUPPORTED_MEDIA_TYPE",
                        "supported": ["application/json"],
                    }
                },
            }
        },
    },
    409: {
        "description": "The request conflicts with the control mode, safety interlocks, or an earlier action using the same request_id.",
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
                    "request_id_reused": {
                        "value": {
                            "detail": {
                                "error": "request_id_conflict",
                                "error_code": "REQUEST_ID_REUSED",
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
                "example": {"detail": {
                    "error": "request_body_too_large",
                    "error_code": "PAYLOAD_TOO_LARGE",
                }},
            }
        },
    },
    401: {
        "description": "The Bearer token is missing or incorrect.",
        "content": {
            "application/json": {
                "example": {"detail": {
                    "error": "unauthorized",
                    "error_code": "UNAUTHORIZED",
                }},
            }
        },
    },
    503: {
        "description": "Authentication is not configured, the robot is unavailable, or STOP was not acknowledged during a mode switch.",
        "content": {
            "application/json": {
                "examples": {
                    "command_queue_busy": {
                        "summary": "The command slot stayed busy; this request was not dispatched",
                        "value": {"detail": {
                            "error": "command_queue_busy",
                            "error_code": "API_BUSY",
                            "retryable": True,
                        }},
                    },
                    "authentication_not_configured": {
                        "summary": "The API token is not configured",
                        "value": {"detail": {
                            "error": "authentication_not_configured",
                            "error_code": "AUTHENTICATION_NOT_CONFIGURED",
                        }},
                    },
                    "robot_unavailable": {
                        "summary": "The Pi cannot dispatch the command",
                        "value": {
                            "detail": {
                                "error": "robot_unavailable",
                                "error_code": "ROBOT_UNAVAILABLE",
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

MOVE_MODE_RATE_LIMIT_RESPONSES = {
    429: {
        "description": "The shared Bearer token bucket for move/mode requests is exhausted.",
        "content": {
            "application/json": {
                "example": {"detail": {
                    "error": "rate_limited",
                    "error_code": "RATE_LIMITED",
                    "retry_after_seconds": 0.2,
                }},
            }
        },
        "headers": {
            "Retry-After": {
                "description": "Whole seconds to wait before retrying.",
                "schema": {"type": "integer", "minimum": 1},
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


async def require_rate_limited_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Authenticate then enforce the shared move/mode token bucket."""
    await require_api_token(credentials)
    retry_after = move_mode_rate_limiter.consume()
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "error_code": "RATE_LIMITED",
                "retry_after_seconds": round(retry_after, 3),
            },
            headers={"Retry-After": str(max(1, ceil(retry_after)))},
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(services.initialize_command_store)
    try:
        yield
    finally:
        pending_commands = tuple(services._command_tasks)
        if pending_commands:
            await asyncio.gather(*pending_commands, return_exceptions=True)
        manager = services._robot_manager
        if manager is not None and services._owns_robot_manager:
            await asyncio.to_thread(manager.motor.gpio.close)
        await asyncio.to_thread(services.close_command_store)


app = FastAPI(
    title="THASHU Raspberry Pi API",
    version="0.1.0",
    description="Robot movement, health, status, and ESP32 telemetry endpoints.",
    lifespan=lifespan,
)
app.add_middleware(CommandBodySizeLimitMiddleware)


_HTTP_STATUS_ERROR_CODES = {
    400: "INVALID_ARGUMENT",
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

_ERROR_NAME_CODES = {
    "authentication_not_configured": "AUTHENTICATION_NOT_CONFIGURED",
    "command_not_found": "COMMAND_NOT_FOUND",
    "command_queue_busy": "API_BUSY",
    "invalid_command": "INVALID_COMMAND",
    "mode_switch_failed": "MODE_SWITCH_FAILED",
    "request_body_too_large": "PAYLOAD_TOO_LARGE",
    "request_id_conflict": "REQUEST_ID_REUSED",
    "rate_limited": "RATE_LIMITED",
    "robot_unavailable": "ROBOT_UNAVAILABLE",
    "safety_blocked": "SAFETY_BLOCKED",
    "unauthorized": "UNAUTHORIZED",
    "unsupported_media_type": "UNSUPPORTED_MEDIA_TYPE",
}


def _error_detail_with_code(status_code, detail):
    """Keep FastAPI's detail envelope and attach a stable code when possible."""
    if isinstance(detail, dict):
        normalized = dict(detail)
        if not normalized.get("error_code"):
            error_name = normalized.get("error")
            normalized["error_code"] = _ERROR_NAME_CODES.get(
                error_name, _HTTP_STATUS_ERROR_CODES.get(status_code, "HTTP_ERROR")
            )
        return normalized
    if isinstance(detail, str):
        return {
            "error": detail,
            "error_code": _HTTP_STATUS_ERROR_CODES.get(status_code, "HTTP_ERROR"),
        }
    return detail


@app.exception_handler(HTTPException)
async def http_error_handler(_request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"detail": _error_detail_with_code(exc.status_code, exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, exc):
    issues = [
        {
            "loc": list(issue.get("loc", ())),
            "msg": issue.get("msg", "Invalid request"),
            "type": issue.get("type", "value_error"),
        }
        for issue in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "detail": {
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "issues": issues,
            }
        }),
    )


@app.exception_handler(Exception)
async def internal_error_handler(request, _exc):
    logger.error("%s", json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "component": "pi_api",
        "event": "unhandled_exception",
        "path": request.url.path,
        "error_code": "INTERNAL_ERROR",
    }, separators=(",", ":"), sort_keys=True))
    return JSONResponse(
        status_code=500,
        content={
            "detail": {"error": "internal_error", "error_code": "INTERNAL_ERROR"}
        },
    )


@app.middleware("http")
async def log_api_request(request, call_next):
    """Log request completion without recording query strings or credentials."""
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "component": "pi_api",
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "http_status": status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        logger.info("%s", json.dumps(record, separators=(",", ":"), sort_keys=True))


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
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
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
    dependencies=[Depends(require_rate_limited_api_token)],
    responses={**ROBOT_COMMAND_ERROR_RESPONSES, **MOVE_MODE_RATE_LIMIT_RESPONSES},
)
async def switch_control_mode(request: ModeSwitchRequest):
    """Stop and confirm before selecting Manual or Auto; never starts motion."""
    request_id = str(uuid4())
    async with command_request_slot():
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
    dependencies=[Depends(require_rate_limited_api_token)],
    responses={**ROBOT_COMMAND_ERROR_RESPONSES, **MOVE_MODE_RATE_LIMIT_RESPONSES},
)
async def move(request: MoveRequest):
    """Dispatch a movement command and report its later ESP32 result asynchronously."""
    request_id = str(request.request_id)
    action = {
        "type": "move",
        "direction": request.direction,
        "speed": request.speed,
    }

    async with command_request_slot():
        existing = services.request_record(request_id)
        if existing is not None:
            response = _replay_command_request(existing, action, request_id)
            _log_command_outcome(
                command_id=response.command_id,
                command=request.direction,
                outcome="duplicate_replay",
                http_status=202,
                control_mode=response.control_mode,
            )
            return response

        manager = await services.robot_manager()
        record, created = services.reserve_command_request(
            request_id, action, request.direction, manager.mode.value
        )
        if not created:
            return _replay_command_request(record, action, request_id)
        command_id = record["command_id"]

        def fail(status_code, detail, *, outcome, error_code, state, control_mode=None):
            services.update_command_request(
                request_id,
                state,
                error_code=error_code,
                http_status=status_code,
                error=detail,
                control_mode=control_mode,
            )
            _log_command_outcome(
                command_id=command_id,
                command=request.direction,
                outcome=outcome,
                http_status=status_code,
                error_code=error_code,
                control_mode=control_mode,
            )
            raise HTTPException(status_code=status_code, detail=detail)

        try:
            sequence = await services.dispatch_in_selected_mode(
                request.direction,
                request.speed,
            )
        except ControlModeError as exc:
            manager = await services.robot_manager()
            fail(
                409,
                {
                    "error": "control_mode_conflict",
                    "error_code": str(exc),
                    "command_id": command_id,
                },
                outcome="rejected",
                error_code=str(exc),
                state="rejected",
                control_mode=manager.mode.value,
            )
        except RobotSafetyError as exc:
            manager = await services.robot_manager()
            fail(
                409,
                {
                    "error": "safety_blocked",
                    "error_code": exc.error_code,
                    "command_id": command_id,
                },
                outcome="rejected",
                error_code=exc.error_code,
                state="rejected",
                control_mode=manager.mode.value,
            )
        except ValueError:
            fail(
                422,
                {"error": "invalid_command", "command_id": command_id},
                outcome="rejected",
                error_code="invalid_command",
                state="rejected",
            )
        except Exception as exc:
            fail(
                503,
                {"error": "robot_unavailable", "command_id": command_id},
                outcome="failed",
                error_code="COMMAND_OUTCOME_UNKNOWN",
                state="unknown",
                control_mode=manager.mode.value,
            )
        if sequence is None:
            fail(
                503,
                {"error": "robot_unavailable", "command_id": command_id},
                outcome="failed",
                error_code="COMMAND_OUTCOME_UNKNOWN",
                state="unknown",
                control_mode=manager.mode.value,
            )

        manager = await services.robot_manager()
        services.register_command(
            command_id,
            request.direction,
            manager.mode.value,
            request_id=request_id,
        )
        services.start_ack_tracking(command_id, sequence)
        _log_command_outcome(
            command_id=command_id,
            command=request.direction,
            outcome="dispatched",
            http_status=202,
            control_mode=manager.mode.value,
        )
        return CommandResponse(**services.command_result(command_id))


@app.post(
    "/api/v1/robot/stop",
    response_model=CommandResponse,
    status_code=202,
    tags=["robot"],
    dependencies=[Depends(require_api_token)],
    responses=ROBOT_COMMAND_ERROR_RESPONSES,
)
async def stop(request: StopRequest):
    """Dispatch STOP and report its later ESP32 result asynchronously."""
    request_id = str(request.request_id)
    action = {"type": "stop"}

    async with command_request_slot("stop"):
        existing = services.request_record(request_id)
        if existing is not None:
            response = _replay_command_request(existing, action, request_id)
            _log_command_outcome(
                command_id=response.command_id,
                command="stop",
                outcome="duplicate_replay",
                http_status=202,
                control_mode=response.control_mode,
            )
            return response

        manager = await services.robot_manager()
        record, created = services.reserve_command_request(
            request_id, action, "stop", manager.mode.value
        )
        if not created:
            return _replay_command_request(record, action, request_id)
        command_id = record["command_id"]

        try:
            sequence = await services.stop_all()
        except Exception as exc:
            detail = {"error": "robot_unavailable", "command_id": command_id}
            services.update_command_request(
                request_id,
                "unknown",
                error_code="COMMAND_OUTCOME_UNKNOWN",
                http_status=503,
                error=detail,
                control_mode=manager.mode.value,
            )
            _log_command_outcome(
                command_id=command_id,
                command="stop",
                outcome="failed",
                http_status=503,
                error_code="COMMAND_OUTCOME_UNKNOWN",
                control_mode=manager.mode.value,
            )
            raise HTTPException(status_code=503, detail=detail) from exc
        if sequence is None:
            detail = {"error": "robot_unavailable", "command_id": command_id}
            services.update_command_request(
                request_id,
                "unknown",
                error_code="COMMAND_OUTCOME_UNKNOWN",
                http_status=503,
                error=detail,
                control_mode=manager.mode.value,
            )
            raise HTTPException(status_code=503, detail=detail)

        manager = await services.robot_manager()
        services.register_command(
            command_id,
            "stop",
            manager.mode.value,
            request_id=request_id,
        )
        services.start_ack_tracking(command_id, sequence)
        _log_command_outcome(
            command_id=command_id,
            command="stop",
            outcome="dispatched",
            http_status=202,
            control_mode=manager.mode.value,
        )
        return CommandResponse(**services.command_result(command_id))


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
