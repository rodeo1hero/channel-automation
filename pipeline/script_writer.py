"""Stage 2: turn a topic into a full scene-by-scene script + stick-figure
staging directions (which actions the character performs, and a background
scene description for the AI-generated backdrop) for visuals.py."""
import json

from .cast_gen import CAST_ROLES
from .character_gen import OUTFITS
from .ideas import ANTHROPIC_MODEL
from .stickman.actions import ACTION_NAMES
from .stickman.cast_descriptions import CAST_POSE_NAMES
from .utils import DRY_RUN, load_channel_config, log

PROMPT_TEMPLATE = """You are the writer for a YouTube video essay channel that
uses simple animated stick-figure storytelling (think hand-drawn explainer
videos) instead of live footage. A single recurring stick-figure character
(same face and build every time, don't describe their face/body) acts out
each scene in front of an AI-generated background illustration, wearing one
outfit for the whole video.

Niche: {niche}
Tone: {tone}
Target length: ~{minutes} minutes spoken ({words} words approx, at ~150 wpm)

Topic: {title}
Angle: {angle}

First choose an "outfit" for the character for this whole video, chosen ONLY from this
exact list (key: what it looks like): {outfit_options}
Pick whichever best matches this video's topic/era/setting (e.g. "historical" for an
ancient-world topic, "business" or "financial" for an economics topic, "standard" when
nothing else fits better). The whole video uses this one outfit throughout.

Then write the full narration script broken into scenes (6-10 seconds of narration each --
favor MORE, SHORTER scenes over fewer long ones: a new scene means a new background and a
fresh beat/action for the character, so more scenes per minute keeps the visuals cutting
and changing at a faster, punchier pace instead of sitting on one backdrop for a long
stretch of narration).
For each scene provide:
- "narration": the exact words to be spoken (no stage directions inside this text)
- "actions": a list of 1-3 action names describing what the stick figure does during
  this scene, chosen ONLY from this exact list: {action_names}
  (walk_left/walk_right/run_left/run_right move the figure across the frame; the rest
  are in-place gestures/poses, several of which include props like a desk, a laptop, or
  an armchair baked into that pose's sprite. Pick actions that physically match the
  narration's beat AND its emotional tone -- e.g. "point_right" when gesturing at
  something, "think" for a reflective line, "walk_right" for a scene about movement or
  progress, "surprised"/"celebrate" for a twist or payoff, "arms_crossed" for a skeptical
  or critical beat, "reading_desk"/"laptop" for a research-y line, "relaxed_chair" for a
  laid-back aside. There's also a money/business set (holding_money, counting_money,
  looking_cash, gold_coin, stock_up, stock_down, calculator, financial_report,
  laptop_stand, handshake, business_deal, adjust_tie, money_celebrate, bankrupt,
  rich_lifestyle, broke) for finance-adjacent topics -- "handshake" and "business_deal"
  render a second, plain generic figure alongside our character (a deal/negotiation
  beat), the rest are our character alone with a prop. Don't just default to "idle"
  every time -- vary it scene to scene, and let the pose carry the character's reaction
  to what's being said.)
- "background_prompt": a concrete, literal, visual description of the ENVIRONMENT/SETTING
  for this scene, for an AI image model to generate as the backdrop (e.g. "a medieval
  battlefield at dawn, tents and banners in the distance" or "a cluttered home office with
  a desk and bookshelf"). Describe ONLY the setting/environment and props in it -- do NOT
  describe any person or character, since the character is composited in separately. Keep
  it consistent with the scene's narration and the chosen outfit's era/setting.
- "cast" (OPTIONAL, omit or use an empty list for most scenes): a list of entries for up
  to 2 supporting characters (one per "side") who appear in this scene and briefly
  interact with the narrator -- use this to turn a scene into a short exchange instead of
  a lecture (e.g. a tax collector demanding payment, a merchant haggling, a guard
  blocking the way) rather than defaulting to it every scene. If a character speaks more
  than once, give them one entry PER LINE (same "archetype" and "side", different
  "dialogue"/"start"/"end") rather than cramming multiple lines into one "dialogue" --
  the character stays visible the whole scene either way, only the bubble timing
  changes. Each entry:
  {{"archetype": "...", "pose": "...", "side": "left"|"right", "dialogue": "...",
    "start": 0.0, "end": 3.0}}
  - "archetype": chosen ONLY from this exact list (key: who they represent):
    {cast_role_options}
    These are reusable roles, not one-off characters -- they'll automatically be dressed
    to match this video's chosen outfit/era (e.g. "official" becomes a Roman tax
    collector in a "historical" outfit, a modern bureaucrat in a "business" outfit), so
    just pick the role, never describe their clothing.
  - "pose": chosen ONLY from this exact list: {cast_pose_names}
    (gesture_talk/point/offer/refuse/shocked are reaction/interaction poses; stand is
    neutral; walk_a/walk_b are a mid-stride walk-cycle frame, for a brief entrance.)
  - "side": "left" or "right" -- which side of the frame they stand on. If a scene has
    cast members, avoid walk_left/walk_right/run_left/run_right in that scene's own
    "actions" (the narrator instead stays on the opposite side and gestures in place),
    since a walking narrator can cross through a fixed cast position.
  - "dialogue": a SHORT line (under ~8 words) shown as an on-screen speech bubble --
    this is text, not spoken audio, so keep exchanges snappy (one or two short lines per
    cast member, not paragraphs). Omit "dialogue" (or leave it empty) for a cast member
    who's just reacting silently via pose/expression.
  - "start"/"end" (OPTIONAL, seconds from the start of THIS scene, default: the whole
    scene): the window during which THIS LINE's speech bubble is shown. The cast member
    themselves stays visible for the whole scene once they appear (never pops in and
    out) -- start/end only controls the bubble, so give each line of a back-and-forth
    its own non-overlapping start/end (e.g. line 1 at 0.0-2.0, line 2 at 2.2-4.5) as
    separate entries with the same "archetype" and "side", one per line.

Also provide a punchy YouTube "title" (different phrasing than the working title is fine)
and a one-paragraph "description" for the video.

Respond as JSON only, matching exactly this shape:
{{
  "title": "...",
  "description": "...",
  "outfit": "...",
  "scenes": [
    {{"narration": "...", "actions": ["...", "..."], "background_prompt": "...",
      "cast": [{{"archetype": "...", "pose": "...", "side": "right", "dialogue": "...",
                 "start": 0.0, "end": 2.5}}]}},
    ...
  ]
}}
"""


def write_script(topic: dict, client=None) -> dict:
    config = load_channel_config()
    words = config["target_length_minutes"] * 150

    if DRY_RUN or client is None:
        log(f"Writing script for '{topic['title']}' (mock)")
        return {
            "title": topic["title"],
            "description": f"A closer look at: {topic.get('angle', topic['title'])}",
            "outfit": "standard",
            "scenes": [
                {
                    "narration": "Every year, thousands of people watch this and think it's ordinary.",
                    "actions": ["walk_right", "idle"],
                    "background_prompt": "a busy city street with shops and pedestrians",
                },
                {
                    "narration": "But underneath, there's a whole hidden system at work.",
                    "actions": ["think", "explain"],
                    "background_prompt": "a simple diagram-like room with large gears on the wall",
                    "cast": [
                        {"archetype": "official", "pose": "offer", "side": "right",
                         "dialogue": "Taxes. For everything.", "start": 0.5, "end": 3.0},
                    ],
                },
            ],
        }

    log(f"Writing script for '{topic['title']}'")
    outfit_options = "; ".join(f'"{k}" ({v})' for k, v in OUTFITS.items())
    cast_role_options = "; ".join(f'"{k}" ({v})' for k, v in CAST_ROLES.items())
    prompt = PROMPT_TEMPLATE.format(
        niche=config["niche"],
        tone=config["tone"],
        minutes=config["target_length_minutes"],
        words=words,
        title=topic["title"],
        angle=topic.get("angle", ""),
        action_names=", ".join(ACTION_NAMES),
        outfit_options=outfit_options,
        cast_role_options=cast_role_options,
        cast_pose_names=", ".join(CAST_POSE_NAMES),
    )
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    script = json.loads(text)

    # Defensive cleanup: the renderer already falls back gracefully on bad
    # values, but sanitize here too so a script with a typo'd action/outfit
    # name doesn't quietly break without anyone noticing.
    if script.get("outfit") not in OUTFITS:
        log(f"Warning: unknown/missing outfit {script.get('outfit')!r} from script, defaulting to 'standard'")
        script["outfit"] = "standard"
    for scene in script.get("scenes", []):
        bad_actions = [a for a in scene.get("actions", []) if a not in ACTION_NAMES]
        if bad_actions:
            log(f"Warning: dropping unknown action name(s) from script: {bad_actions}")
            scene["actions"] = [a for a in scene.get("actions", []) if a in ACTION_NAMES] or ["idle"]
        scene["cast"] = _sanitize_cast(scene.get("cast"))

    return script


MAX_CAST_ENTRIES_PER_SCENE = 4  # up to 2 sides x up to 2 dialogue lines each


def _sanitize_cast(cast_list) -> list:
    """Drops any cast entry with an unknown archetype/pose or missing archetype, clamps
    side/dialogue to sane values, and caps the TOTAL entry count (not distinct
    characters -- a single cast member speaking twice is 2 entries with the same
    archetype/side, see ai_scene_renderer._active_cast_for_side) so a malformed script
    response degrades gracefully instead of crashing the render."""
    if not isinstance(cast_list, list):
        return []
    cleaned = []
    for entry in cast_list:
        if not isinstance(entry, dict):
            continue
        archetype = entry.get("archetype")
        if archetype not in CAST_ROLES:
            log(f"Warning: dropping cast entry with unknown archetype {archetype!r}")
            continue
        pose = entry.get("pose")
        if pose not in CAST_POSE_NAMES:
            pose = "stand"
        side = entry.get("side") if entry.get("side") in ("left", "right") else "right"
        dialogue = entry.get("dialogue")
        dialogue = dialogue.strip() if isinstance(dialogue, str) else None
        clean = {"archetype": archetype, "pose": pose, "side": side}
        if dialogue:
            clean["dialogue"] = dialogue
        for key in ("start", "end"):
            try:
                if entry.get(key) is not None:
                    clean[key] = float(entry[key])
            except (TypeError, ValueError):
                pass
        cleaned.append(clean)
        if len(cleaned) == MAX_CAST_ENTRIES_PER_SCENE:
            break
    return cleaned
