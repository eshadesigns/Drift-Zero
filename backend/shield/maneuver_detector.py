"""
maneuver_detector.py

Detects maneuver events from a time-ordered sequence of TLE records per satellite.
A maneuver is flagged when epoch-to-epoch orbital element deltas exceed thresholds
that cannot be explained by natural perturbations alone.

Reuses the delta-v proxy formula established in rogue/feature_engineering.py.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

# ── Thresholds ────────────────────────────────────────────────────────────────

DELTA_MM_THRESHOLD   = 0.0005  # rev/day  — calibrated against Starlink p90 distribution
DELTA_INC_THRESHOLD  = 0.005   # degrees  — plane change
DELTA_ECC_THRESHOLD  = 0.0002  # unitless — perigee/apogee raise

# ── Operator extraction ───────────────────────────────────────────────────────

# Known constellation prefixes to canonical operator names
OPERATOR_ALIASES: dict[str, str] = {
    "STARLINK":    "STARLINK",
    "ONEWEB":      "ONEWEB",
    "IRIDIUM":     "IRIDIUM",
    "GLOBALSTAR":  "GLOBALSTAR",
    "GPS":         "GPS",
    "GLONASS":     "GLONASS",
    "BEIDOU":      "BEIDOU",
    "GALILEO":     "GALILEO",
    "COSMOS":      "COSMOS",
    "SES":         "SES",
    "INTELSAT":    "INTELSAT",
    "TELESAT":     "TELESAT",
    "EUTELSAT":    "EUTELSAT",
    "SPIRE":       "SPIRE",
    "PLANET":      "PLANET",
    "SWARM":       "SWARM",
    "ICEYE":       "ICEYE",
    "CAPELLA":     "CAPELLA",
    "UMBRA":       "UMBRA",
    "ISS":         "ISS",
    "TIANHE":      "CSS",
    "FENGYUN":     "FENGYUN",
}

_OPERATOR_RE = re.compile(
    r"^(" + "|".join(re.escape(k) for k in OPERATOR_ALIASES) + r")[\s\-_]",
    re.IGNORECASE,
)


def extract_operator(object_name: str, country_code: str = "") -> str:
    """
    Derives operator name from OBJECT_NAME.
    Falls back to COUNTRY_CODE if no known prefix matches.
    """
    if object_name:
        m = _OPERATOR_RE.match(object_name.strip())
        if m:
            return OPERATOR_ALIASES[m.group(1).upper()]
        # Try exact match on the full name (e.g. "ISS (ZARYA)")
        upper = object_name.upper()
        for prefix, canonical in OPERATOR_ALIASES.items():
            if upper.startswith(prefix):
                return canonical
    return country_code.upper() if country_code else "UNKNOWN"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ManeuverEvent:
    norad_id: str
    object_name: str
    operator: str
    epoch_pre: datetime
    epoch_post: datetime
    time_gap_hours: float
    delta_mean_motion: float    # rev/day
    delta_inclination: float    # degrees
    delta_eccentricity: float
    delta_raan: float           # degrees
    delta_bstar: float
    estimated_delta_v: float    # m/s proxy


# ── Detector ──────────────────────────────────────────────────────────────────

class ManeuverDetector:
    """
    Detects maneuvers from a DataFrame of TLE history records.

    Expected columns (subset of drift_zero.orbital.tle_history):
        NORAD_CAT_ID, OBJECT_NAME, COUNTRY_CODE, EPOCH,
        MEAN_MOTION, INCLINATION, ECCENTRICITY, RA_OF_ASC_NODE, BSTAR
    """

    def detect(self, df: pd.DataFrame) -> list[ManeuverEvent]:
        """
        Runs maneuver detection across all satellites in the DataFrame.
        df must be sorted by NORAD_CAT_ID, EPOCH ascending.
        Returns a list of ManeuverEvent instances.
        """
        events: list[ManeuverEvent] = []

        required = {"NORAD_CAT_ID", "EPOCH", "MEAN_MOTION", "INCLINATION",
                    "ECCENTRICITY", "RA_OF_ASC_NODE", "BSTAR"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df.sort_values(["NORAD_CAT_ID", "EPOCH"]).reset_index(drop=True)

        for norad_id, group in df.groupby("NORAD_CAT_ID", sort=False):
            group = group.reset_index(drop=True)
            if len(group) < 2:
                continue

            object_name  = str(group["OBJECT_NAME"].iloc[0]) if "OBJECT_NAME" in group.columns else ""
            country_code = str(group["COUNTRY_CODE"].iloc[0]) if "COUNTRY_CODE" in group.columns else ""
            operator     = extract_operator(object_name, country_code)

            for i in range(1, len(group)):
                prev = group.iloc[i - 1]
                curr = group.iloc[i]

                delta_mm   = float(curr["MEAN_MOTION"])   - float(prev["MEAN_MOTION"])
                delta_inc  = float(curr["INCLINATION"])   - float(prev["INCLINATION"])
                delta_ecc  = float(curr["ECCENTRICITY"])  - float(prev["ECCENTRICITY"])
                delta_raan = float(curr["RA_OF_ASC_NODE"]) - float(prev["RA_OF_ASC_NODE"])
                delta_bstar = float(curr["BSTAR"])        - float(prev["BSTAR"])

                # Maneuver flag: any threshold exceeded
                if (
                    abs(delta_mm)  <= DELTA_MM_THRESHOLD and
                    abs(delta_inc) <= DELTA_INC_THRESHOLD and
                    abs(delta_ecc) <= DELTA_ECC_THRESHOLD
                ):
                    continue

                # Delta-v proxy — same formula as rogue/feature_engineering.py
                mm_prev = float(prev["MEAN_MOTION"])
                v_orb_km_s = 7.784 * (mm_prev / 15.0) ** (1 / 3)
                dv = abs(delta_mm / mm_prev) * v_orb_km_s * 1000 if mm_prev > 0 else 0.0

                epoch_pre  = prev["EPOCH"]
                epoch_post = curr["EPOCH"]
                if hasattr(epoch_pre, "to_pydatetime"):
                    epoch_pre  = epoch_pre.to_pydatetime()
                    epoch_post = epoch_post.to_pydatetime()

                time_gap_h = (
                    (epoch_post - epoch_pre).total_seconds() / 3600
                    if isinstance(epoch_post, datetime) and isinstance(epoch_pre, datetime)
                    else 0.0
                )

                events.append(ManeuverEvent(
                    norad_id=str(norad_id),
                    object_name=object_name,
                    operator=operator,
                    epoch_pre=epoch_pre,
                    epoch_post=epoch_post,
                    time_gap_hours=time_gap_h,
                    delta_mean_motion=delta_mm,
                    delta_inclination=delta_inc,
                    delta_eccentricity=delta_ecc,
                    delta_raan=delta_raan,
                    delta_bstar=delta_bstar,
                    estimated_delta_v=dv,
                ))

        return events


def events_to_dataframe(events: list[ManeuverEvent]) -> pd.DataFrame:
    """Converts a list of ManeuverEvent instances to a DataFrame for upload."""
    if not events:
        return pd.DataFrame(columns=[
            "norad_id", "object_name", "operator",
            "epoch_pre", "epoch_post", "time_gap_hours",
            "delta_mean_motion", "delta_inclination", "delta_eccentricity",
            "delta_raan", "delta_bstar", "estimated_delta_v",
        ])
    return pd.DataFrame([vars(e) for e in events])
