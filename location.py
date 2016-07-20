import settings
import struct
from geopy.geocoders import GoogleV3


def f2i(float):
    return struct.unpack('<Q', struct.pack('<d', float))[0]


def f2h(float):
    return hex(struct.unpack('<Q', struct.pack('<d', float))[0])


def h2f(hex):
    return struct.unpack('<d', struct.pack('<Q', int(hex, 16)))[0]


def set_location(location_name):
    geolocator = GoogleV3()
    loc = geolocator.geocode(location_name)
    print('[*] Location: %s  (%s, %s)' % (loc.address.encode('utf-8'),
                                          loc.latitude,
                                          loc.longitude))
    set_location_coords(loc.latitude, loc.longitude, loc.altitude)


def set_location_coords(lat, long, alt):
    settings.FLOAT_LAT = lat
    settings.FLOAT_LONG = long
    settings.COORDS_LATITUDE = f2i(lat)  # 0x4042bd7c00000000 # f2i(lat)
    settings.COORDS_LONGITUDE = f2i(long)  # 0xc05e8aae40000000 #f2i(long)
    settings.COORDS_ALTITUDE = f2i(alt)
