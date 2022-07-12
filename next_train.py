from datetime import datetime
import os
import datetime
import pprint

from lib import amtrak

# Get our station
our_station = os.environ.get("STATION_CODE", "ALX")
data = amtrak.fetch_data()
trains = amtrak.get_trains(data, our_station)
now = datetime.datetime.now()
for train in trains:
    if train["arrival_time"] >= now or train["departure_time"] >= now:
        pprint.pprint(train)
        quit()
