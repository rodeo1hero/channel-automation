"""Stage 6: assemble scene images (with pan/zoom) + full narration audio +
burned-in captions into the final .mp4, using ffmpeg."""
import subprocess
from pathlib import Path

from .utils import log

FPS = 30
WIDTH, HEIGHT = 1920, 1080


def _ken_burns_clip(image_path: Path, duration: float, out_path: Path, zoom_in: bool) -> None:
    """Renders one scene image into a short video clip with a slow pan/zoom
    (Ken Burns effect), zooming into the center of the frame."""
    n_frames = max(1, int(duration * FPS))
    # -t must match n_frames/FPS exactly. If it's even slightly longer, ffmpeg's
    # "-loop 1" feeds the image as a second input frame partway through, which
    # resets zoompan's internal zoom accumulator back to 1 -- the "zooms, snaps
    # back to full image, zooms again" glitch.
    clip_duration = n_frames / FPS

    max_zoom = 1.15
    zoom_rate = (max_zoom - 1.0) / n_frames
    if zoom_in:
        zoom_expr = f"min(zoom+{zoom_rate:.6f},{max_zoom})"
    else:
        # Start at max_zoom on the very first output frame ("on" is zoompan's
        # output-frame-number variable), then count down each frame after.
        # (Deliberately not using the `reverse` filter for this -- it has to
        # buffer every decoded frame in memory first, which is heavy enough to
        # get OOM-killed on a modest runner for even a few seconds of 1080p.)
        zoom_expr = f"if(eq(on,1),{max_zoom},max(zoom-{zoom_rate:.6f},1.0))"
    # Keep the crop centered on the image -- without explicit x/y expressions,
    # zoompan defaults to cropping from the top-left corner as it zooms in.
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"scale=8000:-2,"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={n_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
            "-vf", vf, "-t", str(clip_duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
        ],
        check=True, capture_output=True,
    )


def assemble_video(scenes: list, narration_path: Path, captions_path: Path, run_dir: Path) -> Path:
    clips_dir = run_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, scene in enumerate(scenes):
        clip_path = clips_dir / f"clip_{i:03d}.mp4"
        log(f"Rendering pan/zoom clip for scene {i}")
        _ken_burns_clip(
            Path(scene["image_path"]), scene["duration"], clip_path, zoom_in=(i % 2 == 0)
        )
        clip_paths.append(clip_path)

    # Concatenate silent video clips
    concat_list = clips_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")
    silent_video = run_dir / "silent_video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(silent_video),
        ],
        check=True, capture_output=True,
    )

    # Mux narration audio + burn in captions
    final_path = run_dir / "final_video.mp4"
    log("Muxing audio and burning in captions")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(narration_path),
            "-vf", f"subtitles={captions_path}:force_style='Fontsize=22,PrimaryColour=&HFFFFFF&'",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(final_path),
        ],
        check=True, capture_output=True,
    )
    return final_path