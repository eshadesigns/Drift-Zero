"""
recreate_tle_history_table.py

One-off recovery script: the Parquet file is already uploaded but the
CREATE TABLE SQL failed due to nanosecond timestamp precision.

This script converts the existing Parquet to microsecond timestamps,
re-uploads it, and recreates the Delta table.  Much faster than
re-fetching all data from Space-Track.

Usage:
    python pipeline/recreate_tle_history_table.py
"""

import io
import os
import sys
import logging

import pandas as pd
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

CATALOG     = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA      = os.getenv("DATABRICKS_SCHEMA",  "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
TABLE_NAME  = f"{CATALOG}.{SCHEMA}.tle_history"
FILE_PATH   = f"{VOLUME_PATH}/tle_history.parquet"


def get_client():
    return WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )


def run_sql(w, statement, warehouse_id):
    import time
    # Submit async (wait_timeout="0s" means don't wait inline)
    result = w.statement_execution.execute_statement(
        statement=statement,
        warehouse_id=warehouse_id,
        wait_timeout="0s",
    )
    statement_id = result.statement_id
    # Poll until terminal state
    while True:
        result = w.statement_execution.get_statement(statement_id)
        state = result.status.state.value if result.status else "UNKNOWN"
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        log.info(f"  SQL state: {state} — waiting...")
        time.sleep(5)
    if state != "SUCCEEDED":
        raise RuntimeError(f"SQL failed [{state}]: {result.status.error}")


def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID not set")
        sys.exit(1)

    w = get_client()

    # Download the already-uploaded parquet, fix timestamps, re-upload
    log.info(f"Downloading {FILE_PATH} from Databricks volume...")
    response = w.files.download(file_path=FILE_PATH)
    raw_bytes = response.contents.read()
    log.info(f"Downloaded {len(raw_bytes) / 1_048_576:.1f} MB")

    log.info("Reading into DataFrame...")
    df = pd.read_parquet(io.BytesIO(raw_bytes))
    log.info(f"Shape: {df.shape}")

    # Fix timestamp precision: nanoseconds -> microseconds
    datetime_cols = ["EPOCH", "CREATION_DATE", "LAUNCH_DATE"]
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            df[col] = df[col].astype("datetime64[us, UTC]")
            log.info(f"  {col}: cast to microsecond UTC")

    log.info("Re-uploading fixed Parquet...")
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    w.files.upload(file_path=FILE_PATH, contents=buf, overwrite=True)
    log.info(f"Upload complete ({buf.tell() / 1_048_576:.1f} MB)")

    log.info(f"Dropping old table if it exists...")
    try:
        run_sql(w, f"DROP TABLE IF EXISTS {TABLE_NAME}", warehouse_id)
    except Exception as e:
        log.warning(f"Drop failed (likely didn't exist): {e}")

    log.info(f"Creating Delta table {TABLE_NAME}...")
    run_sql(
        w,
        f"""
        CREATE TABLE {TABLE_NAME}
        USING DELTA
        AS SELECT * FROM parquet.`{FILE_PATH}`
        """,
        warehouse_id,
    )
    log.info(f"Done — {TABLE_NAME} is ready")


if __name__ == "__main__":
    main()
