import serial
import time

ser = serial.Serial("/dev/ttyACM0", 9600)
time.sleep(2)

print("Sending test...")

while True:
    ser.write(b"90,90\n")
    print("Sent 90,90")
    time.sleep(2)

    ser.write(b"120,90\n")
    print("Sent 120,90")
    time.sleep(2)