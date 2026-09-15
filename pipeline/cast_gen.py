"""Generates and caches sprite sheets for secondary/supporting "cast" characters --
temporary characters the recurring narrator interacts with in a scene (a tax collector
demanding payment, a guard, a wealthy Roman hugging a coin pouch, ...) rather than
explains things to the camera about.

Unlike the narrator (pipeline/character_gen.py), a cast member is a REUSABLE ARCHETYPE,
not a fixed individual: each of CAST_ROLES is a role ("authority", "guard", "wealthy",
"poor", "merchant", "official") with a small set of identifying props/accessories, and
that role gets dressed in whichever era the video's chosen narrator outfit calls for
(the same "standard/historical/business/casual/modern/financial" keys as
character_gen.OUTFITS) via ERA_CLOTHING below -- so "official" becomes a Roman tax
collector for a historical video and a modern-day bureaucrat for a business video,
without redefining the character.

Sprites are cached to assets/cast/<archetype>/<outfit>/<pose>.png (assets/_dryrun_cast/
under DRY_RUN -- see character_gen.py's DRYRUN_CHARACTER_DIR for why dry-run output must
never land in the real cache). Once a given (archetype, outfit) combination has been
generated, every future video reusing it (any two historical-outfit videos both wanting
an "official") generates nothing new.

Cost: one reference-image call plus ONE grid-sheet call covering the entire
CAST_POSE_NAMES set generates a full archetype+outfit combination (Replicate bills per
call, not per pose drawn in it -- see cost_tracker.py), so a new (archetype, outfit)
combination costs about the same as two ordinary character_gen.py calls regardless of
how many of the 8 cast poses are actually used."""
import math
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw

from . import cost_tracker
from .replicate_gen_utils import (
    THROTTLE_SECONDS,
    download_image,
    image_to_data_uri,
    post_prediction,
    remove_background_via_flood,
    slice_grid_cells,
)
from .stickman.cast_descriptions import CAST_POSE_DESCRIPTIONS, CAST_POSE_NAMES
from .utils import DRY_RUN, log

ROOT = Path(__file__).resolve().parent.parent
CAST_DIR = ROOT / "assets" / "cast"
# Same dry-run-cache-pollution guard as character_gen.py's DRYRUN_CHARACTER_DIR: a
# --dry-run test run must never write into the real, committed cast cache.
DRYRUN_CAST_DIR = ROOT / "assets" / "_dryrun_cast"

QUALITY = "low"  # same tier/economics rationale as character_gen.QUALITY

# Generic, era-neutral base clothing per era key -- deliberately NOT character_gen.py's
# OUTFITS text, which includes the narrator's own signature accessories (e.g. the
# "historical" outfit's gold laurel wreath). A cast member should read as belonging to
# the same world/era as the narrator without being visually mistaken for them, so cast
# members get plain period-appropriate clothing and each archetype's own identifying
# prop (CAST_ROLES below) does the work of telling them apart from each other.
ERA_CLOTHING = {
    "standard": "wearing simple plain clothing with no particular era or style",
    "historical": "wearing a simple draped Roman-style tunic, undyed or muted in color",
    "business": "wearing simple modern business-casual clothing",
    "casual": "wearing simple modern casual streetwear",
    "modern": "wearing simple modern everyday clothing",
    "financial": "wearing simple modern business clothing",
}

# Reusable supporting-cast roles. Each is defined by what it's FOR (what kind of scene
# beat it plays) and a small set of props/accessories layered on top of ERA_CLOTHING so
# it silhouette-reads distinctly from the narrator and from every other role at a glance,
# even in a wide shot. Add new roles here as future scripts need them -- nothing else
# needs to change (script_writer.py reads this dict's keys automatically).
CAST_ROLES = {
    "authority": (
        "a figure of power and command, representing leadership or government: wears a "
        "simple gold crown or circlet on the head and an ornate clasped cloak with bold "
        "trim, standing with a tall, commanding bearing"
    ),
    "guard": (
        "a protector or enforcer figure, representing military or security force: wears "
        "a simple helmet and carries a short spear or baton in one hand"
    ),
    "wealthy": (
        "a person of obvious wealth and privilege: wears an extra gold chain or ring, "
        "finely trimmed clothing, and carries a bulging drawstring coin pouch at the belt"
    ),
    "poor": (
        "a person of modest means, representing ordinary working people: wears simple "
        "patched, worn clothing with no jewelry, and carries a small, visibly flat or "
        "empty pouch"
    ),
    "merchant": (
        "a trader or shopkeeper, representing commerce: wears a simple work apron over "
        "their clothing and carries a satchel or a small tray of goods"
    ),
    "official": (
        "a bureaucratic or administrative figure, representing taxes/paperwork/"
        "institutions: carries a rolled scroll or a clipboard-style tablet, and wears a "
        "simple sash marking their office"
    ),
}

BASE_STYLE = (
    "A simple graphic character for a hand-drawn explainer video, whiteboard-animation "
    "style, matching the show's established look. Off-white circular head, bald with no "
    "hair (unless described otherwise below), with soft flat shading, thin expressive "
    "dark eyebrows, simple eyes, and a small expressive mouth. No glasses unless "
    "described otherwise below. The body is a solid black flat silhouette: a tapered "
    "wedge-shaped torso narrowing at the neck, thin uniform black line arms and legs, no "
    "visible hand or foot detail -- this black silhouette is the character's core "
    "identity and must remain visible as the body, never replaced by separately drawn, "
    "fully illustrated realistic clothing. Any clothing/props described below are a "
    "small accent layered on top of the silhouette (trim, a held prop, a headpiece), not "
    "a redrawn garment. No color besides the character's outfit accents, which may "
    "include small muted or gold details. Clean, minimal, consistent line weight "
    "throughout. This is a SEPARATE, DIFFERENT individual from the show's main narrator "
    "character -- same simple line-art aesthetic and world, but do NOT give them a gold "
    "laurel wreath, sunglasses, or any other accessory that is the narrator's own "
    "signature look; this character has their own distinct identity as described below."
)

CONSISTENCY_SUFFIX = (
    "Character consistency is critical: do not redesign or reinterpret the character. "
    "Preserve the exact same head, facial features, body proportions, outfit, and "
    "line-art style."
)

REFERENCE_PROMPT_TEMPLATE = (
    BASE_STYLE + " The character is {clothing}. {role}. Standing in a relaxed, neutral "
    "pose, facing forward, full body visible, centered in frame with margin on all "
    "sides, plain white background. " + CONSISTENCY_SUFFIX
)

GRID_PROMPT_TEMPLATE = (
    BASE_STYLE + " The character is {clothing}. {role}.\n\n"
    "Create a grid of {n} separate full-body poses of this SAME character, arranged in "
    "{rows} row(s) of {cols}, in this exact left-to-right, top-to-bottom order, each "
    "pose clearly separated with generous white space between cells and no overlapping "
    "figures:\n{numbered_list}\n\n"
    "Keep all props extremely simple and graphic, matching the whiteboard-animation "
    "aesthetic. Plain white background. " + CONSISTENCY_SUFFIX
)

GRID_COLS = 4


def cast_dir(archetype: str, outfit: str) -> Path:
    base = DRYRUN_CAST_DIR if DRY_RUN else CAST_DIR
    return base / archetype / outfit


def _clothing_and_role(archetype: str, outfit: str) -> tuple:
    clothing = ERA_CLOTHING.get(outfit, ERA_CLOTHING["standard"])
    role = CAST_ROLES[archetype]
    return clothing, role


def generate_cast_reference(archetype: str, outfit: str, token: str, quality: str = QUALITY,
                             run_id: str = "unknown") -> Path:
    log(f"Generating cast reference (archetype={archetype}, outfit={outfit}, quality={quality})...")
    clothing, role = _clothing_and_role(archetype, outfit)
    prompt = REFERENCE_PROMPT_TEMPLATE.format(clothing=clothing, role=role)
    data = post_prediction(
        {"prompt": prompt, "aspect_ratio": "1:1", "quality": quality, "background": "opaque"},
        token,
    )
    url = data["output"][0] if isinstance(data["output"], list) else data["output"]
    img = download_image(url)
    out_dir = cast_dir(archetype, outfit)
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_path = out_dir / "_reference.png"
    img.convert("RGB").save(ref_path)
    log(f"  saved {ref_path}")
    cost_tracker.record_replicate_cast_call(run_id, archetype, outfit, "reference", ["_reference"], quality)
    return ref_path


def generate_cast_pose_grid(archetype: str, outfit: str, pose_names: list, reference_image: str,
                             token: str, quality: str = QUALITY, cols: int = GRID_COLS,
                             run_id: str = "unknown") -> list:
    """Generates every requested cast pose in ONE grid-sheet image (see
    character_gen.generate_pose_grid -- same slicing/background-removal logic, reused
    from replicate_gen_utils rather than duplicated)."""
    n = len(pose_names)
    if n == 0:
        return []
    cols = max(1, min(cols, n))
    rows = math.ceil(n / cols)
    clothing, role = _clothing_and_role(archetype, outfit)
    numbered_list = "\n".join(f"{i + 1}. {CAST_POSE_DESCRIPTIONS[name]}" for i, name in enumerate(pose_names))
    prompt = GRID_PROMPT_TEMPLATE.format(
        clothing=clothing, role=role, n=n, rows=rows, cols=cols, numbered_list=numbered_list,
    )
    log(f"Generating cast pose grid for '{archetype}' ({outfit}, {rows}x{cols}): {pose_names}")
    data = post_prediction(
        {
            "prompt": prompt,
            "input_images": [reference_image],
            "aspect_ratio": "1:1",
            "quality": quality,
            "background": "opaque",
        },
        token,
    )
    url = data["output"][0] if isinstance(data["output"], list) else data["output"]
    sheet = download_image(url).convert("RGB")
    out_dir = cast_dir(archetype, outfit)
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / f"_grid_debug_{pose_names[0]}.png")
    cost_tracker.record_replicate_cast_call(run_id, archetype, outfit, f"grid ({rows}x{cols})", pose_names, quality)

    boxes = slice_grid_cells(sheet, n)
    if len(boxes) != n:
        log(f"  Warning: detected {len(boxes)} grid cells but expected {n} -- slicing may be off")
    saved = []
    for i, (name, box) in enumerate(zip(pose_names, boxes)):
        cell = sheet.crop(box)
        cleaned = remove_background_via_flood(cell)
        bbox = cleaned.getbbox()
        if bbox:
            cleaned = cleaned.crop(bbox)
        out_path = out_dir / f"{name}.png"
        cleaned.save(out_path)
        log(f"  saved {out_path} (grid cell {i + 1}/{n})")
        saved.append(out_path)
    return saved


def _placeholder_sprite(archetype: str, pose_name: str) -> Image.Image:
    """Trivial transparent placeholder used only in --dry-run, so testing the pipeline
    stays fully offline and free (no Replicate calls) -- same idea as
    character_gen._placeholder_sprite, kept as its own tiny copy since it never touches
    real assets either way (no drift risk)."""
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((150, 20, 250, 120), outline=(0, 0, 0, 255), width=4)
    draw.line((200, 120, 200, 280), fill=(0, 0, 0, 255), width=4)
    draw.line((200, 160, 130, 220), fill=(0, 0, 0, 255), width=4)
    draw.line((200, 160, 270, 220), fill=(0, 0, 0, 255), width=4)
    draw.line((200, 280, 140, 380), fill=(0, 0, 0, 255), width=4)
    draw.line((200, 280, 260, 380), fill=(0, 0, 0, 255), width=4)
    draw.text((140, 135), f"{archetype[:6]}/{pose_name[:6]}", fill=(0, 0, 0, 255))
    return img


def ensure_cast_sprites(archetype: str, outfit: str, pose_names, token: str = None, quality: str = QUALITY,
                         run_id: str = "unknown") -> Path:
    """Makes sure assets/cast/<archetype>/<outfit>/<pose>.png exists for every name in
    pose_names, generating (and caching) only whatever's actually missing. Returns the
    archetype+outfit's sprite directory."""
    if archetype not in CAST_ROLES:
        log(f"Warning: unknown cast archetype '{archetype}', skipping")
        return cast_dir(archetype, outfit)
    if outfit not in ERA_CLOTHING:
        log(f"Warning: unknown outfit '{outfit}' for cast archetype '{archetype}', falling back to 'standard'")
        outfit = "standard"

    out_dir = cast_dir(archetype, outfit)
    out_dir.mkdir(parents=True, exist_ok=True)
    pose_names = sorted(set(pose_names) | {"stand"})
    missing = [p for p in pose_names if p in CAST_POSE_DESCRIPTIONS and not (out_dir / f"{p}.png").exists()]

    if not missing:
        log(f"All needed cast poses already cached for '{archetype}/{outfit}': {pose_names}")
        return out_dir

    if DRY_RUN:
        log(f"Generating placeholder cast sprites for '{archetype}/{outfit}': {missing} (dry-run, no API call)")
        for pose_name in missing:
            _placeholder_sprite(archetype, pose_name).save(out_dir / f"{pose_name}.png")
        return out_dir

    log(f"Cast '{archetype}/{outfit}' needs {len(missing)} new pose(s): {missing} (rest already cached)")
    token = token or os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is required to generate cast sprites")

    ref_path = out_dir / "_reference.png"
    if not ref_path.exists():
        ref_path = generate_cast_reference(archetype, outfit, token, quality=quality, run_id=run_id)
        time.sleep(THROTTLE_SECONDS)
    reference_image = image_to_data_uri(ref_path)

    generate_cast_pose_grid(archetype, outfit, missing, reference_image, token, quality=quality, run_id=run_id)
    return out_dir
