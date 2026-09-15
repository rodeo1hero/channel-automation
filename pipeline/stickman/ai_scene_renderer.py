"""Renders one script scene into a short .mp4 clip by compositing the
pre-rendered character sprite (see character_sprites.py) walking/gesturing
over an AI-generated background image (pipeline/scene_backgrounds.py), with
a subtle Ken Burns pan/zoom on the background for motion. This is the
current default renderer -- see scene_renderer.py for the earlier fully
free/local vector-line renderer (still available, just not wired up by
default any more).

Also composites any secondary/supporting "cast" characters a scene calls for
(see pipeline/cast_gen.py) -- reusable archetypes like a tax collector or
guard, positioned to one side of the narrator, each optionally showing a
speech-bubble line of dialogue. Cast dialogue is rendered as on-screen text,
never a separate TTS voice, so it adds zero narration/audio cost or sync
work -- see cast_sprites.py / the "cast" key in a scene dict."""
import math
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .actions import generate_sprite_frames
from .cast_sprites import composite_cast_member
from .character_sprites import composite_character

WIDTH, HEIGHT = 1920, 1080
# Vertical frame size for a YouTube Short (see pipeline/shorts.py) -- same 1080-px
# short edge as the landscape frame's height, so character/cast sprites (a fixed
# pixel height fraction of the frame) read at a similar on-screen size in both.
SHORT_WIDTH, SHORT_HEIGHT = 1080, 1920
FPS = 24
ON_TWOS = True
GROUND_FRAC = 0.94
CHARACTER_HEIGHT_FRAC = 0.58  # character height as a fraction of frame height
CAST_HEIGHT_FRAC = CHARACTER_HEIGHT_FRAC * 0.92  # slightly smaller -- reads as "not the lead"
MARGIN = 300
MAX_ZOOM = 1.06  # Ken Burns zoom range on the background -- subtle/slow (was 1.12, felt too
# fast/noticeable per user feedback on the cast-system demo clip)

# Horizontal slots a cast member/the narrator can be staged at, as a fraction of frame
# width. When a scene has cast members, the narrator is shifted off-center to make room
# rather than risk a walk action carrying it through a cast member's fixed position --
# a v1 limitation: with cast present, keep narrator actions to in-place gestures rather
# than walk_left/right (script_writer.py's prompt says so).
SIDE_X_FRAC = {"left": 0.22, "right": 0.78}
CAST_BOB_AMPLITUDE = 3  # px, subtle idle bob so a held cast pose doesn't look frozen
CAST_BOB_PERIOD = 2.3
BUBBLE_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BUBBLE_MAX_WIDTH = 460
BUBBLE_PADDING = 22
BUBBLE_FONT_SIZE = 34


def _group_cast_by_side(cast_entries: list) -> dict:
    """Groups cast entries by which side of the frame they occupy, sorted by start
    time -- a side's entries form that slot's "timeline" (see _active_cast_for_side),
    whether that's one character speaking twice or two different characters taking
    turns in the same spot."""
    by_side = {}
    for c in cast_entries:
        side = c.get("side") or "right"
        by_side.setdefault(side, []).append(c)
    for entries in by_side.values():
        entries.sort(key=lambda c: float(c.get("start", 0.0)))
    return by_side


def _active_cast_for_side(entries: list, t_seconds: float, duration: float) -> tuple:
    """Picks what to draw for one side's slot at time t_seconds: the character sprite
    is visible for the WHOLE scene once it has any entry there (never pops in/out), and
    only the speech bubble is scoped to its own entry's [start, end) window -- before
    the first entry's start it holds that first pose silently, between two entries it
    holds the previous one's pose silently, and after the last entry's end it holds the
    last pose silently. This is what keeps a cast member from visibly vanishing between
    two lines of dialogue, which is exactly what a shared start/end for both the sprite
    and the bubble used to cause. Returns (entry, show_bubble)."""
    current = entries[0]
    show_bubble = False
    for entry in entries:
        start = float(entry.get("start", 0.0))
        end = float(entry.get("end", duration))
        if t_seconds < start:
            break
        current = entry
        show_bubble = start <= t_seconds < end
    return current, show_bubble


def _narrator_start_x(cast_entries: list, width: int = WIDTH) -> float:
    sides = {(c.get("side") or "right") for c in cast_entries}
    if sides == {"left"}:
        return width * SIDE_X_FRAC["right"]
    if sides == {"right"}:
        return width * SIDE_X_FRAC["left"]
    return width / 2  # cast on both sides (or none) -- keep the narrator centered


def _has_bubble_font() -> bool:
    try:
        ImageFont.truetype(BUBBLE_FONT_PATH, 10)
        return True
    except OSError:
        return False


def _draw_speech_bubble(frame: Image.Image, text: str, anchor_x: float, anchor_y: float) -> None:
    """Draws a rounded speech bubble with a small tail, its bottom tip at
    (anchor_x, anchor_y) -- meant to sit just above a cast member's head."""
    if not text:
        return
    draw = ImageDraw.Draw(frame)
    font = ImageFont.truetype(BUBBLE_FONT_PATH, BUBBLE_FONT_SIZE) if _has_bubble_font() else ImageFont.load_default()

    avg_char_w = max(1.0, draw.textlength("MNOPQRabcdefghij", font=font) / 16)
    wrap_chars = max(8, int((BUBBLE_MAX_WIDTH - 2 * BUBBLE_PADDING) / avg_char_w))
    lines = textwrap.wrap(text, width=wrap_chars) or [text]
    line_height = font.size * 1.25
    text_w = max((draw.textlength(line, font=font) for line in lines), default=0)

    box_w = min(BUBBLE_MAX_WIDTH, text_w + 2 * BUBBLE_PADDING)
    box_h = line_height * len(lines) + 2 * BUBBLE_PADDING
    tail_h = 22
    box_left = anchor_x - box_w / 2
    box_bottom = anchor_y - tail_h
    box_top = box_bottom - box_h
    box_right = box_left + box_w

    draw.rounded_rectangle(
        (box_left, box_top, box_right, box_bottom), radius=18,
        fill=(255, 255, 255, 235), outline=(20, 20, 20, 255), width=3,
    )
    draw.polygon(
        [(anchor_x - 14, box_bottom - 1), (anchor_x + 14, box_bottom - 1), (anchor_x, box_bottom + tail_h)],
        fill=(255, 255, 255, 235), outline=(20, 20, 20, 255),
    )
    y = box_top + BUBBLE_PADDING
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text((anchor_x - lw / 2, y), line, font=font, fill=(15, 15, 15, 255))
        y += line_height


def _default_actions_for_duration(duration: float) -> list:
    return [("idle", duration)]


def _split_duration(actions: list, duration: float) -> list:
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


def _load_background(path: str, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    img = Image.open(path).convert("RGB")
    # Upscale a bit beyond the target frame size so the Ken Burns zoom has
    # room to crop without ever needing to upsample past source resolution
    # by much (a mild resize step handles any odd aspect ratio too).
    target_w, target_h = int(width * MAX_ZOOM * 1.02), int(height * MAX_ZOOM * 1.02)
    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = round(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = round(new_w / src_ratio)
    return img.resize((new_w, new_h), Image.LANCZOS)


def _ken_burns_crop(bg: Image.Image, progress: float, zoom_in: bool,
                     width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """progress: 0..1 through the scene. Returns a width x height crop."""
    t = progress if zoom_in else (1.0 - progress)
    zoom = 1.0 + (MAX_ZOOM - 1.0) * t
    crop_w = width * zoom
    crop_h = height * zoom
    # Center crop -- keeps it simple and avoids ever panning off the edges
    # of a background image that wasn't composed with a pan in mind.
    cx, cy = bg.width / 2, bg.height / 2
    box = (cx - crop_w / 2, cy - crop_h / 2, cx + crop_w / 2, cy + crop_h / 2)
    box = (max(0, box[0]), max(0, box[1]), min(bg.width, box[2]), min(bg.height, box[3]))
    crop = bg.crop(box)
    return crop.resize((width, height), Image.LANCZOS)


def render_scene_clip(scene: dict, duration: float, out_path: Path, outfit: str = "standard",
                       zoom_in: bool = True, frames_dir: Path = None, log=print,
                       width: int = WIDTH, height: int = HEIGHT) -> Path:
    """width/height default to the landscape 1920x1080 main-video frame; pass
    SHORT_WIDTH, SHORT_HEIGHT (1080x1920) to render a vertical YouTube Short clip
    instead -- everything below (Ken Burns crop, ground line, character/cast
    positioning) is computed off these rather than the module-level WIDTH/HEIGHT
    constants, so the two orientations share this one code path instead of a second,
    driftable copy of it."""
    actions = [a for a in scene.get("actions", []) if isinstance(a, str)]
    action_list = _split_duration(actions, duration)
    bg = _load_background(scene["background_path"], width=width, height=height)
    cast_entries = [c for c in (scene.get("cast") or []) if isinstance(c, dict) and c.get("archetype")]
    cast_by_side = _group_cast_by_side(cast_entries)

    ground_y = height * GROUND_FRAC
    target_height = height * CHARACTER_HEIGHT_FRAC
    cast_target_height = height * CAST_HEIGHT_FRAC
    start_x = _narrator_start_x(cast_entries, width=width) if cast_entries else width / 2

    own_tmp = frames_dir is None
    frames_dir = frames_dir or out_path.parent / f"_frames_{out_path.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    total_frames = max(1, round(duration * FPS))
    idx = 0
    prev_frame_path = None
    for pose_name, root_x, y_offset, flip in generate_sprite_frames(action_list, FPS, width, start_x, margin=MARGIN):
        frame_path = frames_dir / f"frame_{idx:05d}.png"
        if ON_TWOS and idx % 2 == 1 and prev_frame_path is not None:
            shutil.copyfile(prev_frame_path, frame_path)
        else:
            progress = idx / max(1, total_frames - 1)
            frame = _ken_burns_crop(bg, progress, zoom_in, width=width, height=height).convert("RGBA")
            t_seconds = idx / FPS

            # Cast members composite BEFORE the narrator, so the narrator (the show's
            # lead) always reads as the frame's foreground when positions are close.
            # Each side's character stays visible for the whole scene once present --
            # only its speech bubble is scoped to its own dialogue window (see
            # _active_cast_for_side) -- so a cast member never visibly vanishes and
            # reappears between two lines the way a shared start/end used to cause.
            for side, entries in cast_by_side.items():
                cast, show_bubble = _active_cast_for_side(entries, t_seconds, duration)
                cast_x = width * SIDE_X_FRAC.get(side, SIDE_X_FRAC["right"])
                bob = CAST_BOB_AMPLITUDE * math.sin(2 * math.pi * t_seconds / CAST_BOB_PERIOD)
                cast_outfit = cast.get("outfit") or outfit
                # Approximation: sprites are generated facing forward (not a specific
                # direction), so flipping a right-side cast member is a best-effort
                # nudge toward "facing the narrator" for asymmetric poses like
                # point/offer, not a guarantee -- good enough for a held, brief
                # appearance; not worth a second generation pass to get exact.
                composite_cast_member(
                    frame, cast["archetype"], cast_outfit, cast.get("pose", "stand"),
                    cast_x, ground_y + bob, cast_target_height, flip=(side == "right"),
                )
                if show_bubble and cast.get("dialogue"):
                    bubble_y = ground_y + bob - cast_target_height - 30
                    _draw_speech_bubble(frame, cast["dialogue"], cast_x, bubble_y)

            composite_character(frame, outfit, pose_name, root_x, ground_y + y_offset, target_height, flip=flip)
            frame.convert("RGB").save(frame_path)
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


def render_still(scene: dict, outfit: str = "standard", pose_name: str = "celebrate",
                  width: int = 1280, height: int = 720) -> Image.Image:
    """Renders a single still frame (for thumbnails)."""
    bg = _load_background(scene["background_path"]) if scene.get("background_path") else \
        Image.new("RGB", (int(width * MAX_ZOOM), int(height * MAX_ZOOM)), (245, 245, 240))
    frame = bg.resize((int(width * MAX_ZOOM), int(height * MAX_ZOOM)), Image.LANCZOS)
    frame = frame.crop((
        (frame.width - width) / 2, (frame.height - height) / 2,
        (frame.width + width) / 2, (frame.height + height) / 2,
    )).convert("RGBA")
    ground_y = height * GROUND_FRAC
    target_height = height * (CHARACTER_HEIGHT_FRAC * 0.9)
    composite_character(frame, outfit, pose_name, width / 2, ground_y, target_height, flip=False)
    return frame.convert("RGB")
