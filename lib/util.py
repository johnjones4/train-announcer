"""General functions"""
import datetime
import logging
import time

from lib import amtrak

AMTRAK_POLLING_INTERVAL = datetime.timedelta(seconds=60)


def runloop(our_station, arrival_callback, departure_callback):
    """Run forever a fire a callback when there's a new train"""
    # Load the stations.json file
    stations = amtrak.load_stations()
    logging.info("Loaded %d stations", len(stations))

    # Initialize the buffer to track (and dedupe) announcements
    previous_arrivals = [None] * 50
    previous_arrivals_index = 0
    previous_departures = [None] * 50
    previous_departures_index = 0

    # Initialize a timestamp to record the last time we polled Amtrak
    last_amtrak_check = None

    # Initialize the list to hold our station's arrivals
    trains = []

    # Loop forever
    while True:
        try:
            # See if there are any arrivals at present
            logging.info("Check for present trains")

            arrival = amtrak.get_current_arrival(trains, previous_arrivals)

            # If there's an arrival
            if arrival:
                logging.info("There is an arrival %s", str(arrival))

                arrival_callback(arrival, stations)

                # Add this arrival to the buffer so we don't resay it
                previous_arrivals[
                    previous_arrivals_index % len(previous_arrivals)
                ] = arrival["id"]
                previous_arrivals_index += 1
            else:
                logging.info("There are no present arrivals")

            departure = amtrak.get_current_departure(trains, previous_arrivals)

            # If there's an arrival
            if departure:
                logging.info("There is a departure %s", str(arrival))

                departure_callback(departure, stations)

                # Add this departure to the buffer so we don't resay it
                previous_departures[
                    previous_departures_index % len(previous_departures)
                ] = departure["id"]
                previous_departures_index += 1
            else:
                logging.info("There are no present departures")

            # Check if we need to poll Amtrak
            if last_amtrak_check:
                time_since_last_check = datetime.datetime.now() - last_amtrak_check
            else:
                time_since_last_check = AMTRAK_POLLING_INTERVAL
            logging.info("%s since last data pull", str(time_since_last_check))

            # If the arrivals list is empty or it's been too long since checking ...
            if not trains or time_since_last_check >= AMTRAK_POLLING_INTERVAL:

                # Get data from the server
                logging.info("Polling Amtrak for data")
                data = amtrak.fetch_data()

                # Filter it down to arrivals for our station
                trains = amtrak.get_trains(data, our_station)
                logging.info("%d trains for %s", len(trains), our_station)

                # Set the timestamp to restart the interval
                last_amtrak_check = datetime.datetime.now()
        except:
            logging.exception("")

        # Wait 10 seconds to check for arrivals again
        time.sleep(10)
