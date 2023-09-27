#! /usr/bin/env python

import asyncio
import aiohttp
import discord
import discord.ext.tasks
import logging
import os


TWITCH_CLIENT_ID_ENV = "TWITCH_CLIENT_ID"
TWITCH_CLIENT_SECRET_ENV = "TWITCH_CLIENT_SECRET"
NETHACK_TWITCH_GAME_ID = 130
NETHACK_TWITCH_GAME_ID = 516575 # valorant for testing
# get again with this:
#   response = twitch.get("https://api.twitch.tv/helix/games?name=nethack&name=nethack-1987")
TWITCH_QUERY = f"https://api.twitch.tv/helix/streams?game_id={NETHACK_TWITCH_GAME_ID}&type=live"

DISCORD_BOT_TOKEN_ENV = "DISCORD_BOT_TOKEN"
DISCORD_CHANNEL = 1156444485442617464

POLL_TIME = 60


class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.announced_streams = set()

    async def setup_hook(self):
        self.poll_twitch.start()

    async def on_ready(self):
        logging.info(f"Discord logged in as {self.user}")

    async def twitch_auth(self):
        self.twitch_client_id = os.environ[TWITCH_CLIENT_ID_ENV]
        client_secret = os.environ[TWITCH_CLIENT_SECRET_ENV]
        data = {
            "client_id": self.twitch_client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://id.twitch.tv/oauth2/token", json=data) as response:
                if 200 <= response.status <= 299:
                    js = await response.json()
                    self.twitch_request_headers = {
                        "Authorization": f"Bearer {js['access_token']}",
                        "Client-Id": self.twitch_client_id,
                    }
                    logging.info("Successfully logged in to twitch")
                else:
                    logging.error(f"Could not log in to twitch, http status {response.status}")

    @discord.ext.tasks.loop(seconds=POLL_TIME)
    async def poll_twitch(self):
        async with aiohttp.ClientSession(headers=self.twitch_request_headers) as session:
            # Screw pagination, there are never going to be more than 20 people streaming nethack at the same time right?
            async with session.get(TWITCH_QUERY) as response:
                if 200 <= response.status <= 299:
                    js = await response.json()
                    await self.announce(js["data"])

    @poll_twitch.before_loop
    async def wait(self):
        await asyncio.gather(self.wait_until_ready(), self.twitch_auth())

    async def announce(self, streams):
        channel = self.get_channel(DISCORD_CHANNEL)
        current_streams = set()
        for st in streams:
            stream_key = (st["user_login"], st["started_at"])
            current_streams.add(stream_key)
            if stream_key in self.announced_streams:
                continue

            message = f"{st['user_name']} is streaming Nethack!"
            link = f"https://twitch.tv/{st['user_login']}"
            logging.info(message)
            await channel.send(f"{message}\n{link}")

        self.announced_streams = current_streams


def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting")

    discord_client = DiscordClient(intents=discord.Intents.default())
    discord_client.run(os.environ[DISCORD_BOT_TOKEN_ENV])


if __name__ == "__main__":
    main()
