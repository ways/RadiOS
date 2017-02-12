# https://sourceforge.net/p/raspberry-gpio-python/wiki/PWM/

import time
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
pin=13
GPIO.setup(13, GPIO.OUT)

p = GPIO.PWM(13, 50)  # channel=12 frequency=50Hz
p.start(0)
try:
    while 1:
        for dc in range(0, 101, 5):
            p.ChangeDutyCycle(dc)
            print dc
            time.sleep(0.1)
        for dc in range(100, -1, -5):
            p.ChangeDutyCycle(dc)
            time.sleep(0.1)
except KeyboardInterrupt:
    pass
p.stop()
GPIO.cleanup()
