# Nethack Announcer

A discord bot which announces when people go live streaming nethack on twitch

To run the backend:

1. Put the secret credentials in a file called `.env`
2. `docker run --name nethack-announcer --detach --restart unless-stopped --env-file .env registry.gitlab.com/danielkinsman/nethack-announcer:latest`

You don't need to download or clone the repo.

The env vars file should look like this:

    TWITCH_CLIENT_ID=someclientid
    TWITCH_CLIENT_SECRET=supersecret
    DISCORD_BOT_TOKEN=alsosupersecret
    DISCORD_CHANNEL=12345

To add the bot to your discord server click this link:

https://discord.com/api/oauth2/authorize?client_id=1156399244350083203&permissions=18432&scope=bot
