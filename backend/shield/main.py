"""
backend/shield/main.py

Orchestrates the Shield collision-avoidance pipeline for a given user satellite.

  0. Fetch current Kp index from NOAA SWPC
  1. Authenticate with Space-Track; fetch the user's satellite by NORAD ID
  2. Fetch a threat catalog of LEO objects (PAYLOAD + DEBRIS)
  3. Screen the user's satellite against the catalog -> candidate pairs
  4. TCA + probability for each candidate pair (threaded)
  5. Filter by miss distance and Pc floor
  6. Compute risk_score (0-100) composite
  7. Sort descending by risk_score
  8. Write backend/shield/output/conjunctions.json
  9. FastAPI  GET /conjunctions/{norad_id}?min_risk=0&limit=20
             GET /satellite/{norad_id}

Risk score weights
------------------
  50 % collision_probability  -- log-scaled, Pc=1e-12 -> 0, Pc>=1e-2 -> 50
  30 % miss_distance_km       -- linear inverse, 0 km -> 30, 200 km -> 0
  20 % secondary object type  -- DEBRIS 20, ROCKET BODY 15, UNKNOWN 10, PAYLOAD 5

Environment variables (.env)
----------------------------
  SPACETRACK_EMAIL or SPACETRACK_USERNAME
  SPACETRACK_PASSWORD
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from shield.propagate import parse_satrec
from shield.tca import find_tca
from shield.probability import compute_probability
from shield.maneuver import compute_maneuvers
from shield.cascade import compute_cascade, LABEL_SLUGS
from shield.maneuver_detector import extract_operator

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent.parent / ".env")

SPACETRACK_BASE  = "https://www.space-track.org"
SPACETRACK_LOGIN = f"{SPACETRACK_BASE}/ajaxauth/login"

# Single satellite lookup by NORAD CAT ID
SPACETRACK_SINGLE_URL = (
    "{base}/basicspacedata/query/class/gp"
    "/NORAD_CAT_ID/{norad_id}"
    "/format/json"
)

# LEO payload threat catalog: periapsis 300-2000 km, freshest TLEs first
SPACETRACK_PAYLOAD_URL = (
    "{base}/basicspacedata/query/class/gp"
    "/OBJECT_TYPE/PAYLOAD"
    "/PERIAPSIS/300--2000"
    "/DECAY_DATE/null-val"
    "/orderby/EPOCH%20desc"
    "/format/json"
    "/limit/{limit}"
)

# LEO debris threat catalog: same altitude band
SPACETRACK_DEBRIS_URL = (
    "{base}/basicspacedata/query/class/gp"
    "/OBJECT_TYPE/DEBRIS"
    "/PERIAPSIS/300--2000"
    "/DECAY_DATE/null-val"
    "/orderby/EPOCH%20desc"
    "/format/json"
    "/limit/{limit}"
)

CATALOG_LIMIT         = 1000        # total threat catalog size (full run, split evenly)
DRY_RUN_CATALOG_LIMIT = 200         # total threat catalog size (--dry-run)
MAX_TCA_WORKERS       = 12          # parallel TCA threads
MAX_TCA_PAIRS         = 5000        # cap after screening to keep runtime manageable

MISS_FILTER_KM = 200.0
PC_FILTER      = 1e-16
PC_LOG_MIN     = 1e-12              # Pc floor for log-scale (= 0 points)
PC_LOG_MAX     = 1e-2               # Pc ceiling for log-scale (= 50 points)

# Screening thresholds (same values as screen.py)
ALT_TOLERANCE_KM    = 50.0
INC_TOLERANCE_DEG   = 10.0
POLAR_THRESHOLD_DEG = 80.0

NOAA_KP_URL = (
    "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
)

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "conjunctions.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Operator do-nothing confidence seed table ─────────────────────────────────
# Probability that the secondary satellite's operator will maneuver away from
# a conjunction without being prompted.  Derived from historical maneuver rate
# data (maneuvers/sat/month): HIGH >= 1.0, MODERATE >= 0.2, LOW < 0.2.
_OPERATOR_DO_NOTHING: dict[str, float] = {
    "STARLINK":   0.85,
    "ONEWEB":     0.80,
    "ISS":        0.75,
    "GLOBALSTAR": 0.55,
    "IRIDIUM":    0.60,
    "CSS":        0.40,
    "SPIRE":      0.35,
    "PLANET":     0.35,
    "SWARM":      0.30,
    "ICEYE":      0.30,
    "CAPELLA":    0.30,
    "UMBRA":      0.30,
    "SES":        0.25,
    "INTELSAT":   0.25,
    "TELESAT":    0.25,
    "EUTELSAT":   0.25,
    "COSMOS":     0.20,
    "GALILEO":    0.20,
    "GPS":        0.15,
    "FENGYUN":    0.15,
    "GLONASS":    0.12,
    "BEIDOU":     0.12,
    "UNKNOWN":    0.20,
}
_DEBRIS_DO_NOTHING   = 0.0   # debris cannot maneuver
_DEFAULT_DO_NOTHING  = 0.25  # fallback for payloads with unmapped operator


def _do_nothing_confidence(rec_b: dict, norad_confidence: Optional[dict]) -> float:
    """Return do-nothing confidence for the secondary object."""
    if rec_b.get("OBJECT_TYPE", "").strip().upper() == "DEBRIS":
        return _DEBRIS_DO_NOTHING
    if norad_confidence is not None:
        val = norad_confidence.get(str(rec_b.get("NORAD_CAT_ID", "")))
        if val is not None:
            return val
    return _DEFAULT_DO_NOTHING


# ── Space-Track auth & fetch ──────────────────────────────────────────────────

def _spacetrack_session() -> requests.Session:
    """Authenticate with Space-Track and return a live session."""
    email = (
        os.environ.get("SPACETRACK_EMAIL")
        or os.environ.get("SPACETRACK_USERNAME")
    )
    password = os.environ.get("SPACETRACK_PASSWORD")
    if not email or not password:
        raise RuntimeError(
            "SPACETRACK_EMAIL (or SPACETRACK_USERNAME) and SPACETRACK_PASSWORD "
            "must be set in .env"
        )
    session = requests.Session()
    resp = session.post(
        SPACETRACK_LOGIN,
        data={"identity": email, "password": password},
        timeout=30,
    )
    if resp.status_code != 200 or "Failed" in resp.text:
        raise RuntimeError(
            f"Space-Track auth failed ({resp.status_code}): {resp.text[:200]}"
        )
    log.info("Space-Track: authenticated as %s", email)
    return session


def fetch_single_satellite(session: requests.Session, norad_id: int) -> dict:
    """
    Fetch the most recent GP record for a single satellite by NORAD CAT ID.

    Raises:
        ValueError: If no record is found for the given NORAD ID.
    """
    url = SPACETRACK_SINGLE_URL.format(base=SPACETRACK_BASE, norad_id=norad_id)
    log.info("Fetching GP record for NORAD %d...", norad_id)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    records = resp.json()
    if not records:
        raise ValueError(f"No GP record found for NORAD ID {norad_id}")
    log.info("  Found: %s", records[0].get("OBJECT_NAME", "unknown"))
    return records[0]


def fetch_threat_catalog(session: requests.Session, limit: int = 1000) -> list[dict]:
    """
    Fetch the LEO threat catalog: equal split of PAYLOAD and DEBRIS records,
    ordered by most recent TLE epoch (freshest first).

    Args:
        limit: Total catalog size; split evenly between PAYLOAD and DEBRIS.
    """
    half = max(1, limit // 2)
    log.info("Fetching threat catalog (%d PAYLOAD + %d DEBRIS)...", half, half)

    payload_url = SPACETRACK_PAYLOAD_URL.format(base=SPACETRACK_BASE, limit=half)
    resp = session.get(payload_url, timeout=60)
    resp.raise_for_status()
    payloads = resp.json()
    log.info("  Received %d PAYLOAD records", len(payloads))

    debris_url = SPACETRACK_DEBRIS_URL.format(base=SPACETRACK_BASE, limit=half)
    resp = session.get(debris_url, timeout=60)
    resp.raise_for_status()
    debris = resp.json()
    log.info("  Received %d DEBRIS records", len(debris))

    return payloads + debris


# ── NOAA SWPC Kp fetch ────────────────────────────────────────────────────────

def _fetch_kp() -> Optional[float]:
    """
    Fetch the most recent *observed* Kp index from NOAA SWPC.

    Response is a list-of-lists: row 0 = column headers, rows 1+ = data.
    Each data row: [time_tag, kp_value, quality_string].
    Quality values: 'observed' | 'estimated' | 'predicted'.

    Returns None on failure; pipeline continues without the solar override.
    """
    try:
        resp = requests.get(NOAA_KP_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("NOAA SWPC Kp fetch failed: %s -- solar override disabled", exc)
        return None

    if not data or not isinstance(data, list):
        log.warning("NOAA SWPC Kp: unexpected response format -- solar override disabled")
        return None

    kp_val: Optional[float] = None

    if isinstance(data[0], list):
        for row in data[1:]:
            if len(row) >= 3 and str(row[2]).strip().lower() == "observed":
                try:
                    kp_val = float(row[1])
                except (ValueError, TypeError):
                    pass
        if kp_val is None and len(data) > 1:
            try:
                kp_val = float(data[1][1])
            except (ValueError, TypeError, IndexError):
                pass

    elif isinstance(data[0], dict):
        for row in data:
            quality = (row.get("observed") or row.get("kp_type") or "").lower()
            if quality == "observed":
                try:
                    kp_val = float(
                        row.get("kp") or row.get("Kp") or row.get("kp_index") or 0
                    )
                except (ValueError, TypeError):
                    pass
        if kp_val is None:
            try:
                first = data[0]
                kp_val = float(
                    first.get("kp") or first.get("Kp") or first.get("kp_index") or 0
                )
            except (ValueError, TypeError):
                pass
    else:
        log.warning("NOAA SWPC Kp: unrecognised response format -- solar override disabled")
        return None

    if kp_val is None:
        log.warning("NOAA SWPC Kp: could not extract a value -- solar override disabled")
        return None

    log.info("NOAA SWPC Kp index (most recent observed): %.1f", kp_val)
    return kp_val


# ── Data-age helper ───────────────────────────────────────────────────────────

def _data_age_minutes(record: dict) -> float:
    """Minutes since the TLE epoch was measured."""
    epoch_str = record.get("EPOCH", "")
    if not epoch_str:
        return 9999.0
    try:
        epoch = datetime.fromisoformat(epoch_str.replace("Z", "")).replace(
            tzinfo=timezone.utc
        )
        delta = datetime.now(timezone.utc) - epoch
        return delta.total_seconds() / 60.0
    except ValueError:
        return 9999.0


# ── Screening (primary vs catalog) ───────────────────────────────────────────

def _screen_catalog(primary: dict, catalog: list[dict]) -> list[dict]:
    """
    Filter catalog objects down to those that could conjunct with the primary.

    Applies the same altitude-band-overlap and inclination-similarity checks
    as screen.py, but with the primary satellite fixed on side A (O(n) instead
    of O(n²)).

    Returns:
        Subset of catalog records that passed the proximity filter.
    """
    try:
        peri_a = float(primary["PERIAPSIS"])
        apo_a  = float(primary["APOAPSIS"])
        inc_a  = float(primary["INCLINATION"])
    except (KeyError, ValueError, TypeError):
        log.warning("Primary record missing orbital elements -- cannot screen")
        return []

    candidates: list[dict] = []
    for rec in catalog:
        try:
            peri_b = float(rec["PERIAPSIS"])
            apo_b  = float(rec["APOAPSIS"])
            inc_b  = float(rec["INCLINATION"])
        except (KeyError, ValueError, TypeError):
            continue

        # Altitude band overlap: skip if bands are separated by more than tolerance
        if apo_a + ALT_TOLERANCE_KM < peri_b:
            continue
        if apo_b + ALT_TOLERANCE_KM < peri_a:
            continue

        # Inclination: polar orbits can encounter anything; others must be close
        polar = inc_a >= POLAR_THRESHOLD_DEG and inc_b >= POLAR_THRESHOLD_DEG
        if not polar and abs(inc_a - inc_b) > INC_TOLERANCE_DEG:
            continue

        candidates.append(rec)

    return candidates


# ── Risk score ────────────────────────────────────────────────────────────────

_TYPE_SCORE: dict[str, float] = {
    "DEBRIS":        20.0,
    "ROCKET BODY":   15.0,
    "UNKNOWN":       10.0,
    "PAYLOAD":        5.0,
}


def _risk_score(pc: float, miss_km: float, secondary_type: str) -> float:
    """
    Composite risk score 0-100.

    50 % Pc component -- log-scaled between PC_LOG_MIN and PC_LOG_MAX
    30 % miss distance -- linear inverse (0 km = 30, MISS_FILTER_KM km = 0)
    20 % object type   -- DEBRIS 20, ROCKET BODY 15, UNKNOWN 10, PAYLOAD 5
    """
    safe_pc  = max(pc, PC_LOG_MIN)
    log_norm = (math.log10(safe_pc) - math.log10(PC_LOG_MIN)) / (
        math.log10(PC_LOG_MAX) - math.log10(PC_LOG_MIN)
    )
    pc_comp = min(max(log_norm, 0.0), 1.0) * 50.0

    miss_comp = max(0.0, 1.0 - miss_km / MISS_FILTER_KM) * 30.0

    type_key  = secondary_type.strip().upper()
    type_comp = _TYPE_SCORE.get(type_key, 10.0)

    return round(pc_comp + miss_comp + type_comp, 2)


# ── TCA worker (runs in thread) ───────────────────────────────────────────────

def _run_tca_pair(
    rec_a: dict, sat_a, rec_b: dict, sat_b, t_start: datetime,
    debug_sink: Optional[list] = None,
    miss_sink: Optional[list] = None,
    kp: Optional[float] = None,
    norad_confidence: Optional[dict] = None,
) -> Optional[dict]:
    """
    Run TCA -> probability for one candidate pair.
    Returns a fully assembled conjunction event dict, or None if filtered out.

    debug_sink: if provided, appends one outcome dict per pair (see --debug).
    miss_sink:  if provided, appends every non-None miss distance (km) before
                any filter runs -- used to report the global closest approach.
    Both lists use GIL-safe append and can be shared across threads.
    """
    tca = find_tca(rec_a, sat_a, rec_b, sat_b, t_start)
    if tca is None:
        if debug_sink is not None:
            debug_sink.append(
                {"tca_none": True, "miss_km": None,
                 "filtered_miss": False, "filtered_pc": False}
            )
        return None

    miss = tca["miss_distance_km"]
    if miss_sink is not None:
        miss_sink.append(miss)

    if miss > MISS_FILTER_KM:
        if debug_sink is not None:
            debug_sink.append(
                {"tca_none": False, "miss_km": miss,
                 "filtered_miss": True, "filtered_pc": False}
            )
        return None

    age_a    = _data_age_minutes(rec_a)
    age_b    = _data_age_minutes(rec_b)
    data_age = max(age_a, age_b)

    result = compute_probability(tca, data_age_minutes=data_age)
    if result is None or result["collision_probability"] < PC_FILTER:
        if debug_sink is not None:
            debug_sink.append(
                {"tca_none": False, "miss_km": miss,
                 "filtered_miss": False, "filtered_pc": True}
            )
        return None

    if debug_sink is not None:
        debug_sink.append(
            {"tca_none": False, "miss_km": miss,
             "filtered_miss": False, "filtered_pc": False}
        )

    pc       = result["collision_probability"]
    miss     = result["miss_distance_km"]
    sec_type = rec_b.get("OBJECT_TYPE", "UNKNOWN")
    risk     = _risk_score(pc, miss, sec_type)

    # Solar weather override -- Kp degrades TLE-based confidence
    confidence = result["confidence"]
    if kp is not None:
        if kp >= 5.0:
            confidence = "low"
        elif kp >= 3.0 and confidence == "nominal":
            confidence = "degraded"

    return {
        "event_id":               str(uuid.uuid4()),
        "timestamp_utc":          datetime.now(timezone.utc).strftime(
                                      "%Y-%m-%dT%H:%M:%S.%fZ"
                                  ),
        "primary": {
            "norad_id":    int(rec_a.get("NORAD_CAT_ID", 0)),
            "name":        rec_a.get("OBJECT_NAME", ""),
            "tle_epoch":   rec_a.get("EPOCH", ""),
            "object_type": rec_a.get("OBJECT_TYPE", "UNKNOWN"),
            "tle_line1":   rec_a.get("TLE_LINE1", ""),
            "tle_line2":   rec_a.get("TLE_LINE2", ""),
        },
        "secondary": {
            "norad_id":       int(rec_b.get("NORAD_CAT_ID", 0)),
            "name":           rec_b.get("OBJECT_NAME", ""),
            "tle_epoch":      rec_b.get("EPOCH", ""),
            "object_type":    sec_type,
            "tle_line1":      rec_b.get("TLE_LINE1", ""),
            "tle_line2":      rec_b.get("TLE_LINE2", ""),
            "inclination_deg": rec_b.get("INCLINATION"),
            "apoapsis_km":    rec_b.get("APOAPSIS"),
            "periapsis_km":   rec_b.get("PERIAPSIS"),
            "country_code":   rec_b.get("COUNTRY_CODE", ""),
            "launch_date":    rec_b.get("LAUNCH_DATE", ""),
        },
        "tca_utc":                result["tca_utc"],
        "miss_distance_km":       round(miss, 4),
        "relative_velocity_km_s": round(result["relative_velocity_km_s"], 4),
        "collision_probability":  pc,
        "pc_method":              result["pc_method"],
        "confidence":             confidence,
        "kp_index":               round(kp, 1) if kp is not None else None,
        "risk_score":             risk,
        "do_nothing_confidence":  _do_nothing_confidence(rec_b, norad_confidence),
        "data_source":            "spacetrack",
        "data_age_minutes":       round(data_age, 1),
    }


# ── Debug stats ───────────────────────────────────────────────────────────────

def _print_debug_stats(debug_records: list[dict]) -> None:
    """Print a structured breakdown of TCA/filter outcomes to stdout."""
    total     = len(debug_records)
    tca_none  = sum(1 for r in debug_records if r["tca_none"])
    had_tca   = [r for r in debug_records if not r["tca_none"]]
    filt_miss = sum(1 for r in had_tca if r["filtered_miss"])
    filt_pc   = sum(1 for r in had_tca if r["filtered_pc"])
    passed    = sum(1 for r in had_tca if not r["filtered_miss"] and not r["filtered_pc"])
    miss_vals = [r["miss_km"] for r in had_tca if r["miss_km"] is not None]

    W = 72
    print("\n" + "-" * W)
    print("  DEBUG -- TCA / FILTER BREAKDOWN")
    print("-" * W)
    print(f"  Candidate pairs processed : {total}")
    print(f"  TCA returned None         : {tca_none}"
          + (f"  ({100*tca_none/total:.1f}%)" if total else ""))
    print(f"  TCA succeeded             : {len(had_tca)}")
    print()
    if miss_vals:
        miss_min  = min(miss_vals)
        miss_max  = max(miss_vals)
        miss_mean = sum(miss_vals) / len(miss_vals)
        buckets = [0.1, 1.0, 5.0, 10.0, 25.0, 50.0]
        counts  = [sum(1 for v in miss_vals if v < b) for b in buckets]
        print(f"  Miss distance (km) -- {len(miss_vals)} non-None results:")
        print(f"    min  : {miss_min:.4f} km")
        print(f"    mean : {miss_mean:.4f} km")
        print(f"    max  : {miss_max:.4f} km")
        print(f"    cumulative distribution:")
        prev = 0
        for b, c in zip(buckets, counts):
            bar = "#" * min(c - prev, 40)
            print(f"      < {b:>5.1f} km : {c:>4}  {bar}")
            prev = c
    else:
        print("  No non-None TCA results to report miss distances for.")
    print()
    print(f"  Filtered out (miss > {MISS_FILTER_KM:.0f} km) : {filt_miss}")
    print(f"  Filtered out (Pc  < {PC_FILTER:.0e})  : {filt_pc}")
    print(f"  Passed all filters          : {passed}")
    print("-" * W + "\n")


# ── Summary table ─────────────────────────────────────────────────────────────

def _print_summary(
    events: list[dict],
    primary_name: str = "",
    dry_run: bool = False,
    min_miss_km: Optional[float] = None,
) -> None:
    W = 110
    SEP = "=" * W
    mode = (
        f" [DRY RUN -- {DRY_RUN_CATALOG_LIMIT} catalog objects, no file written]"
        if dry_run else ""
    )
    miss_str = (
        f"  closest approach seen (all pairs): {min_miss_km:.4f} km"
        if min_miss_km is not None else ""
    )
    print("\n" + SEP)
    print(
        f"  DRIFT ZERO -- SHIELD   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        + (f"   primary: {primary_name}" if primary_name else "")
        + mode
    )
    print(f"  {len(events)} conjunction events above threshold")
    if miss_str:
        print(miss_str)
    print(SEP)
    if not events:
        print("  No events above threshold.")
        print(SEP + "\n")
        return

    hdr = (
        f"  {'RISK':>5}  {'Pc':>10}  {'MISS km':>8}  {'REL km/s':>9}  "
        f"{'CONF':>8}  {'SECONDARY':<26}  TCA UTC"
    )
    print(hdr)
    print("  " + "-" * (W - 2))
    for ev in events[:20]:
        print(
            f"  {ev['risk_score']:>5.1f}  "
            f"{ev['collision_probability']:>10.3e}  "
            f"{ev['miss_distance_km']:>8.3f}  "
            f"{ev['relative_velocity_km_s']:>9.3f}  "
            f"{ev['confidence']:>8}  "
            f"{ev['secondary']['name'][:26]:<26}  "
            f"{ev['tca_utc'][:19]}"
        )
    if len(events) > 20:
        print(f"  ... and {len(events) - 20} more events (see conjunctions.json)")
    print(SEP + "\n")


# ── Databricks Delta Lake write ───────────────────────────────────────────────

def _write_conjunctions_to_databricks(
    events: list[dict], norad_id: int, primary_name: str
) -> None:
    """
    Write conjunction events to drift_zero.orbital.conjunctions Delta table.
    Non-blocking on error — a failed write never breaks the API response.
    """
    host    = os.getenv("DATABRICKS_HOST")
    token   = os.getenv("DATABRICKS_TOKEN")
    wh_id   = os.getenv("DATABRICKS_WAREHOUSE_ID")
    catalog = os.getenv("DATABRICKS_CATALOG", "drift_zero")
    schema  = os.getenv("DATABRICKS_SCHEMA", "orbital")

    if not (host and token and wh_id):
        log.warning("Databricks env vars not set — skipping Delta write")
        return

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState
    except ImportError:
        log.warning("databricks-sdk not installed — skipping Delta write")
        return

    w     = WorkspaceClient(host=host, token=token)
    table = f"`{catalog}`.`{schema}`.`conjunctions`"

    ddl = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        event_id               STRING,
        timestamp_utc          STRING,
        primary_norad_id       INT,
        primary_name           STRING,
        secondary_norad_id     INT,
        secondary_name         STRING,
        secondary_object_type  STRING,
        tca_utc                STRING,
        miss_distance_km       DOUBLE,
        relative_velocity_km_s DOUBLE,
        collision_probability  DOUBLE,
        risk_score             DOUBLE,
        do_nothing_confidence  DOUBLE,
        confidence             STRING,
        kp_index               DOUBLE,
        data_age_minutes       DOUBLE,
        data_source            STRING
    )
    USING DELTA
    """
    try:
        stmt = w.statement_execution.execute_statement(
            warehouse_id=wh_id, statement=ddl, wait_timeout="30s",
        )
        if stmt.status.state != StatementState.SUCCEEDED:
            log.warning("Databricks DDL state: %s — %s", stmt.status.state, stmt.status.error)
            return
    except Exception as exc:
        log.warning("Databricks table create failed: %s", exc)
        return

    if not events:
        return

    def _v(val):
        if val is None:
            return "NULL"
        if isinstance(val, str):
            return "'" + val.replace("\\", "\\\\").replace("'", "\\'") + "'"
        return str(val)

    rows_sql = ",\n".join(
        "({})".format(", ".join(_v(x) for x in [
            e.get("event_id", ""),
            e.get("timestamp_utc", ""),
            e.get("primary", {}).get("norad_id", 0),
            e.get("primary", {}).get("name", ""),
            e.get("secondary", {}).get("norad_id", 0),
            e.get("secondary", {}).get("name", ""),
            e.get("secondary", {}).get("object_type", ""),
            e.get("tca_utc", ""),
            e.get("miss_distance_km", 0.0),
            e.get("relative_velocity_km_s", 0.0),
            e.get("collision_probability", 0.0),
            e.get("risk_score", 0.0),
            e.get("do_nothing_confidence", 0.0),
            e.get("confidence", ""),
            e.get("kp_index") if e.get("kp_index") is not None else 0.0,
            e.get("data_age_minutes", 0.0),
            e.get("data_source", "spacetrack"),
        ]))
        for e in events
    )
    insert_sql = f"INSERT INTO {table} VALUES\n{rows_sql}"

    try:
        stmt = w.statement_execution.execute_statement(
            warehouse_id=wh_id, statement=insert_sql, wait_timeout="60s",
        )
        if stmt.status.state == StatementState.SUCCEEDED:
            log.info(
                "Databricks: wrote %d conjunction events for NORAD %d (%s)",
                len(events), norad_id, primary_name,
            )
        else:
            log.warning(
                "Databricks INSERT state: %s — %s",
                stmt.status.state, stmt.status.error,
            )
    except Exception as exc:
        log.warning("Databricks INSERT failed: %s", exc)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    norad_id: int,
    dry_run: bool = False,
    debug: bool = False,
) -> list[dict]:
    """
    Execute the Shield pipeline for a given satellite and return sorted events.

    Args:
        norad_id: NORAD CAT ID of the user's satellite.
        dry_run:  If True, use a smaller catalog and skip writing output.
        debug:    If True, print a structured TCA/filter breakdown.
    """
    t_start       = datetime.now(timezone.utc)
    catalog_limit = DRY_RUN_CATALOG_LIMIT if dry_run else CATALOG_LIMIT

    if dry_run:
        log.info(
            "*** DRY RUN: NORAD %d vs %d catalog objects, no file output ***",
            norad_id, catalog_limit,
        )

    # 0. Solar weather
    kp_index = _fetch_kp()

    # 1. Auth + fetch primary satellite
    session      = _get_session()
    primary_rec  = fetch_single_satellite(session, norad_id)
    primary_name = primary_rec.get("OBJECT_NAME", f"NORAD {norad_id}")

    # 2. Fetch threat catalog (cached for 5 min); remove user's own satellite if present
    catalog = _get_threat_catalog(session, catalog_limit)
    catalog = [r for r in catalog if str(r.get("NORAD_CAT_ID")) != str(norad_id)]
    log.info("Threat catalog after dedup: %d objects", len(catalog))

    # 3. Parse Satrecs
    primary_sat = parse_satrec(primary_rec)
    if primary_sat is None:
        raise RuntimeError(f"Could not parse TLE for NORAD {norad_id} ({primary_name})")

    parsed_catalog: list[tuple[dict, object]] = []
    skipped = 0
    for rec in catalog:
        sat = parse_satrec(rec)
        if sat is None:
            skipped += 1
            continue
        parsed_catalog.append((rec, sat))
    log.info("Parsed %d catalog Satrecs (%d skipped)", len(parsed_catalog), skipped)

    sat_by_norad    = {r.get("NORAD_CAT_ID"): s for r, s in parsed_catalog}
    catalog_records = [r for r, _ in parsed_catalog]

    # Build NORAD → do_nothing_confidence lookup from catalog
    norad_confidence: dict[str, float] = {}
    for rec in catalog_records:
        obj_type = rec.get("OBJECT_TYPE", "").strip().upper()
        if obj_type == "DEBRIS":
            norad_confidence[str(rec.get("NORAD_CAT_ID", ""))] = _DEBRIS_DO_NOTHING
        else:
            op  = extract_operator(
                str(rec.get("OBJECT_NAME", "")),
                str(rec.get("COUNTRY_CODE", "")),
            )
            norad_confidence[str(rec.get("NORAD_CAT_ID", ""))] = _OPERATOR_DO_NOTHING.get(
                op, _DEFAULT_DO_NOTHING
            )
    log.info("Operator confidence map built for %d catalog objects", len(norad_confidence))

    # Store pipeline state for cascade analysis
    _pipeline_cache[norad_id] = {
        "primary_rec":     primary_rec,
        "primary_sat":     primary_sat,
        "catalog_records": catalog_records,
        "sat_by_norad":    sat_by_norad,
        "t_start":         t_start,
    }

    # 4. Screen primary against catalog
    log.info("Screening %s against %d catalog objects...", primary_name, len(catalog_records))
    candidates = _screen_catalog(primary_rec, catalog_records)
    log.info("Screen returned %d candidate pairs", len(candidates))

    # Cap to most-interleaved pairs
    pairs: list[tuple[dict, dict]] = [(primary_rec, c) for c in candidates]
    if len(pairs) > MAX_TCA_PAIRS:
        def _band_overlap(pair):
            a, b = pair
            try:
                return (
                    abs(float(a["APOAPSIS"]) - float(b["PERIAPSIS"])) +
                    abs(float(b["APOAPSIS"]) - float(a["PERIAPSIS"]))
                )
            except (KeyError, ValueError, TypeError):
                return 9999.0

        pairs.sort(key=_band_overlap)
        pairs = pairs[:MAX_TCA_PAIRS]
        log.info("Capped to %d most-interleaved pairs for TCA", MAX_TCA_PAIRS)

    # 5. TCA + probability (threaded)
    log.info(
        "Running TCA + probability on %d pairs (%d threads)...",
        len(pairs), MAX_TCA_WORKERS,
    )
    events: list[dict] = []
    debug_records: list[dict] = [] if debug else None  # type: ignore[assignment]
    all_miss_km: list[float] = []
    done = 0

    def _worker(pair):
        _, rec_b = pair
        sb = sat_by_norad.get(rec_b.get("NORAD_CAT_ID"))
        if sb is None:
            return None
        return _run_tca_pair(
            primary_rec, primary_sat, rec_b, sb, t_start,
            debug_sink=debug_records,
            miss_sink=all_miss_km,
            kp=kp_index,
            norad_confidence=norad_confidence,
        )

    with ThreadPoolExecutor(max_workers=MAX_TCA_WORKERS) as pool:
        futures = {pool.submit(_worker, p): p for p in pairs}
        for fut in as_completed(futures):
            done += 1
            if done % 50 == 0:
                log.info("  TCA progress: %d / %d", done, len(pairs))
            try:
                result = fut.result()
                if result is not None:
                    events.append(result)
            except Exception as exc:  # noqa: BLE001
                log.warning("TCA worker error: %s", exc)

    log.info("Pipeline complete: %d events above threshold", len(events))

    if debug and debug_records is not None:
        _print_debug_stats(debug_records)

    # 6. Sort descending by risk_score
    events.sort(key=lambda e: e["risk_score"], reverse=True)

    # 6a. Write to Databricks Delta Lake (background thread — non-blocking)
    if not dry_run and events:
        import threading
        threading.Thread(
            target=_write_conjunctions_to_databricks,
            args=(events, norad_id, primary_name),
            daemon=True,
        ).start()

    # 7. Write output JSON
    if dry_run:
        log.info("DRY RUN: skipping write to %s", OUTPUT_FILE)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(
                {
                    "generated_at": t_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "norad_id":     norad_id,
                    "primary_name": primary_name,
                    "total_events": len(events),
                    "events":       events,
                },
                f,
                indent=2,
            )
        log.info("Wrote %d events to %s", len(events), OUTPUT_FILE)

    # 8. Print summary
    min_miss = min(all_miss_km) if all_miss_km else None
    _print_summary(events, primary_name=primary_name, dry_run=dry_run, min_miss_km=min_miss)

    return events


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Drift Zero -- Shield API", version="0.2.0")
router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Simple in-memory cache: norad_id -> list of conjunction event dicts.
# Populated by GET /conjunctions/{norad_id}; read by GET /maneuvers/{norad_id}/{event_id}.
# No expiry needed for demo use.
_conjunction_cache: dict[int, list[dict]] = {}

# Pipeline state cache: norad_id -> {primary_rec, primary_sat, catalog_records,
# sat_by_norad, t_start}. Populated by run_pipeline(); read by GET /cascade.
_pipeline_cache: dict[int, dict] = {}

# ── 5-minute threat-catalog cache ────────────────────────────────────────────
# Avoids re-fetching ~1000 Space-Track objects on every API call.
_catalog_cache: dict = {}       # keys: catalog, limit, expires_at
_CATALOG_TTL = 300              # seconds

# ── Session cache ─────────────────────────────────────────────────────────────
# Re-uses the authenticated requests.Session across calls within a 4.5-min window.
_session_store: dict = {}       # keys: session, expires_at
_SESSION_TTL = 270              # re-auth before Space-Track's ~5-min idle timeout


def _get_session() -> requests.Session:
    """Return a cached Space-Track session, re-authenticating as needed."""
    now = time.monotonic()
    if _session_store.get("session") and _session_store.get("expires_at", 0) > now:
        log.info("Space-Track: reusing cached session")
        return _session_store["session"]
    session = _spacetrack_session()
    _session_store["session"]    = session
    _session_store["expires_at"] = now + _SESSION_TTL
    return session


def _get_threat_catalog(session: requests.Session, limit: int) -> list[dict]:
    """
    Return the LEO threat catalog, serving from a 5-minute in-memory cache
    when available so repeated calls for different NORAD IDs skip the
    two-request Space-Track round-trip.
    """
    now    = time.monotonic()
    cached = _catalog_cache
    if (
        cached.get("catalog") is not None
        and cached.get("limit") == limit
        and cached.get("expires_at", 0) > now
    ):
        log.info(
            "Threat catalog: serving %d objects from cache (%.0fs remaining)",
            len(cached["catalog"]),
            cached["expires_at"] - now,
        )
        return cached["catalog"]

    catalog = fetch_threat_catalog(session, limit)
    _catalog_cache["catalog"]    = catalog
    _catalog_cache["limit"]      = limit
    _catalog_cache["expires_at"] = now + _CATALOG_TTL
    log.info(
        "Threat catalog: fetched and cached %d objects (TTL %ds)",
        len(catalog), _CATALOG_TTL,
    )
    return catalog


@app.get("/satellite/{norad_id}")
async def get_satellite(norad_id: int):
    """
    Return name and basic orbital parameters for a NORAD CAT ID.
    Use this to confirm a satellite exists before running a full conjunction check.
    """
    try:
        session = _get_session()
        rec     = fetch_single_satellite(session, norad_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "norad_id":        norad_id,
        "name":            rec.get("OBJECT_NAME", ""),
        "object_type":     rec.get("OBJECT_TYPE", ""),
        "country_code":    rec.get("COUNTRY_CODE", ""),
        "launch_date":     rec.get("LAUNCH_DATE", ""),
        "period_min":      rec.get("PERIOD"),
        "inclination_deg": rec.get("INCLINATION"),
        "apoapsis_km":     rec.get("APOAPSIS"),
        "periapsis_km":    rec.get("PERIAPSIS"),
        "eccentricity":    rec.get("ECCENTRICITY"),
        "tle_epoch":       rec.get("EPOCH", ""),
        "tle_line1":       rec.get("TLE_LINE1", ""),
        "tle_line2":       rec.get("TLE_LINE2", ""),
    }


@router.get("/maneuvers/{norad_id}/{event_id}")
async def get_maneuvers(norad_id: str, event_id: str):
    """
    Return three maneuver options for a specific conjunction event.

    Requires that GET /conjunctions/{norad_id} has been called first to
    populate the cache. Returns 409 if the cache is empty for this satellite
    (so the caller knows to run /conjunctions first rather than getting a
    misleading 404).
    """
    cache_key = int(norad_id) if norad_id.isdigit() else norad_id
    events = _conjunction_cache.get(cache_key)
    if events is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No conjunction data cached for NORAD {norad_id}. "
                f"Call GET /conjunctions/{norad_id} first."
            ),
        )

    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Event {event_id!r} not found for NORAD {norad_id}. "
                "Conjunction data has refreshed — please reselect an event."
            ),
        )

    return compute_maneuvers(event)


@router.get("/conjunctions/{norad_id}")
async def get_conjunctions(
    norad_id: int,
    min_risk: float = Query(default=0.0, ge=0.0, le=100.0),
    limit:    int   = Query(default=20,  ge=1,   le=500),
):
    """
    Run the full Shield conjunction analysis for a satellite on demand.

    Query params:
      min_risk  -- minimum risk_score threshold (0-100, default 0)
      limit     -- maximum number of events to return (1-500, default 20)
    """
    try:
        events = run_pipeline(norad_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _conjunction_cache[norad_id] = events

    filtered = [e for e in events if e["risk_score"] >= min_risk]
    return {
        "norad_id":       norad_id,
        "total_matching": len(filtered),
        "returned":       min(len(filtered), limit),
        "events":         filtered[:limit],
    }


@router.get("/cascade/{norad_id}/{event_id}/{maneuver_label}")
async def get_cascade(norad_id: str, event_id: str, maneuver_label: str):
    """
    Compute downstream conjunction risks introduced or worsened by a maneuver.

    maneuver_label must be one of: maximum_safety, balanced, fuel_efficient.

    Requires that GET /conjunctions/{norad_id} has been called first to populate
    the conjunction cache and pipeline state cache.
    Returns 409 if either cache is empty.
    """
    valid_labels = set(LABEL_SLUGS.keys())
    if maneuver_label not in valid_labels:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid maneuver_label {maneuver_label!r}. "
                f"Must be one of: {sorted(valid_labels)}"
            ),
        )

    cache_key = int(norad_id) if norad_id.isdigit() else norad_id
    events = _conjunction_cache.get(cache_key)
    if events is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No conjunction data cached for NORAD {norad_id}. "
                f"Call GET /conjunctions/{norad_id} first."
            ),
        )

    pipeline = _pipeline_cache.get(cache_key)
    if pipeline is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No pipeline state cached for NORAD {norad_id}. "
                f"Call GET /conjunctions/{norad_id} first."
            ),
        )

    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Event {event_id!r} not found for NORAD {norad_id}. "
                "Conjunction data has refreshed — please reselect an event."
            ),
        )

    # Resolve slug -> display label and build a minimal maneuver dict
    display_label = LABEL_SLUGS[maneuver_label]
    maneuvers_result = compute_maneuvers(event)
    maneuver = next(
        (m for m in maneuvers_result["maneuver_options"] if m["label"] == display_label),
        None,
    )
    if maneuver is None:
        raise HTTPException(
            status_code=500,
            detail=f"Could not find maneuver option {display_label!r} in computed options",
        )

    try:
        result = compute_cascade(
            event=event,
            maneuver=maneuver,
            primary_rec=pipeline["primary_rec"],
            primary_sat=pipeline["primary_sat"],
            catalog_records=pipeline["catalog_records"],
            sat_by_norad=pipeline["sat_by_norad"],
            original_events=events,
            t_start=pipeline["t_start"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result


app.include_router(router)

# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Drift Zero -- Shield pipeline")
    parser.add_argument(
        "--norad-id",
        type=int,
        default=25544,
        metavar="ID",
        help="NORAD CAT ID of the satellite to analyse (default: 25544 = ISS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            f"Use a reduced catalog ({DRY_RUN_CATALOG_LIMIT} objects), print the "
            "summary table, and skip writing conjunctions.json."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Print a structured breakdown of TCA/filter outcomes after the "
            "TCA pool drains. Can be combined with --dry-run."
        ),
    )
    args = parser.parse_args()
    run_pipeline(norad_id=args.norad_id, dry_run=args.dry_run, debug=args.debug)
