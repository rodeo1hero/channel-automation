"""Companion-Short orchestrator: runs the same voiceover -> visuals -> captions ->
assemble -> upload pipeline stages script_writer.py's own output goes through, just
fed a shorts_writer.py hook script instead and rendered vertical (9:16). Runs AFTER
the main video is fully uploaded, since the Short's description links to the main
video's now-known URL -- that's the entire point of a companion Short (see
ARCHITECTURE.md's "Companion Shorts" section).

Kept as its own thin module (rather than folded into run_pipeline.py directly) so it
can also be run standalone for an already-published video -- see
scripts/run_rome_cast_trial.py-style manual invocation, or a future
`scripts/backfill_short.py` for old videos that predate this feature."""
from pathlib import Path

from . import upload, visuals, voiceover
from .assemble import assemble_video
from .shorts_writer import write_hook_script
from .utils import DRY_RUN, load_channel_config, log


def produce_short(main_script: dict, outfit: str, main_video_id: str, run_dir: Path,
                   run_id: str = "unknown", client=None) -> dict:
    """Returns {"video_id", "title", "scenes"} for the produced Short. main_script is
    script_writer.write_script()'s own return value for the video this Short promotes;
    outfit is that same video's outfit (reused as-is, not re-picked -- see
    shorts_writer.py's docstring for why)."""
    short_dir = run_dir / "short"
    short_dir.mkdir(parents=True, exist_ok=True)

    short_script = write_hook_script(main_script, client=client)
    scenes = short_script["scenes"]
    log(f"Short has {len(scenes)} scenes")

    voiceover.synthesize_scenes(scenes, short_dir, run_id=run_id)
    narration_path = voiceover.concat_audio(scenes, short_dir)

    visuals.generate_scene_clips(scenes, short_dir, outfit=outfit, run_id=run_id, aspect_ratio="9:16")

    # No captions on the Short -- per the user's request, and it sidesteps the
    # narrow-vertical-frame caption overlap issue entirely rather than trying to
    # fix the sizing (see assemble_video's docstring).
    final_short = assemble_video(scenes, narration_path, None, short_dir)
    log(f"Final Short: {final_short}")

    main_video_url = f"https://youtu.be/{main_video_id}"
    description = (
        f"{short_script.get('teaser', '')}\n\n"
        f"Watch the full video: {main_video_url}\n\n#Shorts"
    ).strip()

    config = load_channel_config()
    tags = list(config["youtube"]["default_tags"]) + ["Shorts"]

    # No custom thumbnail -- the Shorts feed doesn't display one (see upload.py).
    short_video_id = upload.upload_video(
        final_short, None, short_script["title"], description, tags,
    )

    if not DRY_RUN:
        short_url = f"https://youtu.be/{short_video_id}"
        log(f"Short uploaded: {short_url} (promotes {main_video_url})")

    return {"video_id": short_video_id, "title": short_script["title"], "scenes": scenes}
