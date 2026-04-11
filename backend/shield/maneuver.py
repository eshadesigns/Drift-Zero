"""
backend/shield/maneuver.py

Given a conjunction event dict from the Shield pipeline, generates three
maneuver options that nudge the primary satellite's velocity to increase
the predicted miss distance.

Options
-------
  Maximum Safety  -- target miss increase +50 km
  Balanced        -- target miss increase +25 km
  Fuel Efficient  -- target miss increase +10 km

Per-option outputs
------------------
  delta_v_ms             m/s  -- velocity increment (time-based)
  fuel_kg                kg   -- propellant mass via Tsiolkovsky equation
  fuel_cost_usd          USD  -- at $10,000/kg launch cost
  lifespan_reduction_days     -- days of station-keeping lifetime consumed
  composite_score        0-1  -- weighted risk/fuel/ops score

Delta-V approximation (time-based)
------------------------------------
    dV (m/s) = miss_increase_km * 1000 / lead_time_s

where lead_time_s = seconds from pipeline run time to TCA, derived from
event["tca_utc"] and event["timestamp_utc"].

Physically: a perpendicular impulse dV displaces the satellite by
dV * lead_time_s metres by TCA, so inverting gives the required impulse.

Tsiolkovsky parameters (defaults)
-----------------------------------
  Isp         = 220 s          (Starlink v2 mini Hall thruster)
  dry_mass_kg = 260 kg         (Starlink v2 mini dry mass)
  g0          = 9.80665 m/s²

Station-keeping budget
----------------------
  0.5 kg/month assumed
  lifespan_reduction_days = fuel_kg / 0.5 * 30

Composite score weights
-----------------------
  50 % risk reduction      -- miss_increase_km / max_miss_increase  (higher = better)
  30 % fuel efficiency     -- min_fuel_kg / fuel_kg                 (lower fuel = better)
  20 % operational impact  -- min_lifespan_days / lifespan_days     (lower impact = better)
  All components normalised relative to the three options in the set.
"""

from __future__ import annotations

import math
from datetime import datetime

# ── Physical constants ────────────────────────────────────────────────────────
G0_MS2: float = 9.80665            # standard gravity, m/s²
DEFAULT_ISP_S: float = 220.0       # specific impulse, seconds
DEFAULT_DRY_MASS_KG: float = 260.0 # satellite dry mass, kg

# ── Cost and budget ───────────────────────────────────────────────────────────
FUEL_COST_PER_KG_USD: float = 10_000.0
SK_BUDGET_KG_PER_MONTH: float = 0.5
DAYS_PER_MONTH: float = 30.0

# ── Maneuver option definitions ───────────────────────────────────────────────
_OPTION_DEFS: list[tuple[str, float]] = [
    ("Maximum Safety", 50.0),
    ("Balanced",       25.0),
    ("Fuel Efficient", 10.0),
]

_MAX_MISS_INCREASE_KM: float = max(inc for _, inc in _OPTION_DEFS)


# ── Core physics helpers ──────────────────────────────────────────────────────

def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _lead_time_s(tca_utc_str: str, timestamp_utc_str: str) -> float:
    """
    Seconds from pipeline run time (timestamp_utc) to TCA (tca_utc).
    Returns 86400.0 (24 h) as a safe fallback if either timestamp is missing
    or cannot be parsed.
    """
    try:
        return max(
            0.0,
            (_parse_utc(tca_utc_str) - _parse_utc(timestamp_utc_str)).total_seconds(),
        )
    except (ValueError, TypeError):
        return 86400.0


def _delta_v_time_based(miss_increase_km: float, lead_time_s: float) -> float:
    """
    Delta-V in m/s required to achieve a given miss-distance increase.

        dV (m/s) = miss_increase_km * 1000 / lead_time_s

    Physically: a perpendicular impulse dV displaces the satellite by
    dV * lead_time_s metres by TCA.
    Returns 0.0 if lead_time_s is zero or negative.
    """
    if lead_time_s <= 0.0:
        return 0.0
    return miss_increase_km * 1000.0 / lead_time_s


def _fuel_kg(
    delta_v_ms: float,
    isp_s: float = DEFAULT_ISP_S,
    dry_mass_kg: float = DEFAULT_DRY_MASS_KG,
) -> float:
    """
    Propellant mass from the Tsiolkovsky rocket equation:

        m_fuel = m_dry * (exp(dV / (Isp * g0)) - 1)

    The exponent is clamped to 700 to avoid float overflow for very large dV.
    """
    if delta_v_ms <= 0.0:
        return 0.0
    exponent = min(delta_v_ms / (isp_s * G0_MS2), 700.0)
    return dry_mass_kg * (math.exp(exponent) - 1.0)


# ── Public API ────────────────────────────────────────────────────────────────

def compute_maneuvers(
    event: dict,
    isp_s: float = DEFAULT_ISP_S,
    dry_mass_kg: float = DEFAULT_DRY_MASS_KG,
) -> dict:
    """
    Generate three maneuver options for a conjunction event.

    Args:
        event:       Conjunction event dict from the Shield pipeline output.
        isp_s:       Specific impulse of the thruster in seconds.
        dry_mass_kg: Dry mass of the satellite in kg.

    Returns:
        Dict with keys:
            event_id, norad_id, primary_name, current_miss_km, maneuver_options.
        maneuver_options is a list of three dicts sorted by composite_score
        descending.
    """
    miss_km      = float(event.get("miss_distance_km", 0))
    event_id     = event.get("event_id", "")
    primary      = event.get("primary", {})
    norad_id     = primary.get("norad_id", 0)
    primary_name = primary.get("name", "")

    lead_s = _lead_time_s(
        event.get("tca_utc", ""),
        event.get("timestamp_utc", ""),
    )

    # ── Build raw option values ───────────────────────────────────────────────
    raw: list[dict] = []
    for label, increase_km in _OPTION_DEFS:
        dv       = _delta_v_time_based(increase_km, lead_s)
        fuel     = _fuel_kg(dv, isp_s, dry_mass_kg)
        cost     = fuel * FUEL_COST_PER_KG_USD
        lifespan = (fuel / SK_BUDGET_KG_PER_MONTH) * DAYS_PER_MONTH

        raw.append({
            "label":                   label,
            "miss_increase_km":        round(increase_km, 2),
            "delta_v_ms":              round(dv, 4),
            "fuel_kg":                 round(fuel, 4),
            "fuel_cost_usd":           round(cost, 2),
            "lifespan_reduction_days": round(lifespan, 2),
            # unrounded versions for composite scoring
            "_fuel":     fuel,
            "_lifespan": lifespan,
            "_increase": increase_km,
        })

    # ── Composite score (normalised across the three options) ─────────────────
    min_fuel     = min(o["_fuel"]     for o in raw)
    min_lifespan = min(o["_lifespan"] for o in raw)

    options: list[dict] = []
    for o in raw:
        risk_score = o["_increase"] / _MAX_MISS_INCREASE_KM
        fuel_score = (min_fuel     / o["_fuel"])     if o["_fuel"]     > 0 else 1.0
        ops_score  = (min_lifespan / o["_lifespan"]) if o["_lifespan"] > 0 else 1.0

        composite = round(0.50 * risk_score + 0.30 * fuel_score + 0.20 * ops_score, 4)

        options.append({
            "label":                   o["label"],
            "miss_increase_km":        o["miss_increase_km"],
            "delta_v_ms":              o["delta_v_ms"],
            "fuel_kg":                 o["fuel_kg"],
            "fuel_cost_usd":           o["fuel_cost_usd"],
            "lifespan_reduction_days": o["lifespan_reduction_days"],
            "composite_score":         composite,
        })

    options.sort(key=lambda x: x["composite_score"], reverse=True)

    return {
        "event_id":         event_id,
        "norad_id":         norad_id,
        "primary_name":     primary_name,
        "current_miss_km":  round(miss_km, 4),
        "maneuver_options": options,
    }
