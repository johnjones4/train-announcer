"""Main application that runs the signal and audio"""
import logging
from lib import signal, util
import os

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

signal.signal_init()

# Get our station
our_station = os.environ.get("STATION_CODE", "ALX")

# Start the runloop
util.runloop(our_station, lambda train, stations: signal.announce_train(train, stations, signal.TYPE_ARRIVAL), lambda train, stations: signal.announce_train(train, stations, signal.TYPE_DEPARTURE))
