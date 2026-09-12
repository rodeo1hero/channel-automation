#!/usr/bin/env python3
"""One-time interactive script: run this locally on your own machine (not in CI)
to generate a long-lived YouTube refresh token for the automation pipeline.

Prerequisites (see ../SETUP_YOUTUBE_API.md for the full walkthrough):
  1. A Google Cloud project with the YouTube Data API v3 enabled.
  2. An OAuth 2.0 Client ID of type "Desktop app", downloaded as client_secret.json
     and placed next to this script.
  3. The OAuth consent screen's publishing status set to "In production"
     (Testing-mode tokens expire after 7 days — no good for unattended automation).

Usage:
    pip install google-auth-oauthlib
    python3 get_youtube_refresh_token.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    # Opens a browser window; log in with the Google account that owns your YouTube channel.
    creds = flow.run_local_server(port=0)

    print("\nSuccess. Add these as GitHub Actions repo secrets (or your .env):\n")
    print(f"YOUTUBE_CLIENT_ID={creds.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={creds.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")

if __name__ == "__main__":
    main()
