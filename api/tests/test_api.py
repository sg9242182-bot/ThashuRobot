import unittest
import os
from unittest.mock import patch

from api import main
from fastapi.security import HTTPAuthorizationCredentials


class FakeTransport:
    def __init__(self, connected=True, messages=()):
        self.connected = connected
        self.messages = list(messages)

    def is_connected(self):
        return self.connected

    def read_line(self, _timeout=0.0):
        return self.messages.pop(0) if self.messages else ""

    def close(self):
        pass


class FakeMotor:
    def __init__(self, messages=()):
        self.gpio = FakeTransport(messages=messages)
        self.commands = []

    def forward(self, speed=None):
        self.commands.append(("forward", speed))
        return 1

    def backward(self, speed=None):
        self.commands.append(("backward", speed))
        return 2

    def left(self, speed=None):
        self.commands.append(("left", speed))
        return 3

    def right(self, speed=None):
        self.commands.append(("right", speed))
        return 4

    def stop(self):
        self.commands.append(("stop", None))
        return 5


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_services = main.services
        main.services = main.ApiServices(lambda: FakeMotor(messages=["EVENT|0|READY"]))
        self.token_env = patch.dict(os.environ, {"THASHU_API_TOKEN": "test-token"})
        self.token_env.start()

    def tearDown(self):
        self.token_env.stop()
        main.services = self.old_services

    def endpoint(self, path):
        return next(route.endpoint for route in main.app.routes if getattr(route, "path", None) == path)

    async def test_health_is_api_liveness_only(self):
        self.assertEqual(await self.endpoint("/health")(), {"status": "ok"})

    async def test_status_does_not_confuse_serial_connection_with_readiness(self):
        self.assertEqual(await self.endpoint("/api/v1/status")(), {
            "api": "ok",
            "esp32_transport": "connected",
            "controller_readiness": "unknown",
        })

    async def test_status_reports_unavailable_transport_without_crashing(self):
        old = main.services
        main.services = main.ApiServices(lambda: (_ for _ in ()).throw(OSError("offline")))
        try:
            status = await self.endpoint("/api/v1/status")()
            self.assertEqual(status["esp32_transport"], "unavailable")
            self.assertEqual(status["controller_readiness"], "unknown")
        finally:
            main.services = old

    async def test_move_dispatches_through_motor_service(self):
        response = await self.endpoint("/api/v1/robot/move")(main.MoveRequest(direction="forward", speed=120))
        self.assertEqual(response.command, "forward")
        self.assertEqual(response.status, "dispatched")
        motor = await main.services.motor()
        self.assertEqual(motor.commands, [("forward", 120)])

    async def test_stop_dispatches_dedicated_stop(self):
        response = await self.endpoint("/api/v1/robot/stop")()
        self.assertEqual(response.command, "stop")
        self.assertEqual(response.status, "dispatched")
        motor = await main.services.motor()
        self.assertEqual(motor.commands, [("stop", None)])

    def test_move_request_rejects_unknown_direction_and_out_of_range_speed(self):
        with self.assertRaises(Exception):
            main.MoveRequest(direction="spin", speed=100)
        with self.assertRaises(Exception):
            main.MoveRequest(direction="forward", speed=256)

    async def test_bearer_auth_accepts_configured_token(self):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
        self.assertIsNone(await main.require_api_token(credentials))

    async def test_bearer_auth_rejects_missing_or_wrong_token(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as missing:
            await main.require_api_token(None)
        self.assertEqual(missing.exception.status_code, 401)

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong")
        with self.assertRaises(HTTPException) as wrong:
            await main.require_api_token(credentials)
        self.assertEqual(wrong.exception.status_code, 401)

    async def test_bearer_auth_fails_closed_when_token_is_not_configured(self):
        from fastapi import HTTPException

        with patch.dict(os.environ, {"THASHU_API_TOKEN": ""}):
            with self.assertRaises(HTTPException) as missing_config:
                await main.require_api_token(None)
        self.assertEqual(missing_config.exception.status_code, 503)

    async def test_telemetry_stream_wraps_raw_line_without_claiming_ack(self):
        class FakeWebSocket:
            def __init__(self):
                self.frames = []
                self.headers = {"authorization": "Bearer test-token"}

            async def accept(self):
                pass

            async def send_json(self, payload):
                self.frames.append(payload)
                from starlette.websockets import WebSocketDisconnect
                raise WebSocketDisconnect()

        socket = FakeWebSocket()
        await main.telemetry(socket)
        self.assertEqual(socket.frames, [{
            "type": "esp32_line",
            "line": "EVENT|0|READY",
        }])


if __name__ == "__main__":
    unittest.main()
