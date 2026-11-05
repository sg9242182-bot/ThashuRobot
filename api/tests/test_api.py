import unittest
import os
import asyncio
import tempfile
from uuid import UUID
from unittest.mock import patch

from api import main
from thashu.core import config as robot_config
from core.robot_manager import ControlModeError, ModeSwitchError
from fastapi.security import HTTPAuthorizationCredentials


class ConfigurationTests(unittest.TestCase):
    def test_api_host_and_port_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(robot_config.api_host(), "127.0.0.1")
            self.assertEqual(robot_config.api_port(), 8000)

    def test_api_host_and_port_overrides_are_validated(self):
        with patch.dict(os.environ, {"THASHU_API_HOST": "0.0.0.0", "THASHU_API_PORT": "8088"}):
            self.assertEqual(robot_config.api_host(), "0.0.0.0")
            self.assertEqual(robot_config.api_port(), 8088)
        for value in ("0", "65536", "abc", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"THASHU_API_PORT": value}):
                with self.assertRaises(ValueError):
                    robot_config.api_port()

    def test_optional_paths_reject_empty_overrides(self):
        for name, getter in (
            ("THASHU_API_STATE_DB", robot_config.api_state_db_path),
            ("THASHU_MODELS_DIR", robot_config.models_dir),
            ("THASHU_DATA_DIR", robot_config.data_dir),
            ("THASHU_VOICE_CACHE_DIR", robot_config.voice_cache_dir),
        ):
            with self.subTest(name=name), patch.dict(os.environ, {name: "   "}):
                with self.assertRaises(ValueError):
                    getter()

    def test_face_match_debug_requires_boolean_text(self):
        with patch.dict(os.environ, {"THASHU_FACE_MATCH_DEBUG": "1"}):
            self.assertTrue(robot_config.face_match_debug_enabled())
        with patch.dict(os.environ, {"THASHU_FACE_MATCH_DEBUG": "yes"}):
            with self.assertRaises(ValueError):
                robot_config.face_match_debug_enabled()


class FakeTransport:
    def __init__(self, connected=True, messages=(), ack_result="OK"):
        self.connected = connected
        self.messages = list(messages)
        self.ack_result = ack_result
        self.sensor_snapshot = {
            "tof_left_mm": 500,
            "tof_center_mm": 500,
            "tof_right_mm": 500,
            "rear_mm": 500,
        }

    def wait_for_ack(self, _sequence, timeout=0.75):
        return self.ack_result

    def get_sensor_snapshot(self, max_age=0.75):
        return self.sensor_snapshot

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
        self.auto_active = False
        self.motion_inhibited = False
        self.state_version = 0

    def dispatch(
        self,
        command,
        speed=None,
        require_current_mode=False,
        expected_state_version=None,
    ):
        if (
            expected_state_version is not None
            and expected_state_version != self.state_version
        ):
            raise ControlModeError("CONTROL_STATE_CHANGED")
        if command in {"forward", "backward", "left", "right"}:
            if require_current_mode and self.mode != main.ControlMode.MANUAL:
                raise ControlModeError("MANUAL_MODE_REQUIRED")
            if self.motion_inhibited:
                raise ControlModeError("STOP_CONFIRMATION_REQUIRED")
            if self.mode == main.ControlMode.AUTO:
                raise ControlModeError("MANUAL_MODE_REQUIRED")
        action = getattr(self.motor, command)
        sequence = action() if speed is None else action(speed)
        if sequence is not None:
            self.mode = main.ControlMode.AUTO if command == "stop" else main.ControlMode.MANUAL
        return sequence

    def safety_stop(self):
        return self.motor.stop()

    def switch_mode(self, mode):
        sequence = self.motor.stop()
        ack = self.motor.gpio.wait_for_ack(sequence)
        if ack != "OK":
            self.motor.stop()
            self.motion_inhibited = True
            raise ModeSwitchError("STOP_ACK_TIMEOUT" if ack is None else "STOP_REJECTED")
        self.mode = main.ControlMode(mode)
        self.auto_active = False
        self.motion_inhibited = False
        self.state_version += 1
        return sequence

    def stop_all(self):
        sequence = self.motor.stop()
        self.mode = main.ControlMode.AUTO
        self.auto_active = False
        self.state_version += 1
        return sequence

    def start_auto(self):
        if self.mode != main.ControlMode.AUTO:
            raise ControlModeError("AUTO_MODE_REQUIRED")
        self.auto_active = True


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_services = main.services
        self.state_directory = tempfile.TemporaryDirectory()
        self.services_for_cleanup = []
        main.services = self.make_services(
            lambda: FakeRobotManager(FakeMotor(messages=["EVENT|0|READY"])),
            ":memory:",
        )
        self.token_env = patch.dict(os.environ, {"THASHU_API_TOKEN": "test-token"})
        self.token_env.start()

    def make_services(self, factory, db_path):
        service = main.ApiServices(factory, state_db_path=db_path)
        self.services_for_cleanup.append(service)
        return service

    async def asyncTearDown(self):
        for service in self.services_for_cleanup:
            pending = tuple(service._command_tasks)
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    def tearDown(self):
        self.token_env.stop()
        for service in self.services_for_cleanup:
            service.close_command_store()
        self.state_directory.cleanup()
        main.services = self.old_services

    def endpoint(self, path):
        return next(route.endpoint for route in main.app.routes if getattr(route, "path", None) == path)

    def test_error_details_get_stable_codes_without_losing_specific_fields(self):
        self.assertEqual(
            main._error_detail_with_code(503, {"error": "robot_unavailable", "command_id": "cmd-1"}),
            {
                "error": "robot_unavailable",
                "error_code": "ROBOT_UNAVAILABLE",
                "command_id": "cmd-1",
            },
        )
        self.assertEqual(
            main._error_detail_with_code(
                409,
                {"error": "control_mode_conflict", "error_code": "MANUAL_MODE_REQUIRED"},
            ),
            {"error": "control_mode_conflict", "error_code": "MANUAL_MODE_REQUIRED"},
        )
        self.assertEqual(
            main._error_detail_with_code(401, "unauthorized"),
            {"error": "unauthorized", "error_code": "UNAUTHORIZED"},
        )

    async def test_http_error_handler_keeps_codes_inside_detail(self):
        from fastapi import HTTPException
        import json

        response = await main.http_error_handler(
            None,
            HTTPException(
                status_code=503,
                detail={"error": "robot_unavailable", "command_id": "cmd-1"},
            ),
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body), {
            "detail": {
                "error": "robot_unavailable",
                "error_code": "ROBOT_UNAVAILABLE",
                "command_id": "cmd-1",
            }
        })

    async def test_validation_error_handler_uses_sanitized_detail_issues(self):
        import json
        from unittest.mock import Mock

        error = Mock()
        error.errors.return_value = [{
            "loc": ("body", "direction"),
            "msg": "Invalid direction",
            "type": "literal_error",
            "input": "secret-value",
        }]
        response = await main.validation_error_handler(None, error)
        body = json.loads(response.body)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(body, {
            "detail": {
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "issues": [{
                    "loc": ["body", "direction"],
                    "msg": "Invalid direction",
                    "type": "literal_error",
                }],
            }
        })

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
        main.services = self.make_services(
            lambda: (_ for _ in ()).throw(OSError("offline")), ":memory:"
        )
        try:
            status = await self.endpoint("/api/v1/status")()
            self.assertEqual(status["esp32_transport"], "unavailable")
            self.assertEqual(status["controller_readiness"], "unknown")
            self.assertEqual(status["control_mode"], "unknown")
        finally:
            main.services = old

    async def test_move_dispatches_through_motor_service(self):
        mode = await self.endpoint("/api/v1/robot/mode")(
            main.ModeSwitchRequest(mode="MANUAL")
        )
        self.assertEqual(mode.status, "switched")
        response = await self.endpoint("/api/v1/robot/move")(
            main.MoveRequest(
                request_id=UUID("11111111-1111-4111-8111-111111111111"),
                direction="forward",
                speed=120,
            )
        )
        self.assertEqual(response.request_id, "11111111-1111-4111-8111-111111111111")
        self.assertTrue(response.command_id)
        self.assertEqual(response.command, "forward")
        self.assertEqual(response.status, "dispatched")
        self.assertEqual(response.control_mode, "MANUAL")
        self.assertTrue(response.timestamp)
        manager = await main.services.robot_manager()
        motor = manager.motor
        self.assertEqual(motor.commands, [
            ("stop", None),
            ("forward", 120),
        ])

    async def test_move_requires_explicit_manual_mode(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as failure:
            await self.endpoint("/api/v1/robot/move")(
                main.MoveRequest(
                    request_id=UUID("22222222-2222-4222-8222-222222222222"),
                    direction="forward",
                    speed=120,
                )
            )
        self.assertEqual(failure.exception.status_code, 409)

    async def test_move_retry_reuses_command_and_does_not_redispatch(self):
        await main.services.switch_mode("MANUAL")
        move = self.endpoint("/api/v1/robot/move")
        request = main.MoveRequest(
            request_id=UUID("33333333-3333-4333-8333-333333333333"),
            direction="forward",
            speed=120,
        )

        original = await move(request)
        manager = await main.services.robot_manager()
        count_after_first = len(manager.motor.commands)
        retry = await move(request)

        self.assertEqual(retry.command_id, original.command_id)
        self.assertEqual(retry.request_id, original.request_id)
        self.assertEqual(retry.status, "dispatched")
        self.assertEqual(len(manager.motor.commands), count_after_first)

    async def test_move_retry_returns_latest_acknowledged_result(self):
        await main.services.switch_mode("MANUAL")
        move = self.endpoint("/api/v1/robot/move")
        request = main.MoveRequest(
            request_id=UUID("44444444-4444-4444-8444-444444444444"),
            direction="forward",
            speed=100,
        )
        original = await move(request)
        await main.services.track_command_ack(original.command_id, 1)

        retry = await move(request)

        self.assertEqual(retry.command_id, original.command_id)
        self.assertEqual(retry.status, "acknowledged")
        self.assertIsNone(retry.error_code)
        self.assertTrue(retry.timestamp)

    async def test_move_retry_survives_api_service_restart(self):
        state_directory = tempfile.TemporaryDirectory()
        db_path = os.path.join(state_directory.name, "commands.sqlite3")
        base_services = main.services
        original_services = self.make_services(
            lambda: FakeRobotManager(FakeMotor()),
            db_path,
        )
        main.services = original_services
        try:
            await original_services.switch_mode("MANUAL")
            request = main.MoveRequest(
                request_id=UUID("10101010-1010-4010-8010-101010101010"),
                direction="forward",
                speed=100,
            )
            original = await self.endpoint("/api/v1/robot/move")(request)
            await original_services.track_command_ack(original.command_id, 1)
            original_services.close_command_store()

            restarted_services = self.make_services(
                lambda: FakeRobotManager(FakeMotor()),
                db_path,
            )
            main.services = restarted_services
            retry = await self.endpoint("/api/v1/robot/move")(request)

            self.assertEqual(retry.command_id, original.command_id)
            self.assertEqual(retry.status, "acknowledged")
            self.assertIsNone(restarted_services._robot_manager)
        finally:
            main.services.close_command_store()
            original_services.close_command_store()
            main.services = base_services
            state_directory.cleanup()

    async def test_interrupted_request_becomes_unknown_without_redispatch(self):
        state_directory = tempfile.TemporaryDirectory()
        db_path = os.path.join(state_directory.name, "commands.sqlite3")
        request_id = "20202020-2020-4020-8020-202020202020"
        base_services = main.services
        original_services = self.make_services(
            lambda: FakeRobotManager(FakeMotor()),
            db_path,
        )
        main.services = original_services
        try:
            record, created = original_services.reserve_command_request(
                request_id,
                {"type": "move", "direction": "forward", "speed": 100},
                "forward",
                "MANUAL",
            )
            self.assertTrue(created)
            original_command_id = record["command_id"]
            original_services.register_command(
                original_command_id,
                "forward",
                "MANUAL",
                request_id=request_id,
            )
            original_services.close_command_store()

            restarted_services = self.make_services(
                lambda: FakeRobotManager(FakeMotor()),
                db_path,
            )
            main.services = restarted_services
            retry = await self.endpoint("/api/v1/robot/move")(
                main.MoveRequest(
                    request_id=UUID(request_id),
                    direction="forward",
                    speed=100,
                )
            )

            self.assertEqual(retry.command_id, original_command_id)
            self.assertEqual(retry.status, "unknown")
            self.assertEqual(retry.error_code, "PROCESS_RESTARTED_DURING_DISPATCH")
            self.assertIsNone(restarted_services._robot_manager)
            result = await self.endpoint("/api/v1/robot/commands/{command_id}")(
                original_command_id
            )
            self.assertEqual(result["status"], "unknown")
        finally:
            main.services.close_command_store()
            original_services.close_command_store()
            main.services = base_services
            state_directory.cleanup()

    def test_persisted_request_expires_after_24_hours(self):
        request_id = "80808080-8080-4080-8080-808080808080"
        record, created = main.services.reserve_command_request(
            request_id,
            {"type": "move", "direction": "forward", "speed": 100},
            "forward",
            "MANUAL",
        )
        self.assertTrue(created)
        connection = main.services._database()
        connection.execute(
            "UPDATE command_requests SET created_at = 1 WHERE request_id = ?",
            (request_id,),
        )

        self.assertIsNone(main.services.request_record(request_id))
        self.assertIsNone(main.services.command_result(record["command_id"]))

    async def test_simultaneous_move_retries_only_dispatch_once(self):
        await main.services.switch_mode("MANUAL")
        move = self.endpoint("/api/v1/robot/move")
        request = main.MoveRequest(
            request_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            direction="left",
            speed=90,
        )

        first, second = await asyncio.gather(move(request), move(request))

        manager = await main.services.robot_manager()
        self.assertEqual(first.command_id, second.command_id)
        self.assertEqual(
            manager.motor.commands,
            [("stop", None), ("left", 90)],
        )

    async def test_reusing_request_id_for_different_action_is_rejected(self):
        from fastapi import HTTPException

        await main.services.switch_mode("MANUAL")
        move = self.endpoint("/api/v1/robot/move")
        request_id = UUID("55555555-5555-4555-8555-555555555555")
        original = await move(main.MoveRequest(
            request_id=request_id,
            direction="forward",
            speed=100,
        ))
        manager = await main.services.robot_manager()
        command_count = len(manager.motor.commands)

        with self.assertRaises(HTTPException) as failure:
            await move(main.MoveRequest(
                request_id=request_id,
                direction="left",
                speed=100,
            ))

        self.assertEqual(failure.exception.status_code, 409)
        self.assertEqual(failure.exception.detail["error_code"], "REQUEST_ID_REUSED")
        self.assertEqual(len(manager.motor.commands), command_count)
        self.assertEqual(original.command, "forward")

    async def test_duplicate_rejected_move_does_not_dispatch_on_retry(self):
        from fastapi import HTTPException

        move = self.endpoint("/api/v1/robot/move")
        request = main.MoveRequest(
            request_id=UUID("66666666-6666-4666-8666-666666666666"),
            direction="forward",
            speed=100,
        )
        with self.assertRaises(HTTPException) as first:
            await move(request)
        manager = await main.services.robot_manager()
        count_after_first = len(manager.motor.commands)
        with self.assertRaises(HTTPException) as retry:
            await move(request)

        self.assertEqual(retry.exception.status_code, first.exception.status_code)
        self.assertEqual(retry.exception.detail, first.exception.detail)
        self.assertEqual(len(manager.motor.commands), count_after_first)

    async def test_stop_dispatches_dedicated_stop(self):
        manager = await main.services.robot_manager()
        await main.services.switch_mode("MANUAL")
        response = await self.endpoint("/api/v1/robot/stop")(
            main.StopRequest(request_id=UUID("abababab-abab-4bab-8bab-abababababab"))
        )
        self.assertEqual(response.command, "stop")
        self.assertEqual(response.status, "dispatched")
        self.assertEqual(response.control_mode, "AUTO")
        self.assertEqual(response.request_id, "abababab-abab-4bab-8bab-abababababab")
        self.assertTrue(response.timestamp)
        manager = await main.services.robot_manager()
        motor = manager.motor
        self.assertEqual(motor.commands, [
            ("stop", None),
            ("stop", None),
        ])

    async def test_stop_retry_reuses_id_and_new_stop_id_reasserts_stop(self):
        manager = await main.services.robot_manager()
        await main.services.switch_mode("MANUAL")
        stop = self.endpoint("/api/v1/robot/stop")
        request = main.StopRequest(
            request_id=UUID("30303030-3030-4030-8030-303030303030")
        )

        first = await stop(request)
        command_count = len(manager.motor.commands)
        retry = await stop(request)

        self.assertEqual(retry.command_id, first.command_id)
        self.assertEqual(len(manager.motor.commands), command_count)

        reasserted = await stop(main.StopRequest(
            request_id=UUID("40404040-4040-4040-8040-404040404040")
        ))
        self.assertNotEqual(reasserted.command_id, first.command_id)
        self.assertEqual(len(manager.motor.commands), command_count + 1)

    async def test_stop_retry_survives_api_service_restart(self):
        state_directory = tempfile.TemporaryDirectory()
        db_path = os.path.join(state_directory.name, "commands.sqlite3")
        base_services = main.services
        original_services = self.make_services(
            lambda: FakeRobotManager(FakeMotor()),
            db_path,
        )
        main.services = original_services
        request = main.StopRequest(
            request_id=UUID("60606060-6060-4060-8060-606060606060")
        )
        try:
            original = await self.endpoint("/api/v1/robot/stop")(request)
            await original_services.track_command_ack(original.command_id, 5)
            original_services.close_command_store()

            restarted_services = self.make_services(
                lambda: FakeRobotManager(FakeMotor()),
                db_path,
            )
            main.services = restarted_services
            retry = await self.endpoint("/api/v1/robot/stop")(request)

            self.assertEqual(retry.command_id, original.command_id)
            self.assertEqual(retry.status, "acknowledged")
            self.assertIsNone(restarted_services._robot_manager)
        finally:
            main.services.close_command_store()
            original_services.close_command_store()
            main.services = base_services
            state_directory.cleanup()

    async def test_interrupted_stop_becomes_unknown_without_redispatch(self):
        state_directory = tempfile.TemporaryDirectory()
        db_path = os.path.join(state_directory.name, "commands.sqlite3")
        request_id = "70707070-7070-4070-8070-707070707070"
        base_services = main.services
        original_services = self.make_services(
            lambda: FakeRobotManager(FakeMotor()),
            db_path,
        )
        main.services = original_services
        try:
            record, created = original_services.reserve_command_request(
                request_id,
                {"type": "stop"},
                "stop",
                "MANUAL",
            )
            self.assertTrue(created)
            command_id = record["command_id"]
            original_services.register_command(
                command_id,
                "stop",
                "MANUAL",
                request_id=request_id,
            )
            original_services.close_command_store()

            restarted_services = self.make_services(
                lambda: FakeRobotManager(FakeMotor()),
                db_path,
            )
            main.services = restarted_services
            retry = await self.endpoint("/api/v1/robot/stop")(
                main.StopRequest(request_id=UUID(request_id))
            )

            self.assertEqual(retry.command_id, command_id)
            self.assertEqual(retry.status, "unknown")
            self.assertEqual(retry.error_code, "PROCESS_RESTARTED_DURING_DISPATCH")
            self.assertIsNone(restarted_services._robot_manager)
        finally:
            main.services.close_command_store()
            original_services.close_command_store()
            main.services = base_services
            state_directory.cleanup()

    async def test_request_id_cannot_be_reused_between_move_and_stop(self):
        from fastapi import HTTPException

        await main.services.switch_mode("MANUAL")
        request_id = UUID("50505050-5050-4050-8050-505050505050")
        await self.endpoint("/api/v1/robot/move")(
            main.MoveRequest(request_id=request_id, direction="forward", speed=100)
        )
        with self.assertRaises(HTTPException) as conflict:
            await self.endpoint("/api/v1/robot/stop")(
                main.StopRequest(request_id=request_id)
            )
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(conflict.exception.detail["error_code"], "REQUEST_ID_REUSED")

    async def test_auto_mode_switch_stops_without_starting_follow(self):
        response = await self.endpoint("/api/v1/robot/mode")(
            main.ModeSwitchRequest(mode="AUTO")
        )
        manager = await main.services.robot_manager()
        self.assertEqual(response.mode, "AUTO")
        self.assertEqual(response.status, "switched")
        self.assertEqual(manager.mode, main.ControlMode.AUTO)
        self.assertEqual(manager.motor.commands, [("stop", None)])

    async def test_mode_switch_timeout_keeps_previous_mode_and_reports_failure(self):
        from fastapi import HTTPException

        manager = await main.services.robot_manager()
        manager.motor.gpio.ack_result = None
        with self.assertRaises(HTTPException) as failure:
            await self.endpoint("/api/v1/robot/mode")(
                main.ModeSwitchRequest(mode="MANUAL")
            )
        self.assertEqual(failure.exception.status_code, 503)
        self.assertEqual(failure.exception.detail["error_code"], "STOP_ACK_TIMEOUT")
        self.assertEqual(manager.mode, main.ControlMode.AUTO)
        self.assertEqual(manager.motor.commands, [
            ("stop", None),
            ("stop", None),
        ])

    async def test_mode_switch_rejection_inhibits_motion_until_confirmed_switch(self):
        from fastapi import HTTPException

        manager = await main.services.robot_manager()
        manager.mode = main.ControlMode.MANUAL
        manager.motor.gpio.ack_result = "ERROR|SAFETY_STOP"
        with self.assertRaises(HTTPException):
            await self.endpoint("/api/v1/robot/mode")(
                main.ModeSwitchRequest(mode="AUTO")
            )
        with self.assertRaises(HTTPException) as blocked:
            await self.endpoint("/api/v1/robot/move")(
                main.MoveRequest(
                    request_id=UUID("77777777-7777-4777-8777-777777777777"),
                    direction="forward",
                    speed=100,
                )
            )
        self.assertEqual(blocked.exception.status_code, 409)
        self.assertEqual(manager.motor.commands, [
            ("stop", None),
            ("stop", None),
        ])

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
            main.MoveRequest(
                request_id=UUID("88888888-8888-4888-8888-888888888888"),
                direction="spin",
                speed=100,
            )
        with self.assertRaises(Exception):
            main.MoveRequest(
                request_id=UUID("99999999-9999-4999-8999-999999999999"),
                direction="forward",
                speed=256,
            )

    def test_move_request_requires_uuid_request_id(self):
        with self.assertRaises(Exception):
            main.MoveRequest(direction="forward", speed=100)
        with self.assertRaises(Exception):
            main.MoveRequest(
                request_id="not-a-uuid",
                direction="forward",
                speed=100,
            )

    def test_stop_request_requires_uuid_request_id(self):
        with self.assertRaises(Exception):
            main.StopRequest()
        with self.assertRaises(Exception):
            main.StopRequest(request_id="invalid")

    def test_openapi_marks_move_request_id_required(self):
        schema = main.app.openapi()
        move_schema = schema["paths"]["/api/v1/robot/move"]["post"]
        request_ref = move_schema["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        model_name = request_ref.rsplit("/", 1)[-1]
        model_schema = schema["components"]["schemas"][model_name]
        self.assertIn("request_id", model_schema["required"])
        self.assertEqual(model_schema["properties"]["request_id"]["format"], "uuid")

        stop_schema_ref = schema["paths"]["/api/v1/robot/stop"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        stop_model = schema["components"]["schemas"][stop_schema_ref.rsplit("/", 1)[-1]]
        self.assertIn("request_id", stop_model["required"])

    def test_openapi_documents_command_body_limit(self):
        schema = main.app.openapi()
        for path in ("/api/v1/robot/move", "/api/v1/robot/stop", "/api/v1/robot/mode"):
            with self.subTest(path=path):
                operation = schema["paths"][path]["post"]
                self.assertIn("413", operation["responses"])
                content = operation["responses"]["413"]["content"]["application/json"]
                self.assertEqual(
                    content["example"],
                    {"detail": {
                        "error": "request_body_too_large",
                        "error_code": "PAYLOAD_TOO_LARGE",
                    }},
                )
                self.assertIn("422", operation["responses"])

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
            {
                "type": "http", "method": "POST", "path": "/api/v1/robot/move",
                "headers": [(b"content-type", b"application/json")],
            },
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
            {
                "type": "http", "method": "POST", "path": "/api/v1/robot/move",
                "headers": [(b"content-type", b"application/json; charset=utf-8")],
            },
            receive,
            send,
        )

        self.assertEqual(len(received), 4096)

    async def test_command_body_rejects_missing_or_non_json_content_type(self):
        for headers in ([], [(b"content-type", b"text/plain")]):
            with self.subTest(headers=headers):
                reached_route = False
                sent = []

                async def app(_scope, _receive, _send):
                    nonlocal reached_route
                    reached_route = True

                async def receive():
                    return {"type": "http.request", "body": b"{}", "more_body": False}

                async def send(message):
                    sent.append(message)

                middleware = main.CommandBodySizeLimitMiddleware(app)
                await middleware(
                    {
                        "type": "http", "method": "POST", "path": "/api/v1/robot/move",
                        "headers": headers,
                    },
                    receive,
                    send,
                )

                self.assertFalse(reached_route)
                self.assertEqual(sent[0]["status"], 415)
                self.assertIn(b"unsupported_media_type", sent[1]["body"])


if __name__ == "__main__":
    unittest.main()
