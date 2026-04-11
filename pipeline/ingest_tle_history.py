"""
ingest_tle_history.py

ONE-TIME bulk pull of 180-day TLE history for all active LEO satellites
from Space-Track's gp_history endpoint. Filters applied server-side in a
single request:
  - MEAN_MOTION > 11.25   (LEO regime)
  - EPOCH > now-180       (last 180 days)
  - DECAY_DATE = null-val (still in orbit)

Skips entirely if drift_zero.orbital.tle_history already has > 1000 rows —
this endpoint must never be called again once data is stored.

Usage:
    python pipeline/ingest_tle_history.py
"""

import io
import os
import sys
import logging
import time
import pandas as pd
import requests
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SPACETRACK_LOGIN_URL = "https://www.space-track.org/ajaxauth/login"

# All active LEO satellites ordered by NORAD_CAT_ID descending so newer
# constellations (Starlink 44xxx+, OneWeb 47xxx+) are fetched first.
# Limit raised to 8000 to cover the full active LEO population.
SPACETRACK_LEO_URL = (
    "https://www.space-track.org/basicspacedata/query"
    "/class/gp"
    "/DECAY_DATE/null-val"
    "/PERIAPSIS/%3C2000"
    "/orderby/NORAD_CAT_ID%20desc"
    "/format/json"
    "/limit/8000"
)

# Historical TLE for a batch of NORAD IDs over the last 180 days
# Single bulk query: LEO + last 180 days + on-orbit only
SPACETRACK_HISTORY_URL = (
    "https://www.space-track.org/basicspacedata/query"
    "/class/gp_history"
    "/MEAN_MOTION/%3E11.25"
    "/EPOCH/%3Enow-180"
    "/DECAY_DATE/null-val"
    "/orderby/NORAD_CAT_ID%20asc,EPOCH%20asc"
    "/format/json"
)

CATALOG    = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA     = os.getenv("DATABRICKS_SCHEMA", "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
TABLE_NAME  = f"{CATALOG}.{SCHEMA}.tle_history"

SKIP_THRESHOLD = 1000  # skip download if table already has this many rows

TLE_COLUMNS = [
    "NORAD_CAT_ID",
    "OBJECT_NAME",
    "OBJECT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
    "SEMIMAJOR_AXIS",
    "PERIOD",
    "APOAPSIS",
    "PERIAPSIS",
    "TLE_LINE1",
    "TLE_LINE2",
    "CREATION_DATE",
    "OBJECT_TYPE",
    "RCS_SIZE",
    "COUNTRY_CODE",
    "LAUNCH_DATE",
]


# ── Space-Track ───────────────────────────────────────────────────────────────

def authenticate() -> requests.Session:
    username = os.getenv("SPACETRACK_USERNAME")
    password = os.getenv("SPACETRACK_PASSWORD")
    if not username or not password:
        raise EnvironmentError("SPACETRACK_USERNAME and SPACETRACK_PASSWORD must be set")

    session = requests.Session()
    log.info("Authenticating with Space-Track...")
    resp = session.post(
        SPACETRACK_LOGIN_URL,
        data={"identity": username, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    if "Login" in resp.text:
        raise RuntimeError("Space-Track authentication failed — check credentials")
    return session


def fetch_history(session: requests.Session) -> list[dict]:
    """Single bulk request for all LEO gp_history records in the last 180 days."""
    log.info("Fetching bulk LEO TLE history from Space-Track (one-time pull)...")
    resp = session.get(SPACETRACK_HISTORY_URL, timeout=300)
    resp.raise_for_status()
    records = resp.json()
    log.info(f"Received {len(records):,} records")
    return records


# ── Transform ─────────────────────────────────────────────────────────────────

def to_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=TLE_COLUMNS)

    df = pd.DataFrame(records)
    cols = [c for c in TLE_COLUMNS if c in df.columns]
    df = df[cols].copy()

    numeric_cols = [
        "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR", "MEAN_MOTION_DOT",
        "MEAN_MOTION_DDOT", "SEMIMAJOR_AXIS", "PERIOD", "APOAPSIS", "PERIAPSIS",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["EPOCH", "CREATION_DATE", "LAUNCH_DATE"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            # Databricks only supports microsecond precision — cast down from nanoseconds
            df[col] = df[col].astype("datetime64[us, UTC]")

    df["NORAD_CAT_ID"] = df["NORAD_CAT_ID"].astype(str)
    df = df.drop_duplicates(subset=["NORAD_CAT_ID", "EPOCH"])

    log.info(f"DataFrame shape after dedup: {df.shape}")
    return df


# ── Databricks ────────────────────────────────────────────────────────────────

def run_sql(w: WorkspaceClient, statement: str, warehouse_id: str):
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
    return result


def existing_row_count(w: WorkspaceClient, warehouse_id: str) -> int:
    """Returns current row count of tle_history, or 0 if it doesn't exist."""
    try:
        result = run_sql(
            w,
            f"SELECT COUNT(*) as cnt FROM {TABLE_NAME}",
            warehouse_id,
        )
        data = result.result.data_array
        if data and data[0]:
            return int(data[0][0])
    except RuntimeError:
        pass
    return 0


def upload_and_register(df: pd.DataFrame, w: WorkspaceClient, warehouse_id: str) -> None:
    file_path = f"{VOLUME_PATH}/tle_history.parquet"

    # Cast timestamps to microseconds — Databricks rejects nanosecond precision
    datetime_cols = ["EPOCH", "CREATION_DATE", "LAUNCH_DATE"]
    for col in datetime_cols:
        if col in df.columns:
            df[col] = df[col].astype("datetime64[us, UTC]")

    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    size_mb = buf.tell() / 1_048_576
    buf.seek(0)

    log.info(f"Uploading {len(df):,} rows ({size_mb:.1f} MB) to {file_path}...")
    w.files.upload(file_path=file_path, contents=buf, overwrite=True)
    log.info("Upload complete")

    log.info(f"Creating Delta table {TABLE_NAME}...")
    run_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TABLE_NAME}
        USING DELTA
        AS SELECT * FROM parquet.`{file_path}`
        """,
        warehouse_id,
    )


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

    # Guard: skip if table is already populated
    count = existing_row_count(w, warehouse_id)
    if count > SKIP_THRESHOLD:
        log.info(f"tle_history already has {count:,} rows — skipping download")
        print(f"Row count: {count:,}")
        return

    session = authenticate()
    records = fetch_history(session)

    if not records:
        log.error("No records returned from Space-Track")
        sys.exit(1)

    df = to_dataframe(records)
    upload_and_register(df, w, warehouse_id)

    print(f"Row count: {len(df):,}")
    log.info("Historical TLE ingestion complete")


if __name__ == "__main__":
    main()
