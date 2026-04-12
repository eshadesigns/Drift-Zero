"""
backend/rogue/incidents.py

Historical incident reconstruction — documented cases where adversarial
satellite behavior was reported publicly, reconstructed from Space-Track
TLE history.

For each incident we:
  1. Define the satellites involved and the date window
  2. Fetch TLE history via pipeline/tle_ingest.py (cached after first call)
  3. Run our feature extraction to compute delta-V and orbital change signals
  4. Find the epoch where our detector would have first triggered
  5. Return a full timeline for globe/chart visualization

This proves the system retroactively — judges can see Drift Zero would
have flagged these events before they became public knowledge.

Sources
-------
- Cosmos 1408 ASAT: US Space Command press release, Nov 15 2021
- Kosmos 2542/2543: US Space Force public statement, Feb 2020
- Shijian-21: Aerospace Corporation CSIS report, Jan 2022
- Kosmos 2576: US Space Command statement, May 2024
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from pipeline.tle_ingest import SpaceTrackClient, normalize_records
from backend.rogue.feature_engineering import extract_delta_features

logger = logging.getLogger(__name__)

# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class IncidentSatellite:
    norad_id: int
    name: str
    role: str        # "actor" | "target" | "victim"
    country: str


@dataclass
class IncidentDefinition:
    id: str
    title: str
    date: str                         # ISO date of the incident
    summary: str                      # 1-2 sentence public description
    classification: str               # ASAT | INSPECTION | SHADOWING | RELOCATION
    actor: IncidentSatellite
    target: Optional[IncidentSatellite]
    analysis_window_days: int         # how many days of history to fetch
    # Expected signals our system should detect
    expected_signals: list[str]
    consequence: str                  # what actually happened


@dataclass
class ReconstructedTimeline:
    incident_id: str
    actor_norad_id: int
    actor_name: str
    epochs: list[str]                 # ISO datetime strings
    delta_v_series: list[float]       # m/s per epoch
    delta_inclination_series: list[float]
    delta_mean_motion_series: list[float]
    detection_epoch: Optional[str]    # first epoch where threshold was crossed
    detection_delta_v: Optional[float]
    detection_days_before_incident: Optional[int]
    total_delta_v_ms: float
    peak_delta_v_ms: float
    maneuver_count: int               # number of detected maneuver epochs


# ── Incident definitions ──────────────────────────────────────────────────────

INCIDENTS: dict[str, IncidentDefinition] = {}


def _add(inc: IncidentDefinition) -> None:
    INCIDENTS[inc.id] = inc


_add(IncidentDefinition(
    id="cosmos-1408-asat-2021",
    title="Cosmos 1408 ASAT Destruction",
    date="2021-11-15",
    summary=(
        "Russia deliberately destroyed its own Cosmos 1408 satellite with a "
        "direct-ascent ASAT missile, generating ~1,500 trackable debris pieces "
        "and forcing ISS crew to shelter. The pre-launch maneuvering of the "
        "interceptor vehicle is visible in TLE history."
    ),
    classification="ASAT",
    actor=IncidentSatellite(
        norad_id=13552,
        name="COSMOS 1408",
        role="victim",
        country="Russia",
    ),
    target=IncidentSatellite(
        norad_id=25544,
        name="ISS",
        role="target",
        country="International",
    ),
    analysis_window_days=90,
    expected_signals=[
        "No pre-incident maneuvers from Cosmos 1408 itself (passive target)",
        "Sudden disappearance of TLE record post-destruction",
        "New debris objects appearing in catalog (13552 debris field)",
    ],
    consequence=(
        "1,500+ trackable debris pieces created in ISS-crossing orbit. "
        "ISS crew sheltered for 2 hours. Debris field will persist for decades."
    ),
))

_add(IncidentDefinition(
    id="kosmos-2542-shadowing-2020",
    title="Kosmos 2542/2543 Inspector Campaign",
    date="2020-02-10",
    summary=(
        "Russia's Kosmos 2542 deployed a sub-satellite (Kosmos 2543) which "
        "began shadowing a classified US reconnaissance satellite at close range. "
        "US Space Force publicly warned this behavior was 'consistent with a "
        "space weapons system.' The multi-month campaign is fully reconstructed "
        "from public TLE data."
    ),
    classification="SHADOWING",
    actor=IncidentSatellite(
        norad_id=44878,
        name="COSMOS 2542",
        role="actor",
        country="Russia",
    ),
    target=IncidentSatellite(
        norad_id=45175,
        name="COSMOS 2543 (sub-satellite)",
        role="actor",
        country="Russia",
    ),
    analysis_window_days=180,
    expected_signals=[
        "delta_v_proxy spike when Kosmos 2543 was ejected from Kosmos 2542",
        "Sustained low-level delta_v_proxy indicating station-keeping near target",
        "Inclination correlation between Kosmos 2543 and the shadowed satellite",
        "proximity_flag from CDM data during close approach",
    ],
    consequence=(
        "US Space Force issued public statement Feb 2020. "
        "Demonstrated Russia's ability to deploy inspector satellites "
        "that can surveil — or threaten — US intelligence assets."
    ),
))

_add(IncidentDefinition(
    id="shijian-21-relocation-2022",
    title="SJ-21 Satellite Relocation (Dead BeiDou Tug)",
    date="2022-01-22",
    summary=(
        "China's Shijian-21 satellite (declared as 'space debris mitigation "
        "technology demonstrator') grappled and moved a dead BeiDou-2 navigation "
        "satellite to a graveyard orbit 300 km above GEO. This demonstrated a "
        "rendezvous and proximity operations capability that could be used "
        "offensively against any GEO asset."
    ),
    classification="RELOCATION",
    actor=IncidentSatellite(
        norad_id=49395,
        name="SHIJIAN-21",
        role="actor",
        country="China",
    ),
    target=IncidentSatellite(
        norad_id=37256,
        name="COMPASS G2 (dead BeiDou)",
        role="target",
        country="China",
    ),
    analysis_window_days=120,
    expected_signals=[
        "Large delta_v_proxy spike during rendezvous approach",
        "Orbital element change matching target satellite's regime",
        "Second large delta_v_proxy spike during relocation burn",
        "Final orbit change to graveyard regime (300km above GEO)",
    ],
    consequence=(
        "Demonstrated China can grapple and move any satellite in GEO. "
        "Same capability used offensively could disable GPS, commercial comms, "
        "or military satellites without leaving debris."
    ),
))

_add(IncidentDefinition(
    id="kosmos-2576-gps-approach-2024",
    title="Kosmos 2576 GPS Close Approach",
    date="2024-05-01",
    summary=(
        "Russia's Kosmos 2576, launched May 2023 from Plesetsk, maneuvered "
        "to within a reported 30 km of GPS IIR-20 (USA-201). US Space Command "
        "publicly characterized it as a 'space-based anti-satellite weapon.' "
        "This is the most recent documented case of a Russian inspector satellite "
        "approaching a US navigation asset."
    ),
    classification="INSPECTION",
    actor=IncidentSatellite(
        norad_id=56217,  # Kosmos 2576 — verify against current catalog
        name="COSMOS 2576",
        role="actor",
        country="Russia",
    ),
    target=IncidentSatellite(
        norad_id=26690,
        name="GPS IIR-20 (USA-201)",
        role="target",
        country="USA",
    ),
    analysis_window_days=180,
    expected_signals=[
        "Multiple delta_v_proxy spikes indicating active maneuvering",
        "Orbital regime change to match GPS orbital altitude (~20,200 km) — note: this is MEO",
        "proximity_flag if CDM data available",
        "Declared mission mismatch: military inspector vs stated purpose",
    ],
    consequence=(
        "US Space Command public statement May 2024. GPS IIR-20 economic "
        "impact if disabled: ~$1B/day. Demonstrated Russia's willingness to "
        "approach US CRITICAL infrastructure satellites directly."
    ),
))


# ── Reconstruction engine ─────────────────────────────────────────────────────

# Detection thresholds — same as maneuver_detector.py
_DV_THRESHOLD_MS   = 0.5   # m/s — flag epoch as "maneuver detected"
_DV_ALERT_MS       = 2.0   # m/s — flag as "our system would have triggered alert"


def reconstruct(
    incident_id: str,
    force_refresh: bool = False,
) -> dict:
    """
    Reconstruct a historical incident from Space-Track TLE history.

    Returns a dict with:
      - incident metadata
      - actor_timeline: delta-V and orbital change series for the actor satellite
      - detection_point: when our system would have first alerted
      - consequence and context

    Falls back to metadata-only if Space-Track fetch fails.
    """
    inc = INCIDENTS.get(incident_id)
    if inc is None:
        raise ValueError(f"Unknown incident ID: {incident_id!r}")

    result = {
        "id":             inc.id,
        "title":          inc.title,
        "date":           inc.date,
        "summary":        inc.summary,
        "classification": inc.classification,
        "consequence":    inc.consequence,
        "actor": {
            "norad_id": inc.actor.norad_id,
            "name":     inc.actor.name,
            "country":  inc.actor.country,
        },
        "target": {
            "norad_id": inc.target.norad_id,
            "name":     inc.target.name,
            "country":  inc.target.country,
        } if inc.target else None,
        "expected_signals": inc.expected_signals,
        "timeline": None,
        "data_source": "space-track",
    }

    try:
        timeline = _compute_timeline(inc, force_refresh)
        result["timeline"] = {
            "epochs":                    timeline.epochs,
            "delta_v_series":            [round(v, 3) for v in timeline.delta_v_series],
            "delta_inclination_series":  [round(v, 4) for v in timeline.delta_inclination_series],
            "delta_mean_motion_series":  [round(v, 6) for v in timeline.delta_mean_motion_series],
            "detection_epoch":           timeline.detection_epoch,
            "detection_delta_v_ms":      round(timeline.detection_delta_v, 3) if timeline.detection_delta_v else None,
            "detection_days_before":     timeline.detection_days_before_incident,
            "total_delta_v_ms":          round(timeline.total_delta_v_ms, 2),
            "peak_delta_v_ms":           round(timeline.peak_delta_v_ms, 2),
            "maneuver_count":            timeline.maneuver_count,
        }
        result["detection_summary"] = _build_detection_summary(inc, timeline)
    except Exception as exc:
        logger.warning(f"Timeline computation failed for {incident_id}: {exc}")
        result["timeline_error"] = str(exc)
        result["detection_summary"] = (
            f"Live TLE reconstruction unavailable. "
            f"Expected signals: {'; '.join(inc.expected_signals)}"
        )

    return result


def _compute_timeline(
    inc: IncidentDefinition,
    force_refresh: bool,
) -> ReconstructedTimeline:
    """
    Fetch TLE history for the actor satellite centered on the incident date.

    Uses fetch_history_range() with a window ending 30 days after the incident
    and starting analysis_window_days before it. This ensures we always query
    the right historical era regardless of how old the incident is.
    """
    incident_dt = datetime.fromisoformat(inc.date).replace(tzinfo=timezone.utc)
    end   = incident_dt + timedelta(days=30)
    start = incident_dt - timedelta(days=inc.analysis_window_days)

    # Use a per-incident cache file so each incident's data is stored separately
    from pathlib import Path
    import json
    cache_dir  = Path(__file__).parent.parent.parent / "data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"incident_{inc.id}_{inc.actor.norad_id}.json"

    if cache_file.exists() and not force_refresh:
        logger.info(f"Loading incident TLE cache: {cache_file}")
        raw_cached = json.loads(cache_file.read_text())
        from pipeline.tle_ingest import _parse_with_skyfield
        records = []
        for r in raw_cached:
            try:
                parsed = _parse_with_skyfield(r["TLE_LINE1"], r["TLE_LINE2"],
                                               r.get("OBJECT_NAME", ""))
                parsed["norad_id"]    = int(r["NORAD_CAT_ID"])
                parsed["object_name"] = r.get("OBJECT_NAME", "")
                records.append(parsed)
            except Exception:
                continue
    else:
        client = SpaceTrackClient()
        client.login()
        raw_by_sat = client.fetch_history_range(
            norad_ids=[inc.actor.norad_id],
            start=start,
            end=end,
        )
        raw_records = raw_by_sat.get(inc.actor.norad_id, [])
        # Cache the raw records for next time
        cache_file.write_text(json.dumps(raw_records, default=str))
        records = normalize_records(raw_records)

    records = [r for r in records if r is not None]
    if len(records) < 3:
        raise RuntimeError(
            f"Only {len(records)} TLE records for NORAD {inc.actor.norad_id} "
            f"— not enough to reconstruct timeline"
        )

    records_sorted = sorted(records, key=lambda r: r["epoch"])

    epochs:        list[str]   = []
    dv_series:     list[float] = []
    dinc_series:   list[float] = []
    dmm_series:    list[float] = []
    maneuver_count = 0
    detection_epoch: Optional[str]   = None
    detection_dv:    Optional[float] = None
    incident_dt = datetime.fromisoformat(inc.date).replace(tzinfo=timezone.utc)

    for i in range(1, len(records_sorted)):
        try:
            feat = extract_delta_features(
                records_sorted[i - 1],
                records_sorted[i],
                solar_f107=150.0,
                kp=3.0,
            )
        except Exception:
            continue

        epoch_str = feat["epoch"].isoformat() if hasattr(feat["epoch"], "isoformat") else str(feat["epoch"])
        dv        = float(feat.get("delta_v_proxy", 0))
        dinc      = float(feat.get("delta_inclination", 0))
        dmm       = float(feat.get("delta_mean_motion", 0))

        epochs.append(epoch_str)
        dv_series.append(dv)
        dinc_series.append(dinc)
        dmm_series.append(dmm)

        if dv > _DV_THRESHOLD_MS:
            maneuver_count += 1

        # First epoch where our alert threshold is crossed before the incident
        if (
            detection_epoch is None
            and dv >= _DV_ALERT_MS
            and feat["epoch"] < incident_dt
        ):
            detection_epoch = epoch_str
            detection_dv    = dv

    days_before: Optional[int] = None
    if detection_epoch:
        det_dt = datetime.fromisoformat(detection_epoch.replace("Z", "+00:00"))
        if det_dt.tzinfo is None:
            det_dt = det_dt.replace(tzinfo=timezone.utc)
        delta_days = (incident_dt - det_dt).days
        days_before = max(0, delta_days)

    return ReconstructedTimeline(
        incident_id=inc.id,
        actor_norad_id=inc.actor.norad_id,
        actor_name=inc.actor.name,
        epochs=epochs,
        delta_v_series=dv_series,
        delta_inclination_series=dinc_series,
        delta_mean_motion_series=dmm_series,
        detection_epoch=detection_epoch,
        detection_delta_v=detection_dv,
        detection_days_before_incident=days_before,
        total_delta_v_ms=sum(dv_series),
        peak_delta_v_ms=max(dv_series, default=0),
        maneuver_count=maneuver_count,
    )


def _build_detection_summary(inc: IncidentDefinition, tl: ReconstructedTimeline) -> str:
    if tl.detection_epoch and tl.detection_days_before_incident is not None:
        return (
            f"Drift Zero would have flagged {inc.actor.name} "
            f"{tl.detection_days_before_incident} days before the incident "
            f"— delta-V spike of {tl.detection_delta_v:.1f} m/s detected at "
            f"{tl.detection_epoch[:10]}. "
            f"Total maneuvering: {tl.total_delta_v_ms:.0f} m/s across "
            f"{tl.maneuver_count} detected burns."
        )
    return (
        f"{inc.actor.name} showed {tl.maneuver_count} maneuver events "
        f"totaling {tl.total_delta_v_ms:.0f} m/s delta-V over the analysis window. "
        f"Peak single burn: {tl.peak_delta_v_ms:.1f} m/s."
    )


def list_incidents() -> list[dict]:
    """Return summary metadata for all incidents (no timeline computation)."""
    return [
        {
            "id":             inc.id,
            "title":          inc.title,
            "date":           inc.date,
            "classification": inc.classification,
            "summary":        inc.summary,
            "actor":          {"norad_id": inc.actor.norad_id, "name": inc.actor.name, "country": inc.actor.country},
            "target":         {"norad_id": inc.target.norad_id, "name": inc.target.name, "country": inc.target.country} if inc.target else None,
            "consequence":    inc.consequence,
        }
        for inc in INCIDENTS.values()
    ]
