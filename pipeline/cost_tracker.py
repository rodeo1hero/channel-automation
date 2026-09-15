"""Tracks estimated API spend across every paid call the pipeline makes
(Replicate character sprites, Replicate/FLUX backgrounds, Google Cloud TTS,
Anthropic script-writing), so cost is visible per run and cumulatively --
not just guessed at after the fact.

Every entry is an ESTIMATE, not a billed figure pulled from the provider --
none of these APIs return an exact per-call dollar cost in their response,
so PRICING below holds the best figures we have (from provider pricing
pages / prior research) and every record is computed from that. If a
provider's pricing changes, update PRICING and future entries reflect it;
past entries keep whatever rate was in effect when they were recorded.

Ledger lives at state/api_usage.json -- a flat list of records, one per API
call. Append-only, never rewritten, so it survives every run and gives an
exact history of what was called, when, and for which run_id."""
import datetime as dt
import json
from pathlib import Path

from .utils import ROOT, STATE_DIR, log

LEDGER_PATH = STATE_DIR / "api_usage.json"

# Best-known per-call pricing. None of these providers expose the exact
# billed cost of a specific call via API, so these are estimates based on
# each provider's published tier pricing at the quality/model settings this
# pipeline actually uses -- see ARCHITECTURE.md for the research behind them.
PRICING = {
    # gpt-image-2.5-flare on Replicate, "low" quality tier, 1024x1024 --
    # roughly a fifth to a sixth of the "high" tier's ~$0.13/image. Costs the
    # same per API CALL whether it's a single pose or an 8-pose grid sheet
    # (Replicate bills per output image, not per subject drawn in it), which
    # is exactly why grid-batching poses is cheaper per pose, not per call.
    "replicate_character_low": 0.025,   # $/call
    # black-forest-labs/flux-1.1-pro on Replicate, one 16:9 background image.
    "replicate_flux_background": 0.04,  # $/image
    # Google Cloud TTS, Chirp 3: HD voices -- $30 per 1M characters, billed
    # by input character count (this channel's low volume stays within the
    # 1M/month free tier most months; tracked here regardless so real spend
    # is visible once that tier is exceeded).
    "google_tts_chirp3_hd_per_char": 30.0 / 1_000_000,  # $/character
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _load() -> list:
    if not LEDGER_PATH.exists():
        return []
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(entries: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def record(run_id: str, api: str, description: str, cost_usd: float, meta: dict = None) -> None:
    """Appends one ledger entry. api is a PRICING-ish tag (e.g.
    'replicate_character', 'replicate_background', 'google_tts') used for
    grouping in reports -- doesn't have to match a PRICING key exactly, e.g.
    reconstructed/backfilled entries use api + a 'reconstructed': True meta
    flag instead of a live PRICING lookup."""
    entries = _load()
    entries.append({
        "timestamp": _now(),
        "run_id": run_id,
        "api": api,
        "description": description,
        "cost_usd": round(cost_usd, 6),
        "meta": meta or {},
    })
    _save(entries)


def record_replicate_character_call(run_id: str, outfit: str, kind: str, items: list, quality: str = "low") -> None:
    rate = PRICING["replicate_character_low"] if quality == "low" else PRICING["replicate_character_low"] * 5
    record(
        run_id, "replicate_character",
        f"{kind} ({outfit}): {', '.join(items)}",
        rate,
        meta={"outfit": outfit, "kind": kind, "items": items, "quality": quality},
    )


def record_replicate_cast_call(run_id: str, archetype: str, outfit: str, kind: str, items: list,
                                quality: str = "low") -> None:
    """Same model/pricing as record_replicate_character_call (identical Replicate call
    shape), tracked under its own 'replicate_cast' tag so the cost report can show
    secondary/supporting-cast spend separately from the main narrator character."""
    rate = PRICING["replicate_character_low"] if quality == "low" else PRICING["replicate_character_low"] * 5
    record(
        run_id, "replicate_cast",
        f"{archetype}/{kind} ({outfit}): {', '.join(items)}",
        rate,
        meta={"archetype": archetype, "outfit": outfit, "kind": kind, "items": items, "quality": quality},
    )


def record_replicate_background_call(run_id: str, scene_index: int, succeeded: bool) -> None:
    record(
        run_id, "replicate_background",
        f"scene {scene_index} background" + ("" if succeeded else " (attempt, later retried)"),
        PRICING["replicate_flux_background"],
        meta={"scene_index": scene_index, "succeeded": succeeded},
    )


def record_google_tts_call(run_id: str, scene_index: int, char_count: int) -> None:
    record(
        run_id, "google_tts",
        f"scene {scene_index} narration ({char_count} chars)",
        char_count * PRICING["google_tts_chirp3_hd_per_char"],
        meta={"scene_index": scene_index, "char_count": char_count},
    )


def run_summary(run_id: str) -> dict:
    entries = [e for e in _load() if e["run_id"] == run_id]
    by_api = {}
    for e in entries:
        by_api[e["api"]] = by_api.get(e["api"], 0.0) + e["cost_usd"]
    total = sum(by_api.values())
    return {"run_id": run_id, "by_api": by_api, "total_usd": total, "n_calls": len(entries)}


def all_time_summary() -> dict:
    entries = _load()
    by_api = {}
    by_run = {}
    for e in entries:
        by_api[e["api"]] = by_api.get(e["api"], 0.0) + e["cost_usd"]
        by_run[e["run_id"]] = by_run.get(e["run_id"], 0.0) + e["cost_usd"]
    total = sum(by_api.values())
    return {"by_api": by_api, "by_run": by_run, "total_usd": total, "n_calls": len(entries)}


def print_run_summary(run_id: str) -> None:
    s = run_summary(run_id)
    log(f"--- API cost for this run ({run_id}) ---")
    for api, cost in sorted(s["by_api"].items(), key=lambda kv: -kv[1]):
        log(f"  {api}: ${cost:.4f}")
    log(f"  TOTAL this run: ${s['total_usd']:.4f} ({s['n_calls']} calls)")
    all_time = all_time_summary()
    log(f"  Cumulative spend to date (all runs): ${all_time['total_usd']:.4f}")
