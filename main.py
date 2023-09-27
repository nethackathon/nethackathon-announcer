#! /usr/bin/env python

import asyncio
import discord
import discord.ext.tasks
import logging
import os
import requests
import requests.exceptions


TWITCH_CLIENT_ID_ENV = "TWITCH_CLIENT_ID"
TWITCH_CLIENT_SECRET_ENV = "TWITCH_CLIENT_SECRET"
NETHACK_TWITCH_GAME_ID = 130
#NETHACK_TWITCH_GAME_ID = 516575 # valorant for testing
# get again with this:
#   response = twitch.get("https://api.twitch.tv/helix/games?name=nethack&name=nethack-1987")

DISCORD_CLIENT_ID_ENV = "DISCORD_CLIENT_ID"
DISCORD_CLIENT_SECRET_ENV = "DISCORD_CLIENT_SECRET"
DISCORD_BOT_TOKEN_ENV = "DISCORD_BOT_TOKEN"
DISCORD_PERMISSIONS = 18432
DISCORD_CHANNEL = 1156444485442617464

POLL_TIME = 60
ERROR_RETRY_TIME = 120


def twitch_session():
    client_id = os.environ[TWITCH_CLIENT_ID_ENV]
    client_secret = os.environ[TWITCH_CLIENT_SECRET_ENV]
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


class DiscordClient(discord.Client):
    async def setup_hook(self):
        self.poll_twitch.start()

    async def on_ready(self):
        logging.info(f"Discord logged in as {self.user}")

    @discord.ext.tasks.loop(seconds=POLL_TIME)
    async def poll_twitch(self):
        await self.announce({"user_name": "me", "user_login": "unit327"})

    @poll_twitch.before_loop
    async def wait(self):
        await self.wait_until_ready()

    async def announce(self, stream):
        message = f"{stream['user_name']} is streaming Nethack!"
        link = f"https://twitch.tv/{stream['user_login']}"

        logging.info(message)
        channel = self.get_channel(DISCORD_CHANNEL)
        await channel.send(f"{message}\n{link}")


def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting")

    announced_streamers = set()
    #twitch = twitch_session()
    discord_client = DiscordClient(intents=discord.Intents.default())
    discord_client.run(os.environ[DISCORD_BOT_TOKEN_ENV])
    return
    
    while True:
        try:
            # Screw pagination, there are never going to be more than 20 people streaming nethack at the same time right?
            response = twitch.get(f"https://api.twitch.tv/helix/streams?game_id={NETHACK_TWITCH_GAME_ID}&type=live")
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.exception(e)
            asyncio.sleep(ERROR_RETRY_TIME)
            if e.status in {401, 403}:
                twitch = twitch.session()  # too lazy to use refresh token timeout
                continue
        except requests.exceptions.ConnectionError:
            logging.exception(e)
            asyncio.sleep(ERROR_RETRY_TIME)
            continue

        current_streamers = set()
        for stream in response.json()["data"]:
            stream_key = (stream["user_login"], stream["started_at"])
            if stream_key not in announced_streamers:
                try:
                    announce(stream, discord_client)
                    current_streamers.add(stream_key)
                except Exception as e:
                    logging.exception(e)
                    #discord_client = discord_session()  # too lazy to use refresh token timeout

        announced_streamers = current_streamers
        asyncio.sleep(POLL_TIME)


if __name__ == "__main__":
    main()
