"""Renders one script scene (narration-free) into a short .mp4 clip: a flat
background + optional prop icons + an animated stick figure acting out the
scene's action list. This replaces the old Replicate-image + Ken-Burns
approach with fully local, free, deterministic rendering."""
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .actions import generate_frames
from .backgrounds import draw_background, draw_prop, PROP_NAMES, PALETTES
from .rig import draw_figure, THIGH, SHIN, full_pose
from .poses import POSES

WIDTH, HEIGHT = 1920, 1080
FPS = 24
ON_TWOS = True  # redraw a new pose every other frame (classic limited-animation
                # technique) and duplicate the previous frame for the skipped
                # one -- halves render time and reads as a natural, slightly
                # stylized hand-drawn cadence rather than a performance hack.
SUPERSAMPLE = 2
FIGURE_SCALE = 3.3
GROUND_FRAC = 0.95  # fraction down the frame where feet stand
MARGIN = 300

PROP_ANCHORS = {
    "top_left": (WIDTH * 0.13, HEIGHT * 0.15),
    "top_right": (WIDTH * 0.87, HEIGHT * 0.15),
}
PROP_SIZE = 190


def clean_background(scene: dict) -> str:
    return scene.get("background") if scene.get("background") in PALETTES else "plain"


def clean_props(scene: dict) -> list:
    return [p for p in scene.get("props", []) if p in PROP_NAMES][:2]


def draw_frame(pose: dict, root_x: float, flip: bool, bg_kind: str, props: list,
               width: int = WIDTH, height: int = HEIGHT, supersample: int = SUPERSAMPLE,
               figure_scale_mult: float = 1.0) -> Image.Image:
    """Draws one full frame (background + props + figure) and returns a PIL
    Image at `width`x`height`. Shared by the per-scene clip renderer and the
    thumbnail renderer so they always look like the same show.

    `root_x` must already be in output pixel space (0..width), same as the
    returned image -- callers targeting a non-1920x1080 output (e.g. the
    1280x720 thumbnail) don't need to do any conversion themselves.
    """
    sf = height / HEIGHT  # scale factor from the 1920x1080 reference design
    fig_scale = FIGURE_SCALE * figure_scale_mult
    ground_y = height * GROUND_FRAC
    hip_y = ground_y - (THIGH + SHIN) * fig_scale * sf
    W, H = width * supersample, height * supersample
    img = Image.new("RGB", (W, H), (245, 245, 240))
    d = ImageDraw.Draw(img)
    draw_background(d, W, H, kind=bg_kind, ground_y=ground_y * supersample)
    for anchor_name, prop_name in zip(("top_left", "top_right"), props):
        ax, ay = PROP_ANCHORS[anchor_name]
        draw_prop(d, prop_name, (ax * sf * supersample, ay * sf * supersample), PROP_SIZE * sf * supersample)
    draw_figure(d, pose, (root_x * supersample, hip_y * supersample),
                scale=fig_scale * sf * supersample, width=max(2, int(9 * sf * supersample)), flip=flip)
    if supersample != 1:
        img = img.resize((width, height), Image.LANCZOS)
    return img


def _default_actions_for_duration(duration: float) -> list:
    return [("idle", duration)]


def _split_duration(actions: list, duration: float) -> list:
    """Evenly splits `duration` across the given action names."""
    if not actions:
        return _default_actions_for_duration(duration)
    n = len(actions)
    share = duration / n
    return [(a, share) for a in actions]


def _run_ffmpeg(args: list, log=print) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        log("ffmpeg failed:")
        log(result.stderr[-4000:])
        raise RuntimeError(f"ffmpeg exited with code {result.returncode}")


def render_scene_clip(scene: dict, duration: float, out_path: Path,
                       frames_dir: Path = None, log=print) -> Path:
    """scene may contain:
      "actions": list of action-name strings (see actions.ACTION_NAMES)
      "background": one of backgrounds.PALETTES keys
      "props": list of up to 2 names from backgrounds.PROP_NAMES
    All are optional; missing/invalid values fall back to sane defaults so a
    malformed script never crashes the render.
    """
    actions = [a for a in scene.get("actions", []) if isinstance(a, str)]
    action_list = _split_duration(actions, duration)
    bg_kind = clean_background(scene)
    props = clean_props(scene)
    start_x = WIDTH / 2

    own_tmp = frames_dir is None
    frames_dir = frames_dir or out_path.parent / f"_frames_{out_path.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    idx = 0
    prev_frame_path = None
    for pose, root_x, flip in generate_frames(action_list, FPS, WIDTH, start_x, margin=MARGIN):
        frame_path = frames_dir / f"frame_{idx:05d}.png"
        if ON_TWOS and idx % 2 == 1 and prev_frame_path is not None:
            shutil.copyfile(prev_frame_path, frame_path)
        else:
            img = draw_frame(pose, root_x, flip, bg_kind, props)
            img.save(frame_path)
        prev_frame_path = frame_path
        idx += 1

    n_frames = idx
    if n_frames == 0:
        raise RuntimeError(f"stickman scene renderer produced 0 frames for scene: {scene}")

    _run_ffmpeg([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-frames:v", str(n_frames),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
    ], log=log)

    if own_tmp:
        shutil.rmtree(frames_dir, ignore_errors=True)

    return out_path


def render_still(scene: dict, pose_name: str = "surprised", width: int = 1280,
                  height: int = 720, figure_scale_mult: float = 0.8) -> Image.Image:
    """Renders a single still frame (for thumbnails), reusing the same
    background/prop/figure look as the video clips. Defaults to an arms-up
    pose scaled down a bit so raised arms/head have headroom to stay on-canvas."""
    pose = full_pose(POSES.get(pose_name, {}))
    bg_kind = clean_background(scene)
    props = clean_props(scene)
    root_x = width / 2
    return draw_frame(pose, root_x, False, bg_kind, props, width=width, height=height,
                       figure_scale_mult=figure_scale_mult)
