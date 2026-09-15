"""Loads and composites the pre-rendered character sprite sheet (see
pipeline/character_gen.py, assets/character/<outfit>/*.png) onto a
background frame. Each sprite is auto-cropped to its non-transparent
bounding box and scaled to a consistent on-screen height so switching
between poses (whose source framing/zoom isn't perfectly uniform) never
produces a jarring size jump -- a deliberate "always looks right next to
itself" simplification over strict physical scale accuracy (e.g. a sitting
or desk/chair pose ends up about as tall on screen as a standing one, not
physically shorter)."""
from functools import lru_cache

from PIL import Image

# Reuse character_gen.py's own outfit_dir() rather than a second hardcoded path --
# it's DRY_RUN-aware (dry-run placeholders live under assets/_dryrun_character/, not
# the real assets/character/ cache, so a --dry-run test run can never poison real
# generated art), and duplicating that logic here previously let the two drift out of
# sync silently.
from ..character_gen import outfit_dir


@lru_cache(maxsize=None)
def _load_cropped(outfit: str, pose_name: str) -> Image.Image:
    path = outfit_dir(outfit) / f"{pose_name}.png"
    if not path.exists():
        # Fall back to this outfit's "stand" pose, then the standard outfit's,
        # so a missing/not-yet-generated pose sprite degrades gracefully
        # instead of crashing a whole render.
        path = outfit_dir(outfit) / "stand.png"
    if not path.exists():
        path = outfit_dir("standard") / "stand.png"
    img = Image.open(path).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    return img


def available_poses(outfit: str) -> set:
    d = outfit_dir(outfit)
    if not d.exists():
        return set()
    return {p.stem for p in d.glob("*.png") if not p.stem.startswith("_")}


def composite_character(frame: Image.Image, outfit: str, pose_name: str, root_x: float, ground_y: float,
                         target_height: int, flip: bool = False) -> None:
    """Pastes the given outfit+pose's sprite onto `frame` (mutated in place)
    so the sprite's bottom-center lands at (root_x, ground_y), scaled so its
    height (after auto-cropping transparent margin) equals `target_height`."""
    sprite = _load_cropped(outfit, pose_name)
    w, h = sprite.size
    if h == 0:
        return
    scale = target_height / h
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    sprite = sprite.resize((new_w, new_h), Image.LANCZOS)
    if flip:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
    paste_x = round(root_x - new_w / 2)
    paste_y = round(ground_y - new_h)
    frame.alpha_composite(sprite, (paste_x, paste_y)) if frame.mode == "RGBA" else frame.paste(sprite, (paste_x, paste_y), sprite)
