"""Generates one AI background image per scene (Replicate/FLUX), styled to
match the hand-drawn stick-figure character so the two composite together
cleanly. This is the one recurring per-video API cost in the visuals stage
now that the character itself is a free, pre-generated, reusable sprite
sheet (see scripts/generate_character.py and pipeline/stickman/)."""
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from . import cost_tracker
from .utils import DRY_RUN, load_channel_config, log, require_env

REPLICATE_MODEL = "black-forest-labs/flux-1.1-pro"

# Pixel size used for a DRY_RUN placeholder image, keyed by the same aspect_ratio string
# passed to Replicate -- keeps the placeholder's proportions honest for whichever
# orientation is being generated (16:9 for the main video, 9:16 for a Short).
PLACEHOLDER_SIZE = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
}


def _style_suffix(aspect_ratio: str) -> str:
    # Deliberately does NOT hardcode "16:9" in the prompt text itself (only the
    # `aspect_ratio` API parameter controls the actual output shape) -- the earlier
    # version baked "16:9" into every prompt, which would have been actively wrong
    # guidance to the model when generating 9:16 Shorts backgrounds.
    return (
        "simple minimalist black-and-white line-art illustration, hand-drawn "
        "whiteboard-animation background art style, clean sparse linework, no "
        "characters or people in the scene, no text or watermarks"
    )


MAX_RETRIES = 6
NSFW_RETRIES = 3


def _placeholder_image(path: Path, text: str, size=(1920, 1080)) -> None:
    img = Image.new("RGB", size, color=(245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), text[:200], fill=(80, 80, 80))
    img.save(path)


def _post_with_retry(url: str, headers: dict, json_body: dict):
    """POSTs to Replicate, retrying on BOTH rate limits (HTTP 429) and transient
    network failures (connection reset, DNS blip, timeout, etc.) -- a bare
    requests.exceptions.RequestException has no HTTP response to check a status
    code on, so it needs its own except clause rather than falling through the
    429-only status check that used to be the only retry path here. A single
    dropped connection on GitHub Actions' runner used to crash the whole run
    (losing all already-completed narration/TTS work for every scene) instead
    of just retrying like a 429 already did."""
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, json=json_body, timeout=120)
        except requests.exceptions.RequestException as e:
            wait_s = 2 ** attempt
            log(f"Replicate network error on POST (attempt {attempt + 1}/{MAX_RETRIES}): {e}; waiting {wait_s}s")
            time.sleep(wait_s)
            continue
        if resp.status_code != 429:
            return resp
        wait_s = float(resp.headers.get("Retry-After", 2 ** attempt))
        log(f"Replicate rate-limited (attempt {attempt + 1}/{MAX_RETRIES}), waiting {wait_s:.0f}s")
        time.sleep(wait_s)

    if resp is None:
        raise RuntimeError(
            f"Replicate POST failed after {MAX_RETRIES} attempts -- network error every time, no response received"
        )
    return resp


def _get_with_retry(url: str, retries: int = 4, **kwargs):
    """Same rationale as _post_with_retry, for the polling and image-download GETs --
    both used to be a single unretried requests.get() that could crash the run on any
    transient network blip."""
    last_exc = None
    for attempt in range(retries):
        try:
            return requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            wait_s = 2 ** attempt
            log(f"Replicate network error on GET (attempt {attempt + 1}/{retries}): {e}; waiting {wait_s}s")
            time.sleep(wait_s)
    raise RuntimeError(f"Replicate GET {url} failed after {retries} attempts: {last_exc}")


def _generate_replicate(prompt: str, out_path: Path, aspect_ratio: str = "16:9",
                         run_id: str = "unknown", scene_index: int = -1) -> None:
    token = require_env("REPLICATE_API_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }

    resp = _post_with_retry(
        f"https://api.replicate.com/v1/models/{REPLICATE_MODEL}/predictions",
        headers,
        {"input": {"prompt": prompt, "aspect_ratio": aspect_ratio}},
    )

    resp.raise_for_status()
    # A 429 never reaches here (it loops or eventually raises via raise_for_status
    # on a non-429 error status) -- getting past this line means Replicate accepted
    # and ran the prediction, which is the actual billing trigger regardless of
    # whether the output later turns out NSFW-flagged, so the cost is real either way.
    cost_tracker.record_replicate_background_call(run_id, scene_index, succeeded=True)
    data = resp.json()

    get_url = data["urls"]["get"]
    for _ in range(60):
        status = data.get("status")
        if status == "succeeded":
            break
        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate prediction {status}: {data.get('error')}")
        time.sleep(5)
        poll_resp = _get_with_retry(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        poll_resp.raise_for_status()
        data = poll_resp.json()
    else:
        raise RuntimeError(f"Replicate prediction did not finish in time: {data.get('status')}")

    output = data.get("output")
    image_url = output[0] if isinstance(output, list) else output
    if not image_url:
        raise RuntimeError(f"Replicate prediction succeeded but returned no output: {data}")

    img_resp = _get_with_retry(image_url, timeout=60)
    img_resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img_resp.content)


def _generate_safely(prompt: str, out_path: Path, fallback_label: str, aspect_ratio: str = "16:9",
                      run_id: str = "unknown", scene_index: int = -1) -> None:
    last_error = None
    for attempt in range(NSFW_RETRIES):
        try:
            _generate_replicate(prompt, out_path, aspect_ratio=aspect_ratio, run_id=run_id, scene_index=scene_index)
            return
        except RuntimeError as e:
            if "NSFW" not in str(e):
                raise
            last_error = e
            log(f"NSFW false-positive on attempt {attempt + 1}/{NSFW_RETRIES}, retrying")
    log(f"Giving up after {NSFW_RETRIES} NSFW-flagged attempts, using placeholder background: {last_error}")
    _placeholder_image(out_path, fallback_label, size=PLACEHOLDER_SIZE.get(aspect_ratio, (1920, 1080)))


def generate_scene_backgrounds(scenes: list, run_dir: Path, run_id: str = "unknown",
                                aspect_ratio: str = "16:9") -> list:
    """Mutates scenes in place, adding 'background_path' to each. aspect_ratio is "16:9"
    for the main video or "9:16" for a vertical Short (see pipeline/shorts.py) -- passed
    straight through to Replicate/FLUX's own aspect_ratio input, not simulated by
    cropping a 16:9 image after the fact, so a Short's backgrounds are actually composed
    for a vertical frame rather than a cropped-down widescreen one."""
    backgrounds_dir = run_dir / "backgrounds"
    backgrounds_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        out_path = backgrounds_dir / f"scene_{i:03d}.png"
        base_prompt = scene.get("background_prompt", "a plain simple background")
        full_prompt = f"{base_prompt}, {_style_suffix(aspect_ratio)}"

        if DRY_RUN:
            log(f"Generating background for scene {i} (mock placeholder)")
            _placeholder_image(out_path, base_prompt, size=PLACEHOLDER_SIZE.get(aspect_ratio, (1920, 1080)))
        else:
            log(f"Generating background for scene {i}")
            _generate_safely(full_prompt, out_path, base_prompt, aspect_ratio=aspect_ratio,
                              run_id=run_id, scene_index=i)
            time.sleep(1.1)  # stay under Replicate's 1 req/sec cap for accounts without billing set up

        scene["background_path"] = str(out_path)

    return scenes
