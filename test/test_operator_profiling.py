"""
test_operator_profiling.py

Tests the 4.2 Operator Behavior Profiling pipeline end-to-end using
synthetic TLE data -- no Databricks connection required.

What this tests:
  1. ManeuverDetector   -- reads TLE time-series, flags epoch-to-epoch
                          orbital changes that exceed natural drift thresholds
  2. extract_operator   -- parses satellite names into operator labels
  3. OperatorProfiler   -- aggregates maneuver events into per-operator
                          behavioral stats
  4. context_string()   -- the text that appears in conjunction alerts, e.g.
                          "STARLINK maneuvers ~2.3x/sat/month -- HIGH likelihood
                           of self-clearing"

Run:
    python test/test_operator_profiling.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

# Make sure backend/ is importable from anywhere in the repo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.shield.maneuver_detector import (
    ManeuverDetector,
    extract_operator,
    events_to_dataframe,
    OPERATOR_ALIASES,
)
from backend.shield.operator_profiler import OperatorProfiler


# -- Terminal formatting helpers -----------------------------------------------

W = 72  # line width

def banner(title: str):
    print()
    print("=" * W)
    print(f"  {title}")
    print("=" * W)

def section(title: str):
    print()
    print(f"-- {title} {'-' * (W - len(title) - 4)}")

def ok(msg):   print(f"  [PASS]  {msg}")
def fail(msg): print(f"  [FAIL]  {msg}"); sys.exit(1)
def note(msg): print(f"          {msg}")


# -- Synthetic TLE dataset -----------------------------------------------------
#
# We build a DataFrame that looks exactly like drift_zero.orbital.tle_history.
# Three operators are represented:
#
#   STARLINK  -- active manoeuvrer: bumps MEAN_MOTION noticeably every ~7 days
#   COSMOS    -- passive/debris: tiny natural drift only, never crosses threshold
#   ONEWEB    -- moderate: one manoeuvre in the 180-day window
#
# Each satellite gets 10 TLE epochs spaced 18 days apart (180 days total).

BASE_TIME = datetime(2025, 10, 1, tzinfo=timezone.utc)
EPOCH_STEP = timedelta(days=18)   # 10 epochs x 18 days = 180 days

def make_epochs(n=10):
    return [BASE_TIME + EPOCH_STEP * i for i in range(n)]


def build_tle_history() -> pd.DataFrame:
    rows = []

    # -- STARLINK-100 (NORAD 44235) -----------------------------------------
    # Performs a station-keeping burn every other epoch (strong signal)
    for i, epoch in enumerate(make_epochs()):
        rows.append({
            "NORAD_CAT_ID":  "44235",
            "OBJECT_NAME":   "STARLINK-100",
            "COUNTRY_CODE":  "US",
            "EPOCH":         epoch,
            "MEAN_MOTION":   15.05 + (0.005 if i % 2 == 0 else 0.0),  # oscillates
            "INCLINATION":   53.0,
            "ECCENTRICITY":  0.0001,
            "RA_OF_ASC_NODE": 120.0,
            "BSTAR":         0.00012,
        })

    # -- STARLINK-200 (NORAD 44236) -----------------------------------------
    # Different Starlink sat -- also manoeuvres, confirms fleet-level pattern
    for i, epoch in enumerate(make_epochs()):
        rows.append({
            "NORAD_CAT_ID":  "44236",
            "OBJECT_NAME":   "STARLINK-200",
            "COUNTRY_CODE":  "US",
            "EPOCH":         epoch,
            "MEAN_MOTION":   15.06 + (0.003 if i % 3 == 0 else 0.0),
            "INCLINATION":   53.0,
            "ECCENTRICITY":  0.0001,
            "RA_OF_ASC_NODE": 122.0,
            "BSTAR":         0.00011,
        })

    # -- COSMOS-2576 (NORAD 57166) ------------------------------------------
    # Russian debris-class object -- micro natural drift only, below every threshold
    for epoch in make_epochs():
        rows.append({
            "NORAD_CAT_ID":  "57166",
            "OBJECT_NAME":   "COSMOS 2576",
            "COUNTRY_CODE":  "CIS",
            "EPOCH":         epoch,
            "MEAN_MOTION":   14.01 + 0.00001,   # essentially flat
            "INCLINATION":   65.0,
            "ECCENTRICITY":  0.0002,
            "RA_OF_ASC_NODE": 80.0,
            "BSTAR":         0.00005,
        })

    # -- ONEWEB-0123 (NORAD 48463) -----------------------------------------
    # One deliberate avoidance burn at epoch 5: orbit steps up and stays there
    # (permanent altitude raise, not a round-trip pulse — so only one threshold
    # crossing occurs rather than two)
    for i, epoch in enumerate(make_epochs()):
        rows.append({
            "NORAD_CAT_ID":  "48463",
            "OBJECT_NAME":   "ONEWEB-0123",
            "COUNTRY_CODE":  "GB",
            "EPOCH":         epoch,
            "MEAN_MOTION":   13.0 + (0.002 if i >= 5 else 0.0),
            "INCLINATION":   87.9,
            "ECCENTRICITY":  0.0001,
            "RA_OF_ASC_NODE": 200.0,
            "BSTAR":         0.00009,
        })

    df = pd.DataFrame(rows)
    df["EPOCH"] = pd.to_datetime(df["EPOCH"], utc=True)
    return df


# -- Test 1: operator name extraction -----------------------------------------

def test_operator_extraction():
    banner("TEST 1 -- Operator Name Extraction")
    note("extract_operator() parses OBJECT_NAME to find the constellation owner.")
    note("It matches against known prefixes (Starlink, OneWeb, GPS, etc.).")
    note("Falls back to COUNTRY_CODE if no prefix matches.")
    section("Test cases")

    cases = [
        ("STARLINK-1234",    "US",  "STARLINK"),
        ("ONEWEB-0099",      "GB",  "ONEWEB"),
        ("COSMOS 2576",      "CIS", "COSMOS"),
        ("GPS BIIF-3",       "US",  "GPS"),
        ("ISS (ZARYA)",      "ISS", "ISS"),
        ("UNKNOWN-SAT-9999", "FR",  "FR"),        # no prefix match -> country code
        ("",                 "CN",  "CN"),          # empty name -> country code
    ]

    all_passed = True
    for name, cc, expected in cases:
        result = extract_operator(name, cc)
        passed = result == expected
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  extract_operator({name!r:25s}, {cc!r:5s})  ->  {result!r}  (expected {expected!r})")
        if not passed:
            all_passed = False

    if not all_passed:
        fail("Operator extraction has unexpected results")
    ok(f"All {len(cases)} extraction cases passed")


# -- Test 2: maneuver detection ------------------------------------------------

def test_maneuver_detection(tle_df: pd.DataFrame) -> list:
    banner("TEST 2 -- Maneuver Detection from TLE Time-Series")
    note("ManeuverDetector compares consecutive TLE epochs for each satellite.")
    note("A maneuver is flagged when any of these thresholds are crossed:")
    note("  |delta MEAN_MOTION|   > 0.001 rev/day  (altitude / velocity change)")
    note("  |delta INCLINATION|   > 0.01deg           (plane change burn)")
    note("  |delta ECCENTRICITY|  > 0.0005          (perigee/apogee raise)")
    note("Delta-v is estimated using the vis-viva approximation from the")
    note("MEAN_MOTION change (same formula used in rogue/feature_engineering.py).")

    section("Running detection on synthetic dataset")
    note(f"Input: {len(tle_df)} TLE records across {tle_df['NORAD_CAT_ID'].nunique()} satellites")

    detector = ManeuverDetector()
    events = detector.detect(tle_df)

    section("Detected maneuver events")
    print(f"  {'NORAD':>8}  {'Operator':12}  {'epoch_pre':22}  {'delta MM (rev/d)':>13}  {'deltav proxy (m/s)':>14}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*22}  {'-'*13}  {'-'*14}")
    for e in events:
        ts = e.epoch_pre.strftime("%Y-%m-%d %H:%M") if e.epoch_pre else "?"
        print(
            f"  {e.norad_id:>8}  {e.operator:12}  {ts:22}  "
            f"{e.delta_mean_motion:>+13.5f}  {e.estimated_delta_v:>14.2f}"
        )

    section("Validation")

    # STARLINK sats should each have multiple events
    starlink_events = [e for e in events if e.operator == "STARLINK"]
    if len(starlink_events) < 2:
        fail(f"Expected >=2 Starlink maneuver events, got {len(starlink_events)}")
    ok(f"STARLINK: {len(starlink_events)} maneuver events detected (expected >=2)")

    # COSMOS should have zero events (below every threshold)
    cosmos_events = [e for e in events if e.operator == "COSMOS"]
    if cosmos_events:
        fail(f"COSMOS should have 0 events (natural drift only), got {len(cosmos_events)}")
    ok("COSMOS:   0 maneuver events (natural drift stays below threshold)")

    # ONEWEB should have exactly 1 event
    oneweb_events = [e for e in events if e.operator == "ONEWEB"]
    if len(oneweb_events) != 1:
        fail(f"ONEWEB should have exactly 1 event, got {len(oneweb_events)}")
    ok("ONEWEB:   1 maneuver event detected (single avoidance burn)")

    # All delta-v values should be positive
    if any(e.estimated_delta_v < 0 for e in events):
        fail("Negative delta-v values found -- estimation formula broken")
    ok("All deltav estimates are non-negative")

    return events


# -- Test 3: operator profile aggregation -------------------------------------

def test_operator_profiling(events: list) -> OperatorProfiler:
    banner("TEST 3 -- Operator Profile Aggregation")
    note("OperatorProfiler groups maneuver events by operator and computes:")
    note("  total_satellites              -- unique NORAD IDs per operator")
    note("  total_maneuvers_180d          -- all detected events in the window")
    note("  maneuver_rate_per_sat/month   -- total / satellites / 6 months")
    note("  median_delta_v_ms             -- median deltav across all events (m/s)")
    note("  self_clear_likelihood         -- HIGH / MODERATE / LOW heuristic")
    note("    HIGH     >= 1.0 manoeuvres/sat/month")
    note("    MODERATE >= 0.2 manoeuvres/sat/month")
    note("    LOW      < 0.2 manoeuvres/sat/month")

    section("Building profiles from detected events")
    events_df = events_to_dataframe(events)

    profiler = OperatorProfiler()
    profiles = profiler.build_profiles(events_df)

    section("Profile summary")
    print(
        f"  {'Operator':12}  {'Sats':>6}  {'Maneuvers':>10}  "
        f"{'Rate/sat/mo':>12}  {'Median deltav':>10}  {'Likelihood':12}"
    )
    print(f"  {'-'*12}  {'-'*6}  {'-'*10}  {'-'*12}  {'-'*10}  {'-'*12}")
    for op, p in sorted(profiles.items()):
        print(
            f"  {p.operator:12}  {p.total_satellites:>6}  {p.total_maneuvers_180d:>10}  "
            f"{p.maneuver_rate_per_sat_per_month:>12.3f}  {p.median_delta_v_ms:>10.2f}  "
            f"{p.self_clear_likelihood():12}"
        )

    section("Validation")

    sl = profiles.get("STARLINK")
    if not sl:
        fail("STARLINK profile missing")
    if sl.total_satellites != 2:
        fail(f"STARLINK should have 2 satellites, got {sl.total_satellites}")
    ok(f"STARLINK: {sl.total_satellites} satellites, rate={sl.maneuver_rate_per_sat_per_month:.3f}/sat/mo")

    ow = profiles.get("ONEWEB")
    if not ow:
        fail("ONEWEB profile missing")
    if ow.total_maneuvers_180d != 1:
        fail(f"ONEWEB should have 1 maneuver, got {ow.total_maneuvers_180d}")
    ok(f"ONEWEB:   {ow.total_maneuvers_180d} maneuver, rate={ow.maneuver_rate_per_sat_per_month:.3f}/sat/mo")

    if "COSMOS" in profiles:
        fail("COSMOS should not appear in profiles (zero maneuver events)")
    ok("COSMOS:   absent from profiles (no events to aggregate)")

    if sl.self_clear_likelihood() != "HIGH":
        fail(f"STARLINK self_clear_likelihood should be HIGH, got {sl.self_clear_likelihood()}")
    ok(f"STARLINK self-clear likelihood correctly classified as HIGH")

    if ow.self_clear_likelihood() not in ("MODERATE", "LOW"):
        fail("ONEWEB likelihood should be MODERATE or LOW")
    ok(f"ONEWEB   self-clear likelihood correctly classified as {ow.self_clear_likelihood()}")

    return profiler


# -- Test 4: conjunction alert context -----------------------------------------

def test_conjunction_alerts(tle_df: pd.DataFrame, profiler: OperatorProfiler):
    banner("TEST 4 -- Conjunction Alert Context Strings")
    note("This is the output that surfaces in the Shield alert UI when a")
    note("conjunction is flagged. The conjunction engine calls:")
    note("")
    note("  profiler.build_norad_map(tle_live_df)")
    note("  context = profiler.get_context_string(threatening_norad_id)")
    note("")
    note("The string is shown alongside the collision probability so operators")
    note("can judge whether to manoeuvre or wait for the threat to self-clear.")

    section("Building NORAD -> operator map from TLE data")
    profiler.build_norad_map(tle_df)
    ok(f"Mapped {len(profiler._norad_operator_map)} NORAD IDs to operators")

    section("Simulated conjunction alerts")

    scenarios = [
        ("44235", "STARLINK-100 approaches your satellite at 2.3 km miss distance"),
        ("48463", "ONEWEB-0123 flagged -- conjunction in 6 hours"),
        ("57166", "COSMOS 2576 debris on close approach"),
        ("99999", "Unknown object -- no catalog entry"),
    ]

    for norad_id, scenario in scenarios:
        context = profiler.get_context_string(norad_id)
        print()
        print(f"  Scenario: {scenario}")
        print(f"  NORAD {norad_id} context string:")
        print(f"  +{'-' * (W - 4)}+")
        # word-wrap the context string to fit
        words = context.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > W - 8:
                print(f"  |  {line:<{W-8}}  |")
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            print(f"  |  {line:<{W-8}}  |")
        print(f"  +{'-' * (W - 4)}+")

    section("Validation")

    sl_ctx = profiler.get_context_string("44235")
    if "STARLINK" not in sl_ctx:
        fail("STARLINK context missing operator name")
    if "HIGH" not in sl_ctx:
        fail("STARLINK context should say HIGH likelihood")
    ok("STARLINK context contains operator name and HIGH likelihood")

    cosmos_ctx = profiler.get_context_string("57166")
    if "no historical maneuver data" not in cosmos_ctx:
        fail("COSMOS context should indicate no data available")
    ok("COSMOS context correctly reports no maneuver data")

    unknown_ctx = profiler.get_context_string("99999")
    if "no historical maneuver data" not in unknown_ctx:
        fail("Unknown NORAD context should fall back gracefully")
    ok("Unknown NORAD ID falls back gracefully")


# -- Test 5: DataFrame serialisation -------------------------------------------

def test_serialisation(events: list, profiler: OperatorProfiler):
    banner("TEST 5 -- DataFrame Serialisation (pipeline upload shape)")
    note("compute_maneuver_events.py and compute_operator_profiles.py both")
    note("convert their outputs to DataFrames before uploading to Databricks.")
    note("This test confirms the shape and column names are correct so the")
    note("pipeline scripts will not fail at the upload step.")

    section("maneuver_events DataFrame")
    events_df = events_to_dataframe(events)
    print(f"  Shape: {events_df.shape[0]} rows x {events_df.shape[1]} columns")
    print(f"  Columns: {list(events_df.columns)}")
    required_event_cols = {
        "norad_id", "object_name", "operator", "epoch_pre", "epoch_post",
        "time_gap_hours", "delta_mean_motion", "delta_inclination",
        "delta_eccentricity", "delta_raan", "delta_bstar", "estimated_delta_v",
    }
    missing = required_event_cols - set(events_df.columns)
    if missing:
        fail(f"maneuver_events missing columns: {missing}")
    ok(f"All {len(required_event_cols)} required columns present")

    section("operator_profiles DataFrame")
    profiles_df = profiler.profiles_to_dataframe()
    print(f"  Shape: {profiles_df.shape[0]} rows x {profiles_df.shape[1]} columns")
    print(f"  Columns: {list(profiles_df.columns)}")
    required_profile_cols = {
        "operator", "total_satellites", "total_maneuvers_180d",
        "maneuver_rate_per_sat_per_month", "median_delta_v_ms", "last_updated",
    }
    missing = required_profile_cols - set(profiles_df.columns)
    if missing:
        fail(f"operator_profiles missing columns: {missing}")
    ok(f"All {len(required_profile_cols)} required columns present")

    section("Round-trip: load_profiles() -> profiles_to_dataframe()")
    note("Simulates reading the operator_profiles Delta table back into a")
    note("fresh OperatorProfiler instance (as happens at Shield runtime).")
    profiler2 = OperatorProfiler()
    profiler2.load_profiles(profiles_df)
    profiles2_df = profiler2.profiles_to_dataframe()
    if len(profiles2_df) != len(profiles_df):
        fail(f"Round-trip row count mismatch: {len(profiles2_df)} != {len(profiles_df)}")
    ok(f"Round-trip preserved {len(profiles_df)} operator rows")


# -- Main ----------------------------------------------------------------------

def main():
    print()
    print("=" * W)
    print("  DRIFT ZERO -- Shield 4.2 Operator Behavior Profiling Tests")
    print("  No Databricks connection required -- uses synthetic TLE data")
    print("=" * W)
    note("What is operator behavior profiling?")
    note("")
    note("When Shield detects a conjunction (two satellites on a near-collision")
    note("course), the operator needs to decide: do I manoeuvre, or will the")
    note("threatening satellite move on its own? Operator profiling answers this")
    note("by looking at historical TLE records: how often does this operator's")
    note("fleet actually fire thrusters when put in similar situations?")
    note("")
    note("This test exercises the full pipeline from raw TLE rows -> alert text.")

    tle_df = build_tle_history()
    section("Synthetic dataset summary")
    note(f"  {len(tle_df)} TLE records | {tle_df['NORAD_CAT_ID'].nunique()} satellites | 180-day window")
    for norad, grp in tle_df.groupby("NORAD_CAT_ID"):
        name = grp["OBJECT_NAME"].iloc[0]
        note(f"  NORAD {norad:>6}  {name:20s}  {len(grp)} epochs")

    test_operator_extraction()
    events  = test_maneuver_detection(tle_df)
    profiler = test_operator_profiling(events)
    test_conjunction_alerts(tle_df, profiler)
    test_serialisation(events, profiler)

    banner("ALL TESTS PASSED")
    note("The operator profiling pipeline is working correctly.")
    note("")
    note("Next steps to run against real data:")
    note("  1. python pipeline/ingest_tle_history.py")
    note("  2. python pipeline/compute_maneuver_events.py")
    note("  3. python pipeline/compute_operator_profiles.py")
    print()


if __name__ == "__main__":
    main()
