"""Named pose library. Each pose is a dict of the joint angles defined in
rig.POSE_FIELDS; full_pose() fills in anything omitted from DEFAULT_POSE
(a relaxed standing pose), so a pose only needs to specify what differs.

Angle convention (see rig.py): 0=right, 90=down, -90=up, 180=left.
"""
from .rig import full_pose, DEFAULT_POSE

STAND = full_pose({})

# --- Walk cycle: two alternating contact poses, held/blended by actions.py ---
WALK_A = full_pose({
    "spine_angle": -93,
    "R_thigh_angle": 55, "R_shin_angle": 72,      # right leg forward
    "L_thigh_angle": 128, "L_shin_angle": 112,    # left leg trailing back
    "L_upper_arm_angle": 68, "L_forearm_angle": 78,    # left arm forward (opposite leg)
    "R_upper_arm_angle": 128, "R_forearm_angle": 122,  # right arm back
    "hip_y_offset": 6,
})
WALK_B = full_pose({
    "spine_angle": -93,
    "L_thigh_angle": 55, "L_shin_angle": 72,      # left leg forward
    "R_thigh_angle": 128, "R_shin_angle": 112,    # right leg trailing back
    "R_upper_arm_angle": 68, "R_forearm_angle": 78,
    "L_upper_arm_angle": 128, "L_forearm_angle": 122,
    "hip_y_offset": 6,
})
WALK_MID = STAND  # brief passing-through-neutral contact pose each half-step

RUN_A = full_pose({
    "spine_angle": -80,
    "R_thigh_angle": 30, "R_shin_angle": 60,
    "L_thigh_angle": 150, "L_shin_angle": 155,
    "L_upper_arm_angle": 40, "L_forearm_angle": 30,
    "R_upper_arm_angle": 150, "R_forearm_angle": 165,
    "hip_y_offset": 22,
})
RUN_B = full_pose({
    "spine_angle": -80,
    "L_thigh_angle": 30, "L_shin_angle": 60,
    "R_thigh_angle": 150, "R_shin_angle": 155,
    "R_upper_arm_angle": 40, "R_forearm_angle": 30,
    "L_upper_arm_angle": 150, "L_forearm_angle": 165,
    "hip_y_offset": 22,
})

POINT_RIGHT = full_pose({
    "R_upper_arm_angle": -8, "R_forearm_angle": -8,
})
POINT_LEFT = full_pose({
    "L_upper_arm_angle": 188, "L_forearm_angle": 188,
})

WAVE = full_pose({
    "R_upper_arm_angle": -65, "R_forearm_angle": -135,
    "spine_angle": -87,
})

THINK = full_pose({
    "R_upper_arm_angle": 45, "R_forearm_angle": -75,
    "spine_angle": -86,
    "head_bob": 4,
})

SHRUG = full_pose({
    "L_upper_arm_angle": 158, "L_forearm_angle": -95,
    "R_upper_arm_angle": 22, "R_forearm_angle": -85,
    "head_bob": 6,
})

ARMS_CROSSED = full_pose({
    "L_upper_arm_angle": 55, "L_forearm_angle": 5,
    "R_upper_arm_angle": 125, "R_forearm_angle": 175,
})

SIT = full_pose({
    "L_thigh_angle": 8, "L_shin_angle": 100,
    "R_thigh_angle": 8, "R_shin_angle": 100,
    "L_upper_arm_angle": 95, "L_forearm_angle": 95,
    "R_upper_arm_angle": 85, "R_forearm_angle": 85,
    "hip_y_offset": -34,
})

SURPRISED = full_pose({
    "L_upper_arm_angle": -128, "L_forearm_angle": -100,
    "R_upper_arm_angle": -52, "R_forearm_angle": -80,
    "hip_y_offset": 14,
    "head_bob": 5,
})

CELEBRATE = SURPRISED  # arms-up pose reused for "celebrate" beats

EXPLAIN = full_pose({
    "L_upper_arm_angle": 142, "L_forearm_angle": 112,
    "R_upper_arm_angle": 38, "R_forearm_angle": 68,
})

NOD_DOWN = full_pose({"head_bob": -6})

# Registry used by actions.py / script_writer validation.
POSES = {
    "stand": STAND,
    "walk_a": WALK_A,
    "walk_b": WALK_B,
    "walk_mid": WALK_MID,
    "run_a": RUN_A,
    "run_b": RUN_B,
    "point_right": POINT_RIGHT,
    "point_left": POINT_LEFT,
    "wave": WAVE,
    "think": THINK,
    "shrug": SHRUG,
    "arms_crossed": ARMS_CROSSED,
    "sit": SIT,
    "surprised": SURPRISED,
    "celebrate": CELEBRATE,
    "explain": EXPLAIN,
    "nod_down": NOD_DOWN,
}
