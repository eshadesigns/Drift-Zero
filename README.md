# Drift Zero

Space domain intelligence platform for the SCI Hackathon 2026 (SpaceTech + DefenseTech tracks, Problem 16 BOXMICA).

Two operational modes:

- **Shield** — real-time collision avoidance: conjunction detection, collision probability, maneuver cost analysis, fleet cascade impact assessment
- **Rogue** — adversarial satellite classification: pattern-of-life modeling, anomaly detection, intent classification

---

## Architecture

```
frontend/          React 19 + Vite dashboard with CesiumJS 3D globe
backend/
  api.py           FastAPI REST gateway + Claude natural-language summaries
  shield/          Collision detection pipeline (SGP4, TCA, Pc, maneuver analysis)
  rogue/           Anomaly detection (IsolationForest, z-score, CDM proximity)
pipeline/          TLE ingestion, maneuver event detection, operator profiling (Databricks)
run_rogue.py       CLI entry point for the Rogue pipeline
```

Data source: **Space-Track.org** TLE catalog (active satellites + debris).  
Orbital frame: TEME throughout the backend. Frontend converts to geographic for globe rendering.  
Primary key across all data: **NORAD CAT ID**.

---

## Setup

### Environment variables

Copy `.env.example` to `.env` and fill in credentials:

```
SPACETRACK_USERNAME=       # Space-Track.org login (email)
SPACETRACK_PASSWORD=

ANTHROPIC_API_KEY=         # Claude API — natural-language alert summaries

DATABRICKS_HOST=           # Optional: Databricks workspace for pipeline ETL
DATABRICKS_TOKEN=
DATABRICKS_WAREHOUSE_ID=
DATABRICKS_CATALOG=drift_zero
DATABRICKS_SCHEMA=orbital

VITE_CESIUM_TOKEN=         # Cesium Ion token for globe imagery
```

### Backend

Python 3.11+ recommended.

```bash
pip install -r requirements.txt
```

Start the API server:

```bash
uvicorn backend.api:app --reload --port 8000
```

### Frontend

All commands from `frontend/`:

```bash
npm install
npm run dev      # localhost:5173
npm run build
npm run lint
```

The Vite config reads `.env` from the repo root, not `frontend/`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/satellite/{norad_id}` | TLE + orbital parameters. Returns 404 if not in Space-Track catalog. |
| `GET` | `/api/conjunctions/{norad_id}` | Shield pipeline results for a satellite. Params: `min_risk` (0–100), `limit` (default 20). |
| `GET` | `/api/maneuvers/{norad_id}/{event_id}` | Three maneuver options for a conjunction event (requires conjunctions cached first). |
| `GET` | `/api/cascade/{norad_id}/{event_id}/{maneuver_label}` | Downstream cascade risk from a chosen maneuver. |
| `GET` | `/api/rogue/events` | Rogue anomaly events. Optional: `?norad_ids=25544,59773` to filter by satellite. |

Responses cached for 30 minutes. Per-NORAD cache keys prevent stale data cross-contamination.

---

## Shield Pipeline

`backend/shield/` processes a target satellite through five stages:

1. **`propagate.py`** — Converts Space-Track GP records to position/velocity vectors via SGP4. Returns TEME-frame arrays (km, km/s).

2. **`screen.py`** — Filters the full catalog (~2000 objects) to candidate conjunction pairs. Criteria: altitude band overlap ±50 km, inclination similarity ≤10° (or both polar). No propagation — fast geometric filter.

3. **`tca.py`** — Time of Closest Approach. Coarse 60-second scan over 24 hours, then bisection refinement within ±120s of the minimum. Outputs `tca_utc`, `miss_distance_km`, `relative_velocity_km_s`.

4. **`probability.py`** — Collision probability via Chan/Alfano 2D projection. Defaults: 1 km radial uncertainty, 5 km cross-track, 10 m hard-body radius.

5. **`maneuver.py`** — Three maneuver options (Maximum Safety +50 km, Balanced +25 km, Fuel Efficient +10 km miss distance). Outputs delta-v, fuel cost (USD), lifespan impact. Uses Tsiolkovsky equation: Isp=220s, dry mass=260 kg.

**Risk score** (0–100):
- 50% Collision probability (log-scaled)
- 30% Miss distance (linear inverse, cap at 200 km)
- 20% Secondary object type (DEBRIS=20, ROCKET BODY=15, UNKNOWN=10, PAYLOAD=5)

**NASA CARA thresholds**: Green < 1:10,000 | Yellow < 1:1,000 | Red ≥ 1:1,000.

**`cascade.py`** — After a maneuver is selected, propagates the primary satellite to the burn epoch, applies delta-v along-track, converts the perturbed state back to orbital elements, and re-screens against the threat catalog to identify new or worsened conjunctions.

### Conjunction event schema

```json
{
  "event_id": "CDM-YYYY-MMDD-NNN",
  "timestamp_utc": "ISO8601",
  "primary": { "norad_id": 25544, "name": "ISS", "tle_epoch": "ISO8601" },
  "secondary": { "norad_id": 48274, "name": "COSMOS-2576", "tle_epoch": "ISO8601" },
  "tca_utc": "ISO8601",
  "miss_distance_km": 0.42,
  "relative_velocity_km_s": 7.8,
  "collision_probability": 1.4e-4,
  "risk_score": 73.2,
  "do_nothing_confidence": 0.18,
  "data_source": "spacetrack",
  "data_age_minutes": 12.0
}
```

---

## Rogue Pipeline

`run_rogue.py` + `backend/rogue/` classifies satellites as NOMINAL / SUSPICIOUS / ADVERSARIAL by detecting maneuver-like orbital changes in TLE history.

**Stages:**

1. Fetch current solar weather from NOAA SWPC (F10.7, Kp index).
2. Pull 180-day TLE history from Space-Track (or local JSON cache in `data/`).
3. Fetch upcoming CDMs from Space-Track for proximity scoring.
4. Per satellite: compute delta features for every consecutive TLE pair, warm up EWMA baseline on the first 20 pairs, train an IsolationForest, then score the remaining observations.
5. Flag SUSPICIOUS and ADVERSARIAL events; rank by composite score.

**Delta features per TLE pair:** time gap, delta mean motion, delta eccentricity, delta inclination, delta RAAN, delta Bstar, delta-v proxy, solar F10.7, Kp.

**Composite score:**
- 35% Z-score against per-satellite EWMA baseline
- 40% IsolationForest anomaly score
- 25% Proximity to known CDM events (< 50 km threshold)

**Severity thresholds:** ROUTINE < 0.5 | SUSPICIOUS 0.5–0.72 | ADVERSARIAL ≥ 0.72

Claude Haiku generates a one-sentence plain-English threat summary for each flagged event (top 10 by score).

**CLI:**

```bash
python run_rogue.py                          # defaults: ISS, CSS, Starlink-1, GPS IIR-20
python run_rogue.py --norad-ids 25544 59773  # specific satellites
python run_rogue.py --days 90                # shorter history window
python run_rogue.py --force-refresh          # bypass local cache
```

---

## Data Pipeline (Databricks)

`pipeline/` handles one-time and recurring ETL. Requires Databricks credentials in `.env`.

```bash
# One-time: bulk TLE history ingest (skips if table already has >1000 rows)
python pipeline/ingest_tle_history.py

# Detect maneuvers from TLE element deltas
python pipeline/compute_maneuver_events.py

# Aggregate per-operator behavioral profiles
python pipeline/compute_operator_profiles.py

# Full Rogue anomaly pipeline run
python pipeline/run_anomaly.py
```

Databricks tables:
- `drift_zero.orbital.tle_history` — 180-day TLE archive per satellite
- `drift_zero.orbital.maneuver_events` — detected maneuvers with delta-v estimates
- `drift_zero.orbital.operator_profiles` — maneuver rate, median delta-v, self-clear likelihood per operator

---

## Frontend

React 19 dashboard overlaid on a CesiumJS globe. All panels use position-absolute overlays with inline styles.

**Key components:**

| Component | Description |
|-----------|-------------|
| `GlobeView.jsx` | CesiumJS viewer with real-time SGP4 satellite propagation via postUpdate listener. Must live outside React StrictMode — double mount crashes Cesium. |
| `App.jsx` | DashboardOverlay: mode switching (Shield/Rogue), Shield pipeline orchestration, satStore sync. |
| `LandingOverlay.jsx` | Entry screen. Validates NORAD ID against `/api/satellite/{id}` before navigating. |
| `RoguePanel.jsx` | Anomaly events display, refetches per-satellite when NORAD ID changes. |
| `AlertQueue.jsx` | Conjunction events ranked by risk score. |
| `ManeuverPanel.jsx` | Three maneuver options with delta-v, fuel cost (USD), lifespan impact. |
| `CascadeAnalysis.jsx` | Downstream conjunction risks from a chosen maneuver. |
| `NaturalLanguageAlert.jsx` | Claude-generated summaries (executive and operator audience levels). |

**State management:** `satStore.js` — lightweight pub/sub that syncs satellite selection between GlobeView and DashboardOverlay, which live in separate React trees (GlobeView is outside StrictMode).

**Mock data:** `src/data/mockData.js` provides CDM-style fallback data for all UI components when the backend is unavailable.

---

## Testing

Validates all five external data sources against a live satellite (defaults to ISS, NORAD 25544) and writes example responses to `example_data.json`:

```bash
pip install -r test/requirements.txt
cp test/.env.example test/.env   # add Space-Track credentials
python test/test_apis.py
```

Data sources tested: Space-Track TLE, Space-Track CDM, Space-Track TLE history, ESA DISCOS, NOAA SWPC.

---

## Team

| Member | Area |
|--------|------|
| Abhay | Shield — conjunction detection pipeline |
| Taher / Nikhil | Databricks pipeline, TLE ingestion, ML |
| Madhu | Dashboard UI components |
| Kushagra | GlobeView, globe rendering |
| Esha | Rogue, anomaly detection |
