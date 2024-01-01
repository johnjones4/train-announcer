import pprint

from lib import amtrak

data = amtrak.fetch_data()
pprint.pprint(data)
