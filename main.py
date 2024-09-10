#! /usr/bin/env python

import asyncio
import aiohttp
import datetime
import discord
import discord.ext.tasks
import itertools
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
NETHACKATHON_API_ENDED_GAMES = "https://api.nethackathon.org/endedGames"
NETHACKATHON_API_LIVELOG = "https://api.nethackathon.org/livelog"
NETHACKATHON_API_STREAMERS = "https://api.nethackathon.org/streamers"

POLL_TIME = int(os.getenv("TWITCH_POLL_TIME", "120"))
STREAM_EXPIRY = datetime.timedelta(minutes=60)


class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.announced_streams = dict()
        self.mastodon = kwargs.get("mastodon")
        self.max_log_time = -1

    async def setup_hook(self):
        self.poll_twitch.start()
        self.poll_nethackathon.start()

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
                    await self.announce_streams(js["data"])
                elif response.status in {401, 403}:
                    logging.error(f"Got {response.status} from twitch, redoing auth")
                    await self.twitch_auth()
                else:
                    logging.error(f"Got {response.status} from twitch")

    @poll_twitch.before_loop
    async def wait(self):
        await asyncio.gather(self.wait_until_ready(), self.twitch_auth())

    @discord.ext.tasks.loop(seconds=POLL_TIME)
    async def poll_nethackathon(self):
        try:
            if not await is_nethackathon_live():
                return

            result = await asyncio.gather(fetch_json(NETHACKATHON_API_LIVELOG), fetch_json(NETHACKATHON_API_ENDED_GAMES))
            messages = []
            for m in sorted(itertools.chain(*result), key=lambda x: x.get("time", 0)):
                if m.get("time", 0) <= self.max_log_time:
                    continue

                if m.get("type", 0) == 16384 or m["message"].endswith("on T:1"):
                    messages.append(m)

            if not messages:
                return

            # Suppress announcment of the first messages when we are restarted
            if self.max_log_time < 0:
                self.max_log_time = max(m.get("time", 0) for m in messages)
                return

            self.max_log_time = max(m.get("time", 0) for m in messages)

            msg = "\n".join(m["message"] for m in messages)
            await self.announce_discord(msg)
            self.announce_mastodon(f"{msg}\n#Nethackathon https://nethackathon.org")
        except Exception as e:
            logging.error("Couldn't announce nethackathon logs")
            logging.exception(e)

    @poll_nethackathon.before_loop
    async def wait_nethackathon(self):
        await self.wait_until_ready()

    async def announce_streams(self, streams):
        current_streams = dict()
        for st in streams:
            streamer = st["user_login"]
            if streamer in self.announced_streams:
                current_streams[streamer] = self.announced_streams[streamer]
                logging.debug(f"{streamer} already announced")
                continue

            results = await asyncio.gather(is_nethackathon_live(), is_nethackathon_participant(streamer))
            nethackathon_streamer = all(results)

            message = f"{st['user_name']} is streaming {st.get('game_name', 'Nethack')}!"
            if nethackathon_streamer:
                message = f"{st['user_name']} is streaming for Nethackathon! https://nethackathon.org"

            title = st.get("title")
            if title:
                message += f"\n{title}"

            link = f"https://twitch.tv/{st['user_login']}"
            logging.info(message)
            try:
                await self.announce_discord(f"{message}\n{link}")
                hashtags = MASTODON_HASHTAGS
                hashtags += " #Nethackathon" if nethackathon_streamer else ""
                self.announce_mastodon(f"{message} {hashtags}\n{link}")
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

    async def announce_discord(self, message):
        channel_id = int(os.environ[DISCORD_CHANNEL_ENV])
        channel = self.get_channel(channel_id)
        if not channel:
            logging.error(f"Couldn't get discord channel {channel_id}")
            return

        await channel.send(message)

    def announce_mastodon(self, message):
        if not self.mastodon:
            return

        self.mastodon.status_post(message)  # synchronous, sad


async def is_nethackathon_live() -> bool:
    try:
        js = await fetch_json(NETHACKATHON_API_EVENT)
        start = datetime.datetime.fromisoformat(js["currentEvent"]["event_start"])
        end = datetime.datetime.fromisoformat(js["currentEvent"]["event_end"])
        return start <= datetime.datetime.now(tz=datetime.timezone.utc) <= end
    except Exception as e:
        logging.error("Failed to determine if nethackathon is live")
        logging.exception(e)

    return False


async def is_nethackathon_participant(streamer: str) -> bool:
    try:
        js = await fetch_json(NETHACKATHON_API_STREAMERS)
        return any(streamer.lower() == x.get("username", "").lower() for x in js["streamers"])
    except Exception as e:
        logging.error("Failed to determine if streamer is participant")
        logging.exception(e)

    return False


async def fetch_json(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if 200 <= response.status <= 299:
                    return await response.json()

                logging.error(f"Got {response.status} from {url}")
    except Exception as e:
        logging.error(f"Failed to fetch {url}")
        raise


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
