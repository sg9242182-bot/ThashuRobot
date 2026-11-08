import threading
import unittest
from unittest.mock import Mock

from thashu.core.api_lifecycle import request_server_shutdown, wait_for_server_start


class FakeServer:
    def __init__(self, *, started=False, should_exit=False):
        self.started = started
        self.should_exit = should_exit


class ApiLifecycleTests(unittest.TestCase):
    def test_start_wait_succeeds_after_server_started(self):
        self.assertTrue(wait_for_server_start(FakeServer(started=True)))

    def test_start_wait_stops_when_exit_requested(self):
        self.assertFalse(
            wait_for_server_start(FakeServer(should_exit=True), timeout=1.0)
        )

    def test_start_wait_times_out_when_server_never_starts(self):
        self.assertFalse(
            wait_for_server_start(FakeServer(), timeout=0.002, poll_interval=0.0005)
        )

    def test_shutdown_requests_exit_and_waits_for_thread(self):
        server = FakeServer()
        thread = Mock()
        thread.is_alive.return_value = False

        self.assertTrue(request_server_shutdown(server, thread, timeout=3.0))
        self.assertTrue(server.should_exit)
        thread.join.assert_called_once_with(timeout=3.0)

    def test_shutdown_reports_thread_that_did_not_exit(self):
        server = FakeServer()
        thread = Mock()
        thread.is_alive.return_value = True

        self.assertFalse(request_server_shutdown(server, thread, timeout=0.01))

    def test_shutdown_from_server_thread_does_not_self_join(self):
        server = FakeServer()
        thread = threading.current_thread()

        self.assertFalse(request_server_shutdown(server, thread))
        self.assertTrue(server.should_exit)


if __name__ == "__main__":
    unittest.main()
