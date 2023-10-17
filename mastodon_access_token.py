#! /usr/bin/env python

from mastodon import Mastodon
import os


MASTODON_CLIENT_ID_ENV = "MASTODON_CLIENT_ID"
MASTODON_CLIENT_SECRET_ENV = "MASTODON_CLIENT_SECRET"
MASTODON_URL_ENV = "MASTODON_URL"
MASTODON_SCOPES = tuple(["write:statuses"])


def create_mastodon_app():
    creds = Mastodon.create_app(
        "nethack-announcer",
        scopes=MASTODON_SCOPES,
        api_base_url=os.getenv(MASTODON_URL_ENV, "https://mastodon.social"),
        website="https://nethackathon.org",
    )
    print("mastodon app details:")
    print(creds)
    print("You'll need these in your env when getting the access token")


def get_mastodon_access_token():
    mastodon = Mastodon(
        client_id=os.environ[MASTODON_CLIENT_ID_ENV],
        api_base_url=os.getenv(MASTODON_URL_ENV, "https://mastodon.social"),
        client_secret=os.environ[MASTODON_CLIENT_SECRET_ENV],
    )

    url = mastodon.auth_request_url(scopes=MASTODON_SCOPES)
    print(f"please visit mastodon auth url: {url}")
    code = input("paste the code: ")
    access_token = mastodon.log_in(code=code, scopes=MASTODON_SCOPES)
    print("add this to your .env for nethack announcer:")
    print(f"MASTODON_ACCESS_TOKEN={access_token}")


if __name__ == "__main__":
    #create_mastodon_app()  # only needs to be done once ever
    get_mastodon_access_token()
