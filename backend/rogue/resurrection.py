"""
backend/rogue/resurrection.py

Dead satellite resurrection detection.

A "resurrection" is when a satellite that appeared dormant — no measurable
delta-V for an extended period — suddenly resumes active maneuvering.

This is one of the strongest anomaly signals in the dataset:
  - Dead satellites don't maneuver. Physics is unambiguous.
  - Resuming after months of silence means someone turned it back on.
  - Could indicate: sleeper asset activation, covert capability reveal,
    or an undeclared on-orbit servicing (fuel transfer).

Real documented cases
---------------------
- Luch (Olymp-K) satellite, Russia: repeatedly went "dark" for months
  then resumed proximity operations near European comms satellites.
- Various Soviet-era inspector satellites reactivated decades after launch.

Algorithm
---------
1. Fetch TLE history for target satellites (via pipeline/tle_ingest.py)
2. Compute delta_v_proxy for each consecutive TLE pair
3. Find "dormancy windows": contiguous periods where cumulative delta-V
   remains below DORMANCY_DV_THRESHOLD for at least DORMANCY_MIN_DAYS
4. After each dormancy window, check if delta_v_proxy spikes above
   RESURRECTION_DV_THRESHOLD
5. Return all resurrection events found

Usage
-----
    from backend.rogue.resurrection import detect_resurrections

    events = detect_resurrections(norad_ids=[44878, 49395], days=180)
    for ev in events:
        print(ev.norad_id, ev.dormancy_days, ev.post_dormancy_delta_v_ms)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from pipeline.tle_ingest import ingest
from backend.rogue.feature_engineering import extract_delta_features

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

DORMANCY_DV_THRESHOLD_MS    = 0.3   # m/s — below this per epoch = "dormant"
DORMANCY_MIN_DAYS           = 21    # minimum dormancy window to count (days)
RESURRECTION_DV_THRESHOLD   = 1.5   # m/s — delta-V spike that counts as "waking up"
RESURRECTION_WINDOW_DAYS    = 14    # how many days after dormancy end to look for spike


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ResurrectionEvent:
    norad_id: int
    object_name: str
    dormancy_start: str               # ISO datetime
    dormancy_end: str                 # ISO datetime
    dormancy_days: int
    resurrection_epoch: str           # ISO datetime of first post-dormancy spike
    post_dormancy_delta_v_ms: float   # m/s of the resurrection burn
    severity: str                     # SUSPICIOUS | ADVERSARIAL
    description: str

    def to_dict(self) -> dict:
        return {
            "norad_id":                  self.norad_id,
            "object_name":               self.object_name,
            "dormancy_start":            self.dormancy_start,
            "dormancy_end":              self.dormancy_end,
            "dormancy_days":             self.dormancy_days,
            "resurrection_epoch":        self.resurrection_epoch,
            "post_dormancy_delta_v_ms":  round(self.post_dormancy_delta_v_ms, 2),
            "severity":                  self.severity,
            "description":               self.description,
        }


# ── Core detection ────────────────────────────────────────────────────────────

def detect_resurrections(
    norad_ids: list[int],
    days: int = 180,
    force_refresh: bool = False,
) -> list[ResurrectionEvent]:
    """
    Detect resurrection events for the given NORAD IDs.

    Args:
        norad_ids:     Satellites to analyze.
        days:          Days of TLE history to fetch.
        force_refresh: Bypass local TLE cache.

    Returns:
        List of ResurrectionEvent, sorted by post_dormancy_delta_v_ms descending.
    """
    logger.info(f"Resurrection detection: {len(norad_ids)} satellites, {days}d window")

    tles_by_sat = ingest(norad_ids=norad_ids, days=days, force_refresh=force_refresh)

    all_events: list[ResurrectionEvent] = []

    for norad_id, records in tles_by_sat.items():
        if len(records) < 4:
            logger.debug(f"NORAD {norad_id}: too few records ({len(records)}) — skipping")
            continue

        records_sorted = sorted(records, key=lambda r: r["epoch"])
        object_name    = records_sorted[-1].get("object_name", f"NORAD {norad_id}")

        try:
            events = _detect_for_satellite(norad_id, object_name, records_sorted)
            all_events.extend(events)
        except Exception as exc:
            logger.warning(f"Resurrection detection failed for NORAD {norad_id}: {exc}")

    all_events.sort(key=lambda e: e.post_dormancy_delta_v_ms, reverse=True)
    logger.info(f"Resurrection detection complete: {len(all_events)} events found")
    return all_events


def _detect_for_satellite(
    norad_id: int,
    object_name: str,
    records: list[dict],
) -> list[ResurrectionEvent]:
    """Run the dormancy → resurrection detection for one satellite's record series."""

    # Build feature time-series
    feature_series: list[dict] = []
    for i in range(1, len(records)):
        try:
            feat = extract_delta_features(
                records[i - 1],
                records[i],
                solar_f107=150.0,
                kp=3.0,
            )
            feature_series.append(feat)
        except Exception:
            continue

    if not feature_series:
        return []

    # Identify dormancy windows and resurrection events
    events: list[ResurrectionEvent] = []
    in_dormancy          = False
    dormancy_start_epoch: Optional[datetime] = None
    dormancy_last_epoch:  Optional[datetime] = None

    for i, feat in enumerate(feature_series):
        epoch = feat["epoch"]
        dv    = float(feat.get("delta_v_proxy", 0))

        if dv <= DORMANCY_DV_THRESHOLD_MS:
            # Dormant observation
            if not in_dormancy:
                in_dormancy          = True
                dormancy_start_epoch = epoch
            dormancy_last_epoch = epoch

        else:
            # Active observation — check if we're emerging from a dormancy window
            if in_dormancy and dormancy_start_epoch and dormancy_last_epoch:
                dormancy_days = (dormancy_last_epoch - dormancy_start_epoch).days

                if dormancy_days >= DORMANCY_MIN_DAYS and dv >= RESURRECTION_DV_THRESHOLD:
                    # Valid resurrection
                    sev = "ADVERSARIAL" if dv >= 5.0 else "SUSPICIOUS"
                    ev  = ResurrectionEvent(
                        norad_id=norad_id,
                        object_name=object_name,
                        dormancy_start=dormancy_start_epoch.isoformat(),
                        dormancy_end=dormancy_last_epoch.isoformat(),
                        dormancy_days=dormancy_days,
                        resurrection_epoch=epoch.isoformat(),
                        post_dormancy_delta_v_ms=dv,
                        severity=sev,
                        description=_describe(
                            object_name, dormancy_days, dv, sev, epoch
                        ),
                    )
                    events.append(ev)

            # Reset dormancy state
            in_dormancy          = False
            dormancy_start_epoch = None
            dormancy_last_epoch  = None

    return events


def _describe(
    name: str,
    dormancy_days: int,
    dv_ms: float,
    severity: str,
    epoch: datetime,
) -> str:
    epoch_str = epoch.strftime("%Y-%m-%d")
    if severity == "ADVERSARIAL":
        return (
            f"{name} was dormant for {dormancy_days} days with no detectable "
            f"maneuvering. On {epoch_str} it executed a {dv_ms:.1f} m/s burn — "
            f"a strong indicator of sleeper asset activation or covert on-orbit "
            f"servicing. Classification: ADVERSARIAL."
        )
    return (
        f"{name} showed no significant maneuvering for {dormancy_days} days. "
        f"On {epoch_str} activity resumed with a {dv_ms:.1f} m/s burn. "
        f"Warrants further monitoring. Classification: SUSPICIOUS."
    )
