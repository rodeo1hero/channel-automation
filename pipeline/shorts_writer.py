"""Companion Shorts stage: turns an already-written main-video script into a
short, vertical "hook" script -- a separate ~20-30s teaser (2-3 scenes) whose
job is to make someone stop scrolling and tap through to the full video, not
to retell or resolve the story itself.

Deliberately reuses the same scene shape (narration/actions/background_prompt)
that script_writer.py produces, so it needs zero changes to voiceover.py,
visuals.py, captions.py, or assemble.py -- those stages already only care
about that shape, not which module wrote it. The main video's own outfit is
passed straight through rather than re-decided, so the Short's narrator (and
any cast) look identical to the main video's -- this is a companion piece for
the SAME character, not a new video with its own look."""
import json

from .ideas import ANTHROPIC_MODEL
from .stickman.actions import ACTION_NAMES
from .utils import DRY_RUN, log, merge_hook_into_opening_scene

TARGET_SECONDS = 25  # midpoint of the ~20-30s target agreed with the user
WORDS_PER_SECOND = 2.5  # ~150 wpm, matching script_writer.py's pacing assumption

PROMPT_TEMPLATE = """You are the writer for a YouTube Shorts account that promotes a
longer video-essay channel. You've already been given the FULL script for the long-form
video below. Your job now is NOT to summarize or retell that video -- it's to write a
separate, self-contained ~{target_seconds}-second vertical hook that makes someone
scrolling Shorts stop and tap through to watch the full video.

The long-form video this Short is promoting:
Title: {main_title}
Description: {main_description}
The video's HOOK claim (its central surprising claim, already used to open the full
video itself): {hook}

Write {target_seconds} seconds of narration (~{target_words} words at ~150 wpm) for the
SAME recurring stick-figure narrator character (same face/build, don't describe it),
broken into 2-3 short scenes (roughly 7-12 seconds of narration each). This is a hook,
not a recap:
- Open Scene 1 with the HOOK claim above, verbatim or near-verbatim -- reuse it as-is
  rather than inventing a different opening claim. The "wait, what?" moment is already
  decided; your job is to make it land in a vertical, fast-cut format.
- Build very briefly (1-2 lines) on why that claim is true or what's at stake.
- End on an explicit, unresolved cliffhanger or open question that the full video
  answers -- something like naming the twist is coming without giving it away. Do NOT
  resolve the hook or state the answer/lesson; that's exactly what should pull someone to
  the full video. Do NOT literally say "link in description" or "full video below" in the
  narration itself -- that's handled separately in the video's description, not spoken.

For each scene provide:
- "narration": the exact words to be spoken (no stage directions inside this text)
- "actions": a list of 1-2 action names describing what the character does during this
  scene, chosen ONLY from this exact list: {action_names}
  (a Short is fast-paced -- prefer punchy reaction poses like surprised/shocked-reading
  as "surprised", point_right/point_left, think, arms_crossed, celebrate over a slow
  walk/run cycle, since there's little time for the character to travel across frame.)
- "background_prompt": a concrete, literal, visual description of the ENVIRONMENT/SETTING
  for this scene (same style as the main video's own background prompts) -- describe
  ONLY the setting/environment and props in it, no people, consistent with the chosen
  outfit's era/setting. This will be generated as a VERTICAL (9:16) image, so favor
  compositions with a clear vertical focal point (e.g. a tall doorway, a single close
  object, a narrow alley) over a wide panorama that would feel empty when cropped tall.

Also provide a short, punchy "title" for the Short itself (can differ from the main
video's title -- more of a hook/question, since Shorts titles work differently from
long-form titles) and a one-sentence "teaser" line (NOT the CTA/link -- just a one-line
teaser of what's coming, the actual link gets appended separately).

Respond as JSON only, matching exactly this shape:
{{
  "title": "...",
  "teaser": "...",
  "scenes": [
    {{"narration": "...", "actions": ["...", "..."], "background_prompt": "..."}},
    ...
  ]
}}
"""


def _mock_short_script(main_script: dict) -> dict:
    hook = main_script.get("hook") or "Everyone thinks this is a good thing. It isn't."
    return {
        "title": f"The dark side of: {main_script.get('title', 'this topic')}",
        "teaser": "It's not what you think.",
        "scenes": [
            {
                "narration": hook,
                "actions": ["surprised", "point_right"],
                "background_prompt": "a narrow dramatic alleyway with tall walls on either side",
            },
            {
                "narration": "But here's the part nobody talks about...",
                "actions": ["think"],
                "background_prompt": "a single tall closed door lit from behind, vertical composition",
            },
        ],
    }


def write_hook_script(main_script: dict, client=None) -> dict:
    """main_script is the dict returned by script_writer.write_script() for the video
    this Short is promoting -- title/description/scenes[0].narration are read from it
    for context, but the Short gets its own separate narration/scenes, never a slice of
    the main video's own audio (a cut-down clip of the full narration reads as an ad for
    itself and loses the "hook" framing; a purpose-written hook is what the user asked
    for over the cheaper auto-extract option)."""
    target_words = round(TARGET_SECONDS * WORDS_PER_SECOND)

    # Reuse the main video's own hook claim rather than asking Claude to derive (and
    # potentially invent) a second one from context -- see merge_hook_into_opening_scene.
    # Falls back to the main video's scene-1 narration for a main script written before
    # the "hook" field existed.
    hook = main_script.get("hook") or ""
    if not hook and main_script.get("scenes"):
        hook = main_script["scenes"][0].get("narration", "")

    if DRY_RUN or client is None:
        log(f"Writing Shorts hook script for '{main_script.get('title')}' (mock)")
        short_script = _mock_short_script(main_script)
    else:
        log(f"Writing Shorts hook script for '{main_script.get('title')}'")
        prompt = PROMPT_TEMPLATE.format(
            target_seconds=TARGET_SECONDS,
            target_words=target_words,
            main_title=main_script.get("title", ""),
            main_description=main_script.get("description", ""),
            hook=hook,
            action_names=", ".join(ACTION_NAMES),
        )
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
        short_script = json.loads(text)

    # Same defensive cleanup as script_writer.write_script() -- a bad action name from
    # Claude shouldn't crash the whole Short, just fall back to something safe.
    for scene in short_script.get("scenes", []):
        bad_actions = [a for a in scene.get("actions", []) if a not in ACTION_NAMES]
        if bad_actions:
            log(f"Warning: dropping unknown action name(s) from Shorts script: {bad_actions}")
            scene["actions"] = [a for a in scene.get("actions", []) if a in ACTION_NAMES] or ["idle"]

    # Enforce "scene 1 opens on the reused hook" in code too, same rationale as the
    # main video's script_writer.write_script().
    merge_hook_into_opening_scene(short_script.get("scenes", []), hook)

    return short_script
