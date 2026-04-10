import serial
import time
import random

arduino = serial.Serial('COM11', 9600, timeout=1)
time.sleep(2)

while True:

    data = arduino.readline().decode().strip()

    if data == "CAR_DETECTED":

        print("Vehicle detected")
        print("Processing blockchain transaction...")

        time.sleep(2)

        # Generate fake transaction hash
        tx = hex(random.randint(0, 0xFFFFFF))

        print(f"Transaction confirmed: {tx}")

        arduino.write((tx + "\n").encode())