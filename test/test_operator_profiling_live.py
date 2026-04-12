"""
test_operator_profiling_live.py

Integration test for 4.2 Operator Behavior Profiling against real
Databricks data.  Requires a populated tle_history table.

PRE-REQUISITES — run these in order before this test:
    python pipeline/ingest_tle_history.py
    python pipeline/compute_maneuver_events.py       (optional, see Mode B)
    python pipeline/compute_operator_profiles.py     (optional, see Mode B)

TWO TEST MODES — choose with the --mode flag:
    python test/test_operator_profiling_live.py --mode detect
        Mode A: pulls a sample from tle_history, runs ManeuverDetector
        locally, and prints what it finds.  Does NOT write to Databricks.
        Use this to validate the detection logic before running the pipeline.

    python test/test_operator_profiling_live.py --mode query
        Mode B: queries the operator_profiles table that was written by
        compute_operator_profiles.py and prints the top operators.
        Use this to validate the pipeline output after running it.

ENV VARS REQUIRED (.env in repo root):
    DATABRICKS_HOST          e.g. https://adb-xxxx.azuredatabricks.net
    DATABRICKS_TOKEN         personal access token or service principal token
    DATABRICKS_WAREHOUSE_ID  SQL warehouse ID (find in Databricks UI -> SQL Warehouses)
    DATABRICKS_CATALOG       default: drift_zero
    DATABRICKS_SCHEMA        default: orbital
"""

import sys
import os
import argparse

import pandas as pd
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.shield.maneuver_detector import ManeuverDetector, events_to_dataframe
from backend.shield.operator_profiler import OperatorProfiler

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Config ────────────────────────────────────────────────────────────────────

CATALOG = os.getenv("DATABRICKS_CATALOG", "drift_zero")
SCHEMA  = os.getenv("DATABRICKS_SCHEMA",  "orbital")

TLE_HISTORY_TABLE    = f"{CATALOG}.{SCHEMA}.tle_history"
MANEUVER_TABLE       = f"{CATALOG}.{SCHEMA}.maneuver_events"
PROFILES_TABLE       = f"{CATALOG}.{SCHEMA}.operator_profiles"

# How many satellites to sample for Mode A (keeps the query fast)
SAMPLE_SIZE = 200

W = 72

# ── Formatting ────────────────────────────────────────────────────────────────

def banner(title):
    print()
    print("=" * W)
    print(f"  {title}")
    print("=" * W)

def section(title):
    print()
    print(f"-- {title} {'-' * (W - len(title) - 4)}")

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def info(msg): print(f"         {msg}")
def fail(msg): print(f"  [FAIL] {msg}"); sys.exit(1)


# ── Databricks helpers ────────────────────────────────────────────────────────

def get_client() -> WorkspaceClient:
    host  = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    if not host or not token:
        fail("DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env")
    return WorkspaceClient(host=host, token=token)


def run_query(w: WorkspaceClient, sql: str, warehouse_id: str) -> pd.DataFrame:
    """Executes a SQL statement and returns results as a DataFrame."""
    import time
    result = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id,
        wait_timeout="0s",
    )
    statement_id = result.statement_id
    while True:
        result = w.statement_execution.get_statement(statement_id)
        state = result.status.state.value if result.status else "UNKNOWN"
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        time.sleep(5)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Query failed [{state}]: {result.status.error}")

    if not result.result or not result.result.data_array:
        return pd.DataFrame()

    columns = [c.name for c in result.manifest.schema.columns]
    rows    = result.result.data_array if result.result.data_array else []
    return pd.DataFrame(rows, columns=columns)


def table_exists(w: WorkspaceClient, warehouse_id: str, table: str) -> bool:
    try:
        run_query(w, f"DESCRIBE TABLE {table}", warehouse_id)
        return True
    except RuntimeError:
        return False


# ── Mode A: detect from tle_history sample ───────────────────────────────────

def run_detect_mode(w: WorkspaceClient, warehouse_id: str):
    banner("MODE A -- Maneuver Detection against live tle_history")
    info("Pulls a sample of satellites from Databricks, runs ManeuverDetector")
    info("locally, and prints what it finds.  Nothing is written back.")

    section("Checking tle_history table")
    if not table_exists(w, warehouse_id, TLE_HISTORY_TABLE):
        fail(f"{TLE_HISTORY_TABLE} does not exist. Run ingest_tle_history.py first.")
    ok(f"{TLE_HISTORY_TABLE} exists")

    # Count rows first
    count_df = run_query(w, f"SELECT COUNT(*) AS n FROM {TLE_HISTORY_TABLE}", warehouse_id)
    total_rows = int(count_df["n"].iloc[0])
    ok(f"Table contains {total_rows:,} TLE records")

    if total_rows == 0:
        fail("Table is empty — run ingest_tle_history.py first")

    section(f"Fetching {SAMPLE_SIZE}-satellite sample")
    info("Picking satellites with the most historical records (most data = best signal)")

    # Get the NORAD IDs with the most history — these are the most active satellites
    top_ids_df = run_query(
        w,
        f"""
        SELECT NORAD_CAT_ID, COUNT(*) AS n
        FROM {TLE_HISTORY_TABLE}
        GROUP BY NORAD_CAT_ID
        ORDER BY n DESC
        LIMIT {SAMPLE_SIZE}
        """,
        warehouse_id,
    )
    norad_ids = top_ids_df["NORAD_CAT_ID"].tolist()
    info(f"Selected {len(norad_ids)} NORAD IDs with the most TLE history")

    # Fetch their full history
    ids_str = ", ".join(f"'{n}'" for n in norad_ids)
    tle_df = run_query(
        w,
        f"""
        SELECT NORAD_CAT_ID, OBJECT_NAME, COUNTRY_CODE, EPOCH,
               MEAN_MOTION, INCLINATION, ECCENTRICITY, RA_OF_ASC_NODE, BSTAR
        FROM {TLE_HISTORY_TABLE}
        WHERE NORAD_CAT_ID IN ({ids_str})
        ORDER BY NORAD_CAT_ID, EPOCH
        """,
        warehouse_id,
    )

    numeric_cols = ["MEAN_MOTION", "INCLINATION", "ECCENTRICITY", "RA_OF_ASC_NODE", "BSTAR"]
    for col in numeric_cols:
        tle_df[col] = pd.to_numeric(tle_df[col], errors="coerce")
    tle_df["EPOCH"] = pd.to_datetime(tle_df["EPOCH"], errors="coerce", utc=True)

    ok(f"Fetched {len(tle_df):,} TLE records for {tle_df['NORAD_CAT_ID'].nunique()} satellites")

    section("Running ManeuverDetector")
    detector = ManeuverDetector()
    events   = detector.detect(tle_df)
    ok(f"Detected {len(events):,} maneuver events")

    if not events:
        warn("No maneuver events found — check that tle_history has enough epochs per satellite")
        return

    events_df = events_to_dataframe(events)

    section("Top 10 satellites by maneuver count")
    top_sats = (
        events_df.groupby(["norad_id", "object_name", "operator"])
        .size()
        .reset_index(name="maneuver_count")
        .nlargest(10, "maneuver_count")
    )
    print(f"  {'NORAD':>8}  {'Object':22}  {'Operator':12}  {'Maneuvers':>10}")
    print(f"  {'-'*8}  {'-'*22}  {'-'*12}  {'-'*10}")
    for _, row in top_sats.iterrows():
        print(f"  {row['norad_id']:>8}  {str(row['object_name'])[:22]:22}  {row['operator']:12}  {int(row['maneuver_count']):>10}")

    section("Building operator profiles from sample")
    profiler = OperatorProfiler()
    profiles = profiler.build_profiles(events_df)

    print(f"\n  {'Operator':14}  {'Sats':>6}  {'Maneuvers':>10}  {'Rate/sat/mo':>12}  {'Likelihood':12}")
    print(f"  {'-'*14}  {'-'*6}  {'-'*10}  {'-'*12}  {'-'*12}")
    for p in sorted(profiles.values(), key=lambda x: -x.maneuver_rate_per_sat_per_month):
        print(
            f"  {p.operator:14}  {p.total_satellites:>6}  {p.total_maneuvers_180d:>10}  "
            f"{p.maneuver_rate_per_sat_per_month:>12.3f}  {p.self_clear_likelihood():12}"
        )

    section("Sample conjunction alert context strings")
    info("What the Shield UI would show for the top 3 threatening satellites:")
    profiler.build_norad_map(tle_df)
    for norad_id in norad_ids[:3]:
        ctx = profiler.get_context_string(str(norad_id))
        name = tle_df[tle_df["NORAD_CAT_ID"] == norad_id]["OBJECT_NAME"].iloc[0] if len(tle_df[tle_df["NORAD_CAT_ID"] == norad_id]) > 0 else norad_id
        print(f"\n  [{name}]")
        print(f"  {ctx}")

    ok("Mode A complete -- detection logic validated against real data")
    info("To persist results, run:")
    info("  python pipeline/compute_maneuver_events.py")
    info("  python pipeline/compute_operator_profiles.py")


# ── Mode B: query persisted operator_profiles table ──────────────────────────

def run_query_mode(w: WorkspaceClient, warehouse_id: str):
    banner("MODE B -- Query persisted operator_profiles table")
    info("Reads the operator_profiles table written by compute_operator_profiles.py")
    info("and validates its contents.")

    section("Checking tables exist")
    for table in [MANEUVER_TABLE, PROFILES_TABLE]:
        if not table_exists(w, warehouse_id, table):
            fail(f"{table} does not exist. Run the pipeline scripts first:\n"
                 "    python pipeline/compute_maneuver_events.py\n"
                 "    python pipeline/compute_operator_profiles.py")
        ok(f"{table} exists")

    section("maneuver_events table stats")
    stats = run_query(
        w,
        f"""
        SELECT
            COUNT(*)                    AS total_events,
            COUNT(DISTINCT norad_id)    AS unique_satellites,
            COUNT(DISTINCT operator)    AS unique_operators,
            MIN(epoch_pre)              AS earliest,
            MAX(epoch_post)             AS latest,
            ROUND(AVG(estimated_delta_v), 2) AS avg_dv_ms
        FROM {MANEUVER_TABLE}
        """,
        warehouse_id,
    )
    for col in stats.columns:
        print(f"  {col:25s}: {stats[col].iloc[0]}")

    section("operator_profiles table -- all operators ranked by maneuver rate")
    profiles_df = run_query(
        w,
        f"""
        SELECT operator, total_satellites, total_maneuvers_180d,
               maneuver_rate_per_sat_per_month, median_delta_v_ms
        FROM {PROFILES_TABLE}
        ORDER BY maneuver_rate_per_sat_per_month DESC
        """,
        warehouse_id,
    )

    if profiles_df.empty:
        fail("operator_profiles table is empty")

    ok(f"Found {len(profiles_df)} operator profiles")

    profiler = OperatorProfiler()
    profiler.load_profiles(profiles_df)

    print(f"\n  {'Operator':14}  {'Sats':>8}  {'Maneuvers':>10}  {'Rate/sat/mo':>12}  {'Median dv':>10}  {'Likelihood':12}")
    print(f"  {'-'*14}  {'-'*8}  {'-'*10}  {'-'*12}  {'-'*10}  {'-'*12}")
    for _, row in profiles_df.iterrows():
        op = str(row["operator"])
        p  = profiler.get_profile(op)
        likelihood = p.self_clear_likelihood() if p else "?"
        print(
            f"  {op:14}  {int(row['total_satellites']):>8}  "
            f"{int(row['total_maneuvers_180d']):>10}  "
            f"{float(row['maneuver_rate_per_sat_per_month']):>12.3f}  "
            f"{float(row['median_delta_v_ms']):>10.2f}  "
            f"{likelihood:12}"
        )

    section("Spot check: conjunction alert context for known operators")
    info("These are the strings the Shield UI would surface in an alert.")
    for op_name in ["STARLINK", "COSMOS", "ONEWEB"]:
        p = profiler.get_profile(op_name)
        if p:
            print(f"\n  {op_name}:")
            print(f"  {p.context_string()}")
        else:
            print(f"\n  {op_name}: not found in profiles table")

    section("Sanity checks")

    if len(profiles_df) < 3:
        warn(f"Only {len(profiles_df)} operators found -- tle_history may not have enough coverage")
    else:
        ok(f"{len(profiles_df)} operators profiled")

    total_maneuvers = profiles_df["total_maneuvers_180d"].astype(int).sum()
    if total_maneuvers == 0:
        fail("Zero total maneuvers -- something went wrong in compute_maneuver_events.py")
    ok(f"{total_maneuvers:,} total maneuver events across all operators")

    neg_rates = profiles_df[pd.to_numeric(profiles_df["maneuver_rate_per_sat_per_month"], errors="coerce") < 0]
    if len(neg_rates) > 0:
        fail(f"Negative maneuver rates found: {neg_rates['operator'].tolist()}")
    ok("All maneuver rates are non-negative")

    ok("Mode B complete -- pipeline output validated")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Live Databricks integration test for operator behavior profiling"
    )
    parser.add_argument(
        "--mode",
        choices=["detect", "query"],
        default="detect",
        help=(
            "detect: run ManeuverDetector against tle_history sample (no writes). "
            "query:  validate the operator_profiles table written by the pipeline."
        ),
    )
    args = parser.parse_args()

    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        fail("DATABRICKS_WAREHOUSE_ID is not set in .env")

    banner("DRIFT ZERO -- Operator Profiling Live Integration Test")
    info(f"Catalog : {CATALOG}.{SCHEMA}")
    info(f"Mode    : {args.mode}")
    info(f"Warehouse: {warehouse_id}")

    section("Connecting to Databricks")
    w = get_client()
    ok("WorkspaceClient created")

    if args.mode == "detect":
        run_detect_mode(w, warehouse_id)
    else:
        run_query_mode(w, warehouse_id)


if __name__ == "__main__":
    main()
