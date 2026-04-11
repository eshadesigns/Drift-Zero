{
  "_meta": {
    "generated_at": "2026-04-11T17:16:12.565156+00:00Z",
    "target_object": "ISS (International Space Station)",
    "norad_id": 25544,
    "cospar_id": "1998-067A",
    "description": "One live record from each Drift Zero data source. Field names, types, and values are exactly what the pipeline will receive. See test_apis.py schema tables for per-field documentation."
  },
  "source_1_spacetrack_live_tle": {
    "_doc": "Latest TLE for the target satellite. Refresh every 4\u20138 hours. JOIN KEY: NORAD_CAT_ID",
    "_endpoint": "https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/25544/format/json/limit/1",
    "record": {
      "CCSDS_OMM_VERS": "3.0",
      "COMMENT": "GENERATED VIA SPACE-TRACK.ORG API",
      "CREATION_DATE": "2026-04-11T15:36:26",
      "ORIGINATOR": "18 SPCS",
      "OBJECT_NAME": "ISS (ZARYA)",
      "OBJECT_ID": "1998-067A",
      "CENTER_NAME": "EARTH",
      "REF_FRAME": "TEME",
      "TIME_SYSTEM": "UTC",
      "MEAN_ELEMENT_THEORY": "SGP4",
      "EPOCH": "2026-04-11T11:44:40.701408",
      "MEAN_MOTION": "15.48873216",
      "ECCENTRICITY": "0.00064320",
      "INCLINATION": "51.6326",
      "RA_OF_ASC_NODE": "270.1822",
      "ARG_OF_PERICENTER": "299.5706",
      "MEAN_ANOMALY": "60.4641",
      "EPHEMERIS_TYPE": "0",
      "CLASSIFICATION_TYPE": "U",
      "NORAD_CAT_ID": "25544",
      "ELEMENT_SET_NO": "999",
      "REV_AT_EPOCH": "56141",
      "BSTAR": "0.00011816000000",
      "MEAN_MOTION_DOT": "0.00006038",
      "MEAN_MOTION_DDOT": "0.0000000000000",
      "SEMIMAJOR_AXIS": "6798.158",
      "PERIOD": "92.971",
      "APOAPSIS": "424.396",
      "PERIAPSIS": "415.651",
      "OBJECT_TYPE": "PAYLOAD",
      "RCS_SIZE": "LARGE",
      "COUNTRY_CODE": "CIS",
      "LAUNCH_DATE": "1998-11-20",
      "SITE": "TTMTR",
      "DECAY_DATE": null,
      "FILE": "5126412",
      "GP_ID": "319129555",
      "TLE_LINE0": "0 ISS (ZARYA)",
      "TLE_LINE1": "1 25544U 98067A   26101.48935997  .00006038  00000-0  11816-3 0  9991",
      "TLE_LINE2": "2 25544  51.6326 270.1822 0006432 299.5706  60.4641 15.48873216561413"
    }
  },
  "source_2_spacetrack_cdm": {
    "_doc": "Conjunction Data Messages where the target is SAT_1. JOIN KEYS: SAT_1_ID, SAT_2_ID \u2192 NORAD_CAT_ID",
    "_endpoint": "https://www.space-track.org/basicspacedata/query/class/cdm_public/SAT_1_ID/25544/TCA/>now/format/json/orderby/TCA asc/limit/3",
    "records": [],
    "_note": "Empty list means no active conjunctions right now \u2014 this is normal. In production poll frequently and store all events."
  },
  "source_3_spacetrack_historical_tle": {
    "_doc": "Historical TLE time-series \u2014 same schema as source_1. Used by Rogue for pattern-of-life baseline.",
    "_endpoint": "https://www.space-track.org/basicspacedata/query/class/gp_history/NORAD_CAT_ID/25544/EPOCH/YYYY-MM-DD--YYYY-MM-DD/orderby/EPOCH asc/format/json",
    "total_records_last_30_days": 120,
    "sample_records": [
      {
        "CCSDS_OMM_VERS": "3.0",
        "COMMENT": "GENERATED VIA SPACE-TRACK.ORG API",
        "CREATION_DATE": "2026-03-12T07:46:21",
        "ORIGINATOR": "18 SPCS",
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "TEME",
        "TIME_SYSTEM": "UTC",
        "MEAN_ELEMENT_THEORY": "SGP4",
        "EPOCH": "2026-03-12T03:49:12.416736",
        "MEAN_MOTION": "15.48595269",
        "ECCENTRICITY": "0.00079840",
        "INCLINATION": "51.6325",
        "RA_OF_ASC_NODE": "60.1463",
        "ARG_OF_PERICENTER": "183.4136",
        "MEAN_ANOMALY": "176.6799",
        "EPHEMERIS_TYPE": "0",
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": "25544",
        "ELEMENT_SET_NO": "999",
        "REV_AT_EPOCH": "55671",
        "BSTAR": "0.00017667000000",
        "MEAN_MOTION_DOT": "0.00009166",
        "MEAN_MOTION_DDOT": "0.0000000000000",
        "SEMIMAJOR_AXIS": "6798.972",
        "PERIOD": "92.987",
        "APOAPSIS": "426.265",
        "PERIAPSIS": "415.408",
        "OBJECT_TYPE": "PAYLOAD",
        "RCS_SIZE": "LARGE",
        "COUNTRY_CODE": "CIS",
        "LAUNCH_DATE": "1998-11-20",
        "SITE": "TTMTR",
... (285 lines left)

example_data.json
15 KB
"""
Drift Zero — API Data Source Explorer
======================================
Hits all 5 data sources from the spec, prints a pipeline-oriented schema
for each one, and saves every live response to example_data.json.

Run:  python -u test_apis.py
Deps: pip install requests
"""

import requests
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SPACETRACK_EMAIL    = "taherakolawala@ufl.edu"
SPACETRACK_PASSWORD = "MHussain786110!"
ESA_DISCOS_TOKEN    = "ImVlYTczNTFlLTI3ZmItNGI4ZC1hMjQ0LTFhNDNhMmMyZTQ5YSI.fg6qVNsYnwdEDRgOMojIxjZCwJM"

# Test target: ISS — safe, always has data, well-known across all catalogs
ISS_NORAD_ID  = 25544
ISS_COSPAR_ID = "1998-067A"

OUTPUT_FILE = Path(__file__).parent / "example_data.json"

# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────

W = 72  # terminal width

def header(source_num, title, subtitle):
    """Big section header for each data source."""
    print("\n" + "━" * W)
    print(f"  SOURCE {source_num}  │  {title}")
    print(f"  {'─' * (W - 4)}")
    print(f"  {subtitle}")
    print("━" * W)

def subheader(title):
    print(f"\n  ┌─ {title} {'─' * max(0, W - len(title) - 6)}┐")

def schema_table(rows):
    """
    Print a schema table.
    rows = list of (field, type, pipeline_role, notes)
    """
    col_w = [26, 10, 20, 0]   # field, type, role — notes fills the rest
    col_w[3] = W - sum(col_w[:3]) - 7
    fmt = "  │ {:<{}} {:<{}} {:<{}} {:<{}}"

    # header row
    print("  │ " + "─" * (W - 4))
    print(fmt.format(
        "FIELD", col_w[0], "TYPE", col_w[1], "PIPELINE ROLE", col_w[2], "NOTES", col_w[3]
    ))
    print("  │ " + "─" * (W - 4))

    for field, typ, role, notes in rows:
        # Word-wrap notes if too long
        words = notes.split()
        lines = []
        line  = ""
        for w in words:
            if len(line) + len(w) + 1 <= col_w[3]:
                line = (line + " " + w).strip()
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)

        print(fmt.format(field, col_w[0], typ, col_w[1], role, col_w[2], lines[0] if lines else "", col_w[3]))
        for extra in lines[1:]:
            print(fmt.format("", col_w[0], "", col_w[1], "", col_w[2], extra, col_w[3]))

    print("  └" + "─" * (W - 2))


def live_value(label, value, note=""):
    """Print a single live value from the actual API response."""
    note_str = f"  ← {note}" if note else ""
    print(f"    {label:<30} {str(value):<25}{note_str}")


# ══════════════════════════════════════════════════════════════════════
# SOURCE 1: Space-Track — Live TLE
# ══════════════════════════════════════════════════════════════════════

def fetch_spacetrack_live_tle(session):
    url = (
        "https://www.space-track.org/basicspacedata/query"
        f"/class/gp/NORAD_CAT_ID/{ISS_NORAD_ID}/format/json/limit/1"
    )
    return session.get(url).json()[0]


... (447 lines left)

test_apis.py
28 KB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DRIFT ZERO — API Data Source Explorer
  Target: ISS  │  NORAD 25544  │  COSPAR 1998-067A
  Output: example_data.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

terminal_Output.txt
45 KB
﻿
"""
Drift Zero — API Data Source Explorer
======================================
Hits all 5 data sources from the spec, prints a pipeline-oriented schema
for each one, and saves every live response to example_data.json.

Run:  python -u test_apis.py
Deps: pip install requests
"""

import requests
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SPACETRACK_EMAIL    = "taherakolawala@ufl.edu"
SPACETRACK_PASSWORD = "MHussain786110!"
ESA_DISCOS_TOKEN    = "ImVlYTczNTFlLTI3ZmItNGI4ZC1hMjQ0LTFhNDNhMmMyZTQ5YSI.fg6qVNsYnwdEDRgOMojIxjZCwJM"

# Test target: ISS — safe, always has data, well-known across all catalogs
ISS_NORAD_ID  = 25544
ISS_COSPAR_ID = "1998-067A"

OUTPUT_FILE = Path(__file__).parent / "example_data.json"

# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────

W = 72  # terminal width

def header(source_num, title, subtitle):
    """Big section header for each data source."""
    print("\n" + "━" * W)
    print(f"  SOURCE {source_num}  │  {title}")
    print(f"  {'─' * (W - 4)}")
    print(f"  {subtitle}")
    print("━" * W)

def subheader(title):
    print(f"\n  ┌─ {title} {'─' * max(0, W - len(title) - 6)}┐")

def schema_table(rows):
    """
    Print a schema table.
    rows = list of (field, type, pipeline_role, notes)
    """
    col_w = [26, 10, 20, 0]   # field, type, role — notes fills the rest
    col_w[3] = W - sum(col_w[:3]) - 7
    fmt = "  │ {:<{}} {:<{}} {:<{}} {:<{}}"

    # header row
    print("  │ " + "─" * (W - 4))
    print(fmt.format(
        "FIELD", col_w[0], "TYPE", col_w[1], "PIPELINE ROLE", col_w[2], "NOTES", col_w[3]
    ))
    print("  │ " + "─" * (W - 4))

    for field, typ, role, notes in rows:
        # Word-wrap notes if too long
        words = notes.split()
        lines = []
        line  = ""
        for w in words:
            if len(line) + len(w) + 1 <= col_w[3]:
                line = (line + " " + w).strip()
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)

        print(fmt.format(field, col_w[0], typ, col_w[1], role, col_w[2], lines[0] if lines else "", col_w[3]))
        for extra in lines[1:]:
            print(fmt.format("", col_w[0], "", col_w[1], "", col_w[2], extra, col_w[3]))

    print("  └" + "─" * (W - 2))


def live_value(label, value, note=""):
    """Print a single live value from the actual API response."""
    note_str = f"  ← {note}" if note else ""
    print(f"    {label:<30} {str(value):<25}{note_str}")


# ══════════════════════════════════════════════════════════════════════
# SOURCE 1: Space-Track — Live TLE
# ══════════════════════════════════════════════════════════════════════

def fetch_spacetrack_live_tle(session):
    url = (
        "https://www.space-track.org/basicspacedata/query"
        f"/class/gp/NORAD_CAT_ID/{ISS_NORAD_ID}/format/json/limit/1"
    )
    return session.get(url).json()[0]


def fetch_spacetrack_historical_tle(session):
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    date_range = f"{start.strftime('%Y-%m-%d')}--{end.strftime('%Y-%m-%d')}"
    url = (
        "https://www.space-track.org/basicspacedata/query"
        f"/class/gp_history/NORAD_CAT_ID/{ISS_NORAD_ID}"
        f"/EPOCH/{date_range}/orderby/EPOCH asc/format/json"
    )
    return session.get(url).json()


def fetch_spacetrack_cdm(session):
    url = (
        "https://www.space-track.org/basicspacedata/query"
        f"/class/cdm_public/SAT_1_ID/{ISS_NORAD_ID}"
        f"/TCA/>now/format/json/orderby/TCA asc/limit/3"
    )
    try:
        return session.get(url).json()
    except Exception:
        return []


def print_source_1(tle):
    header(1, "Space-Track.org — Live TLE", "Two-Line Element sets: the orbital state of a satellite right now.")
    print("""
  WHAT IS A TLE?
  A Two-Line Element set is a standardized snapshot of a satellite's orbit.
  Feed it into the sgp4 library to get X/Y/Z position (km) at any timestamp.
  Space-Track updates TLEs every few hours for active objects.

  JOIN KEY:  NORAD_CAT_ID  →  links to ESA DISCOS via satno field
  PARTITION: EPOCH         →  use as the Databricks Delta Lake partition key
  UPDATE FREQ: ~4–8 hrs for active LEO satellites
""")

    subheader("SCHEMA — fields the pipeline ingests from each TLE record")
    schema_table([
        ("NORAD_CAT_ID",      "str",     "JOIN KEY",          "Primary key across all space databases. Use to join with DISCOS."),
        ("OBJECT_NAME",       "str",     "label / display",   "Human-readable name. Use for UI only — not stable enough for joins."),
        ("EPOCH",             "datetime","partition key",      "When this TLE was measured. Older epoch = less accurate propagated position."),
        ("MEAN_MOTION",       "float",   "maneuver detection", "Orbits/day. Sudden delta between epochs = thruster firing (Rogue signal)."),
        ("ECCENTRICITY",      "float",   "orbit classifier",  "0 = circular, 1 = parabolic. Most LEO ops sats are < 0.01."),
        ("INCLINATION",       "float",   "orbit classifier",  "Degrees from equator. Determines ground track and coverage zone."),
        ("RA_OF_ASC_NODE",    "float",   "propagation input", "Orbital plane orientation. Drifts predictably — key input to sgp4."),
        ("ARG_OF_PERICENTER", "float",   "propagation input", "Ellipse orientation within plane. Matters for eccentric orbits."),
        ("MEAN_ANOMALY",      "float",   "propagation input", "Position within orbit at epoch. Combined with MEAN_MOTION → position."),
        ("BSTAR",             "float",   "drag correction",   "Drag coefficient. NOAA Kp/F10.7 corrects this for current solar activity."),
        ("OBJECT_TYPE",       "str",     "filter",            "PAYLOAD / DEBRIS / ROCKET BODY / UNKNOWN. Rogue profiles PAYLOAD only."),
        ("COUNTRY_CODE",      "str",     "geopolitical ctx",  "Operator country. Adds context to Rogue intent classification."),
        ("REV_AT_EPOCH",      "int",     "age proxy",         "Total revolutions since launch. Use to estimate satellite age."),
    ])

    subheader("LIVE VALUES from this request (ISS)")
    for field in ["OBJECT_NAME","NORAD_CAT_ID","EPOCH","MEAN_MOTION","ECCENTRICITY",
                  "INCLINATION","BSTAR","OBJECT_TYPE","COUNTRY_CODE"]:
        live_value(field, tle.get(field))
    print()


def print_source_3(hist_data):
    header(3, "Space-Track.org — Historical TLE Archive", "Same schema as live TLE, queried over a date range. Rogue's baseline input.")
    print(f"""
  WHAT IS THIS FOR?
  Rogue mode builds a 180-day pattern-of-life baseline per satellite by
  diffing consecutive TLE epochs. A sudden change in MEAN_MOTION or
  ECCENTRICITY = the satellite maneuvered. That is the core Rogue signal.

  SAME SCHEMA as Source 1 — only the query changes:
    Live TLE:    /class/gp/NORAD_CAT_ID/{{id}}
    Historical:  /class/gp_history/NORAD_CAT_ID/{{id}}/EPOCH/YYYY-MM-DD--YYYY-MM-DD

  Records returned (last 30 days for ISS): {len(hist_data)}
""")

    if hist_data:
        subheader("MANEUVER DETECTION SIGNAL — MEAN_MOTION sampled over 30 days")
        print(f"  {'EPOCH':<22} {'MEAN_MOTION (rev/day)':<25} {'BSTAR (drag)':<20}")
        print(f"  {'─'*22} {'─'*25} {'─'*20}")
        step = max(1, len(hist_data) // 10)
        for rec in hist_data[::step]:
            print(f"  {rec.get('EPOCH','')[:19]:<22} {str(rec.get('MEAN_MOTION','')):<25} {str(rec.get('BSTAR','')):<20}")
        print()
        print("  PIPELINE NOTE: store as a time-series table partitioned by NORAD_CAT_ID.")
        print("  Compute MEAN_MOTION delta row-by-row. Flag rows where |delta| > 0.001 rev/day.")
    print()


def print_source_2(cdm_data):
    header(2, "Space-Track.org — Conjunction Data Messages (CDMs)", "Pre-computed close-approach warnings. Primary input to Shield's alert queue.")
    print("""
  WHAT IS A CDM?
  Space-Track's CARA team computes close approaches for every tracked pair.
  A CDM is generated when two objects will come within ~5 km of each other.
  Shield consumes CDMs directly — no need to compute conjunctions from scratch.

  UPDATE FREQ: Multiple times per day. New CDMs appear as orbital states update.
  JOIN KEY:    SAT_1_ID / SAT_2_ID  →  NORAD_CAT_ID in TLE table
""")

    subheader("SCHEMA — fields the pipeline ingests from each CDM record")
    schema_table([
        ("CDM_ID",               "str",     "primary key",       "Unique ID for this conjunction event."),
        ("SAT_1_NAME",           "str",     "display",           "Your asset. Filter CDMs where SAT_1 is in your constellation."),
        ("SAT_1_ID",             "str",     "JOIN KEY",          "NORAD ID of your asset. Join to TLE table for current state."),
        ("SAT_2_NAME",           "str",     "display",           "The threat object."),
        ("SAT_2_ID",             "str",     "JOIN KEY",          "NORAD ID of the threat. Join to TLE + DISCOS for full profile."),
        ("TCA",                  "datetime","event timestamp",   "Time of Closest Approach — when they are nearest. This drives alert timing."),
        ("MISS_DISTANCE",        "float",   "risk metric",       "Closest approach distance in meters. <1000m = worth reviewing."),
        ("COLLISION_PROBABILITY","float",   "risk metric",       "Impact probability 0–1. >1e-4 = standard maneuver threshold."),
        ("RELATIVE_SPEED",       "float",   "risk metric",       "m/s at closest approach. Higher = more kinetic energy if impact occurs."),
        ("SAT_2_OBJECT_TYPE",    "str",     "filter",            "DEBRIS / PAYLOAD / ROCKET BODY. Payload = may maneuver (check operator profile)."),
        ("PC_METHOD",            "str",     "model metadata",    "Which probability model was used. Affects how to interpret the Pc value."),
    ])

    if not cdm_data:
        print("\n  LIVE: No upcoming CDMs for ISS right now (normal — conjunctions are rare).")
        print("  The pipeline should poll /class/cdm_public/limit/100 on a schedule and store all events.\n")
    else:
        subheader(f"LIVE VALUES — {len(cdm_data)} upcoming conjunction(s) found for ISS")
        for i, cdm in enumerate(cdm_data):
            print(f"\n  Conjunction #{i+1}:")
            for field in ["SAT_1_NAME","SAT_2_NAME","TCA","MISS_DISTANCE","COLLISION_PROBABILITY","RELATIVE_SPEED","SAT_2_OBJECT_TYPE"]:
                live_value(field, cdm.get(field))
    print()


# ══════════════════════════════════════════════════════════════════════
# SOURCE 4: ESA DISCOS
# ══════════════════════════════════════════════════════════════════════

def fetch_esa_discos():
    headers = {
        "Authorization": f"Bearer {ESA_DISCOS_TOKEN}",
        "DiscosWeb-Api-Version": "2",
        "Accept": "application/json"
    }
    BASE = "https://discosweb.esoc.esa.int/api"
    url  = f"{BASE}/objects?filter=eq(cosparId,'{ISS_COSPAR_ID}')"
    resp = requests.get(url, headers=headers)

    if resp.status_code == 401:
        print("\n  !! ESA DISCOS: 401 Unauthorized — check ESA_DISCOS_TOKEN")
        return None, None
    if resp.status_code != 200:
        print(f"\n  !! ESA DISCOS: request failed {resp.status_code} — {resp.text[:200]}")
        return None, None

    data = resp.json()
    if not data.get("data"):
        return None, data

    return data["data"][0].get("attributes", {}), data


def print_source_4(obj):
    header(4, "ESA DISCOS — Debris & Spacecraft Physical Catalog",
           "Physical properties of space objects. Space-Track = WHERE. DISCOS = WHAT.")
    print("""
  WHAT IS DISCOS?
  ESA's Database and Information System Characterising Objects in Space.
  Provides mass, dimensions, shape, and cross-section for every tracked object.

  WHY THE PIPELINE NEEDS IT:
  → mass (kg)      feeds the Tsiolkovsky fuel equation in Shield
  → xSectAvg (m²) feeds the collision probability model
  → objectClass   tells Rogue which objects are worth profiling

  JOIN KEY:  satno  →  NORAD_CAT_ID in Space-Track TLE table
  AUTH:      Bearer token  +  header DiscosWeb-Api-Version: 2  (both required)
  BASE URL:  https://discosweb.esoc.esa.int/api
""")

    subheader("SCHEMA — fields the pipeline ingests from each DISCOS object record")
    schema_table([
        ("satno",         "int",   "JOIN KEY",          "NORAD catalog number. Use to join with Space-Track TLE records."),
        ("cosparId",      "str",   "secondary key",     "COSPAR ID. Format YYYY-NNNX. Cross-reference when NORAD IDs mismatch."),
        ("name",          "str",   "display only",      "ESA catalog name. May differ from Space-Track name — use IDs for joins."),
        ("objectClass",   "str",   "filter",            "Payload / Debris / Rocket Body / Unknown. Rogue profiles Payload only."),
        ("mass",          "float", "fuel equation",     "Dry mass in kg. Required input to Tsiolkovsky: Δm = m*(1 - e^(-Δv/ve))."),
        ("xSectAvg",      "float", "collision prob",    "Average radar cross-section m². Larger = higher effective collision area."),
        ("xSectMax",      "float", "collision prob",    "Max cross-section (broadside). Use for worst-case Pc bound."),
        ("depth",         "float", "physical model",    "Depth dimension in meters."),
        ("height",        "float", "physical model",    "Height dimension in meters."),
        ("span",          "float", "physical model",    "Span (width) in meters."),
        ("shape",         "str",   "physical model",    "Geometry: Box+Appendages, Cylinder, Sphere, etc. Affects tumble/drag."),
    ])

    if obj is None:
        print("\n  LIVE: Could not retrieve DISCOS data — see error above.\n")
        return

    subheader("LIVE VALUES from this request (ISS)")
    for field in ["satno","cosparId","name","objectClass","mass","xSectAvg","xSectMax","depth","height","span","shape"]:
        live_value(field, obj.get(field))
    print()


# ══════════════════════════════════════════════════════════════════════
# SOURCE 5: NOAA SWPC
# ══════════════════════════════════════════════════════════════════════

def fetch_noaa():
    kp_raw   = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json").json()
    f107_raw = requests.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json").json()
    wind_raw = requests.get("https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json").json()
    return kp_raw, f107_raw, wind_raw


def parse_kp(kp_raw):
    first = kp_raw[0]
    if isinstance(first, list):
        # list-of-lists: row 0 = headers, row 1+ = data
        row = kp_raw[1]
        return {"time_tag": row[0], "kp": row[1], "quality": row[2]}
    elif isinstance(first, dict):
        return {
            "time_tag": first.get("time_tag"),
            "kp":       first.get("kp") or first.get("Kp") or first.get("kp_index"),
            "quality":  first.get("observed") or first.get("kp_type") or "N/A"
        }
    return {}


def parse_wind(wind_raw):
    first = wind_raw[0]
    last  = wind_raw[-1]
    if isinstance(first, list) and all(isinstance(x, str) for x in first):
        return {"time_tag": last[0], "density": last[1], "speed": last[2], "temperature": last[3]}
    elif isinstance(last, dict):
        return {
            "time_tag":   last.get("time_tag"),
            "density":    last.get("density")     or last.get("proton_density"),
            "speed":      last.get("speed")        or last.get("bulk_speed"),
            "temperature":last.get("temperature")  or last.get("ion_temperature")
        }
    return {}


def print_source_5(kp_raw, f107_raw, wind_raw):
    header(5, "NOAA SWPC — Solar Weather & Atmospheric Drag",
           "No API key required. Live solar activity data for drag correction in Shield.")
    print("""
  WHAT IS THIS FOR?
  Solar activity heats the upper atmosphere, causing it to expand.
  This increases drag on LEO satellites — their actual orbit decays faster
  than the TLE's BSTAR term predicts. Shield uses NOAA data to:
    1. Correct the drag coefficient for current solar conditions
    2. Flag conjunctions computed during high-Kp periods as lower confidence

  THREE FEEDS (all free JSON endpoints, no auth):
    Kp index      →  geomagnetic storm level right now
    F10.7 flux    →  solar activity index used in atmospheric density models
    Solar wind    →  upstream conditions arriving from DSCOVR at L1
""")

    kp   = parse_kp(kp_raw)
    f107 = f107_raw[-1]
    wind = parse_wind(wind_raw)

    subheader("SCHEMA — Kp Index  (noaa-planetary-k-index-forecast.json)")
    schema_table([
        ("time_tag", "datetime", "timestamp",        "When this Kp reading was taken."),
        ("kp",       "float",    "drag correction",  "0–9 scale. >5 = geomagnetic storm. Flag TLE-based conjunctions as low-confidence."),
        ("quality",  "str",      "data quality",     "observed / estimated / predicted. Use observed for corrections, predicted for scheduling."),
    ])
    subheader("LIVE VALUES")
    for k, v in kp.items():
        live_value(k, v)

    print()
    subheader("SCHEMA — F10.7 Solar Flux  (observed-solar-cycle-indices.json)")
    schema_table([
        ("time-tag",       "str",   "timestamp",        "Month of observation (monthly averages)."),
        ("f10.7",          "float", "drag model input", "Solar flux units. Baseline ~70, solar max >200. Input to NRLMSISE-00 density model."),
        ("smoothed_f10.7", "float", "trend",            "81-day average. Use for long-term drag trend in pattern-of-life modeling."),
        ("ssn",            "float", "solar activity",   "Sunspot number. 0 = solar minimum, 200+ = solar maximum. Correlated with F10.7."),
    ])
    subheader("LIVE VALUES")
    for k, v in f107.items():
        live_value(k, v)

    print()
    subheader("SCHEMA — Solar Wind Plasma  (solar-wind/plasma-7-day.json)")
    schema_table([
        ("time_tag",    "datetime", "timestamp",    "UTC timestamp of this solar wind reading."),
        ("density",     "float",    "early warning", "Protons/cm³. High density → elevated Kp incoming in hours."),
        ("speed",       "float",    "early warning", "km/s. Fast stream >600 km/s from coronal hole → Kp storm in 1–3 days."),
        ("temperature", "float",    "wind type",     "Kelvin. Used to classify wind type (slow/fast stream vs CME)."),
    ])
    subheader("LIVE VALUES")
    for k, v in wind.items():
        live_value(k, v)
    print()

    return kp, f107, wind


# ══════════════════════════════════════════════════════════════════════
# SAVE EXAMPLE JSON
# ══════════════════════════════════════════════════════════════════════

def save_example_json(tle, hist_data, cdm_data, discos_obj, discos_raw, kp, f107, wind):
    """
    Saves one representative record from every source into example_data.json.
    This is the single file your pipeline teammate needs to understand every
    field name, type, and value they will see in production.
    """

    # For historical TLEs, pick 3 samples spread across the date range
    hist_samples = []
    if hist_data:
        step = max(1, len(hist_data) // 3)
        hist_samples = hist_data[::step][:3]

    payload = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "target_object": "ISS (International Space Station)",
            "norad_id": ISS_NORAD_ID,
            "cospar_id": ISS_COSPAR_ID,
            "description": (
                "One live record from each Drift Zero data source. "
                "Field names, types, and values are exactly what the pipeline will receive. "
                "See test_apis.py schema tables for per-field documentation."
            )
        },

        "source_1_spacetrack_live_tle": {
            "_doc": "Latest TLE for the target satellite. Refresh every 4–8 hours. JOIN KEY: NORAD_CAT_ID",
            "_endpoint": f"https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{ISS_NORAD_ID}/format/json/limit/1",
            "record": tle
        },

        "source_2_spacetrack_cdm": {
            "_doc": "Conjunction Data Messages where the target is SAT_1. JOIN KEYS: SAT_1_ID, SAT_2_ID → NORAD_CAT_ID",
            "_endpoint": f"https://www.space-track.org/basicspacedata/query/class/cdm_public/SAT_1_ID/{ISS_NORAD_ID}/TCA/>now/format/json/orderby/TCA asc/limit/3",
            "records": cdm_data if cdm_data else [],
            "_note": "Empty list means no active conjunctions right now — this is normal. In production poll frequently and store all events."
        },

        "source_3_spacetrack_historical_tle": {
            "_doc": "Historical TLE time-series — same schema as source_1. Used by Rogue for pattern-of-life baseline.",
            "_endpoint": f"https://www.space-track.org/basicspacedata/query/class/gp_history/NORAD_CAT_ID/{ISS_NORAD_ID}/EPOCH/YYYY-MM-DD--YYYY-MM-DD/orderby/EPOCH asc/format/json",
            "total_records_last_30_days": len(hist_data) if hist_data else 0,
            "sample_records": hist_samples,
            "_pipeline_note": "Store full 180-day history per satellite. Detect maneuvers by computing |delta(MEAN_MOTION)| between consecutive rows."
        },

        "source_4_esa_discos": {
            "_doc": "Physical catalog. JOIN KEY: satno → NORAD_CAT_ID. Provides mass for fuel equation, xSectAvg for collision probability.",
            "_endpoint": f"https://discosweb.esoc.esa.int/api/objects?filter=eq(cosparId,'{ISS_COSPAR_ID}')",
            "_auth": "Authorization: Bearer <token>  +  DiscosWeb-Api-Version: 2",
            "attributes": discos_obj if discos_obj else {},
            "full_raw_response": discos_raw if discos_raw else {}
        },

        "source_5_noaa_swpc": {
            "_doc": "Solar weather for atmospheric drag correction. No auth required.",

            "kp_index": {
                "_doc": "Current geomagnetic activity. >5 = flag TLE conjunctions as low-confidence.",
                "_endpoint": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
                "parsed": kp,
                "raw_sample": kp_raw_global[0:3] if kp_raw_global else []
            },

            "f107_solar_flux": {
                "_doc": "Monthly solar flux. Input to atmospheric density model (NRLMSISE-00).",
                "_endpoint": "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",
                "latest_record": f107
            },

            "solar_wind": {
                "_doc": "Real-time solar wind from DSCOVR satellite at L1. Elevated speed = Kp storm coming in 1–3 days.",
                "_endpoint": "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json",
                "latest_record": wind,
                "raw_sample": wind_raw_global[-3:] if wind_raw_global else []
            }
        }
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"  Saved → {OUTPUT_FILE}")
    print(f"  Size  → {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

# Globals to pass raw NOAA data into save_example_json
kp_raw_global   = []
wind_raw_global = []

if __name__ == "__main__":
    print("\n" + "━" * W)
    print("  DRIFT ZERO — API Data Source Explorer")
    print(f"  Target: ISS  │  NORAD {ISS_NORAD_ID}  │  COSPAR {ISS_COSPAR_ID}")
    print(f"  Output: {OUTPUT_FILE.name}")
    print("━" * W)

    # ── Space-Track (sources 1, 2, 3) ──────────────────────────────────
    session = requests.Session()
    print("\n  Authenticating with Space-Track...")
    auth = session.post(
        "https://www.space-track.org/ajaxauth/login",
        data={"identity": SPACETRACK_EMAIL, "password": SPACETRACK_PASSWORD}
    )
    if auth.status_code != 200 or "Failed" in auth.text:
        print(f"  !! Auth failed: {auth.status_code} — {auth.text[:100]}")
        tle = {}; hist_data = []; cdm_data = []
    else:
        print("  Auth OK\n")
        tle       = fetch_spacetrack_live_tle(session)
        hist_data = fetch_spacetrack_historical_tle(session)
        cdm_data  = fetch_spacetrack_cdm(session)

    print_source_1(tle)
    print_source_3(hist_data)
    print_source_2(cdm_data)

    # ── ESA DISCOS (source 4) ───────────────────────────────────────────
    discos_obj, discos_raw = fetch_esa_discos()
    print_source_4(discos_obj)

    # ── NOAA SWPC (source 5) ────────────────────────────────────────────
    kp_raw, f107_raw, wind_raw = fetch_noaa()
    kp_raw_global   = kp_raw
    wind_raw_global = wind_raw
    kp, f107, wind  = print_source_5(kp_raw, f107_raw, wind_raw)

    # ── Save everything ─────────────────────────────────────────────────
    print("\n" + "━" * W)
    print("  SAVING example_data.json")
    print("━" * W)
    save_example_json(tle, hist_data, cdm_data, discos_obj, discos_raw, kp, f107, wind)

    print("\n" + "━" * W)
    print("  DONE")
    print("  → example_data.json  contains one live record from every source")
    print("  → test_apis.py schema tables document every field in the pipeline")
    print("━" * W + "\n")
