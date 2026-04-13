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
from backend.rogue.impact import get_impact, get_all_assets, enrich_event
from backend.rogue.incidents import list_incidents, reconstruct, INCIDENTS
from backend.rogue.resurrection import detect_resurrections
from backend.rogue.mission_mismatch import get_all_known_satellites, get_mismatch

logger = logging.getLogger("api")

app = FastAPI(title="Drift Zero — Rogue API", version="0.3.0")

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
    days: int = Query(default=_ROGUE_DAYS, ge=7, le=180),
):
    global _rogue_cache, _rogue_cache_time

    # If caller passes specific IDs, bypass cache (targeted query)
    target_ids = norad_ids if norad_ids else _DEFAULT_ROGUE_NORADS
    using_cache = not norad_ids

    now = time.time()
    if using_cache and _rogue_cache is not None and (now - _rogue_cache_time) < _CACHE_TTL:
        logger.info("Rogue: serving from cache")
        return _rogue_cache

    flagged = run(norad_ids=target_ids, days=days)

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

        event_dict = {
            "norad_id": e.norad_id,
            "epoch": str(e.epoch),
            "severity": e.severity,
            "composite_score": round(e.composite_score, 3),
            "z_score_max": round(e.z_score_max, 3),
            "anomalous_features": e.anomalous_features,
            "description": e.description,
            "summary": summary,
        }
        # Attach asset impact if this satellite is a high-value target
        event_dict["asset_impact"] = get_impact(
            e.norad_id,
            getattr(e, "object_name", ""),
        )
        results.append(event_dict)

    if using_cache:
        _rogue_cache = results
        _rogue_cache_time = now
    return results


# ── Economic / strategic impact ───────────────────────────────────────────────

@app.get("/api/rogue/impact/{norad_id}")
def get_asset_impact(norad_id: int, object_name: str = Query(default="")):
    """
    Return economic and strategic impact data for a satellite.

    Returns 404 if the satellite is not in the high-value asset registry
    and does not match any known constellation pattern.
    """
    impact = get_impact(norad_id, object_name)
    if impact is None:
        raise HTTPException(
            status_code=404,
            detail=f"NORAD {norad_id} is not a registered high-value asset"
        )
    return impact


@app.get("/api/rogue/assets")
def get_asset_registry():
    """
    Return the full high-value asset registry.
    Used to overlay strategic asset markers on the globe.
    """
    return get_all_assets()


# ── Historical incident reconstruction ───────────────────────────────────────

@app.get("/api/rogue/incidents")
def get_incidents():
    """
    Return summary metadata for all documented historical incidents.
    No TLE computation — fast metadata only. Use /incidents/{id} for full reconstruction.
    """
    return list_incidents()


@app.get("/api/rogue/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    force_refresh: bool = Query(default=False),
):
    """
    Reconstruct a specific historical incident from Space-Track TLE history.

    Returns the delta-V timeline for the actor satellite with the epoch
    at which Drift Zero would have first triggered an alert.

    incident_id options:
      cosmos-1408-asat-2021
      kosmos-2542-shadowing-2020
      shijian-21-relocation-2022
      kosmos-2576-gps-approach-2024

    This call fetches live TLE data from Space-Track on first run (~5-10s).
    Subsequent calls use cached data.
    """
    if incident_id not in INCIDENTS:
        valid = list(INCIDENTS.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown incident ID. Valid IDs: {valid}"
        )
    try:
        return reconstruct(incident_id, force_refresh=force_refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Dead satellite resurrection ───────────────────────────────────────────────

@app.get("/api/rogue/resurrections")
def get_resurrections(
    norad_ids: str = Query(
        description="Comma-separated NORAD IDs to scan for resurrection events"
    ),
    days: int = Query(default=180, ge=30, le=365),
    force_refresh: bool = Query(default=False),
):
    """
    Detect dead satellite resurrection events — satellites that were dormant
    for an extended period and then suddenly resumed maneuvering.

    Returns list of resurrection events sorted by post-dormancy delta-V descending.

    Example:
      GET /api/rogue/resurrections?norad_ids=44878,45175,49395&days=180
    """
    try:
        ids = [int(x.strip()) for x in norad_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="norad_ids must be comma-separated integers")

    try:
        events = detect_resurrections(norad_ids=ids, days=days, force_refresh=force_refresh)
        return [e.to_dict() for e in events]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Mission mismatch ──────────────────────────────────────────────────────────

@app.get("/api/rogue/mismatch/known")
def get_known_mismatches():
    """
    Return the full registry of satellites with documented declared vs.
    actual mission mismatches. No computation needed — returns immediately.

    Suitable for a 'Known Offenders' panel on the Rogue dashboard.
    """
    return get_all_known_satellites()


@app.get("/api/rogue/mismatch/{norad_id}")
def get_mismatch_for_satellite(
    norad_id: int,
    object_name: str = Query(default=""),
    country_code: str = Query(default=""),
    days: int = Query(default=180, ge=30, le=365),
    force_refresh: bool = Query(default=False),
):
    """
    Compute a declared vs. actual mission mismatch score for a satellite
    using its TLE history.

    Returns mismatch_score (0-1), verdict (NORMAL/ANOMALOUS/SUSPICIOUS/ADVERSARIAL),
    and the specific signals that triggered the mismatch.

    This call fetches live TLE data from Space-Track on first run.
    """
    from pipeline.tle_ingest import ingest
    from rogue.feature_engineering import extract_delta_features, normalize_tle_row

    try:
        tles = ingest(norad_ids=[norad_id], days=days, force_refresh=force_refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TLE fetch failed: {exc}")

    records = tles.get(norad_id, [])
    if not records:
        raise HTTPException(status_code=404, detail=f"No TLE history found for NORAD {norad_id}")

    records_sorted = sorted(records, key=lambda r: r["epoch"])
    sat_name = object_name or records_sorted[-1].get("object_name", f"NORAD {norad_id}")

    feature_series: list[dict] = []
    for i in range(1, len(records_sorted)):
        try:
            feat = extract_delta_features(
                normalize_tle_row(records_sorted[i - 1]),
                normalize_tle_row(records_sorted[i]),
                solar_f107=150.0,
                kp=3.0,
            )
            feature_series.append(feat)
        except Exception:
            continue

    return get_mismatch(
        norad_id=norad_id,
        feature_series=feature_series,
        object_name=sat_name,
        country_code=country_code,
    )


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
