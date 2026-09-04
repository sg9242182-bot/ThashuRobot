import subprocess
import threading

DEVICE  = "default"
_lock   = threading.Lock()


def _play(path: str):
    """Internal — plays a wav file, blocks until done."""
    try:
        subprocess.run(
            ["aplay", "-D", DEVICE, "--quiet", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[SOUND ERROR]: {e}")


def play(path: str, blocking: bool = True):
    """
    Play a sound file. Only one sound plays at a time.
    blocking=True  → waits until sound finishes (e.g. startup)
    blocking=False → plays in background thread (e.g. beep)
    """
    if blocking:
        with _lock:
            _play(path)
    else:
        def _run():
            with _lock:
                _play(path)
        threading.Thread(target=_run, daemon=True).start()