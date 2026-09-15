"""Loads and composites a secondary/supporting "cast" character's sprite (see
pipeline/cast_gen.py, assets/cast/<archetype>/<outfit>/*.png) onto a frame -- the same
approach as character_sprites.py (auto-crop to non-transparent bounding box, scale to a
consistent on-screen height) but rooted at the cast cache instead of the narrator's, and
keyed by (archetype, outfit) instead of just outfit, since a cast archetype is reusable
across every era/outfit the show uses."""
from functools import lru_cache

from PIL import Image

from ..cast_gen import cast_dir


@lru_cache(maxsize=None)
def _load_cropped(archetype: str, outfit: str, pose_name: str) -> Image.Image:
    path = cast_dir(archetype, outfit) / f"{pose_name}.png"
    if not path.exists():
        # Fall back to this archetype's "stand" pose, so a missing/not-yet-generated
        # pose sprite degrades gracefully instead of crashing a whole render.
        path = cast_dir(archetype, outfit) / "stand.png"
    img = Image.open(path).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    return img


def available_cast_poses(archetype: str, outfit: str) -> set:
    d = cast_dir(archetype, outfit)
    if not d.exists():
        return set()
    return {p.stem for p in d.glob("*.png") if not p.stem.startswith("_")}


def composite_cast_member(frame: Image.Image, archetype: str, outfit: str, pose_name: str,
                           root_x: float, ground_y: float, target_height: int, flip: bool = False) -> None:
    """Pastes the given cast archetype+outfit+pose's sprite onto `frame` (mutated in
    place) so the sprite's bottom-center lands at (root_x, ground_y), scaled so its
    height (after auto-cropping transparent margin) equals `target_height`. Mirrors
    character_sprites.composite_character exactly, just addressed by (archetype,
    outfit) instead of a single outfit key."""
    sprite = _load_cropped(archetype, outfit, pose_name)
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
