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
from pipeline import ideas, script_writer, voiceover, visuals, captions, assemble, upload


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
    log(f"Script has {len(scenes)} scenes")

    voiceover.synthesize_scenes(scenes, run_dir)
    narration_path = voiceover.concat_audio(scenes, run_dir)

    visuals.generate_scene_images(scenes, run_dir)
    thumb_prompt = scenes[0]["visual_prompt"] if scenes else script["title"]
    thumbnail_path = visuals.generate_thumbnail(script["title"], thumb_prompt, run_dir)

    captions_path = captions.generate_captions(narration_path, scenes, run_dir)

    final_video = assemble.assemble_video(scenes, narration_path, captions_path, run_dir)
    log(f"Final video: {final_video}")

    tags = load_channel_config()["youtube"]["default_tags"]

    video_id = upload.upload_video(
        final_video, thumbnail_path, script["title"], script["description"], tags
    )

    append_history({
        "run_id": run_id,
        "topic_title": topic["title"],
        "published_title": script["title"],
        "video_id": video_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    })

    log(f"=== Done. video_id={video_id} ===")


if __name__ == "__main__":
    sys.exit(main())
