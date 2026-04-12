"""
pipeline/tle_ingest.py
Drift Zero — TLE Ingestion

Authenticates with Space-Track.org (cookie-based POST), fetches up to 180 days
of historical TLEs for a list of NORAD IDs, normalizes field names and types,
and persists records locally as JSON.

Output contract — each normalized TLE record is a dict with:
    norad_id      int
    object_name   str
    epoch         datetime   UTC, timezone-aware
    mean_motion   float      rev/day
    eccentricity  float
    inclination   float      degrees
    raan          float      degrees  (RA_OF_ASC_NODE)
    arg_perigee   float      degrees  (ARG_OF_PERICENTER)
    mean_anomaly  float      degrees
    bstar         float
    tle_line1     str
    tle_line2     str

These field names and types match what rogue/feature_engineering.py expects.

Assumptions:
  - Space-Track credentials are in env vars SPACETRACK_USERNAME / SPACETRACK_PASSWORD
    (or passed explicitly to SpaceTrackClient / ingest).
  - Space-Track rate-limits requests; a 0.5 s sleep is injected between satellite
    fetches as a courtesy. Do not remove for production use.
  - skyfield is used as the canonical TLE parser: epoch and orbital elements are
    extracted from the sgp4 Satrec model, not the JSON strings, to avoid
    float-string edge cases (e.g. leading-zero exponent notation in BSTAR).
  - CDM MISS_DISTANCE comes back in meters from Space-Track; we convert to km.
"""

import json
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from skyfield.api import EarthSatellite
from skyfield.api import load as skyfield_load

load_dotenv()

logger = logging.getLogger(__name__)

SPACETRACK_BASE = "https://www.space-track.org"
_DATA_DIR = Path(__file__).parent.parent / "data"


# ─── Space-Track client ────────────────────────────────────────────────────────

class SpaceTrackClient:
    """Cookie-based Space-Track.org client."""

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.environ.get("SPACETRACK_USERNAME", "")
        self.password = password or os.environ.get("SPACETRACK_PASSWORD", "")
        self.session = requests.Session()
        self._logged_in = False

    def login(self):
        if not self.username or not self.password:
            raise RuntimeError(
                "Space-Track credentials missing. "
                "Set SPACETRACK_USERNAME and SPACETRACK_PASSWORD in .env"
            )
        resp = self.session.post(
            f"{SPACETRACK_BASE}/ajaxauth/login",
            data={"identity": self.username, "password": self.password},
            timeout=30,
        )
        resp.raise_for_status()
        if "Failed" in resp.text:
            raise RuntimeError(f"Space-Track login rejected: {resp.text[:200]}")
        self._logged_in = True
        logger.info("Space-Track login OK")

    def _get(self, url: str) -> requests.Response:
        if not self._logged_in:
            self.login()
        resp = self.session.get(url, timeout=60)
        resp.raise_for_status()
        return resp

    def fetch_history(
        self, norad_ids: list[int], days: int = 180
    ) -> dict[int, list[dict]]:
        """
        Fetch historical TLEs for each NORAD ID over the last `days` days.
        Returns {norad_id: [raw_record, ...]} sorted by epoch ascending.
        """
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return self.fetch_history_range(norad_ids, start, end)

    def fetch_history_range(
        self,
        norad_ids: list[int],
        start: datetime,
        end: datetime,
    ) -> dict[int, list[dict]]:
        """
        Fetch historical TLEs for each NORAD ID over a specific date range.

        Use this for historical incident reconstruction where the relevant
        data is not in the recent N-day window.

        Args:
            norad_ids: Satellites to fetch.
            start:     Start of the date range (UTC).
            end:       End of the date range (UTC).

        Returns:
            {norad_id: [raw_record, ...]} sorted by epoch ascending.
        """
        date_range = (
            f"{start.strftime('%Y-%m-%d')}--{end.strftime('%Y-%m-%d')}"
        )

        results: dict[int, list[dict]] = {}
        for norad_id in norad_ids:
            url = (
                f"{SPACETRACK_BASE}/basicspacedata/query"
                f"/class/gp_history/NORAD_CAT_ID/{norad_id}"
                f"/EPOCH/{date_range}/orderby/EPOCH asc/format/json"
            )
            logger.info(
                f"Fetching TLE history: NORAD {norad_id} "
                f"({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})"
            )
            raw = self._get(url).json()
            results[norad_id] = raw
            logger.info(f"  -> {len(raw)} records")
            time.sleep(0.5)  # polite rate-limiting

        return results

    def fetch_cdm(self, norad_id: int) -> list[dict]:
        """Fetch upcoming CDMs where this satellite is SAT_1."""
        url = (
            f"{SPACETRACK_BASE}/basicspacedata/query"
            f"/class/cdm_public/SAT_1_ID/{norad_id}"
            f"/TCA/>now/format/json/orderby/TCA asc/limit/20"
        )
        try:
            return self._get(url).json()
        except Exception as exc:
            logger.warning(f"CDM fetch failed for NORAD {norad_id}: {exc}")
            return []


# ─── TLE parsing (skyfield) ────────────────────────────────────────────────────

_ts = None  # lazy-initialised timescale (downloading leap-second data once)


def _get_timescale():
    global _ts
    if _ts is None:
        _ts = skyfield_load.timescale()
    return _ts


def _parse_with_skyfield(line1: str, line2: str, name: str = "") -> dict:
    """
    Parse TLE lines with skyfield/sgp4 and return normalized orbital elements.
    All angles in degrees; mean_motion in rev/day.
    """
    ts = _get_timescale()
    sat = EarthSatellite(line1, line2, name, ts)
    m = sat.model  # sgp4 Satrec object

    # no_kozai is in rad/min → convert to rev/day
    mean_motion_revday = m.no_kozai * (1440.0 / (2.0 * math.pi))

    return {
        "epoch": sat.epoch.utc_datetime(),        # tz-aware UTC datetime
        "mean_motion": mean_motion_revday,
        "eccentricity": m.ecco,
        "inclination": math.degrees(m.inclo),
        "raan": math.degrees(m.nodeo),
        "arg_perigee": math.degrees(m.argpo),
        "mean_anomaly": math.degrees(m.mo),
        "bstar": m.bstar,
        "tle_line1": line1,
        "tle_line2": line2,
    }


def parse_raw_record(raw: dict) -> dict:
    """
    Normalize one raw Space-Track gp / gp_history JSON record.
    Orbital elements are taken from skyfield (parsed TLE lines) not the JSON
    floats, so the epoch and bstar representations are always canonical.
    """
    line1 = raw["TLE_LINE1"]
    line2 = raw["TLE_LINE2"]
    name = raw.get("OBJECT_NAME", "")

    parsed = _parse_with_skyfield(line1, line2, name)
    parsed["norad_id"] = int(raw["NORAD_CAT_ID"])
    parsed["object_name"] = name
    return parsed


def normalize_records(raw_records: list[dict]) -> list[dict]:
    """Parse and normalize a list of raw Space-Track records, skipping bad ones."""
    out = []
    for r in raw_records:
        try:
            out.append(parse_raw_record(r))
        except Exception as exc:
            logger.warning(
                f"Skipping TLE record (parse error): {exc} — epoch={r.get('EPOCH')}"
            )
    return out


# ─── Local persistence ─────────────────────────────────────────────────────────

def save_tles(tles_by_sat: dict[int, list[dict]], path: Path = None) -> Path:
    """
    Persist normalized TLEs to a JSON file.
    Epoch datetimes are serialized as ISO-8601 strings.
    """
    if path is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _DATA_DIR / "tle_history.json"

    serializable = {
        str(norad_id): [
            {**r, "epoch": r["epoch"].isoformat()} for r in records
        ]
        for norad_id, records in tles_by_sat.items()
    }

    with open(path, "w") as f:
        json.dump(serializable, f, indent=2)

    logger.info(f"Saved TLE history → {path}")
    return path


def load_tles(path: Path = None) -> dict[int, list[dict]]:
    """
    Load normalized TLEs from JSON, restoring epoch datetimes.
    Returns {norad_id: [record, ...]}
    """
    if path is None:
        path = _DATA_DIR / "tle_history.json"

    with open(path) as f:
        raw = json.load(f)

    result: dict[int, list[dict]] = {}
    for norad_id_str, records in raw.items():
        restored = []
        for r in records:
            r = dict(r)
            ep = datetime.fromisoformat(r["epoch"])
            if ep.tzinfo is None:
                ep = ep.replace(tzinfo=timezone.utc)
            r["epoch"] = ep
            restored.append(r)
        result[int(norad_id_str)] = restored

    return result


# ─── Top-level entry point ─────────────────────────────────────────────────────

def ingest(
    norad_ids: list[int],
    days: int = 180,
    cache_path: Path = None,
    force_refresh: bool = False,
    username: str = None,
    password: str = None,
) -> dict[int, list[dict]]:
    """
    Fetch (or load from cache) normalized TLE history for the given NORAD IDs.

    Returns {norad_id: [normalized_tle_record, ...]} sorted by epoch ascending.

    If cache_path exists and force_refresh is False, the cache is used and
    no Space-Track request is made.  Set force_refresh=True to re-fetch.
    """
    if cache_path is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        ids_tag = "_".join(str(x) for x in sorted(norad_ids))
        cache_path = _DATA_DIR / f"tle_history_{ids_tag}.json"

    if cache_path.exists() and not force_refresh:
        logger.info(f"Loading TLEs from cache: {cache_path}")
        tles = load_tles(cache_path)
        return {nid: tles[nid] for nid in norad_ids if nid in tles}

    client = SpaceTrackClient(username=username, password=password)
    client.login()
    raw_by_sat = client.fetch_history(norad_ids, days=days)

    tles_by_sat = {
        norad_id: normalize_records(raw_records)
        for norad_id, raw_records in raw_by_sat.items()
    }

    save_tles(tles_by_sat, cache_path)
    return tles_by_sat
