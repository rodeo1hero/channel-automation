"""Stage 1: pick (or generate) the next video topic."""
import json
import os

from .utils import DRY_RUN, load_channel_config, load_history, log, pop_next_topic

# Check https://docs.claude.com/en/docs/about-claude/models for the current model list —
# pin an exact model string here (or override via ANTHROPIC_MODEL) rather than "latest".
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")


PROMPT_TEMPLATE = """You generate video topics for a YouTube channel.

Channel niche: {niche}
Tone: {tone}

Topics already covered (do not repeat these or close variants):
{history}

Propose ONE new topic that fits the niche. Respond as JSON only, matching this shape:
{{"title": "...", "angle": "one or two sentences describing the specific hook/mechanism"}}
"""


def get_next_topic(client=None) -> dict:
    """Returns {"title": ..., "angle": ...}. Pulls from the queue first;
    if the queue is empty, asks Claude to propose a fresh, non-repeated topic.
    """
    topic = pop_next_topic()
    if topic:
        log(f"Using queued topic: {topic['title']}")
        return topic

    log("Topic queue empty — asking Claude to propose a new topic")
    config = load_channel_config()
    history = load_history()
    past_titles = "\n".join(
        f"- {h.get('published_title', h.get('topic_title', '(untitled)'))}" for h in history
    ) or "(none yet)"

    if DRY_RUN or client is None:
        return {
            "title": "[DRY RUN] Why traffic jams appear out of nowhere",
            "angle": "Emergent behavior in traffic flow, no accident required.",
        }

    prompt = PROMPT_TEMPLATE.format(
        niche=config["niche"], tone=config["tone"], history=past_titles
    )
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip potential markdown code fences
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    return json.loads(text)