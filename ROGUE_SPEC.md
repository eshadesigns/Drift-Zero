# Rogue Mode — Implementation Spec
**Drift Zero | SCI Hackathon 2026**

Rogue answers a fundamentally different question than Shield.

- **Shield asks:** "Will this debris hit my satellite, and should I burn fuel to dodge it?"
- **Rogue asks:** "Is that satellite behaving suspiciously, and does it have hostile intent?"

Same underlying TLE data, completely different analytical pipeline and output.

---

## How Rogue Differs from Shield

| | Shield | Rogue |
|---|---|---|
| Threat source | Passive debris / uncontrolled objects | Active, potentially adversarial satellites |
| Historical TLE used for... | Operator profiling — will *they* move? (aggregate per operator) | Pattern-of-life — is *this satellite* deviating from its own baseline? (per satellite, 180 days) |
| Core output | Collision probability + maneuver recommendation | Intent classification + behavioral anomaly score |
| Operator action | "Should I burn fuel to dodge this?" | "Should I alert someone about this satellite?" |

---

## Three-Layer Architecture

### Layer 1 — Data Collection

**Status: Mostly done.**

| Component | What it does | Status |
|---|---|---|
| TLE parser | Normalizes Space-Track JSON to lowercase feature keys | Done — `rogue/feature_engineering.py` |
| Orbit propagator | SGP4 position/velocity from TLE | Done — `backend/shield/propagate.py` (shared) |
| Historical delta calculator | Computes epoch-to-epoch deltas: delta_mean_motion, delta_eccentricity, delta_inclination, delta_bstar, delta_v_proxy, time_gap_hours | Done — `rogue/feature_engineering.py` |
| Proximity filter | Spatial index to find satellites that came within 50km of the target | Not implemented — use simple distance check from CDM data for now |

**Skip the r-tree spatial index.** The CDM feed from Space-Track already surfaces proximity events. Use that.

---

### Layer 2 — Behavior Classifier

**Status: Partially done. Two components need to be built.**

#### 2a. Feature Engineering
**Done.** `rogue/feature_engineering.py` extracts:
- `delta_mean_motion` — altitude/energy change
- `delta_eccentricity` — orbit shape change
- `delta_inclination` — plane change (expensive maneuver, deliberate)
- `delta_bstar` — drag coefficient change
- `delta_v_proxy` — estimated delta-v in m/s
- `delta_raan` — right ascension drift
- `time_gap_hours` — time between TLE epochs
- `solar_f107`, `kp_index` — space weather context

---

#### 2b. Physics Rules Engine
**NOT implemented. Build this first.**

Hard-coded orbital mechanics gates that run **before** any ML. Fast, interpretable, no training data needed. Catches obvious cases.

Rules to implement in `rogue/rules_engine.py`:

```
STATION_KEEPING:
  - delta_v_proxy < 2.0 m/s
  - |delta_inclination| < 0.01 deg
  - |delta_eccentricity| < 0.0002
  → Label: STATION_KEEPING, confidence: HIGH

DEBRIS_ANOMALY (physically impossible maneuver):
  - object_type == DEBRIS
  - delta_v_proxy > 1.0 m/s
  → Label: ANOMALY (fragmentation or misidentified object), confidence: HIGH

EVASIVE:
  - delta_v_proxy > 5.0 m/s
  - |delta_inclination| > 0.05 deg OR |delta_mean_motion| > 0.005 rev/day
  - No conjunction event in CDM feed (i.e. not a collision avoidance burn)
  → Label: EVASIVE, confidence: MEDIUM

INSPECTION:
  - delta_v_proxy > 2.0 m/s
  - proximity_flag == True (CDM miss distance < 50 km)
  - maneuver reduces separation (closing, not opening)
  → Label: INSPECTION, confidence: HIGH

SHADOWING:
  - Multiple consecutive epochs with small correlated DV
  - proximity_flag == True sustained over > 3 epochs
  - delta_inclination correlated with another satellite's inclination change
  → Label: SHADOWING, confidence: MEDIUM

Default (no rule fires):
  → Label: UNKNOWN, pass to ML classifier
```

Output per observation: `{ "label": str, "confidence": str, "rule_fired": str | None }`

If a rule fires, **skip the ML classifier** for that observation. Rules take priority.

---

#### 2c. ML Threat Classifier
**Partially done — currently IsolationForest (unsupervised). Needs upgrade.**

Current state: `rogue/anomaly_detector.py` uses IsolationForest + Z-score to produce a composite score. Outputs ROUTINE / SUSPICIOUS / ADVERSARIAL but cannot name the *type* of behavior.

Target state: Add a supervised Random Forest classifier that outputs an intent label.

**File to build: `rogue/intent_classifier.py`**

```python
# Labels (classes):
LABELS = ["STATION_KEEPING", "EVASIVE", "INSPECTION", "SHADOWING", "ROUTINE"]

# Input features (same as FEATURE_KEYS in anomaly_detector.py):
# delta_mean_motion, delta_eccentricity, delta_inclination,
# delta_bstar, delta_v_proxy, time_gap_hours, solar_f107, kp_index

# Model: RandomForestClassifier (scikit-learn)
# Output: label + confidence score (0-1)
```

**Only called when the physics rules engine returns UNKNOWN.**

---

#### 2d. Synthetic Training Data
**NOT implemented. Needed for the supervised classifier.**

Since no real labeled adversarial satellite dataset exists, generate synthetic observations.

**File to build: `rogue/synthetic_data.py`**

Generate feature vectors per class:

| Class | delta_v_proxy | delta_inclination | delta_eccentricity | proximity_flag |
|---|---|---|---|---|
| STATION_KEEPING | 0.1–1.5 m/s | < 0.01 deg | < 0.0001 | False |
| ROUTINE | 0–0.5 m/s | ~0 | ~0 | False |
| EVASIVE | 5–30 m/s | 0.05–0.5 deg | variable | False |
| INSPECTION | 2–15 m/s | small | small | True |
| SHADOWING | 1–5 m/s (repeated) | correlated | small | True (sustained) |

Add Gaussian noise to each feature to simulate TLE measurement uncertainty. Generate ~500 samples per class. Train the Random Forest on this. Save model to `rogue/models/intent_classifier.pkl`.

---

### Layer 3 — Visualization & Alerting

**Status: Nothing built yet. All four components needed.**

#### 3a. Threat Dashboard (Frontend)
**File to build: `frontend/src/components/rogue/RoguePanel.jsx`**

Table of flagged satellites from `GET /api/rogue/events`. Columns:
- Satellite name + NORAD ID
- Intent label badge (color-coded: ROUTINE gray, SUSPICIOUS yellow, ADVERSARIAL red)
- Composite score (0–1)
- delta_v_proxy (m/s)
- Anomalous features list
- Timestamp

Filterable by severity. Sortable by composite score.

---

#### 3b. Alert System (Claude API)
**NOT implemented. Critical for demo.**

When an event is SUSPICIOUS or ADVERSARIAL, call Claude to generate a plain-English threat summary.

**Backend:** Add `GET /api/rogue/alert/{norad_id}/{epoch}` endpoint in `backend/api.py`.

Prompt structure to send to Claude:
```
Satellite: {name} (NORAD {norad_id})
Classification: {severity} — {intent_label}
Delta-V: {delta_v_proxy} m/s at {epoch}
Anomalous features: {anomalous_features}
Proximity event: {proximity_flag} (miss distance: {miss_distance_km} km)
Baseline deviation: Z-score max = {z_score_max}

Generate a concise threat summary for a space domain awareness operator.
Include: what happened, why it's suspicious, and recommended action.
```

Output stored on `AnomalyEvent.description`. Surfaced in the dashboard.

---

#### 3c. Globe Color-Coding (Rogue Mode)
**Needs coordination with Kushagra (GlobeView.jsx — DO NOT MODIFY directly).**

When the UI is in Rogue mode, satellites should be color-coded by threat level:
- Gray — ROUTINE
- Yellow — SUSPICIOUS  
- Red — ADVERSARIAL

The globe already renders satellites. The Rogue panel needs to push threat labels into whatever state mechanism GlobeView reads from (`satStore.js`).

---

#### 3d. Maneuver Replay
**Skip for now.** Labeled "demo-effective but less operationally useful" — not worth the build time at hackathon scope.

---

## Updated AnomalyEvent Schema

The current `AnomalyEvent` dataclass needs two new fields:

```python
@dataclass
class AnomalyEvent:
    norad_id: int
    epoch: datetime
    severity: str               # ROUTINE | SUSPICIOUS | ADVERSARIAL
    intent_label: str           # NEW: STATION_KEEPING | EVASIVE | INSPECTION | SHADOWING | ROUTINE | UNKNOWN
    rule_fired: str | None      # NEW: which physics rule triggered (None if ML classified)
    composite_score: float
    z_score_max: float
    iso_score: float
    proximity_flag: bool
    anomalous_features: list[str]
    description: str            # Claude API natural language summary
```

---

## API Endpoints (final Rogue surface)

| Method | Path | Description |
|---|---|---|
| GET | `/api/rogue/events` | All flagged events for default target satellites |
| GET | `/api/rogue/events?norad_ids=25544,48274` | Flagged events for specific satellites |
| GET | `/api/rogue/alert/{norad_id}/{epoch}` | Claude-generated natural language summary for one event |

---

## Build Order

| Step | Component | File | Time estimate |
|---|---|---|---|
| 1 | Physics rules engine | `rogue/rules_engine.py` | ~2 hrs |
| 2 | Synthetic training data generator | `rogue/synthetic_data.py` | ~2 hrs |
| 3 | Intent classifier (Random Forest) | `rogue/intent_classifier.py` | ~2 hrs |
| 4 | Update AnomalyEvent + wire rules + classifier into run_rogue.py | `rogue/anomaly_detector.py`, `run_rogue.py` | ~1 hr |
| 5 | Claude API alert endpoint | `backend/api.py` | ~1 hr |
| 6 | Rogue dashboard frontend | `frontend/src/components/rogue/RoguePanel.jsx` | ~3 hrs |
| 7 | Globe color-coding in Rogue mode | `frontend/src/satStore.js` + coordination with Kushagra | ~1 hr |

---

## What Already Exists (Do Not Rebuild)

- `rogue/feature_engineering.py` — delta feature extraction
- `rogue/pol_model.py` — Welford online EWMA baseline per satellite
- `rogue/anomaly_detector.py` — Z-score + IsolationForest composite scoring
- `run_rogue.py` — E2E pipeline runner (Space-Track ingestion, CDM fetch, baseline warmup, IsoForest training, scoring)
- `backend/api.py` — FastAPI app with `GET /api/rogue/events` already wired to `run_rogue.py`
- `pipeline/ingest_tle_history.py` — 180-day TLE history ingestion to Databricks

The physics rules engine and intent classifier slot **in between** the existing feature engineering and the existing anomaly scorer. They don't replace it — the IsolationForest composite score still runs. The rules engine and RF classifier add the **intent label** on top.
