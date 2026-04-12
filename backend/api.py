"""
backend/api.py

Drift Zero unified API — rogue anomaly events and conjunction events,
each enriched with an OpenAI-generated plain-English threat summary.

Endpoints
---------
  GET /api/rogue/events
  GET /api/conjunctions/{norad_id}?min_risk=0&limit=20

Environment
-----------
  OPENAI_API_KEY      — required for OpenAI summaries
  SPACETRACK_EMAIL / SPACETRACK_PASSWORD — required for Shield pipeline
"""

import os
import time
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv

from run_rogue import run
from backend.shield.main import run_pipeline

load_dotenv()

log = logging.getLogger(__name__)

app = FastAPI(title="Drift Zero API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODEL = "gpt-4o-mini"

# ── Prompt builders ───────────────────────────────────────────────────────────

def _rogue_prompt(e) -> str:
    features = ", ".join(e.anomalous_features) if e.anomalous_features else "none"
    return (
        "You are a space domain awareness analyst writing concise alerts for an "
        "operator dashboard. Summarise this anomaly event in 2-3 sentences of plain "
        "English. Be specific, include the key numbers, and state the threat level "
        "clearly. Do not use bullet points or headers.\n\n"
        f"NORAD ID: {e.norad_id}\n"
        f"Epoch: {e.epoch}\n"
        f"Severity: {e.severity}\n"
        f"Composite score: {e.composite_score:.3f} (0–1 scale)\n"
        f"Z-score max: {e.z_score_max:.2f}σ\n"
        f"IsolationForest score: {e.iso_score:.3f}\n"
        f"Proximity flag (close CDM event < 50 km): {e.proximity_flag}\n"
        f"Intent label (rule-based): {e.intent_label}\n"
        f"Anomalous features: {features}"
    )


def _conjunction_prompt(e: dict) -> str:
    primary = e["primary"]
    secondary = e["secondary"]
    return (
        "You are a space domain awareness analyst writing concise alerts for an "
        "operator dashboard. Summarise this conjunction event in 2-3 sentences of "
        "plain English. Be specific, include the key numbers, and state whether "
        "operator action is warranted. Do not use bullet points or headers.\n\n"
        f"Primary: {primary['name']} (NORAD {primary['norad_id']}, "
        f"{primary.get('object_type', 'UNKNOWN')})\n"
        f"Secondary: {secondary['name']} (NORAD {secondary['norad_id']}, "
        f"{secondary.get('object_type', 'UNKNOWN')})\n"
        f"Time of closest approach: {e['tca_utc']}\n"
        f"Miss distance: {e['miss_distance_km']:.4f} km\n"
        f"Relative velocity: {e['relative_velocity_km_s']:.3f} km/s\n"
        f"Collision probability: {e['collision_probability']:.3e}\n"
        f"Risk score: {e['risk_score']:.1f} / 100\n"
        f"Data confidence: {e.get('confidence', 'unknown')}\n"
        f"Kp index: {e.get('kp_index', 'N/A')}"
    )


# ── OpenAI call ───────────────────────────────────────────────────────────────

def _summarise(prompt: str) -> str | None:
    """
    Send prompt to OpenAI and return the response text.
    Returns None on any failure so the calling endpoint still responds.
    """
    try:
        msg = _openai.chat.completions.create(
            model=_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("OpenAI summary failed: %s", exc)
        return None


# ── Result caches ─────────────────────────────────────────────────────────────
# Both pipelines are expensive (Space-Track fetches + TCA/ML + Claude calls).
# Cache results for 30 minutes so each pipeline runs at most twice per hour.

_CACHE_TTL = 30 * 60   # seconds
_CLAUDE_SUMMARY_LIMIT = 10   # only call Claude for the N most severe events per pipeline

_rogue_cache: list | None = None
_rogue_cache_time: float = 0.0

# Shield cache is keyed by norad_id so different satellites don't collide.
_shield_cache: dict[int, list] = {}
_shield_cache_time: dict[int, float] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/rogue/events")
def get_rogue_events():
    """
    Run the Rogue anomaly pipeline and return all SUSPICIOUS / ADVERSARIAL
    events. Results are cached for 30 minutes. Claude summaries are generated
    only for the top-10 events by composite score to avoid rate limits.
    """
    global _rogue_cache, _rogue_cache_time

    if _rogue_cache is not None and (time.time() - _rogue_cache_time) < _CACHE_TTL:
        log.info("Returning cached rogue events (%d)", len(_rogue_cache))
        return _rogue_cache

    flagged = run(norad_ids=[25544, 48274, 44713, 28190], days=30)

    # Sort descending by composite score so the most critical events get summaries
    flagged_sorted = sorted(flagged, key=lambda e: e.composite_score, reverse=True)

    result = []
    for i, e in enumerate(flagged_sorted):
        summary = _summarise(_rogue_prompt(e)) if i < _CLAUDE_SUMMARY_LIMIT else None
        result.append({
            "norad_id":           e.norad_id,
            "epoch":              str(e.epoch),
            "severity":           e.severity,
            "composite_score":    round(e.composite_score, 3),
            "z_score_max":        round(e.z_score_max, 3),
            "iso_score":          round(e.iso_score, 3),
            "proximity_flag":     e.proximity_flag,
            "anomalous_features": e.anomalous_features,
            "intent_label":       e.intent_label,
            "description":        e.description,
            "summary":            summary,
        })

    _rogue_cache = result
    _rogue_cache_time = time.time()
    return result


@app.get("/api/conjunctions/{norad_id}")
def get_conjunctions(
    norad_id: int,
    min_risk: float = Query(default=0.0, ge=0.0, le=100.0),
    limit:    int   = Query(default=20,  ge=1,   le=500),
):
    """
    Run the Shield conjunction pipeline for a satellite and return events
    above the risk threshold, each with a Claude-generated threat summary.
    Results are cached per NORAD ID for 30 minutes.
    """
    now = time.time()
    if (
        norad_id in _shield_cache
        and (now - _shield_cache_time.get(norad_id, 0)) < _CACHE_TTL
    ):
        log.info("Returning cached shield events for NORAD %d (%d)", norad_id, len(_shield_cache[norad_id]))
        cached = _shield_cache[norad_id]
        filtered = [e for e in cached if e["risk_score"] >= min_risk][:limit]
        return {
            "norad_id":       norad_id,
            "total_matching": len(filtered),
            "returned":       len(filtered),
            "events":         filtered,
        }

    try:
        events = run_pipeline(norad_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Add Claude summaries to the top N events only
    enriched = []
    for i, e in enumerate(events):
        summary = _summarise(_conjunction_prompt(e)) if i < _CLAUDE_SUMMARY_LIMIT else None
        enriched.append({**e, "summary": summary})

    _shield_cache[norad_id] = enriched
    _shield_cache_time[norad_id] = time.time()

    filtered = [e for e in enriched if e["risk_score"] >= min_risk][:limit]
    return {
        "norad_id":       norad_id,
        "total_matching": len(filtered),
        "returned":       len(filtered),
        "events":         filtered,
    }
