import hashlib
import os
import subprocess
import threading

from core.model_paths import model_path
from core.quick_responses import QuickResponses
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
    "obstacle_stop": "I stopped because an obstacle was detected.",
    "obstacle_blocked_v2": "I can't move because an obstacle was detected.",
    "safety_stop": "The safety system stopped the move, so I didn't move. Check for an obstacle or sensor issue.",
    "sensor_not_ready_forward": "A front safety sensor isn't ready, so I can't move forward.",
    "sensor_not_ready_reverse": "My rear sensor isn't ready, so I can't move backward.",
    "sensor_not_ready_turn": "A safety sensor isn't ready, so I can't turn.",
    "ack_timeout": "I couldn't confirm that move, so I stopped.",
    "controller_unavailable": "I couldn't reach the motor controller, so I can't move.",
    "not_understood": "I don't understand, please say that again.",
    "follow_stopped": "I stopped following.",
    "follow_started": "Follow mode is on. I will scan with my camera and track one selected face; the wheels stay stopped until follow distance and route safety are calibrated.",
    "follow_selection_required": "I see several people. Say follow left, follow center, or follow right.",
    "follow_no_face": "I haven't found a face yet. I'm scanning with my camera and will keep searching.",
    "follow_target_lost": "I lost the selected person. I stopped tracking them. Say follow me again when they are visible to select again.",
    "follow_target_ambiguous": "I can't tell which person you selected. Following is stopped; say follow me again to choose a target.",
    "follow_stale_camera": "The camera feed is stale, so I stopped following. Say follow me again after the camera is working.",
    "follow_link_lost": "I lost the motor and servo controller connection, so follow mode stopped. Say follow me again after it reconnects.",
    "look_up": "Looking up.",
    "look_down": "Looking down.",
    "look_left": "Looking left.",
    "look_right": "Looking right.",
    "look_center": "Looking straight ahead.",
}
def _quick_response_voice_prompts():
    """Build stable cache names for every possible fixed quick-response reply."""
    prompts = {}
    command_replies = set(COMMAND_VOICE_PROMPTS.values())
    for replies in QuickResponses().data.values():
        for reply in replies:
            if reply in command_replies:
                continue
            digest = hashlib.sha256(reply.encode("utf-8")).hexdigest()[:16]
            prompts[f"quick_{digest}"] = reply
    return prompts


# QuickResponses chooses among variants, so pre-cache every unique possible line.
# The name is a content hash, keeping filenames stable without storing long text.
ALL_VOICE_PROMPTS = _quick_response_voice_prompts()
ALL_VOICE_PROMPTS.update(COMMAND_VOICE_PROMPTS)
_PROMPT_TO_VOICE = {text: name for name, text in ALL_VOICE_PROMPTS.items()}


def _voice_path(name):
    return os.path.join(VOICE_CACHE_DIR, f"{name}.wav")


def prepare_command_voice_cache():
    """Pre-render short command replies to WAV so playback avoids live Piper latency."""
    os.makedirs(VOICE_CACHE_DIR, exist_ok=True)
    for name, prompt in ALL_VOICE_PROMPTS.items():
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
