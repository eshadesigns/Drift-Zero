"""
compute_operator_profiles.py

Reads maneuver events from drift_zero.orbital.maneuver_events,
aggregates per-operator behavioral profiles via OperatorProfiler,
and writes to drift_zero.orbital.operator_profiles (CREATE OR REPLACE).

Run after compute_maneuver_events.py.

Usage:
    python pipeline/compute_operator_profiles.py
"""

import io
import os
import sys
import logging

import pandas as pd
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

from backend.shield.operator_profiler import OperatorProfiler

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

CATALOG     = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA      = os.getenv("DATABRICKS_SCHEMA", "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.maneuver_events"
TARGET_TABLE = f"{CATALOG}.{SCHEMA}.operator_profiles"


# ── Databricks helpers ────────────────────────────────────────────────────────

def get_client() -> WorkspaceClient:
    return WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )


def run_sql(w: WorkspaceClient, statement: str, warehouse_id: str) -> None:
    import time
    result = w.statement_execution.execute_statement(
        statement=statement,
        warehouse_id=warehouse_id,
        wait_timeout="0s",
    )
    statement_id = result.statement_id
    while True:
        result = w.statement_execution.get_statement(statement_id)
        state = result.status.state.value if result.status else "UNKNOWN"
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        log.info(f"  SQL state: {state} — waiting...")
        time.sleep(5)
    if state != "SUCCEEDED":
        error = result.status.error if result.status else None
        raise RuntimeError(f"SQL failed [{state}]: {error}")


def fetch_maneuver_events(w: WorkspaceClient, warehouse_id: str) -> pd.DataFrame:
    """Fetches the columns needed for profile aggregation."""
    log.info(f"Fetching maneuver events from {SOURCE_TABLE}...")
    import time
    result = w.statement_execution.execute_statement(
        statement=f"SELECT norad_id, operator, estimated_delta_v FROM {SOURCE_TABLE}",
        warehouse_id=warehouse_id,
        wait_timeout="0s",
    )
    statement_id = result.statement_id
    while True:
        result = w.statement_execution.get_statement(statement_id)
        state = result.status.state.value if result.status else "UNKNOWN"
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        log.info(f"  SQL state: {state} — waiting...")
        time.sleep(5)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Fetch failed [{state}]: {result.status.error}")

    columns = [c.name for c in result.manifest.schema.columns]
    rows    = result.result.data_array if result.result.data_array else []
    df = pd.DataFrame(rows, columns=columns)
    df["estimated_delta_v"] = pd.to_numeric(df["estimated_delta_v"], errors="coerce").fillna(0.0)

    log.info(f"Loaded {len(df):,} maneuver events for {df['operator'].nunique()} operators")
    return df


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    return buf.read()


def upload_and_replace(
    w: WorkspaceClient,
    df: pd.DataFrame,
    warehouse_id: str,
) -> None:
    file_path = f"{VOLUME_PATH}/operator_profiles.parquet"

    log.info(f"Uploading {len(df)} operator profiles to {file_path}...")
    w.files.upload(
        file_path=file_path,
        contents=io.BytesIO(to_parquet_bytes(df)),
        overwrite=True,
    )
    log.info("Upload complete")

    # Full refresh — operator_profiles is small (~200 rows) and recomputed each run
    run_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TARGET_TABLE}
        USING DELTA
        AS SELECT * FROM parquet.`{file_path}`
        """,
        warehouse_id,
    )
    log.info(f"{TARGET_TABLE} created/replaced successfully")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID is not set")
        sys.exit(1)

    w = get_client()

    maneuver_df = fetch_maneuver_events(w, warehouse_id)

    if maneuver_df.empty:
        log.warning("No maneuver events found — run compute_maneuver_events.py first")
        sys.exit(0)

    profiler = OperatorProfiler()
    profiler.build_profiles(maneuver_df)

    profiles_df = profiler.profiles_to_dataframe()
    log.info(f"Built profiles for {len(profiles_df)} operators")

    # Log top operators by maneuver rate for visibility
    top = profiles_df.nlargest(5, "maneuver_rate_per_sat_per_month")[
        ["operator", "total_satellites", "maneuver_rate_per_sat_per_month"]
    ]
    log.info(f"Top operators by maneuver rate:\n{top.to_string(index=False)}")

    upload_and_replace(w, profiles_df, warehouse_id)
    log.info("Operator profile computation complete")


if __name__ == "__main__":
    main()
