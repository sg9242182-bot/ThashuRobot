import unittest
import os
from unittest.mock import patch

from api import main
from fastapi.security import HTTPAuthorizationCredentials


class FakeTransport:
    def __init__(self, connected=True, messages=(), ack_result="OK"):
        self.connected = connected
        self.messages = list(messages)
        self.ack_result = ack_result

    def wait_for_ack(self, _sequence, _timeout=0.75):
        return self.ack_result

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


class FakeRobotManager:
    def __init__(self, motor):
        self.motor = motor
        self.mode = main.ControlMode.AUTO

    def dispatch(self, command, speed=None):
        action = getattr(self.motor, command)
        sequence = action() if speed is None else action(speed)
        if sequence is not None:
            self.mode = main.ControlMode.AUTO if command == "stop" else main.ControlMode.MANUAL
        return sequence

    def safety_stop(self):
        return self.motor.stop()


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_services = main.services
        main.services = main.ApiServices(lambda: FakeRobotManager(FakeMotor(messages=["EVENT|0|READY"])))
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
            "control_mode": "AUTO",
        })

    async def test_status_reports_unavailable_transport_without_crashing(self):
        old = main.services
        main.services = main.ApiServices(lambda: (_ for _ in ()).throw(OSError("offline")))
        try:
            status = await self.endpoint("/api/v1/status")()
            self.assertEqual(status["esp32_transport"], "unavailable")
            self.assertEqual(status["controller_readiness"], "unknown")
            self.assertEqual(status["control_mode"], "unknown")
        finally:
            main.services = old

    async def test_move_dispatches_through_motor_service(self):
        response = await self.endpoint("/api/v1/robot/move")(main.MoveRequest(direction="forward", speed=120))
        self.assertTrue(response.command_id)
        self.assertEqual(response.command, "forward")
        self.assertEqual(response.status, "dispatched")
        self.assertEqual(response.control_mode, "MANUAL")
        manager = await main.services.robot_manager()
        motor = manager.motor
        self.assertEqual(motor.commands, [("forward", 120)])

    async def test_stop_dispatches_dedicated_stop(self):
        response = await self.endpoint("/api/v1/robot/stop")()
        self.assertEqual(response.command, "stop")
        self.assertEqual(response.status, "dispatched")
        self.assertEqual(response.control_mode, "AUTO")
        manager = await main.services.robot_manager()
        motor = manager.motor
        self.assertEqual(motor.commands, [("stop", None)])

    async def test_acknowledged_command_result_can_be_looked_up(self):
        services = main.services
        services.register_command("command-1", "forward", "MANUAL")
        await services.track_command_ack("command-1", 1)

        lookup = self.endpoint("/api/v1/robot/commands/{command_id}")
        result = await lookup("command-1")
        self.assertEqual(result["command_id"], "command-1")
        self.assertEqual(result["command"], "forward")
        self.assertEqual(result["status"], "acknowledged")
        self.assertIsNone(result["error_code"])
        self.assertTrue(result["timestamp"])

    async def test_safety_ack_is_published_as_command_result_event(self):
        manager = await main.services.robot_manager()
        manager.motor.gpio.ack_result = "ERROR|OBSTACLE"
        manager.mode = main.ControlMode.MANUAL
        subscriber = main.services.subscribe_command_results()
        try:
            main.services.register_command("command-2", "forward", "MANUAL")
            await main.services.track_command_ack("command-2", 2)
            event = subscriber.get_nowait()
            self.assertEqual(event["type"], "command_result")
            self.assertEqual(event["command_id"], "command-2")
            self.assertEqual(event["status"], "safety_error")
            self.assertEqual(event["error_code"], "OBSTACLE")
            self.assertTrue(event["timestamp"])
            self.assertEqual(manager.motor.commands, [("stop", None)])
            self.assertEqual(manager.mode, main.ControlMode.MANUAL)
        finally:
            main.services.unsubscribe_command_results(subscriber)

    async def test_missing_ack_becomes_timeout(self):
        manager = await main.services.robot_manager()
        manager.motor.gpio.ack_result = None
        main.services.register_command("command-3", "forward", "MANUAL")
        await main.services.track_command_ack("command-3", 3)
        result = main.services.command_result("command-3")
        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(result["error_code"], "ACK_TIMEOUT")
        self.assertEqual(manager.motor.commands, [("stop", None)])
        self.assertEqual(manager.mode, main.ControlMode.AUTO)

    async def test_failed_stop_ack_does_not_trigger_another_stop(self):
        manager = await main.services.robot_manager()
        manager.motor.gpio.ack_result = None
        main.services.register_command("command-stop", "stop", "AUTO")
        await main.services.track_command_ack("command-stop", 5)
        self.assertEqual(manager.motor.commands, [])
        result = main.services.command_result("command-stop")
        self.assertEqual(result["status"], "timed_out")

    def test_move_request_rejects_unknown_direction_and_out_of_range_speed(self):
        with self.assertRaises(Exception):
            main.MoveRequest(direction="spin", speed=100)
        with self.assertRaises(Exception):
            main.MoveRequest(direction="forward", speed=256)

    def test_openapi_documents_command_body_limit(self):
        schema = main.app.openapi()
        for path in ("/api/v1/robot/move", "/api/v1/robot/stop"):
            with self.subTest(path=path):
                operation = schema["paths"][path]["post"]
                self.assertIn("413", operation["responses"])
                content = operation["responses"]["413"]["content"]["application/json"]
                self.assertEqual(
                    content["example"],
                    {"detail": {"error": "request_body_too_large"}},
                )

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

    async def test_command_body_limit_rejects_oversized_request_before_route(self):
        reached_route = False
        sent = []

        async def app(scope, receive, send):
            nonlocal reached_route
            reached_route = True

        async def receive():
            return {
                "type": "http.request",
                "body": b"x" * 4097,
                "more_body": False,
            }

        async def send(message):
            sent.append(message)

        middleware = main.CommandBodySizeLimitMiddleware(app)
        await middleware(
            {"type": "http", "method": "POST", "path": "/api/v1/robot/move"},
            receive,
            send,
        )

        self.assertFalse(reached_route)
        self.assertEqual(sent[0]["status"], 413)
        self.assertIn(b"request_body_too_large", sent[1]["body"])

    async def test_command_body_at_limit_reaches_route_unchanged(self):
        received = bytearray()

        async def app(scope, receive, send):
            message = await receive()
            received.extend(message["body"])

        async def receive():
            return {
                "type": "http.request",
                "body": b"x" * 4096,
                "more_body": False,
            }

        async def send(_message):
            pass

        middleware = main.CommandBodySizeLimitMiddleware(app)
        await middleware(
            {"type": "http", "method": "POST", "path": "/api/v1/robot/move"},
            receive,
            send,
        )

        self.assertEqual(len(received), 4096)


if __name__ == "__main__":
    unittest.main()
