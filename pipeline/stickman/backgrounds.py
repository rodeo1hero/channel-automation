"""Minimal flat-color/line-art backgrounds and a small prop icon library, so
scenes have some visual variety without needing per-image AI generation."""
import math
from PIL import ImageDraw

PALETTES = {
    "plain":        {"sky": (245, 245, 240), "ground": None},
    "outdoor_day":  {"sky": (214, 234, 248), "ground": (203, 230, 190)},
    "outdoor_dusk": {"sky": (250, 214, 175), "ground": (196, 214, 180)},
    "outdoor_night": {"sky": (35, 40, 62), "ground": (48, 54, 74)},
    "indoor":       {"sky": (238, 231, 219), "ground": (214, 200, 178)},
    "office":       {"sky": (229, 231, 235), "ground": (196, 190, 178)},
}
LINE = (30, 30, 30)


def draw_background(draw: ImageDraw.ImageDraw, width: int, height: int,
                     kind: str = "plain", ground_y: float = None) -> None:
    pal = PALETTES.get(kind, PALETTES["plain"])
    draw.rectangle([0, 0, width, height], fill=pal["sky"])
    if pal["ground"] is not None:
        gy = ground_y if ground_y is not None else height * 0.82
        draw.rectangle([0, gy, width, height], fill=pal["ground"])
        draw.line([(0, gy), (width, gy)], fill=LINE, width=3)


# --- Prop icons: simple line-art, drawn centered at `pos` with a given `size` ---

def _sun(draw, pos, size, color=LINE):
    x, y = pos
    r = size * 0.32
    draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=max(3, int(size * 0.05)))
    for i in range(8):
        a = math.radians(i * 45)
        x1, y1 = x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 1.35
        x2, y2 = x + math.cos(a) * r * 1.75, y + math.sin(a) * r * 1.75
        draw.line([(x1, y1), (x2, y2)], fill=color, width=max(3, int(size * 0.045)))


def _cloud(draw, pos, size, color=LINE):
    x, y = pos
    r = size * 0.2
    for dx, dy, rr in [(-r, 0, r), (0, -r * 0.5, r * 1.1), (r, 0, r * 0.85)]:
        draw.ellipse([x + dx - rr, y + dy - rr, x + dx + rr, y + dy + rr],
                     outline=color, width=max(3, int(size * 0.045)))


def _house(draw, pos, size, color=LINE):
    # `pos` is the vertical CENTER of the icon (consistent with the other
    # prop drawers), not the ground -- these are small corner decorations,
    # not physically grounded set pieces.
    x, y = pos
    w, h = size * 0.7, size * 0.5
    roof_h = h * 0.7
    top = y - (h + roof_h) / 2 + roof_h
    bottom = top + h
    draw.line([(x - w / 2, top), (x, top - roof_h), (x + w / 2, top)], fill=color,
              width=max(3, int(size * 0.05)), joint="curve")
    draw.rectangle([x - w / 2, top, x + w / 2, bottom], outline=color, width=max(3, int(size * 0.05)))
    dw, dh = w * 0.22, h * 0.5
    draw.rectangle([x - dw / 2, bottom - dh, x + dw / 2, bottom], outline=color, width=max(2, int(size * 0.035)))


def _tree(draw, pos, size, color=LINE):
    x, y = pos
    trunk_w, trunk_h = size * 0.16, size * 0.28
    r = size * 0.34
    total_h = trunk_h + r * 2
    top = y - total_h / 2
    canopy_cy = top + r
    trunk_top = canopy_cy + r * 0.55
    trunk_bottom = trunk_top + trunk_h
    draw.rectangle([x - trunk_w / 2, trunk_top, x + trunk_w / 2, trunk_bottom],
                    fill=color)
    draw.ellipse([x - r, canopy_cy - r, x + r, canopy_cy + r], outline=color, width=max(4, int(size * 0.06)))


def _lightbulb(draw, pos, size, color=LINE):
    x, y = pos
    r = size * 0.24
    draw.ellipse([x - r, y - r * 1.3, x + r, y + r * 0.7], outline=color, width=max(3, int(size * 0.05)))
    draw.line([(x - r * 0.4, y + r * 0.7), (x + r * 0.4, y + r * 0.7)], fill=color, width=max(3, int(size * 0.05)))
    draw.line([(x - r * 0.3, y + r * 1.05), (x + r * 0.3, y + r * 1.05)], fill=color, width=max(3, int(size * 0.05)))
    for i in range(5):
        a = math.radians(-90 + (i - 2) * 30)
        x1 = x + math.cos(a) * r * 1.5
        y1 = y - r * 0.3 + math.sin(a) * r * 1.5
        x2 = x + math.cos(a) * r * 1.9
        y2 = y - r * 0.3 + math.sin(a) * r * 1.9
        draw.line([(x1, y1), (x2, y2)], fill=color, width=max(2, int(size * 0.035)))


def _gear(draw, pos, size, color=LINE):
    x, y = pos
    r = size * 0.26
    draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=max(3, int(size * 0.05)))
    draw.ellipse([x - r * 0.35, y - r * 0.35, x + r * 0.35, y + r * 0.35], outline=color,
                 width=max(2, int(size * 0.035)))
    for i in range(8):
        a = math.radians(i * 45)
        x1, y1 = x + math.cos(a) * r * 0.95, y + math.sin(a) * r * 0.95
        x2, y2 = x + math.cos(a) * r * 1.3, y + math.sin(a) * r * 1.3
        draw.line([(x1, y1), (x2, y2)], fill=color, width=max(4, int(size * 0.06)))


def _question_mark(draw, pos, size, color=LINE):
    from PIL import ImageFont
    x, y = pos
    try:
        font = ImageFont.load_default(size=int(size))
    except TypeError:
        font = ImageFont.load_default()
    draw.text((x, y), "?", fill=color, font=font, anchor="mm")


def _arrow(draw, pos, size, color=LINE, direction="right"):
    x, y = pos
    w = size * 0.5
    dx = w if direction == "right" else -w
    draw.line([(x - dx, y), (x + dx, y)], fill=color, width=max(4, int(size * 0.06)))
    a = 0 if direction == "right" else 180
    ang = math.radians(a)
    for off in (35, -35):
        ang2 = ang + math.radians(off + 180)
        x2 = x + dx + math.cos(ang2) * w * 0.4
        y2 = y + math.sin(ang2) * w * 0.4
        draw.line([(x + dx, y), (x2, y2)], fill=color, width=max(4, int(size * 0.06)))


def _book(draw, pos, size, color=LINE):
    x, y = pos
    w, h = size * 0.5, size * 0.4
    draw.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], outline=color, width=max(3, int(size * 0.05)))
    draw.line([(x, y - h / 2), (x, y + h / 2)], fill=color, width=max(2, int(size * 0.035)))


def _clock(draw, pos, size, color=LINE):
    x, y = pos
    r = size * 0.26
    draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=max(3, int(size * 0.05)))
    draw.line([(x, y), (x, y - r * 0.6)], fill=color, width=max(3, int(size * 0.045)))
    draw.line([(x, y), (x + r * 0.4, y + r * 0.2)], fill=color, width=max(3, int(size * 0.045)))


PROP_DRAWERS = {
    "sun": _sun, "cloud": _cloud, "house": _house, "tree": _tree,
    "lightbulb": _lightbulb, "gear": _gear, "question_mark": _question_mark,
    "arrow_right": lambda d, p, s, c=LINE: _arrow(d, p, s, c, "right"),
    "arrow_left": lambda d, p, s, c=LINE: _arrow(d, p, s, c, "left"),
    "book": _book, "clock": _clock,
}
PROP_NAMES = sorted(PROP_DRAWERS.keys())


def draw_prop(draw, name, pos, size, color=LINE):
    fn = PROP_DRAWERS.get(name)
    if fn:
        fn(draw, pos, size, color)
