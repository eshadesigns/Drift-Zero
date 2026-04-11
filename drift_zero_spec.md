# DRIFT ZERO
**Space Domain Intelligence Platform**
Product Specification Document
Version 1.0 | April 2026 | SCI Hackathon 2026
Hackers Track | SpaceTech + DefenseTech | Problem 16 (BOXMICA)

Drift Zero is a unified space domain intelligence platform addressing two critical blind spots in orbital operations: debris threatening operator assets, and adversarial satellites threatening everyone's assets. Both problems share the same underlying data layer, but have never been addressed together in a single system.

---

## 1. Executive Summary

Drift Zero operates in two modes. **Shield** handles real-time collision avoidance with cost-optimized maneuver recommendations, operator behavior profiling, fuel estimation, and fleet cascade analysis. **Rogue** classifies satellite behavioral patterns to detect anomalies and adversarial intent. A Databricks Delta Lake pipeline and a CesiumJS globe tie both modes together into one operator interface.

The platform directly addresses Problem 16 from the BOXMICA Intelligence as a Service challenge set, while simultaneously competing in the SpaceTech and DefenseTech tracks.

---

## 2. Problem Statement

| Blind Spot | Current State | Consequence |
|---|---|---|
| Debris & Conjunctions | Fragmented feeds, manual analysis, no cost context | Unnecessary maneuvers shorten satellite lifespan |
| Adversarial Satellites | No automated behavioral classification exists | Proximity events and hostile maneuvers go undetected |
| Fleet Impact | Maneuver decisions made in isolation | Avoiding one threat creates new risks across the constellation |

---

## 3. Platform Architecture

Three layers: a data foundation ingesting live orbital data into Databricks Delta Lake, an intelligence layer running conjunction detection and behavioral classification, and an interface layer rendering everything on a real-time globe with Claude-powered natural language alerts.

| Layer | Components | Technology |
|---|---|---|
| Data Foundation | TLE ingestion, CDM feeds, debris catalog, solar weather | Databricks Delta Lake, Space-Track, NASA CDM, ESA DISCOS, NOAA |
| Intelligence | Conjunction detection, pattern-of-life modeling, anomaly classification, operator profiling, fuel estimation, fleet cascade | Python, scikit-learn, orbital mechanics (sgp4) |
| Interface | 3D globe, alert queue, maneuver comparison, natural language summaries | CesiumJS, React, Claude API |

---

## 4. Shield Mode — Collision Avoidance

Shield addresses the defensive problem: protecting operator assets from debris and conjunction events. It provides real-time threat detection, cost-aware maneuver recommendations, and fleet-wide impact analysis.

### 4.1 Conjunction Detection & Collision Probability

- Continuously computes collision probability using live TLE data and SGP4 propagation
- "Do Nothing" confidence score: probability the threat resolves without operator action
- Alert prioritization ranked by composite risk score across all active conjunctions
- Solar weather integration via NOAA SWPC for atmospheric drag correction

### 4.2 Operator Behavior Profiling

- Historical maneuver response rate per operator derived from TLE time-series, stored in Databricks
- When a conjunction is flagged, surfaces context — e.g. "Starlink maneuvers in 87% of similar scenarios"
- Reduces unnecessary maneuvers by factoring in whether the threatening satellite is likely to move

### 4.3 Fuel & Delta-V Estimation

- Calculates delta-v cost of proposed maneuver from orbital mechanics
- Converts delta-v to estimated fuel mass using the Tsiolkovsky rocket equation with known satellite parameters
- Outputs estimated fuel consumed (kg), approximate operational lifespan reduction, and dollar cost estimate
- Multiple maneuver options ranked by composite score: risk reduction, fuel cost, and operational downtime

### 4.4 Fleet Cascade Analysis

- Before recommending any maneuver, runs conjunction checks on the proposed trajectory against all constellation members
- Flags satellites whose collision risk increases post-maneuver
- Visualized on globe: proposed maneuver path highlighted, cascade risks shown separately
- Implemented as a second pass of the conjunction engine on the delta trajectory — reuses existing logic

---

## 5. Rogue Mode — Adversarial Intelligence

Rogue addresses the offensive intelligence problem: identifying satellites behaving abnormally or with potential hostile intent. Directly maps to Problem 16 (Space Object Behavior).

### 5.1 Pattern-of-Life Modeling

- Builds baseline behavioral model per satellite from historical TLE time-series
- Tracks orbital regime, maneuver frequency, typical drift rate, and station-keeping patterns
- Deviations from established baseline trigger anomaly scoring

### 5.2 Anomaly Detection

- Detects unexpected maneuvers, sudden orbital changes, and proximity events
- Flags uncharacteristic rendezvous behavior: sustained close approach to another satellite
- Identifies potential unreported fragmentation events from debris signature changes
- Anomaly severity scored on three levels: routine, suspicious, adversarial

### 5.3 Intent Classification

- Classifies satellite behavior: routine station-keeping, evasive, inspection, shadowing, or aggressive proximity
- Threat scoring combines maneuver pattern, proximity history, and orbital context
- Natural language threat summary generated via Claude API for every flagged event

> **Example alert:** "Satellite COSMOS-2576 performed an unscheduled 47 m/s maneuver at 03:14 UTC, reducing separation from GPS Block IIF-3 from 847 km to 23 km over 6 hours. Pattern deviates from 180-day baseline. Classification: HIGH SUSPICION — PROXIMITY INSPECTION."

---

## 6. Data Sources

| Source | Data Type | Access | Used By |
|---|---|---|---|
| Space-Track.org | TLE orbital element sets | Free public API | Shield + Rogue |
| NASA CDM Feeds | Conjunction Data Messages | Public feed | Shield |
| ESA DISCOS | Debris & spacecraft catalog | Public API | Shield + Rogue |
| NOAA SWPC | Solar weather / atmospheric drag | Public feed | Shield |
| Historical TLE archive | Pattern-of-life baselines | Space-Track historical | Rogue |

---

## 7. Team & Role Assignments

| Role | Owner | Deliverable |
|---|---|---|
| Data Pipeline | TBD | TLE ingestion, Databricks Delta Lake, historical operator data |
| Shield Intelligence | TBD | Conjunction detection, collision probability, fleet cascade |
| Rogue Intelligence | TBD | Pattern-of-life modeling, anomaly detection, intent classification |
| Estimation Layer | TBD | Operator behavior profiling, fuel and delta-v estimation |
| Frontend | TBD | CesiumJS globe, unified dashboard, alert queue, maneuver comparison UI |
| Alerts & Pitch | TBD | Claude API natural language alerts, POV madlib, demo narrative |

### Build Priority Order

| Priority | Milestone | Blocks |
|---|---|---|
| Hour 0–4 | TLE data flowing into Databricks; API contracts and schemas defined | Everything |
| Hour 4–10 | Conjunction detection working end to end | Shield, Fleet Cascade |
| Hour 4–10 | Globe rendering live satellite positions | Full demo |
| Hour 10–18 | Pattern-of-life baseline and anomaly detection | Rogue mode |
| Hour 18–24 | Operator behavior profiling and fuel estimation | Shield depth |
| Hour 24–36 | Fleet cascade and intent classification | Full platform |
| Hour 36–48 | Claude API alerts, demo polish, pitch prep | Presentation |

---

## 8. Demo Success Criteria

| Criterion | Target |
|---|---|
| Live TLE data on globe | Real satellites rendering in real time at demo |
| Conjunction alert | At least one real or simulated conjunction flagged with probability score |
| Rogue classification | At least one satellite classified with behavioral reasoning and confidence score |
| Natural language alert | Plain English summary generated for a threat event via Claude API |
| Fleet cascade | Proposed maneuver shows downstream constellation impact on globe |
| Fuel estimate | Delta-v cost shown for at least one maneuver option |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| TLE data latency | Stale orbits reduce prediction accuracy | Multi-source fusion; flag data age in UI |
| Integration bottleneck | Six parallel workstreams break at merge | Define API contracts and data schemas by Hour 4 |
| Overscoped build | Partial demo looks incomplete | Core demo is globe + conjunction + anomaly; all else layers on top |
| CesiumJS complexity | 3D globe takes too long to build | Fall back to 2D map if needed; data quality over visuals |
| Fuel estimation accuracy | Numbers imprecise without proprietary telemetry | Frame explicitly as estimates; judges will not penalize approximations |

---

*Drift Zero | SCI Hackathon 2026 | SpaceTech · DefenseTech | Hackers Track | Problem 16 (BOXMICA)*