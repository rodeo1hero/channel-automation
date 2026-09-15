"""Turns a scene's action list (e.g. [("walk_right", 1.5), ("point_right", 2.0)])
into a per-frame stream of (pose, root_x, flip) that scene_renderer.py draws.

This is the only file that needs to change to add a new action name; keep
ACTION_NAMES in sync with whatever script_writer.py is allowed to emit.
"""
import math

from .poses import (
    STAND, WALK_A, WALK_B, WALK_MID, RUN_A, RUN_B, POSES,
)
from .rig import POSE_FIELDS

# Names script_writer.py may use in a scene's "actions" list.
WALK_RUN_ACTIONS = {"walk_right", "walk_left", "run_right", "run_left"}
HOLD_ACTIONS = {
    "idle", "point_right", "point_left", "wave", "think", "shrug",
    "arms_crossed", "sit", "surprised", "celebrate", "explain", "nod",
    "reading_desk", "laptop", "relaxed_chair",
    # Business & money set
    "holding_money", "counting_money", "looking_cash", "gold_coin",
    "stock_up", "stock_down", "calculator", "financial_report",
    "laptop_stand", "handshake", "business_deal", "adjust_tie",
    "money_celebrate", "bankrupt", "rich_lifestyle", "broke",
}
ACTION_NAMES = sorted(WALK_RUN_ACTIONS | HOLD_ACTIONS)

_HOLD_POSE_FOR = {
    "idle": STAND,
    "point_right": POSES["point_right"],
    "point_left": POSES["point_left"],
    "wave": POSES["wave"],
    "think": POSES["think"],
    "shrug": POSES["shrug"],
    "arms_crossed": POSES["arms_crossed"],
    "sit": POSES["sit"],
    "surprised": POSES["surprised"],
    "celebrate": POSES["celebrate"],
    "explain": POSES["explain"],
    "nod": POSES["nod_down"],
}

WALK_SPEED = 150   # px/sec
RUN_SPEED = 330
WALK_STEP = 0.55   # seconds per quarter-cycle (A -> mid -> B -> mid)
RUN_STEP = 0.30
EASE_SECONDS = 0.3
SWAY_AMPLITUDE = 1.6   # degrees, subtle idle breathing motion
SWAY_PERIOD = 2.6      # seconds per sway cycle


def lerp_pose(a: dict, b: dict, t: float) -> dict:
    t = max(0.0, min(1.0, t))
    return {k: a[k] + (b[k] - a[k]) * t for k in POSE_FIELDS}


def _walk_cycle_pose(local_t: float, running: bool):
    step = RUN_STEP if running else WALK_STEP
    cycle = [RUN_A, WALK_MID, RUN_B, WALK_MID] if running else [WALK_A, WALK_MID, WALK_B, WALK_MID]
    phase = (local_t / step) % len(cycle)
    idx = int(phase) % len(cycle)
    frac = phase - int(phase)
    return lerp_pose(cycle[idx], cycle[(idx + 1) % len(cycle)], frac)


def generate_frames(action_list, fps: int, width: int, start_x: float, margin: float = 200):
    """Yields (pose, root_x, flip) once per frame across the whole scene.

    action_list: list of (action_name, duration_seconds). Unknown action
    names are treated as "idle" so a bad Claude response degrades gracefully
    instead of crashing a whole run.
    """
    root_x = start_x
    flip = False
    current_pose = dict(STAND)
    hold_start_pose = dict(STAND)
    hold_start_time = 0.0
    t_in_scene = 0.0

    for action, duration in action_list:
        duration = max(0.05, float(duration))
        n_frames = max(1, round(duration * fps))
        action = action if action in (WALK_RUN_ACTIONS | HOLD_ACTIONS) else "idle"

        if action in WALK_RUN_ACTIONS:
            running = action.startswith("run")
            moving_right = action.endswith("right")
            speed = RUN_SPEED if running else WALK_SPEED
            start_x_local = root_x
            for i in range(n_frames):
                local_t = i / fps
                pose = _walk_cycle_pose(local_t, running)
                dx = speed * local_t * (1 if moving_right else -1)
                nx = start_x_local + dx
                nx = max(margin, min(width - margin, nx))
                flip = not moving_right
                current_pose = pose
                root_x = nx
                yield (pose, root_x, flip)
            hold_start_pose = current_pose
            hold_start_time = t_in_scene + duration
            flip = False  # gestures always face the viewer, regardless of last walk direction
        else:
            target = _HOLD_POSE_FOR.get(action, STAND)
            for i in range(n_frames):
                local_t = i / fps
                since_hold_start = t_in_scene + local_t - hold_start_time
                ease = min(1.0, since_hold_start / EASE_SECONDS) if EASE_SECONDS > 0 else 1.0
                pose = lerp_pose(hold_start_pose, target, ease)
                sway = SWAY_AMPLITUDE * math.sin(2 * math.pi * (t_in_scene + local_t) / SWAY_PERIOD)
                pose = dict(pose)
                pose["spine_angle"] += sway
                pose["head_bob"] += sway * 0.8
                current_pose = pose
                yield (pose, root_x, False)

        t_in_scene += duration


# --- Discrete pose-name variant, for the AI-rendered sprite renderer -------
# Sprites are pre-rendered raster images (see scripts/generate_character.py),
# so unlike generate_frames() above there's no continuous joint-angle
# blending between them -- each frame just picks the nearest keyframe pose
# *name* (plus a small vertical bob for idle/walk motion) and the renderer
# pastes that sprite image.

_SPRITE_NAME_FOR = {k: ("stand" if k == "idle" else k) for k in HOLD_ACTIONS}
BOB_AMPLITUDE = 5  # px, subtle idle/walk vertical bob


def generate_sprite_frames(action_list, fps: int, width: int, start_x: float, margin: float = 200):
    """Yields (pose_name, root_x, y_offset, flip) once per frame. pose_name is
    a key into the sprite sheet (assets/character/<pose_name>.png)."""
    root_x = start_x
    t_in_scene = 0.0

    for action, duration in action_list:
        duration = max(0.05, float(duration))
        n_frames = max(1, round(duration * fps))
        action = action if action in (WALK_RUN_ACTIONS | HOLD_ACTIONS) else "idle"

        if action in WALK_RUN_ACTIONS:
            running = action.startswith("run")
            moving_right = action.endswith("right")
            speed = RUN_SPEED if running else WALK_SPEED
            step = RUN_STEP if running else WALK_STEP
            cycle = ["run_a", "stand", "run_b", "stand"] if running else ["walk_a", "stand", "walk_b", "stand"]
            start_x_local = root_x
            for i in range(n_frames):
                local_t = i / fps
                phase = (local_t / step) % len(cycle)
                name = cycle[int(phase) % len(cycle)]
                bob = -BOB_AMPLITUDE * abs(math.sin(math.pi * phase))
                dx = speed * local_t * (1 if moving_right else -1)
                root_x = max(margin, min(width - margin, start_x_local + dx))
                yield (name, root_x, bob, not moving_right)
        else:
            name = _SPRITE_NAME_FOR.get(action, "stand")
            for i in range(n_frames):
                local_t = i / fps
                bob = SWAY_AMPLITUDE * math.sin(2 * math.pi * (t_in_scene + local_t) / SWAY_PERIOD)
                yield (name, root_x, bob, False)

        t_in_scene += duration


def sprite_names_needed_for(action_names) -> set:
    """Given an iterable of action names (as emitted by script_writer.py, or
    read back from a scene's "actions" list), returns the set of sprite
    pose names (assets/character/<outfit>/<name>.png) that rendering them
    will actually require -- used by visuals.py to only generate the poses
    a given script needs, not the whole library, in whatever outfit that
    video is using."""
    needed = set()
    for action in action_names:
        if action not in (WALK_RUN_ACTIONS | HOLD_ACTIONS):
            action = "idle"
        if action in WALK_RUN_ACTIONS:
            needed.update(("run_a", "run_b", "stand") if action.startswith("run") else ("walk_a", "walk_b", "stand"))
        else:
            needed.add(_SPRITE_NAME_FOR.get(action, "stand"))
    return needed
