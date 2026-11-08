"""Small, testable helpers for starting and stopping the embedded Pi API."""

import threading
import time


def wait_for_server_start(server, timeout=5.0, poll_interval=0.01):
    """Wait for Uvicorn's startup signal, stopping early if shutdown is requested."""
    deadline = time.monotonic() + timeout
    while not getattr(server, "started", False):
        if getattr(server, "should_exit", False) or time.monotonic() >= deadline:
            return False
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
    return True


def request_server_shutdown(server, thread, timeout=5.0):
    """Request graceful shutdown and report whether the server thread exited."""
    server.should_exit = True
    if thread is None or thread is threading.current_thread():
        return thread is None
    thread.join(timeout=timeout)
    return not thread.is_alive()
