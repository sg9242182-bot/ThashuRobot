"""GPIO 17 short-click/long-hold actions shared by the BLE setup service."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


BUTTON_PIN = 17
HOLD_SECONDS = 3.0
MIN_CLICK_SECONDS = 0.06
SHUTDOWN_GRACE_SECONDS = 8.0


class ButtonGesture:
    """Map a debounced short click to BLE and a 3-second hold to shutdown."""

    def __init__(
        self,
        hold_seconds: float = HOLD_SECONDS,
        min_click_seconds: float = MIN_CLICK_SECONDS,
    ) -> None:
        if min_click_seconds < 0 or hold_seconds <= min_click_seconds:
            raise ValueError("hold_seconds must exceed a non-negative click debounce")
        self.hold_seconds = hold_seconds
        self.min_click_seconds = min_click_seconds
        self._pressed_at: float | None = None
        self._shutdown_latched = False

    def update(self, pressed: bool, now: float) -> str | None:
        """Return ``ble`` on short-click release or ``shutdown`` after a hold."""
        if self._shutdown_latched:
            return None

        if pressed:
            if self._pressed_at is None:
                self._pressed_at = now
                return None
            if now - self._pressed_at >= self.hold_seconds:
                self._shutdown_latched = True
                return "shutdown"
            return None

        if self._pressed_at is None:
            return None

        duration = now - self._pressed_at
        self._pressed_at = None
        if duration >= self.hold_seconds:
            self._shutdown_latched = True
            return "shutdown"
        if self.min_click_seconds <= duration < self.hold_seconds:
            return "ble"
        return None


def _is_robot_main_process(pid: int, project_dir: Path) -> bool:
    """Match main.py only when it belongs to this Thashu checkout."""
    process_dir = Path("/proc") / str(pid)
    try:
        args = [
            part.decode("utf-8", errors="replace")
            for part in (process_dir / "cmdline").read_bytes().split(b"\0")
            if part
        ]
        cwd = (process_dir / "cwd").resolve()
    except OSError:
        return False

    expected_script = project_dir / "main.py"
    for arg in args[1:]:
        script = Path(arg)
        if script.name != "main.py":
            continue
        if (script if script.is_absolute() else cwd / script).resolve() == expected_script:
            return True
    return False


def request_robot_shutdown(project_dir: Path | None = None) -> None:
    """Let main.py run its cleanup, then power off the Pi."""
    project_dir = project_dir or Path(__file__).resolve().parents[1]
    robot_pid = next(
        (
            int(entry.name)
            for entry in Path("/proc").iterdir()
            if entry.name.isdigit()
            and int(entry.name) != os.getpid()
            and _is_robot_main_process(int(entry.name), project_dir)
        ),
        None,
    )

    if robot_pid is not None:
        try:
            os.kill(robot_pid, signal.SIGINT)
            deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
            while time.monotonic() < deadline and _is_robot_main_process(robot_pid, project_dir):
                time.sleep(0.1)
            if _is_robot_main_process(robot_pid, project_dir):
                print("[SYSTEM] Robot cleanup exceeded 8 seconds; continuing power-off.")
            else:
                print("[SYSTEM] Robot cleanup completed.")
        except ProcessLookupError:
            pass
        except PermissionError:
            print("[SYSTEM] Could not signal the robot process; continuing power-off.")
    else:
        print("[SYSTEM] Robot process is not running; powering off the Pi.")

    try:
        result = subprocess.run(
            ["shutdown", "now"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("[SYSTEM] Power-off request failed.")
        return
    if result.returncode != 0:
        print("[SYSTEM] Power-off request failed.")
