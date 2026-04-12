# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**Drift Zero** is a space domain intelligence platform built for SCI Hackathon 2026 (SpaceTech + DefenseTech tracks, Problem 16 BOXMICA). It has two modes:
- **Shield** — real-time collision avoidance: conjunction detection, collision probability, maneuver cost analysis, fleet cascade impact
- **Rogue** — adversarial satellite classification: pattern-of-life modeling, anomaly detection, intent classification

Two layers:
- **`frontend/`** — React + Vite dashboard with CesiumJS 3D globe

frontend/
  src/
    main.jsx       ← entry point — GlobeView OUTSIDE StrictMode
    components/
      GlobeView.jsx        ← Kushagra — DO NOT MODIFY
      SatelliteModal.jsx   ← Kushagra — DO NOT MODIFY
      dashboard/           ← Madhu
    data/
      mockData.js

- **`backend/`** — Python orbital mechanics pipeline, Databricks integration, FastAPI, Claude API alerts

---

## Frontend Commands

All commands run from `frontend/`:

```bash
npm install       # install dependencies
npm run dev       # start dev server (localhost:5173)
npm run build     # production build
npm run lint      # run ESLint
```

## Frontend Architecture

**Stack:** React 19, Vite 8, Tailwind CSS v4, Cesium/Resium, Axios

**Dashboard components** (`frontend/src/components/dashboard/`):
- `StatsBar` — fleet KPIs
- `AlertQueue` — conjunction events ranked by risk score
- `NaturalLanguageAlert` — Claude API plain-English summaries (executive vs operator audience)
- `ManeuverPanel` — three maneuver options with deltaV, fuel cost, USD cost, lifespan impact
- `CascadeAnalysis` — downstream conjunction risks from a chosen maneuver

**Mock data:** `frontend/src/data/mockData.js` — realistic CDM-style records, maneuver options, cascade risks, operator profiles. Backend will replace this.

**Risk thresholds** (NASA CARA):
- Green: < 1:10,000
- Yellow: < 1:1,000
- Red: ≥ 1:1,000
- Industry maneuver threshold: 1:10,000

---

## Backend Architecture

**Stack:** Python, `sgp4`, `numpy`, `scipy`, `requests`, `fastapi`, `databricks-sdk`, `anthropic`, `python-dotenv`

**Data source:** Space-Track.org — auth confirmed working. Credentials in `.env` (never commit).

**Module build order:**

### `backend/shield/propagate.py`
Turns Space-Track GP records into position/velocity vectors.
- Input: dict with `TLE_LINE1`, `TLE_LINE2`, `OBJECT_NAME`, `NORAD_CAT_ID`, `EPOCH`
- Builds `Satrec` via `sgp4.api.Satrec.twoline2rv`
- Two functions: `propagate_at(sat, datetime)` → single point; `propagate_window(sat, t_start, hours, step_s)` → list of (datetime, r, v)
- Returns numpy arrays in TEME frame (km, km/s)
- SGP4 error code != 0 → skip silently
- Verification: ISS propagates to ~420km altitude

### `backend/shield/screen.py`
Filters ~1000-2000 objects down to candidate conjunction pairs cheaply.
- Input: list of parsed GP records
- Filter by altitude band overlap (~50km tolerance) and inclination similarity
- Output: list of (obj_a, obj_b) pairs worth running TCA on
- Verification: output is a few hundred pairs, not 0 or millions

### `backend/shield/tca.py`
Finds Time of Closest Approach and miss distance for a pair.
- Coarse scan: propagate both satellites at 60s steps over 24 hours, compute distance at each step
- Fine search: bisection refinement around the coarse minimum
- Output: `tca_utc`, `miss_distance_km`, `relative_velocity_km_s`
- Verification: miss distances are physically plausible (not negative, not >50,000 km)

### `backend/shield/probability.py`
Computes collision probability using Chan/Alfano 2D projection method.
- Input: miss distance, relative velocity, position uncertainty (hardcoded defaults: ~100m radial, ~500m along-track)
- Output: `collision_probability` (float 0–1)
- Verification: Pc for 10km miss ≈ negligible; Pc for 0.1km miss ≈ non-trivial

### `backend/shield/main.py`
Orchestrates the full pipeline.
- Fetches TLEs from Space-Track (active satellites + debris)
- Runs screen → tca → probability pipeline
- Computes `risk_score` (0–100 composite of Pc, miss distance, object type, relative velocity)
- Computes `do_nothing_confidence` (float passed in from operator behavior data)
- Writes output to Databricks Delta table
- Exposes `GET /conjunctions?min_risk=50&limit=20` via FastAPI

---

## Output JSON Schema (per conjunction event)

```json
{
  "event_id": "uuid",
  "timestamp_utc": "ISO8601",
  "primary": { "norad_id": int, "name": str, "tle_epoch": "ISO8601" },
  "secondary": { "norad_id": int, "name": str, "tle_epoch": "ISO8601" },
  "tca_utc": "ISO8601",
  "miss_distance_km": float,
  "relative_velocity_km_s": float,
  "collision_probability": float,
  "risk_score": float,
  "do_nothing_confidence": float,
  "data_source": "spacetrack",
  "data_age_minutes": float
}
```

---

## Environment Variables (`.env` — never commit)

```
SPACETRACK_EMAIL=...
SPACETRACK_PASSWORD=...
ANTHROPIC_API_KEY=...
DATABRICKS_HOST=...
DATABRICKS_TOKEN=...
```

---

## Key Design Patterns

- NORAD CAT ID is the primary key across all space data
- All conjunction IDs follow `CDM-YYYY-MMDD-NNN` format
- `naturalLanguageAlerts` have `audienceLevel`: `"executive"` or `"operator"`
- TEME frame used throughout backend — frontend handles coordinate conversion for globe rendering
- Data age is tagged on every TLE record and surfaced in the UI
- Solar weather (NOAA SWPC) is used to flag low-confidence conjunctions during high-Kp periods
- - GlobeView.jsx must stay outside React StrictMode — double mount crashes Cesium
- All dashboard panels use position: absolute overlays on top of the globe
- Pure inline styles in dashboard components, no Tailwind
- npm run dev must be run from frontend/, not repo root




## Team
- Abhay: backend/shield — conjunction detection pipeline
- Taher/Nikhil: Databricks pipeline, TLE ingestion, ML
- Madhu: dashboard UI components
- Kushagra: GlobeView, globe rendering
- Esha: Rogue, Anomaly detection