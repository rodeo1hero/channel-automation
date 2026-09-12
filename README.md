# Channel automation pipeline

Turns a topic into a finished, uploaded YouTube video with no manual steps:
idea → script → voiceover → visuals → captions → assembly → thumbnail → upload.

See `ARCHITECTURE.md` for the full design and stack rationale, and
`SETUP_YOUTUBE_API.md` for the one-time YouTube/Google Cloud setup.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Test the whole pipeline with mock data, no API keys needed:
python run_pipeline.py --dry-run

# Real run (needs .env filled in — copy from .env.example):
cp .env.example .env   # then fill in your keys
python run_pipeline.py
```

## Editing the channel's voice/format

Everything creative lives in `config/channel_config.yaml` (tone, niche, target
length, TTS voice, visual style) and `config/topics_queue.yaml` (upcoming
topics — add to this list any time; the pipeline asks Claude for a new idea
automatically once it runs dry).

## Running unattended

`.github/workflows/publish.yml` runs the pipeline on a schedule via GitHub
Actions (free for this volume) once you've pushed this repo to GitHub and
added the required secrets — see `SETUP_YOUTUBE_API.md` for the full list.
You can also trigger a run manually from the repo's Actions tab
("Run workflow") to test before trusting the schedule.

## Swapping providers

- TTS: `pipeline/voiceover.py` — currently Google Cloud TTS; ElevenLabs would
  be a second `_synthesize_elevenlabs()` function plus a `TTS_PROVIDER` check.
- Images: `pipeline/visuals.py` — currently Replicate/FLUX; swap the model
  string or the API call to use a different provider.
