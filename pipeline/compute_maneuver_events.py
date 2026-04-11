"""
compute_maneuver_events.py

Detects maneuver events from drift_zero.orbital.tle_history and writes
results to drift_zero.orbital.maneuver_events.

Detection runs entirely inside Databricks as a single SQL query using
LAG window functions — no large data transfer to local machine.

A maneuver is flagged when epoch-to-epoch deltas exceed:
  |delta MEAN_MOTION|  > 0.001 rev/day
  |delta INCLINATION|  > 0.01 degrees
  |delta ECCENTRICITY| > 0.0005

Operator name is extracted from OBJECT_NAME prefix in SQL (CASE statement
mirrors the OPERATOR_ALIASES dict in backend/shield/maneuver_detector.py).

Usage:
    python pipeline/compute_maneuver_events.py
"""

import os
import sys
import time
import logging

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

CATALOG      = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA       = os.getenv("DATABRICKS_SCHEMA",  "orbital")
SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.tle_history"
TARGET_TABLE = f"{CATALOG}.{SCHEMA}.maneuver_events"

# Mirrors OPERATOR_ALIASES in backend/shield/maneuver_detector.py
OPERATOR_CASE_SQL = """
    CASE
      WHEN UPPER(OBJECT_NAME) LIKE 'STARLINK%'   THEN 'STARLINK'
      WHEN UPPER(OBJECT_NAME) LIKE 'ONEWEB%'     THEN 'ONEWEB'
      WHEN UPPER(OBJECT_NAME) LIKE 'IRIDIUM%'    THEN 'IRIDIUM'
      WHEN UPPER(OBJECT_NAME) LIKE 'GLOBALSTAR%' THEN 'GLOBALSTAR'
      WHEN UPPER(OBJECT_NAME) LIKE 'GPS%'        THEN 'GPS'
      WHEN UPPER(OBJECT_NAME) LIKE 'GLONASS%'    THEN 'GLONASS'
      WHEN UPPER(OBJECT_NAME) LIKE 'BEIDOU%'     THEN 'BEIDOU'
      WHEN UPPER(OBJECT_NAME) LIKE 'GALILEO%'    THEN 'GALILEO'
      WHEN UPPER(OBJECT_NAME) LIKE 'COSMOS%'     THEN 'COSMOS'
      WHEN UPPER(OBJECT_NAME) LIKE 'SES%'        THEN 'SES'
      WHEN UPPER(OBJECT_NAME) LIKE 'INTELSAT%'   THEN 'INTELSAT'
      WHEN UPPER(OBJECT_NAME) LIKE 'TELESAT%'    THEN 'TELESAT'
      WHEN UPPER(OBJECT_NAME) LIKE 'EUTELSAT%'   THEN 'EUTELSAT'
      WHEN UPPER(OBJECT_NAME) LIKE 'SPIRE%'      THEN 'SPIRE'
      WHEN UPPER(OBJECT_NAME) LIKE 'PLANET%'     THEN 'PLANET'
      WHEN UPPER(OBJECT_NAME) LIKE 'SWARM%'      THEN 'SWARM'
      WHEN UPPER(OBJECT_NAME) LIKE 'ICEYE%'      THEN 'ICEYE'
      WHEN UPPER(OBJECT_NAME) LIKE 'CAPELLA%'    THEN 'CAPELLA'
      WHEN UPPER(OBJECT_NAME) LIKE 'UMBRA%'      THEN 'UMBRA'
      WHEN UPPER(OBJECT_NAME) LIKE 'ISS%'        THEN 'ISS'
      WHEN UPPER(OBJECT_NAME) LIKE 'TIANHE%'     THEN 'CSS'
      WHEN UPPER(OBJECT_NAME) LIKE 'FENGYUN%'      THEN 'FENGYUN'
      WHEN UPPER(OBJECT_NAME) LIKE 'HULIANWANG%'   THEN 'GUOWANG'
      WHEN UPPER(OBJECT_NAME) LIKE 'KUIPER%'       THEN 'KUIPER'
      WHEN UPPER(OBJECT_NAME) LIKE 'TELESAT%'      THEN 'TELESAT'
      WHEN UPPER(OBJECT_NAME) LIKE 'ORBCOMM%'      THEN 'ORBCOMM'
      WHEN UPPER(OBJECT_NAME) LIKE 'DOVE%'         THEN 'PLANET'
      WHEN UPPER(OBJECT_NAME) LIKE 'FLOCK%'        THEN 'PLANET'
      WHEN UPPER(OBJECT_NAME) LIKE 'SKYSAT%'       THEN 'PLANET'
      -- Rocket bodies and debris — group by launch vehicle family
      WHEN UPPER(OBJECT_NAME) LIKE 'SL-%'          THEN 'RUS_ROCKETBODY'
      WHEN UPPER(OBJECT_NAME) LIKE 'CZ-%'          THEN 'CHN_ROCKETBODY'
      WHEN UPPER(OBJECT_NAME) LIKE 'TBA%'          THEN 'UNKNOWN'
      WHEN COUNTRY_CODE IS NOT NULL AND COUNTRY_CODE != '' THEN UPPER(COUNTRY_CODE)
      ELSE 'UNKNOWN'
    END
"""

# Thresholds (match backend/shield/maneuver_detector.py)
# 0.0005 rev/day sits between p50 (0.000104) and p90 (0.00116) of Starlink
# delta_mm distribution — catches real burns without drowning in TLE noise.
DELTA_MM_THRESHOLD  = 0.0005
DELTA_INC_THRESHOLD = 0.005
DELTA_ECC_THRESHOLD = 0.0002

# ── Databricks ────────────────────────────────────────────────────────────────

def get_client() -> WorkspaceClient:
    return WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )


def run_sql(w: WorkspaceClient, statement: str, warehouse_id: str) -> None:
    """Submits SQL async and polls until terminal state."""
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


def table_exists(w: WorkspaceClient, warehouse_id: str, table: str) -> bool:
    try:
        run_sql(w, f"DESCRIBE TABLE {table}", warehouse_id)
        return True
    except RuntimeError:
        return False


# ── Detection SQL ─────────────────────────────────────────────────────────────

def build_detection_sql() -> str:
    """
    Single SQL statement that:
    1. Uses LAG() to compute epoch-to-epoch orbital element deltas per satellite
    2. Filters to rows where any threshold is exceeded (maneuver detected)
    3. Estimates delta-v from the mean motion change (vis-viva approximation)
    4. Extracts operator name from OBJECT_NAME using CASE

    Runs entirely inside Databricks — no data pulled to local machine.
    """
    return f"""
    WITH lagged AS (
        SELECT
            NORAD_CAT_ID,
            OBJECT_NAME,
            COUNTRY_CODE,
            EPOCH                                                              AS epoch_post,
            LAG(EPOCH)         OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS epoch_pre,
            MEAN_MOTION,
            LAG(MEAN_MOTION)   OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS prev_mean_motion,
            INCLINATION        - LAG(INCLINATION)   OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS delta_inclination,
            ECCENTRICITY       - LAG(ECCENTRICITY)  OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS delta_eccentricity,
            RA_OF_ASC_NODE     - LAG(RA_OF_ASC_NODE) OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS delta_raan,
            BSTAR              - LAG(BSTAR)          OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH) AS delta_bstar
        FROM {SOURCE_TABLE}
    ),
    with_deltas AS (
        SELECT *,
            MEAN_MOTION - prev_mean_motion AS delta_mean_motion,
            (unix_timestamp(epoch_post) - unix_timestamp(epoch_pre)) / 3600.0 AS time_gap_hours
        FROM lagged
        WHERE epoch_pre IS NOT NULL
    )
    SELECT
        NORAD_CAT_ID                                                    AS norad_id,
        OBJECT_NAME                                                     AS object_name,
        ({OPERATOR_CASE_SQL})                                           AS operator,
        epoch_pre,
        epoch_post,
        time_gap_hours,
        delta_mean_motion,
        delta_inclination,
        delta_eccentricity,
        delta_raan,
        delta_bstar,
        ABS(delta_mean_motion / NULLIF(prev_mean_motion, 0))
            * 7.784 * POWER(prev_mean_motion / 15.0, 1.0/3.0)
            * 1000                                                      AS estimated_delta_v
    FROM with_deltas
    WHERE ABS(delta_mean_motion)  > {DELTA_MM_THRESHOLD}
       OR ABS(delta_inclination)  > {DELTA_INC_THRESHOLD}
       OR ABS(delta_eccentricity) > {DELTA_ECC_THRESHOLD}
    """


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        log.error("DATABRICKS_WAREHOUSE_ID is not set")
        sys.exit(1)

    w = get_client()

    detection_sql = build_detection_sql()

    if not table_exists(w, warehouse_id, TARGET_TABLE):
        log.info(f"Creating {TARGET_TABLE} via in-database detection...")
        run_sql(
            w,
            f"CREATE TABLE {TARGET_TABLE} USING DELTA AS {detection_sql}",
            warehouse_id,
        )
    else:
        log.info(f"Merging new maneuver events into {TARGET_TABLE}...")
        run_sql(
            w,
            f"""
            MERGE INTO {TARGET_TABLE} AS target
            USING ({detection_sql}) AS source
            ON  target.norad_id  = source.norad_id
            AND target.epoch_pre = source.epoch_pre
            WHEN NOT MATCHED THEN INSERT *
            """,
            warehouse_id,
        )

    log.info(f"{TARGET_TABLE} ready")
    log.info("Maneuver event computation complete")


if __name__ == "__main__":
    main()
