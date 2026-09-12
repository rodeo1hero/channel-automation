"""Stage 4: generate one still image per scene from its visual_prompt."""
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .utils import DRY_RUN, load_channel_config, log, require_env

REPLICATE_MODEL = "black-forest-labs/flux-1.1-pro"  # swap for whatever FLUX/other model
# you have access to on Replicate — check https://replicate.com/explore for current options.


def _placeholder_image(path: Path, text: str, size=(1792, 1008)) -> None:
    img = Image.new("RGB", size, color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), text[:200], fill=(220, 220, 220))
    img.save(path)


MAX_RETRIES = 6


def _generate_replicate(prompt: str, out_path: Path) -> None:
    token = require_env("REPLICATE_API_TOKEN")

    resp = None
    for attempt in range(MAX_RETRIES):
        resp = requests.post(
            f"https://api.replicate.com/v1/models/{REPLICATE_MODEL}/predictions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            },
            json={"input": {"prompt": prompt, "aspect_ratio": "16:9"}},
            timeout=120,
        )
        if resp.status_code != 429:
            break
        # Rate-limited: back off and retry rather than crashing the whole run.
        # Respect the server's Retry-After header when it sends one, otherwise
        # use exponential backoff (this matters most for accounts without a
        # payment method on file, which Replicate caps at ~1 request/second).
        wait_s = float(resp.headers.get("Retry-After", 2 ** attempt))
        log(f"Replicate rate-limited (attempt {attempt + 1}/{MAX_RETRIES}), waiting {wait_s:.0f}s")
        time.sleep(wait_s)

    resp.raise_for_status()
    data = resp.json()
    output = data.get("output")
    image_url = output[0] if isinstance(output, list) else output
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img_resp.content)


def generate_scene_images(scenes: list, run_dir: Path) -> list:
    """Mutates scenes in place, adding 'image_path' to each."""
    config = load_channel_config()
    style_suffix = config.get("visual_style_suffix", "")
    images_dir = run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        out_path = images_dir / f"scene_{i:03d}.png"
        full_prompt = f"{scene['visual_prompt']}, {style_suffix}".strip(", ")

        if DRY_RUN:
            log(f"Generating image for scene {i} (mock placeholder)")
            _placeholder_image(out_path, scene["visual_prompt"])
        else:
            log(f"Generating image for scene {i}")
            _generate_replicate(full_prompt, out_path)
            time.sleep(1.1)  # stay under Replicate's 1 req/sec cap for accounts without billing set up

        scene["image_path"] = str(out_path)

    return scenes


def generate_thumbnail(title: str, hero_prompt: str, run_dir: Path) -> Path:
    out_path = run_dir / "thumbnail.png"
    if DRY_RUN:
        log("Generating thumbnail (mock placeholder)")
        _placeholder_image(out_path, title, size=(1280, 720))
    else:
        log("Generating thumbnail")
        _generate_replicate(hero_prompt, out_path)
    return out_path