"""All functions regarding getting and parsing data from Amtrak"""
import base64
import datetime
import json
import logging
import operator
import os
import pprint

import requests
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2

URL = "https://maps.amtrak.com/services/MapDataService/trains/getTrainsData"
S_VALUE = "9a3686ac"
I_VALUE = "c6eb2f7f5c4740c1a2f708fefd947d39"
PUBLIC_KEY = "69af143c-e8cf-47f8-bf09-fc1f61e5cc33"
MASTER_SEGMENT = 88
DATETIME_FORMAT = "%m/%d/%Y %H:%M:%S"


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
    with open("./stations.json", "r", encoding="utf-8") as file:
        return json.loads(file.read())


def get_trains(data, station_code):
    """Filter the arrivals data for just our station"""
    trains = []
    # Iterate through the "features" list
    for feature in data["features"]:
        # Go through each property in the feature
        for prop in feature["properties"]:
            # Look for properties that start with "Station" and have content
            if prop.startswith("Station") and feature["properties"][prop]:
                # Parse the JSON inside the Station content.
                # (Yeah it's JSON inside a JSON string ...)
                info = json.loads(feature["properties"][prop])
                # See if this station is ours
                if info and info["code"] == station_code:
                    logging.debug(pprint.pformat(info))

                    # Populate the arrival and departure times and status
                    arrival_time_str = None
                    departure_time_str = None

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
                        logging.warn("Encountered unknown arrival")

                    if "estdep" in info and info["estdep"]:
                        departure_time_str = info["estdep"]
                    elif "schdep" in info and info["schdep"]:
                        departure_time_str = info["schdep"]
                    elif "postdep" in info and info["postdep"]:
                        departure_time_str = info["postdep"]
                    else:
                        logging.warn("Encountered unknown departure")

                    # If we found an arrival time, create an entry in arrivals for it
                    if arrival_time_str:
                        trains.append(
                            dict(
                                arrival_time=datetime.datetime.strptime(
                                    arrival_time_str, DATETIME_FORMAT
                                ) if arrival_time_str else None,
                                departure_time=datetime.datetime.strptime(
                                    departure_time_str, DATETIME_FORMAT
                                ) if departure_time_str else None,
                                station=info["code"],
                                destination=feature["properties"]["DestCode"],
                                status=status,
                                train=feature["properties"]["RouteName"],
                                number=feature["properties"]["TrainNum"],
                                id=feature["id"],
                            )
                        )
    # Sort the arrivals
    trains.sort(key=operator.itemgetter("arrival_time"))
    return trains


def get_current_arrival(trains, previous_trains):
    """Get a current arrival"""
    now = datetime.datetime.now()
    five_minutes_ago = now - datetime.timedelta(minutes=5)
    for train in trains:
        if os.environ.get("FORCE_ARRIVAL"):
            return train
        # If an arrival has happened within the past five minutes,
        # and we have announced it, return it
        if (
            train["arrival_time"]
            and train["arrival_time"] <= now
            and train["arrival_time"] >= five_minutes_ago
            and train["id"] not in previous_trains
        ):
            return train
    return None


def get_current_departure(trains, previous_trains):
    """Get a current departure"""
    now = datetime.datetime.now()
    five_minutes_ago = now - datetime.timedelta(minutes=5)
    for train in trains:
        if os.environ.get("FORCE_DEPARTURE"):
            return train
        # If an arrival has happened within the past five minutes,
        # and we have announced it, return it
        if (
            train["departure_time"]
            and train["departure_time"] <= now
            and train["departure_time"] >= five_minutes_ago
            and train["id"] not in previous_trains
        ):
            return train
    return None
