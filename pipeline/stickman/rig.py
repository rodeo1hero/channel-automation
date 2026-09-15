"""A minimal 2D stick-figure skeleton: forward kinematics + drawing.

Angles are in degrees, using image-space convention (y grows downward):
  0   = pointing screen-right
  90  = pointing straight down
  -90 = pointing straight up
  180 = pointing screen-left

A "pose" is a plain dict of joint angles (see POSE_FIELDS below) plus a
couple of extra offsets (hip_y_offset for crouch/sit/jump, head_bob for
subtle idle motion). Poses are authored by hand in poses.py and blended
frame-by-frame by actions.py.
"""
import math
from PIL import ImageDraw

# Bone lengths, in pixels, at scale=1.0 (a life-size-feeling figure at
# scale=1.0 stands roughly 340px tall -- actions.py / scene_renderer.py
# pick a scale appropriate to the frame size).
HEAD_R = 22
NECK = 10
TORSO = 105
UPPER_ARM = 44
FOREARM = 40
THIGH = 62
SHIN = 58

POSE_FIELDS = [
    "spine_angle",
    "L_upper_arm_angle", "L_forearm_angle",
    "R_upper_arm_angle", "R_forearm_angle",
    "L_thigh_angle", "L_shin_angle",
    "R_thigh_angle", "R_shin_angle",
    "hip_y_offset",
    "head_bob",
]

# A neutral pose used as a fallback / base to merge partial pose dicts onto.
DEFAULT_POSE = {
    "spine_angle": -90,
    "L_upper_arm_angle": 112, "L_forearm_angle": 100,
    "R_upper_arm_angle": 68, "R_forearm_angle": 80,
    "L_thigh_angle": 100, "L_shin_angle": 95,
    "R_thigh_angle": 80, "R_shin_angle": 85,
    "hip_y_offset": 0,
    "head_bob": 0,
}


def full_pose(partial: dict) -> dict:
    """Fills in any missing fields from DEFAULT_POSE."""
    p = dict(DEFAULT_POSE)
    p.update(partial)
    return p


def _pt(origin, angle_deg, length):
    a = math.radians(angle_deg)
    return (origin[0] + length * math.cos(a), origin[1] + length * math.sin(a))


def solve(pose: dict, root, scale: float = 1.0) -> dict:
    """Forward-kinematics: turns a pose dict + a root (hip) position into
    world-space joint coordinates, scaled by `scale`."""
    rx, ry = root
    ry -= pose.get("hip_y_offset", 0) * scale
    hip = (rx, ry)

    torso = TORSO * scale
    neck = NECK * scale
    head_r = HEAD_R * scale
    upper_arm = UPPER_ARM * scale
    forearm = FOREARM * scale
    thigh = THIGH * scale
    shin = SHIN * scale

    shoulder = _pt(hip, pose["spine_angle"], torso)
    head_base = _pt(shoulder, pose["spine_angle"], neck)
    head_center = (head_base[0], head_base[1] - pose.get("head_bob", 0) * scale)

    l_elbow = _pt(shoulder, pose["L_upper_arm_angle"], upper_arm)
    l_hand = _pt(l_elbow, pose["L_forearm_angle"], forearm)
    r_elbow = _pt(shoulder, pose["R_upper_arm_angle"], upper_arm)
    r_hand = _pt(r_elbow, pose["R_forearm_angle"], forearm)

    l_knee = _pt(hip, pose["L_thigh_angle"], thigh)
    l_foot = _pt(l_knee, pose["L_shin_angle"], shin)
    r_knee = _pt(hip, pose["R_thigh_angle"], thigh)
    r_foot = _pt(r_knee, pose["R_shin_angle"], shin)

    return {
        "hip": hip, "shoulder": shoulder, "head_center": head_center,
        "head_r": head_r,
        "L_elbow": l_elbow, "L_hand": l_hand,
        "R_elbow": r_elbow, "R_hand": r_hand,
        "L_knee": l_knee, "L_foot": l_foot,
        "R_knee": r_knee, "R_foot": r_foot,
    }


def draw_figure(draw: ImageDraw.ImageDraw, pose: dict, root, scale: float = 1.0,
                 color=(20, 20, 20), width: int = 8, flip: bool = False) -> None:
    """Draws one stick figure onto a PIL ImageDraw canvas.

    flip=True mirrors the figure horizontally around `root` (for facing
    screen-left instead of the default screen-right-ish neutral facing).
    """
    if flip:
        pose = dict(pose)
        for k in ("spine_angle", "L_upper_arm_angle", "L_forearm_angle",
                   "R_upper_arm_angle", "R_forearm_angle",
                   "L_thigh_angle", "L_shin_angle", "R_thigh_angle", "R_shin_angle"):
            pose[k] = 180 - pose[k]

    j = solve(pose, root, scale)

    def line(a, b):
        draw.line([a, b], fill=color, width=width, joint="curve")

    def dot(p, r):
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)

    # Legs (drawn first so torso/arms overlap them at the hip, like clothing)
    line(j["hip"], j["L_knee"]); line(j["L_knee"], j["L_foot"])
    line(j["hip"], j["R_knee"]); line(j["R_knee"], j["R_foot"])
    # Torso
    line(j["hip"], j["shoulder"])
    # Arms
    line(j["shoulder"], j["L_elbow"]); line(j["L_elbow"], j["L_hand"])
    line(j["shoulder"], j["R_elbow"]); line(j["R_elbow"], j["R_hand"])
    # Joints (small dots so elbows/knees/hands read cleanly at the seams)
    for p in (j["hip"], j["shoulder"], j["L_elbow"], j["R_elbow"],
              j["L_knee"], j["R_knee"], j["L_hand"], j["R_hand"],
              j["L_foot"], j["R_foot"]):
        dot(p, width * 0.42)
    # Head: outline circle, not filled, so the face reads as a head not a blob
    hc, hr = j["head_center"], j["head_r"]
    draw.ellipse([hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr],
                 outline=color, width=width)
