#! /usr/bin/env python

import logging
import oauthlib.oauth2
import os
import requests
import requests_oauthlib


CLIENT_ID_ENV = "TWITCH_CLIENT_ID"
CLIENT_SECRET_ENV = "TWITCH_CLIENT_SECRET"
NETHACK_TWITCH_GAME_ID = 130
# get again with this:
#   response = twitch.get("https://api.twitch.tv/helix/games?name=nethack&name=nethack-1987")


def twitch_session():
    client_id = os.environ[CLIENT_ID_ENV]
    client_secret = os.environ[CLIENT_SECRET_ENV]
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    response = requests.post("https://id.twitch.tv/oauth2/token", data=data)
    response.raise_for_status()

    token = response.json()['access_token']

    session = requests.Session()
    session.headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id,
    }

    return session


def main():
    twitch = twitch_session()
    response = twitch.get(f"https://api.twitch.tv/helix/streams?game_id={NETHACK_TWITCH_GAME_ID}&type=live")
    print(response.json())


if __name__ == "__main__":
    main()
