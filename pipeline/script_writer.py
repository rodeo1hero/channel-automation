"""Stage 2: turn a topic into a full scene-by-scene script + visual prompts."""
import json

from .ideas import ANTHROPIC_MODEL
from .utils import DRY_RUN, load_channel_config, log

PROMPT_TEMPLATE = """You are the writer for a YouTube video essay channel.

Niche: {niche}
Tone: {tone}
Target length: ~{minutes} minutes spoken ({words} words approx, at ~150 wpm)

Topic: {title}
Angle: {angle}

Write the full narration script broken into scenes (10-25 seconds of narration each).
For each scene provide:
- "narration": the exact words to be spoken (no stage directions inside this text)
- "visual_prompt": a concrete, literal description of what should be shown on screen
  for this scene (this becomes an AI image-generation prompt, so be specific and visual,
  not abstract)

Also provide a punchy YouTube "title" (different phrasing than the working title is fine)
and a one-paragraph "description" for the video.

Respond as JSON only, matching exactly this shape:
{{
  "title": "...",
  "description": "...",
  "scenes": [
    {{"narration": "...", "visual_prompt": "..."}},
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
            "scenes": [
                {
                    "narration": "Every year, thousands of people watch this and think it's ordinary.",
                    "visual_prompt": "wide establishing shot, muted colors, cinematic",
                },
                {
                    "narration": "But underneath, there's a whole hidden system at work.",
                    "visual_prompt": "close-up detail shot revealing mechanism, dramatic lighting",
                },
            ],
        }

    log(f"Writing script for '{topic['title']}'")
    prompt = PROMPT_TEMPLATE.format(
        niche=config["niche"],
        tone=config["tone"],
        minutes=config["target_length_minutes"],
        words=words,
        title=topic["title"],
        angle=topic.get("angle", ""),
    )
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    return json.loads(text)
