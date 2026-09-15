#!/usr/bin/env python3
"""Real, hand-authored validation of the new vertical Shorts rendering path (see
pipeline/shorts.py) -- same staged-runner pattern as run_rome_cast_trial.py. Written by
hand (like the cast pilot before it) rather than via shorts_writer.py's live Claude
call, since no ANTHROPIC_API_KEY is configured in this sandbox; this only proves the
vertical rendering machinery (real 9:16 FLUX backgrounds, real TTS, real compositing,
real 1.2x-sped assembly) actually works end to end, not the hook-writing prompt itself.

Promotes the "How Rome Became Rich" trial video (scripts/rome_script.py) -- reuses its
real https://youtu.be/... placeholder-free description style but points at a fake
video_id since that trial was never actually uploaded to YouTube."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.utils import ROOT, log
from pipeline import voiceover, visuals, assemble
from scripts.rome_script import SCRIPT as MAIN_SCRIPT

STAGE = sys.argv[1] if len(sys.argv) > 1 else None
run_dir = ROOT / "assets" / "runs" / "rome_short_trial"
run_dir.mkdir(parents=True, exist_ok=True)
state_path = run_dir / "state.json"

SHORT_SCRIPT = {
    "title": "Rome was the richest empire on Earth. Here's how it lost it all.",
    "teaser": "The empire that had everything -- and quietly gave it all away.",
    "scenes": [
        {
            "narration": (
                "Rome was once the richest empire the world had ever seen. Gold, "
                "taxes, trade -- all of it flowing straight into the treasury."
            ),
            "actions": ["celebrate"],
            "background_prompt": (
                "a tall narrow view straight up into a golden Roman treasury vault, "
                "coins and gold objects stacked high on shelves, dramatic upward "
                "vertical composition"
            ),
        },
        {
            "narration": (
                "So how did that same empire end up debasing its own currency into "
                "basically a worthless coin?"
            ),
            "actions": ["surprised", "point_right"],
            "background_prompt": (
                "an extreme close-up of a single cracked, worn ancient Roman coin "
                "filling most of the vertical frame, dramatic side lighting"
            ),
        },
        {
            "narration": (
                "The collapse took centuries -- and almost nobody in charge saw it "
                "coming until it was way too late."
            ),
            "actions": ["think"],
            "background_prompt": (
                "a single tall crumbling Roman column standing alone against a "
                "dramatic overcast sky, vertical composition, weathered stone"
            ),
        },
    ],
}


def load_scenes():
    if state_path.exists():
        return json.loads(state_path.read_text())
    return SHORT_SCRIPT["scenes"]


def save_scenes(scenes):
    state_path.write_text(json.dumps(scenes, indent=2))


outfit = MAIN_SCRIPT.get("outfit", "standard")

if STAGE == "voiceover":
    scenes = load_scenes()
    voiceover.synthesize_scenes(scenes, run_dir)
    total = sum(s["duration"] for s in scenes)
    log(f"Total narration duration: {total:.1f}s across {len(scenes)} scenes")
    narration_path = voiceover.concat_audio(scenes, run_dir)
    log(f"Narration: {narration_path}")
    save_scenes(scenes)

elif STAGE == "visuals":
    scenes = load_scenes()
    visuals.generate_scene_clips(scenes, run_dir, outfit=outfit, aspect_ratio="9:16")
    save_scenes(scenes)

elif STAGE == "finish":
    scenes = load_scenes()
    narration_path = run_dir / "audio" / "full_narration.wav"
    # No captions on Shorts -- see pipeline/shorts.py / assemble.py's docstring.
    final_video = assemble.assemble_video(scenes, narration_path, None, run_dir)
    log(f"=== Final Short: {final_video} ===")

else:
    print("Usage: rome_short_trial.py [voiceover|visuals|finish]")
    sys.exit(1)
