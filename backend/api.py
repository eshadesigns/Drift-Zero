from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from run_rogue import run
from backend.rogue.impact import get_impact, get_all_assets, enrich_event
from backend.rogue.incidents import list_incidents, reconstruct, INCIDENTS
from backend.rogue.resurrection import detect_resurrections
from backend.rogue.mission_mismatch import get_all_known_satellites, get_mismatch

app = FastAPI(title="Drift Zero — Rogue API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rogue anomaly events ──────────────────────────────────────────────────────

@app.get("/api/rogue/events")
def get_events(
    norad_ids: str = Query(
        default=None,
        description="Comma-separated NORAD IDs (default: ISS, CSS, Starlink-1, GPS IIR-16)"
    ),
    days: int = Query(default=30, ge=7, le=180),
):
    """
    Run the Rogue anomaly pipeline and return flagged events.
    Events are enriched with asset impact data if any nearby satellite
    is a known high-value target.

    Query params:
      norad_ids — comma-separated list of NORAD IDs to analyze
      days      — history window in days (7-180, default 30)
    """
    if norad_ids:
        try:
            ids = [int(x.strip()) for x in norad_ids.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="norad_ids must be comma-separated integers")
    else:
        ids = [25544, 48274, 44713, 28190]

    flagged = run(norad_ids=ids, days=days)

    results = []
    for e in flagged:
        event_dict = {
            "norad_id":           e.norad_id,
            "epoch":              str(e.epoch),
            "severity":           e.severity,
            "composite_score":    round(e.composite_score, 3),
            "z_score_max":        round(e.z_score_max, 3),
            "anomalous_features": e.anomalous_features,
            "description":        e.description,
        }
        # Attach asset impact if this satellite is a high-value target
        event_dict["asset_impact"] = get_impact(
            e.norad_id,
            getattr(e, "object_name", ""),
        )
        results.append(event_dict)

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
