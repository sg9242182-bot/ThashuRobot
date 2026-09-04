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
from vision.vision_core   import VisionCore
from hardware.eyes        import Eyes

# ── Sounds ────────────────────────────────────────────────────────────────────
SOUND_STARTUP   = "/home/tharun/thashu/sounds/startup.wav"
SOUND_YES       = "/home/tharun/thashu/sounds/yes.wav"
SOUND_NOT_HEARD = "/home/tharun/thashu/sounds/not_heard.wav"

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_RECORD_SECONDS = 10
SILENCE_TIMEOUT    = 0.8
GRACE_PERIOD       = 4.0
SAMPLE_RATE        = 48000
BLOCK_SIZE         = 5460

# ── Shutdown Button ───────────────────────────────────────────────────────────
BUTTON_PIN = 17

# ── States ────────────────────────────────────────────────────────────────────
IDLE      = "IDLE"
LISTENING = "LISTENING"

# ── Boot ──────────────────────────────────────────────────────────────────────
brain  = Brain()
audio  = AudioManager(sample_rate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
wake = WakeWordEngine(
    model_path="models/wake_word/hey_jarvis_v0.1.onnx",
    threshold=0.5,
    cooldown=4.0
)
vad    = VoiceActivityDetector()
attn   = AttentionSystem()
vision = VisionCore()
eyes   = Eyes()


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


# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    print("[SYSTEM] Jarvis started")

    # Start systems
    vision.start()
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

    state = IDLE

    while True:
        chunk = audio.read()

        if chunk is None:
            continue

        # ── Pass vision state to attention system ─────────────────────────
        vis = vision.get_state()

        is_speech_now = vad.is_speech(chunk)
        attn.update(vis["faces"], is_speech_now)

        # ── IDLE: watch for wake word ─────────────────────────────────────
        if state == IDLE:
            if wake.process(chunk):
                state = LISTENING

                print("[SYSTEM] ═══════════════════════════")
                print("[SYSTEM] 👂  LISTENING...")
                print("[SYSTEM] ═══════════════════════════")

                # ── Play yes.wav ──────────────────────────────────────────
                wake.lock()

                safe_play(SOUND_YES)

                wake.unlock()

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

                    state = IDLE
                    continue

                # ── Transcribe ───────────────────────────────────────────
                # Pause mic and lock wake word before transcribe — not after.
                # Whisper blocks the main loop for 2–4 s on Pi 4; leaving the
                # stream running during that time fills and overflows the queue.
                wake.lock()
                audio.pause()

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

                    state = IDLE
                    continue

                # ── Brain + Speak ────────────────────────────────────────
                # Already paused and locked from before transcribe.
                eyes.thinking()

                print("[SYSTEM] 🧠  THINKING...")

                brain_start = time.time()

                response = brain.process(text)

                brain_time = time.time() - brain_start
                print(f"[TIME] BRAIN = {brain_time:.2f}s")

                if response:
                    print(f"[SYSTEM] 💬  THASHU: {response}")

                    eyes.happy()

                    tts_start = time.time()

                    speak(response)

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

                state = IDLE


if __name__ == "__main__":
    main()