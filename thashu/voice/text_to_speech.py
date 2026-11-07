import hashlib
import os
import subprocess
import threading
import time

from core.model_paths import model_path
from core.quick_responses import QuickResponses
from voice.sound_player import _lock, play

PIPER_PATH = os.environ.get(
    "THASHU_PIPER_BIN", os.path.expanduser("~/piper/piper/piper")
)
MODEL_PATH = model_path("piper", "en_US-lessac-low.onnx")
DEVICE     = os.environ.get("THASHU_AUDIO_OUTPUT", "sysdefault:CARD=Headphones")
TTS_PROCESS_TIMEOUT_SECONDS = 30.0
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
    "follow_started": "Follow mode is on.",
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
    "identity_capture_start": "I am collecting five clear views of one face. Keep your face centered and still for a few seconds, then tell me your name.",
    "identity_capture_complete": "I have finished taking the face pictures. Tell me your name, and spell it with letters if the first name I hear is wrong.",
    "identity_capture_unavailable": "Face registration is unavailable because the landmark model is not installed.",
    "identity_capture_failed": "I could not get a stable single face. Please try again with only one face in view.",
    "identity_spell_retry": "I didn't catch the spelling. Please say each letter separately, for example T H A R U N.",
    "identity_spelling_required": "Please spell the name using ordinary letter names, like T H A R U N, or say cancel.",
    "identity_not_recognized": "I don't recognize a confirmed face right now.",
    "person_recognized": "I recognize a known person.",
    "identity_registration_cancelled": "I cancelled face registration.",
    "identity_change_cancelled": "I cancelled that identity change.",
    "identity_not_saved": "I did not save the face identity.",
    "identity_save_failed": "I could not safely save that face identity. Please try registration again.",
    "follow_upper_body_missing": "I haven't found an upper body yet. I'm scanning with my camera and will keep searching.",
    "follow_selection_not_unique": "I can't identify one person in that direction. Please choose left, center, or right again.",
    "follow_reselect": "I couldn't safely reacquire the same person. Say follow me again to select a target.",
    "follow_stale_camera": "The camera feed is stale, so I stopped following. Say follow me again after the camera is working.",
    "follow_controller_lost": "I lost the motor and servo controller connection, so follow mode stopped. Say follow me again after it reconnects.",
    "follow_sensor_not_ready": "My safety sensors aren't ready, so I stopped following until they recover.",
    "follow_obstacle_blocked": "An obstacle blocks my route. I stopped following and will wait for a clear path.",
    "controller_unavailable_short": "I couldn't reach the motor controller.",
    "motor_command_rejected": "The motor controller rejected that command.",
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


def play_cached_response(text: str) -> bool:
    """Play an already-rendered exact reply without starting Piper."""
    if not text or not text.strip():
        return False
    voice_name = _PROMPT_TO_VOICE.get(text.strip())
    if not voice_name:
        return False
    voice_path = _voice_path(voice_name)
    if not os.path.isfile(voice_path) or os.path.getsize(voice_path) <= 44:
        return False
    play(voice_path, blocking=True)
    print(f"[VOICE] Cached WAV played: {voice_name}")
    return True


def prepare_command_voice_cache(names=None):
    """Pre-render selected command replies, or every reply when names is omitted."""
    os.makedirs(VOICE_CACHE_DIR, exist_ok=True)
    if names is None:
        prompts = ALL_VOICE_PROMPTS
    else:
        requested = {names} if isinstance(names, str) else set(names)
        unknown = requested.difference(ALL_VOICE_PROMPTS)
        if unknown:
            raise ValueError(f"Unknown voice cache name(s): {', '.join(sorted(unknown))}")
        prompts = {name: ALL_VOICE_PROMPTS[name] for name in requested}
    for name, prompt in prompts.items():
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
                    "--length_scale", "1.0",
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


def _terminate_process(process):
    """Terminate a child process and reap it, escalating to kill if necessary."""
    if process is None:
        return
    try:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.0)
    except Exception as exc:
        print(f"[TTS] Could not stop child process: {exc}")


def speak(text: str):
    if not text or not text.strip():
        return

    voice_name = _PROMPT_TO_VOICE.get(text.strip())
    if voice_name:
        voice_path = _voice_path(voice_name)
        if os.path.isfile(voice_path):
            try:
                cache_started = time.monotonic()
                play(voice_path)
                print(f"[TTS DETAIL] Cached WAV playback = {time.monotonic() - cache_started:.2f}s")
                return
            except Exception as exc:
                print(f"[TTS] Cached WAV playback failed; trying Piper: {exc}")

    with _lock:
        piper = None
        aplay = None
        piper_started = None
        aplay_started = None
        try:
            piper_started = time.monotonic()
            piper = subprocess.Popen(
                [
                    PIPER_PATH,
                    "--model", MODEL_PATH,
                    "--output-raw",
                    "--length_scale", "1.0",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            aplay_started = time.monotonic()
            aplay = subprocess.Popen(
                [
                    "aplay",
                    "-D", DEVICE,
                    "--rate", "16000",
                    "--format", "S16_LE",
                    "--channels", "1",
                    "--buffer-size", "4096",
                ],
                stdin=piper.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # aplay owns the read end. Close the parent's duplicate so either
            # child can observe EOF/SIGPIPE correctly if the other exits.
            if piper.stdout is not None:
                piper.stdout.close()
            if piper.stdin is not None:
                piper.stdin.write(text.encode("utf-8"))
                piper.stdin.close()

            deadline = time.monotonic() + TTS_PROCESS_TIMEOUT_SECONDS
            piper.wait(timeout=max(0.0, deadline - time.monotonic()))
            piper_finished = time.monotonic()
            print(
                "[TTS DETAIL] Piper process to EOF = "
                f"{piper_finished - piper_started:.2f}s "
                "(includes startup, generation, and streaming)"
            )
            aplay.wait(timeout=max(0.0, deadline - time.monotonic()))
            aplay_finished = time.monotonic()
            print(
                f"[TTS DETAIL] aplay process = "
                f"{aplay_finished - aplay_started:.2f}s"
            )
            if piper.returncode != 0 or aplay.returncode != 0:
                print(
                    f"[TTS] Playback process failed "
                    f"(Piper={piper.returncode}, aplay={aplay.returncode})"
                )
        except subprocess.TimeoutExpired:
            print(
                f"[TTS] Piper/audio playback exceeded "
                f"{TTS_PROCESS_TIMEOUT_SECONDS:.0f}s; terminating it"
            )
        except Exception as exc:
            print(f"[TTS ERROR]: {exc}")
        finally:
            # Stop downstream playback first, then Piper, so no child or pipe
            # can keep the voice loop blocked after an error or timeout.
            _terminate_process(aplay)
            _terminate_process(piper)
            for process in (aplay, piper):
                for stream_name in ("stdin", "stdout", "stderr"):
                    stream = getattr(process, stream_name, None) if process else None
                    if stream is not None and not stream.closed:
                        try:
                            stream.close()
                        except OSError:
                            pass

if __name__ == "__main__":
    prepare_command_voice_cache()
