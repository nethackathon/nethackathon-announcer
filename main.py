#! /usr/bin/env python

import logging
import os
import requests
import requests.exceptions
import time


CLIENT_ID_ENV = "TWITCH_CLIENT_ID"
CLIENT_SECRET_ENV = "TWITCH_CLIENT_SECRET"
NETHACK_TWITCH_GAME_ID = 130
#NETHACK_TWITCH_GAME_ID = 516575 # valorant for testing
# get again with this:
#   response = twitch.get("https://api.twitch.tv/helix/games?name=nethack&name=nethack-1987")
POLL_TIME = 10
ERROR_RETRY_TIME = 120


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


def announce(stream):
    message = f"{stream['user_name']} is streaming Nethack!"
    link = "https://twitch.tv/{stream['user_login']}"

    announce_log(message, link)


def announce_log(message, link):
    logging.info(message)


def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting")
    announced_streamers = set()
    twitch = twitch_session()
    
    while True:
        try:
            # Screw pagination, there are never going to be more than 20 people streaming nethack at the same time right?
            response = twitch.get(f"https://api.twitch.tv/helix/streams?game_id={NETHACK_TWITCH_GAME_ID}&type=live")
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.exception(e)
            time.sleep(ERROR_RETRY_TIME)
            if e.status in {401, 403}:
                twitch = twitch.session()  # too lazy to use refresh token timeout
                continue
        except requests.exceptions.ConnectionError:
            logging.exception(e)
            time.sleep(ERROR_RETRY_TIME)
            continue

        current_streamers = set()
        for stream in response.json()["data"]:
            stream_key = (stream["user_login"], stream["started_at"])
            current_streamers.add(stream_key)
            if stream_key not in announced_streamers:
                announce(stream)

        announced_streamers = current_streamers
        time.sleep(POLL_TIME)


if __name__ == "__main__":
    main()
