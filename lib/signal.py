import logging
import time
from threading import Thread

import RPi.GPIO as GPIO
from RaspberryMotors.motors import servos

from lib import audio

SERVO_PIN = 16
LIGHT_PINS = [18, 22]
MIN_GATE_ANGLE = 0
MAX_GATE_ANGLE = 135
GATE_UP = MAX_GATE_ANGLE
GATE_DOWN = MIN_GATE_ANGLE
BLINK_DELAY = 0.5

TYPE_ARRIVAL = 1
TYPE_DEPARTURE = 2

def set_servo_angle(angle):
    """Set the angle of the gate servo"""
    servo = servos.servo(SERVO_PIN)
    servo.setAngleAndWait(angle)
    servo.shutdown()


def announce_train(train, stations, type):
    """Announce a new arrival"""
    # Format it for speaking
    if type == TYPE_ARRIVAL:
        formatted = audio.format_arrival(train, stations)
    elif type == TYPE_DEPARTURE:
        formatted = audio.format_departure(train, stations)
    logging.info('Will say "%s"', formatted)

    # Create the audio
    audio.create_audio(formatted)

    # Mix it
    audio.mix_audio()

    logging.info('Starting audio')

    # Start the audio
    thread = Thread(target=audio.play_audio)
    thread.start()

    logging.info('Dropping gate')

    # Lower the crossing gate
    set_servo_angle(GATE_DOWN)

    logging.info('Blinking lights')

    # Blink the lights until the audio is done play
    light_on = 0
    while thread.is_alive():
        for i, light_pin in enumerate(LIGHT_PINS):
            GPIO.output(light_pin, light_on % len(LIGHT_PINS) == i)
        light_on += 1
        time.sleep(BLINK_DELAY)

    # Turn off the lights
    for light_pin in LIGHT_PINS:
        GPIO.output(light_pin, False)

    logging.info('Lifting gate')

    # Raise the crossing gate
    set_servo_angle(GATE_UP)


def signal_init():
    logging.info("Starting up")

    # Don't release all GPIOs when we stop the servo
    servos.ResetGpioAtShutdown(False)

    # Make sure the gate is up
    set_servo_angle(GATE_UP)

    # Setup IO
    GPIO.setmode(GPIO.BOARD)
    for pin in LIGHT_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, False)
