"""
speech_to_text.py — Thashu Voice Pipeline
Transcribes int16 audio at 48 kHz using faster-whisper (Whisper tiny, int8).

Key design decisions:
- Lazy model load (first call, not import time) — avoids crashing the entire
  voice system if faster-whisper is unavailable.
- Minimum audio length guard — prevents hallucination on very short clips.
- Input dtype check — refuses to silently process pre-normalized float32.
- compute_type="int8" + model="tiny" is correct for Pi 4; see notes on
  hallucination risk in model selection comment.
"""

import numpy as np
from scipy.signal import resample_poly


# ── Constants ─────────────────────────────────────────────────────────────────

INPUT_RATE    = 48_000
TARGET_RATE   = 16_000
RESAMPLE_DOWN = INPUT_RATE // TARGET_RATE   # = 3

# Minimum audio to attempt transcription: 0.5 seconds at 48 kHz.
# Whisper pads short clips heavily and hallucinates on sub-500ms input.
MIN_SAMPLES_48K = INPUT_RATE // 2   # 24 000 samples = 0.5 s

# Model selection note:
#   "tiny"  int8 — fastest, most likely to hallucinate on short/quiet input.
#   "base"  int8 — ~2× slower but noticeably more accurate; still runs on Pi 4.
# Change MODEL_SIZE to "base" if STT quality is poor.
MODEL_SIZE    = "tiny"
COMPUTE_TYPE  = "int8"


# ── Lazy model singleton ──────────────────────────────────────────────────────

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            _model = WhisperModel(MODEL_SIZE, compute_type=COMPUTE_TYPE)
            print(f"[STT] Whisper {MODEL_SIZE!r} ({COMPUTE_TYPE}) loaded")
        except Exception as e:
            print(f"[STT] Failed to load Whisper model: {e}")
            raise
    return _model


# ── Public API ────────────────────────────────────────────────────────────────

def transcribe(audio_48k: np.ndarray) -> str:
    """
    Transcribe int16 audio at 48 kHz. Returns the transcribed string,
    or "" on error or too-short input.

    Args:
        audio_48k: int16 numpy array at 48 kHz.
                   Caller (voice pipeline) is responsible for concatenating
                   VAD-gated chunks before passing here.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    if audio_48k is None or len(audio_48k) == 0:
        print("[STT] Empty audio — skipping")
        return ""

    if audio_48k.dtype != np.int16:
        print(f"[STT] Expected int16 audio, got {audio_48k.dtype}. "
              f"This may indicate a pre-normalized float array — refusing to proceed.")
        return ""

    if len(audio_48k) < MIN_SAMPLES_48K:
        duration_ms = len(audio_48k) * 1000 // INPUT_RATE
        print(f"[STT] Audio too short ({duration_ms} ms) — minimum is "
              f"{MIN_SAMPLES_48K * 1000 // INPUT_RATE} ms. Skipping.")
        return ""

    try:
        # ── Resample 48 kHz → 16 kHz ─────────────────────────────────────────
        # Normalize int16 to float32 in [−1, 1] as Whisper expects.
        audio_16k = resample_poly(
            audio_48k.astype(np.float32) / 32768.0, 1, RESAMPLE_DOWN
        )

        # ── Transcribe ────────────────────────────────────────────────────────
        model = _get_model()
        segments, info = model.transcribe(
            audio_16k,
            language="en",
            vad_filter=True,      # faster-whisper built-in VAD filter; reduces hallucination
            vad_parameters={
                "min_silence_duration_ms": 300,
            },
        )
        text = " ".join(s.text.strip() for s in segments).strip()

        duration_s = len(audio_48k) / INPUT_RATE
        print(f"[STT] ({duration_s:.1f}s audio) Heard: {text!r}")
        return text

    except Exception as e:
        print(f"[STT] Transcription error: {e}")
        return ""
