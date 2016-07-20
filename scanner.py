# Standard library
import requests
import struct
import json
import time
import os
import sys
from ConfigParser import RawConfigParser

# Modularized code
from login import login, heartbeat, getNeighbors
import settings

# Pypi packages
from geopy.geocoders import GoogleV3, Nominatim
from s2sphere import CellId, LatLng, Cell
from adb_android import adb_android as adb
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Initialization
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


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


def load_config(account):
    print('')

    config = RawConfigParser()
    config.read('pokemon.cfg')

    try:
        if account not in '':
            config.options(account)
    except:
        print('[-] No settings found for that profile. Switching to default profile.')
        account = ''

    if account in '':
        account = config.sections()[0]
    print('[*] Profile: %s' % account)

    # Login settings
    username = config.get(account, 'username')
    password = config.get(account, 'password')
    auth_service = config.get(account, 'auth_service')
    location = config.get(account, 'location')

    # Program settings
    alerts = config.get(account, 'alert')
    evolved = config.getboolean(account, 'evolved')
    evolved_verbose = config.getboolean(account, 'evolved_verbose')
    address = config.getboolean(account, 'address')
    logging = config.getboolean(account, 'logging')
    teleport = config.getboolean(account, 'teleport')
    sounds = config.getboolean(account, 'sounds')
    open_app = config.getboolean(account, 'openapp')

    if evolved or evolved_verbose:
        print('[*] Tracking: Evolved Only')

    if alerts is not None:
        alertlist = [x for x in alerts.split(',') if x.isdigit()]

        with open('pokemon.json', 'r') as pokemonjson:
            pokefile = json.load(pokemonjson)
            alertstring = ''
            for x in alertlist:
                alertstring += '%s, ' % (pokefile[int(x) - 1]['Name'])

        print('[*] Alerts Enabled: %s' % alertstring[:-2])
    else:
        alerts = False

    if address:
        print('[*] Address Format: Enabled')

    if logging:
        print('[*] Logging: Enabled - history.json')

    if teleport:
        print('[*] Teleporting: Enabled')
        adb_devices()

    if sounds:
        soundfile = config.get(account, 'soundfile')
        print('[*] Sounds: Enabled')
        print('[*] Audio file: %s' % soundfile)

    if open_app:
        print('[*] Opening PGO app after teleporting')

    print('')

    config_dict = {}
    config_dict['username'] = username
    config_dict['password'] = password
    config_dict['auth_service'] = auth_service
    config_dict['location'] = location
    config_dict['alerts'] = alerts
    config_dict['alertlist'] = alertlist
    config_dict['evolved'] = evolved
    config_dict['evolved_verbose'] = evolved_verbose
    config_dict['address'] = address
    config_dict['logging'] = logging
    config_dict['teleport'] = teleport
    config_dict['sounds'] = sounds
    config_dict['soundfile'] = soundfile
    config_dict['open_app'] = open_app

    return config_dict


def address_creator(poke):
    try:
        geolocator = Nominatim()
        location = geolocator.reverse('%s, %s' % (poke.Latitude,
                                                  poke.Longitude))
    except:
        try:
            time.sleep(5)
            geolocator = Nominatim()
            location = geolocator.reverse('%s, %s' % (poke.Latitude,
                                                      poke.Longitude))
        except:
            location = 'Could not connect to Geolocator'
    return location


def adb_devices():
    # Stops the method from printing to stdout (No idea why it does this by default).
    sys.stdout = open(os.devnull, 'w')
    # Calls adb devices
    cmd = adb.devices()
    # Restore stdout
    sys.stdout = sys.__stdout__

    # Isolates ip/device id of android device connected
    print('[*] Android device: %s' % cmd[1].replace('List of devices attached', '').replace('\n', '').replace('device', ''))
    return


def adb_teleport(poke):
    # Stops the method from printing to stdout (No idea why it does this by default).
    sys.stdout = open(os.devnull, 'w')

    # Starts fakegps service to teleport you
    adb.shell('am startservice -a com.incorporateapps.fakegps.ENGAGE --ef lat %s --ef lng %s' % (poke.Latitude,
                                                                                                 poke.Longitude))

    # Restore stdout
    sys.stdout = sys.__stdout__
    print('[!] Teleporting to (%s, %s)' % (poke.Latitude,
                                           poke.Longitude))


def adb_play_sound(soundfile):
    try:
        # Plays a sound
        adb.shell('am start -a android.intent.action.VIEW -d file://%s -t audio/wav' % soundfile)
    except:
        pass


def adb_open_pogo():
    adb.shell('monkey -p com.nianticlabs.pokemongo -c android.intent.category.LAUNCHER 1')


def scan(account):
    settings.init()

    config = load_config(account)

    set_location(config['location'])

    api_endpoint, access_token, response = login(config['auth_service'], config['username'], config['password'])

    pokemons = json.load(open('pokemon.json'))
    origin = LatLng.from_degrees(settings.FLOAT_LAT, settings.FLOAT_LONG)
    while True:
        # All Evolved
        # evolvedlist = ['2','3','5','6','8','9','11','12','14','15','17','18','20','22','24','26','28','30','31','33','34','36','38','40','42','44','45','47','49','51','53','55','57','59','61','62','64','65','67','68','70','71','73','75','76','78','80','82','85','87','89','91','93','94','97','99','101','103','105','107','110','112','117','119','121','130','134','135','136','139','141','149']

        # No Pidgeotto 17, Pidgeot 18, Raticate 20, Kakuna 14, Metapod 11, Golbat 42, Poliwhirl 61, Nidorina 30, Nidorino 33, Fearow 22
        evolvedlist = ['2', '3', '5', '6', '8', '9', '12', '15', '24', '26', '28', '31', '34', '36', '38', '40', '44', '45', '47', '49', '51', '53', '55', '57', '59', '62', '64', '65', '67', '68', '70', '71', '73', '75', '76', '78', '80', '82', '85', '87', '89', '91', '93', '94', '97', '99', '101', '103', '105', '107', '110', '112', '117', '119', '121', '130', '134', '135', '136', '139', '141', '149']
        original_lat = settings.FLOAT_LAT
        original_long = settings.FLOAT_LONG
        parent = CellId.from_lat_lng(
                    LatLng.from_degrees(settings.FLOAT_LAT, settings.FLOAT_LONG)).parent(15)

        for x in range(6):
            h = heartbeat(config['auth_service'],
                          api_endpoint,
                          access_token,
                          response)
            if x == 5:
                print('[-] Connection Terminated')
                return
            try:
                if 'failed' not in h:
                    pass
            except:
                break
            else:
                print('[!] Connection Error: Retrying in 5 seconds... Attempt: %d' % (x+1))
                time.sleep(5)

        hs = [h]
        seen = set([])

        for child in parent.children():
            latlng = LatLng.from_point(Cell(child).get_center())
            set_location_coords(latlng.lat().degrees,
                                latlng.lng().degrees,
                                0)  # Alt
            hs.append(heartbeat(config['auth_service'],
                                api_endpoint,
                                access_token,
                                response))

        set_location_coords(original_lat, original_long, 0)

        visible = []

        try:
            for hh in hs:
                for cell in hh.cells:
                    for wild in cell.WildPokemon:
                        hash = wild.SpawnPointId + ':' + str(wild.pokemon.PokemonId)
                        if (hash not in seen):
                            visible.append(wild)
                            seen.add(hash)
        except:
            continue

        if config['evolved'] or config['evolved_verbose']:
            skipped_list = []

        for poke in visible:
            other = LatLng.from_degrees(poke.Latitude, poke.Longitude)
            diff = other - origin
            difflat = diff.lat().degrees
            difflng = diff.lng().degrees
            direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '') + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')

            base = '(%s) %s is visible at (%s, %s) for %s seconds (%sm %s from you)'
            found_pokemon = base % (poke.pokemon.PokemonId,
                                    pokemons[poke.pokemon.PokemonId - 1]['Name'],
                                    poke.Latitude, poke.Longitude,
                                    poke.TimeTillHiddenMs / 1000,
                                    int(origin.get_distance(other).radians * 6366468.241830914),
                                    direction)
            if config['logging']:
                timestamp = int(time.time())
                try:
                    with open('history.json', 'a+') as file:
                        json.dump({'PokemonID': str(poke.pokemon.PokemonId),
                                   'Pokemon Name': pokemons[poke.pokemon.PokemonId - 1]['Name'],
                                   'Coordinates': {'X': poke.Latitude,
                                                   'Y': poke.Longitude},
                                   'Timestamp': timestamp},
                                  file, indent=4)
                except:
                    print('Unable to Open Log File')

            if config['alerts'] and str(poke.pokemon.PokemonId) in config['alertlist']:
                print('')
                print('[+]    ==========================FOUND A %s============================' % pokemons[poke.pokemon.PokemonId - 1]['Name'].upper())
                print('[+]    ' + found_pokemon)
                if config.address:
                    print('[+] Address: %s' % address_creator(poke))
                print('[+]    ===================================================================')

                # Code to teleport you to the target
                if config['teleport']:
                    adb_teleport(poke)
                if config['sounds']:
                    adb_play_sound(config['soundfile'])
                if config['open_app']:
                    time.sleep(2)
                    adb_open_pogo()
                print('')

            elif config['evolved'] or config['evolved_verbose']:

                if str(poke.pokemon.PokemonId) in evolvedlist:
                    print(' - ' + found_pokemon)
                    if config['address']:
                        print(' - Address: %s' % address_creator(poke))
                    print('')
                else:
                    skipped_list.append(pokemons[poke.pokemon.PokemonId - 1]['Name'])

            else:
                print(' - ' + found_pokemon)
                if config['address']:
                    print(' - Address: %s' % address_creator(poke))

        if config['evolved_verbose']:
            if not not skipped_list:  # If it is not empty
                print_string = ''
                for x in skipped_list:
                    print_string += x + ', '
                print('[I] ' + print_string[:-2])

        walk = getNeighbors()
        next = LatLng.from_point(Cell(CellId(walk[2])).get_center())
        time.sleep(10)
        set_location_coords(next.lat().degrees, next.lng().degrees, 0)
