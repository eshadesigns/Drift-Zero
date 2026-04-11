"""
ingest_tle_history.py

Fetches 180-day TLE history for all active LEO satellites from Space-Track,
converts to Parquet, uploads to a Databricks Unity Catalog Volume, and
creates or merges into the tle_history Delta table.

Composite key: NORAD_CAT_ID + EPOCH (one row per satellite per TLE update)

Usage:
    python pipeline/ingest_tle_history.py
"""

import io
import os
import sys
import time
import logging

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
SPACETRACK_HISTORY_URL = (
    "https://www.space-track.org/basicspacedata/query"
    "/class/gp_history"
    "/NORAD_CAT_ID/{norad_ids}"
    "/EPOCH/%3Enow-180"
    "/orderby/NORAD_CAT_ID%20asc,EPOCH%20asc"
    "/format/json"
)

CATALOG = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
TABLE_NAME = f"{CATALOG}.{SCHEMA}.tle_history"

BATCH_SIZE = 100       # NORAD IDs per Space-Track request
BATCH_SLEEP_SEC = 1.5  # courtesy sleep between batches to avoid rate limits

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


def fetch_active_leo_norad_ids(session: requests.Session) -> list[str]:
    """Returns NORAD_CAT_IDs for all active LEO satellites."""
    log.info("Fetching active LEO satellite list...")
    resp = session.get(SPACETRACK_LEO_URL, timeout=60)
    resp.raise_for_status()
    records = resp.json()
    ids = [r["NORAD_CAT_ID"] for r in records if r.get("NORAD_CAT_ID")]
    log.info(f"Found {len(ids)} active LEO satellites")
    return ids


def fetch_history_batch(session: requests.Session, norad_ids: list[str]) -> list[dict]:
    """Fetches 180-day TLE history for a batch of NORAD IDs."""
    ids_str = ",".join(norad_ids)
    url = SPACETRACK_HISTORY_URL.format(norad_ids=ids_str)
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    return resp.json()


def fetch_all_history(session: requests.Session, norad_ids: list[str]) -> pd.DataFrame:
    """
    Fetches 180-day history for all NORAD IDs in batches.
    Returns a single combined DataFrame.
    """
    batches = [
        norad_ids[i : i + BATCH_SIZE]
        for i in range(0, len(norad_ids), BATCH_SIZE)
    ]
    total = len(batches)
    log.info(f"Fetching history in {total} batches of up to {BATCH_SIZE} satellites...")

    all_records = []
    for i, batch in enumerate(batches, start=1):
        log.info(f"Batch {i}/{total} ({len(batch)} satellites)...")
        records = fetch_history_batch(session, batch)
        all_records.extend(records)
        if i < total:
            time.sleep(BATCH_SLEEP_SEC)

    log.info(f"Total records fetched: {len(all_records)}")
    return to_dataframe(all_records)


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

    datetime_cols = ["EPOCH", "CREATION_DATE", "LAUNCH_DATE"]
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            # Databricks only supports microsecond precision — cast down from nanoseconds
            df[col] = df[col].astype("datetime64[us, UTC]")

    df["NORAD_CAT_ID"] = df["NORAD_CAT_ID"].astype(str)

    # Drop exact duplicates on composite key before upload
    df = df.drop_duplicates(subset=["NORAD_CAT_ID", "EPOCH"])

    log.info(f"DataFrame shape after dedup: {df.shape}")
    return df


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    return buf.read()


# ── Databricks ────────────────────────────────────────────────────────────────

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


def table_exists(w: WorkspaceClient, warehouse_id: str) -> bool:
    try:
        run_sql(w, f"DESCRIBE TABLE {TABLE_NAME}", warehouse_id)
        return True
    except RuntimeError:
        return False


def upload_and_register(df: pd.DataFrame, warehouse_id: str) -> None:
    w = WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )

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

    log.info(f"Table {TABLE_NAME} ready")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID is not set")
        sys.exit(1)

    session = authenticate()
    norad_ids = fetch_active_leo_norad_ids(session)

    if not norad_ids:
        log.error("No active LEO satellites found — check Space-Track credentials/filters")
        sys.exit(1)

    df = fetch_all_history(session, norad_ids)

    if df.empty:
        log.warning("No historical records returned — nothing to upload")
        sys.exit(0)

    upload_and_register(df, warehouse_id)
    log.info("Historical TLE ingestion complete")


if __name__ == "__main__":
    main()
