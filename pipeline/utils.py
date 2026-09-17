"""Shared helpers: config loading, logging, dry-run flag."""
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
ASSETS_DIR = ROOT / "assets"

DRY_RUN = os.environ.get("PIPELINE_DRY_RUN", "0") == "1"


def log(msg: str) -> None:
    prefix = "[DRY RUN] " if DRY_RUN else ""
    print(f"{prefix}{msg}", flush=True)


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def load_channel_config() -> dict:
    return load_yaml(CONFIG_DIR / "channel_config.yaml")


def load_topics_queue() -> list:
    path = CONFIG_DIR / "topics_queue.yaml"
    if not path.exists():
        return []
    data = load_yaml(path)
    return data or []


def pop_next_topic() -> dict | None:
    queue = load_topics_queue()
    if not queue:
        return None
    topic = queue.pop(0)
    save_yaml(CONFIG_DIR / "topics_queue.yaml", queue)
    return topic


def load_history() -> list:
    path = STATE_DIR / "history.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_history(entry: dict) -> None:
    path = STATE_DIR / "history.json"
    history = load_history()
    history.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val and not DRY_RUN:
        sys.exit(f"Missing required environment variable: {name}")
    return val or f"DRY-RUN-{name}"


def merge_hook_into_opening_scene(scenes: list, hook: str) -> None:
    """Guarantees scene 1's narration opens with `hook`, even if the model didn't
    follow the prompt's "scene 1 opens with the hook, verbatim or near-verbatim"
    instruction. Skips the merge if scene 1 already starts with (a normalized prefix
    of) the hook, so a model that DID comply doesn't get the hook stated twice.
    Shared by script_writer.py (main video) and shorts_writer.py (companion Short),
    since both scripts carry a "hook" field and both need this same guarantee."""
    hook = (hook or "").strip()
    if not hook or not scenes:
        return
    narration = scenes[0].get("narration", "") or ""
    # Compare a short, normalized prefix rather than the whole strings, since the
    # model may rephrase slightly ("near-verbatim") even when it did follow the
    # instruction.
    hook_prefix = hook[:40].strip().lower()
    if hook_prefix and narration.strip().lower().startswith(hook_prefix):
        return
    scenes[0]["narration"] = f"{hook} {narration}".strip()
