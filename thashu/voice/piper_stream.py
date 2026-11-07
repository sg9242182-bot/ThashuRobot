"""In-process libpiper ONNX streaming adapter.

The voice model and its encoder/decoder ONNX sessions are kept resident by
libpiper. Audio chunks are sent to ALSA as soon as they are produced.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
import wave
from pathlib import Path

import numpy as np

from core.model_paths import model_path


PIPER_OK = 0
PIPER_DONE = 1
DEVICE = os.environ.get("THASHU_AUDIO_OUTPUT", "sysdefault:CARD=Headphones")
MODEL_PATH = Path(model_path("piper", "en_US-lessac-low.onnx"))
CONFIG_PATH = Path(str(MODEL_PATH) + ".json")
DEFAULT_LIB = Path.home() / "piper1-gpl/libpiper/install/lib/libpiper.so"
DEFAULT_ESPEAK_DATA = (
    Path.home() / "piper1-gpl/libpiper/install/share/espeak-ng-data"
)


class PiperAudioChunk(ctypes.Structure):
    _fields_ = [
        ("samples", ctypes.POINTER(ctypes.c_float)),
        ("num_samples", ctypes.c_size_t),
        ("sample_rate", ctypes.c_int),
        ("is_last", ctypes.c_bool),
        ("phonemes", ctypes.POINTER(ctypes.c_uint32)),
        ("num_phonemes", ctypes.c_size_t),
        ("phoneme_ids", ctypes.POINTER(ctypes.c_int)),
        ("num_phoneme_ids", ctypes.c_size_t),
        ("alignments", ctypes.POINTER(ctypes.c_int)),
        ("num_alignments", ctypes.c_size_t),
    ]


class PiperSynthesizeOptions(ctypes.Structure):
    _fields_ = [
        ("speaker_id", ctypes.c_int),
        ("length_scale", ctypes.c_float),
        ("noise_scale", ctypes.c_float),
        ("noise_w_scale", ctypes.c_float),
    ]


class PiperStream:
    """One resident native Piper synthesizer that emits PCM chunks."""

    def __init__(self, library_path=None, espeak_data_dir=None):
        self.library_path = Path(
            library_path or os.environ.get("THASHU_LIBPIPER", DEFAULT_LIB)
        ).expanduser()
        self.espeak_data_dir = Path(
            espeak_data_dir
            or os.environ.get("THASHU_ESPEAK_DATA_DIR", DEFAULT_ESPEAK_DATA)
        ).expanduser()
        self._lib = None
        self._synth = None
        self._lock = threading.Lock()

    def load(self):
        if self._synth:
            return

        encoder = Path(str(MODEL_PATH).removesuffix(".onnx") + ".encoder.onnx")
        decoder = Path(str(MODEL_PATH).removesuffix(".onnx") + ".decoder.onnx")
        if not encoder.is_file() or not decoder.is_file():
            raise FileNotFoundError(
                "Streaming voice files are missing. Run Piper's "
                "split_voice_for_streaming tool for this model first."
            )
        if not self.library_path.is_file():
            raise FileNotFoundError(f"libpiper not found: {self.library_path}")
        if not self.espeak_data_dir.is_dir():
            raise FileNotFoundError(
                f"espeak-ng data directory not found: {self.espeak_data_dir}"
            )

        lib = ctypes.CDLL(str(self.library_path))
        lib.piper_create.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        lib.piper_create.restype = ctypes.c_void_p
        lib.piper_free.argtypes = [ctypes.c_void_p]
        lib.piper_free.restype = None
        lib.piper_default_synthesize_options.argtypes = [ctypes.c_void_p]
        lib.piper_default_synthesize_options.restype = PiperSynthesizeOptions
        lib.piper_synthesize_start.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(PiperSynthesizeOptions),
        ]
        lib.piper_synthesize_start.restype = ctypes.c_int
        lib.piper_synthesize_next.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(PiperAudioChunk),
        ]
        lib.piper_synthesize_next.restype = ctypes.c_int

        synth = lib.piper_create(
            os.fsencode(MODEL_PATH),
            os.fsencode(CONFIG_PATH),
            os.fsencode(self.espeak_data_dir),
        )
        if not synth:
            raise RuntimeError("libpiper could not load the ONNX voice")

        self._lib = lib
        self._synth = synth
        print(
            f"[TTS] Streaming ONNX voice loaded in RAM "
            f"({self.library_path.name})"
        )

    def _start_stream(self, text):
        self.load()
        options = self._lib.piper_default_synthesize_options(self._synth)
        options.length_scale = 1.0
        result = self._lib.piper_synthesize_start(
            self._synth,
            text.encode("utf-8"),
            ctypes.byref(options),
        )
        if result != PIPER_OK:
            raise RuntimeError(f"libpiper synthesis start failed: {result}")

    def _next_chunk(self):
        chunk = PiperAudioChunk()
        result = self._lib.piper_synthesize_next(
            self._synth,
            ctypes.byref(chunk),
        )
        if result not in (PIPER_OK, PIPER_DONE):
            raise RuntimeError(f"libpiper synthesis failed: {result}")

        payload = b""
        if chunk.num_samples:
            payload = ctypes.string_at(
                chunk.samples,
                chunk.num_samples * ctypes.sizeof(ctypes.c_float),
            )
        return result, int(chunk.sample_rate), payload

    def speak(self, text):
        """Stream each native decoder chunk directly to the configured speaker."""
        with self._lock:
            started = time.monotonic()
            player = None
            first_audio_at = None
            try:
                self._start_stream(text.strip())
                while True:
                    result, sample_rate, pcm = self._next_chunk()
                    if pcm:
                        if player is None:
                            player = subprocess.Popen(
                                [
                                    "aplay", "-q", "-D", DEVICE, "-t", "raw",
                                    "-f", "FLOAT_LE", "-r", str(sample_rate),
                                    "-c", "1",
                                ],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                bufsize=0,
                            )
                            first_audio_at = time.monotonic()
                        if player.poll() is not None:
                            raise RuntimeError(
                                f"aplay exited early with {player.returncode}"
                            )
                        player.stdin.write(pcm)

                    if result == PIPER_DONE:
                        break

                if player is None:
                    raise RuntimeError("libpiper produced no audio")
                player.stdin.close()
                player.wait(timeout=60)
                if player.returncode != 0:
                    raise RuntimeError(
                        f"aplay exited with {player.returncode}"
                    )

                print(
                    "[TTS DETAIL] Streaming first chunk = "
                    f"{first_audio_at - started:.2f}s"
                )
                print(
                    "[TTS DETAIL] Playback complete = "
                    f"{time.monotonic() - started:.2f}s"
                )
            except Exception:
                if player is not None:
                    try:
                        player.kill()
                        player.wait(timeout=2)
                    except Exception:
                        pass
                raise
            finally:
                if player is not None and player.stdin and not player.stdin.closed:
                    try:
                        player.stdin.close()
                    except OSError:
                        pass

    def write_wav(self, text, output_path):
        """Generate a cached WAV using the resident streamed voice."""
        with self._lock:
            self._start_stream(text.strip())
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            wav_file = None
            try:
                while True:
                    result, sample_rate, pcm = self._next_chunk()
                    if pcm:
                        if wav_file is None:
                            wav_file = wave.open(str(output_path), "wb")
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2)
                            wav_file.setframerate(sample_rate)
                        audio = np.frombuffer(pcm, dtype="<f4")
                        pcm16 = (
                            np.clip(audio, -1.0, 1.0) * 32767.0
                        ).astype("<i2")
                        wav_file.writeframes(pcm16.tobytes())
                    if result == PIPER_DONE:
                        break
                if wav_file is None:
                    raise RuntimeError("libpiper produced no audio for WAV")
            finally:
                if wav_file is not None:
                    wav_file.close()

    def shutdown(self):
        with self._lock:
            if self._synth and self._lib:
                self._lib.piper_free(self._synth)
            self._synth = None
            self._lib = None
