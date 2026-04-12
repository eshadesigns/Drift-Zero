"""
backend/rogue/simulation_physics.py

Builds a future orbital trajectory from a normalized TLE dict.

Designed to be isolated — no coupling to shield/ or the anomaly pipeline.
Intended future use: run post-maneuver trajectory simulations once an operator
selects an optimal maneuver option.

Input: normalized TLE dict produced by rogue.feature_engineering.normalize_tle_row
       (must include arg_of_pericenter and mean_anomaly)

Output: list of TrajectoryPoint(datetime, r, v) in TEME frame (km, km/s)
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
from sgp4.api import Satrec, WGS72, jday


@dataclass
class TrajectoryPoint:
    t: datetime          # UTC
    r: np.ndarray        # position vector, km, TEME frame
    v: np.ndarray        # velocity vector, km/s, TEME frame


def _days_since_1950(epoch: datetime) -> float:
    """Convert a UTC datetime to days from Jan 0.0, 1950 (SGP4 internal epoch format)."""
    ref = datetime(1950, 1, 1, tzinfo=timezone.utc)
    epoch_utc = epoch.replace(tzinfo=timezone.utc) if epoch.tzinfo is None else epoch.astimezone(timezone.utc)
    return (epoch_utc - ref).total_seconds() / 86400.0


def build_satrec(tle: dict, norad_id: int = 0) -> Satrec:
    """
    Construct an sgp4 Satrec from a normalized TLE dict.

    Required keys:
        epoch, mean_motion, eccentricity, inclination,
        raan, arg_of_pericenter, mean_anomaly, bstar

    mean_motion in rev/day (Space-Track units).
    Angles in degrees (Space-Track units).
    """
    deg2rad = math.pi / 180.0

    # SGP4 wants mean motion in rad/min
    xno_kozai = tle['mean_motion'] * 2.0 * math.pi / (24.0 * 60.0)

    sat = Satrec()
    sat.sgp4init(
        WGS72,                          # gravity model
        'i',                            # opsmode: improved
        norad_id,                       # satellite number
        _days_since_1950(tle['epoch']), # epoch (days from Jan 0.0 1950)
        tle['bstar'],                   # drag term
        0.0,                            # ndot  (1st deriv mean motion) — not in normalized dict
        0.0,                            # nddot (2nd deriv mean motion) — not in normalized dict
        tle['eccentricity'],
        tle['arg_of_pericenter'] * deg2rad,
        tle['inclination']       * deg2rad,
        tle['mean_anomaly']      * deg2rad,
        xno_kozai,
        tle['raan']              * deg2rad,
    )
    return sat


def propagate_trajectory(
    tle: dict,
    t_start: datetime,
    hours: float,
    step_s: float = 60.0,
    norad_id: int = 0,
) -> list[TrajectoryPoint]:
    """
    Propagate a satellite's orbit forward in time from t_start.

    Args:
        tle:      normalized TLE dict (from normalize_tle_row, with all 6 elements)
        t_start:  start time (UTC)
        hours:    how far forward to propagate
        step_s:   time step in seconds (default 60)
        norad_id: optional NORAD ID to tag the Satrec

    Returns:
        List of TrajectoryPoint. Steps where SGP4 errors occur are silently skipped.
    """
    sat = build_satrec(tle, norad_id=norad_id)

    t_utc = (
        t_start.replace(tzinfo=timezone.utc)
        if t_start.tzinfo is None
        else t_start.astimezone(timezone.utc)
    )

    total_steps = int(hours * 3600 / step_s)
    results = []

    for i in range(total_steps + 1):
        t = t_utc + timedelta(seconds=i * step_s)
        jd, fr = jday(
            t.year, t.month, t.day,
            t.hour, t.minute,
            t.second + t.microsecond / 1e6,
        )
        e, r, v = sat.sgp4(jd, fr)
        if e != 0:
            continue
        results.append(TrajectoryPoint(
            t=t,
            r=np.array(r),
            v=np.array(v),
        ))

    return results


def propagate_at(tle: dict, t: datetime, norad_id: int = 0) -> Optional[TrajectoryPoint]:
    """
    Propagate to a single point in time.

    Returns None if SGP4 reports an error (decayed orbit, bad epoch, etc.).
    """
    sat = build_satrec(tle, norad_id=norad_id)

    t_utc = t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)
    jd, fr = jday(
        t_utc.year, t_utc.month, t_utc.day,
        t_utc.hour, t_utc.minute,
        t_utc.second + t_utc.microsecond / 1e6,
    )
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        return None

    return TrajectoryPoint(t=t_utc, r=np.array(r), v=np.array(v))