import os
import subprocess
import threading

from core.model_paths import model_path
from voice.sound_player import _lock, play

PIPER_PATH = os.environ.get(
    "THASHU_PIPER_BIN", os.path.expanduser("~/piper/piper/piper")
)
MODEL_PATH = model_path("piper", "en_US-lessac-low.onnx")
DEVICE     = "default"
VOICE_CACHE_DIR = os.path.expanduser(os.environ.get(
    "THASHU_VOICE_CACHE_DIR",
    os.path.join(os.environ.get("XDG_DATA_HOME", "~/.local/share"),
                 "thashu", "voice_responses"),
))

# Short, fixed replies are generated once on the Pi and kept outside the repo.
COMMAND_VOICE_PROMPTS = {
    "forward_slow": "Forward slowly.",
    "forward_medium": "Moving forward.",
    "forward_fast": "Forward quickly.",
    "backward": "Moving backward.",
    "turn_left": "Turning left.",
    "turn_right": "Turning right.",
    "stop": "Stopping.",
    "obstacle_stop": "Obstacle detected. Stopping.",
    "obstacle_blocked": "Obstacle ahead. I can't move.",
}
_PROMPT_TO_VOICE = {text: name for name, text in COMMAND_VOICE_PROMPTS.items()}


def _voice_path(name):
    return os.path.join(VOICE_CACHE_DIR, f"{name}.wav")


def prepare_command_voice_cache():
    """Pre-render short command replies to WAV so playback avoids live Piper latency."""
    os.makedirs(VOICE_CACHE_DIR, exist_ok=True)
    for name, prompt in COMMAND_VOICE_PROMPTS.items():
        output_path = _voice_path(name)
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 44:
            print(f"[PIPER] Cached voice ready: {name}")
            continue

        temporary_path = output_path + ".tmp.wav"
        try:
            result = subprocess.run(
                [
                    PIPER_PATH, "--model", MODEL_PATH,
                    "--output_file", temporary_path,
                    "--length_scale", "1.1",
                ],
                input=prompt.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            if result.returncode != 0 or not os.path.isfile(temporary_path):
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(detail or f"Piper exited with {result.returncode}")
            os.replace(temporary_path, output_path)
            print(f"[PIPER] Generated voice: {name}")
        except Exception as exc:
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)
            except OSError:
                pass
            print(f"[PIPER] Could not generate {name}: {exc}")


def speak(text: str):
    if not text or not text.strip():
        return

    voice_name = _PROMPT_TO_VOICE.get(text.strip())
    if voice_name:
        voice_path = _voice_path(voice_name)
        if os.path.isfile(voice_path):
            play(voice_path)
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

if __name__ == "__main__":
    prepare_command_voice_cache()
