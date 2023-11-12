import os
import logging

from lib import util

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Get our station
our_station = os.environ.get("STATION_CODE", "WAS")

# Start the runloop
util.runloop(our_station, lambda train, _: print(f"Arrival: {train}"), lambda train, _: print(f"Departure: {train}"))
