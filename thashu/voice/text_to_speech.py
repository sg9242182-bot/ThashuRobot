import subprocess
import threading
from voice.sound_player import _lock

PIPER_PATH = "/home/tharun/piper/piper/piper"
MODEL_PATH = "/home/tharun/piper/piper/models/en_US-lessac-low.onnx"
DEVICE     = "default"


def speak(text: str):
    if not text or not text.strip():
        return

    with _lock:
        try:
            piper = subprocess.Popen(
                [
                    PIPER_PATH,
                    "--model",        MODEL_PATH,
                    "--output-raw",
                    "--length_scale", "1.1"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            aplay = subprocess.Popen(
                [
                    "aplay",
                    "-D",            DEVICE,
                    "--rate",        "16000",
                    "--format",      "S16_LE",
                    "--channels",    "1",
                    "--buffer-size", "4096"
                ],
                stdin=piper.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            piper.stdout.close()
            piper.communicate(input=text.encode())
            aplay.wait()

        except Exception as e:
            print(f"[TTS ERROR]: {e}")