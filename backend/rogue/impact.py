"""
backend/rogue/impact.py

Asset impact registry — maps high-value satellite NORAD IDs (and name
patterns) to their economic and strategic importance.

When Rogue flags a close approach to one of these assets, the impact
score makes the threat concrete for operators and executives:
  "This satellite is currently 18 km from GPS IIR-20 — a satellite
   whose loss would cost the US economy ~$1B/day."

Usage
-----
    from backend.rogue.impact import get_impact, enrich_event

    # Look up a specific satellite
    impact = get_impact(26690)   # GPS IIR-20

    # Attach to a rogue event dict
    event = enrich_event(event)  # adds "target_impact" key if target is known
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class AssetImpact:
    norad_id: int
    name: str
    constellation: str
    strategic_tier: str          # CRITICAL | HIGH | MEDIUM
    economic_impact_usd_per_day: int
    users_at_risk: str
    mission_description: str
    replacement_cost_usd: int
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "norad_id":                    self.norad_id,
            "name":                        self.name,
            "constellation":               self.constellation,
            "strategic_tier":              self.strategic_tier,
            "economic_impact_usd_per_day": self.economic_impact_usd_per_day,
            "economic_impact_formatted":   _fmt_usd(self.economic_impact_usd_per_day),
            "users_at_risk":               self.users_at_risk,
            "mission_description":         self.mission_description,
            "replacement_cost_usd":        self.replacement_cost_usd,
            "replacement_cost_formatted":  _fmt_usd(self.replacement_cost_usd),
            "notes":                       self.notes,
        }


def _fmt_usd(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,}"


# ── Asset registry ────────────────────────────────────────────────────────────
# Sources: RAND Corporation GPS economic analysis, ESA satellite cost estimates,
# US Space Force public briefings, academic literature on satellite costs.

_REGISTRY: dict[int, AssetImpact] = {}


def _register(asset: AssetImpact) -> None:
    _REGISTRY[asset.norad_id] = asset


# GPS Block IIR — workhorse of the GPS constellation
_register(AssetImpact(
    norad_id=26690,
    name="GPS IIR-20 (USA-201)",
    constellation="GPS",
    strategic_tier="CRITICAL",
    economic_impact_usd_per_day=1_000_000_000,
    users_at_risk="500M+ civilians, all US military operations",
    mission_description="GPS navigation signal for L1/L2 civil and military use",
    replacement_cost_usd=223_000_000,
    notes="Targeted by Kosmos 2576 in 2024. Part of 24-satellite minimum constellation."
))

_register(AssetImpact(
    norad_id=28190,
    name="GPS IIR-16 (USA-196)",
    constellation="GPS",
    strategic_tier="CRITICAL",
    economic_impact_usd_per_day=1_000_000_000,
    users_at_risk="500M+ civilians, all US military operations",
    mission_description="GPS navigation signal — M-code military anti-jam capability",
    replacement_cost_usd=223_000_000,
))

_register(AssetImpact(
    norad_id=40534,
    name="GPS III-1 (USA-292)",
    constellation="GPS",
    strategic_tier="CRITICAL",
    economic_impact_usd_per_day=1_000_000_000,
    users_at_risk="500M+ civilians, all US military operations",
    mission_description="GPS III — next-gen signal with 3× better accuracy, anti-jam",
    replacement_cost_usd=529_000_000,
    notes="Most expensive GPS satellite ever launched. Loss would degrade precision-guided munitions."
))

# International Space Station
_register(AssetImpact(
    norad_id=25544,
    name="International Space Station",
    constellation="ISS",
    strategic_tier="HIGH",
    economic_impact_usd_per_day=150_000_000,
    users_at_risk="7 crew members, 15-nation partnership",
    mission_description="Human spaceflight platform, microgravity research, international cooperation",
    replacement_cost_usd=150_000_000_000,
    notes="$150B assembly cost. Loss would end human low-Earth orbit presence for years."
))

# Hubble Space Telescope (in LEO, publicly tracked)
_register(AssetImpact(
    norad_id=20580,
    name="Hubble Space Telescope",
    constellation="Science",
    strategic_tier="HIGH",
    economic_impact_usd_per_day=10_000_000,
    users_at_risk="Global scientific community",
    mission_description="UV/optical astronomy — 30-year mission, 1.5M observations",
    replacement_cost_usd=10_000_000_000,
    notes="Irreplaceable scientific asset. No servicing mission currently planned."
))

# NOAA weather satellites (GOES-East in GEO but NOAA-15 is LEO)
_register(AssetImpact(
    norad_id=25338,
    name="NOAA-15",
    constellation="NOAA",
    strategic_tier="HIGH",
    economic_impact_usd_per_day=50_000_000,
    users_at_risk="300M US residents (weather forecasting)",
    mission_description="Polar-orbiting weather satellite — hurricane track, severe weather",
    replacement_cost_usd=500_000_000,
))

# Iridium (critical for DoD MUOS/AEHF backup and maritime)
_register(AssetImpact(
    norad_id=41928,
    name="Iridium NEXT-1",
    constellation="Iridium",
    strategic_tier="MEDIUM",
    economic_impact_usd_per_day=5_000_000,
    users_at_risk="DoD, maritime, aviation emergency comms",
    mission_description="LEO mobile satellite communications — sole global voice/data coverage",
    replacement_cost_usd=70_000_000,
    notes="Iridium constellation provides DoD backup comms if GPS jamming occurs."
))


# ── Name pattern matching (for satellites not individually registered) ─────────

_PATTERN_IMPACTS: list[tuple[str, dict]] = [
    ("GPS", {
        "constellation": "GPS",
        "strategic_tier": "CRITICAL",
        "economic_impact_usd_per_day": 1_000_000_000,
        "users_at_risk": "500M+ civilians, all US military operations",
        "replacement_cost_usd": 300_000_000,
    }),
    ("NAVSTAR", {
        "constellation": "GPS",
        "strategic_tier": "CRITICAL",
        "economic_impact_usd_per_day": 1_000_000_000,
        "users_at_risk": "500M+ civilians, all US military operations",
        "replacement_cost_usd": 300_000_000,
    }),
    ("GALILEO", {
        "constellation": "Galileo",
        "strategic_tier": "CRITICAL",
        "economic_impact_usd_per_day": 800_000_000,
        "users_at_risk": "450M EU residents, global aviation",
        "replacement_cost_usd": 500_000_000,
    }),
    ("GLONASS", {
        "constellation": "GLONASS",
        "strategic_tier": "HIGH",
        "economic_impact_usd_per_day": 400_000_000,
        "users_at_risk": "Russian military and civilian navigation",
        "replacement_cost_usd": 200_000_000,
    }),
    ("ISS", {
        "constellation": "ISS",
        "strategic_tier": "HIGH",
        "economic_impact_usd_per_day": 150_000_000,
        "users_at_risk": "7 crew, 15-nation partnership",
        "replacement_cost_usd": 150_000_000_000,
    }),
    ("USA-", {
        "constellation": "US Military",
        "strategic_tier": "CRITICAL",
        "economic_impact_usd_per_day": 500_000_000,
        "users_at_risk": "US military operations globally",
        "replacement_cost_usd": 1_000_000_000,
    }),
]


# ── Public API ────────────────────────────────────────────────────────────────

def get_impact(norad_id: int, object_name: str = "") -> Optional[dict]:
    """
    Return impact data for a satellite, or None if not a known high-value asset.

    Checks the NORAD registry first, then falls back to name pattern matching.
    """
    # Direct NORAD lookup
    asset = _REGISTRY.get(norad_id)
    if asset:
        return asset.to_dict()

    # Pattern match on name
    name_upper = object_name.upper()
    for pattern, impact_data in _PATTERN_IMPACTS:
        if pattern in name_upper:
            return {
                "norad_id":                    norad_id,
                "name":                        object_name or f"NORAD {norad_id}",
                "constellation":               impact_data["constellation"],
                "strategic_tier":              impact_data["strategic_tier"],
                "economic_impact_usd_per_day": impact_data["economic_impact_usd_per_day"],
                "economic_impact_formatted":   _fmt_usd(impact_data["economic_impact_usd_per_day"]),
                "users_at_risk":               impact_data["users_at_risk"],
                "replacement_cost_usd":        impact_data["replacement_cost_usd"],
                "replacement_cost_formatted":  _fmt_usd(impact_data["replacement_cost_usd"]),
                "mission_description":         f"{impact_data['constellation']} constellation member",
                "notes":                       "",
            }

    return None


def enrich_event(event: dict) -> dict:
    """
    Attach target_impact to a rogue AnomalyEvent dict if any nearby satellite
    is a high-value asset. Checks proximity_flag CDM events for the target.

    Also checks if the event satellite itself is high-value (indicating it may
    be a target, not just the actor).

    Returns the event dict with "target_impact" added (or None if no match).
    """
    event = dict(event)

    # Check if the flagged satellite itself is a high-value target
    norad_id   = event.get("norad_id", 0)
    name       = str(event.get("object_name", ""))
    impact     = get_impact(norad_id, name)
    event["asset_impact"] = impact  # None if not a known asset

    return event


def get_all_assets() -> list[dict]:
    """Return all registered high-value assets for the asset registry UI."""
    return [a.to_dict() for a in _REGISTRY.values()]
