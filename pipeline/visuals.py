"""Stage 4: render one animated clip per scene by compositing the reusable
character sprite sheet (assets/character/<outfit>/, generated on demand by
pipeline/character_gen.py -- and cached there, so a given outfit/pose
combination is only ever paid for once) over an AI-generated background
per scene, plus a thumbnail. The recurring API costs here are the per-scene
background (pipeline/scene_backgrounds.py) and, the first time a given
video's outfit/pose combination hasn't been seen before, that handful of
new character sprites."""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .cast_gen import CAST_ROLES, ensure_cast_sprites
from .character_gen import ensure_outfit_sprites
from .scene_backgrounds import generate_scene_backgrounds
from .stickman.actions import sprite_names_needed_for
from .stickman.ai_scene_renderer import HEIGHT, SHORT_HEIGHT, SHORT_WIDTH, WIDTH, render_scene_clip, render_still
from .utils import log

# (aspect_ratio string, FLUX param) -> (render width, render height). "16:9" is the
# main video's landscape frame; "9:16" is a vertical YouTube Short (see
# pipeline/shorts.py) -- both backgrounds (Replicate/FLUX's own aspect_ratio input)
# and the stick-figure compositing/Ken Burns math share this one lookup so the two
# orientations can never quietly drift out of sync with each other.
FRAME_SIZE_FOR_ASPECT = {
    "16:9": (WIDTH, HEIGHT),
    "9:16": (SHORT_WIDTH, SHORT_HEIGHT),
}

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _ensure_cast_for_scenes(scenes: list, outfit: str, run_id: str) -> None:
    """Groups every scene's cast appearances by (archetype, outfit-override-or-video-
    outfit) and generates whatever poses that combination is missing -- same
    only-pay-for-what's-new caching model as ensure_outfit_sprites, just keyed on one
    more dimension (archetype) since a cast role is reused across many outfits/videos."""
    needed = {}  # (archetype, outfit) -> set of pose names
    for scene in scenes:
        for cast in (scene.get("cast") or []):
            if not isinstance(cast, dict):
                continue
            archetype = cast.get("archetype")
            if archetype not in CAST_ROLES:
                log(f"Warning: dropping unknown cast archetype {archetype!r} from scene")
                continue
            cast_outfit = cast.get("outfit") or outfit
            key = (archetype, cast_outfit)
            needed.setdefault(key, set()).add(cast.get("pose", "stand"))

    for (archetype, cast_outfit), poses in needed.items():
        log(f"Ensuring cast sprites for '{archetype}' in outfit '{cast_outfit}': {sorted(poses)}")
        ensure_cast_sprites(archetype, cast_outfit, poses, run_id=run_id)


def generate_scene_clips(scenes: list, run_dir: Path, outfit: str = "standard", run_id: str = "unknown",
                          aspect_ratio: str = "16:9") -> list:
    """Mutates scenes in place, adding 'background_path' and 'clip_path' to
    each. Requires scene['duration'] to already be set (voiceover runs
    before this stage in run_pipeline.py). aspect_ratio is "16:9" for the main video
    or "9:16" for a vertical Short -- see FRAME_SIZE_FOR_ASPECT above; character/cast
    sprites themselves need no regeneration for a different aspect ratio (they're
    just transparent cutouts composited at whatever size the frame calls for), only
    the backgrounds and the render frame size change."""
    width, height = FRAME_SIZE_FOR_ASPECT.get(aspect_ratio, (WIDTH, HEIGHT))
    generate_scene_backgrounds(scenes, run_dir, run_id=run_id, aspect_ratio=aspect_ratio)

    all_actions = [a for scene in scenes for a in (scene.get("actions") or [])]
    needed_poses = sprite_names_needed_for(all_actions)
    log(f"Ensuring character sprites for outfit '{outfit}': {sorted(needed_poses)}")
    ensure_outfit_sprites(outfit, needed_poses, run_id=run_id)
    _ensure_cast_for_scenes(scenes, outfit, run_id=run_id)

    clips_dir = run_dir / "scene_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        out_path = clips_dir / f"scene_{i:03d}.mp4"
        duration = scene.get("duration", 8.0)
        log(f"Rendering scene {i} clip ({duration:.1f}s, actions={scene.get('actions')})")
        render_scene_clip(scene, duration, out_path, outfit=outfit, zoom_in=(i % 2 == 0), log=log,
                           width=width, height=height)
        scene["clip_path"] = str(out_path)

    return scenes


def _wrap_and_fit(draw: ImageDraw.ImageDraw, title: str, max_width: int, max_height: int,
                   start_size: int, max_lines: int = 2):
    """Finds the largest font size (down to a legible floor) at which the
    FULL title -- never truncated, every word kept -- wraps to at most
    `max_lines` lines and fits within max_width x max_height. Tries
    progressively smaller sizes, then progressively more allowed lines, and
    only as a last resort accepts a result taller than max_height (still
    never drops words)."""
    if not _has_font():
        return ImageFont.load_default(), textwrap.wrap(title.upper(), width=20)

    best = None
    for lines_allowed in (max_lines, max_lines + 1, max_lines + 2):
        size = start_size
        while size >= 30:
            font = ImageFont.truetype(FONT_PATH, size)
            avg_char_w = max(1.0, draw.textlength("MNOPQR", font=font) / 6)
            wrap_chars = max(6, int(max_width / avg_char_w))
            lines = textwrap.wrap(title.upper(), width=wrap_chars)
            widest = max((draw.textlength(line, font=font) for line in lines), default=0)
            line_height = font.size * 1.15
            total_h = line_height * len(lines)
            if len(lines) <= lines_allowed and widest <= max_width:
                if total_h <= max_height:
                    return font, lines
                best = best or (font, lines)  # fits width, just a bit tall -- keep as fallback
            size -= 4
    return best or (ImageFont.truetype(FONT_PATH, 30), textwrap.wrap(title.upper(), width=16))


def _has_font() -> bool:
    try:
        ImageFont.truetype(FONT_PATH, 10)
        return True
    except OSError:
        return False


def _draw_title_banner(img: Image.Image, title: str) -> Image.Image:
    """Overlays a bold, outlined title across the top of the thumbnail --
    the figure is rendered with headroom left specifically for this."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    max_width = int(w * 0.90)
    max_height = int(h * 0.32)
    font, lines = _wrap_and_fit(draw, title, max_width, max_height, start_size=76, max_lines=2)

    line_height = font.size * 1.15
    y = h * 0.035
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (w - tw) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255),
                   stroke_width=max(3, font.size // 14), stroke_fill=(15, 15, 15))
        y += line_height
    return img


def generate_thumbnail(title: str, hero_scene: dict, run_dir: Path, outfit: str = "standard") -> Path:
    out_path = run_dir / "thumbnail.png"
    log("Rendering thumbnail")
    img = render_still(hero_scene or {}, outfit=outfit, pose_name="celebrate")
    img = _draw_title_banner(img, title)
    img.save(out_path)
    return out_path
