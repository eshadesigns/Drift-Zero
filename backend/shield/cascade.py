"""
backend/shield/cascade.py

Computes downstream conjunction risks introduced or worsened by a maneuver.

Given a conjunction event, a chosen maneuver option (from maneuver.py), and the
cached pipeline data (primary Satrec, threat catalog), this module:

  1. Propagates the primary satellite to the burn epoch (pipeline t_start)
  2. Applies delta_v_ms along the along-track (velocity unit) direction
  3. Converts the perturbed state vector back to an sgp4 Satrec via Keplerian
     element inversion (r,v -> a, e, i, RAAN, argp, M)
  4. Screens the post-maneuver satellite against the threat catalog using the
     same altitude-band-overlap and inclination filters as the main pipeline
  5. Runs find_tca on each candidate pair
  6. Compares against the original conjunction events:
       new      -- secondary was not in the original conjunction list
       worsened -- secondary was in the original list and miss distance shrank

Returns a dict with maneuver_label, delta_v_ms, candidates_screened, and a
cascade_risks list sorted by miss distance ascending.

Physical note
-------------
An along-track impulse dV changes the satellite's orbital energy and hence its
period, causing it to drift ahead of or behind its original ground track over the
following 24-hour window. This phase drift is what creates new or worsened
conjunctions.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import numpy as np
from sgp4.api import Satrec, WGS84, jday as _jday

from shield.propagate import propagate_at
from shield.tca import find_tca

# ── Physical constants ────────────────────────────────────────────────────────
MU_KM3_S2       = 398600.4418   # Earth gravitational parameter, km³/s²
EARTH_RADIUS_KM = 6378.137      # WGS-84 equatorial radius, km

# ── Screening thresholds (mirrors of main.py / screen.py) ────────────────────
ALT_TOLERANCE_KM    = 50.0
INC_TOLERANCE_DEG   = 10.0
POLAR_THRESHOLD_DEG = 80.0

# ── Only surface cascade risks closer than this ───────────────────────────────
CASCADE_MISS_KM = 100.0

# ── Maneuver slug -> display label ────────────────────────────────────────────
LABEL_SLUGS: dict[str, str] = {
    "maximum_safety": "Maximum Safety",
    "balanced":       "Balanced",
    "fuel_efficient": "Fuel Efficient",
}


# ── State-vector -> Satrec ────────────────────────────────────────────────────

def _rv_to_satrec(
    r_km: np.ndarray,
    v_km_s: np.ndarray,
    epoch_jd: float,
    bstar: float = 1e-5,
    norad_id: int = 99999,
) -> Satrec:
    """
    Convert a TEME Cartesian state vector to an sgp4 Satrec.

    Standard two-body inversion:
      angular momentum -> eccentricity vector -> semi-major axis ->
      inclination, RAAN, argp, true anomaly -> eccentric anomaly -> mean anomaly

    Args:
        r_km:      Position vector in TEME frame, km.
        v_km_s:    Velocity vector in TEME frame, km/s.
        epoch_jd:  Full Julian date of the epoch.
        bstar:     SGP4 drag coefficient (inherit from original satellite).
        norad_id:  Synthetic NORAD ID for the virtual post-maneuver satellite.

    Returns:
        Initialised sgp4 Satrec.
    """
    r = np.asarray(r_km, dtype=float)
    v = np.asarray(v_km_s, dtype=float)

    r_mag = float(np.linalg.norm(r))
    v_mag = float(np.linalg.norm(v))

    # Angular momentum
    h     = np.cross(r, v)
    h_mag = float(np.linalg.norm(h))

    # Eccentricity vector
    e_vec = (np.cross(v, h) / MU_KM3_S2) - (r / r_mag)
    e     = float(np.linalg.norm(e_vec))

    # Orbital energy -> semi-major axis
    energy = v_mag ** 2 / 2.0 - MU_KM3_S2 / r_mag
    a = -MU_KM3_S2 / (2.0 * energy)

    # Inclination
    inc = math.acos(max(-1.0, min(1.0, h[2] / h_mag)))

    # Node vector
    K     = np.array([0.0, 0.0, 1.0])
    N     = np.cross(K, h)
    N_mag = float(np.linalg.norm(N))

    # RAAN
    if N_mag > 1e-10:
        raan = math.acos(max(-1.0, min(1.0, N[0] / N_mag)))
        if N[1] < 0.0:
            raan = 2.0 * math.pi - raan
    else:
        raan = 0.0

    # Argument of perigee
    if e > 1e-10 and N_mag > 1e-10:
        argp = math.acos(max(-1.0, min(1.0, float(np.dot(N, e_vec)) / (N_mag * e))))
        if e_vec[2] < 0.0:
            argp = 2.0 * math.pi - argp
    else:
        argp = 0.0

    # True anomaly (use argument of latitude for near-circular orbits)
    if e > 1e-10:
        nu = math.acos(max(-1.0, min(1.0, float(np.dot(e_vec, r)) / (e * r_mag))))
        if float(np.dot(r, v)) < 0.0:
            nu = 2.0 * math.pi - nu
    else:
        nu = math.acos(max(-1.0, min(1.0, float(np.dot(N, r)) / (N_mag * r_mag))))
        if r[2] < 0.0:
            nu = 2.0 * math.pi - nu

    # True -> Eccentric anomaly (Battin's stable formula)
    E_anom = 2.0 * math.atan2(
        math.sqrt(max(0.0, 1.0 - e)) * math.sin(nu / 2.0),
        math.sqrt(max(0.0, 1.0 + e)) * math.cos(nu / 2.0),
    )

    # Mean anomaly (ensure [0, 2π))
    M = (E_anom - e * math.sin(E_anom)) % (2.0 * math.pi)

    # Mean motion: rad/s -> rad/min
    n_rad_min = math.sqrt(MU_KM3_S2 / (a ** 3)) * 60.0

    sat = Satrec()
    sat.sgp4init(
        WGS84,
        "i",                        # opsmode: improved
        norad_id,
        epoch_jd - 2433281.5,       # days from 1949-12-31 00:00 UT
        bstar,
        0.0,                        # ndot
        0.0,                        # nddot
        e,
        argp,
        inc,
        M,
        n_rad_min,
        raan,
    )
    return sat


def _perturbed_record(
    r_km: np.ndarray,
    v_km_s: np.ndarray,
    original_rec: dict,
) -> dict:
    """
    Build a GP-record-style dict for the post-maneuver satellite.

    Only PERIAPSIS, APOAPSIS, and INCLINATION are recomputed from the perturbed
    state; all other fields are inherited from the original record so the object
    passes through existing screening logic correctly.
    """
    r = np.asarray(r_km, dtype=float)
    v = np.asarray(v_km_s, dtype=float)

    r_mag = float(np.linalg.norm(r))
    v_mag = float(np.linalg.norm(v))
    h     = np.cross(r, v)
    h_mag = float(np.linalg.norm(h))

    e_vec  = (np.cross(v, h) / MU_KM3_S2) - (r / r_mag)
    e      = float(np.linalg.norm(e_vec))
    energy = v_mag ** 2 / 2.0 - MU_KM3_S2 / r_mag
    a      = -MU_KM3_S2 / (2.0 * energy)

    inc_deg      = math.degrees(math.acos(max(-1.0, min(1.0, h[2] / h_mag))))
    periapsis_km = a * (1.0 - e) - EARTH_RADIUS_KM
    apoapsis_km  = a * (1.0 + e) - EARTH_RADIUS_KM

    rec = dict(original_rec)
    rec["PERIAPSIS"]   = str(round(periapsis_km, 3))
    rec["APOAPSIS"]    = str(round(apoapsis_km, 3))
    rec["INCLINATION"] = str(round(inc_deg, 4))
    return rec


# ── Screening (duplicated from main.py to avoid circular import) ──────────────

def _screen(primary_rec: dict, catalog: list[dict]) -> list[dict]:
    """
    Filter catalog against the post-maneuver primary record using the same
    altitude-band-overlap and inclination checks as main._screen_catalog.
    """
    try:
        peri_a = float(primary_rec["PERIAPSIS"])
        apo_a  = float(primary_rec["APOAPSIS"])
        inc_a  = float(primary_rec["INCLINATION"])
    except (KeyError, ValueError, TypeError):
        return []

    out: list[dict] = []
    for rec in catalog:
        try:
            peri_b = float(rec["PERIAPSIS"])
            apo_b  = float(rec["APOAPSIS"])
            inc_b  = float(rec["INCLINATION"])
        except (KeyError, ValueError, TypeError):
            continue

        if apo_a + ALT_TOLERANCE_KM < peri_b:
            continue
        if apo_b + ALT_TOLERANCE_KM < peri_a:
            continue

        polar = inc_a >= POLAR_THRESHOLD_DEG and inc_b >= POLAR_THRESHOLD_DEG
        if not polar and abs(inc_a - inc_b) > INC_TOLERANCE_DEG:
            continue

        out.append(rec)
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def compute_cascade(
    event: dict,
    maneuver: dict,
    primary_rec: dict,
    primary_sat: Satrec,
    catalog_records: list[dict],
    sat_by_norad: dict,
    original_events: list[dict],
    t_start: datetime,
) -> dict:
    """
    Compute downstream conjunction risks introduced or worsened by a maneuver.

    Args:
        event:           The conjunction event being mitigated.
        maneuver:        One option dict from compute_maneuvers() output.
        primary_rec:     GP record dict for the primary satellite.
        primary_sat:     sgp4 Satrec for the primary satellite.
        catalog_records: List of catalog GP record dicts (from pipeline cache).
        sat_by_norad:    Dict mapping NORAD_CAT_ID str -> Satrec.
        original_events: All conjunction events from the original pipeline run.
        t_start:         Pipeline run time used as the maneuver burn epoch.

    Returns:
        Dict containing: event_id, norad_id, primary_name, maneuver_label,
        delta_v_ms, candidates_screened, cascade_risks (list, sorted by miss
        distance ascending).
    """
    delta_v_ms    = float(maneuver.get("delta_v_ms", 0.0))
    maneuver_label = maneuver.get("label", "Unknown")

    # 1. Propagate primary to burn epoch
    state = propagate_at(primary_sat, t_start)
    if state is None:
        return {
            "event_id":            event.get("event_id", ""),
            "norad_id":            event.get("primary", {}).get("norad_id"),
            "primary_name":        event.get("primary", {}).get("name", ""),
            "maneuver_label":      maneuver_label,
            "delta_v_ms":          delta_v_ms,
            "error":               "Could not propagate primary satellite to burn epoch",
            "candidates_screened": 0,
            "cascade_risks":       [],
        }

    r, v = state

    # 2. Apply delta_v along the along-track (velocity unit vector) direction
    v_mag        = float(np.linalg.norm(v))
    along_track  = v / v_mag
    v_perturbed  = v + (delta_v_ms / 1000.0) * along_track   # km/s

    # 3. Compute Julian date of burn epoch and convert perturbed state to Satrec
    jd, fr = _jday(
        t_start.year, t_start.month, t_start.day,
        t_start.hour, t_start.minute,
        t_start.second + t_start.microsecond / 1e6,
    )
    epoch_jd = jd + fr
    bstar    = float(primary_rec.get("BSTAR", 1e-5))
    post_sat = _rv_to_satrec(r, v_perturbed, epoch_jd, bstar=bstar)

    # 4. Build a lightweight GP record with updated orbital elements for screening
    post_rec = _perturbed_record(r, v_perturbed, primary_rec)

    # 5. Screen post-maneuver satellite against the threat catalog
    candidates = _screen(post_rec, catalog_records)

    # 6. Index original conjunctions by secondary NORAD ID for comparison
    original_by_norad: dict[str, float] = {
        str(ev["secondary"]["norad_id"]): ev["miss_distance_km"]
        for ev in original_events
    }

    # 7. Run TCA on each candidate; classify new or worsened risks
    cascade_risks: list[dict] = []

    for cat_rec in candidates:
        sec_norad = str(cat_rec.get("NORAD_CAT_ID", ""))
        sb = sat_by_norad.get(sec_norad)
        if sb is None:
            continue

        tca = find_tca(post_rec, post_sat, cat_rec, sb, t_start)
        if tca is None:
            continue

        new_miss = tca["miss_distance_km"]
        if new_miss > CASCADE_MISS_KM:
            continue

        original_miss: Optional[float] = original_by_norad.get(sec_norad)

        if original_miss is None:
            risk_type = "new"
        elif new_miss < original_miss:
            risk_type = "worsened"
        else:
            continue     # existing conjunction, not made worse — not a cascade risk

        cascade_risks.append({
            "norad_id":               int(sec_norad) if sec_norad.isdigit() else sec_norad,
            "name":                   cat_rec.get("OBJECT_NAME", ""),
            "object_type":            cat_rec.get("OBJECT_TYPE", ""),
            "miss_distance_km":       round(new_miss, 4),
            "original_miss_km":       round(original_miss, 4) if original_miss is not None else None,
            "risk_type":              risk_type,
            "tca_utc":                tca["tca_utc"],
            "relative_velocity_km_s": round(tca["relative_velocity_km_s"], 4),
        })

    cascade_risks.sort(key=lambda x: x["miss_distance_km"])

    return {
        "event_id":            event.get("event_id", ""),
        "norad_id":            event.get("primary", {}).get("norad_id"),
        "primary_name":        event.get("primary", {}).get("name", ""),
        "maneuver_label":      maneuver_label,
        "delta_v_ms":          delta_v_ms,
        "candidates_screened": len(candidates),
        "cascade_risks":       cascade_risks,
    }
