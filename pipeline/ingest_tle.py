"""
ingest_tle.py

Fetches the latest TLE data from Space-Track.org for a given set of NORAD IDs,
converts to Parquet, uploads to a Databricks Unity Catalog Volume, and creates
or replaces the Delta table from that file.

Usage:
    python pipeline/ingest_tle.py
"""

import io
import os
import sys
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
SPACETRACK_TLE_URL = (
    "https://www.space-track.org/basicspacedata/query"
    "/class/gp/NORAD_CAT_ID/{norad_ids}/format/json"
)

CATALOG = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "orbital")
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
TABLE_NAME = f"{CATALOG}.{SCHEMA}.tle_live"

# Columns to keep — everything the intelligence layer needs
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

def fetch_tles(norad_ids: list[int]) -> list[dict]:
    """
    Authenticates to Space-Track and fetches the latest GP record
    for each NORAD ID. Returns raw JSON records.
    """
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

    ids_str = ",".join(str(n) for n in norad_ids)
    url = SPACETRACK_TLE_URL.format(norad_ids=ids_str)

    log.info(f"Fetching TLEs for NORAD IDs: {ids_str}")
    resp = session.get(url, timeout=60)
    resp.raise_for_status()

    records = resp.json()
    log.info(f"Received {len(records)} TLE records")
    return records


# ── Transform ─────────────────────────────────────────────────────────────────

def to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Converts raw Space-Track JSON records to a clean DataFrame.
    Selects relevant columns and casts numeric fields.
    """
    df = pd.DataFrame(records)

    # Keep only the columns we need (drop any missing ones gracefully)
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

    df["NORAD_CAT_ID"] = df["NORAD_CAT_ID"].astype(str)

    log.info(f"DataFrame shape: {df.shape}")
    return df


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    return buf.read()


# ── Databricks ────────────────────────────────────────────────────────────────

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


def setup_unity_catalog(w: WorkspaceClient, warehouse_id: str) -> None:
    """Creates the catalog, schema, and volume if they don't already exist."""
    log.info(f"Ensuring catalog '{CATALOG}' exists...")
    run_sql(w, f"CREATE CATALOG IF NOT EXISTS {CATALOG}", warehouse_id)

    log.info(f"Ensuring schema '{CATALOG}.{SCHEMA}' exists...")
    run_sql(w, f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}", warehouse_id)

    log.info(f"Ensuring volume '{VOLUME_PATH}' exists...")
    run_sql(w, f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw", warehouse_id)


def upload_and_register(parquet_bytes: bytes, warehouse_id: str) -> None:
    """
    Uploads the Parquet file to the UC Volume and creates/replaces
    the Delta table from it via SQL statement execution.
    """
    w = WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )

    setup_unity_catalog(w, warehouse_id)

    file_path = f"{VOLUME_PATH}/tle_live.parquet"

    log.info(f"Uploading parquet to {file_path}...")
    w.files.upload(
        file_path=file_path,
        contents=io.BytesIO(parquet_bytes),
        overwrite=True,
    )
    log.info("Upload complete")

    sql = f"""
        CREATE OR REPLACE TABLE {TABLE_NAME}
        USING DELTA
        AS SELECT * FROM parquet.`{file_path}`
    """

    log.info(f"Creating Delta table {TABLE_NAME}...")
    run_sql(w, sql, warehouse_id)
    log.info(f"Table {TABLE_NAME} created successfully")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID is not set")
        sys.exit(1)

    # Start with ISS — expand this list as needed
    norad_ids = [25544]

    records = fetch_tles(norad_ids)
    df = to_dataframe(records)
    parquet_bytes = to_parquet_bytes(df)
    upload_and_register(parquet_bytes, warehouse_id)

    log.info("Ingestion complete")


if __name__ == "__main__":
    main()
