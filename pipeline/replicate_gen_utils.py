"""Shared low-level helpers for talking to Replicate's gpt-image-2.5-flare model and
post-processing its output -- used by BOTH pipeline/character_gen.py (the recurring
narrator) and pipeline/cast_gen.py (secondary/supporting characters), so the two never
duplicate this logic and drift out of sync (that happened once already this session with
outfit_dir()/CHARACTER_DIR -- see character_gen.py's DRYRUN_CHARACTER_DIR comment -- so
now there is exactly one copy of everything reusable here)."""
import base64
import io
import time

import numpy as np
import requests
from PIL import Image, ImageChops, ImageDraw

from .utils import log

MODEL = "openai/gpt-image-2.5-flare"
MAX_RETRIES = 5
THROTTLE_SECONDS = 1.1  # stay under Replicate's 1 req/sec cap for accounts without billing set up


def image_to_data_uri(path) -> str:
    from pathlib import Path
    data = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def post_prediction(payload: dict, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    last_error = None
    for attempt in range(MAX_RETRIES):
        resp = requests.post(
            f"https://api.replicate.com/v1/models/{MODEL}/predictions",
            headers=headers, json={"input": payload}, timeout=180,
        )
        if resp.status_code == 429:
            wait_s = float(resp.headers.get("Retry-After", 2 ** attempt))
            log(f"  rate-limited, waiting {wait_s:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait_s)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "succeeded":
            return data
        if data.get("error"):
            last_error = data["error"]
            log(f"  generation error, retrying: {last_error}")
            time.sleep(2 ** attempt)
            continue
        # "Prefer: wait" should block until done, but poll defensively just in case.
        get_url = data["urls"]["get"]
        for _ in range(30):
            time.sleep(4)
            poll = requests.get(get_url, headers=headers, timeout=30)
            poll.raise_for_status()
            data = poll.json()
            if data.get("status") == "succeeded":
                return data
            if data.get("status") in ("failed", "canceled"):
                last_error = data.get("error")
                break
        else:
            last_error = "timed out waiting for prediction"
    raise RuntimeError(f"gpt-image-2.5-flare failed after {MAX_RETRIES} attempts: {last_error}")


def download_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


def remove_background_via_flood(img: Image.Image, flood_thresh: int = 30, diff_thresh: int = 40) -> Image.Image:
    """Strips a roughly-white background from a grid cell by flood-filling inward from
    the cell's border with a sentinel color, then turning sentinel-colored pixels
    transparent. Flood-filling from the BORDER (rather than color-keying every
    near-white pixel in the whole image) is what makes this safe for a character with
    white/cream clothing (like a toga) -- an enclosed white garment isn't connected to
    the border through the black outline around it, so the flood fill can't leak into it
    and erase it, the way a naive "make all white pixels transparent" pass would."""
    rgb = img.convert("RGB")
    filled = rgb.copy()
    sentinel = (255, 0, 255)
    w, h = filled.size
    seeds = [
        (0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
        (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2),
    ]
    for seed in seeds:
        try:
            ImageDraw.floodfill(filled, seed, sentinel, thresh=flood_thresh)
        except (IndexError, ValueError):
            pass
    sentinel_img = Image.new("RGB", filled.size, sentinel)
    diff = ImageChops.difference(filled, sentinel_img).convert("L")
    alpha = diff.point(lambda x: 0 if x < diff_thresh else 255)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def find_bands(mask_1d, min_gap: int = 6, min_width: int = 10) -> list:
    """Given a 1D boolean sequence (True = "content" present at that index),
    returns a list of (start, end) index ranges for contiguous content runs,
    merging runs separated by a gap smaller than min_gap (so a thin
    anti-aliased seam between two poses doesn't split one pose into two
    bands) and dropping any band narrower than min_width (stray noise)."""
    n = len(mask_1d)
    raw = []
    start = None
    for i in range(n):
        if mask_1d[i]:
            if start is None:
                start = i
        elif start is not None:
            raw.append((start, i))
            start = None
    if start is not None:
        raw.append((start, n))
    if not raw:
        return []

    merged = [raw[0]]
    for s, e in raw[1:]:
        ps, pe = merged[-1]
        if s - pe <= min_gap:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    return [(s, e) for s, e in merged if e - s >= min_width]


def slice_grid_cells(sheet: Image.Image, n: int) -> list:
    """Figures out where each of the n poses actually landed in a generated grid
    sheet by looking at the ink itself, instead of trusting the rows x cols we
    asked the model for -- gpt-image-2.5-flare doesn't reliably draw the exact
    grid dimensions requested (e.g. asked for "2 rows of 4" for 6 poses, it
    sometimes draws a 2x3 grid instead), and slicing at the WRONG assumed
    boundaries bleeds neighboring poses into each other. Returns a list of n
    (left, top, right, bottom) boxes in reading order (top-to-bottom row
    bands, left-to-right within each row), matching the order poses were
    listed in the prompt."""
    gray = np.array(sheet.convert("L"))
    h, w = gray.shape
    ink = gray < 245  # non-white pixel

    row_bands = find_bands(ink.any(axis=1), min_gap=max(4, h // 80), min_width=h // 20)
    if not row_bands:
        row_bands = [(0, h)]

    # First try: does content-projection column detection within each row band
    # find exactly n poses total? If so, trust it -- it's the most accurate
    # boundary. If the model drew ragged/uneven cells, or noise throws the
    # count off, fall back to evenly dividing each row's width using the
    # CORRECT per-row pose count inferred from how many row bands were
    # actually detected.
    row_col_bands = []
    for rt, rb in row_bands:
        col_mask = ink[rt:rb, :].any(axis=0)
        row_col_bands.append(find_bands(col_mask, min_gap=max(4, w // 80), min_width=w // 20))

    boxes = []
    if sum(len(cb) for cb in row_col_bands) == n:
        for (rt, rb), col_bands in zip(row_bands, row_col_bands):
            for cl, cr in col_bands:
                boxes.append((cl, rt, cr, rb))
    else:
        num_rows = len(row_bands)
        base, rem = divmod(n, num_rows)
        counts = [base + (1 if i < rem else 0) for i in range(num_rows)]
        for (rt, rb), count in zip(row_bands, counts):
            if count <= 0:
                continue
            cell_w = w / count
            for c in range(count):
                boxes.append((int(c * cell_w), rt, int((c + 1) * cell_w), rb))

    # Pad each box outward a little so the border-flood-fill background
    # remover in remove_background_via_flood has real background pixels to
    # seed from, even when a detected content box hugs the pose tightly.
    pad = max(6, int(0.02 * min(w, h)))
    padded = []
    for l, t, r, b in boxes[:n]:
        padded.append((max(0, l - pad), max(0, t - pad), min(w, r + pad), min(h, b + pad)))
    return padded
