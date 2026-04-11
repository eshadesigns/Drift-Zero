# Drift Zero — Project Guide

**Contributors:** eshadesigns

---

## Project Overview

Drift Zero is a space domain awareness platform with two modes:

- **Shield** — real-time collision avoidance, maneuver recommendations, fuel estimation, fleet cascade analysis
- **Rogue** — satellite behavioral pattern classification, anomaly detection, adversarial intent scoring

Frontend uses CesiumJS. Backend pipeline targets Databricks Delta Lake (deferred for now — local JSON used instead).

---

## Repo Structure

```
backend/
  rogue/
    anomaly_detector.py   # AnomalyDetector — z-score + IsolationForest + proximity scoring
    feature_engineering.py # extract_delta_features() — computes orbital deltas between TLE pairs
    pol_model.py           # SatelliteBaseline — EWMA pattern-of-life model per satellite
pipeline/
  __init__.py
  tle_ingest.py            # Space-Track auth, 180-day TLE history fetch, skyfield parsing, JSON cache
frontend/                  # React + CesiumJS globe
run_rogue.py               # End-to-end Rogue pipeline runner (CLI)
test_apis.py               # Live API explorer for all 5 data sources
example_data.json          # One live record per data source (ISS, NORAD 25544)
requirements.txt
.env.example
```

---

## Rogue Intelligence (sections 5.1 + 5.2)

### 5.1 Pattern-of-Life Modeling (`backend/rogue/pol_model.py`)

`SatelliteBaseline` — EWMA dataclass per satellite. Tracks mean and variance of orbital delta features. `update(features)` feeds new observations in; `zscore(feature, value)` returns how anomalous a new value is relative to the baseline.

- `ALPHA = 0.05` — EWMA decay rate (class variable, not a dataclass field)
- Non-numeric fields (e.g. `epoch` datetime) are skipped in `update()`

### 5.2 Anomaly Detection (`backend/rogue/anomaly_detector.py`)

`AnomalyDetector` — three-layer scoring:
1. **Z-score** — per-feature deviation from EWMA baseline
2. **IsolationForest** — unsupervised outlier score across all features
3. **Proximity flag** — CDM miss distance < 50 km

Composite score → severity: `ROUTINE` (<0.3) / `SUSPICIOUS` (0.3–0.65) / `ADVERSARIAL` (>0.65)

`FEATURE_KEYS` (used by all three layers):
```python
['delta_mean_motion', 'delta_eccentricity', 'delta_inclination',
 'delta_bstar', 'delta_v_proxy', 'time_gap_hours', 'solar_f107', 'kp_index']
```

### Feature Engineering (`backend/rogue/feature_engineering.py`)

`extract_delta_features(tle_prev, tle_curr, solar_f107, kp)` — computes deltas between consecutive TLE records. Input TLE dicts must have these keys (lowercase, float, epoch as datetime):

```
epoch, mean_motion, eccentricity, inclination, raan, bstar
```

Delta-v proxy formula: `dv ≈ |delta_mm / mm| * v_orb * 1000` (m/s)

---

## TLE Ingestion (`pipeline/tle_ingest.py`)

- Auth: `POST https://www.space-track.org/ajaxauth/login` (cookie-based)
- Endpoint: `gp_history` class, date range `YYYY-MM-DD--YYYY-MM-DD`
- Parsing: skyfield `EarthSatellite` → `sat.model` (sgp4 Satrec) for canonical epoch + orbital elements
- `no_kozai` (rad/min) → rev/day: `no_kozai * 1440 / (2 * pi)`
- Cache: saved to `data/tle_history_<ids>.json`, loaded automatically on re-runs
- CDMs: `MISS_DISTANCE` comes in metres from Space-Track, converted to km

---

## Running the Rogue Pipeline

```bash
# Setup
cp .env.example .env
# Fill in SPACETRACK_USERNAME and SPACETRACK_PASSWORD in .env
pip install -r requirements.txt

# Run (uses local cache if available)
python run_rogue.py

# Force re-fetch from Space-Track
python run_rogue.py --force-refresh

# Target specific satellites
python run_rogue.py --norad-ids 25544 48274
```

Default target satellites: ISS (25544), CSS/Tianhe (48274), Starlink-1 (44713), GPS IIR-20 (28190)

---

## Data Sources

| Source | Auth | Key fields |
|---|---|---|
| Space-Track `gp` / `gp_history` | Cookie (email + password) | `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `BSTAR`, `TLE_LINE1/2` |
| Space-Track `cdm_public` | Same session | `MISS_DISTANCE` (metres), `COLLISION_PROBABILITY`, `TCA` |
| NOAA SWPC | None | `f10.7` (solar flux), `kp` (geomagnetic index) |
| ESA DISCOS | Bearer token | `mass`, `xSectAvg`, `satno` → NORAD join key |

Join key across all sources: `NORAD_CAT_ID`

---

## Key Assumptions

- IsolationForest is trained per satellite (cluster_id = norad_id). Production would use k-means cluster IDs across the full catalogue.
- Solar F10.7 and Kp are the latest observed values, applied uniformly across the analysis window. Production would interpolate per-epoch.
- `WARMUP_OBS = 20` TLE pairs are used to build the EWMA baseline before scoring begins.
- No Databricks yet — all data stored in `data/` as local JSON.

---

## Branch Structure

- `main` — stable base
- `rogue` — Rogue Intelligence module (sections 5.1 + 5.2), owned by eshadesigns
- `frontend` — CesiumJS globe and dashboard
- `backend` — Shield mode pipeline
