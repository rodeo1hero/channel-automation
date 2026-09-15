#!/usr/bin/env python3
"""Main orchestrator: idea -> script -> voiceover -> visuals -> captions ->
assembly -> thumbnail -> upload -> history log.

Run with --dry-run to execute the whole pipeline with mock data and no API
calls or API keys required (useful for testing the plumbing).
"""
import argparse
import datetime as dt
import os
import sys

# Parse args and set the dry-run env var BEFORE importing any pipeline module,
# since pipeline.utils.DRY_RUN is a module-level constant read at import time.
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="run with mock data, no API calls")
args = parser.parse_args()
if args.dry_run:
    os.environ["PIPELINE_DRY_RUN"] = "1"

from pipeline.utils import ROOT, DRY_RUN, append_history, load_channel_config, log, require_env
from pipeline import cost_tracker, ideas, script_writer, shorts, voiceover, visuals, captions, assemble, upload


def main():
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "assets" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log(f"=== Starting pipeline run {run_id} ===")

    anthropic_client = None
    if not DRY_RUN:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))

    topic = ideas.get_next_topic(anthropic_client)
    log(f"Topic: {topic['title']}")

    script = script_writer.write_script(topic, anthropic_client)
    scenes = script["scenes"]
    outfit = script.get("outfit", "standard")
    log(f"Script has {len(scenes)} scenes, outfit={outfit}")

    voiceover.synthesize_scenes(scenes, run_dir, run_id=run_id)
    narration_path = voiceover.concat_audio(scenes, run_dir)

    visuals.generate_scene_clips(scenes, run_dir, outfit=outfit, run_id=run_id)
    hero_scene = scenes[0] if scenes else {}
    thumbnail_path = visuals.generate_thumbnail(script["title"], hero_scene, run_dir, outfit=outfit)

    captions_path = captions.generate_captions(narration_path, scenes, run_dir)

    final_video = assemble.assemble_video(scenes, narration_path, captions_path, run_dir)
    log(f"Final video: {final_video}")

    tags = load_channel_config()["youtube"]["default_tags"]

    video_id = upload.upload_video(
        final_video, thumbnail_path, script["title"], script["description"], tags
    )

    # Companion Short: runs AFTER the main video is uploaded, since its description
    # links to the main video's now-known URL (https://youtu.be/<video_id>) -- the
    # whole point of a companion Short is to hook viewers into the video it promotes.
    # A failure here should never take down an otherwise-successful main-video
    # publish, so it's caught and logged rather than left to crash the run.
    short_video_id = None
    try:
        short_result = shorts.produce_short(script, outfit, video_id, run_dir, run_id=run_id,
                                             client=anthropic_client)
        short_video_id = short_result["video_id"]
    except Exception as e:
        log(f"Warning: companion Short failed, main video was still published fine: {e}")

    append_history({
        "run_id": run_id,
        "topic_title": topic["title"],
        "published_title": script["title"],
        "video_id": video_id,
        "short_video_id": short_video_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    })

    log(f"=== Done. video_id={video_id} short_video_id={short_video_id} ===")
    if not DRY_RUN:
        cost_tracker.print_run_summary(run_id)


if __name__ == "__main__":
    sys.exit(main())
