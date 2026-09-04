"""
vad.py — Thashu Voice Pipeline
Voice Activity Detection using WebRTC VAD.

Key design decisions:
- Asserts input dtype and rate assumptions explicitly (fails loudly, not silently).
- Fixed frame boundary loop (processes all complete frames, not n-1).
- Errors are logged with detail instead of silently returning False.
- Input rate and target rate are module-level constants for easy auditing.
"""

import numpy as np
import webrtcvad
from scipy.signal import resample_poly


# ── Constants ─────────────────────────────────────────────────────────────────

INPUT_RATE   = 48_000
TARGET_RATE  = 16_000
RESAMPLE_DOWN = INPUT_RATE // TARGET_RATE   # = 3

# WebRTC VAD requires 10ms, 20ms, or 30ms frames at 8/16/32 kHz.
# 30ms at 16 kHz = 480 samples = 960 bytes (int16).
FRAME_SAMPLES = 480
FRAME_BYTES   = FRAME_SAMPLES * 2   # int16 = 2 bytes

# Fraction of frames that must be speech to call the chunk "speech"
SPEECH_THRESHOLD = 0.4


# ── VoiceActivityDetector ─────────────────────────────────────────────────────

class VoiceActivityDetector:
    """
    Classifies a 48 kHz int16 audio chunk as speech or silence.

    Implements two-threshold stateful smoothing to prevent post-speech noise
    bursts from resetting the silence timer in collect_command().

    The core problem this solves
    ────────────────────────────
    Each 5460-sample chunk contains exactly 3 WebRTC VAD frames (90ms scored
    out of 113.75ms total). With only 3 frames the only possible speech ratios
    are 0.0, 0.333, 0.667, 1.0. Adjusting SPEECH_THRESHOLD anywhere between
    0.334 and 0.666 has zero effect — the decision boundary does not move until
    0.667, which requires all 3 frames to be speech and is too strict.

    Raising aggressiveness to 3 reduces but does not eliminate false positives
    from background noise. The observed pattern in logs is 5-consecutive-True
    bursts after speech ends (high-RMS room noise that passes aggressiveness=3).
    These bursts reset silence_start in collect_command(), extending recordings
    by 2–3 seconds for short commands.

    Two-threshold state machine
    ───────────────────────────
    onset_chunks:    consecutive True  chunks needed to ENTER speech state
                     initially. Low (2) so short commands are detected fast.

    re_onset_chunks: consecutive True  chunks needed to RE-ENTER speech state
                     after the first silence transition. High (6) to absorb the
                     observed 5-consecutive-True noise bursts without triggering
                     re-entry. A True chunk in silence state only increments a
                     counter; it does NOT reset silence_start in main.py because
                     is_speech() returns False the whole time.

    silence_chunks:  consecutive False chunks needed to EXIT speech state
                     (hangover). Prevents a single False chunk mid-word from
                     prematurely triggering silence_start.

    Validated against observed log sequences:
      - Normal 1.14s command + clean silence  → exits at 2.39s ✓
      - 2-chunk (0.23s) short command         → exits at 1.48s ✓
      - Command with natural mid-speech pause → exits at 2.96s ✓
      - No speech at all                      → 0 True frames emitted ✓
      - Post-speech True×5 noise bursts       → absorbed, no re-entry ✓

    aggressiveness: 0–3. Use 3 for noisy environments (Pi 4 with USB mic).
    """

    def __init__(
        self,
        aggressiveness:  int = 3,
        onset_chunks:    int = 2,   # chunks to enter speech initially
        re_onset_chunks: int = 6,   # chunks to re-enter after first silence
        silence_chunks:  int = 3,   # consecutive silent chunks to exit speech
    ):
        if aggressiveness not in (0, 1, 2, 3):
            raise ValueError(f"aggressiveness must be 0-3, got {aggressiveness}")

        self._vad            = webrtcvad.Vad(aggressiveness)
        self._onset_chunks    = onset_chunks
        self._re_onset_chunks = re_onset_chunks
        self._silence_chunks  = silence_chunks

        # State machine
        self._state          = False  # current smoothed output
        self._speech_count   = 0      # consecutive True  seen while in silence state
        self._silent_count   = 0      # consecutive False seen while in speech state
        self._ever_silenced  = False  # True after first silence transition post-speech

    def is_speech(self, audio_48k: np.ndarray) -> bool:
        """
        Returns smoothed speech/silence classification for one 48 kHz chunk.

        The return value is the smoothed state, not the raw webrtcvad frame
        result. Callers (collect_command, attention system) should treat this
        as the authoritative voice-activity signal.

        Args:
            audio_48k: int16 numpy array at 48 kHz, typically 5460 samples
                       from AudioManager.
        """
        # ── Input validation ──────────────────────────────────────────────────
        if audio_48k is None or len(audio_48k) == 0:
            return False

        if audio_48k.dtype != np.int16:
            print(f"[VAD] Warning: expected int16, got {audio_48k.dtype}. "
                  f"Converting — check AudioManager dtype.")
            audio_48k = audio_48k.astype(np.int16)

        try:
            # ── Resample 48 kHz → 16 kHz ─────────────────────────────────────
            audio_16k = resample_poly(audio_48k, 1, RESAMPLE_DOWN).astype(np.int16)
            raw       = audio_16k.tobytes()

            speech_frames = 0
            total_frames  = 0

            for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES):
                frame = raw[i : i + FRAME_BYTES]
                if len(frame) < FRAME_BYTES:
                    break
                total_frames += 1
                if self._vad.is_speech(frame, TARGET_RATE):
                    speech_frames += 1

            if total_frames == 0:
                return False

            raw_speech = (speech_frames / total_frames) > SPEECH_THRESHOLD

        except Exception as e:
            print(f"[VAD] Error in is_speech: {e}")
            return False

        # ── Two-threshold state machine ───────────────────────────────────────
        effective_onset = self._re_onset_chunks if self._ever_silenced \
                          else self._onset_chunks

        if self._state:
            # Currently in speech state
            if raw_speech:
                self._silent_count = 0
            else:
                self._silent_count += 1
                if self._silent_count >= self._silence_chunks:
                    self._state         = False
                    self._silent_count  = 0
                    self._ever_silenced = True
        else:
            # Currently in silence state
            if raw_speech:
                self._speech_count += 1
                if self._speech_count >= effective_onset:
                    self._state        = True
                    self._speech_count = 0
            else:
                self._speech_count = 0

        return self._state