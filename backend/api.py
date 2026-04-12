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
    _conjunction_cache_time,
    _pipeline_cache,
    compute_maneuvers,
    fetch_single_satellite,
    _get_session,
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
# Only summarise the single highest-priority event per response.
# Each call is a synchronous Anthropic round-trip; keep this at 1 to avoid
# rate-limit storms when the cache is cold.
_SUMMARY_LIMIT = 1

# Single shared client — no retries so a 429 fails fast and returns ""
# rather than sleeping 10-12s and firing another request into the limit.
_anthropic_key = os.getenv("ANTHROPIC_API_KEY")
_anthropic_client = (
    anthropic.Anthropic(api_key=_anthropic_key, max_retries=0)
    if _anthropic_key else None
)

def _summarise(prompt: str) -> str:
    if not _anthropic_client:
        return ""
    try:
        msg = _anthropic_client.messages.create(
            model=_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        logger.warning(f"Anthropic summarise failed: {exc}")
        return ""

# ── Rogue cache ────────────────────────────────────────────────────────────────
# Default-list cache (no specific norad_ids passed)
_rogue_cache: list | None = None
_rogue_cache_time: float = 0.0

# Per-query cache keyed by sorted tuple of NORAD IDs → avoids re-running the
# full pipeline every time the Rogue tab opens for the same tracked satellite.
_rogue_query_cache: dict[str, list] = {}
_rogue_query_cache_time: dict[str, float] = {}

# Max events returned per response — prevents flooding the UI when a cooperative
# satellite (e.g. ISS) generates dozens of SUSPICIOUS maneuver events.
_ROGUE_RESULT_LIMIT = 10


# ── Rogue ──────────────────────────────────────────────────────────────────────

_DEFAULT_ROGUE_NORADS = [59773, 25544, 48274, 44713, 28190]
_ROGUE_DAYS = 180   # must reach Feb 2026 events (~45 days back from demo date)

@app.get("/api/rogue/events")
def get_events(
    norad_ids: list[int] = Query(default=None),
):
    global _rogue_cache, _rogue_cache_time

    target_ids = norad_ids if norad_ids else _DEFAULT_ROGUE_NORADS
    now = time.time()

    # ── Cache lookup ───────────────────────────────────────────────────────────
    if norad_ids:
        cache_key = ",".join(str(n) for n in sorted(norad_ids))
        cached = _rogue_query_cache.get(cache_key)
        cached_time = _rogue_query_cache_time.get(cache_key, 0.0)
        if cached is not None and (now - cached_time) < _CACHE_TTL:
            logger.info("Rogue: serving per-query cache for %s", cache_key)
            return cached
    else:
        cache_key = None
        if _rogue_cache is not None and (now - _rogue_cache_time) < _CACHE_TTL:
            logger.info("Rogue: serving from default cache")
            return _rogue_cache

    # ── Run pipeline ───────────────────────────────────────────────────────────
    flagged = run(norad_ids=target_ids, days=_ROGUE_DAYS)

    # Sort highest composite score first, then cap to avoid UI floods from
    # satellites that maneuver frequently (e.g. ISS reboosts).
    flagged = sorted(flagged, key=lambda e: (e.composite_score, e.z_score_max), reverse=True)
    flagged = flagged[:_ROGUE_RESULT_LIMIT]

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

    # ── Store in cache ─────────────────────────────────────────────────────────
    if cache_key:
        _rogue_query_cache[cache_key] = results
        _rogue_query_cache_time[cache_key] = now
    else:
        _rogue_cache = results
        _rogue_cache_time = now

    return results


# ── Shield: conjunctions ───────────────────────────────────────────────────────

@app.get("/api/conjunctions/{norad_id}")
def get_conjunctions(norad_id: int, min_risk: float = 0.0, limit: int = 20):
    now = time.time()
    # _conjunction_cache and _conjunction_cache_time are both keyed by norad_id
    # (integer NORAD CAT ID). They live in shield/main.py so all modules share
    # the same objects — no risk of the TTL dict drifting out of sync.
    cached_time = _conjunction_cache_time.get(norad_id, 0.0)

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
        _conjunction_cache[norad_id] = events
        _conjunction_cache_time[norad_id] = now

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


# ── Shield: satellite lookup (validation + TLE info) ──────────────────────────

@app.get("/api/satellite/{norad_id}")
def get_satellite(norad_id: int):
    """
    Return basic orbital parameters for a NORAD CAT ID.
    Used by the landing page to validate user input before starting the pipeline.
    Returns 404 if Space-Track has no record for this NORAD ID.
    """
    try:
        session = _get_session()
        rec = fetch_single_satellite(session, norad_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"NORAD {norad_id} not found in Space-Track catalog.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "norad_id":        norad_id,
        "name":            rec.get("OBJECT_NAME", ""),
        "object_type":     rec.get("OBJECT_TYPE", ""),
        "country_code":    rec.get("COUNTRY_CODE", ""),
        "launch_date":     rec.get("LAUNCH_DATE", ""),
        "period_min":      rec.get("PERIOD"),
        "inclination_deg": rec.get("INCLINATION"),
        "apoapsis_km":     rec.get("APOAPSIS"),
        "periapsis_km":    rec.get("PERIAPSIS"),
        "tle_line1":       rec.get("TLE_LINE1", ""),
        "tle_line2":       rec.get("TLE_LINE2", ""),
    }


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
