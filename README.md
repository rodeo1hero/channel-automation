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

## The character

The channel's recurring stick-figure character has one fixed identity (face,
head, body) but wears one of a handful of outfits (standard, historical,
business, casual, modern, financial — see `pipeline/character_gen.py`'s
`OUTFITS`) that Claude picks per video to match its topic/era. Poses aren't
pre-baked for every outfit up front — they're generated the first time a
given (outfit, pose) combination is actually needed, then cached to
`assets/character/<outfit>/*.png` forever after, so a later video reusing an
outfit generates nothing new for any pose it shares with an earlier one. See
`ARCHITECTURE.md`'s "The character: one identity, cached per outfit" section
for the full picture. Beyond the everyday gestures (point, wave, think,
walk/run, sit, ...), there's a money/business pose set (holding cash, a
stock chart, a calculator, a handshake with a second figure, going broke,
...) for finance-adjacent topics — see `pipeline/stickman/pose_descriptions.py`
for the full list. To pre-warm an outfit's cache by hand, or fix a pose
that came out wrong, run:

```bash
python3 scripts/generate_character.py --outfit historical --only think wave
```

## Supporting cast characters

Beyond the recurring narrator, a scene can bring in up to 2 temporary "cast" characters
who briefly interact with it -- a tax collector demanding payment, a guard, a merchant
haggling -- instead of the narrator just explaining everything to camera. These are
reusable ROLES (`pipeline/cast_gen.py`'s `CAST_ROLES`: authority, guard, wealthy, poor,
merchant, official), not one-off characters: each role gets dressed to match whatever
outfit/era the video is already using (the same standard/historical/business/casual/
modern/financial keys as the narrator's outfits), so "official" becomes a Roman tax
collector in a historical video and a modern-day bureaucrat in a business video, with no
extra work. `script_writer.py`'s prompt describes the system to Claude directly; a scene
gets a `"cast"` list with each member's role, pose (`pipeline/stickman/cast_descriptions.py`),
which side of the frame they stand on, and an optional short line of dialogue.

Cast dialogue shows as an on-screen speech bubble, not spoken audio -- no extra TTS
voice, no audio sync work, zero added narration cost. Sprites are cached the same way as
the narrator's, at `assets/cast/<role>/<outfit>/<pose>.png`, generated the first time a
given (role, outfit) combination is actually needed and reused free after that. A whole
role+outfit combination (every pose in `CAST_POSE_NAMES`) costs about the same as two of
the narrator's own calls, since it's one reference-image call plus one grid-sheet call
covering all of that role's poses at once (Replicate bills per call, not per pose drawn
in it).

To pre-warm a role's cache by hand:

```bash
python3 -c "from pipeline.cast_gen import ensure_cast_sprites; ensure_cast_sprites('official', 'historical', ['stand', 'offer', 'gesture_talk', 'refuse'])"
```

## Companion Shorts

Every run now also produces a vertical YouTube Short (`pipeline/shorts.py`) that promotes
the main video, uploaded right after it. Claude writes a separate ~20-30s hook script
(`pipeline/shorts_writer.py`) -- not a cut-down clip of the main narration, but its own
short narration built to make someone scrolling Shorts stop and tap through: the most
surprising claim from the video, a beat on why it's true, then an unresolved cliffhanger.
The Short reuses the main video's exact narrator/outfit (and cast, if any), and its
description links to the main video plus `#Shorts`.

Rendering is 9:16 vertical instead of 16:9 -- `pipeline/visuals.py`'s `aspect_ratio`
parameter controls this, threaded down to both the FLUX background calls (their own
`aspect_ratio` input) and the stick-figure compositing/Ken Burns math in
`ai_scene_renderer.py`, so both pieces stay in sync from one code path rather than a
second copy of the renderer. Character/cast sprites need no separate generation for the
vertical version -- they're transparent cutouts composited at whatever size the frame
calls for, so only new backgrounds (and any pose the main video hadn't already used) cost
anything.

A companion Short costs roughly the same as 2-3 extra scenes' worth of backgrounds (about
$0.10-0.15) on top of the main video's own cost, and a failed Short never blocks or
un-publishes the main video -- `run_pipeline.py` catches and logs a Short failure rather
than letting it fail the whole run.

Shorts render with no captions (`assemble_video`'s `captions_path` is passed as `None`)
-- the narrow 1080px-wide vertical frame made the main video's fixed-size burned-in
captions wrap to 4-5 lines and overlap the character, and per the user's request Shorts
skip subtitles entirely rather than trying to shrink/reflow them to fit.

To generate a Short for an already-published video by hand, see
`scripts/rome_short_trial.py` for the pattern (build a script dict shaped like
`script_writer.write_script()`'s own output, then walk it through
`voiceover.synthesize_scenes` -> `visuals.generate_scene_clips(..., aspect_ratio="9:16")`
-> `assemble.assemble_video(..., captions_path=None)`).

## Checking API spend

Every real (non-dry-run) API call the pipeline makes — Replicate character
sprites, Replicate/FLUX backgrounds, Google Cloud TTS — is logged with an
estimated cost to `state/api_usage.json` (`pipeline/cost_tracker.py`),
committed to the repo by the same GitHub Actions step that commits
`state/history.json`, so it accumulates across every scheduled run. Each
real `run_pipeline.py` run prints a cost breakdown for that run plus the
running total at the end. To check spend any time without waiting for a
run:

```bash
python3 scripts/show_usage.py            # full report: by API, by run, total to date
python3 scripts/show_usage.py <run_id>   # just one run's breakdown
```

These are estimates from known per-call pricing (see `PRICING` in
`pipeline/cost_tracker.py`), not a live balance pulled from Replicate or
Google — neither exposes the exact billed cost of a specific call via API.

## Swapping providers

- TTS: `pipeline/voiceover.py` — currently Google Cloud TTS; ElevenLabs would
  be a second `_synthesize_elevenlabs()` function plus a `TTS_PROVIDER` check.
- Backgrounds: `pipeline/scene_backgrounds.py` — currently FLUX 1.1 Pro via
  Replicate; swap the model string/API call to use a different provider.
- Outfits: add a new key to `pipeline/character_gen.py`'s `OUTFITS` dict with
  a short description of the look — `script_writer.py` picks up the new
  option automatically, no other change needed.
- Character poses/gestures: add a new pose (with its baked-in expression) to
  `pipeline/stickman/pose_descriptions.py`, register the name in
  `pipeline/stickman/actions.py`'s `HOLD_ACTIONS`, then either let the
  pipeline generate it on demand the next time a script calls for it, or run
  `python3 scripts/generate_character.py --outfit <name> --only <pose>` to
  pre-generate it for one outfit by hand. `script_writer.py` reads
  `ACTION_NAMES` automatically, so it becomes usable in scripts immediately.
