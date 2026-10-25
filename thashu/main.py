import time
import threading
import os

import numpy as np
import RPi.GPIO as GPIO

from voice.audio_manager  import AudioManager
from voice.wake_word      import WakeWordEngine
from voice.vad            import VoiceActivityDetector
from voice.speech_to_text import transcribe 
from voice.text_to_speech import speak
from voice.sound_player   import play
from core.brain           import Brain
from core.attention       import AttentionSystem
from core.state           import RuntimeState, RuntimeStateMachine
from core.event_bus       import EventBus
from vision.vision_core   import VisionCore
from hardware.eyes        import Eyes
from hardware.motors      import MotorController
from core.decision        import get_forward_speed, get_direction_command, is_stop_command
from core.model_paths import model_path, project_path

# ── Sounds ────────────────────────────────────────────────────────────────────
SOUND_STARTUP   = project_path("sounds", "startup.wav")
SOUND_YES       = project_path("sounds", "yes.wav")
SOUND_NOT_HEARD = project_path("sounds", "not_heard.wav")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_RECORD_SECONDS = 10
SILENCE_TIMEOUT    = 0.8
GRACE_PERIOD       = 4.0
SAMPLE_RATE        = 48000
BLOCK_SIZE         = 5460
FORWARD_COMMAND_DURATION_SECONDS = 30.0
TURN_COMMAND_DURATION_SECONDS = 1.0

# ── Shutdown Button ───────────────────────────────────────────────────────────
BUTTON_PIN = 17


# ── Boot ──────────────────────────────────────────────────────────────────────
runtime   = RuntimeStateMachine()
event_bus = EventBus()

brain  = Brain()
motors = MotorController()
audio  = AudioManager(sample_rate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
wake = WakeWordEngine(
    model_path=model_path("openwakeword", "hey_jarvis_v0.1.onnx"),
    threshold=0.5,
    cooldown=4.0
)
vad    = VoiceActivityDetector()
attn   = AttentionSystem()
vision = VisionCore()
eyes   = Eyes()
_motion_timer = None
_motion_generation = 0
_motion_lock = threading.Lock()
event_bus.subscribe(
    "RUNTIME_STATE_CHANGED",
    vision.on_runtime_state_changed,
)


# ── Shutdown Button Monitor ───────────────────────────────────────────────────
def monitor_shutdown_button():
    GPIO.setmode(GPIO.BCM)

    # Internal pull-up resistor
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print("[SYSTEM] Shutdown button monitoring started")

    while True:
        # Button pressed = LOW
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            print("[SYSTEM] Shutdown button pressed")

            # Optional: eyes expression before shutdown
            eyes.thinking()

            # Prevent accidental double trigger
            time.sleep(1)

            os.system("sudo shutdown now")
            break

        time.sleep(0.1)


# ── Collect spoken command ─────────────────────────────────────────────────────
def collect_command() -> np.ndarray:
    """
    Collects audio until silence or max duration.
    Grace period: waits GRACE_PERIOD seconds for user to START speaking.
    Silence timeout: cuts off SILENCE_TIMEOUT seconds after speech ends.
    """
    audio.drain()

    chunks         = []
    silence_start  = None
    speech_started = False
    grace_start    = time.time()
    max_chunks     = int((MAX_RECORD_SECONDS * SAMPLE_RATE) / BLOCK_SIZE)

    for _ in range(max_chunks):
        chunk = audio.read()

        if chunk is None:
            continue

        is_speech = vad.is_speech(chunk)
            

        
                

        if is_speech or speech_started:
            chunks.append(chunk)

        if is_speech:
            speech_started = True
            silence_start  = None

        else:
            # ── Grace period: waiting for user to start ───────────────────
            if not speech_started:
                if time.time() - grace_start > GRACE_PERIOD:
                    print("[STT] No speech in grace period, cancelling.")
                    return np.array([], dtype=np.int16)

                continue

            # ── After speech: count silence ───────────────────────────────
            if silence_start is None:
                silence_start = time.time()

            elif time.time() - silence_start > SILENCE_TIMEOUT:
                
                print("[STT] Silence detected, stopping.")
                break
    
            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)


# ── Safe sound player ──────────────────────────────────────────────────────────
def safe_play(path: str):
    """
    Pauses mic → plays sound → waits for echo to die → resumes mic.
    Prevents Thashu hearing its own audio output.
    """
    audio.pause()

    play(path, blocking=True)

    time.sleep(0.5)
    audio.resume()
    time.sleep(0.15)

def transition_runtime(target_state):
    previous, current = runtime.transition_to(target_state)

    event_bus.publish(
        "RUNTIME_STATE_CHANGED",
        {
            "from": previous.value,
            "to": current.value,
        },
    )

    print(f"[STATE] {previous.value} -> {current.value}")

    return current


def _auto_stop_motion(generation):
    global _motion_timer

    with _motion_lock:
        if generation != _motion_generation:
            return
        _motion_timer = None
        sequence = motors.stop()

    if sequence is None:
        print("[COMMAND] Timed motor STOP could not be sent; ESP32 watchdog remains the fallback")
    else:
        print(f"[COMMAND] Movement timeout; STOP sent (sequence {sequence})")


def start_bounded_motion(direction, speed):
    global _motion_timer, _motion_generation

    motor_commands = {
        "FORWARD": motors.forward,
        "BACKWARD": motors.backward,
        "LEFT": motors.left,
        "RIGHT": motors.right,
    }
    command = motor_commands.get(direction)
    if command is None:
        return None

    with _motion_lock:
        if _motion_timer is not None:
            _motion_timer.cancel()
            _motion_timer = None

        _motion_generation += 1
        generation = _motion_generation
        sequence = command(speed)
        if sequence is None:
            return None

        duration = (
            TURN_COMMAND_DURATION_SECONDS
            if direction in ("LEFT", "RIGHT")
            else FORWARD_COMMAND_DURATION_SECONDS
        )
        _motion_timer = threading.Timer(
            duration,
            _auto_stop_motion,
            args=(generation,),
        )
        _motion_timer.daemon = True
        _motion_timer.start()
        return sequence


def start_bounded_forward(speed):
    return start_bounded_motion("FORWARD", speed)


def stop_motion():
    global _motion_timer, _motion_generation

    with _motion_lock:
        _motion_generation += 1
        if _motion_timer is not None:
            _motion_timer.cancel()
            _motion_timer = None
        return motors.stop()


def confirm_motion_command(sequence, direction):
    acknowledgement = motors.gpio.wait_for_ack(sequence, timeout=0.75)
    if acknowledgement == "OK":
        return True, None

    if acknowledgement is None:
        print(f"[COMMAND] No ESP32 acknowledgement for {direction}; sending STOP")
        failure = "ACK_TIMEOUT"
    else:
        print(f"[COMMAND] ESP32 rejected {direction}: {acknowledgement}")
        failure = {
            "ERROR|OBSTACLE": "OBSTACLE",
            "ERROR|SENSOR_NOT_READY": "SENSOR_NOT_READY",
            "ERROR|SAFETY_STOP": "SAFETY_STOP",
        }.get(acknowledgement, "REJECTED")

    # The controller has either rejected the command or failed to confirm it.
    # Cancel the Pi timer and issue a dedicated STOP as a fail-safe.
    stop_motion()
    return False, failure


def motion_failure_response(direction, failure):
    if failure == "OBSTACLE":
        # The ESP32 also emits BLOCKED|OBSTACLE; process_safety_events speaks it.
        return ""
    if failure == "SENSOR_NOT_READY":
        if direction == "BACKWARD":
            return "My rear sensor isn't ready, so I can't move backward."
        if direction in ("LEFT", "RIGHT"):
            return "A safety sensor isn't ready, so I can't turn."
        return "A front safety sensor isn't ready, so I can't move forward."
    if failure == "SAFETY_STOP":
        # Older firmware reports the obstacle detail as a BLOCKED event.
        return ""
    if failure == "ACK_TIMEOUT":
        return "I couldn't confirm that move, so I stopped."
    return "The motor controller rejected that command."


def announce_safety_message(message):
    print(f"[SAFETY] {message}")
    wake.lock()
    audio.pause()
    eyes.alert()
    try:
        speak(message)
        time.sleep(0.6)
    except Exception as exc:
        print(f"[SAFETY] Could not speak safety message: {exc}")
    finally:
        audio.resume()
        wake.unlock()
        eyes.idle()


def process_safety_events():
    for event in motors.gpio.drain_events():
        if event == "EVENT|0|STOP|OBSTACLE":
            # This is an asynchronous ESP32 safety event; announce it in IDLE too,
            # without waiting for a wake word or an active conversation.
            announce_safety_message("I stopped because an obstacle was detected.")
        elif event == "EVENT|0|BLOCKED|OBSTACLE":
            announce_safety_message("I can't move because an obstacle was detected.")
        # EVENT and FAULT lines are logged immediately by GPIOControl's reader thread.


# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    print("[SYSTEM] Jarvis started")

    # Start systems
    audio.start()

    # ── Start shutdown button monitor ───────────────────────────────────────
    shutdown_thread = threading.Thread(
        target=monitor_shutdown_button,
        daemon=True
    )

    shutdown_thread.start()

    # ── Startup sound ───────────────────────────────────────────────────────

    wake.lock()

    audio.pause()

    play(SOUND_STARTUP, blocking=True)

    time.sleep(0.6)

    audio.resume()

    time.sleep(0.2)

    wake.unlock()

    print("[SYSTEM] ── Ready. Say 'Hey Thashu'")

    eyes.idle()
    # Start autonomous following only after the startup audio has finished.
    vision.start()



    while True:
        process_safety_events()
        chunk = audio.read()

        if chunk is None:
            continue

        # ── Pass vision state to attention system ─────────────────────────
        vis = vision.get_state()

        is_speech_now = vad.is_speech(chunk)
        attn.update(vis["faces"], is_speech_now)

        # ── IDLE: watch for wake word ─────────────────────────────────────
        if runtime.current == RuntimeState.IDLE:
            if wake.process(chunk):
                transition_runtime(RuntimeState.WAKE_DETECTED)

                print("[SYSTEM] ═══════════════════════════")
                print("[SYSTEM] 👂  LISTENING...")
                print("[SYSTEM] ═══════════════════════════")

                # ── Play yes.wav ──────────────────────────────────────────
                wake.lock()

                safe_play(SOUND_YES)

                wake.unlock()
                transition_runtime(RuntimeState.LISTENING)
                # ── Collect command ──────────────────────────────────────
                
                interaction_start = time.time()

                record_start = time.time()
                raw_audio = collect_command()
                record_time = time.time() - record_start

                print(f"[TIME] Recording = {record_time:.2f}s")

                # ── Nothing heard ────────────────────────────────────────
                if len(raw_audio) == 0:
                    print("[SYSTEM] ── Nothing heard")

                    wake.lock()

                    safe_play(SOUND_NOT_HEARD)

                    time.sleep(0.8)

                    wake.unlock()

                    transition_runtime(RuntimeState.RETURN_TO_IDLE)
                    transition_runtime(RuntimeState.IDLE)
                    continue

                # ── Transcribe ───────────────────────────────────────────
                # Pause mic and lock wake word before transcribe — not after.
                # Whisper blocks the main loop for 2–4 s on Pi 4; leaving the
                # stream running during that time fills and overflows the queue.
                wake.lock()
                audio.pause()

                transition_runtime(RuntimeState.THINKING)
                eyes.thinking()

                stt_start = time.time()

                text = transcribe(raw_audio)

                stt_time = time.time() - stt_start
                print(f"[TIME] STT = {stt_time:.2f}s")

                print(f"[SYSTEM] 🗣  YOU SAID: {text}")

                # ── Whisper returned empty ───────────────────────────────
                if not text or not text.strip():
                    # mic is already paused — play directly, not via safe_play
                    # (safe_play would call audio.pause/resume internally and
                    # unpause before wake.unlock, leaving the pipeline in a
                    # wrong state)
                    play(SOUND_NOT_HEARD, blocking=True)

                    time.sleep(0.8)

                    audio.resume()
                    wake.unlock()

                    transition_runtime(RuntimeState.RETURN_TO_IDLE)
                    transition_runtime(RuntimeState.IDLE)
                    continue

                # ── Brain + Speak ────────────────────────────────────────
                # Already paused and locked from before transcribe.


                print("[SYSTEM] 🧠  THINKING...")

                brain_start = time.time()

                if is_stop_command(text):
                    print("[COMMAND] Explicit STOP recognized; sending directly to ESP32")
                    stop_sequence = stop_motion()
                    if stop_sequence is None:
                        print("[COMMAND] STOP could not be sent; ESP32 link is unavailable")
                        response = "I couldn't reach the motor controller, so I can't confirm the stop."
                    else:
                        print(f"[COMMAND] STOP sent to ESP32 (sequence {stop_sequence})")
                        response = "Stopping."
                elif (forward_speed := get_forward_speed(text)) is not None:
                    speed_name, pwm = forward_speed
                    print(
                        f"[COMMAND] Explicit FORWARD recognized at {speed_name} speed "
                        f"(PWM {pwm}); auto-stop in {FORWARD_COMMAND_DURATION_SECONDS:.0f}s"
                    )
                    move_sequence = start_bounded_motion("FORWARD", pwm)
                    if move_sequence is None:
                        print("[COMMAND] FORWARD could not be sent; ESP32 link is unavailable")
                        response = "I couldn't reach the motor controller, so I can't move."
                    else:
                        accepted, failure = confirm_motion_command(move_sequence, "FORWARD")
                        if accepted:
                            print(f"[COMMAND] FORWARD accepted by ESP32 (sequence {move_sequence})")
                            response = {
                                "slow": "Forward slowly.",
                                "medium": "Moving forward.",
                                "fast": "Forward quickly.",
                            }[speed_name]
                        else:
                            response = motion_failure_response("FORWARD", failure)
                elif (direction := get_direction_command(text)) is not None:
                    direction_name = direction.lower().replace("_", " ")
                    duration = (
                        TURN_COMMAND_DURATION_SECONDS
                        if direction in ("LEFT", "RIGHT")
                        else FORWARD_COMMAND_DURATION_SECONDS
                    )
                    print(
                        f"[COMMAND] Explicit {direction_name.upper()} recognized "
                        f"(PWM 200); auto-stop in {duration:.0f}s"
                    )
                    move_sequence = start_bounded_motion(direction, 200)
                    if move_sequence is None:
                        print(f"[COMMAND] {direction_name.upper()} could not be sent; ESP32 link is unavailable")
                        response = "I couldn't reach the motor controller."
                    else:
                        accepted, failure = confirm_motion_command(move_sequence, direction)
                        if accepted:
                            print(f"[COMMAND] {direction_name.upper()} accepted by ESP32 (sequence {move_sequence})")
                            response = {
                                "BACKWARD": "Moving backward.",
                                "LEFT": "Turning left.",
                                "RIGHT": "Turning right.",
                            }[direction]
                        else:
                            response = motion_failure_response(direction, failure)
                else:
                    response = brain.process(text)

                brain_time = time.time() - brain_start
                print(f"[TIME] BRAIN = {brain_time:.2f}s")

                if response:
                    print(f"[SYSTEM] 💬  THASHU: {response}")

                    eyes.happy()

                    transition_runtime(RuntimeState.SPEAKING)

                    tts_start = time.time()

                    speak(response)

                    # A safety stop can arrive while this confirmation is playing.
                    # Handle it before reopening the microphone or returning to IDLE.
                    process_safety_events()

                    tts_time = time.time() - tts_start
                    print(f"[TIME] TTS = {tts_time:.2f}s")

                    time.sleep(0.6)

                audio.resume()

                time.sleep(0.2)

                wake.unlock()
                total_time = time.time() - interaction_start

                print("=" * 40)
                print(f"[TIME] TOTAL = {total_time:.2f}s")
                print("=" * 40)

                eyes.idle()


                print("[SYSTEM] ── Back to idle, say 'Hey Thashu'")

                transition_runtime(RuntimeState.RETURN_TO_IDLE)
                transition_runtime(RuntimeState.IDLE)


if __name__ == "__main__":
    main()