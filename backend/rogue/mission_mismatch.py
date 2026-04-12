"""
backend/rogue/mission_mismatch.py

Declared vs. actual behavior mismatch detection.

Every satellite has a declared mission (weather, science, comms, navigation).
Each mission type has expected behavioral characteristics — how much it should
maneuver, what delta-V budget is normal, whether proximity operations are expected.

When a satellite's actual behavior significantly exceeds or contradicts its
declared mission profile, that is a mismatch. Mismatches are a primary signal
of deception: state actors routinely launch "science" or "debris mitigation"
satellites that are actually inspector vehicles or ASAT platforms.

Real documented cases
---------------------
- Shijian-17: declared "experimental comms" — actually performed GEO rendezvous
- Shijian-21: declared "space debris mitigation" — grappled and moved a satellite
- Kosmos 2499/2504/2519: declared "inspector satellites" — actually weapons tests
- Luch/Olymp-K: declared "relay satellite" — positioned between Intelsat/SES sats

Mismatch scoring
----------------
  0.0 – 0.3  : Normal — behavior consistent with declared mission
  0.3 – 0.6  : Anomalous — exceeds expected parameters
  0.6 – 0.85 : Suspicious — significantly inconsistent with declared mission
  0.85 – 1.0 : Adversarial — behavior directly contradicts declared purpose

Usage
-----
    from backend.rogue.mission_mismatch import get_mismatch, KNOWN_SATELLITES

    result = get_mismatch(norad_id=49395, feature_series=features)
    print(result["mismatch_score"], result["verdict"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Mission profile definitions ───────────────────────────────────────────────

@dataclass
class MissionProfile:
    """Expected behavioral envelope for a given mission type."""
    mission_type: str
    expected_max_dv_per_epoch_ms: float    # m/s — normal single-epoch maneuver
    expected_max_total_dv_180d_ms: float   # m/s — total over 6 months
    proximity_operations_expected: bool    # should this satellite approach others?
    inclination_changes_expected: bool     # plane changes expected?
    description: str


MISSION_PROFILES: dict[str, MissionProfile] = {
    "weather": MissionProfile(
        mission_type="weather",
        expected_max_dv_per_epoch_ms=2.0,
        expected_max_total_dv_180d_ms=20.0,
        proximity_operations_expected=False,
        inclination_changes_expected=False,
        description="Station-keeping only. No rendezvous or plane changes.",
    ),
    "science": MissionProfile(
        mission_type="science",
        expected_max_dv_per_epoch_ms=5.0,
        expected_max_total_dv_180d_ms=50.0,
        proximity_operations_expected=False,
        inclination_changes_expected=False,
        description="Occasional orbit adjustments for coverage. No proximity ops.",
    ),
    "navigation": MissionProfile(
        mission_type="navigation",
        expected_max_dv_per_epoch_ms=3.0,
        expected_max_total_dv_180d_ms=30.0,
        proximity_operations_expected=False,
        inclination_changes_expected=False,
        description="Precise station-keeping in designated orbital slot.",
    ),
    "communications": MissionProfile(
        mission_type="communications",
        expected_max_dv_per_epoch_ms=5.0,
        expected_max_total_dv_180d_ms=60.0,
        proximity_operations_expected=False,
        inclination_changes_expected=False,
        description="Station-keeping at assigned GEO/LEO slot.",
    ),
    "earth_observation": MissionProfile(
        mission_type="earth_observation",
        expected_max_dv_per_epoch_ms=5.0,
        expected_max_total_dv_180d_ms=40.0,
        proximity_operations_expected=False,
        inclination_changes_expected=False,
        description="Orbit maintenance for ground track repeatability.",
    ),
    "debris_mitigation": MissionProfile(
        mission_type="debris_mitigation",
        expected_max_dv_per_epoch_ms=50.0,   # can move dead satellites
        expected_max_total_dv_180d_ms=500.0,
        proximity_operations_expected=True,   # explicitly expected
        inclination_changes_expected=True,
        description="Proximity operations to remove debris are expected.",
    ),
    "inspector": MissionProfile(
        mission_type="inspector",
        expected_max_dv_per_epoch_ms=30.0,
        expected_max_total_dv_180d_ms=300.0,
        proximity_operations_expected=True,
        inclination_changes_expected=True,
        description="Declared rendezvous/inspection mission.",
    ),
    "military_general": MissionProfile(
        mission_type="military_general",
        expected_max_dv_per_epoch_ms=20.0,
        expected_max_total_dv_180d_ms=200.0,
        proximity_operations_expected=False,
        inclination_changes_expected=True,
        description="Generic military satellite — station-keeping plus possible maneuvers.",
    ),
}


# ── Known satellite registry ──────────────────────────────────────────────────

@dataclass
class KnownSatellite:
    norad_id: int
    name: str
    country: str
    declared_mission: str          # what the operator claims
    actual_mission: str            # what open-source analysis shows
    mission_profile_key: str       # key into MISSION_PROFILES for declared mission
    notes: str = ""
    threat_context: str = ""       # why this satellite is notable


KNOWN_SATELLITES: dict[int, KnownSatellite] = {}


def _reg(sat: KnownSatellite) -> None:
    KNOWN_SATELLITES[sat.norad_id] = sat


# ── Russian inspector/ASAT candidates ────────────────────────────────────────

_reg(KnownSatellite(
    norad_id=44878,
    name="COSMOS 2542",
    country="Russia",
    declared_mission="Military technology demonstrator",
    actual_mission="Inspector satellite / ASAT platform — deployed Kosmos 2543 subsatellite",
    mission_profile_key="military_general",
    notes="Launched Nov 2019. Deployed Kosmos 2543 subsatellite in Jan 2020.",
    threat_context="US Space Force stated this system is 'consistent with a space weapons system.'",
))

_reg(KnownSatellite(
    norad_id=45175,
    name="COSMOS 2543",
    country="Russia",
    declared_mission="Military technology demonstrator",
    actual_mission="Inspector satellite — shadowed US reconnaissance satellite",
    mission_profile_key="military_general",
    notes="Ejected from Kosmos 2542. Shadowed USA-245 at close range for months.",
    threat_context="Performed high-speed flyby of another Russian satellite in July 2020 — interpreted as weapons test.",
))

_reg(KnownSatellite(
    norad_id=13552,
    name="COSMOS 1408",
    country="Russia",
    declared_mission="Electronic intelligence (ELINT) satellite",
    actual_mission="ASAT target — destroyed by Russian DA-ASAT missile Nov 15 2021",
    mission_profile_key="military_general",
    notes="Tselina-D ELINT satellite, launched 1982. Destroyed by Russian ASAT test.",
    threat_context="Destruction created 1,500+ trackable debris pieces threatening ISS and other LEO assets.",
))

_reg(KnownSatellite(
    norad_id=56217,
    name="COSMOS 2576",
    country="Russia",
    declared_mission="Military technology satellite",
    actual_mission="Space-based ASAT / inspector — approached GPS IIR-20 in 2024",
    mission_profile_key="military_general",
    notes="Launched May 16 2023 from Plesetsk Cosmodrome.",
    threat_context="US Space Command: 'a space-based anti-satellite weapon' — approached GPS IIR-20 to within reported 30 km.",
))


# ── Chinese inspector/RPO candidates ─────────────────────────────────────────

_reg(KnownSatellite(
    norad_id=49395,
    name="SHIJIAN-21",
    country="China",
    declared_mission="Space debris mitigation technology demonstrator",
    actual_mission="Satellite tug — grappled and relocated dead BeiDou G2 satellite",
    mission_profile_key="debris_mitigation",
    notes="Launched Oct 23 2021. Moved COMPASS G2 (37256) to graveyard orbit Jan 2022.",
    threat_context="Same rendezvous capability could be used to disable any GEO asset. Demonstrated without advance notice.",
))

_reg(KnownSatellite(
    norad_id=41838,
    name="SHIJIAN-17",
    country="China",
    declared_mission="Experimental communications technology",
    actual_mission="GEO inspector — performed proximity operations near other GEO satellites",
    mission_profile_key="communications",
    notes="Launched Nov 2016. Multiple unannounced proximity operations in GEO belt.",
    threat_context="Approached Chinasat-20 and other satellites. Demonstrated ability to inspect any GEO satellite.",
))


# ── Russian 'relay' satellite with suspicious behavior ────────────────────────

_reg(KnownSatellite(
    norad_id=40258,
    name="LUCH (OLYMP-K)",
    country="Russia",
    declared_mission="Data relay satellite",
    actual_mission="Intelligence collection / ASAT — positioned between Intelsat and SES satellites",
    mission_profile_key="communications",
    notes="Parked between commercial comms satellites for years, eavesdropping on traffic.",
    threat_context="Positioned within the stationkeeping box of commercial satellites — potential comms intercept or RF jamming asset.",
))


# ── Mismatch detection ────────────────────────────────────────────────────────

def get_mismatch(
    norad_id: int,
    feature_series: list[dict],
    object_name: str = "",
    country_code: str = "",
) -> dict:
    """
    Compute a mismatch score for a satellite given its feature time-series.

    Args:
        norad_id:       NORAD CAT ID of the satellite.
        feature_series: Output of extract_delta_features() for consecutive TLEs.
        object_name:    Satellite name (for pattern-based lookup if not in registry).
        country_code:   Two-letter country code from Space-Track.

    Returns:
        Dict with mismatch_score (0-1), verdict, declared_mission, actual_signals,
        and known_context if the satellite is in the registry.
    """
    known   = KNOWN_SATELLITES.get(norad_id)
    profile_key = known.mission_profile_key if known else _infer_profile(object_name, country_code)
    profile = MISSION_PROFILES.get(profile_key, MISSION_PROFILES["military_general"])

    if not feature_series:
        return _no_data_result(norad_id, object_name, known, profile)

    # Compute actual behavior metrics
    dv_values      = [float(f.get("delta_v_proxy", 0)) for f in feature_series]
    dinc_values    = [abs(float(f.get("delta_inclination", 0))) for f in feature_series]
    total_dv       = sum(dv_values)
    peak_dv        = max(dv_values, default=0)
    proximity_flag = any(f.get("proximity_flag", False) for f in feature_series)
    has_inc_change = any(v > 0.05 for v in dinc_values)

    # Score each component
    scores: dict[str, float] = {}
    reasons: list[str] = []

    # 1. Peak single-epoch delta-V vs expected max
    if profile.expected_max_dv_per_epoch_ms > 0:
        dv_ratio = peak_dv / profile.expected_max_dv_per_epoch_ms
        scores["peak_dv"] = min(dv_ratio, 1.0)
        if dv_ratio > 1.5:
            reasons.append(
                f"Peak burn {peak_dv:.1f} m/s exceeds expected max "
                f"{profile.expected_max_dv_per_epoch_ms:.1f} m/s for {profile.mission_type} satellite"
            )

    # 2. Total delta-V vs expected budget
    if profile.expected_max_total_dv_180d_ms > 0:
        total_ratio = total_dv / profile.expected_max_total_dv_180d_ms
        scores["total_dv"] = min(total_ratio, 1.0)
        if total_ratio > 1.5:
            reasons.append(
                f"Total delta-V {total_dv:.0f} m/s exceeds expected 180-day budget "
                f"{profile.expected_max_total_dv_180d_ms:.0f} m/s"
            )

    # 3. Proximity operations when not expected
    if proximity_flag and not profile.proximity_operations_expected:
        scores["proximity"] = 0.9
        reasons.append(
            f"Proximity operations detected — not expected for a {profile.mission_type} satellite"
        )

    # 4. Inclination changes when not expected
    if has_inc_change and not profile.inclination_changes_expected:
        scores["inclination"] = 0.6
        reasons.append(
            f"Plane-change maneuver detected — inconsistent with {profile.mission_type} mission"
        )

    mismatch_score = max(scores.values(), default=0.0)

    # If it's a known-bad satellite, floor the score
    if known and known.actual_mission != known.declared_mission:
        mismatch_score = max(mismatch_score, 0.65)
        reasons.insert(0, f"Known case: {known.threat_context}")

    verdict = _verdict(mismatch_score)

    return {
        "norad_id":           norad_id,
        "object_name":        known.name if known else object_name,
        "declared_mission":   known.declared_mission if known else profile.mission_type,
        "actual_mission":     known.actual_mission if known else "Unknown",
        "mission_profile":    profile.mission_type,
        "mismatch_score":     round(mismatch_score, 3),
        "verdict":            verdict,
        "reasons":            reasons,
        "actual_signals": {
            "peak_delta_v_ms":   round(peak_dv, 2),
            "total_delta_v_ms":  round(total_dv, 2),
            "proximity_flag":    proximity_flag,
            "inclination_change": has_inc_change,
        },
        "known_context":      known.threat_context if known else None,
        "country":            known.country if known else country_code,
        "notes":              known.notes if known else "",
    }


def _verdict(score: float) -> str:
    if score < 0.3:
        return "NORMAL"
    if score < 0.6:
        return "ANOMALOUS"
    if score < 0.85:
        return "SUSPICIOUS"
    return "ADVERSARIAL"


def _infer_profile(name: str, country_code: str) -> str:
    """Guess mission type from satellite name and country if not in registry."""
    n = name.upper()
    if any(k in n for k in ("COSMOS", "KOSMOS")):
        return "military_general"
    if any(k in n for k in ("SHIJIAN", "SJ-")):
        return "science"
    if "GPS" in n or "NAVSTAR" in n or "GLONASS" in n or "GALILEO" in n or "BEIDOU" in n:
        return "navigation"
    if any(k in n for k in ("NOAA", "METOP", "FENGYUN")):
        return "weather"
    if country_code in ("CIS", "PRC"):
        return "military_general"
    return "military_general"


def _no_data_result(norad_id, name, known, profile) -> dict:
    return {
        "norad_id":       norad_id,
        "object_name":    known.name if known else name,
        "declared_mission": known.declared_mission if known else profile.mission_type,
        "actual_mission": known.actual_mission if known else "Insufficient data",
        "mission_profile": profile.mission_type,
        "mismatch_score": 0.65 if known else 0.0,
        "verdict":        "SUSPICIOUS" if known else "NORMAL",
        "reasons":        [known.threat_context] if known else [],
        "actual_signals": None,
        "known_context":  known.threat_context if known else None,
        "country":        known.country if known else "",
        "notes":          known.notes if known else "",
    }


def get_all_known_satellites() -> list[dict]:
    """Return the full known satellite registry for the Rogue dashboard."""
    return [
        {
            "norad_id":        s.norad_id,
            "name":            s.name,
            "country":         s.country,
            "declared_mission": s.declared_mission,
            "actual_mission":  s.actual_mission,
            "threat_context":  s.threat_context,
            "notes":           s.notes,
        }
        for s in KNOWN_SATELLITES.values()
    ]
