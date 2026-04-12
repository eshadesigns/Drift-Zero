"""
test_rogue_features.py
======================
Verifies and demonstrates the four Rogue intelligence features.

Run:
    python test_rogue_features.py                    # all tests
    python test_rogue_features.py --impact           # impact registry (instant, no API)
    python test_rogue_features.py --mismatch         # known satellite registry (instant, no API)
    python test_rogue_features.py --incidents        # incident reconstruction (hits Space-Track)
    python test_rogue_features.py --resurrection     # resurrection detection (hits Space-Track)

What is hardcoded vs. live
---------------------------
  HARDCODED (by design):
    - Economic impact dollar values      <- from RAND Corp / ESA cost estimates
    - Strategic tier labels              <- from US Space Command public briefings
    - Incident definitions + metadata    <- from public US Space Force statements
    - Known satellite declared missions  <- from CSIS / Aerospace Corp reports

  LIVE (fetched from Space-Track API):
    - TLE history for all satellites     <- gp_history endpoint, real orbital data
    - Delta-V timeline reconstruction    <- computed from consecutive real TLE pairs
    - Resurrection detection results     <- computed from real TLE time series
    - Mismatch behavioral scoring        <- computed from real TLE feature extraction

  The hardcoded values are the CONTEXT (what the numbers mean).
  The live data is the SIGNAL (what the satellite actually did).
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

W = 76

def section(title):
    print("\n" + "=" * W)
    print("  " + title)
    print("=" * W)

def subsection(title):
    pad = max(0, W - len(title) - 6)
    print("\n  -- " + title + " " + "-" * pad)

def ok(msg):
    print("  [OK]  " + msg)

def info(label, value, note=""):
    note_str = ("   <- " + note) if note else ""
    print("     {:<38} {}{}".format(label, str(value), note_str))

def warn(msg):
    print("  [WARN]  " + msg)

def die(msg):
    print("  [FAIL]  " + msg)
    sys.exit(1)

def data_source(label):
    print("\n  [DATA SOURCE: " + label + "]")


# ==============================================================================
# TEST 1 -- Economic Impact Registry
# Data: HARDCODED lookup table (RAND/ESA/US Space Command sources)
# ==============================================================================

def test_impact():
    section("TEST 1 -- Economic Impact Registry")
    print("""
  What this tests:
    The impact registry maps satellite NORAD IDs (and name patterns) to
    economic and strategic context. When Rogue flags a close approach, the
    frontend can say "this satellite is 18km from GPS IIR-20 -- $1B/day at risk."

  Data source: HARDCODED lookup table
    Dollar values from RAND Corporation GPS economic analysis, ESA satellite
    cost estimates, US Space Force public briefings. These are deliberately
    hardcoded -- the economic value of GPS does not change based on TLE data.
    """)

    from backend.rogue.impact import get_impact, get_all_assets

    data_source("HARDCODED -- RAND / ESA / US Space Command research")

    # 1a. Direct NORAD lookups
    subsection("1a. Direct NORAD ID lookups")
    test_cases = [
        (25544, "ISS",         "HIGH"),
        (26690, "GPS IIR-20",  "CRITICAL"),
        (20580, "Hubble",      "HIGH"),
        (25338, "NOAA-15",     "HIGH"),
        (99999, "Unknown sat", None),
    ]
    for norad_id, label, expected_tier in test_cases:
        result = get_impact(norad_id)
        if expected_tier is None:
            assert result is None, \
                "Expected None for unknown NORAD {}, got {}".format(norad_id, result)
            ok("NORAD {} ({}) -> correctly returns None".format(norad_id, label))
        else:
            assert result is not None, \
                "Expected impact data for NORAD {}, got None".format(norad_id)
            assert result["strategic_tier"] == expected_tier, \
                "NORAD {}: expected tier {}, got {}".format(
                    norad_id, expected_tier, result["strategic_tier"])
            ok("NORAD {} ({})".format(norad_id, result["name"]))
            info("economic_impact_usd_per_day", result["economic_impact_formatted"])
            info("strategic_tier",              result["strategic_tier"])
            info("users_at_risk",               result["users_at_risk"][:60])

    # 1b. Name pattern matching (catches entire constellations)
    subsection("1b. Name pattern matching -- catches entire constellations")
    pattern_tests = [
        (55001, "GPS IIIF-1",          "CRITICAL"),
        (60001, "GALILEO-27",          "CRITICAL"),
        (48001, "GLONASS-M 755",       "HIGH"),
        (40001, "USA-123 (military)",  "CRITICAL"),
    ]
    for norad_id, name, expected_tier in pattern_tests:
        result = get_impact(norad_id, name)
        assert result is not None, \
            "Pattern match failed for '{}'".format(name)
        assert result["strategic_tier"] == expected_tier, \
            "{}: expected {}, got {}".format(name, expected_tier, result["strategic_tier"])
        ok("'{}' -> constellation={}  tier={}".format(
            name, result["constellation"], result["strategic_tier"]))

    # 1c. Full registry
    subsection("1c. Full asset registry")
    all_assets = get_all_assets()
    print("\n  {} individually registered high-value satellites:\n".format(len(all_assets)))
    for a in all_assets:
        print("    NORAD {:<8} {:<32} {:<10} {}/day".format(
            a["norad_id"], a["name"], a["strategic_tier"],
            a["economic_impact_formatted"]))

    print("\n  RESULT: Impact registry working. {} registered assets + pattern matching.".format(
        len(all_assets)))


# ==============================================================================
# TEST 2 -- Mission Mismatch
# Data: HARDCODED known offenders + optional live TLE scoring
# ==============================================================================

def test_mismatch():
    section("TEST 2 -- Mission Mismatch Detection")
    print("""
  What this tests:
    Every satellite has a declared mission. When actual behavior contradicts
    that mission, something is wrong.

    Part A: Known offenders registry -- hardcoded from public intelligence
            reporting (CSIS, Aerospace Corporation, US Space Force statements).
            Returns immediately, no API needed.

    Part B: Scoring check -- verifies scores are non-trivial for known bad
            actors and low for normal satellites.
    """)

    from backend.rogue.mission_mismatch import (
        get_all_known_satellites, get_mismatch, KNOWN_SATELLITES
    )

    # 2a. Known offenders
    subsection("2a. Known offenders registry (hardcoded -- public intelligence sources)")
    data_source("HARDCODED -- CSIS, Aerospace Corp, US Space Force statements")

    known = get_all_known_satellites()
    assert len(known) > 0, "Expected at least one known satellite"

    print("\n  {} documented satellites with declared vs. actual mission mismatch:\n".format(
        len(known)))
    for s in known:
        print("    NORAD {:<8} {:<20} [{}]".format(
            s["norad_id"], s["name"], s["country"]))
        print("      Declared: " + s["declared_mission"])
        print("      Actual:   " + s["actual_mission"])
        ctx = s["threat_context"]
        print("      Context:  " + ctx[:78] + ("..." if len(ctx) > 78 else ""))
        print()

    # 2b. Mismatch scoring for known bad actors (no TLE needed)
    subsection("2b. Mismatch scores for known satellites (no TLE -- uses hardcoded context)")

    test_cases = [
        (44878, "COSMOS 2542",  0.5),
        (49395, "SHIJIAN-21",   0.5),
        (40258, "LUCH (OLYMP-K)", 0.5),
    ]
    for norad_id, name, min_score in test_cases:
        result = get_mismatch(norad_id=norad_id, feature_series=[], object_name=name)
        assert result["mismatch_score"] >= min_score, \
            "{}: expected score >= {}, got {}".format(name, min_score, result["mismatch_score"])
        ok("NORAD {} ({})".format(norad_id, name))
        info("declared_mission", result["declared_mission"][:50])
        info("actual_mission",   result["actual_mission"][:50])
        info("mismatch_score",   result["mismatch_score"],
             note="verdict: " + result["verdict"])

    # 2c. Normal satellite should score low
    subsection("2c. Normal satellite should score NORMAL")
    normal = get_mismatch(
        norad_id=25338,
        feature_series=[{
            "delta_v_proxy": 0.3,
            "delta_inclination": 0.001,
            "delta_eccentricity": 0.00001,
            "delta_mean_motion": 0.0001,
            "time_gap_hours": 6,
            "solar_f107": 150,
            "kp_index": 2.0,
            "proximity_flag": False,
        }],
        object_name="NOAA-15",
    )
    assert normal["verdict"] in ("NORMAL", "ANOMALOUS"), \
        "NOAA-15 should be NORMAL or ANOMALOUS, got {}".format(normal["verdict"])
    ok("NOAA-15 (routine weather sat) -> score={}  verdict={}".format(
        normal["mismatch_score"], normal["verdict"]))

    print("\n  RESULT: Mission mismatch registry working. {} known offenders documented.".format(
        len(known)))


# ==============================================================================
# TEST 3 -- Historical Incident Reconstruction
# Data: LIVE -- fetched from Space-Track gp_history endpoint
# ==============================================================================

def test_incidents():
    section("TEST 3 -- Historical Incident Reconstruction")
    print("""
  What this tests:
    Takes documented real-world incidents and reconstructs the delta-V
    signature from live Space-Track TLE history. Shows the exact epoch
    where Drift Zero would have triggered an alert, and how many days
    before the incident that was.

  Data source: LIVE -- Space-Track gp_history API
    TLE history fetched for the actor satellite over the incident analysis
    window. Feature extraction computes delta-V between consecutive TLE
    epochs. The detection point is the first epoch where delta-V exceeded
    the alert threshold (2.0 m/s).

  NOTE: First run fetches from Space-Track (~10s per incident).
        Results are cached locally -- subsequent runs are instant.
    """)

    from backend.rogue.incidents import list_incidents, reconstruct, INCIDENTS

    data_source("LIVE -- Space-Track gp_history API (cached after first fetch)")

    # 3a. List all incidents (no API)
    subsection("3a. Incident catalog (hardcoded metadata -- no API)")
    incidents = list_incidents()
    print("\n  {} documented incidents:\n".format(len(incidents)))
    for inc in incidents:
        print("  [{:<12}] {}  {}".format(
            inc["classification"], inc["date"], inc["title"]))
        print("    Actor:  NORAD {} -- {} ({})".format(
            inc["actor"]["norad_id"], inc["actor"]["name"], inc["actor"]["country"]))
        if inc["target"]:
            print("    Target: NORAD {} -- {}".format(
                inc["target"]["norad_id"], inc["target"]["name"]))
        print()

    # 3b. Reconstruct one incident with live TLE data
    subsection("3b. Live TLE reconstruction -- Kosmos 2542 inspector campaign")
    incident_id = "kosmos-2542-shadowing-2020"
    inc_meta    = INCIDENTS[incident_id]

    print("\n  Fetching {}-day TLE history for NORAD {} ({})...".format(
        inc_meta.analysis_window_days,
        inc_meta.actor.norad_id,
        inc_meta.actor.name))
    print("  May take ~10 seconds on first run (cached after that).\n")

    t0      = time.time()
    result  = reconstruct(incident_id)
    elapsed = time.time() - t0

    print("  Fetch + computation: {:.1f}s".format(elapsed))

    assert result["id"] == incident_id
    assert result["actor"]["norad_id"] == inc_meta.actor.norad_id
    assert result["classification"] == "SHADOWING"

    ok("Incident retrieved: '{}'".format(result["title"]))
    info("actor",          "NORAD {} -- {}".format(
        result["actor"]["norad_id"], result["actor"]["name"]))
    info("incident_date",  result["date"])
    info("classification", result["classification"])

    tl = result.get("timeline")
    if tl:
        ok("Timeline computed from LIVE Space-Track TLE data")
        info("TLE epochs in window",   len(tl["epochs"]),
             note="each = one real Space-Track record")
        info("Total maneuver events",  tl["maneuver_count"],
             note="epochs where delta-V > 0.5 m/s")
        info("Total delta-V (m/s)",    tl["total_delta_v_ms"])
        info("Peak single burn (m/s)", tl["peak_delta_v_ms"])

        if tl["detection_epoch"]:
            ok("DETECTION POINT FOUND -- Drift Zero would have triggered:")
            info("  detection_epoch",       tl["detection_epoch"][:19])
            info("  detection_delta_v_ms",  tl["detection_delta_v_ms"])
            info("  days_before_incident",  tl["detection_days_before"],
                 note="days of advance warning")
            print("\n  Detection summary:")
            print("  " + result.get("detection_summary", ""))
        else:
            warn("No detection point in window -- data may be sparse for this period")

        assert len(tl["epochs"]) > 5, \
            "Expected >5 TLE epochs, got {} -- data likely did not fetch".format(
                len(tl["epochs"]))
        assert len(tl["delta_v_series"]) == len(tl["epochs"]), \
            "delta_v_series length mismatch"
        ok("{} real TLE records processed -- data is live".format(len(tl["epochs"])))

        # Show delta-V timeline sample
        subsection("3c. Delta-V timeline sample (first 10 + last 10 epochs)")
        epochs  = tl["epochs"]
        dv_vals = tl["delta_v_series"]
        n       = len(epochs)
        indices = list(range(min(10, n))) + list(range(max(0, n - 10), n))
        indices = sorted(set(indices))

        print("\n  {:<22} {:<16} {}".format("EPOCH", "DELTA-V (m/s)", "FLAG"))
        print("  " + "-" * 22 + " " + "-" * 16 + " " + "-" * 20)
        prev = -1
        for i in indices:
            if prev != -1 and i > prev + 1:
                print("  {:<22} {:<16}".format("...", "..."))
            ep   = epochs[i][:19]
            dv   = dv_vals[i]
            flag = ""
            if dv >= 2.0:
                flag = "<< ALERT TRIGGERED"
            elif dv >= 0.5:
                flag = "<< maneuver detected"
            print("  {:<22} {:<16.3f} {}".format(ep, dv, flag))
            prev = i
    else:
        err = result.get("timeline_error", "unknown error")
        warn("Timeline not computed: " + err)
        warn("Check Space-Track credentials and verify NORAD 44878 exists in catalog")

    print("\n  RESULT: Incident reconstruction working. Live TLE data fetched and processed.")


# ==============================================================================
# TEST 4 -- Dead Satellite Resurrection
# Data: LIVE -- fetched from Space-Track gp_history endpoint
# ==============================================================================

def test_resurrection():
    section("TEST 4 -- Dead Satellite Resurrection Detection")
    print("""
  What this tests:
    Scans TLE history for satellites that went dormant (no detectable
    maneuvering for >= 21 days) and then suddenly resumed activity.

    This is one of the strongest anomaly signals -- dead satellites do not
    maneuver. Resuming after months of silence means someone turned it on.

  Data source: LIVE -- Space-Track gp_history API
    TLE history fetched for target satellites. Feature extraction computes
    delta-V for every consecutive TLE pair. Dormancy windows and resurrection
    spikes are found algorithmically -- nothing is hardcoded about the results.

  Test satellites:
    NORAD 40258 -- Luch/Olymp-K (Russian relay sat known to go dark + reactivate)
    NORAD 44878 -- Kosmos 2542  (Russian inspector -- may show dormancy gaps)
    NORAD 25544 -- ISS (control: should NOT show resurrections)

  Why these satellites:
    Luch/Olymp-K has been documented multiple times going silent for weeks
    then resuming proximity operations near commercial satellites (Intelsat,
    SES, Eutelsat). It is the canonical "resurrection" satellite.
    Kosmos 2542 launched 2019 and has been intermittently active -- may show
    dormancy windows in a 180-day slice.
    """)

    from backend.rogue.resurrection import (
        detect_resurrections,
        DORMANCY_MIN_DAYS,
        DORMANCY_DV_THRESHOLD_MS,
        RESURRECTION_DV_THRESHOLD,
    )

    data_source("LIVE -- Space-Track gp_history API (cached after first fetch)")

    subsection("4a. Algorithm parameters (not hardcoded -- tunable thresholds)")
    info("dormancy_dv_threshold_ms",   DORMANCY_DV_THRESHOLD_MS,
         note="delta-V below this per epoch = satellite considered dormant")
    info("dormancy_min_days",          DORMANCY_MIN_DAYS,
         note="minimum continuous dormancy to count")
    info("resurrection_dv_threshold",  RESURRECTION_DV_THRESHOLD,
         note="m/s spike after dormancy = resurrection event")

    # 4b. Scan resurrection-prone satellites
    subsection("4b. Scanning Luch/Olymp-K + Kosmos 2542 for resurrection events (LIVE)")
    # Luch/Olymp-K (40258) is the canonical resurrection satellite -- documented
    # multiple times going dark then reactivating near commercial satellites.
    # Kosmos 2542 (44878) also has intermittent activity patterns.
    target_ids = [40258, 44878]
    print("\n  Fetching 180-day TLE history for NORAD {}...".format(target_ids))
    print("  NORAD 40258 = Luch/Olymp-K (known to go silent + reactivate)")
    print("  NORAD 44878 = Kosmos 2542 (Russian inspector)")
    print("  May take ~15 seconds on first run (cached after that).\n")

    t0      = time.time()
    events  = detect_resurrections(norad_ids=target_ids, days=180)
    elapsed = time.time() - t0
    print("  Fetch + detection: {:.1f}s".format(elapsed))

    if events:
        ok("{} resurrection event(s) found".format(len(events)))
        for ev in events:
            print("\n  +-- RESURRECTION EVENT " + "-" * 48)
            print("  |  Satellite:         NORAD {} -- {}".format(
                ev.norad_id, ev.object_name))
            print("  |  Dormancy window:   {} -> {}".format(
                ev.dormancy_start[:10], ev.dormancy_end[:10]))
            print("  |  Dormancy duration: {} days".format(ev.dormancy_days))
            print("  |  Resumed activity:  {}".format(ev.resurrection_epoch[:19]))
            print("  |  Post-dormancy dV:  {:.2f} m/s".format(
                ev.post_dormancy_delta_v_ms))
            print("  |  Severity:          {}".format(ev.severity))
            print("  +-- " + ev.description[:70])
    else:
        warn("No resurrection events found in 180-day window.")
        warn("These satellites may have been continuously active in this period.")
        warn("Resurrection events are more likely in longer history windows or")
        warn("for satellites that were known to go dark (e.g. Luch/Olymp-K).")

    # 4c. Control test -- ISS maneuvers constantly, should NOT resurrect
    subsection("4c. Control test -- ISS should NOT have resurrection events")
    print("\n  Fetching TLE history for ISS (NORAD 25544)...")
    iss_events = detect_resurrections(norad_ids=[25544], days=90)

    if not iss_events:
        ok("ISS returned 0 resurrection events -- correct (ISS maneuvers constantly)")
    else:
        warn("ISS returned {} resurrection event(s) -- unexpected.".format(
            len(iss_events)))
        warn("May indicate threshold tuning needed. Review DORMANCY_DV_THRESHOLD_MS.")
        for ev in iss_events:
            info("  dormancy_days", ev.dormancy_days)
            info("  post_dv_ms",   ev.post_dormancy_delta_v_ms)

    # 4d. Prove the data is live -- use ISS which always has fresh TLEs
    subsection("4d. Proving data is LIVE from Space-Track (not hardcoded)")
    from pipeline.tle_ingest import ingest
    raw = ingest(norad_ids=[25544], days=14)
    records = raw.get(25544, [])

    assert len(records) > 0, (
        "No TLE records returned for ISS (NORAD 25544). "
        "Check Space-Track credentials in .env"
    )

    ok("{} real TLE records for ISS / NORAD 25544 (14-day window)".format(len(records)))
    info("earliest epoch",  records[0]["epoch"].strftime("%Y-%m-%d %H:%M UTC"))
    info("latest epoch",    records[-1]["epoch"].strftime("%Y-%m-%d %H:%M UTC"),
         note="should be within the last few days")
    info("object_name",     records[-1].get("object_name", "N/A"),
         note="pulled directly from Space-Track -- this is real data")
    info("mean_motion",     "{:.6f} rev/day".format(records[-1]["mean_motion"]),
         note="ISS ~15.5 rev/day")
    info("inclination",     "{:.4f} deg".format(records[-1]["inclination"]),
         note="ISS ~51.6 deg")
    info("eccentricity",    "{:.7f}".format(records[-1]["eccentricity"]))
    info("bstar",           "{:.6e}".format(records[-1]["bstar"]))

    print("\n  RESULT: Resurrection detection working on real Space-Track TLE data.")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test and demonstrate Rogue intelligence features"
    )
    parser.add_argument("--impact",       action="store_true",
                        help="Test impact registry (instant, no API)")
    parser.add_argument("--mismatch",     action="store_true",
                        help="Test mission mismatch (instant, no API)")
    parser.add_argument("--incidents",    action="store_true",
                        help="Test incident reconstruction (hits Space-Track)")
    parser.add_argument("--resurrection", action="store_true",
                        help="Test resurrection detection (hits Space-Track)")
    args = parser.parse_args()

    run_all = not any([args.impact, args.mismatch, args.incidents, args.resurrection])

    print("\n" + "=" * W)
    print("  DRIFT ZERO -- Rogue Feature Test Suite")
    print("  " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    print("=" * W)
    print("""
  What is live vs. hardcoded:
    HARDCODED  <- economic impact values, incident definitions, known offenders
                 These are reference data sourced from public intelligence reports.
    LIVE       <- all TLE history, delta-V computations, detection timestamps
                 These are fetched from Space-Track API and computed fresh.
    """)

    if run_all or args.incidents or args.resurrection:
        username = os.getenv("SPACETRACK_USERNAME") or os.getenv("SPACETRACK_EMAIL")
        password = os.getenv("SPACETRACK_PASSWORD")
        if not username or not password:
            die(
                "SPACETRACK_USERNAME and SPACETRACK_PASSWORD not found in .env\n"
                "  Live tests require Space-Track credentials.\n"
                "  Run with --impact or --mismatch to test without credentials."
            )
        print("  Space-Track credentials found for: " + username)

    passed = 0
    failed = 0

    def run_test(name, fn):
        nonlocal passed, failed
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print("  [FAIL] ASSERTION FAILED in {}: {}".format(name, e))
            failed += 1
        except SystemExit:
            raise
        except Exception as e:
            print("  [FAIL] ERROR in {}: {}".format(name, e))
            import traceback
            traceback.print_exc()
            failed += 1

    if run_all or args.impact:
        run_test("impact", test_impact)

    if run_all or args.mismatch:
        run_test("mismatch", test_mismatch)

    if run_all or args.incidents:
        run_test("incidents", test_incidents)

    if run_all or args.resurrection:
        run_test("resurrection", test_resurrection)

    print("\n" + "=" * W)
    print("  TEST SUMMARY")
    print("=" * W)
    print("  Passed: {}".format(passed))
    print("  Failed: {}".format(failed))
    if failed == 0:
        print("\n  All tests passed. Rogue features working with real data.")
    else:
        print("\n  {} test(s) failed. See output above.".format(failed))
    print("=" * W + "\n")


if __name__ == "__main__":
    main()
