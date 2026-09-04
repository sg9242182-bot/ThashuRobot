import RPi.GPIO as GPIO
import os
import time

BUTTON_PIN = 17

GPIO.setmode(GPIO.BCM)

# Use internal pull-up resistor
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Shutdown button ready")

try:
    while True:
        # Button pressed = LOW
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            print("Shutdown initiated")

            # Small delay to prevent accidental triggers
            time.sleep(1)

            os.system("sudo shutdown now")
            break

        time.sleep(0.1)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()