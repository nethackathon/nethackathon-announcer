# Nethack Announcer

A discord bot which announces when people go live streaming nethack on twitch

To run the backend:

1. Put the secret credentials in a file called `.env`
2. `docker run --name nethack-announcer --detach --restart unless-stopped --env-file .env registry.gitlab.com/danielkinsman/nethack-announcer:main`

You don't need to download or clone the repo.

The env vars file should look like this:

    TWITCH_CLIENT_ID=someclientid
    TWITCH_CLIENT_SECRET=supersecret
    DISCORD_BOT_TOKEN=alsosupersecret
    DISCORD_CHANNEL=12345

To add the bot to your discord server click this link:

https://discord.com/api/oauth2/authorize?client_id=1156399244350083203&permissions=18432&scope=bot

## Updating

To update to a newer version:

1. `docker pull registry.gitlab.com/danielkinsman/nethack-announcer:main`
2. `docker container stop nethack-announcer`
3. `docker container rm nethack-announcer`
4. `docker run --name nethack-announcer --detach --restart unless-stopped --env-file .env registry.gitlab.com/danielkinsman/nethack-announcer:main`

## Mastodon

To run mastodon announcements as well, you'll need to generate an access token. First set the following env vars:

    export MASTODON_URL="https://mastodon.social"
    export MASTODON_CLIENT_ID="someclientid"
    export MASTODON_CLIENT_SECRET="someclientsecret"

Then:

1. make yourself a python virtual environment (e.g. virtualenv mastodon)
2. activate it (e.g. 'source mastodon/bin/activate`)
3. run `pip install -r requirements.txt`
4. run `python mastodon_access_token.py` and follow the instructions it gives you

I'm not sure how long the access token is valid for...
