#!/usr/bin/env python
import requests
import re
import struct
import json
import argparse
import pokemon_pb2
import time
import os
import sys
from ConfigParser import ConfigParser
from google.protobuf.internal import encoder

from gpsoauth import perform_master_login, perform_oauth
from datetime import datetime
from geopy.geocoders import GoogleV3, Nominatim
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from s2sphere import *
from adb_android import adb_android as adb


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
    print('[*] Location: %s  (%s, %s)' % (loc.address.encode('utf-8'), loc.latitude, loc.longitude))
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
    api = 'https://pgorelease.nianticlabs.com/plfe/rpc'
    p_ret = get_profile(service, access_token, api, None)
    try:
        return ('https://%s/rpc' % p_ret.api_url)
    except:
        return None

def login_google(username, password):
    print('[+] Google User: %s' % username)
    ANDROID_ID = '9774d56d682e549c'
    SERVICE= 'audience:server:client_id:848232511240-7so421jotr2609rmqakceuu1luuq0ptb.apps.googleusercontent.com'
    APP = 'com.nianticlabs.pokemongo'
    CLIENT_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'
    r1 = perform_master_login(username, password, ANDROID_ID)
    r2 = perform_oauth(username, r1.get('Token', ''), ANDROID_ID, SERVICE, APP, CLIENT_SIG)
    return r2.get('Auth') # access token

def login_ptc(username, password):
    print('[+] PTC User: %s' % username)
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
def scan():
    config = ConfigParser()
    config.read('pokemon.cfg')

    # Login settings
    username = config.get('Login1','username')
    password = config.get('Login1','password')
    auth_service = config.get('Login1','auth_service')
    location = config.get('Login1','location')

    # Program settings
    alert=config.get('Login1','alert')
    debug=config.get('Login1','debug')
    evolved=config.get('Login1','evolved')
    evolved_verbose=config.get('Login1','evolved_verbose')
    address=config.get('Login1','address')
    logging=config.get('Login1','logging')
    teleport=config.get('Login1','teleport')
    sounds=config.get('Login1','sounds')

    print("")

    if evolved.lower() in ["yes", "true", "t", "1"]:
        print("[*] Tracking: Evolved Only")
    else:
        evolved = False

    if evolved_verbose.lower() in ["yes", "true", "t", "1"]:
        print("[*] Tracking: Evolved Only")
    else:
        evolved_verbose = False

    if alert is not None:
        alerts = [x for x in alert.split(',')]
        alertlist = [ x for x in alerts if x.isdigit() ]
        
        with open('pokemon.json','r') as pokemonjson:
            pokefile = json.load(pokemonjson)
            alertstring = ""
            for x in alertlist:
                alertstring += pokefile[int(x) - 1]['Name'] + ", "
        print("[*] Alerts Enabled: %s" % alertstring[:-2])
    else:
        alert = False

    if address.lower() == "true":
        print("[*] Address Format: Enabled")
    else:
        address = False

    if logging.lower() == "true":
        print("[*] Logging: Enabled - history.json")
    else:
        logging = False

    if teleport.lower() == "true":
        print("[*] Teleporting: Enabled")
    else:
        teleport = False

    if sounds.lower() == "true":
        soundfile = config.get('Login1','soundfile')
        print("[*] Sounds: Enabled")
    else:
        sounds = False

    set_location(location)

    if auth_service in ['ptc','google']:
        if auth_service == 'google':
            access_token = login_google(username, password)
        else:
            access_token = login_ptc(username, password)
    else:
        print("[x] Invalid Authentication Service")
        return

    if access_token is None:
        print('[-] Log In Failed: Retrying in 60 Seconds...')
        time.sleep(60)
        return
    print('[+] RPC Token Assigned: %s' % (access_token[:25]))
    print '[+] Receiving API Endpoint...'
    api_endpoint = get_api_endpoint(auth_service, access_token)
    if api_endpoint is None:
        print('[-] RPC Server Offline: Retrying in 60 Seconds...')
        time.sleep(60)
        return
    print('[+] API Endpoint Assigned: %s' % api_endpoint)

    response = get_profile(auth_service, access_token, api_endpoint, None)
    if response is not None:
        print('[+] Login Successful')

        payload = response.payload[0]
        profile = pokemon_pb2.ResponseEnvelop.ProfilePayload()
        profile.ParseFromString(payload)
        print('[+] Username: %s ' % profile.profile.username)

        creation_time = datetime.fromtimestamp(int(profile.profile.creation_time)/1000)
        print('[+] Character Creation: %s' % creation_time.strftime('%Y-%m-%d %H:%M:%S'))

        for curr in profile.profile.currency:
            print('[+] %s: %s' % (curr.type, curr.amount))
    else:
        print('[x] Login Error')

    pokemons = json.load(open('pokemon.json'))
    origin = LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)
    while True:
        #All Evolved
        #evolvedlist = ['2','3','5','6','8','9','11','12','14','15','17','18','20','22','24','26','28','30','31','33','34','36','38','40','42','44','45','47','49','51','53','55','57','59','61','62','64','65','67','68','70','71','73','75','76','78','80','82','85','87','89','91','93','94','97','99','101','103','105','107','110','112','117','119','121','130','134','135','136','139','141','149']
       
        #No Pidgeotto 17, Pidgeot 18, Raticate 20, Kakuna 14, Metapod 11, Golbat 42, Poliwhirl 61, Nidorina 30, nidorino 33, fearow 22
        evolvedlist = ['2','3','5','6','8','9','12','15','24','26','28','31','34','36','38','40','44','45','47','49','51','53','55','57','59','62','64','65','67','68','70','71','73','75','76','78','80','82','85','87','89','91','93','94','97','99','101','103','105','107','110','112','117','119','121','130','134','135','136','139','141','149']        
        original_lat = FLOAT_LAT
        original_long = FLOAT_LONG
        parent = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)).parent(15)

        for x in range(6):
            h = heartbeat(auth_service, api_endpoint, access_token, response)
            if x == 5:
                print("Connection Terminated")
                return
            try:
                if "failed" not in h:
                    pass
            except:
                break
            else:
                print("Connection Error: Retrying in 5 seconds... Attempt: %d" % (x+1))
                time.sleep(5)
        hs = [h]
        seen = set([])
        for child in parent.children():
            latlng = LatLng.from_point(Cell(child).get_center())
            set_location_coords(latlng.lat().degrees, latlng.lng().degrees, 0)
            hs.append(heartbeat(auth_service, api_endpoint, access_token, response))
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

        if evolved or evolved_verbose:
            skipped_list = []
        for poke in visible:
            other = LatLng.from_degrees(poke.Latitude, poke.Longitude)
            diff = other - origin
            difflat = diff.lat().degrees
            difflng = diff.lng().degrees
            direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')

            found_pokemon = "(%s) %s is visible at (%s, %s) for %s seconds (%sm %s from you)" % (poke.pokemon.PokemonId, pokemons[poke.pokemon.PokemonId - 1]['Name'], poke.Latitude, poke.Longitude, poke.TimeTillHiddenMs / 1000, int(origin.get_distance(other).radians * 6366468.241830914), direction)
            if logging:
                timestamp = int(time.time())
                try:
                    with open("history.json","a+") as file:
                        json.dump({'PokemonID':str(poke.pokemon.PokemonId), 'Pokemon Name':pokemons[poke.pokemon.PokemonId - 1]['Name'], "Coordinates":{"X":poke.Latitude, "Y":poke.Longitude}, "Timestamp":timestamp}, file, indent=4)
                except:
                    print("Unable to Open Log File")

            if address:
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
            if alert and str(poke.pokemon.PokemonId) in alertlist:
                print("")
                print("[+]    ==========================FOUND A %s============================" % pokemons[poke.pokemon.PokemonId - 1]['Name'].upper())
                print("[+]    " + found_pokemon)
                if address:
                    print("[+] Address: %s" % location)
                print("[+]    =====================================================================")

                #code to teleport you to the target
                if teleport:    

                    #stops the shitty method from printing to stdout. 
                    sys.stdout=open(os.devnull,"w")

                    #starts fakegps service to teleport you
                    adb.shell("am startservice -a com.incorporateapps.fakegps.ENGAGE --ef lat %s --ef lng %s" % (poke.Latitude, poke.Longitude) )
                    if sounds:
                        try:
                            adb.shell("am start -a android.intent.action.VIEW -d file://%s -t audio/wav" % soundfile)
                        except:
                            pass
                    time.sleep(2)
                    adb.shell("monkey -p com.nianticlabs.pokemongo -c android.intent.category.LAUNCHER 1")

                    #restore stdout 
                    sys.stdout=sys.__stdout__
                    print("Teleporting to (%s, %s)" % (poke.Latitude, poke.Longitude))
                print("")

            elif evolved or evolved_verbose:
                if str(poke.pokemon.PokemonId) in evolvedlist:
                    print(" - " + found_pokemon)
                    if address:
                        print(" - Address: %s" % location)
                    print("")

                else:
                    skipped_list.append(pokemons[poke.pokemon.PokemonId - 1]['Name'])
            else:
                print(" - " + found_pokemon)                
                if address:
                    print(" - Address: %s" % location)

        if evolved_verbose:
            if not not skipped_list: # if it is not empty
                print_string = ""
                for x in skipped_list:
                    print_string += x + ", "
                print("[I] " + print_string[:-2])
        walk = getNeighbors()
        next = LatLng.from_point(Cell(CellId(walk[2])).get_center())
        time.sleep(10)
        set_location_coords(next.lat().degrees, next.lng().degrees, 0)
