"""
audio_manager.py — Thashu Voice Pipeline
Owns the microphone stream. Provides raw int16 chunks at 48 kHz via a queue.

Key design decisions:
- Device selection uses a priority-ordered preferred-name list with exact-match
  preference over substring match, and 48 kHz support as a tiebreaker.
- Watchdog thread restarts the stream on device error or disconnect.
- Queue drops are logged (not silently discarded).
- pause()/resume() use close/reopen instead of stop/start to avoid
  ALSA undefined-behavior on Raspberry Pi.
"""

import queue
import threading
import time

import numpy as np
import sounddevice as sd


# ── Configuration ─────────────────────────────────────────────────────────────

SAMPLE_RATE  = 48_000          # Hz — mic native rate; do not change
BLOCKSIZE    = 5_460           # samples; 113.75 ms per chunk (divisible by 3 for 16k resample)
CHANNELS     = 1
DTYPE        = "int16"
QUEUE_MAXLEN = 40              # chunks; ~4.5 s of audio before dropping
WATCHDOG_INTERVAL = 2.0        # seconds between watchdog checks

# Device preference list — checked in order, case-insensitive.
# First entry that matches any connected input device wins.
# Exact name match scores higher than substring match within each entry.
# Among equal-scoring candidates, devices supporting 48 kHz are preferred.
PREFERRED_DEVICES = [
    "Generalplus USB Audio Device",   # primary mic — exact name preferred
    "USB Audio Device",               # generic fallback before other USB devices
    "USB",                            # last-resort USB catch-all
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def list_input_devices() -> list[dict]:
    """Return all input-capable devices for diagnostics."""
    return [
        {
            "index":       i,
            "name":        d["name"],
            "channels":    d["max_input_channels"],
            "default_rate": d["default_samplerate"],
        }
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] >= 1
    ]


def _supports_48k(dev: dict) -> bool:
    """
    Best-effort check whether a device supports 48 kHz input.
    sounddevice doesn't expose a supported-rates list; we use default_samplerate
    as a proxy. This is accurate for most USB audio devices — if the device
    defaults to 48 kHz, it almost certainly supports it.
    """
    return int(dev.get("default_samplerate", 0)) == 48_000


def find_input_device(preferred: list[str]) -> int | None:
    """
    Select the best input device from all connected devices.

    Selection algorithm (applied per preferred-name entry in order):
      1. Exact name match (case-insensitive) + supports 48 kHz  → score 4
      2. Exact name match (case-insensitive)                     → score 3
      3. Substring match + supports 48 kHz                       → score 2
      4. Substring match                                         → score 1

    The first preferred entry that yields at least one candidate wins.
    Within that entry's candidates the highest-score device is selected.
    Ties are broken by device index (lower = more stable on ALSA).

    Logs every candidate and the final selection.
    Returns the winning device index, or None if nothing matches.
    """
    all_inputs = [
        (i, d)
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] >= 1
    ]

    if not all_inputs:
        print("[AUDIO] No input devices found at all.")
        return None

    print("[AUDIO] Available input devices:")
    for idx, dev in all_inputs:
        rate = int(dev["default_samplerate"])
        print(f"  [{idx}] {dev['name']!r}  "
              f"ch={dev['max_input_channels']}  default_rate={rate} Hz")

    for preference in preferred:
        pref_lower = preference.lower()
        candidates = []

        for idx, dev in all_inputs:
            name_lower = dev["name"].lower()
            exact = name_lower == pref_lower
            substr = pref_lower in name_lower

            if not (exact or substr):
                continue

            has_48k = _supports_48k(dev)
            if exact and has_48k:
                score = 4
            elif exact:
                score = 3
            elif has_48k:
                score = 2
            else:
                score = 1

            candidates.append((score, idx, dev["name"]))
            print(f"[AUDIO] Candidate: [{idx}] {dev['name']!r}  "
                  f"score={score}  48kHz={has_48k}  "
                  f"({'exact' if exact else 'substring'} match for {preference!r})")

        if candidates:
            candidates.sort(key=lambda c: (-c[0], c[1]))   # highest score, lowest index
            _, winning_idx, winning_name = candidates[0]
            print(f"[AUDIO] Selected: [{winning_idx}] {winning_name!r}  "
                  f"(matched preference {preference!r})")
            return winning_idx

    print(f"[AUDIO] No device matched any preference in {preferred}.")
    return None


# ── AudioManager ──────────────────────────────────────────────────────────────

class AudioManager:
    """
    Manages the microphone input stream.

    Usage:
        am = AudioManager()
        am.start()
        chunk = am.read()   # returns np.ndarray (int16, shape=(BLOCKSIZE,)) or None
        am.stop()

    Thread safety:
        read() and drain() are safe to call from any thread.
        start()/stop()/pause()/resume() should be called from one thread only.
    """

    def __init__(
        self,
        sample_rate:      int        = SAMPLE_RATE,
        blocksize:        int        = BLOCKSIZE,
        preferred_devices: list[str] = PREFERRED_DEVICES,
    ):
        self.sample_rate       = sample_rate
        self.blocksize         = blocksize
        self.preferred_devices = preferred_devices

        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=QUEUE_MAXLEN)
        self._stream: sd.InputStream | None  = None
        self._paused      = False
        self._running     = False
        self._device_idx: int | None = None

        # Counters for diagnostics
        self._overflow_count   = 0
        self._queue_drop_count = 0

        # Watchdog
        self._watchdog_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── Device resolution ─────────────────────────────────────────────────────

    def _resolve_device(self) -> int:
        idx = find_input_device(self.preferred_devices)
        if idx is not None:
            return idx

        # Fallback: system default input
        default = sd.default.device[0]
        if default is not None and default >= 0:
            name = sd.query_devices(default)["name"]
            print(f"[AUDIO] No preferred device found. Falling back to system default: "
                  f"[{default}] {name!r}")
            return default

        raise RuntimeError(
            f"[AUDIO] No input device found matching {self.preferred_devices}. "
            f"Available: {list_input_devices()}"
        )

    # ── Callback ──────────────────────────────────────────────────────────────

    def _callback(self, indata, frames, time_info, status):
        if status:
            # status.input_overflow is the common case; log sparingly
            self._overflow_count += 1
            if self._overflow_count % 20 == 1:
                print(f"[AUDIO] PortAudio status flags: {status} (x{self._overflow_count} total)")

        chunk = indata.copy().flatten()   # shape: (blocksize,), dtype int16

        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            self._queue_drop_count += 1
            if self._queue_drop_count % 20 == 1:
                print(f"[AUDIO] Queue full — dropping chunk (x{self._queue_drop_count} total). "
                      f"Consumer too slow?")

    # ── Stream lifecycle ──────────────────────────────────────────────────────

    def _open_stream(self) -> sd.InputStream:
        return sd.InputStream(
            samplerate = self.sample_rate,
            channels   = CHANNELS,
            dtype      = DTYPE,
            blocksize  = self.blocksize,
            device     = self._device_idx,
            callback   = self._callback,
        )

    def start(self):
        """Open the mic and start streaming. Launches the watchdog."""
        self._overflow_count   = 0
        self._queue_drop_count = 0
        self._running = True
        self._paused  = False
        self._stop_event.clear()

        self._device_idx = self._resolve_device()
        self._stream = self._open_stream()
        self._stream.start()
        print("[AUDIO] Stream started")

        self._watchdog_thread = threading.Thread(
            target=self._watchdog, daemon=True, name="audio-watchdog"
        )
        self._watchdog_thread.start()

    def stop(self):
        """Stop streaming and shut down the watchdog."""
        self._running = False
        self._stop_event.set()

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                print(f"[AUDIO] Error closing stream: {e}")
            self._stream = None

        print("[AUDIO] Stream stopped")

    def pause(self):
        """
        Close the mic during TTS/brain processing to avoid self-triggering.
        Safer than stop/start on ALSA — we fully close and will reopen on resume().
        """
        if self._stream and not self._paused:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                print(f"[AUDIO] Error pausing stream: {e}")
            self._stream = None
            self._paused = True
            self.drain()
            print("[AUDIO] Paused")

    def resume(self):
        """
        Reopen the mic after TTS/brain has finished.
        Uses the device index already resolved at start() — no re-enumeration.
        Re-enumeration only happens in start() and the watchdog (on actual disconnect).
        """
        if self._paused and self._running:
            self.drain()
            self._overflow_count = 0
            try:
                # _device_idx is already set from start(); do not call _resolve_device()
                # here — that re-enumerates all devices and prints the full listing on
                # every pause/resume cycle, which is unnecessary and noisy.
                self._stream = self._open_stream()
                self._stream.start()
                self._paused = False
                print(f"[AUDIO] Resumed (device [{self._device_idx}])")
            except Exception as e:
                print(f"[AUDIO] Resume failed: {e}")

    # ── Watchdog ──────────────────────────────────────────────────────────────

    def _watchdog(self):
        """
        Periodically checks whether the stream is still alive.
        Attempts to restart it if the device disappeared and came back.

        Race condition fixed (was causing PortAudioError -9988):
          pause() closes and nulls self._stream, then sets self._paused = True.
          Between the `if self._paused` guard and the `self._stream.active` call,
          pause() can close the stream — leaving a non-None pointer that raises
          "Invalid stream pointer" on .active. Three fixes:
          1. try/except around .active catches the error if the race fires.
          2. Re-check _paused after stream_ok to abort before entering restart
             when pause() fired between the guard and the stream_ok test.
          3. Re-check _paused/_running after each sleep() inside the restart
             loop so a pause/stop during backoff doesn't trigger a spurious
             stream open that races with resume().
        """
        while not self._stop_event.wait(WATCHDOG_INTERVAL):
            if self._paused or not self._running:
                continue

            # Fix 1: wrap .active — pause() may close the stream between the
            # `_paused` guard above and this line, leaving an invalid pointer.
            try:
                stream_ok = self._stream is not None and self._stream.active
            except Exception as e:
                print(f"[AUDIO] Watchdog: error reading stream state: {e}")
                stream_ok = False

            if stream_ok:
                continue

            # Fix 2: re-check after stream_ok — pause() may have just fired.
            if self._paused or not self._running:
                continue

            print("[AUDIO] Watchdog: stream not active — attempting restart")
            for attempt in range(5):
                try:
                    time.sleep(1.0 * (attempt + 1))   # back off between retries

                    # Fix 3: re-check after sleep — pause/stop may have been
                    # called during the backoff window.
                    if self._paused or not self._running:
                        print("[AUDIO] Watchdog: restart aborted (paused or stopped)")
                        break

                    self._device_idx = self._resolve_device()
                    self.drain()
                    self._overflow_count = 0
                    self._stream = self._open_stream()
                    self._stream.start()
                    print(f"[AUDIO] Watchdog: stream restarted (attempt {attempt + 1})")
                    break
                except Exception as e:
                    print(f"[AUDIO] Watchdog: restart attempt {attempt + 1} failed: {e}")
            else:
                print("[AUDIO] Watchdog: could not restart after 5 attempts. "
                      "Mic may be disconnected.")

    # ── Consumer API ──────────────────────────────────────────────────────────

    def read(self, timeout: float = 0.1) -> np.ndarray | None:
        """
        Return the next audio chunk (int16 numpy array, shape=(blocksize,)),
        or None if no chunk is available within `timeout` seconds.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self):
        """Discard all queued audio (call before/after pause to clear stale data)."""
        discarded = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break
        if discarded:
            print(f"[AUDIO] Drained {discarded} stale chunks")
