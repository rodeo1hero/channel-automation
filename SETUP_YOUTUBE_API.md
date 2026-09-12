# One-time setup: YouTube Data API access

This part has to be done by you personally — Google requires the channel owner
to grant this consent interactively. It takes about 15 minutes and you only do
it once. It also sets up Google Cloud Text-to-Speech, since it lives in the
same free Google Cloud project.

## 1. Create a Google Cloud project

1. Go to https://console.cloud.google.com/ and sign in with the Google account
   that owns your YouTube channel.
2. Create a new project (top bar → "Select a project" → "New project"). Name
   it anything, e.g. "channel-automation".

## 2. Enable the APIs you need

In the Cloud Console search bar, enable both of these (search the name, click
"Enable"):
- **YouTube Data API v3**
- **Cloud Text-to-Speech API**

## 3. Set up the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**.
2. User type: **External**. App name: anything (e.g. "Channel Automation").
   Add your own email as the support email and developer contact.
3. Scopes: add `.../auth/youtube.upload`.
4. On the "Test users" step, add your own Google account's email.
5. Save. The app starts in **Testing** status.
6. **Important:** while in Testing, refresh tokens expire after 7 days, which
   breaks unattended automation. Once you've confirmed everything works
   (step 6 below), go back to this screen and click **"Publish app"** to move
   it to **Production**. For a single-user personal tool this doesn't require
   Google's verification review — you'll just see an "unverified app" warning
   the one time you authorize it in step 5, which is expected and fine to
   click through for your own app.

## 4. Create OAuth 2.0 credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**. Name it anything.
3. Download the JSON — save it as `client_secret.json` in this repo's
   `scripts/` folder (it's already in `.gitignore`, so it won't get committed).

## 5. Generate your refresh token (one-time, run locally on your own machine)

```bash
cd scripts
pip install google-auth-oauthlib
python3 get_youtube_refresh_token.py
```

This opens a browser window — log in with your channel's Google account and
approve access. The script then prints:

```
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
```

Save these — you'll add them as GitHub Actions secrets in step 7.

## 6. Verify the token isn't a 7-day one

Before publishing the app to Production (step 3.6), you can leave it in
Testing and confirm a real upload works end-to-end. Once confirmed, publish
the app so the refresh token stops expiring weekly.

## 7. Set up a service account for Text-to-Speech

1. Go to **IAM & Admin → Service Accounts → Create service account**.
2. Grant it the role **Cloud Text-to-Speech User** (or "Editor" for simplicity
   on a personal project).
3. Create a JSON key for it and download it.
4. This is the value that goes in `GOOGLE_APPLICATION_CREDENTIALS_JSON` — paste
   the entire file contents as one line/secret.

## 8. Get the remaining API keys

- **Anthropic (Claude)**: https://console.anthropic.com/ → API Keys →
  `ANTHROPIC_API_KEY`.
- **Replicate (image generation)**: https://replicate.com/ → Account →
  API tokens → `REPLICATE_API_TOKEN`.

## 9. Push the repo to GitHub and add secrets

1. Create a new (private is fine) GitHub repo and push this project to it.
2. In the repo, go to **Settings → Secrets and variables → Actions → New
   repository secret**, and add each of:
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`
   - `REPLICATE_API_TOKEN`
3. In the repo's **Actions** tab, run the "Publish next video" workflow
   manually once ("Run workflow") to confirm everything works before trusting
   the Monday/Thursday schedule.

That's the whole one-time setup — after this, the schedule in
`.github/workflows/publish.yml` runs on its own.
