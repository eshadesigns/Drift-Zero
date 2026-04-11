"""
backend/shield/tca.py

Finds the Time of Closest Approach (TCA) and miss distance for a satellite pair
over a 24-hour window from a given start time.

Algorithm
---------
1. Coarse scan: propagate both satellites at 60-second steps over 24 hours.
   Compute Euclidean distance between position vectors at each shared step.
   Record the step with the minimum distance.

2. Fine refinement: bisection search within ±120 seconds of the coarse minimum,
   iteratively halving the window until it is narrower than 1 second.
   At each bisection step, evaluate the midpoint and the quarter-points to
   determine which half of the interval contains the true minimum.

Steps where either satellite fails to propagate are silently skipped.
Returns None if no valid coarse step exists.

Output
------
{
    "tca_utc":             str    # ISO 8601, e.g. "2026-04-12T03:47:22.341000Z"
    "miss_distance_km":    float  # always >= 0
    "relative_velocity_km_s": float  # magnitude of (v_a - v_b) at TCA
}
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
from sgp4.api import Satrec

from backend.shield.propagate import propagate_at

COARSE_STEP_S = 60.0
WINDOW_S = 24 * 3600
BISECT_HALF_WINDOW_S = 120.0
BISECT_TOLERANCE_S = 1.0


def _dist(sat_a: Satrec, sat_b: Satrec, t: datetime) -> Optional[tuple[float, np.ndarray, np.ndarray]]:
    """
    Return (distance_km, r_a, r_b) at time t, or None if either sat fails.
    """
    res_a = propagate_at(sat_a, t)
    res_b = propagate_at(sat_b, t)
    if res_a is None or res_b is None:
        return None
    r_a, _ = res_a
    r_b, _ = res_b
    return float(np.linalg.norm(r_a - r_b)), r_a, r_b


def find_tca(
    rec_a: dict,
    sat_a: Satrec,
    rec_b: dict,
    sat_b: Satrec,
    t_start: datetime,
) -> Optional[dict]:
    """
    Find TCA for a satellite pair over the 24 hours starting at t_start.

    Args:
        rec_a, rec_b: Space-Track GP record dicts (used for context only here)
        sat_a, sat_b: sgp4 Satrec objects
        t_start:      start of search window (UTC)

    Returns:
        dict with tca_utc, miss_distance_km, relative_velocity_km_s,
        or None if no valid propagation steps exist.
    """
    t_utc = (
        t_start.replace(tzinfo=timezone.utc)
        if t_start.tzinfo is None
        else t_start.astimezone(timezone.utc)
    )

    # ── Coarse scan ───────────────────────────────────────────────────────────
    total_steps = int(WINDOW_S / COARSE_STEP_S)
    best_t: Optional[datetime] = None
    best_dist = float("inf")

    for i in range(total_steps + 1):
        t = t_utc + timedelta(seconds=i * COARSE_STEP_S)
        result = _dist(sat_a, sat_b, t)
        if result is None:
            continue
        d, _, _ = result
        if d < best_dist:
            best_dist = d
            best_t = t

    if best_t is None:
        return None

    # ── Fine refinement: bisection within ±120 s of coarse minimum ───────────
    lo = best_t - timedelta(seconds=BISECT_HALF_WINDOW_S)
    hi = best_t + timedelta(seconds=BISECT_HALF_WINDOW_S)

    while (hi - lo).total_seconds() > BISECT_TOLERANCE_S:
        span = (hi - lo).total_seconds()
        t_q1 = lo + timedelta(seconds=span * 0.25)
        t_mid = lo + timedelta(seconds=span * 0.5)
        t_q3 = lo + timedelta(seconds=span * 0.75)

        # Evaluate distance at the three interior points; fall back to coarse
        # best_dist if propagation fails at a quarter-point.
        d_q1 = (_dist(sat_a, sat_b, t_q1) or (best_dist, None, None))[0]
        d_mid = (_dist(sat_a, sat_b, t_mid) or (best_dist, None, None))[0]
        d_q3 = (_dist(sat_a, sat_b, t_q3) or (best_dist, None, None))[0]

        # The minimum lives in the quarter containing the smallest distance
        min_d = min(d_q1, d_mid, d_q3)
        if min_d == d_q1:
            hi = t_mid           # minimum is in [lo, mid]
        elif min_d == d_q3:
            lo = t_mid           # minimum is in [mid, hi]
        else:
            lo = t_q1            # minimum is in [q1, q3]
            hi = t_q3

    # ── Evaluate at refined midpoint ──────────────────────────────────────────
    t_tca = lo + timedelta(seconds=(hi - lo).total_seconds() / 2.0)

    res_a = propagate_at(sat_a, t_tca)
    res_b = propagate_at(sat_b, t_tca)

    # Fall back to coarse best if fine midpoint fails propagation
    if res_a is None or res_b is None:
        t_tca = best_t
        res_a = propagate_at(sat_a, t_tca)
        res_b = propagate_at(sat_b, t_tca)
        if res_a is None or res_b is None:
            return None

    r_a, v_a = res_a
    r_b, v_b = res_b

    miss_distance_km = float(np.linalg.norm(r_a - r_b))
    relative_velocity_km_s = float(np.linalg.norm(v_a - v_b))

    return {
        "tca_utc": t_tca.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "miss_distance_km": miss_distance_km,
        "relative_velocity_km_s": relative_velocity_km_s,
    }
