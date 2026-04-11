"""
backend/shield/propagate.py

Turns Space-Track GP records into position/velocity vectors using SGP4.

Input record shape (dict):
    {
        "TLE_LINE1": str,
        "TLE_LINE2": str,
        "OBJECT_NAME": str,
        "NORAD_CAT_ID": int | str,
        "EPOCH": str  # ISO8601, informational only
    }

Returns TEME-frame vectors (km, km/s) as numpy arrays.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np
from sgp4.api import Satrec, SGP4_ERRORS


def parse_satrec(record: dict) -> Optional[Satrec]:
    """
    Build an sgp4 Satrec from a Space-Track GP record.
    Returns None if the TLE lines are malformed.
    """
    line1 = record.get("TLE_LINE1", "").strip()
    line2 = record.get("TLE_LINE2", "").strip()
    if not line1 or not line2:
        return None
    return Satrec.twoline2rv(line1, line2)


def propagate_at(sat: Satrec, t: datetime) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    Propagate a satellite to a single point in time.

    Args:
        sat: sgp4 Satrec object
        t:   UTC datetime

    Returns:
        (r, v) where r is position (km) and v is velocity (km/s) in TEME frame,
        or None if sgp4 returns a non-zero error code.
    """
    t_utc = t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)

    # sgp4 wants Julian date split into whole + fractional parts
    from sgp4.api import jday
    jd, fr = jday(
        t_utc.year,
        t_utc.month,
        t_utc.day,
        t_utc.hour,
        t_utc.minute,
        t_utc.second + t_utc.microsecond / 1e6,
    )

    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        return None

    return np.array(r), np.array(v)


def propagate_window(
    sat: Satrec,
    t_start: datetime,
    hours: float,
    step_s: float = 60.0,
) -> list[tuple[datetime, np.ndarray, np.ndarray]]:
    """
    Propagate a satellite over a time window at fixed step intervals.

    Args:
        sat:    sgp4 Satrec object
        t_start: start of window (UTC)
        hours:  window length in hours
        step_s: propagation step in seconds (default 60)

    Returns:
        List of (datetime, r, v) tuples. Steps where SGP4 errors occur are
        silently skipped (error code != 0 means decayed / invalid epoch).
    """
    t_utc = (
        t_start.replace(tzinfo=timezone.utc)
        if t_start.tzinfo is None
        else t_start.astimezone(timezone.utc)
    )

    total_steps = int(hours * 3600 / step_s)
    results = []

    for i in range(total_steps + 1):
        t = t_utc + timedelta(seconds=i * step_s)
        point = propagate_at(sat, t)
        if point is None:
            continue
        r, v = point
        results.append((t, r, v))

    return results
