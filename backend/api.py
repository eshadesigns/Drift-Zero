import os
import time
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import anthropic

from run_rogue import run
from backend.shield.main import (
    run_pipeline as _run_pipeline,
    _conjunction_cache,
    _pipeline_cache,
    compute_maneuvers,
)
from backend.shield.cascade import compute_cascade, LABEL_SLUGS

logger = logging.getLogger("api")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_MODEL = "claude-haiku-4-5-20251001"
_CACHE_TTL = 30 * 60
_SUMMARY_LIMIT = 10

def _summarise(prompt: str) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return ""
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        logger.warning(f"Anthropic summarise failed: {exc}")
        return ""

# ── Rogue cache ────────────────────────────────────────────────────────────────
_rogue_cache: list | None = None
_rogue_cache_time: float = 0.0

# ── Shield TTL cache (separate from shield/main's pipeline state cache) ────────
_shield_cache_time: dict[int, float] = {}


# ── Rogue ──────────────────────────────────────────────────────────────────────

_DEFAULT_ROGUE_NORADS = [59773, 25544, 48274, 44713, 28190]
_ROGUE_DAYS = 180   # must reach Feb 2026 events (~45 days back from demo date)

@app.get("/api/rogue/events")
def get_events(
    norad_ids: list[int] = Query(default=None),
):
    global _rogue_cache, _rogue_cache_time

    # If caller passes specific IDs, bypass cache (targeted query)
    target_ids = norad_ids if norad_ids else _DEFAULT_ROGUE_NORADS
    using_cache = not norad_ids

    now = time.time()
    if using_cache and _rogue_cache is not None and (now - _rogue_cache_time) < _CACHE_TTL:
        logger.info("Rogue: serving from cache")
        return _rogue_cache

    flagged = run(norad_ids=target_ids, days=_ROGUE_DAYS)

    # Sort highest composite score first so the summary budget goes to the most
    # significant events regardless of chronological position in the run output.
    flagged = sorted(flagged, key=lambda e: (e.composite_score, e.z_score_max), reverse=True)

    results = []
    for i, e in enumerate(flagged):
        summary = ""
        if i < _SUMMARY_LIMIT:
            prompt = (
                f"Satellite NORAD {e.norad_id} flagged {e.severity} at epoch {e.epoch}. "
                f"Composite score {e.composite_score:.3f}, z_max {e.z_score_max:.2f}. "
                f"Anomalous features: {e.anomalous_features}. "
                f"Description: {e.description}. "
                "Write a one-sentence plain-English threat summary for a space operations analyst. "
                "Do not use markdown headers or formatting. Write in plain prose only."
            )
            summary = _summarise(prompt)

        results.append({
            "norad_id": e.norad_id,
            "epoch": str(e.epoch),
            "severity": e.severity,
            "composite_score": round(e.composite_score, 3),
            "z_score_max": round(e.z_score_max, 3),
            "anomalous_features": e.anomalous_features,
            "description": e.description,
            "summary": summary,
        })

    if using_cache:
        _rogue_cache = results
        _rogue_cache_time = now
    return results


# ── Shield: conjunctions ───────────────────────────────────────────────────────

@app.get("/api/conjunctions/{norad_id}")
def get_conjunctions(norad_id: int, min_risk: float = 0.0, limit: int = 20):
    now = time.time()
    cached_time = _shield_cache_time.get(norad_id, 0.0)

    if norad_id in _conjunction_cache and (now - cached_time) < _CACHE_TTL:
        logger.info(f"Shield: serving NORAD {norad_id} from cache")
        events = _conjunction_cache[norad_id]
    else:
        try:
            events = _run_pipeline(norad_id=norad_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        # Populate the shared shield caches so /maneuvers and /cascade work
        _conjunction_cache[norad_id] = events
        _shield_cache_time[norad_id] = now

    filtered = [e for e in events if e.get("risk_score", 0) >= min_risk]
    filtered.sort(key=lambda e: e.get("risk_score", 0), reverse=True)
    top = filtered[:limit]

    for i, e in enumerate(top):
        if i >= _SUMMARY_LIMIT:
            break
        if e.get("summary"):
            continue
        prompt = (
            f"Conjunction event: primary NORAD {e.get('primary', {}).get('norad_id')} "
            f"vs secondary NORAD {e.get('secondary', {}).get('norad_id')}. "
            f"TCA: {e.get('tca_utc')}. "
            f"Miss distance: {e.get('miss_distance_km', 0):.2f} km. "
            f"Collision probability: {e.get('collision_probability', 0):.2e}. "
            f"Risk score: {e.get('risk_score', 0):.1f}/100. "
            "Write a one-sentence plain-English summary for a space operations analyst. "
            "Do not use markdown headers or formatting. Write in plain prose only."
        )
        e["summary"] = _summarise(prompt)

    # Return wrapped so frontend can use data.events consistently
    return {"norad_id": norad_id, "events": top}


# ── Shield: maneuver options ───────────────────────────────────────────────────

@app.get("/api/maneuvers/{norad_id}/{event_id}")
def get_maneuvers(norad_id: int, event_id: str):
    events = _conjunction_cache.get(norad_id)
    if events is None:
        raise HTTPException(
            status_code=409,
            detail=f"No data cached for NORAD {norad_id}. Call /api/conjunctions/{norad_id} first.",
        )
    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found.")
    return compute_maneuvers(event)


# ── Shield: cascade analysis ───────────────────────────────────────────────────

@app.get("/api/cascade/{norad_id}/{event_id}/{maneuver_label}")
def get_cascade(norad_id: int, event_id: str, maneuver_label: str):
    valid = set(LABEL_SLUGS.keys())
    if maneuver_label not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"maneuver_label must be one of: {sorted(valid)}",
        )

    events = _conjunction_cache.get(norad_id)
    pipeline = _pipeline_cache.get(norad_id)

    if events is None or pipeline is None:
        raise HTTPException(
            status_code=409,
            detail=f"No data cached for NORAD {norad_id}. Call /api/conjunctions/{norad_id} first.",
        )

    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found.")

    display_label = LABEL_SLUGS[maneuver_label]
    options = compute_maneuvers(event)["maneuver_options"]
    maneuver = next((m for m in options if m["label"] == display_label), None)
    if maneuver is None:
        raise HTTPException(status_code=500, detail=f"Could not resolve maneuver option {display_label!r}.")

    try:
        result = compute_cascade(
            event=event,
            maneuver=maneuver,
            primary_rec=pipeline["primary_rec"],
            primary_sat=pipeline["primary_sat"],
            catalog_records=pipeline["catalog_records"],
            sat_by_norad=pipeline["sat_by_norad"],
            original_events=events,
            t_start=pipeline["t_start"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result
