"""
wake_word.py — Thashu Voice Pipeline
Wake word detection using openWakeWord's pretrained "hey jarvis" model.

Key design decisions:
- melspec_model_path/embedding_model_path point at local copies in
  models/openwakeword/ *if present*, so Model() doesn't hit the network on
  boot on a robot with no guaranteed internet at startup. If those two
  files aren't there, we fall back to openWakeWord's own default behavior
  (its bundled resource path, downloading on first use if needed) rather
  than crashing — this project doesn't ship those files, so fresh checkouts
  must not assume they exist. Run once with internet to fetch them locally:
      python3 -c "from openwakeword.utils import download_models as d; d()"
  then copy melspectrogram.onnx and embedding_model.onnx out of wherever
  that prints into models/openwakeword/ for permanent offline use.
- Resampling mirrors vad.py exactly (48 kHz -> 16 kHz via resample_poly,
  down=3), since openWakeWord's models are trained on 16 kHz audio.
- predict() is called on every unlocked, off-cooldown chunk, gated or not.
  openWakeWord's Model keeps a stateful rolling buffer across calls (raw
  audio -> melspectrogram -> embedding) to build the ~1s window it needs
  to recognize a word. An earlier version of this file gated quiet chunks
  out before predict() to save CPU; that punched gaps in the buffer on
  every soft syllable onset (the "h" in "hey", the dip between "jar" and
  "vis") and was the root cause of both missed activations and false
  triggers. Inference is cheap enough to run unconditionally.
- lock()/unlock() let main.py suppress detection during TTS playback and
  STT transcription, so Thashu can't hear itself say "jarvis" mid-response.
  cooldown after unlock() additionally absorbs the mic settling time from
  safe_play()/audio.resume() before detection resumes.
- process() never raises — a bad chunk should drop one detection window,
  not take down the main loop (same fail-safe posture as VAD.is_speech()).
- Detection requires `consecutive_hits` chunks in a row scoring above
  threshold (default 2) AND a stateless WebRTC VAD check on the same
  chunk. These two guards catch different failure modes:
    * consecutive_hits rejects brief impulse noise (clap, bump) — it spikes
      one chunk but essentially never a second, since a single transient
      barely overlaps between chunks.
    * the VAD check rejects sustained tonal noise (fan hum, servo whine,
      appliance drone) — which consecutive_hits CANNOT catch. openWakeWord
      scores off roughly the last ~1.2s of audio, so with ~113ms chunks,
      two consecutive calls share ~90% of the same window; a steady tone
      that fools the model once will fool it identically next chunk too,
      passing any N-in-a-row requirement. WebRTC VAD's speech/noise model
      is a genuinely independent signal — a continuous single-frequency
      hum reliably fails it while real speech formants pass — so it's the
      actual fix, not a bigger streak count.
  This uses its own bare webrtcvad.Vad instance, not vad.py's
  VoiceActivityDetector — that one has 6-chunk (~680ms) hysteresis before
  re-entering speech state, tuned for extending command recording, which
  would make wake-word response feel sluggish. Wake word needs a fast,
  stateless "does this chunk look like speech" check, not smoothed state.
  Aggressiveness and fraction threshold are copied from vad.py's own
  hardware-tested values (mode 3, fraction 0.4) rather than chosen fresh —
  an earlier version used mode 2 / fraction 0.3 and speech_like was True
  on essentially every chunk, including hundreds of consecutive frames of
  dead silence in a real deployment log. vad.py had already documented
  why: with 3 frames per chunk the only possible voiced ratios are
  0/0.333/0.667/1.0, so any fraction in (0.334, 0.666] moves the decision
  boundary nowhere, and mode 2 is provably too lenient for this mic's
  noise floor. Don't relax either value without re-checking a real log.
"""

import os
import threading
import time

import numpy as np
import webrtcvad
from scipy.signal import resample_poly
from openwakeword.model import Model


# ── Constants ─────────────────────────────────────────────────────────────────

INPUT_RATE    = 48_000
TARGET_RATE   = 16_000
RESAMPLE_DOWN = INPUT_RATE // TARGET_RATE   # = 3

# WebRTC VAD requires 10/20/30ms frames at 8/16/32 kHz — same constraint as
# vad.py. 30ms at 16 kHz = 480 samples = 960 bytes (int16).
_VAD_FRAME_SAMPLES = 480
_VAD_FRAME_BYTES   = _VAD_FRAME_SAMPLES * 2

# Fraction of frames in a chunk that must be voiced for the chunk to count
# as speech-like. No smoothing/hysteresis — see module docstring for why.
# Matches vad.py's SPEECH_THRESHOLD exactly: with only 3 frames per chunk,
# the only possible ratios are 0, 0.333, 0.667, 1.0, so anything in
# (0.334, 0.666] moves the boundary nowhere — 0.4 is the smallest value
# that actually requires 2 of 3 frames instead of just 1.
_VAD_SPEECH_FRACTION = 0.4

# Local copies of the shared openWakeWord support models, used only if
# present — see module docstring for how to fetch them once.
_OWW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "openwakeword",
)
_MELSPEC_LOCAL   = os.path.join(_OWW_DIR, "melspectrogram.onnx")
_EMBEDDING_LOCAL = os.path.join(_OWW_DIR, "embedding_model.onnx")
_HAVE_LOCAL_SUPPORT_MODELS = os.path.isfile(_MELSPEC_LOCAL) and os.path.isfile(_EMBEDDING_LOCAL)


# ── WakeWordEngine ───────────────────────────────────────────────────────────

class WakeWordEngine:
    """
    Detects a wake word ("hey jarvis" by default) in a stream of 48 kHz
    int16 audio chunks.

    Usage:
        wake = WakeWordEngine(model_path="models/wake_word/hey_jarvis_v0.1.onnx")
        if wake.process(chunk):
            ...  # wake word heard

        wake.lock()    # suppress detection during TTS / STT
        ...
        wake.unlock()  # re-arm, starting the cooldown window
    """

    def __init__(
        self,
        model_path:        str,
        threshold:         float = 0.5,
        cooldown:          float = 4.0,
        consecutive_hits:  int = 2,
    ):
        self.threshold         = threshold
        self.cooldown          = cooldown
        self.consecutive_hits  = consecutive_hits
        self._hit_streak       = 0
        self._recent_speech_chunks = 0  # Tracks recent speech frames to sync VAD with Wake Word score timing

        oww_kwargs = {}
        if _HAVE_LOCAL_SUPPORT_MODELS:
            oww_kwargs["melspec_model_path"]   = _MELSPEC_LOCAL
            oww_kwargs["embedding_model_path"] = _EMBEDDING_LOCAL
        else:
            print(
                "[WAKE] Warning: models/openwakeword/{melspectrogram,embedding_model}.onnx "
                "not found. Falling back to openWakeWord's default support-model path — "
                "this may try to download them over the network on first use. See the "
                "module docstring in wake_word.py to fetch them once and go fully offline."
            )

        self.model = Model(
            wakeword_models=[model_path],
            inference_framework="onnx",
            **oww_kwargs,
        )

        # Stateless, deliberately un-smoothed — see module docstring.
        # Aggressiveness 3 (max), matching vad.py's own hardware-tested
        # tuning for this mic — mode 2 passed background noise essentially
        # unfiltered in testing.
        self._vad = webrtcvad.Vad(3)

        # openWakeWord keys predictions by model name (derived from the
        # filename), not by the path we passed in — resolve it once here.
        self.model_name = list(self.model.models.keys())[0]

        self.last_detected = 0.0
        self.lock_event = threading.Event()

        print(f"[WAKE] Initialized (model={self.model_name!r})")

    # ── Lock / cooldown control ─────────────────────────────────────────────

    def lock(self):
        """Suppress detection entirely — call before TTS/STT so Thashu can't self-trigger."""
        self.lock_event.set()

    def unlock(self):
        """
        Re-arm detection and start the cooldown window.

        Stamping last_detected here (not just on a real detection) means the
        mic-settling time after audio.resume() is also covered by cooldown,
        not just the post-detection window.
        """
        self.last_detected = time.time()
        self._hit_streak = 0
        self._recent_speech_chunks = 0
        self.lock_event.clear()

    # ── Detection ────────────────────────────────────────────────────────────

    def _looks_like_speech(self, audio16: np.ndarray) -> bool:
        """
        Fresh per-chunk WebRTC VAD check, no state carried between calls.
        Used only to corroborate a high wake word score, never to gate what
        reaches the model (see module docstring).
        """
        raw = audio16.tobytes()
        voiced, total = 0, 0
        for i in range(0, len(raw) - _VAD_FRAME_BYTES + 1, _VAD_FRAME_BYTES):
            frame = raw[i : i + _VAD_FRAME_BYTES]
            total += 1
            if self._vad.is_speech(frame, TARGET_RATE):
                voiced += 1
        return total > 0 and (voiced / total) > _VAD_SPEECH_FRACTION

    def process(self, audio_chunk: np.ndarray | None) -> bool:
        """
        Feed one 48 kHz int16 chunk from AudioManager. Returns True the
        instant the wake word is detected, False otherwise.

        None/lock/cooldown checks run before resampling or inference, in
        that order, so a locked or cooling-down chunk costs as little CPU
        as possible. Every other chunk is resampled and fed to the model
        unconditionally — see the module docstring for why this must not
        be gated by volume.
        """
        if audio_chunk is None:
            return False

        if self.lock_event.is_set():
            return False

        if time.time() - self.last_detected < self.cooldown:
            return False

        if audio_chunk.dtype != np.int16:
            print(f"[WAKE] Warning: expected int16, got {audio_chunk.dtype}. "
                  f"Converting — check AudioManager dtype.")
            audio_chunk = audio_chunk.astype(np.int16)

        try:
            # ── Resample 48 kHz → 16 kHz ─────────────────────────────────────
            # Unconditional — no volume gate. See module docstring.
            audio16 = resample_poly(audio_chunk, 1, RESAMPLE_DOWN).astype(np.int16)

            # ── Inference ─────────────────────────────────────────────────────
            prediction = self.model.predict(audio16)
            score = prediction[self.model_name]

            # ── VAD corroboration ────────────────────────────────────────────
            # Independent of the score above — see module docstring for why
            # this, and not a larger consecutive_hits, is what rejects
            # sustained tonal false triggers.
            speech_like = self._looks_like_speech(audio16)

            # Maintain a 5-chunk (~500ms) hangover so VAD stays true while openWakeWord catches up
            if speech_like:
                self._recent_speech_chunks = 5
            else:
                self._recent_speech_chunks = max(0, self._recent_speech_chunks - 1)

            recent_speech = self._recent_speech_chunks > 0

        except Exception as e:
            print(f"[WAKE] Error in process: {e}")
            return False

        print(f"[WAKE] score={score:.3f} speech_like={speech_like} recent_speech={recent_speech}")

        if score >= self.threshold and recent_speech:
            self._hit_streak += 1
        else:
            self._hit_streak = 0

        if self._hit_streak >= self.consecutive_hits:
            self.last_detected = time.time()
            self._hit_streak = 0
            print("[WAKE] Detected!")
            return True

        return False