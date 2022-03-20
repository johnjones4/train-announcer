import base64
import datetime
import enum
import json
import logging
import operator
import os
import os.path
import pprint
import time
from threading import Thread

import boto3
import requests
import sox
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
import RPi.GPIO as GPIO

URL = "https://maps.amtrak.com/services/MapDataService/trains/getTrainsData"
S_VALUE = "9a3686ac"
I_VALUE = "c6eb2f7f5c4740c1a2f708fefd947d39"
PUBLIC_KEY = "69af143c-e8cf-47f8-bf09-fc1f61e5cc33"
MASTER_SEGMENT = 88
DATETIME_FORMAT = "%m/%d/%Y %H:%M:%S"
AUDIO_DIR = os.environ.get("AUDIO_DIR", "./audio")
ANNOUNCEMENT_AUDIO_FILE = os.path.join(AUDIO_DIR, "announcement.ogg")
UPRATED_ANNOUNCEMENT_AUDIO_FILE = os.path.join(AUDIO_DIR, "announcement_uprated.ogg")
BACKGROUND_AUDIO_FILE = os.path.join(AUDIO_DIR, "background.ogg")
SILENCE_AUDIO_FILE = os.path.join(AUDIO_DIR, "silence.ogg")
AMTRAK_POLLING_INTERVAL = datetime.timedelta(seconds=60)
SERVO_PIN = 23
LIGHT_PINS = [24, 25]
MIN_GATE_ANGLE = 5
MAX_GATE_ANGLE = 130
PWM=None


def decrypt(data: str, key: str):
    """Decrypt data using AES and a PBKDF2 key"""
    p_key = PBKDF2(key, bytes.fromhex(S_VALUE)).read(16)
    cypher = AES.new(p_key, AES.MODE_CBC, bytes.fromhex(I_VALUE))
    plaintext = cypher.decrypt(base64.b64decode(data))
    return plaintext.decode("utf-8")


def clean_string(string: str):
    """Clean the nonprintable characters at the end of a string"""
    while ord(string[len(string) - 1]) <= 32:
        string = string[: len(string) - 1]
    return string


def fetch_data():
    """Fetch data from Amtrak"""
    # Make the GET request
    response = requests.get(URL)

    # Slice the content and the key
    encrypted_content = response.text[: len(response.text) - MASTER_SEGMENT]
    encrypted_private_key = response.text[len(response.text) - MASTER_SEGMENT :]

    # Decrypt the private key using the public key
    private_key = decrypt(encrypted_private_key, PUBLIC_KEY).split("|")[0]

    # Decrypt and clean the content
    content = decrypt(encrypted_content, private_key)
    cleaned = clean_string(content)

    # Parse the JSON
    return json.loads(cleaned)


def load_stations():
    """Load a JSON file containing a map of station codes => station names"""
    with open("./stations.json", "r") as file:
        return json.loads(file.read())


def get_arrivals(data, station_code):
    """Filter the arrivals data for just our station"""
    arrivals = []
    # Iterate through the "features" list
    for feature in data["features"]:
        # Go through each property in the feature
        for prop in feature["properties"]:
            # Look for properties that start with "Station" and have content
            if prop.startswith("Station") and feature["properties"][prop]:
                # Parse the JSON inside the Station content. (Yeah it's JSON inside a JSON string ...)
                info = json.loads(feature["properties"][prop])
                # See if this station is ours
                if info and info["code"] == station_code:
                    # Populate the arrival time and status
                    arrival_time_str = None
                    status = None
                    if "estarr" in info and info["estarr"]:
                        arrival_time_str = info["estarr"]
                        status = info["estarrcmnt"]
                    elif "scharr" in info and info["scharr"]:
                        arrival_time_str = info["scharr"]
                        status = info["postcmnt"]
                    elif "postarr" in info and info["postarr"]:
                        arrival_time_str = info["postarr"]
                        status = info["postcmnt"]
                    else:
                        pprint.pprint(info)
                    # If we found an arrival time, create an entry in arrivals for it
                    if arrival_time_str:
                        arrivals.append(
                            dict(
                                arrival_time=datetime.datetime.strptime(
                                    arrival_time_str, DATETIME_FORMAT
                                ),
                                station=info["code"],
                                destination=feature["properties"]["DestCode"],
                                status=status,
                                train=feature["properties"]["RouteName"],
                                number=feature["properties"]["TrainNum"],
                                id=feature["id"],
                            )
                        )
    # Sort the arrivals
    arrivals.sort(key=operator.itemgetter("arrival_time"))
    return arrivals


def get_current_arrival(arrivals, previous_arrivals):
    """Get a current arrival"""
    now = datetime.datetime.now()
    five_minutes_ago = now - datetime.timedelta(minutes=5)
    for arrival in arrivals:
        if os.environ.get("FORCE_ARRIVAL"):
            return arrival
        # return arrival
        # If an arrival has happened within the past five minutes, and we have announced it, return it
        if (
            arrival["arrival_time"] <= now
            and arrival["arrival_time"] >= five_minutes_ago
            and arrival["id"] not in previous_arrivals
        ):
            return arrival
    return None


def format_arrival(arrival, stations):
    """Format the arrival into a speakable string"""
    return f"Now arriving at {stations[arrival['station']]} station.<break time=\"0.25s\"/> The <emphasis>{arrival['train']}</emphasis> <break time=\"0.05s\"/> number <break time=\"0.005s\"/> <emphasis>{arrival['number']}</emphasis> <break time=\"0.05s\"/> bound for <break time=\"0.005s\"/> <emphasis>{stations[arrival['destination']]}</emphasis> station."


def create_audio(text):
    """Convert the string to audio using AWS Polly"""
    output = boto3.client("polly").synthesize_speech(
        Text=f'<speak><break time="1s"/>{text}</speak>',
        TextType="ssml",
        OutputFormat="ogg_vorbis",
        VoiceId="Matthew",
    )
    with open(ANNOUNCEMENT_AUDIO_FILE, "wb") as file:
        file.write(output["AudioStream"].read())


def play_audio():
    """Apply some effects to the audio and play it"""

    # Create combiner to apply effects to the announcement and pad it with silence
    tfm = sox.Combiner()

    # This one goes to eleven
    tfm.gain(10)

    # Add an echo
    tfm.echo(gain_in=0.5, gain_out=0.9, delays=[150], decays=[0.1])

    # Upgrade its channels and sample rate to be compatible with the background audio
    tfm.channels(2)
    tfm.rate(44100)

    # Prepend silence and output the file
    tfm.build(
        [SILENCE_AUDIO_FILE, ANNOUNCEMENT_AUDIO_FILE],
        UPRATED_ANNOUNCEMENT_AUDIO_FILE,
        "concatenate",
    )

    # Mix the background audio and the effects-added announcement
    sox.Combiner().preview(
        [BACKGROUND_AUDIO_FILE, UPRATED_ANNOUNCEMENT_AUDIO_FILE], "mix"
    )

def setServoAngle(angle):
    duty = angle / 18 + 3
    GPIO.output(11, True)
    PWM.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(11, False)
    PWM.ChangeDutyCycle(duty)


def main():
    """The main function of this application"""
    global PWM

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("Starting up")

    # Setup IO
    GPIO.setmode(GPIO.BOARD)

    GPIO.setup(SERVO_PIN, GPIO.OUT)
    PWM=GPIO.PWM(SERVO_PIN, 50)
    PWM.start(0)
    setServoAngle(MAX_GATE_ANGLE)

    for pin in LIGHT_PINS:
        GPIO.setup(pin, GPIO.OUT)

    # Get our station
    our_station = os.environ.get("STATION_CODE", "ALX")

    # Load the stations.json file
    stations = load_stations()
    logging.info(f"Loaded {len(stations)} stations")

    # Initialize the buffer to track (and dedupe) announcements
    previous_arrivals = [None] * 50
    previous_arrivals_index = 0

    # Initialize a timestamp to record the last time we polled Amtrak
    last_arrival_check = None

    # Initialize the list to hold our station's arrivals
    arrivals = []

    # Loop forever
    while True:
        try:
            # See if there are any arrivals at present
            logging.info("Check for present arrivals")
            arrival = get_current_arrival(arrivals, previous_arrivals)

            # If there's an arrival
            if arrival:
                logging.info(f"There is an arrival {arrival}")

                # Format it for speaking
                formatted = format_arrival(arrival, stations)
                logging.info(f'Will say "{formatted}"')

                # Create the audio
                create_audio(formatted)

                # Start the audio
                t = Thread(target = play_audio)

                # Lower the crossing gate
                setServoAngle(MIN_GATE_ANGLE)

                # Blink the lights until the audio is done play
                light_on = 0
                while t.is_alive():
                    for i, light_pin in enumerate(LIGHT_PINS):
                        GPIO.output(light_pin, light_on % len(LIGHT_PINS) == i)
                    light_on+=1
                    time.sleep(1)

                # Turn off the lights
                for light_pin in LIGHT_PINS:
                    GPIO.output(light_pin, False)

                # Raise the crossing gate
                setServoAngle(MAX_GATE_ANGLE)

                # Add this arrival to the buffer so we don't resay it
                previous_arrivals[
                    previous_arrivals_index % len(previous_arrivals)
                ] = arrival["id"]
                previous_arrivals_index += 1
            else:
                logging.info("There are no present arrivals")

            # Check if we need to poll Amtrak
            if last_arrival_check:
                time_since_last_check = datetime.datetime.now() - last_arrival_check
            else:
                time_since_last_check = AMTRAK_POLLING_INTERVAL
            logging.info(f"{time_since_last_check} since last data pull")

            # If the arrivals list is empty or it's been too long since checking ...
            if not arrivals or time_since_last_check >= AMTRAK_POLLING_INTERVAL:

                # Get data from the server
                logging.info("Polling Amtrak for data")
                data = fetch_data()

                # Filter it down to arrivals for our station
                arrivals = get_arrivals(data, our_station)
                logging.info(f"{len(arrivals)} arrivals for {our_station}")

                # Set the timestamp to restart the interval
                last_arrival_check = datetime.datetime.now()
        except:
            logging.exception("")

        # Wait 10 seconds to check for arrivals again
        time.sleep(10)


main()
