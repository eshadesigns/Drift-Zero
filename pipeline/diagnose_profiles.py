"""
diagnose_profiles.py

Diagnostic queries to understand the current state of the data before
improving the maneuver detection and operator profiling.

Answers:
  1. Are Starlink/OneWeb satellites in tle_history at all?
  2. What do their delta mean_motion values actually look like?
     (helps calibrate the detection threshold)
  3. What are the most common OBJECT_NAME patterns not being caught
     by the current operator CASE statement?

Usage:
    python pipeline/diagnose_profiles.py
"""

import os
import sys
import time
import logging
import pandas as pd
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CATALOG = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA  = os.getenv("DATABRICKS_SCHEMA",  "orbital")
TLE     = f"{CATALOG}.{SCHEMA}.tle_history"
W = 72


def get_client():
    return WorkspaceClient(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
    )


def query(w, sql, warehouse_id):
    result = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=warehouse_id, wait_timeout="0s"
    )
    sid = result.statement_id
    while True:
        result = w.statement_execution.get_statement(sid)
        state = result.status.state.value if result.status else "UNKNOWN"
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        time.sleep(3)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Query failed [{state}]: {result.status.error}")
    if not result.result or not result.result.data_array:
        return pd.DataFrame()
    cols = [c.name for c in result.manifest.schema.columns]
    return pd.DataFrame(result.result.data_array, columns=cols)


def section(title):
    print(f"\n-- {title} {'-' * (W - len(title) - 4)}")


def main():
    wh = os.getenv("DATABRICKS_WAREHOUSE_ID")
    w  = get_client()

    print("=" * W)
    print("  DRIFT ZERO -- Data Diagnostic")
    print("=" * W)

    # ── 1. Overall coverage ───────────────────────────────────────────────
    section("1. tle_history coverage")
    df = query(w, f"""
        SELECT COUNT(DISTINCT NORAD_CAT_ID) AS total_sats,
               COUNT(*) AS total_records,
               MIN(EPOCH) AS earliest,
               MAX(EPOCH) AS latest
        FROM {TLE}
    """, wh)
    for col in df.columns:
        print(f"  {col:20s}: {df[col].iloc[0]}")

    # ── 2. Starlink / OneWeb presence ─────────────────────────────────────
    section("2. Starlink / OneWeb satellites in tle_history")
    df = query(w, f"""
        SELECT
            CASE
              WHEN UPPER(OBJECT_NAME) LIKE 'STARLINK%' THEN 'STARLINK'
              WHEN UPPER(OBJECT_NAME) LIKE 'ONEWEB%'   THEN 'ONEWEB'
              ELSE 'OTHER'
            END AS constellation,
            COUNT(DISTINCT NORAD_CAT_ID) AS unique_sats,
            COUNT(*) AS total_records
        FROM {TLE}
        GROUP BY 1
        ORDER BY unique_sats DESC
    """, wh)
    print(df.to_string(index=False))

    # ── 3. Starlink delta mean_motion distribution ────────────────────────
    section("3. Starlink delta mean_motion distribution (sample of 5000)")
    df = query(w, f"""
        WITH lagged AS (
            SELECT
                NORAD_CAT_ID,
                MEAN_MOTION - LAG(MEAN_MOTION) OVER (
                    PARTITION BY NORAD_CAT_ID ORDER BY EPOCH
                ) AS delta_mm,
                (unix_timestamp(EPOCH) - unix_timestamp(
                    LAG(EPOCH) OVER (PARTITION BY NORAD_CAT_ID ORDER BY EPOCH)
                )) / 3600.0 AS gap_hours
            FROM {TLE}
            WHERE UPPER(OBJECT_NAME) LIKE 'STARLINK%'
        )
        SELECT
            ROUND(PERCENTILE(ABS(delta_mm), 0.50), 6) AS p50,
            ROUND(PERCENTILE(ABS(delta_mm), 0.90), 6) AS p90,
            ROUND(PERCENTILE(ABS(delta_mm), 0.95), 6) AS p95,
            ROUND(PERCENTILE(ABS(delta_mm), 0.99), 6) AS p99,
            ROUND(MAX(ABS(delta_mm)), 6)               AS max_val,
            ROUND(AVG(gap_hours), 1)                   AS avg_gap_hours,
            COUNT(*) AS total_epochs
        FROM lagged
        WHERE delta_mm IS NOT NULL
    """, wh)
    if df.empty or df["total_epochs"].iloc[0] == '0' or df["p50"].iloc[0] is None:
        print("  No Starlink records found in tle_history!")
        print("  Root cause: SPACETRACK_LEO_URL had no orderby, so Space-Track")
        print("  returned low-NORAD-ID legacy satellites first. Starlink (44xxx+)")
        print("  was cut off by the LIMIT. Fix: re-run ingest_tle_history.py with")
        print("  orderby=NORAD_CAT_ID desc so newest constellations are fetched first.")
    else:
        print("  |delta mean_motion| percentiles (rev/day):")
        for col in df.columns:
            print(f"  {col:20s}: {df[col].iloc[0]}")
        print()
        current_threshold = 0.001
        p50 = float(df["p50"].iloc[0])
        p90 = float(df["p90"].iloc[0])
        print(f"  Current threshold : {current_threshold}")
        print(f"  p50 delta_mm      : {p50:.6f}  ({'BELOW' if p50 < current_threshold else 'ABOVE'} threshold)")
        print(f"  p90 delta_mm      : {p90:.6f}  ({'BELOW' if p90 < current_threshold else 'ABOVE'} threshold)")

    # ── 4. Top OBJECT_NAME patterns not in current CASE ──────────────────
    section("4. Top 20 OBJECT_NAME prefixes not caught by operator CASE")
    df = query(w, f"""
        SELECT
            SPLIT(UPPER(OBJECT_NAME), ' ')[0]    AS name_prefix,
            SPLIT(UPPER(OBJECT_NAME), '-')[0]    AS dash_prefix,
            COUNT(DISTINCT NORAD_CAT_ID)          AS unique_sats
        FROM {TLE}
        WHERE UPPER(OBJECT_NAME) NOT LIKE 'STARLINK%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'ONEWEB%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'IRIDIUM%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'GLOBALSTAR%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'GPS%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'GLONASS%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'BEIDOU%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'GALILEO%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'COSMOS%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'SES%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'INTELSAT%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'SPIRE%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'PLANET%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'SWARM%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'ICEYE%'
          AND UPPER(OBJECT_NAME) NOT LIKE 'ISS%'
        GROUP BY 1, 2
        ORDER BY unique_sats DESC
        LIMIT 20
    """, wh)
    print(df.to_string(index=False))

    # ── 5. Current threshold sensitivity ─────────────────────────────────
    section("5. How many MORE events at lower thresholds (all satellites)")
    df = query(w, f"""
        WITH lagged AS (
            SELECT
                MEAN_MOTION - LAG(MEAN_MOTION) OVER (
                    PARTITION BY NORAD_CAT_ID ORDER BY EPOCH
                ) AS delta_mm,
                INCLINATION - LAG(INCLINATION) OVER (
                    PARTITION BY NORAD_CAT_ID ORDER BY EPOCH
                ) AS delta_inc,
                ECCENTRICITY - LAG(ECCENTRICITY) OVER (
                    PARTITION BY NORAD_CAT_ID ORDER BY EPOCH
                ) AS delta_ecc
            FROM {TLE}
        )
        SELECT
            SUM(CASE WHEN ABS(delta_mm) > 0.001  OR ABS(delta_inc) > 0.01   OR ABS(delta_ecc) > 0.0005 THEN 1 ELSE 0 END) AS threshold_current,
            SUM(CASE WHEN ABS(delta_mm) > 0.0005 OR ABS(delta_inc) > 0.005  OR ABS(delta_ecc) > 0.0002 THEN 1 ELSE 0 END) AS threshold_half,
            SUM(CASE WHEN ABS(delta_mm) > 0.0002 OR ABS(delta_inc) > 0.002  OR ABS(delta_ecc) > 0.0001 THEN 1 ELSE 0 END) AS threshold_fifth,
            COUNT(*) AS total_transitions
        FROM lagged
        WHERE delta_mm IS NOT NULL
    """, wh)
    print(f"  {'Threshold':30s}  {'Events':>10}  {'% of transitions':>18}")
    print(f"  {'-'*30}  {'-'*10}  {'-'*18}")
    total = int(df["total_transitions"].iloc[0])
    for col in ["threshold_current", "threshold_half", "threshold_fifth"]:
        n = int(df[col].iloc[0])
        label = col.replace("threshold_", "").replace("_", " ").title()
        pct = n / total * 100 if total else 0
        print(f"  {col:30s}  {n:>10,}  {pct:>17.3f}%")
    print(f"  {'Total transitions':30s}  {total:>10,}")


if __name__ == "__main__":
    main()
