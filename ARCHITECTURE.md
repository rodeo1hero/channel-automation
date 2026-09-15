# Automated Channel Pipeline — Architecture & Stack

Goal: a solo-run pipeline that takes the channel's format (short pop-science/psychology
video essays — "take an everyday thing and reveal the hidden mechanism behind it") from
topic idea all the way to a published YouTube video, with no manual steps once configured.

## Pipeline stages

1. **Idea queue** — a simple `config/topics_queue.yaml` list of upcoming topics (you can
   seed it, e.g. "What it actually meant to be a knight"). When the queue runs low, Claude
   proposes new topics in the channel's niche, checking `state/history.json` so it never
   repeats a topic.
2. **Script writing** — Claude (Anthropic API) turns a topic into: a title, an outfit for
   the recurring character to wear for this whole video (see "The character" below), a
   scene-by-scene narration script (scenes are deliberately kept short -- 6-10 seconds of
   narration each, favoring more, shorter scenes over fewer long ones, so the video cuts to
   a new background/beat more often and reads as more energetically paced), and, per scene,
   stick-figure staging directions (which actions/expressions the character performs) plus
   a text description of that scene's background/setting for the AI-generated backdrop.
3. **Voiceover (TTS)** — the script is synthesized to speech, one audio clip per scene, so
   each scene's exact spoken duration is known (needed to time the visuals).
4. **Visuals** — a recurring stick-figure character (same face and build every video, in
   whichever outfit the script picked — see "The character: one identity, cached per
   outfit" below) acts out each scene's actions (walk/run cycles, pointing, waving,
   thinking, sitting at a desk, using a laptop, etc. — each with a matching facial
   expression baked into the pose) composited over an AI-generated background image for
   that scene, with a subtle Ken Burns pan/zoom on the background.
   `pipeline/scene_backgrounds.py` generates the backgrounds (Replicate/FLUX);
   `pipeline/stickman/ai_scene_renderer.py` does the compositing and encodes each scene to
   a clip.
5. **Captions** — Whisper transcribes the finished voiceover to generate accurately-timed
   burned-in or soft captions.
6. **Assembly** — ffmpeg stitches audio + panned images + captions (+ optional royalty-free
   background music) into the final .mp4, then speeds the whole finished video (video,
   narration audio, and already-burned-in captions together) up by a fixed 1.2x
   (`assemble.py`'s `SPEED_FACTOR`) for a punchier pace -- the audio uses ffmpeg's `atempo`
   filter, which speeds speech up without pitch-shifting it (no "chipmunk" effect), and the
   video's `setpts` remap runs after the `subtitles` burn-in so captions stay in sync
   automatically rather than needing separate rescaling.
7. **Thumbnail + metadata** — one higher-quality image plus a title/description/tags pass
   from Claude, written for YouTube SEO in the channel's niche.
8. **Upload** — the YouTube Data API v3 uploads the video, sets the thumbnail, and publishes
   (or schedules) it on your existing channel.
9. **Companion Short** — see "Companion Shorts: a vertical hook for every video" below.
   Runs after the main video's own upload, since the Short's description links to that
   video's now-known URL; a failed Short is logged and skipped rather than failing the run.
10. **History log** — every run appends to `state/history.json` (topic, title, publish date,
    video id, and now short_video_id) so future idea-generation and metadata avoid repeats.

## Recommended stack (optimized for a solo creator's budget)

| Stage | Tool | Why | Approx. cost |
|---|---|---|---|
| Script + ideas + metadata | Claude (Anthropic API) | Already your voice/format | ~$0.05–0.15/video |
| Voiceover | Google Cloud TTS — Chirp 3: HD voices | Most natural-sounding tier; at this channel's volume (a few videos/month) it's fully covered by the 1M-character/month free allowance, so real cost is $0 | $0 (within free tier); $30/1M chars beyond it |
| Visuals: character | AI-rendered sprite sheet (`openai/gpt-image-2.5-flare` on Replicate, `low` quality tier), cached per outfit | Real movement + expression, perfectly consistent per outfit since poses are reused pixel-for-pixel once generated; only new outfit/pose combinations cost anything | ~$0.02–0.03/pose the first time it's needed, $0 every time after (cached) |
| Visuals: backgrounds | FLUX 1.1 Pro (via Replicate) | Style-matched hand-drawn backdrop per scene, cheap | ~$0.03–0.04/image, ~$0.30–0.60/video |
| Captions | Whisper (open source, runs free) | Accurate forced alignment, no API cost | $0 |
| Assembly | ffmpeg (scripted, no GUI editor) | Free, fully scriptable | $0 |
| Upload | YouTube Data API v3 | Official, required for automated publishing | Free (well within the 10,000 unit/day quota — an upload costs 1,600 units, so 6/day is possible) |

**Total: roughly $0.35–$0.90 in API costs per video**, depending on how many of that
video's outfit/pose combinations are new versus already cached (Claude script/ideas +
per-scene backgrounds + whatever character sprites haven't been generated before). Once a
channel has run for a while and its handful of outfits have most common poses cached, this
settles close to the background-only cost (~$0.35–$0.60).

### The character: one identity, cached per outfit

The channel's recurring stick-figure character is NOT drawn by code, and poses aren't
regenerated from scratch every video — they're generated on demand, the first time a given
(outfit, pose) combination is needed, and cached forever after. `pipeline/character_gen.py`
holds the shared logic: it asks an AI image model (`openai/gpt-image-2.5-flare` on Replicate,
which does instruction-following image editing, at the `low` quality tier — plenty for flat
graphic line art, and roughly a fifth to a sixth the cost of the `high` tier meant for
photorealistic detail) to draw a reference image for a given outfit, then — reusing that same
reference (re-derived from the locally saved file each time, not a Replicate URL, so it never
depends on that URL staying alive) as input for every call, so the face/head/body stays
identical — generates whichever poses in `pipeline/stickman/pose_descriptions.py` (walk, run,
point, wave, think, sit at a desk, use a laptop, ...) that video's script actually calls for,
each with a matching facial expression baked into the pose itself, with a transparent
background. Results are saved to `assets/character/<outfit>/<pose_name>.png` and committed to
the repo (including by the GitHub Actions workflow itself, so the cache persists across
scheduled runs, not just a local machine).

**Outfits, not a single fixed look.** `pipeline/character_gen.py`'s `OUTFITS` dict (standard,
historical, business, casual, modern, financial) describes a handful of outfit variants; the
face/head/body silhouette is identical across all of them, only the outfit description changes.
`script_writer.py` has Claude pick one outfit per video, matching that video's topic/era, and
the whole video uses it throughout. `pipeline/visuals.py` figures out exactly which poses that
video's scenes need (`pipeline/stickman/actions.py`'s `sprite_names_needed_for`) and calls
`ensure_outfit_sprites()`, which only generates whatever's missing for that outfit — so a
second video reusing "business", say, generates nothing at all for any pose it shares with the
first one. `pipeline/stickman/character_sprites.py` then pastes the right cached sprite for the
current action/frame. To pre-warm an outfit's cache by hand, or fix one pose that came out
wrong, run `python3 scripts/generate_character.py --outfit <name> [--only <pose_name> ...]`.

**Core poses vs. the long tail (hybrid generation).** Not every pose is generated the same
way. `pipeline/stickman/pose_descriptions.py`'s `CORE_POSES` (stand, walk/run, point, wave,
think, sit, explain, ...) get heavy screen time, so they're each generated with their own
single API call at full resolution. Everything else — the money/business set (holding cash,
a stock chart, a calculator, a handshake with a second figure, going broke, ...) and other
occasional reaction poses — is batched into "grid sheet" calls instead
(`generate_pose_grid()`): several poses rendered as one image, then sliced into individual
transparent sprites locally. This is roughly 4-8x cheaper per pose, since one API call
produces several poses at once, at the cost of somewhat lower per-pose sharpness after
upscaling (a fine tradeoff for poses that show up occasionally, not for ones on screen most
of every video). Slicing the sheet doesn't trust the grid dimensions requested in the prompt
— the model doesn't always draw exactly the rows×cols asked for — instead it detects the
actual pose boundaries by looking for bands of whitespace between figures (row bands first,
then column bands within each row, falling back to an even split using the *actual* detected
row count if content-detection doesn't cleanly find the right number of poses). Background
removal for a sliced cell flood-fills inward from the cell's border rather than color-keying
every whitish pixel, so an enclosed white/cream garment (the toga) doesn't get erased along
with the real background.

**Identity consistency.** Every generation call — reference, single pose, and grid sheet
alike — ends with the same hard-lock sentence telling the model not to redesign the
character. `BASE_STYLE` additionally pins down that the head is bald and glasses-free unless
an outfit specifically calls for headwear/eyewear, and that an outfit is always a small
accent layered on the black silhouette (trim, a collar line, a held prop) rather than a
separately illustrated garment — without this, business-style outfits previously caused the
model to grow unrequested hair and glasses and draw a full illustrated suit that replaced the
black silhouette outright, breaking the character's identity. This matters more than it might
for a channel meant to run unattended: a new outfit generated by a scheduled CI run has no
human reviewing the result before it's cached and reused in every future video with that
outfit.

### Supporting cast: reusable secondary characters, not one-offs

The narrator isn't the only character a scene can use. `pipeline/cast_gen.py` generates
and caches sprites for a small set of reusable secondary ROLES (`CAST_ROLES`: authority,
guard, wealthy, poor, merchant, official) that a scene can bring in to interact with the
narrator instead of having the narrator explain everything to camera alone -- a tax
collector demanding payment, a guard blocking the way, a wealthy citizen refusing to
share. These are archetypes, not fixed individuals: each role is dressed per-video in
whatever outfit/era the narrator's own outfit calls for (`ERA_CLOTHING`, deliberately
generic period clothing rather than the narrator's own `OUTFITS` text, which carries the
narrator's own signature accessories like the historical outfit's laurel wreath), so
"official" becomes a Roman tax collector in a historical video and a modern bureaucrat in
a business video with no extra authoring. Each role's own prop/accessory (a crown, a
spear, a coin pouch, a scroll, ...) is what makes it silhouette-readable at a glance, both
from the narrator and from every other role.

Generation reuses the exact same low-level Replicate call/retry/grid-slicing/background-
removal logic as the narrator (factored out into `pipeline/replicate_gen_utils.py` so the
two never duplicate it and drift out of sync -- that already happened once with an
outfit-path constant, see the cache-pollution note below). Unlike the narrator, cast poses
aren't split into a "core" (one-per-call) and "long tail" (grid-batched) tier -- a cast
member never gets narrator-level screen time, so all of `pipeline/stickman/
cast_descriptions.py`'s `CAST_POSE_NAMES` (stand, walk_a/b, gesture_talk, point, offer,
refuse, shocked) are generated together in ONE grid-sheet call. A whole (role, outfit)
combination therefore costs one reference call plus one grid call -- about the same as
two of the narrator's own calls, however many of the 8 poses actually get used later.
Sprites cache to `assets/cast/<role>/<outfit>/<pose>.png`, same forever-reused-after-
the-first-time model as the narrator's own cache.

**Dialogue is text, not audio.** A cast member's line renders as an on-screen speech
bubble (`ai_scene_renderer.py`'s `_draw_speech_bubble`) drawn locally with Pillow, never
a second TTS voice -- so a scene with back-and-forth dialogue costs nothing beyond the
sprite generation itself, and needs no audio-sync work. `script_writer.py`'s prompt gives
Claude the full role/pose vocabulary and has it emit an optional `"cast"` list (up to 2
members) per scene, each with a role, pose, which side of the frame they stand on, a
short dialogue line, and an optional start/end time within the scene so two lines can be
staged one after another. `pipeline/visuals.py`'s `_ensure_cast_for_scenes` generates
whatever (role, outfit) combinations a script's scenes actually need, the same
only-pay-for-what's-missing pattern as the narrator.

**Staging is a v1 simplification, not full blocking.** Cast members are held (not
walking-cycle-animated by default) at one of two fixed x-positions (`SIDE_X_FRAC`,
22%/78% of frame width); when a scene has cast members, the narrator is shifted to the
opposite side rather than left centered, so a walk_left/right narrator action doesn't
carry it through a cast member's fixed spot -- `script_writer.py`'s prompt tells Claude to
avoid walking actions in cast scenes for this reason. This covers every interaction in the
brief that motivated the system (two figures having a brief, staged exchange) without the
complexity of full multi-character blocking/collision.

### Companion Shorts: a vertical hook for every video

Every run also produces a YouTube Short promoting the main video, uploaded right after
it (`pipeline/shorts.py`'s `produce_short`, called from `run_pipeline.py` once the main
video's own `video_id` is known). The design choice the user made explicitly: a Short is
a **purpose-written hook**, not a cut-down clip of the main video's own narration --
`pipeline/shorts_writer.py` gives Claude the main video's title/description/opening line
as context and asks for a separate ~20-30s narration (2-3 scenes) that opens on the most
surprising/counterintuitive claim from the full video, briefly builds on it, and ends on
an explicit, UNRESOLVED cliffhanger -- the prompt is direct that the hook must not answer
its own question, since that's what should pull someone into the full video. The Short's
description links to the main video (`https://youtu.be/<video_id>`) plus `#Shorts`; a
literal "link in bio"-style line is deliberately kept OUT of the spoken narration itself.

The Short reuses the main video's exact `outfit` (and thus its narrator/cast look)
rather than letting Claude re-pick one -- it's a companion piece for the same character,
not a new video with its own identity. Because character/cast sprites are just
transparent cutouts, no new sprite generation is needed purely for the orientation
change; only the Short's own new poses (if its hook narration calls for an action the
main video's scenes didn't use) and its own 9:16 backgrounds cost anything.

**Rendering both orientations from one code path, not two.** Rather than a separate
vertical renderer, `pipeline/stickman/ai_scene_renderer.py`'s `render_scene_clip` (and
its `_load_background`/`_ken_burns_crop`/`_narrator_start_x` helpers) now take `width`/
`height` parameters instead of reading module-level constants directly -- landscape
(1920x1080, `WIDTH`/`HEIGHT`) is the default, vertical (1080x1920, `SHORT_WIDTH`/
`SHORT_HEIGHT`) is passed explicitly for a Short. `pipeline/visuals.py`'s
`generate_scene_clips` takes an `aspect_ratio` ("16:9" or "9:16") and looks up the right
frame size via `FRAME_SIZE_FOR_ASPECT`, threading the SAME string straight through to
`scene_backgrounds.py`'s own `aspect_ratio` argument (Replicate/FLUX's own input, so a
Short's backgrounds are actually composed for a tall frame, not a 16:9 image cropped down
after the fact). This one-shared-path approach is deliberate, after this session already
hit the "two copies of the same logic quietly drift apart" bug once (see the dry-run
cache-pollution note above) -- a second vertical-only renderer would have been exactly
that risk again.

**Shorts render with no captions at all.** The first real trial surfaced a cosmetic
rough edge -- burned-in captions used the same fixed font size as the landscape video, so
on the narrow 1080px-wide vertical frame a long caption line wrapped to 4-5 lines and
visually overlapped the character rather than sitting cleanly below it. Rather than tune
caption sizing specifically for the vertical case, the user asked to drop subtitles from
Shorts entirely -- `assemble_video`'s `captions_path` parameter now accepts `None` to
skip the `subtitles` burn-in filter altogether (video still gets the `setpts` speed-up,
audio still gets `atempo`, just no caption track), and `shorts.py` no longer calls
`captions.generate_captions` at all for a Short, since nothing downstream needs the .srt
file any more.

A companion Short costs roughly the same as 2-3 extra scenes' worth of backgrounds on top
of the main video (about $0.10-0.15), validated for real end to end (`scripts/
rome_short_trial.py`: real TTS, real 9:16 FLUX backgrounds, real compositing, real
1.2x-sped assembly, no captions -- 3 hand-written scenes, 19.1s narration -> 15.9s final
Short, 1080x1920 confirmed). The hook-WRITING prompt itself (`shorts_writer.py`'s Claude call)
is NOT yet validated against a live Anthropic API key, since none is configured in this
sandbox -- only its DRY_RUN mock has been exercised. `pipeline/upload.py`'s
`upload_video` now accepts `thumbnail_path=None`, since a Short skips a custom thumbnail
entirely (the Shorts feed doesn't display one). A Short's own generation isn't yet broken
out under its own cost-tracker tag the way cast spend is (`replicate_cast`) -- it's
currently lumped into the same run's `replicate_background`/`google_tts` totals as the
main video, a reasonable but so-far-unaddressed follow-up.

An earlier iteration of the visuals stage drew the character itself with vector line art
(no AI involved at all -- see `pipeline/stickman/rig.py`, `poses.py`'s angle-based pose dicts,
and `scene_renderer.py`) with flat-color backgrounds. That code is still in the repo and still
works (truly free, zero API calls) but isn't wired up by default any more, since the AI-rendered
sprite sheet composited over AI backgrounds looks substantially better.

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
3. Get API keys for: Anthropic (Claude), Google Cloud TTS, and Replicate (for the per-scene
   background art and any not-yet-cached character sprites).
4. Push the repo to GitHub and add the above as repository secrets.

After that, the schedule runs unattended: it pulls the next topic, produces a full video,
and publishes it.
