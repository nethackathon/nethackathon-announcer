#! /usr/bin/env python

import asyncio
import aiohttp
import datetime
import discord
import discord.ext.tasks
import logging
from mastodon import Mastodon
import os


TWITCH_CLIENT_ID_ENV = "TWITCH_CLIENT_ID"
TWITCH_CLIENT_SECRET_ENV = "TWITCH_CLIENT_SECRET"
TWITCH_GAME_ID = int(os.getenv("TWITCH_GAME_ID", "130"))
#TWITCH_GAME_ID = 516575 # valorant for testing
# get again with this:
#   https://api.twitch.tv/helix/games?name=nethack&name=nethack-1987
TWITCH_QUERY = f"https://api.twitch.tv/helix/streams?game_id={TWITCH_GAME_ID}&type=live"

DISCORD_BOT_TOKEN_ENV = "DISCORD_BOT_TOKEN"
DISCORD_CHANNEL_ENV = "DISCORD_CHANNEL"

MASTODON_URL_ENV = "MASTODON_URL"
MASTODON_ACCESS_TOKEN_ENV = "MASTODON_ACCESS_TOKEN"
MASTODON_SCOPES = tuple(["write:statuses"])
MASTODON_HASHTAGS = "#NetHack #RogueLike"

NETHACKATHON_API_EVENT = "https://api.nethackathon.org/event/current"

POLL_TIME = int(os.getenv("TWITCH_POLL_TIME", "120"))
STREAM_EXPIRY = datetime.timedelta(minutes=60)


class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.announced_streams = dict()
        self.mastodon = kwargs.get("mastodon")

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
                    self.twitch_request_headers = dict()

    @discord.ext.tasks.loop(seconds=POLL_TIME)
    async def poll_twitch(self):
        async with aiohttp.ClientSession(headers=self.twitch_request_headers) as session:
            # Screw pagination, there are never going to be more than 20 people streaming nethack at the same time right?
            async with session.get(TWITCH_QUERY) as response:
                if 200 <= response.status <= 299:
                    js = await response.json()
                    await self.announce(js["data"])
                elif response.status in {401, 403}:
                    logging.error(f"Got {response.status} from twitch, redoing auth")
                    await self.twitch_auth()
                else:
                    logging.error(f"Got {response.status} from twitch")

    @poll_twitch.before_loop
    async def wait(self):
        await asyncio.gather(self.wait_until_ready(), self.twitch_auth())

    async def announce(self, streams):
        channel_id = int(os.environ[DISCORD_CHANNEL_ENV])
        channel = self.get_channel(channel_id)
        if not channel:
            logging.error(f"Couldn't get discord channel {channel_id}")
            return

        nethackathon_live = await is_nethackathon_live()

        current_streams = dict()
        for st in streams:
            streamer = st["user_login"]
            if streamer in self.announced_streams:
                current_streams[streamer] = self.announced_streams[streamer]
                logging.debug(f"{streamer} already announced")
                continue

            message = f"{st['user_name']} is streaming {st.get('game_name', 'Nethack')}!"
            if nethackathon_live:
                message = f"{st['user_name']} is streaming for Nethackathon! https://nethackathon.org"

            title = st.get("title")
            if title:
                message += f"\n{title}"

            link = f"https://twitch.tv/{st['user_login']}"
            logging.info(message)
            try:
                await channel.send(f"{message}\n{link}")
                if self.mastodon:
                    hashtags = MASTODON_HASHTAGS
                    hashtags += " #Nethackathon" if nethackathon_live else ""
                    self.mastodon.status_post(f"{message} {hashtags}\n{link}")  # synchronous, sad
                    # may get discord spam if mastodon throws errors often

                current_streams[streamer] = datetime.datetime.now()
            except Exception as e:
                logging.exception(e)
    
        # prune old streams
        self.announced_streams = {
            s: dt for s, dt in self.announced_streams.items()
            if datetime.datetime.now() - dt < STREAM_EXPIRY
        }
        # but add back in ones that are still going
        self.announced_streams.update(current_streams)
        # this avoids spam if people stop and restart the stream within STREAM_EXPIRY


async def is_nethackathon_live() -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(NETHACKATHON_API_EVENT) as response:
                if 200 <= response.status <= 299:
                    js = await response.json()
                    start = datetime.datetime.fromisoformat(js["currentEvent"]["event_start"])
                    end = datetime.datetime.fromisoformat(js["currentEvent"]["event_end"])
                    return start <= datetime.datetime.now(tz=datetime.timezone.utc) <= end

                logging.error(f"Got {response.status} from nethackathon")
    except Exception as e:
        logging.error("Failed to determine if nethackathon is live")
        logging.exception(e)

    return False


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(name)s:%(levelname)s %(message)s")
    logging.info("Starting")

    try:
        mastodon = Mastodon(
            api_base_url=os.getenv(MASTODON_URL_ENV, "https://mastodon.social"),
            access_token=os.environ[MASTODON_ACCESS_TOKEN_ENV],
        )
    except Exception as e:
        logging.exception(e)
        logging.error("Could not log in to mastodon, starting without it")
        mastodon = None

    intents = discord.Intents(guilds=True)
    discord_client = DiscordClient(intents=intents, mastodon=mastodon)
    discord_client.run(os.environ[DISCORD_BOT_TOKEN_ENV])


if __name__ == "__main__":
    main()
