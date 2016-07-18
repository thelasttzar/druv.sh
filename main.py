#!/usr/bin/env python
import requests
import re
import struct
import json
import argparse
import pokemon_pb2
import time

from google.protobuf.internal import encoder

from gpsoauth import perform_master_login, perform_oauth
from datetime import datetime
from geopy.geocoders import GoogleV3, Nominatim
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from s2sphere import *

def encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)

def getNeighbors():
    origin = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)).parent(15)
    walk = [origin.id()]
    # 10 before and 10 after
    next = origin.next()
    prev = origin.prev()
    for i in range(10):
        walk.append(prev.id())
        walk.append(next.id())
        next = next.next()
        prev = prev.prev()
    return walk



API_URL = 'https://pgorelease.nianticlabs.com/plfe/rpc'
LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'

SESSION = requests.session()
SESSION.headers.update({'User-Agent': 'Niantic App'})
SESSION.verify = False

DEBUG = False
COORDS_LATITUDE = 0
COORDS_LONGITUDE = 0
COORDS_ALTITUDE = 0
FLOAT_LAT = 0
FLOAT_LONG = 0




def f2i(float):
  return struct.unpack('<Q', struct.pack('<d', float))[0]

def f2h(float):
  return hex(struct.unpack('<Q', struct.pack('<d', float))[0])

def h2f(hex):
  return struct.unpack('<d', struct.pack('<Q', int(hex,16)))[0]

def set_location(location_name):
    geolocator = GoogleV3()
    loc = geolocator.geocode(location_name)
    print('[*] Location: {}'.format(loc.address.encode('utf-8')) + ' {} {}'.format(loc.latitude, loc.longitude))
    set_location_coords(loc.latitude, loc.longitude, loc.altitude)

def set_location_coords(lat, long, alt):
    global COORDS_LATITUDE, COORDS_LONGITUDE, COORDS_ALTITUDE
    global FLOAT_LAT, FLOAT_LONG
    FLOAT_LAT = lat
    FLOAT_LONG = long
    COORDS_LATITUDE = f2i(lat) # 0x4042bd7c00000000 # f2i(lat)
    COORDS_LONGITUDE = f2i(long) # 0xc05e8aae40000000 #f2i(long)
    COORDS_ALTITUDE = f2i(alt)

def get_location_coords():
    return (COORDS_LATITUDE, COORDS_LONGITUDE, COORDS_ALTITUDE)

def api_req(service, api_endpoint, access_token, *mehs, **kw):
    try:
        p_req = pokemon_pb2.RequestEnvelop()
        p_req.rpc_id = 1469378659230941192

        p_req.unknown1 = 2

        p_req.latitude, p_req.longitude, p_req.altitude = get_location_coords()

        p_req.unknown12 = 989

        if 'useauth' not in kw or not kw['useauth']:
            p_req.auth.provider = service
            p_req.auth.token.contents = access_token
            p_req.auth.token.unknown13 = 14
        else:
            p_req.unknown11.unknown71 = kw['useauth'].unknown71
            p_req.unknown11.unknown72 = kw['useauth'].unknown72
            p_req.unknown11.unknown73 = kw['useauth'].unknown73

        for meh in mehs:
            p_req.MergeFrom(meh)

        protobuf = p_req.SerializeToString()

        r = SESSION.post(api_endpoint, data=protobuf, verify=False)

        p_ret = pokemon_pb2.ResponseEnvelop()
        p_ret.ParseFromString(r.content)

        if DEBUG:
            print("REQUEST:")
            print(p_req)
            print("Response:")
            print(p_ret)
            print("\n\n")

        time.sleep(2)
        return p_ret
    except Exception, e:
        if DEBUG:
            print(e)
        return None

def get_profile(service, access_token, api, useauth, *reqq):
    req = pokemon_pb2.RequestEnvelop()

    req1 = req.requests.add()
    req1.type = 2
    if len(reqq) >= 1:
        req1.MergeFrom(reqq[0])

    req2 = req.requests.add()
    req2.type = 126
    if len(reqq) >= 2:
        req2.MergeFrom(reqq[1])

    req3 = req.requests.add()
    req3.type = 4
    if len(reqq) >= 3:
        req3.MergeFrom(reqq[2])

    req4 = req.requests.add()
    req4.type = 129
    if len(reqq) >= 4:
        req4.MergeFrom(reqq[3])

    req5 = req.requests.add()
    req5.type = 5
    if len(reqq) >= 5:
        req5.MergeFrom(reqq[4])

    return api_req(service, api, access_token, req, useauth = useauth)

def get_api_endpoint(service, access_token, api = API_URL):
    p_ret = get_profile(service, access_token, api, None)
    try:
        return ('https://%s/rpc' % p_ret.api_url)
    except:
        return None


def login_google(username, password):
    print('[+] Google User: {}'.format(username))
    ANDROID_ID = '9774d56d682e549c'
    SERVICE= 'audience:server:client_id:848232511240-7so421jotr2609rmqakceuu1luuq0ptb.apps.googleusercontent.com'
    APP = 'com.nianticlabs.pokemongo'
    CLIENT_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'
    r1 = perform_master_login(username, password, ANDROID_ID)
    r2 = perform_oauth(username, r1.get('Token', ''), ANDROID_ID, SERVICE, APP, CLIENT_SIG)
    return r2.get('Auth') # access token

def login_ptc(username, password):
    print('[!] PTC User: {}'.format(username))
    head = {'User-Agent': 'niantic'}
    r = SESSION.get(LOGIN_URL, headers=head)
    jdata = json.loads(r.content)
    data = {
        'lt': jdata['lt'],
        'execution': jdata['execution'],
        '_eventId': 'submit',
        'username': username,
        'password': password,
    }
    r1 = SESSION.post(LOGIN_URL, data=data, headers=head)

    ticket = None
    try:
        ticket = re.sub('.*ticket=', '', r1.history[0].headers['Location'])
    except Exception as e:
        if DEBUG:
            print(r1.json()['errors'][0])
        return None

    data1 = {
        'client_id': 'mobile-app_pokemon-go',
        'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
        'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
        'grant_type': 'refresh_token',
        'code': ticket,
    }
    r2 = SESSION.post(LOGIN_OAUTH, data=data1)
    access_token = re.sub('&expires.*', '', r2.content)
    access_token = re.sub('.*access_token=', '', access_token)
    return access_token

def heartbeat(service, api_endpoint, access_token, response):
    m4 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleInt()
    m.f1 = int(time.time() * 1000)
    m4.message = m.SerializeToString()
    m5 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleString()
    m.bytes = "05daf51635c82611d1aac95c0b051d3ec088a930"
    m5.message = m.SerializeToString()

    walk = sorted(getNeighbors())

    m1 = pokemon_pb2.RequestEnvelop.Requests()
    m1.type = 106
    m = pokemon_pb2.RequestEnvelop.MessageQuad()
    m.f1 = ''.join(map(encode, walk))
    m.f2 = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000"
    m.lat = COORDS_LATITUDE
    m.long = COORDS_LONGITUDE
    m1.message = m.SerializeToString()
    response = get_profile( 
        service,
        access_token,
        api_endpoint,
        response.unknown7,
        m1,
        pokemon_pb2.RequestEnvelop.Requests(),
        m4,
        pokemon_pb2.RequestEnvelop.Requests(),
        m5)
    try:
        payload = response.payload[0]
    except Exception as e:
        return("failed")
    else:
        heartbeat = pokemon_pb2.ResponseEnvelop.HeartbeatPayload()
        heartbeat.ParseFromString(payload)
        return heartbeat

def main():
    pokemons = json.load(open('pokemon.json'))
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", help="PTC Username", required=True)
    parser.add_argument("-p", "--password", help="PTC Password", required=True)
    parser.add_argument("-l", "--location", help="Location", required=True)
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("-e", "--evolved",  help="Only show evolved Pokemon", action='store_true')
    parser.add_argument("-ev", "--evolved-verbose",  help="Show evolved Pokemon, but also show ignored in one line", action='store_true')
    parser.add_argument("-a", "--alert", help="Places an extra alert around requested PokemonIds or Pokemon Names.", action="append")
    parser.add_argument("-A", "--address", help="Shows the address of the pokemon in addition to the coordinates.", action='store_true')
    parser.add_argument("-L", "--log", help="Enable logging to file", action='store_true')
    parser.add_argument("-g", "--google-auth", help="Uses Google auth instead of PTC", action='store_true')
    parser.set_defaults(DEBUG=False)
    args = parser.parse_args()

    if args.debug:
        global DEBUG
        DEBUG = True
        print('[*] Debug Mode Enabled')

    if args.evolved or args.evolved_verbose:
        print("[*] Tracking: Evolved Only")

    if args.alert:
        print("[*] Alerts: Enabled")

    if args.address:
        print("[*] Address Format: Enabled")

    if args.alert:
        alertlist = [x for x in args.alert[0].split(',')]

    if args.log:
        print("[*] Logging: Enabled - history.log")
        try:
            f = open("history.log","a+")
        except:
            print("[-] Unable to Write Log")

    set_location(args.location)

    service = "ptc"
    if args.google_auth:
        service = "google"
        access_token = login_google(args.username, args.password)
    else:
        access_token = login_ptc(args.username, args.password)

    if access_token is None:
        print('[-] Wrong username/password')
        return
    print('[+] RPC Session Token: {} ...'.format(access_token[:25]))

    api_endpoint = get_api_endpoint(service, access_token)
    if api_endpoint is None:
        print('[-] RPC Server Offline')
        return
    print('[+] Received API Endpoint: {}'.format(api_endpoint))

    response = get_profile(service, access_token, api_endpoint, None)
    if response is not None:
        #print('[+] Login Successful')

        payload = response.payload[0]
        profile = pokemon_pb2.ResponseEnvelop.ProfilePayload()
        profile.ParseFromString(payload)
        print('[+] Username: {}'.format(profile.profile.username))

        creation_time = datetime.fromtimestamp(int(profile.profile.creation_time)/1000)
        print('[+] Character Creation: {}'.format(
            creation_time.strftime('%Y-%m-%d %H:%M:%S'),
        ))

        for curr in profile.profile.currency:
            print('[+] {}: {}'.format(curr.type, curr.amount))
    else:
        print('[-] Login Error')

    origin = LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)
    while True:
        #All Evolved
        evolvedlist = ['2','3','5','6','8','9','11','12','14','15','17','18','20','22','24','26','28','30','31','33','34','36','38','40','42','44','45','47','49','51','53','55','57','59','61','62','64','65','67','68','70','71','73','75','76','78','80','82','85','87','89','91','93','94','97','99','101','103','105','107','110','112','117','119','121','130','134','135','136','139','141','149']
       
        #No Pidgeotto, Raticate, Kakuna, Metapod
        #evolvedlist = ['2','3','5','6','8','9','12','15','18','22','24','26','28','30','31','33','34','36','38','40','42','44','45','47','49','51','53','55','57','59','61','62','64','65','67','68','70','71','73','75','76','78','80','82','85','87','89','91','93','94','97','99','101','103','105','107','110','112','117','119','121','130','134','135','136','139','141','149']        
        original_lat = FLOAT_LAT
        original_long = FLOAT_LONG
        parent = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)).parent(15)

        for x in range(16):
            h = heartbeat(service, api_endpoint, access_token, response)
            if x == 15:
                print("Connection Terminated")
                return
            try:
                if "failed" not in h:
                    pass
            except:
                break
            else:
                print("Connetion Error: Retrying in 5 seconds... Attempt: %d" % x)
                time.sleep(5)
        hs = [h]
        seen = set([])
        for child in parent.children():
            latlng = LatLng.from_point(Cell(child).get_center())
            set_location_coords(latlng.lat().degrees, latlng.lng().degrees, 0)
            hs.append(heartbeat(service, api_endpoint, access_token, response))
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

        # print('')
        # for cell in h.cells:
        #     if cell.NearbyPokemon:
        #         other = LatLng.from_point(Cell(CellId(cell.S2CellId)).get_center())
        #         diff = other - origin
        #         # print(diff)
        #         difflat = diff.lat().degrees
        #         difflng = diff.lng().degrees
        #         direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
        #         print("Within one step of %s (%sm %s from you):" % (other, int(origin.get_distance(other).radians * 6366468.241830914), direction))
        #         for poke in cell.NearbyPokemon:
        #             print('    (%s) %s' % (poke.PokedexNumber, pokemons[poke.PokedexNumber - 1]['Name']))

        # print('')
        if args.evolved or args.evolved_verbose:
            found = False
            skipped_list = []
        for poke in visible:
            other = LatLng.from_degrees(poke.Latitude, poke.Longitude)
            diff = other - origin
            # print(diff)
            difflat = diff.lat().degrees
            difflng = diff.lng().degrees
            direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')

            found_pokemon = "(%s) %s is visible at (%s, %s) for %s seconds (%sm %s from you)" % (poke.pokemon.PokemonId, pokemons[poke.pokemon.PokemonId - 1]['Name'], poke.Latitude, poke.Longitude, poke.TimeTillHiddenMs / 1000, int(origin.get_distance(other).radians * 6366468.241830914), direction)
            if args.log:
                timestamp = str(datetime.utcnow().strftime("[%Y-%m-%d %H:%M:%S]"))
                log_message = "%s\t%s - %s       \t(%s, %s)" % (timestamp, poke.pokemon.PokemonId, pokemons[poke.pokemon.PokemonId - 1]['Name'], poke.Latitude, poke.Longitude)
                f.write(log_message + "\n")

            if args.address:
                try:
                    geolocator = Nominatim()
                    location = geolocator.reverse("%s, %s" % (poke.Latitude, poke.Longitude))
                except:
                    try:
                        time.sleep(5)
                        geolocator = Nominatim()
                        location = geolocator.reverse("%s, %s" % (poke.Latitude, poke.Longitude))
                    except:
                        location = "GeoLocator Connection Timed Out"
            if args.alert and str(poke.pokemon.PokemonId) in alertlist:
                print("")
                print("[+]    ==========================FOUND A %s============================" % pokemons[poke.pokemon.PokemonId - 1]['Name'].upper())
                print("[+]    " + found_pokemon)
                if args.address:
                    print("[+] Address: %s" % location)
                print("[+]    =====================================================================")
                print("")
                if args.evolved:
                    found = True     
            elif args.evolved or args.evolved_verbose:
                if str(poke.pokemon.PokemonId) in evolvedlist:
                    print(" - " + found_pokemon)
                    if args.address:
                        print(" - Address: %s" % location)
                    found = True
                    print("")

                else:
                    skipped_list.append(pokemons[poke.pokemon.PokemonId - 1]['Name'])
            else:
                print(" - " + found_pokemon)                
                if args.address:
                    print(" - Address: %s" % location)

        if args.evolved_verbose:
            if not found:
                if not not skipped_list: # if it is not empty
                    print_string = ""
                    for x in skipped_list:
                        print_string += x + ", "
                    print("[I] : " + print_string[:-2])
        # print('')
        walk = getNeighbors()
        next = LatLng.from_point(Cell(CellId(walk[2])).get_center())
        time.sleep(10)
        set_location_coords(next.lat().degrees, next.lng().degrees, 0)
    f.close()
if __name__ == '__main__':
    main()
