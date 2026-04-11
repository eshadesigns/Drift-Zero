"""
backend/shield/screen.py

Filters a list of Space-Track GP records down to candidate conjunction pairs
worth running TCA analysis on. Designed to be cheap — no propagation here,
only metadata comparisons.

Screening criteria
------------------
1. Altitude band overlap:
   Object A and Object B must have overlapping altitude bands within 50 km.
   Band = [PERIAPSIS - 50, APOAPSIS + 50] (km above Earth's surface).

2. Inclination filter (one of the following must be true):
   a. |inc_a - inc_b| <= 10 degrees  (similar orbital planes can converge)
   b. Both inclinations >= 80 degrees (near-polar objects cross all longitudes
      and can encounter each other regardless of RAAN difference)

Self-pairs and duplicate pairs (a,b) / (b,a) are excluded.

Input
-----
List of dicts with at minimum:
    NORAD_CAT_ID : int | str
    APOAPSIS     : float | str   (km, geodetic altitude of apoapsis)
    PERIAPSIS    : float | str   (km, geodetic altitude of periapsis)
    INCLINATION  : float | str   (degrees)

Output
------
List of (record_a, record_b) tuples — candidates for TCA computation.
"""

from __future__ import annotations

ALT_TOLERANCE_KM = 50.0
INC_TOLERANCE_DEG = 10.0
POLAR_THRESHOLD_DEG = 80.0


def _floats(record: dict, *keys: str) -> tuple[float, ...]:
    """Extract and cast multiple fields to float from a GP record."""
    return tuple(float(record[k]) for k in keys)


def screen(records: list[dict]) -> list[tuple[dict, dict]]:
    """
    Return candidate conjunction pairs from a list of GP records.

    Pairs where either object is missing APOAPSIS, PERIAPSIS, or INCLINATION
    are silently skipped — bad data should not crash the pipeline.
    """
    # Pre-parse to avoid repeated float() calls in the O(n²) loop
    parsed: list[tuple[dict, float, float, float]] = []  # (record, apo, peri, inc)
    for rec in records:
        try:
            apo, peri, inc = _floats(rec, "APOAPSIS", "PERIAPSIS", "INCLINATION")
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append((rec, apo, peri, inc))

    pairs: list[tuple[dict, dict]] = []

    for i in range(len(parsed)):
        rec_a, apo_a, peri_a, inc_a = parsed[i]
        # Expanded altitude band for A
        band_a_low = peri_a - ALT_TOLERANCE_KM
        band_a_high = apo_a + ALT_TOLERANCE_KM

        for j in range(i + 1, len(parsed)):
            rec_b, apo_b, peri_b, inc_b = parsed[j]

            # ── Filter 1: altitude band overlap ──────────────────────────────
            band_b_low = peri_b - ALT_TOLERANCE_KM
            band_b_high = apo_b + ALT_TOLERANCE_KM

            # Bands overlap when neither is entirely above or below the other
            if band_a_high < band_b_low or band_b_high < band_a_low:
                continue

            # ── Filter 2: inclination ─────────────────────────────────────────
            inc_diff = abs(inc_a - inc_b)
            similar_plane = inc_diff <= INC_TOLERANCE_DEG
            both_polar = inc_a >= POLAR_THRESHOLD_DEG and inc_b >= POLAR_THRESHOLD_DEG

            if not (similar_plane or both_polar):
                continue

            pairs.append((rec_a, rec_b))

    return pairs
