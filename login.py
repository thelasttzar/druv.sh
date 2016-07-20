import re
import json
from datetime import datetime
import time

import settings
import pokemon_pb2

from gpsoauth import perform_master_login, perform_oauth
from s2sphere import CellId, LatLng
from google.protobuf.internal import encoder


def login_google(username, password):

    ANDROID_ID = '9774d56d682e549c'
    SERVICE = 'audience:server:client_id:848232511240-7so421jotr2609rmqakceuu1luuq0ptb.apps.googleusercontent.com'
    APP = 'com.nianticlabs.pokemongo'
    CLIENT_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'

    print('[+] Google User: %s' % username)

    r1 = perform_master_login(username, password, ANDROID_ID)
    r2 = perform_oauth(username,
                       r1.get('Token', ''),
                       ANDROID_ID,
                       SERVICE,
                       APP,
                       CLIENT_SIG)
    return r2.get('Auth')  # access token


def login_ptc(username, password):
    print('[+] PTC User: %s' % username)
    head = {'User-Agent': 'niantic'}
    r = settings.SESSION.get(settings.LOGIN_URL, headers=head)
    jdata = json.loads(r.content)
    data = {
        'lt': jdata['lt'],
        'execution': jdata['execution'],
        '_eventId': 'submit',
        'username': username,
        'password': password,
    }
    r1 = settings.SESSION.post(settings.LOGIN_URL, data=data, headers=head)

    ticket = None
    try:
        ticket = re.sub('.*ticket=', '', r1.history[0].headers['Location'])
    except:
        return None

    data1 = {
        'client_id': 'mobile-app_pokemon-go',
        'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
        'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
        'grant_type': 'refresh_token',
        'code': ticket,
    }
    r2 = settings.SESSION.post(settings.LOGIN_OAUTH, data=data1)
    access_token = re.sub('&expires.*', '', r2.content)
    access_token = re.sub('.*access_token=', '', access_token)
    return access_token


def get_api_endpoint(service, access_token, api):
    api = 'https://pgorelease.nianticlabs.com/plfe/rpc'
    p_ret = get_profile(service, access_token, api, None)
    try:
        return ('https://%s/rpc' % p_ret.api_url)
    except:
        return None


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

        r = settings.SESSION.post(api_endpoint, data=protobuf, verify=False)

        p_ret = pokemon_pb2.ResponseEnvelop()
        p_ret.ParseFromString(r.content)

        time.sleep(2)
        return p_ret
    except Exception:
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

    return api_req(service, api, access_token, req, useauth=useauth)


def heartbeat(service, api_endpoint, access_token, response):
    m4 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleInt()
    m.f1 = int(time.time() * 1000)
    m4.message = m.SerializeToString()
    m5 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleString()
    m.bytes = '05daf51635c82611d1aac95c0b051d3ec088a930'
    m5.message = m.SerializeToString()

    walk = sorted(getNeighbors())

    m1 = pokemon_pb2.RequestEnvelop.Requests()
    m1.type = 106
    m = pokemon_pb2.RequestEnvelop.MessageQuad()
    m.f1 = ''.join(map(encode, walk))
    m.f2 = '\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000'
    m.lat = settings.COORDS_LATITUDE
    m.long = settings.COORDS_LONGITUDE
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
    except:
        return('failed')
    else:
        heartbeat = pokemon_pb2.ResponseEnvelop.HeartbeatPayload()
        heartbeat.ParseFromString(payload)
        return heartbeat


def getNeighbors():
    origin = CellId.from_lat_lng(
        LatLng.from_degrees(settings.FLOAT_LAT, settings.FLOAT_LONG)).parent(15)
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


def encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)


def get_location_coords():
    return (settings.COORDS_LATITUDE, settings.COORDS_LONGITUDE, settings.COORDS_ALTITUDE)


def login(auth_service, username, password):

    if auth_service in ['ptc', 'google']:
        if auth_service == 'google':
            access_token = login_google(username, password)
        else:
            access_token = login_ptc(username, password)
    else:
        print('[-] Invalid Authentication Service')
        return

    if access_token is None:
        print('[-] Login Failed')
        return

    print('[+] RPC Token Assigned: %s' % (access_token[:25]))
    print '[+] Receiving API Endpoint...'

    api_endpoint = get_api_endpoint(auth_service, access_token, settings.API_URL)

    if api_endpoint is None:
        print('[-] RPC Server Offline')
        return
    print('[+] API Endpoint Assigned: %s' % api_endpoint)

    response = get_profile(auth_service, access_token, api_endpoint, None)

    if response is not None:
        print('[+] Login Successful')

        payload = response.payload[0]
        profile = pokemon_pb2.ResponseEnvelop.ProfilePayload()
        profile.ParseFromString(payload)

        print('[+] Username: %s ' % profile.profile.username)

        creation_time = datetime.fromtimestamp(
                        int(profile.profile.creation_time)/1000)
        print('[+] Character Creation: %s' % creation_time.strftime('%Y-%m-%d %H:%M:%S'))

        for curr in profile.profile.currency:
            print('[+] %s: %s' % (curr.type, curr.amount))

        print('')
    else:
        print('[-] Login Error')
    return api_endpoint, access_token, response
