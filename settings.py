import requests


def init():
    global SESSION
    SESSION = requests.session()
    SESSION.headers.update({'User-Agent': 'Niantic App'})
    SESSION.verify = False

    global LOGIN_URL
    LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'

    global LOGIN_OAUTH
    LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'

    global API_URL
    API_URL = 'https://pgorelease.nianticlabs.com/plfe/rpc'

    global COORDS_LATITUDE
    COORDS_LATITUDE = 0
    global COORDS_LONGITUDE
    COORDS_LONGITUDE = 0
    global COORDS_ALTITUDE
    COORDS_ALTITUDE = 0

    global FLOAT_LAT
    FLOAT_LAT = 0
    global FLOAT_LONG
    FLOAT_LONG = 0
