"""
run_rogue.py
Drift Zero — Rogue Intelligence end-to-end runner

Pipeline
--------
1. Fetch current solar weather from NOAA SWPC (no auth required)
2. Ingest 180-day TLE history from Space-Track (or local JSON cache)
3. Fetch upcoming CDMs from Space-Track (gracefully degraded if unavailable)
4. Per satellite:
     a. Sort TLEs by epoch
     b. Compute delta features for every consecutive TLE pair
     c. Feed first WARMUP_OBS pairs into SatelliteBaseline (EWMA warm-up)
     d. Train one IsolationForest on the warmup feature vectors
     e. Score remaining observations with AnomalyDetector
5. Print every SUSPICIOUS and ADVERSARIAL event to stdout

Usage
-----
    python run_rogue.py                          # default target list
    python run_rogue.py --norad-ids 25544 48274  # specific satellites
    python run_rogue.py --force-refresh          # bypass local cache

Environment (.env)
------------------
    SPACETRACK_USERNAME=<your email>
    SPACETRACK_PASSWORD=<your password>

Assumptions
-----------
- A single IsolationForest is trained per satellite on its own warmup data
  (cluster_id = norad_id).  For a production deployment these would be
  k-means cluster models trained across the full catalogue.
- Solar F10.7 and Kp are constant across the analysis window (latest values
  only).  A production pipeline would interpolate per-epoch space-weather.
- CDM MISS_DISTANCE from Space-Track is in meters; we convert to km.
- If fewer than WARMUP_OBS TLE pairs exist, the satellite is skipped.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.tle_ingest import SpaceTrackClient, ingest
from rogue.anomaly_detector import FEATURE_KEYS, AnomalyDetector
from rogue.feature_engineering import extract_delta_features
from rogue.pol_model import SatelliteBaseline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s: %(message)s",
)
logger = logging.getLogger("run_rogue")

# ─── Configuration ─────────────────────────────────────────────────────────────

# Default targets: ISS, CSS (Tianhe), Starlink-1, GPS IIR-20
DEFAULT_NORAD_IDS = [25544, 48274, 44713, 28190]

DAYS_OF_HISTORY = 180
WARMUP_OBS = 20        # TLE pairs used to build EWMA baseline + train IsoForest
MIN_ISO_OBS = 10       # minimum observations required to fit IsolationForest


# ─── Solar weather ─────────────────────────────────────────────────────────────

def fetch_solar_weather() -> tuple[float, float]:
    """
    Return (f107, kp) — most recent observed values from NOAA SWPC.
    Falls back to solar-moderate defaults on any failure.
    """
    f107, kp = 150.0, 3.0

    try:
        data = requests.get(
            "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",
            timeout=15,
        ).json()
        f107 = float(data[-1].get("f10.7", f107))
    except Exception as exc:
        logger.warning(f"F10.7 fetch failed (default {f107}): {exc}")

    try:
        data = requests.get(
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
            timeout=15,
        ).json()
        first = data[0]
        if isinstance(first, list):
            # list-of-lists: row 0 = column headers, row 1+ = data
            kp = float(data[1][1])
        elif isinstance(first, dict):
            kp = float(first.get("kp") or first.get("Kp") or kp)
    except Exception as exc:
        logger.warning(f"Kp fetch failed (default {kp}): {exc}")

    return f107, kp


# ─── CDM fetching ──────────────────────────────────────────────────────────────

def fetch_cdms(norad_ids: list[int]) -> list[dict]:
    """
    Fetch upcoming CDMs for all target satellites from Space-Track.
    Returns a list of dicts with keys sat_id and miss_distance_km.
    Returns [] gracefully if Space-Track auth is unavailable.
    """
    try:
        client = SpaceTrackClient()
        client.login()
    except Exception as exc:
        logger.warning(f"CDM fetch skipped (auth unavailable): {exc}")
        return []

    all_cdms: list[dict] = []
    for nid in norad_ids:
        for raw in client.fetch_cdm(nid):
            try:
                all_cdms.append({
                    "sat_id": int(raw.get("SAT_1_ID", nid)),
                    # Space-Track MISS_DISTANCE is in metres
                    "miss_distance_km": float(raw.get("MISS_DISTANCE") or 0) / 1000.0,
                    "tca": raw.get("TCA"),
                    "pc": float(raw.get("COLLISION_PROBABILITY") or 0),
                })
            except Exception:
                continue

    logger.info(f"CDMs loaded: {len(all_cdms)}")
    return all_cdms


# ─── Feature extraction ────────────────────────────────────────────────────────

def build_feature_series(
    records: list[dict], f107: float, kp: float
) -> list[dict]:
    """
    Compute delta features for every consecutive TLE pair in `records`.
    `records` must already be sorted by epoch ascending.
    """
    features: list[dict] = []
    for i in range(1, len(records)):
        try:
            feat = extract_delta_features(records[i - 1], records[i], f107, kp)
            features.append(feat)
        except Exception as exc:
            logger.debug(f"Feature extraction skipped at index {i}: {exc}")
    return features


# ─── IsolationForest training ──────────────────────────────────────────────────

def train_iso(feature_series: list[dict]) -> IsolationForest | None:
    """Fit an IsolationForest on FEATURE_KEYS columns of the given series."""
    if len(feature_series) < MIN_ISO_OBS:
        return None
    X = np.array([[f.get(k, 0.0) for k in FEATURE_KEYS] for f in feature_series])
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(X)
    return model


# ─── Main pipeline ─────────────────────────────────────────────────────────────

def run(
    norad_ids: list[int] = None,
    days: int = DAYS_OF_HISTORY,
    force_refresh: bool = False,
) -> list:
    if norad_ids is None:
        norad_ids = DEFAULT_NORAD_IDS

    logger.info("=== Drift Zero — Rogue Intelligence ===")
    logger.info(f"Targets: {norad_ids}  |  History window: {days}d")

    # ── Step 1: Solar weather ───────────────────────────────────────────────
    logger.info("Fetching solar weather (NOAA SWPC)...")
    f107, kp = fetch_solar_weather()
    logger.info(f"  F10.7 = {f107:.1f}   Kp = {kp:.2f}")

    # ── Step 2: TLE history ─────────────────────────────────────────────────
    logger.info("Ingesting TLE history (Space-Track / cache)...")
    tles_by_sat = ingest(norad_ids=norad_ids, days=days, force_refresh=force_refresh)

    # ── Step 3: CDMs ────────────────────────────────────────────────────────
    logger.info("Fetching CDMs...")
    cdm_events = fetch_cdms(norad_ids)

    # ── Step 4: Build baselines, warmup, and per-satellite IsoForest ────────
    baseline_store: dict[int, SatelliteBaseline] = {}
    iso_models: dict[int, IsolationForest] = {}
    scored_features: dict[int, list[dict]] = {}  # post-warmup features per sat

    for norad_id, records in tles_by_sat.items():
        if len(records) < 3:
            logger.warning(f"NORAD {norad_id}: only {len(records)} TLEs — skipping")
            continue

        records_sorted = sorted(records, key=lambda r: r["epoch"])
        feature_series = build_feature_series(records_sorted, f107, kp)

        if len(feature_series) < WARMUP_OBS + 1:
            logger.warning(
                f"NORAD {norad_id}: {len(feature_series)} feature pairs "
                f"(need >{WARMUP_OBS}) — skipping"
            )
            continue

        warmup = feature_series[:WARMUP_OBS]
        to_score = feature_series[WARMUP_OBS:]

        # Initialize baseline and warm up EWMA stats
        baseline = SatelliteBaseline(norad_id=norad_id, cluster_id=norad_id)
        for feat in warmup:
            baseline.update(feat)
        baseline_store[norad_id] = baseline

        # Train per-satellite IsolationForest (cluster_id = norad_id)
        iso = train_iso(warmup)
        if iso is not None:
            iso_models[norad_id] = iso
        else:
            logger.warning(
                f"NORAD {norad_id}: warmup too small for IsolationForest "
                f"({len(warmup)} < {MIN_ISO_OBS}) — iso_score will be 0"
            )

        scored_features[norad_id] = to_score
        logger.info(
            f"NORAD {norad_id}: {len(records_sorted)} TLEs → "
            f"{len(feature_series)} pairs | warmup={len(warmup)} | score={len(to_score)}"
        )

    if not baseline_store:
        logger.error("No satellites had enough data. Exiting.")
        return []

    # ── Step 5: Score ───────────────────────────────────────────────────────
    detector = AnomalyDetector(baseline_store=baseline_store, iso_models=iso_models)
    flagged: list = []

    for norad_id, features in scored_features.items():
        logger.info(f"Scoring NORAD {norad_id}: {len(features)} observations...")
        for feat in features:
            try:
                event = detector.score(norad_id, feat, cdm_events)
                if event.severity in ("SUSPICIOUS", "ADVERSARIAL"):
                    flagged.append(event)
            except Exception as exc:
                logger.debug(
                    f"Score failed NORAD {norad_id} "
                    f"epoch={feat.get('epoch')}: {exc}"
                )

    # ── Step 6: Report ──────────────────────────────────────────────────────
    sep = "═" * 72
    print(f"\n{sep}")
    print("  DRIFT ZERO — ROGUE INTELLIGENCE REPORT")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  |  "
          f"F10.7={f107:.0f}  Kp={kp:.1f}")
    print(sep)

    if not flagged:
        print("\n  No SUSPICIOUS or ADVERSARIAL events detected.\n")
    else:
        flagged.sort(key=lambda e: e.composite_score, reverse=True)
        print(f"\n  {len(flagged)} flagged event(s):\n")
        for ev in flagged:
            epoch_str = (
                ev.epoch.strftime("%Y-%m-%dT%H:%M:%SZ")
                if hasattr(ev.epoch, "strftime")
                else str(ev.epoch)
            )
            print(f"  [{ev.severity}]  NORAD {ev.norad_id}  epoch={epoch_str}")
            print(
                f"    composite={ev.composite_score:.3f}  "
                f"z_max={ev.z_score_max:.2f}  "
                f"iso={ev.iso_score:.3f}  "
                f"proximity={ev.proximity_flag}"
            )
            if ev.anomalous_features:
                print(f"    anomalous: {ev.anomalous_features}")
            print(f"    {ev.description}")
            print()

    print(sep + "\n")
    return flagged


# ─── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Drift Zero — Rogue Intelligence pipeline"
    )
    parser.add_argument(
        "--norad-ids", nargs="+", type=int, default=DEFAULT_NORAD_IDS,
        help="NORAD IDs to analyze (default: ISS, CSS, Starlink-1, GPS IIR-20)",
    )
    parser.add_argument(
        "--days", type=int, default=DAYS_OF_HISTORY,
        help=f"Days of TLE history to fetch (default: {DAYS_OF_HISTORY})",
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Re-fetch from Space-Track even if a local cache exists",
    )
    args = parser.parse_args()

    run(norad_ids=args.norad_ids, days=args.days, force_refresh=args.force_refresh)
