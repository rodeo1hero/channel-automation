# Automated Channel Pipeline — Architecture & Stack

Goal: a solo-run pipeline that takes the channel's format (short pop-science/psychology
video essays — "take an everyday thing and reveal the hidden mechanism behind it") from
topic idea all the way to a published YouTube video, with no manual steps once configured.

## Pipeline stages

1. **Idea queue** — a simple `config/topics_queue.yaml` list of upcoming topics (you can
   seed it, e.g. "What it actually meant to be a knight"). When the queue runs low, Claude
   proposes new topics in the channel's niche, checking `state/history.json` so it never
   repeats a topic.
2. **Script writing** — Claude (Anthropic API) turns a topic into: a title, a scene-by-scene
   narration script, and a visual prompt per scene (this mirrors the idea → script → visual
   prompt process you already do by hand).
3. **Voiceover (TTS)** — the script is synthesized to speech, one audio clip per scene, so
   each scene's exact spoken duration is known (needed to time the visuals).
4. **Visuals** — an AI image model generates 1–3 images per scene from its visual prompt.
   Images are combined with a slow pan/zoom ("Ken Burns") effect rather than full AI video
   generation — much cheaper, and it fits a documentary/essay style well.
5. **Captions** — Whisper transcribes the finished voiceover to generate accurately-timed
   burned-in or soft captions.
6. **Assembly** — ffmpeg stitches audio + panned images + captions (+ optional royalty-free
   background music) into the final .mp4.
7. **Thumbnail + metadata** — one higher-quality image plus a title/description/tags pass
   from Claude, written for YouTube SEO in the channel's niche.
8. **Upload** — the YouTube Data API v3 uploads the video, sets the thumbnail, and publishes
   (or schedules) it on your existing channel.
9. **History log** — every run appends to `state/history.json` (topic, title, publish date,
   video id) so future idea-generation and metadata avoid repeats.

## Recommended stack (optimized for a solo creator's budget)

| Stage | Tool | Why | Approx. cost |
|---|---|---|---|
| Script + ideas + metadata | Claude (Anthropic API) | Already your voice/format | ~$0.05–0.15/video |
| Voiceover | Google Cloud TTS (Neural2/Chirp HD voices) | Near-ElevenLabs quality, ~8x cheaper than ElevenLabs | ~$0.014/min → ~$0.15/video for a 10-min video |
| Visuals | FLUX.2 [Pro] (via Replicate or fal.ai) | Strong quality-per-dollar, ~$0.03/image | ~$0.30–0.60/video (10–20 images) |
| Captions | Whisper (open source, runs free) | Accurate forced alignment, no API cost | $0 |
| Assembly | ffmpeg (scripted, no GUI editor) | Free, fully scriptable | $0 |
| Upload | YouTube Data API v3 | Official, required for automated publishing | Free (well within the 10,000 unit/day quota — an upload costs 1,600 units, so 6/day is possible) |

**Total: roughly $0.50–$1.00 in API costs per video.**

If you'd rather prioritize voice quality over cost, swap in ElevenLabs (~$0.11–0.15/min,
so ~$1.10–1.50 for a 10-minute video) — the code is written so the TTS provider is a
single swappable module.

## Where it runs ("fully by itself")

A chat session isn't persistent infrastructure, so the pipeline is built as a normal
Python repo that runs on **GitHub Actions** on a cron schedule (e.g. twice a week):
GitHub Actions is free for this volume, keeps your API keys as encrypted repo secrets,
and needs no server to maintain. This is the standard way solo creators run "channel runs
itself" automation reliably. (Alternative: any small always-on VPS with a cron job — the
same script runs unchanged either way.)

## One-time human setup (can't be automated — Google requires you personally)

1. Create a Google Cloud project, enable the YouTube Data API v3.
2. Create OAuth 2.0 credentials and generate a long-lived refresh token for your channel's
   Google account (one script, run once, see `SETUP_YOUTUBE_API.md`).
3. Get API keys for: Anthropic (Claude), Google Cloud TTS, and an image-gen provider
   (Replicate or fal.ai account).
4. Push the repo to GitHub and add the above as repository secrets.

After that, the schedule runs unattended: it pulls the next topic, produces a full video,
and publishes it.
