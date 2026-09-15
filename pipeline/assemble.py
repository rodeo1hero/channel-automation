"""Stage 6: concatenate the per-scene stick-figure clips (already rendered
by visuals.generate_scene_clips, each at its scene's exact spoken duration)
into one silent video, then mux in the full narration + burned-in captions."""
import subprocess
from pathlib import Path

from .utils import log

# Final video is sped up uniformly (video + audio + already-burned-in captions all
# together, in the same ffmpeg pass that muxes/burns them) by this factor, per the
# user's request for a punchier pace -- 1.2x is the same "slightly faster" feel as
# watching at 1.2x playback speed on YouTube, applied once at render time instead of
# left to the viewer. ffmpeg's `atempo` audio filter accepts 0.5-2.0 directly, so a
# single atempo=SPEED_FACTOR needs no chaining. Captions are burned in via the
# `subtitles` filter earlier in the SAME -vf chain (at the original, un-sped narration
# timing from Whisper), then `setpts` remaps every frame's timestamp by this factor --
# since it runs after the subtitles filter, the burned-in caption timing is carried
# along with the speedup rather than needing separate rescaling.
SPEED_FACTOR = 1.2


def _run_ffmpeg(args: list) -> None:
    """subprocess.run wrapper that prints ffmpeg's actual stderr on failure
    instead of just an opaque exit code -- ffmpeg's error output is the whole
    point of capturing it."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        log("ffmpeg failed:")
        log(result.stderr[-4000:])  # tail -- full output can be huge
        raise RuntimeError(f"ffmpeg exited with code {result.returncode}")


def _filtergraph_path(path: Path) -> str:
    """Escape a filesystem path for use as a value inside an ffmpeg filtergraph
    argument (e.g. subtitles=...:option). On Windows, a raw 'C:\\...' path
    breaks the filtergraph parser: backslashes are its own escape character,
    and the drive-letter colon gets misread as a filter-option separator."""
    return str(path).replace("\\", "/").replace(":", "\\:")


def assemble_video(scenes: list, narration_path: Path, captions_path, run_dir: Path) -> Path:
    """captions_path may be None to skip caption burn-in entirely (used for Shorts --
    see shorts.py: the narrow 1080px-wide vertical frame made the fixed-size burned-in
    captions wrap to 4-5 lines and overlap the character, and the user asked for no
    subtitles on the Shorts at all, so shorts.py now skips generating them and passes
    None here rather than trying to shrink/reflow them to fit)."""
    clip_paths = [Path(scene["clip_path"]) for scene in scenes]
    if not clip_paths:
        raise RuntimeError("assemble_video: no scene clips to concatenate")

    # Concatenate silent scene clips (each already rendered at its scene's
    # exact spoken duration, so no re-timing is needed here).
    concat_list = run_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")
    silent_video = run_dir / "silent_video.mp4"
    log(f"Concatenating {len(clip_paths)} scene clips")
    _run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(silent_video),
    ])

    # Mux narration audio + (optionally) burn in captions + speed the whole thing up
    final_path = run_dir / "final_video.mp4"
    if captions_path:
        log(f"Muxing audio, burning in captions, and speeding up {SPEED_FACTOR}x")
        subtitles_arg = f"subtitles={_filtergraph_path(captions_path)}:force_style='Fontsize=22,PrimaryColour=&HFFFFFF&'"
        video_filter = f"{subtitles_arg},setpts=PTS/{SPEED_FACTOR}"
    else:
        log(f"Muxing audio (no captions) and speeding up {SPEED_FACTOR}x")
        video_filter = f"setpts=PTS/{SPEED_FACTOR}"
    audio_filter = f"atempo={SPEED_FACTOR}"
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(narration_path),
        "-vf", video_filter, "-af", audio_filter,
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(final_path),
    ])
    return final_path
