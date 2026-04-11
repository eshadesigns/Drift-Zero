"""
backend/shield/main.py

Orchestrates the full Shield collision-avoidance pipeline:

  1. Authenticate with Space-Track and fetch GP records
     (800 PAYLOAD + 800 DEBRIS, most recent TLE per object)
  2. Parse each record into a sgp4 Satrec
  3. screen.py  → candidate conjunction pairs
  4. tca.py     → Time of Closest Approach for each pair (threaded)
  5. probability.py → collision probability + confidence
  6. Filter:  miss_distance_km > 50 km  OR  Pc < 1e-12  → discard
  7. Compute risk_score (0–100) composite
  8. Sort descending by risk_score
  9. Write backend/shield/output/conjunctions.json
 10. FastAPI  GET /conjunctions?min_risk=0&limit=20

Risk score weights
------------------
  50 % collision_probability  — log-scaled, Pc=1e-12 → 0, Pc≥1e-2 → 50
  30 % miss_distance_km       — linear inverse, 0 km → 30, 50 km → 0
  20 % secondary object type  — DEBRIS 20, ROCKET BODY 15, UNKNOWN 10, PAYLOAD 5

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
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from backend.shield.propagate import parse_satrec
from backend.shield.screen import screen
from backend.shield.tca import find_tca
from backend.shield.probability import compute_probability

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent.parent / ".env")

SPACETRACK_BASE  = "https://www.space-track.org"
SPACETRACK_LOGIN = f"{SPACETRACK_BASE}/ajaxauth/login"

# LEO payload: periapsis 300–2000 km, ordered by most-recently updated TLE first
SPACETRACK_PAYLOAD_URL = (
    "{base}/basicspacedata/query/class/gp"
    "/OBJECT_TYPE/PAYLOAD"
    "/PERIAPSIS/300--2000"           # LEO band only
    "/DECAY_DATE/null-val"           # still in orbit
    "/orderby/EPOCH%20desc"          # freshest TLEs first → active crowded shells
    "/format/json"
    "/limit/{limit}"
)

# LEO debris: same altitude band; DECAY_DATE/null-val excludes re-entered objects
# (gp class has no DECAYED column — that lives in satcat)
SPACETRACK_DEBRIS_URL = (
    "{base}/basicspacedata/query/class/gp"
    "/OBJECT_TYPE/DEBRIS"
    "/PERIAPSIS/300--2000"           # LEO band only
    "/DECAY_DATE/null-val"           # still in orbit
    "/orderby/EPOCH%20desc"          # freshest TLEs first
    "/format/json"
    "/limit/{limit}"
)

FETCH_LIMIT          = 800          # per object type (full run)
DRY_RUN_FETCH_LIMIT  = 100          # per object type (--dry-run)
MAX_TCA_WORKERS      = 6            # parallel TCA threads
MAX_TCA_PAIRS        = 5000         # cap after screening to keep runtime manageable

NOAA_KP_URL = (
    "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
)

MISS_FILTER_KM  = 200.0
PC_FILTER       = 1e-15
PC_LOG_MIN      = 1e-12             # Pc floor for log-scale (= 0 points)
PC_LOG_MAX      = 1e-2              # Pc ceiling for log-scale (= 50 points)

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "conjunctions.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


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


def _fetch_gp(session: requests.Session, obj_type: str, limit: int) -> list[dict]:
    """Fetch LEO GP records for PAYLOAD or DEBRIS."""
    template = (
        SPACETRACK_PAYLOAD_URL if obj_type == "PAYLOAD" else SPACETRACK_DEBRIS_URL
    )
    url = template.format(base=SPACETRACK_BASE, limit=limit)
    log.info("Fetching %d LEO %s records from Space-Track...", limit, obj_type)
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    records = resp.json()
    log.info("  Received %d %s records", len(records), obj_type)
    return records


# ── NOAA SWPC Kp fetch ────────────────────────────────────────────────────────

def _fetch_kp() -> Optional[float]:
    """
    Fetch the most recent *observed* Kp index from NOAA SWPC.

    Response is a list-of-lists: row 0 = column headers, rows 1+ = data.
    Each data row: [time_tag, kp_value, quality_string].
    Quality values: 'observed' | 'estimated' | 'predicted'.

    Returns the Kp float, or None if the fetch/parse fails (pipeline continues
    without the solar weather override in that case).
    """
    try:
        resp = requests.get(NOAA_KP_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("NOAA SWPC Kp fetch failed: %s — solar override disabled", exc)
        return None

    if not data or not isinstance(data, list):
        log.warning("NOAA SWPC Kp: unexpected response format — solar override disabled")
        return None

    kp_val: Optional[float] = None

    if isinstance(data[0], list):
        # list-of-lists: row 0 is the header row, skip it
        for row in data[1:]:
            if len(row) >= 3 and str(row[2]).strip().lower() == "observed":
                try:
                    kp_val = float(row[1])
                except (ValueError, TypeError):
                    pass
        # Fallback: use the first data row if no "observed" entry found
        if kp_val is None and len(data) > 1:
            try:
                kp_val = float(data[1][1])
            except (ValueError, TypeError, IndexError):
                pass

    elif isinstance(data[0], dict):
        for row in data:
            quality = (
                row.get("observed") or row.get("kp_type") or ""
            ).lower()
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
        log.warning("NOAA SWPC Kp: unrecognised response format — solar override disabled")
        return None

    if kp_val is None:
        log.warning("NOAA SWPC Kp: could not extract a value — solar override disabled")
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
        # Space-Track EPOCH has no timezone — assume UTC
        epoch = datetime.fromisoformat(epoch_str.replace("Z", "")).replace(
            tzinfo=timezone.utc
        )
        delta = datetime.now(timezone.utc) - epoch
        return delta.total_seconds() / 60.0
    except ValueError:
        return 9999.0


# ── Risk score ────────────────────────────────────────────────────────────────

_TYPE_SCORE: dict[str, float] = {
    "DEBRIS":        20.0,
    "ROCKET BODY":   15.0,
    "UNKNOWN":       10.0,
    "PAYLOAD":        5.0,
}


def _risk_score(pc: float, miss_km: float, secondary_type: str) -> float:
    """
    Composite risk score 0–100.

    50 % Pc component — log-scaled between PC_LOG_MIN and PC_LOG_MAX
    30 % miss distance — linear inverse (0 km = 30, 50 km = 0)
    20 % object type   — DEBRIS 20, ROCKET BODY 15, UNKNOWN 10, PAYLOAD 5
    """
    # Pc component
    safe_pc  = max(pc, PC_LOG_MIN)
    log_norm = (math.log10(safe_pc) - math.log10(PC_LOG_MIN)) / (
        math.log10(PC_LOG_MAX) - math.log10(PC_LOG_MIN)
    )
    pc_comp = min(max(log_norm, 0.0), 1.0) * 50.0

    # Miss distance component
    miss_comp = max(0.0, 1.0 - miss_km / MISS_FILTER_KM) * 30.0

    # Object type component
    type_key  = secondary_type.strip().upper()
    type_comp = _TYPE_SCORE.get(type_key, 10.0)

    return round(pc_comp + miss_comp + type_comp, 2)


# ── TCA worker (runs in thread) ───────────────────────────────────────────────

def _run_tca_pair(
    rec_a: dict, sat_a, rec_b: dict, sat_b, t_start: datetime,
    debug_sink: Optional[list] = None,
    miss_sink: Optional[list] = None,
    kp: Optional[float] = None,
) -> Optional[dict]:
    """
    Run TCA → probability for one candidate pair.
    Returns a fully assembled conjunction event dict, or None if filtered out.

    debug_sink: if provided, appends one outcome dict per pair (see --debug).
    miss_sink:  if provided, appends every non-None miss distance (km) before
                any filter runs — used to report the global closest approach
                regardless of whether the pair passed filters.
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
        miss_sink.append(miss)          # record before any filter

    if miss > MISS_FILTER_KM:
        if debug_sink is not None:
            debug_sink.append(
                {"tca_none": False, "miss_km": miss,
                 "filtered_miss": True, "filtered_pc": False}
            )
        return None

    age_a    = _data_age_minutes(rec_a)
    age_b    = _data_age_minutes(rec_b)
    data_age = max(age_a, age_b)   # report worst-case data quality

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

    pc         = result["collision_probability"]
    miss       = result["miss_distance_km"]
    sec_type   = rec_b.get("OBJECT_TYPE", "UNKNOWN")
    risk       = _risk_score(pc, miss, sec_type)

    # Solar weather override — Kp degrades TLE-based confidence
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
            "norad_id":   int(rec_a.get("NORAD_CAT_ID", 0)),
            "name":       rec_a.get("OBJECT_NAME", ""),
            "tle_epoch":  rec_a.get("EPOCH", ""),
            "object_type": rec_a.get("OBJECT_TYPE", "UNKNOWN"),
        },
        "secondary": {
            "norad_id":   int(rec_b.get("NORAD_CAT_ID", 0)),
            "name":       rec_b.get("OBJECT_NAME", ""),
            "tle_epoch":  rec_b.get("EPOCH", ""),
            "object_type": sec_type,
        },
        "tca_utc":                result["tca_utc"],
        "miss_distance_km":       round(miss, 4),
        "relative_velocity_km_s": round(result["relative_velocity_km_s"], 4),
        "collision_probability":  pc,
        "pc_method":              result["pc_method"],
        "confidence":             confidence,
        "kp_index":               round(kp, 1) if kp is not None else None,
        "risk_score":             risk,
        "do_nothing_confidence":  0.5,   # placeholder — Taher/Nikhil to replace
        "data_source":            "spacetrack",
        "data_age_minutes":       round(data_age, 1),
    }


# ── Debug stats ──────────────────────────────────────────────────────────────

def _print_debug_stats(debug_records: list[dict]) -> None:
    """Print a structured breakdown of TCA/filter outcomes to stdout."""
    total        = len(debug_records)
    tca_none     = sum(1 for r in debug_records if r["tca_none"])
    had_tca      = [r for r in debug_records if not r["tca_none"]]
    filt_miss    = sum(1 for r in had_tca if r["filtered_miss"])
    filt_pc      = sum(1 for r in had_tca if r["filtered_pc"])
    passed       = sum(1 for r in had_tca if not r["filtered_miss"] and not r["filtered_pc"])
    miss_vals    = [r["miss_km"] for r in had_tca if r["miss_km"] is not None]

    W = 72
    print("\n" + "-" * W)
    print("  DEBUG -- TCA / FILTER BREAKDOWN")
    print("-" * W)
    print(f"  Candidate pairs processed : {total}")
    print(f"  TCA returned None         : {tca_none}"
          f"  ({100*tca_none/total:.1f}%)" if total else "")
    print(f"  TCA succeeded             : {len(had_tca)}")
    print()
    if miss_vals:
        miss_min  = min(miss_vals)
        miss_max  = max(miss_vals)
        miss_mean = sum(miss_vals) / len(miss_vals)
        # Percentile-style buckets
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
    dry_run: bool = False,
    min_miss_km: Optional[float] = None,
) -> None:
    W = 110
    SEP = "=" * W
    mode = " [DRY RUN -- 100 objects/type, no file written]" if dry_run else ""
    miss_str = (
        f"  closest approach seen (all pairs): {min_miss_km:.4f} km"
        if min_miss_km is not None else ""
    )
    print("\n" + SEP)
    print(f"  DRIFT ZERO -- SHIELD PIPELINE RESULTS   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}{mode}")
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
        f"{'CONF':>8}  {'PRIMARY':<22}  {'SECONDARY':<22}  TCA UTC"
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
            f"{ev['primary']['name'][:22]:<22}  "
            f"{ev['secondary']['name'][:22]:<22}  "
            f"{ev['tca_utc'][:19]}"
        )
    if len(events) > 20:
        print(f"  ... and {len(events) - 20} more events (see conjunctions.json)")
    print(SEP + "\n")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False, debug: bool = False) -> list[dict]:
    """
    Execute the full Shield pipeline and return sorted conjunction events.

    Args:
        dry_run: If True, fetch only 100 objects per type, skip writing
                 conjunctions.json, and label the summary as a dry run.
        debug:   If True, collect per-pair TCA/filter outcomes and print a
                 structured breakdown (None count, miss distribution, filter
                 split) after the TCA pool drains.
    """
    t_start = datetime.now(timezone.utc)
    fetch_limit = DRY_RUN_FETCH_LIMIT if dry_run else FETCH_LIMIT

    if dry_run:
        log.info("*** DRY RUN: %d PAYLOAD + %d DEBRIS, no file output ***",
                 fetch_limit, fetch_limit)

    # 0. Solar weather — fetch current Kp index before anything else
    kp_index = _fetch_kp()

    # 1. Fetch records
    session  = _spacetrack_session()
    payloads = _fetch_gp(session, "PAYLOAD", fetch_limit)
    debris   = _fetch_gp(session, "DEBRIS",  fetch_limit)
    all_records = payloads + debris
    log.info("Total GP records: %d", len(all_records))

    # 2. Parse Satrecs — skip records with no TLE lines
    parsed: list[tuple[dict, object]] = []
    skipped = 0
    for rec in all_records:
        sat = parse_satrec(rec)
        if sat is None:
            skipped += 1
            continue
        parsed.append((rec, sat))
    log.info("Parsed %d Satrecs (%d skipped — missing TLE lines)", len(parsed), skipped)

    # 3. Screen for candidate pairs
    records_only = [r for r, _ in parsed]
    sat_by_norad = {r.get("NORAD_CAT_ID"): s for r, s in parsed}

    log.info("Screening %d objects for candidate pairs...", len(records_only))
    pairs = screen(records_only)
    log.info("Screen returned %d candidate pairs", len(pairs))

    # Cap to avoid extremely long runtime; prioritise pairs whose altitude bands
    # are most deeply interleaved (smallest band-overlap metric = most overlap).
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

    # 4+5. TCA + probability (threaded)
    log.info("Running TCA + probability on %d pairs (%d threads)...", len(pairs), MAX_TCA_WORKERS)
    events: list[dict] = []
    debug_records: list[dict] = [] if debug else None  # type: ignore[assignment]
    all_miss_km: list[float] = []   # every non-None miss distance, pre-filter
    done = 0

    def _worker(pair):
        rec_a, rec_b = pair
        sa = sat_by_norad.get(rec_a.get("NORAD_CAT_ID"))
        sb = sat_by_norad.get(rec_b.get("NORAD_CAT_ID"))
        if sa is None or sb is None:
            return None
        return _run_tca_pair(rec_a, sa, rec_b, sb, t_start,
                             debug_sink=debug_records,
                             miss_sink=all_miss_km,
                             kp=kp_index)

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

    # 7. Write output JSON (skipped in dry-run mode)
    if dry_run:
        log.info("DRY RUN: skipping write to %s", OUTPUT_FILE)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(
                {
                    "generated_at": t_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "total_events": len(events),
                    "events": events,
                },
                f,
                indent=2,
            )
        log.info("Wrote %d events to %s", len(events), OUTPUT_FILE)

    # 8. Print summary
    min_miss = min(all_miss_km) if all_miss_km else None
    _print_summary(events, dry_run=dry_run, min_miss_km=min_miss)

    return events


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Drift Zero — Shield API", version="0.1.0")

_cached_events: list[dict] = []


@app.on_event("startup")
async def _startup():
    """Load conjunctions.json into memory on startup (if it exists)."""
    global _cached_events
    if OUTPUT_FILE.exists():
        try:
            data = json.loads(OUTPUT_FILE.read_text())
            _cached_events = data.get("events", [])
            log.info("Loaded %d cached events from %s", len(_cached_events), OUTPUT_FILE)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not load cached events: %s", exc)


@app.get("/conjunctions")
def get_conjunctions(
    min_risk: float = Query(default=0.0, ge=0.0, le=100.0),
    limit:    int   = Query(default=20,  ge=1,   le=500),
):
    """
    Return conjunction events sorted by risk_score descending.

    Query params:
      min_risk  — minimum risk_score threshold (0–100, default 0)
      limit     — maximum number of events to return (1–500, default 20)
    """
    if not _cached_events:
        raise HTTPException(
            status_code=503,
            detail="No conjunction data available. Run the pipeline first.",
        )

    filtered = [e for e in _cached_events if e["risk_score"] >= min_risk]
    return {
        "total_matching": len(filtered),
        "returned":       min(len(filtered), limit),
        "events":         filtered[:limit],
    }


@app.post("/conjunctions/refresh")
async def refresh_conjunctions():
    """Re-run the pipeline and reload the cache. May take 30–90 seconds."""
    global _cached_events
    try:
        _cached_events = run_pipeline()
        return {"status": "ok", "total_events": len(_cached_events)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Drift Zero — Shield pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Fetch only 100 PAYLOAD + 100 DEBRIS objects, print the summary "
            "table, and skip writing conjunctions.json. Use this to verify "
            "Space-Track auth and pipeline health before a full pull."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "After the TCA pool drains, print a structured breakdown: "
            "how many TCA results were None, miss-distance distribution "
            "(min/mean/max + cumulative buckets), and filter split "
            "(miss > 50 km vs Pc < 1e-12). Can be combined with --dry-run."
        ),
    )
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run, debug=args.debug)
