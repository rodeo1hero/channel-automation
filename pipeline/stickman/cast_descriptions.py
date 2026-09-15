"""Plain-English pose descriptions for secondary/supporting "cast" characters (see
pipeline/cast_gen.py) -- the temporary characters the narrator interacts with in a scene
(a tax collector, a guard, a merchant, ...). Deliberately a much smaller set than the
narrator's own pose_descriptions.py: cast members appear briefly, so a handful of
generic interaction poses covers every archetype rather than a full gesture library.

All of these are generated together in a single grid-sheet call per (archetype, outfit)
-- see cast_gen.ensure_cast_sprites -- since none of them get anywhere near the screen
time that would justify the narrator's "core" one-per-call treatment."""

CAST_POSE_DESCRIPTIONS = {
    "stand": ("standing relaxed, neutral calm expression, arms at the sides, facing "
              "forward -- the character's default resting pose"),
    "walk_a": ("mid-stride walking to the right: right leg forward and bent, left leg "
               "trailing back, arms swinging naturally in opposition to the legs"),
    "walk_b": ("mid-stride walking to the right: left leg forward and bent, right leg "
               "trailing back, arms swinging naturally in opposition to the legs"),
    "gesture_talk": ("standing, actively speaking -- mouth open mid-word, one hand raised "
                      "near chest height as if making a point, engaged expressive "
                      "eyebrows"),
    "point": ("standing, pointing one arm straight out to the side at shoulder height, "
              "assertive focused expression"),
    "offer": ("standing, one arm extended straight forward with the palm up as if "
              "demanding or presenting something to whoever they're facing, direct "
              "expectant expression"),
    "refuse": ("standing with arms crossed tightly over the chest, or pulling something "
               "protectively close to the body, dismissive/defensive expression, chin "
               "slightly raised"),
    "shocked": ("standing, both hands raised near the face, eyes wide and mouth open in "
                "surprise or alarm"),
}

# All cast poses are "long tail" -- batched into one grid-sheet call per (archetype,
# outfit) rather than split into a core/long-tail tier like the narrator's poses.
CAST_POSE_NAMES = sorted(CAST_POSE_DESCRIPTIONS)
