"""Main application that runs the signal and audio"""
import logging
from lib import signal, amtrak

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

signal.signal_init()

train = {
    "station": "WAS",
    "train": "Northeast Regional",
    "destination": "NYP",
    "number": "156"
}

stations = amtrak.load_stations()

# Start the runloop
signal.announce_train(train, stations, signal.TYPE_DEPARTURE)
