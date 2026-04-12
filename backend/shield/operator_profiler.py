"""
operator_profiler.py

Aggregates maneuver events by operator to build behavioral profiles.
When a conjunction is flagged by the Shield conjunction engine, call
get_context_string() to surface operator history in the alert UI.

Example output:
    "STARLINK maneuvers ~2.3×/sat/month across 6,200 satellites —
     high likelihood of self-clearing."
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class OperatorProfile:
    operator: str
    total_satellites: int
    total_maneuvers_180d: int
    maneuver_rate_per_sat_per_month: float   # maneuvers / satellite / month
    median_delta_v_ms: float                  # m/s
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def self_clear_likelihood(self) -> str:
        """
        Heuristic label for how likely this operator is to maneuver away
        from a conjunction without being prompted.
        """
        rate = self.maneuver_rate_per_sat_per_month
        if rate >= 1.0:
            return "HIGH"
        elif rate >= 0.2:
            return "MODERATE"
        else:
            return "LOW"

    def context_string(self) -> str:
        """
        Human-readable context surfaced in the conjunction alert.
        e.g. "STARLINK maneuvers ~2.3×/sat/month — HIGH likelihood of self-clearing."
        """
        likelihood = self.self_clear_likelihood()
        return (
            f"{self.operator} maneuvers ~{self.maneuver_rate_per_sat_per_month:.1f}×/sat/month "
            f"({self.total_maneuvers_180d:,} maneuvers across {self.total_satellites:,} satellites "
            f"in 180 days) — {likelihood} likelihood of self-clearing."
        )


# ── Profiler ──────────────────────────────────────────────────────────────────

class OperatorProfiler:
    """
    Builds and queries operator behavioral profiles from maneuver events.

    Usage:
        profiler = OperatorProfiler()
        profiles = profiler.build_profiles(maneuver_events_df)

        # At conjunction time:
        profile = profiler.get_profile_for_norad(norad_id, tle_live_df)
        if profile:
            print(profile.context_string())
    """

    def __init__(self):
        # operator name -> OperatorProfile
        self._profiles: dict[str, OperatorProfile] = {}
        # norad_id -> operator name (populated from tle_live)
        self._norad_operator_map: dict[str, str] = {}

    # ── Build ──────────────────────────────────────────────────────────────

    def build_profiles(self, maneuver_df: pd.DataFrame) -> dict[str, OperatorProfile]:
        """
        Computes per-operator profiles from a maneuver_events DataFrame.

        Expected columns:
            norad_id, operator, estimated_delta_v
            (all other columns optional)

        Returns a dict of operator -> OperatorProfile (also stored internally).
        """
        if maneuver_df.empty:
            self._profiles = {}
            return self._profiles

        required = {"norad_id", "operator", "estimated_delta_v"}
        missing = required - set(maneuver_df.columns)
        if missing:
            raise ValueError(f"maneuver_df missing columns: {missing}")

        grouped = maneuver_df.groupby("operator")

        profiles: dict[str, OperatorProfile] = {}
        for operator, grp in grouped:
            total_sats      = grp["norad_id"].nunique()
            total_maneuvers = len(grp)
            rate            = total_maneuvers / max(total_sats, 1) / 6.0  # 180d = 6 months
            median_dv       = float(grp["estimated_delta_v"].median())

            profiles[operator] = OperatorProfile(
                operator=operator,
                total_satellites=total_sats,
                total_maneuvers_180d=total_maneuvers,
                maneuver_rate_per_sat_per_month=round(rate, 3),
                median_delta_v_ms=round(median_dv, 2),
            )

        self._profiles = profiles
        return profiles

    def load_profiles(self, profiles_df: pd.DataFrame) -> None:
        """
        Populates the internal profile store from the operator_profiles Delta table.

        Expected columns match operator_profiles schema:
            operator, total_satellites, total_maneuvers_180d,
            maneuver_rate_per_sat_per_month, median_delta_v_ms, last_updated
        """
        self._profiles = {}
        for _, row in profiles_df.iterrows():
            op = str(row["operator"])
            last_upd = row.get("last_updated")
            if pd.isna(last_upd) if hasattr(pd, "isna") else last_upd is None:
                last_upd = datetime.now(timezone.utc)
            elif hasattr(last_upd, "to_pydatetime"):
                last_upd = last_upd.to_pydatetime()

            self._profiles[op] = OperatorProfile(
                operator=op,
                total_satellites=int(row["total_satellites"]),
                total_maneuvers_180d=int(row["total_maneuvers_180d"]),
                maneuver_rate_per_sat_per_month=float(row["maneuver_rate_per_sat_per_month"]),
                median_delta_v_ms=float(row["median_delta_v_ms"]),
                last_updated=last_upd,
            )

    def build_norad_map(self, tle_df: pd.DataFrame) -> None:
        """
        Builds a NORAD_CAT_ID -> operator lookup from tle_live or tle_history.
        Required before calling get_profile_for_norad().

        Expected columns: NORAD_CAT_ID, OBJECT_NAME, COUNTRY_CODE (optional)
        """
        from backend.shield.maneuver_detector import extract_operator

        self._norad_operator_map = {}
        for _, row in tle_df.iterrows():
            norad = str(row["NORAD_CAT_ID"])
            name  = str(row.get("OBJECT_NAME", ""))
            cc    = str(row.get("COUNTRY_CODE", ""))
            self._norad_operator_map[norad] = extract_operator(name, cc)

    # ── Query ──────────────────────────────────────────────────────────────

    def get_profile(self, operator: str) -> Optional[OperatorProfile]:
        """Returns the profile for a given operator name, or None."""
        return self._profiles.get(operator)

    def get_profile_for_norad(self, norad_id: str) -> Optional[OperatorProfile]:
        """
        Resolves NORAD ID -> operator -> OperatorProfile.
        Requires build_norad_map() to have been called first.
        """
        operator = self._norad_operator_map.get(str(norad_id))
        if not operator:
            return None
        return self._profiles.get(operator)

    def get_context_string(self, norad_id: str) -> str:
        """
        Convenience method: returns a ready-to-display context string for a
        threatening satellite's operator, for use in conjunction alerts.

        Returns a fallback string if the operator is unknown.
        """
        profile = self.get_profile_for_norad(str(norad_id))
        if profile:
            return profile.context_string()
        operator = self._norad_operator_map.get(str(norad_id), "Unknown operator")
        return f"{operator} — no historical maneuver data available."

    # ── Serialisation ──────────────────────────────────────────────────────

    def profiles_to_dataframe(self) -> pd.DataFrame:
        """Exports current profiles to a DataFrame for upload to Databricks."""
        if not self._profiles:
            return pd.DataFrame(columns=[
                "operator", "total_satellites", "total_maneuvers_180d",
                "maneuver_rate_per_sat_per_month", "median_delta_v_ms", "last_updated",
            ])
        rows = []
        for p in self._profiles.values():
            rows.append({
                "operator":                        p.operator,
                "total_satellites":                p.total_satellites,
                "total_maneuvers_180d":            p.total_maneuvers_180d,
                "maneuver_rate_per_sat_per_month": p.maneuver_rate_per_sat_per_month,
                "median_delta_v_ms":               p.median_delta_v_ms,
                "last_updated":                    p.last_updated,
            })
        df = pd.DataFrame(rows)
        # Databricks requires microsecond precision — cast down from nanoseconds
        df["last_updated"] = pd.to_datetime(df["last_updated"], utc=True).astype("datetime64[us, UTC]")
        return df
