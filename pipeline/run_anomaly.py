"""
run_anomaly.py

Pulls tle_history from Databricks, builds per-satellite baselines,
trains one IsolationForest per orbital regime cluster, scores all
remaining data points, and writes AnomalyEvent results to
drift_zero.orbital.anomaly_events.

Usage:
    python pipeline/run_anomaly.py
"""

import io
import json
import os
import sys
import logging
from collections import defaultdict
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest

# Make backend importable from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.rogue.feature_engineering import normalize_tle_row, extract_delta_features
from backend.rogue.anomaly_detector import AnomalyDetector, AnomalyEvent, SatelliteBaseline, FEATURE_KEYS

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

CATALOG = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA  = os.getenv("DATABRICKS_SCHEMA", "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
HISTORY_TABLE  = f"{CATALOG}.{SCHEMA}.tle_history"
ANOMALY_TABLE  = f"{CATALOG}.{SCHEMA}.anomaly_events"

TRAINING_WINDOW_DAYS = 30
SOLAR_F107_PLACEHOLDER = 150.0
KP_INDEX_PLACEHOLDER   = 3.0

# Orbital regime clusters
def get_cluster_id(mean_motion: float) -> int:
    if mean_motion > 11.25:
        return 0  # LEO
    elif mean_motion >= 2.0:
        return 1  # MEO
    else:
        return 2  # GEO

CLUSTER_LABELS = {0: "LEO", 1: "MEO", 2: "GEO"}


# ── Databricks helpers ────────────────────────────────────────────────────────

def run_sql(w: WorkspaceClient, statement: str, warehouse_id: str) -> None:
    result = w.statement_execution.execute_statement(
        statement=statement,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
    )
    state = result.status.state.value if result.status else "UNKNOWN"
    if state != "SUCCEEDED":
        error = result.status.error if result.status else None
        raise RuntimeError(f"SQL failed [{state}]: {error}")


def fetch_dataframe(w: WorkspaceClient, warehouse_id: str, sql: str) -> pd.DataFrame:
    """
    Executes SQL via statement execution and returns all results as a DataFrame.
    Handles multi-chunk pagination automatically.
    """
    response = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
    )
    state = response.status.state.value if response.status else "UNKNOWN"
    if state != "SUCCEEDED":
        error = response.status.error if response.status else None
        raise RuntimeError(f"Query failed [{state}]: {error}")

    cols = [c.name for c in response.manifest.schema.columns]
    rows = []

    if response.result and response.result.data_array:
        rows.extend(response.result.data_array)

    total_chunks = response.manifest.total_chunk_count or 1
    for chunk_idx in range(1, total_chunks):
        chunk = w.statement_execution.get_statement_result_chunk_n(
            statement_id=response.statement_id,
            chunk_index=chunk_idx,
        )
        if chunk.data_array:
            rows.extend(chunk.data_array)

    return pd.DataFrame(rows, columns=cols)


def cast_tle_df(df: pd.DataFrame) -> pd.DataFrame:
    """Cast string columns from the REST API to proper Python types."""
    numeric_cols = [
        "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
        "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT",
        "SEMIMAJOR_AXIS", "PERIOD", "APOAPSIS", "PERIAPSIS",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["EPOCH", "CREATION_DATE"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    return df


# ── Core pipeline ─────────────────────────────────────────────────────────────

def build_baselines_and_training_features(
    satellite_groups: dict,
) -> tuple[dict, dict]:
    """
    For each satellite:
      - Splits records into training window (first 30 days) and scoring window
      - Builds SatelliteBaseline from training pairs
      - Collects training feature vectors per cluster for IsolationForest

    Returns:
        baselines: norad_id (str) -> SatelliteBaseline
        cluster_train_X: cluster_id -> list of feature vectors
    """
    baselines: dict[str, SatelliteBaseline] = {}
    cluster_train_X: dict[int, list] = defaultdict(list)

    for norad_id, rows in satellite_groups.items():
        if len(rows) < 2:
            continue

        min_epoch = rows[0]["EPOCH"]
        cutoff = min_epoch + timedelta(days=TRAINING_WINDOW_DAYS)

        train_rows = [r for r in rows if r["EPOCH"] <= cutoff]
        cluster_id = get_cluster_id(float(rows[0]["MEAN_MOTION"] or 0))

        baseline = SatelliteBaseline(norad_id=int(norad_id), cluster_id=cluster_id)

        for prev, curr in zip(train_rows, train_rows[1:]):
            try:
                norm_prev = normalize_tle_row(prev)
                norm_curr = normalize_tle_row(curr)
                features = extract_delta_features(
                    norm_prev, norm_curr,
                    solar_f107=SOLAR_F107_PLACEHOLDER,
                    kp=KP_INDEX_PLACEHOLDER,
                )
                baseline.update(features)
                vec = [features.get(k, 0.0) for k in FEATURE_KEYS]
                if not any(v is None or (isinstance(v, float) and np.isnan(v)) for v in vec):
                    cluster_train_X[cluster_id].append(vec)
            except Exception:
                continue

        baselines[norad_id] = baseline

    return baselines, cluster_train_X


def train_iso_models(cluster_train_X: dict) -> dict:
    """Trains one IsolationForest per orbital regime cluster."""
    iso_models = {}
    for cluster_id, X in cluster_train_X.items():
        if len(X) < 10:
            log.warning(f"Cluster {CLUSTER_LABELS[cluster_id]}: only {len(X)} training samples, skipping IsoForest")
            continue
        log.info(f"Training IsolationForest for {CLUSTER_LABELS[cluster_id]} ({len(X)} samples)...")
        model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        model.fit(X)
        iso_models[cluster_id] = model
    return iso_models


def score_satellites(
    satellite_groups: dict,
    detector: AnomalyDetector,
) -> list[AnomalyEvent]:
    """
    Runs AnomalyDetector.score() on the scoring window
    (everything after the first 30 days) for each satellite.
    """
    events = []
    for norad_id, rows in satellite_groups.items():
        if len(rows) < 2:
            continue

        min_epoch = rows[0]["EPOCH"]
        cutoff = min_epoch + timedelta(days=TRAINING_WINDOW_DAYS)
        score_rows = [r for r in rows if r["EPOCH"] > cutoff]

        for prev, curr in zip(score_rows, score_rows[1:]):
            try:
                norm_prev = normalize_tle_row(prev)
                norm_curr = normalize_tle_row(curr)
                features = extract_delta_features(
                    norm_prev, norm_curr,
                    solar_f107=SOLAR_F107_PLACEHOLDER,
                    kp=KP_INDEX_PLACEHOLDER,
                )
                event = detector.score(
                    norad_id=int(norad_id),
                    features=features,
                    cdm_events=[],  # CDM integration: pass live events here
                )
                events.append(event)
            except Exception:
                continue

    return events


# ── Output ────────────────────────────────────────────────────────────────────

def events_to_df(events: list[AnomalyEvent]) -> pd.DataFrame:
    records = []
    for e in events:
        records.append({
            "norad_id":          e.norad_id,
            "epoch":             e.epoch,
            "severity":          e.severity,
            "composite_score":   round(e.composite_score, 6),
            "z_score_max":       round(e.z_score_max, 6),
            "iso_score":         round(e.iso_score, 6),
            "proximity_flag":    e.proximity_flag,
            "anomalous_features": json.dumps(e.anomalous_features),
            "description":       e.description,
        })
    return pd.DataFrame(records)


def upload_and_register_events(
    df: pd.DataFrame,
    w: WorkspaceClient,
    warehouse_id: str,
) -> None:
    file_path = f"{VOLUME_PATH}/anomaly_events.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)

    log.info(f"Uploading {len(df):,} anomaly events to {file_path}...")
    w.files.upload(file_path=file_path, contents=buf, overwrite=True)

    log.info(f"Creating Delta table {ANOMALY_TABLE}...")
    run_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {ANOMALY_TABLE}
        USING DELTA
        AS SELECT * FROM parquet.`{file_path}`
        """,
        warehouse_id,
    )
    log.info(f"Table {ANOMALY_TABLE} ready")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID is not set")
        sys.exit(1)

    w = WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )

    # 1. Pull full history, ordered by satellite + time
    log.info(f"Querying {HISTORY_TABLE}...")
    df = fetch_dataframe(
        w, warehouse_id,
        f"SELECT * FROM {HISTORY_TABLE} ORDER BY NORAD_CAT_ID, EPOCH",
    )
    log.info(f"Loaded {len(df):,} TLE records for {df['NORAD_CAT_ID'].nunique()} satellites")

    df = cast_tle_df(df)

    # 2. Group by satellite as ordered list of row dicts
    satellite_groups: dict[str, list[dict]] = {}
    for norad_id, group in df.groupby("NORAD_CAT_ID", sort=False):
        satellite_groups[str(norad_id)] = group.to_dict(orient="records")

    # 3. Build baselines from training window + collect cluster training data
    log.info(f"Building baselines from first {TRAINING_WINDOW_DAYS} days per satellite...")
    baselines, cluster_train_X = build_baselines_and_training_features(satellite_groups)
    log.info(f"Built {len(baselines)} baselines")

    # 4. Train IsolationForest per cluster
    iso_models = train_iso_models(cluster_train_X)

    # 5. Score remaining data
    detector = AnomalyDetector(baseline_store=baselines, iso_models=iso_models)
    log.info("Scoring satellites...")
    events = score_satellites(satellite_groups, detector)
    log.info(f"Scored {len(events):,} events")

    if not events:
        log.warning("No events to write — check that tle_history has > 30 days of data")
        sys.exit(0)

    # 6. Write results
    events_df = events_to_df(events)
    upload_and_register_events(events_df, w, warehouse_id)

    # 7. Summary
    counts = events_df["severity"].value_counts()
    print("\n── Anomaly Detection Summary ──────────────────")
    for severity in ["ROUTINE", "SUSPICIOUS", "ADVERSARIAL"]:
        print(f"  {severity:<12} {counts.get(severity, 0):>6,}")
    print(f"  {'TOTAL':<12} {len(events_df):>6,}")
    print("───────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
