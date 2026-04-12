// src/data/mockData.js
// Based on real orbital mechanics and conjunction statistics
// Sources: NASA CARA, SpaceX regulatory filings, ESA Space Debris Office

// ─── FLEET STATS (top of StatsBar) ───────────────────────────────────────────
export const fleetStats = {
  activeSatellites: 6547,
  activeConjunctions: 7,
  criticalAlerts: 2,
  avgCollisionProb: 0.00031,   // realistic LEO average per NASA CARA data
  maneuversThisMonth: 23,
  fuelSpentUSD: 847000,
  totalTrackedObjects: 27543,
  unconfirmedDebris: 500000
}

// ─── SATELLITES ───────────────────────────────────────────────────────────────
export const satellites = [
  {
    id: "STARLINK-3120",
    name: "Starlink-3120",
    operator: "SpaceX",
    orbitAltitudeKm: 548,
    inclination: 53.0,
    vulnerabilityScore: 72,
    fuelRemainingKg: 18.4,
    operationalLifeRemainingMonths: 34,
    missionType: "communications",
    tle1: "1 48274U 21044AV  24101.50000000  .00002182  00000-0  16538-3 0  9993",
    tle2: "2 48274  53.0535 142.1234 0001480  89.9374  270.1733 15.06407014169839"
  },
  {
    id: "STARLINK-4891",
    name: "Starlink-4891",
    operator: "SpaceX",
    orbitAltitudeKm: 551,
    inclination: 53.2,
    vulnerabilityScore: 45,
    fuelRemainingKg: 22.1,
    operationalLifeRemainingMonths: 41,
    missionType: "communications",
    tle1: "1 52713U 22057B   24101.50000000  .00001847  00000-0  14022-3 0  9991",
    tle2: "2 52713  53.2182 198.4521 0001123  91.2341  268.8932 15.06398234156721"
  },
  {
    id: "ISS",
    name: "Intl Space Station",
    operator: "NASA/Roscosmos",
    orbitAltitudeKm: 421,
    inclination: 51.6,
    vulnerabilityScore: 88,
    fuelRemainingKg: 4200,
    operationalLifeRemainingMonths: 48,
    missionType: "crewed",
    tle1: "1 25544U 98067A   24101.50000000  .00020769  00000-0  36778-3 0  9993",
    tle2: "2 25544  51.6416 247.4627 0002781  40.4321 319.7032 15.50037028447473"
  },
  {
    id: "WORLDVIEW-3",
    name: "WorldView-3",
    operator: "Maxar Technologies",
    orbitAltitudeKm: 617,
    inclination: 97.9,
    vulnerabilityScore: 61,
    fuelRemainingKg: 312,
    operationalLifeRemainingMonths: 67,
    missionType: "imaging",
    tle1: "1 40115U 14048A   24101.50000000 -.00000115  00000-0  00000-0 0  9994",
    tle2: "2 40115  97.9204 154.3421 0001267  97.2341 262.9021 14.83221234198234"
  },
  {
    id: "COSMOS-1408-DEB-047",
    name: "COSMOS 1408 DEB",
    operator: "UNTRACKED",
    orbitAltitudeKm: 485,
    inclination: 82.9,
    vulnerabilityScore: 0,
    fuelRemainingKg: 0,
    operationalLifeRemainingMonths: 0,
    missionType: "debris",
    tle1: "1 52900U 82092BU  24101.50000000  .00021734  00000-0  22134-2 0  9998",
    tle2: "2 52900  82.9621 156.7234 0008234  47.1234 313.0412 15.72341234287234"
  },
  {
    id: "SENTINEL-6A",
    name: "Sentinel-6A",
    operator: "ESA/NASA/EUMETSAT",
    orbitAltitudeKm: 1336,
    inclination: 66.0,
    vulnerabilityScore: 38,
    fuelRemainingKg: 87,
    operationalLifeRemainingMonths: 52,
    missionType: "earth_observation",
    tle1: "1 46984U 20080A   24101.50000000 -.00000071  00000-0  00000-0 0  9991",
    tle2: "2 46984  66.0013 312.4521 0001234 121.3421 238.7834 12.80023412234123"
  }
]

// ─── CONJUNCTIONS ─────────────────────────────────────────────────────────────
// Realistic collision probabilities based on NASA CARA thresholds:
// Green  < 1:10,000  (0.0001)
// Yellow < 1:1,000   (0.001)
// Red    > 1:1,000   (0.001+)
// Industry standard maneuver threshold: 1:10,000

export const conjunctions = [
  {
    id: "CDM-2026-0411-001",
    primarySatId: "ISS",
    primarySatName: "Intl Space Station",
    secondarySatId: "COSMOS-1408-DEB-047",
    secondarySatName: "COSMOS 1408 DEB",
    probability: 0.00312,       // 1:320 — well above maneuver threshold
    tcaTime: "2026-04-12T03:47:22Z",
    timeToTCA: "4h 32m",
    missDistanceKm: 0.127,      // 127 meters — extremely close
    relativeVelocityKms: 14.8,
    riskScore: 97,
    severity: "CRITICAL",
    doNothingConfidence: 0.04,  // 4% chance it resolves itself
    operatorWillManeuver: false, // debris can't maneuver
    lastUpdated: "2026-04-11T22:15:00Z"
  },
  {
    id: "CDM-2026-0411-002",
    primarySatId: "STARLINK-3120",
    primarySatName: "Starlink-3120",
    secondarySatId: "COSMOS-1408-DEB-047",
    secondarySatName: "COSMOS 1408 DEB",
    probability: 0.00187,       // 1:535
    tcaTime: "2026-04-12T07:12:44Z",
    timeToTCA: "7h 57m",
    missDistanceKm: 0.203,
    relativeVelocityKms: 13.2,
    riskScore: 89,
    severity: "CRITICAL",
    doNothingConfidence: 0.08,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T22:15:00Z"
  },
  {
    id: "CDM-2026-0411-003",
    primarySatId: "WORLDVIEW-3",
    primarySatName: "WorldView-3",
    secondarySatId: "SL-8-RB-2341",
    secondarySatName: "SL-8 Rocket Body",
    probability: 0.00043,       // 1:2,325 — above threshold
    tcaTime: "2026-04-12T14:33:17Z",
    timeToTCA: "15h 18m",
    missDistanceKm: 0.891,
    relativeVelocityKms: 11.7,
    riskScore: 74,
    severity: "HIGH",
    doNothingConfidence: 0.21,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T21:44:00Z"
  },
  {
    id: "CDM-2026-0411-004",
    primarySatId: "STARLINK-4891",
    primarySatName: "Starlink-4891",
    secondarySatId: "STARLINK-3120",
    secondarySatName: "Starlink-3120",
    probability: 0.00021,
    tcaTime: "2026-04-12T19:08:55Z",
    timeToTCA: "20h 53m",
    missDistanceKm: 1.243,
    relativeVelocityKms: 0.31,  // low rel velocity — constellation crossing
    riskScore: 61,
    severity: "HIGH",
    doNothingConfidence: 0.67,  // SpaceX will likely maneuver Starlink-3120
    operatorWillManeuver: true,
    lastUpdated: "2026-04-11T20:32:00Z"
  },
  {
    id: "CDM-2026-0411-005",
    primarySatId: "SENTINEL-6A",
    primarySatName: "Sentinel-6A",
    secondarySatId: "FENGYUN-1C-DEB-1823",
    secondarySatName: "FY-1C Debris",
    probability: 0.000089,
    tcaTime: "2026-04-13T06:21:33Z",
    timeToTCA: "31h 6m",
    missDistanceKm: 2.847,
    relativeVelocityKms: 9.4,
    riskScore: 42,
    severity: "MEDIUM",
    doNothingConfidence: 0.44,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T19:17:00Z"
  },
  {
    id: "CDM-2026-0411-006",
    primarySatId: "STARLINK-3120",
    primarySatName: "Starlink-3120",
    secondarySatId: "IRIDIUM-33-DEB-0412",
    secondarySatName: "Iridium 33 Debris",
    probability: 0.000034,
    tcaTime: "2026-04-13T11:44:21Z",
    timeToTCA: "36h 29m",
    missDistanceKm: 4.112,
    relativeVelocityKms: 15.1,
    riskScore: 28,
    severity: "LOW",
    doNothingConfidence: 0.71,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T18:55:00Z"
  },
  {
    id: "CDM-2026-0411-007",
    primarySatId: "WORLDVIEW-3",
    primarySatName: "WorldView-3",
    secondarySatId: "COSMOS-2251-DEB-0891",
    secondarySatName: "COSMOS 2251 Debris",
    probability: 0.000012,
    tcaTime: "2026-04-13T22:17:44Z",
    timeToTCA: "47h 2m",
    missDistanceKm: 7.234,
    relativeVelocityKms: 12.3,
    riskScore: 14,
    severity: "LOW",
    doNothingConfidence: 0.89,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T17:23:00Z"
  }
]

// ─── MANEUVERS ────────────────────────────────────────────────────────────────
// deltaV in m/s — typical CAM is 0.1-2.0 m/s per ESA/NASA operational data
// fuelKg based on ISP of ~220s for hydrazine thrusters
// costUSD = fuel cost + operational overhead + lifespan reduction value

export const maneuvers = [
  {
    conjunctionId: "CDM-2026-0411-001",
    options: [
      {
        id: "A",
        label: "Maximum Safety",
        deltaVms: 1.82,
        fuelKg: 0.94,
        burnDurationSec: 47,
        riskReductionPct: 99.8,
        newProbability: 0.0000063,
        costUSD: 127400,
        lifespanImpactDays: 18,
        missionDowntimeHrs: 2.3,
        executionWindowMin: 94,
        cascadeRiskCreated: false
      },
      {
        id: "B",
        label: "Balanced",
        deltaVms: 0.94,
        fuelKg: 0.48,
        burnDurationSec: 24,
        riskReductionPct: 98.1,
        newProbability: 0.0000589,
        costUSD: 64800,
        lifespanImpactDays: 9,
        missionDowntimeHrs: 1.1,
        executionWindowMin: 187,
        cascadeRiskCreated: false
      },
      {
        id: "C",
        label: "Fuel Efficient",
        deltaVms: 0.41,
        fuelKg: 0.21,
        burnDurationSec: 11,
        riskReductionPct: 91.4,
        newProbability: 0.000268,
        costUSD: 28300,
        lifespanImpactDays: 4,
        missionDowntimeHrs: 0.4,
        executionWindowMin: 312,
        cascadeRiskCreated: true   // creates new low risk with ISS DEB-051
      }
    ]
  },
  {
    conjunctionId: "CDM-2026-0411-002",
    options: [
      {
        id: "A",
        label: "Maximum Safety",
        deltaVms: 0.94,
        fuelKg: 0.48,
        burnDurationSec: 24,
        riskReductionPct: 99.2,
        newProbability: 0.0000149,
        costUSD: 42100,
        lifespanImpactDays: 12,
        missionDowntimeHrs: 0.8,
        executionWindowMin: 142,
        cascadeRiskCreated: false
      },
      {
        id: "B",
        label: "Balanced",
        deltaVms: 0.47,
        fuelKg: 0.24,
        burnDurationSec: 12,
        riskReductionPct: 96.8,
        newProbability: 0.0000598,
        costUSD: 21200,
        lifespanImpactDays: 6,
        missionDowntimeHrs: 0.4,
        executionWindowMin: 284,
        cascadeRiskCreated: false
      },
      {
        id: "C",
        label: "Fuel Efficient",
        deltaVms: 0.18,
        fuelKg: 0.09,
        burnDurationSec: 5,
        riskReductionPct: 87.2,
        newProbability: 0.000238,
        costUSD: 8100,
        lifespanImpactDays: 2,
        missionDowntimeHrs: 0.1,
        executionWindowMin: 498,
        cascadeRiskCreated: false
      }
    ]
  },
  {
    conjunctionId: "CDM-2026-0411-003",
    options: [
      {
        id: "A",
        label: "Maximum Safety",
        deltaVms: 0.63,
        fuelKg: 0.31,
        burnDurationSec: 16,
        riskReductionPct: 98.4,
        newProbability: 0.00000688,
        costUSD: 89200,
        lifespanImpactDays: 8,
        missionDowntimeHrs: 3.2,
        executionWindowMin: 234,
        cascadeRiskCreated: false
      },
      {
        id: "B",
        label: "Balanced",
        deltaVms: 0.31,
        fuelKg: 0.15,
        burnDurationSec: 8,
        riskReductionPct: 94.1,
        newProbability: 0.0000254,
        costUSD: 43700,
        lifespanImpactDays: 4,
        missionDowntimeHrs: 1.6,
        executionWindowMin: 412,
        cascadeRiskCreated: false
      },
      {
        id: "C",
        label: "Fuel Efficient",
        deltaVms: 0.12,
        fuelKg: 0.06,
        burnDurationSec: 3,
        riskReductionPct: 83.7,
        newProbability: 0.0000702,
        costUSD: 17400,
        lifespanImpactDays: 2,
        missionDowntimeHrs: 0.6,
        executionWindowMin: 687,
        cascadeRiskCreated: false
      }
    ]
  }
]

// ─── CASCADE RISKS ────────────────────────────────────────────────────────────
export const cascadeRisks = [
  {
    maneuverOptionId: "CDM-2026-0411-001-C",
    triggeringSatId: "ISS",
    affectedConjunctions: [
      {
        satId: "ISS",
        threatId: "ISS-DEB-051",
        newProbability: 0.000142,
        severity: "MEDIUM",
        timeToTCA: "6h 12m"
      }
    ]
  },
  {
    maneuverOptionId: "CDM-2026-0411-004-A",
    triggeringSatId: "STARLINK-4891",
    affectedConjunctions: [
      {
        satId: "STARLINK-4891",
        threatId: "STARLINK-5021",
        newProbability: 0.000089,
        severity: "LOW",
        timeToTCA: "22h 44m"
      },
      {
        satId: "STARLINK-4891",
        threatId: "STARLINK-4902",
        newProbability: 0.000034,
        severity: "LOW",
        timeToTCA: "23h 17m"
      }
    ]
  }
]

// ─── NATURAL LANGUAGE ALERTS (mocked Claude API output) ───────────────────────
export const naturalLanguageAlerts = [
  {
    id: "NLA-001",
    conjunctionId: "CDM-2026-0411-001",
    severity: "CRITICAL",
    satelliteId: "ISS",
    timestamp: "2026-04-11T22:17:34Z",
    headline: "ISS faces critical conjunction in 4h 32m",
    summary: "The International Space Station is on a collision course with a debris fragment from the 2021 COSMOS 1408 anti-satellite test. At 127 meters miss distance and 14.8 km/s relative velocity, a collision would be catastrophic. The debris cannot maneuver. ISS must act within the next 94 minutes to maintain maximum execution flexibility. Recommend Option B — balanced maneuver costing $64,800 and 9 days of operational life.",
    recommendedAction: "Execute maneuver Option B within 94 minutes",
    audienceLevel: "executive"
  },
  {
    id: "NLA-002",
    conjunctionId: "CDM-2026-0411-002",
    severity: "CRITICAL",
    satelliteId: "STARLINK-3120",
    timestamp: "2026-04-11T22:15:12Z",
    headline: "Starlink-3120 critical debris conjunction in 7h 57m",
    summary: "Starlink-3120 is approaching a COSMOS 1408 debris fragment at 203 meter miss distance. The debris object cannot maneuver. SpaceX standard protocol triggers automatic avoidance at 1:1,000,000 probability — this event at 1:535 is 1,870x above their threshold. Automated maneuver likely but manual confirmation recommended given proximity to ISS avoidance corridor.",
    recommendedAction: "Confirm automated maneuver, verify no ISS corridor conflict",
    audienceLevel: "operator"
  },
  {
    id: "NLA-003",
    conjunctionId: "CDM-2026-0411-003",
    severity: "HIGH",
    satelliteId: "WORLDVIEW-3",
    timestamp: "2026-04-11T21:44:08Z",
    headline: "WorldView-3 elevated risk — 15h window",
    summary: "WorldView-3 faces a 1:2,325 conjunction with an SL-8 rocket body. At $890M replacement value, maneuver cost of $17,400-$89,200 represents 0.002-0.01% of asset value. Rocket body cannot maneuver. 15-hour window provides flexibility. Recommend monitoring with maneuver decision by 06:00 UTC.",
    recommendedAction: "Monitor — decide by 06:00 UTC April 12",
    audienceLevel: "executive"
  },
  {
    id: "NLA-004",
    conjunctionId: "CDM-2026-0411-004",
    severity: "HIGH",
    satelliteId: "STARLINK-4891",
    timestamp: "2026-04-11T20:32:41Z",
    headline: "Starlink-to-Starlink conjunction — SpaceX likely coordinating",
    summary: "Two Starlink satellites are projected to pass within 1.2 km. Low relative velocity (0.31 km/s) indicates orbital plane crossing. SpaceX's automated system typically handles intra-constellation conjunctions. 67% confidence SpaceX maneuvers Starlink-3120 which resolves this event. Recommend waiting 4 hours for SpaceX coordination update before deciding.",
    recommendedAction: "Wait for SpaceX coordination — reassess in 4 hours",
    audienceLevel: "operator"
  }
]

// ─── OPERATOR BEHAVIOR PROFILES ──────────────────────────────────────────────
export const operatorProfiles = [
  {
    operator: "SpaceX",
    maneuverThreshold: 0.000001,  // 1:1,000,000 — 100x more conservative than industry
    historicalManeuverRate: 0.94, // maneuvers 94% of the time when threshold exceeded
    avgResponseTimeHrs: 2.3,
    fleetSize: 6200,
    dataSharing: "high"
  },
  {
    operator: "ESA",
    maneuverThreshold: 0.0001,    // 1:10,000 — industry standard
    historicalManeuverRate: 0.87,
    avgResponseTimeHrs: 6.1,
    fleetSize: 23,
    dataSharing: "high"
  },
  {
    operator: "Maxar Technologies",
    maneuverThreshold: 0.0001,
    historicalManeuverRate: 0.91,
    avgResponseTimeHrs: 4.2,
    fleetSize: 7,
    dataSharing: "medium"
  },
  {
    operator: "NASA",
    maneuverThreshold: 0.0001,
    historicalManeuverRate: 0.96,
    avgResponseTimeHrs: 8.4,
    fleetSize: 31,
    dataSharing: "high"
  }
]