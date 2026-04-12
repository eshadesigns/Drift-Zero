// src/data/mockData.js
// Based on real orbital mechanics and conjunction statistics
// Sources: NASA CARA, SpaceX regulatory filings, ESA Space Debris Office

// ─── FLEET STATS (top of StatsBar) ───────────────────────────────────────────
export const fleetStats = {
  activeSatellites: 142,
  activeConjunctions: 7,
  criticalAlerts: 2,
  avgCollisionProb: 0.00031,   // realistic LEO average per NASA CARA data
  maneuversThisMonth: 23,
  fuelSpentUSD: 847000,
  totalTrackedObjects: 27543,
  unconfirmedDebris: 500000
}

// ─── SATELLITES ───────────────────────────────────────────────────────────────
// IDs match GlobeView.jsx SAT_TLES entity IDs exactly
export const satellites = [
  {
    id: "ISS",
    name: "ISS (ZARYA)",
    operator: "NASA/Roscosmos",
    orbitAltitudeKm: 421,
    inclination: 51.6,
    vulnerabilityScore: 88,
    fuelRemainingKg: 4200,
    operationalLifeRemainingMonths: 48,
    missionType: "crewed",
    tle1: "1 25544U 98067A   24010.51860654  .00015509  00000-0  27915-3 0  9990",
    tle2: "2 25544  51.6416  16.2913 0004381  52.1284  87.2753 15.50117024412214"
  },
  {
    id: "HST",
    name: "Hubble Space Telescope",
    operator: "NASA/ESA",
    orbitAltitudeKm: 537,
    inclination: 28.5,
    vulnerabilityScore: 62,
    fuelRemainingKg: 0,
    operationalLifeRemainingMonths: 36,
    missionType: "science",
    tle1: "1 20580U 90037B   24010.12345678  .00001234  00000-0  56789-4 0  9991",
    tle2: "2 20580  28.4700 200.1234 0002345 100.5678 259.4321 15.09099873456789"
  },
  {
    id: "SL1",
    name: "STARLINK-1007",
    operator: "SpaceX",
    orbitAltitudeKm: 551,
    inclination: 53.0,
    vulnerabilityScore: 55,
    fuelRemainingKg: 18.4,
    operationalLifeRemainingMonths: 34,
    missionType: "communications",
    tle1: "1 44713U 19074A   24010.56525141  .00001064  00000-0  83911-4 0  9991",
    tle2: "2 44713  53.0543 144.1568 0001407  83.2185 276.9030 15.06399142211516"
  },
  {
    id: "SL2",
    name: "STARLINK-2055",
    operator: "SpaceX",
    orbitAltitudeKm: 551,
    inclination: 53.0,
    vulnerabilityScore: 48,
    fuelRemainingKg: 22.1,
    operationalLifeRemainingMonths: 41,
    missionType: "communications",
    tle1: "1 47526U 21006BK  24010.43210000  .00000800  00000-0  60000-4 0  9992",
    tle2: "2 47526  53.0550 220.3456 0001200  90.1234 270.0000 15.06400000200000"
  },
  {
    id: "NOAA18",
    name: "NOAA-18",
    operator: "NOAA",
    orbitAltitudeKm: 854,
    inclination: 99.0,
    vulnerabilityScore: 41,
    fuelRemainingKg: 45,
    operationalLifeRemainingMonths: 24,
    missionType: "earth_observation",
    tle1: "1 28654U 05018A   24010.50000000  .00000060  00000-0  60000-4 0  9993",
    tle2: "2 28654  99.0000  45.0000 0013000  80.0000 280.0000 14.12000000900000"
  },
  {
    id: "TERRA",
    name: "Terra (EOS AM-1)",
    operator: "NASA",
    orbitAltitudeKm: 716,
    inclination: 98.2,
    vulnerabilityScore: 67,
    fuelRemainingKg: 18,
    operationalLifeRemainingMonths: 12,
    missionType: "earth_observation",
    tle1: "1 25994U 99068A   24010.50000000  .00000050  00000-0  48000-4 0  9994",
    tle2: "2 25994  98.2000 120.0000 0001200 100.0000 260.0000 14.57000000800000"
  },
  {
    id: "METOP",
    name: "MetOp-A",
    operator: "EUMETSAT/ESA",
    orbitAltitudeKm: 830,
    inclination: 98.7,
    vulnerabilityScore: 38,
    fuelRemainingKg: 87,
    operationalLifeRemainingMonths: 18,
    missionType: "earth_observation",
    tle1: "1 29499U 06044A   24010.50000000  .00000040  00000-0  38000-4 0  9995",
    tle2: "2 29499  98.7000 200.0000 0002000 120.0000 240.0000 14.21000000850000"
  },
  {
    id: "AQUA",
    name: "Aqua (EOS PM-1)",
    operator: "NASA",
    orbitAltitudeKm: 705,
    inclination: 98.2,
    vulnerabilityScore: 44,
    fuelRemainingKg: 22,
    operationalLifeRemainingMonths: 18,
    missionType: "earth_observation",
    tle1: "1 27424U 02022A   24010.50000000  .00000050  00000-0  48000-4 0  9996",
    tle2: "2 27424  98.2000  60.0000 0001100 110.0000 250.0000 14.57100000700000"
  }
]

// ─── CONJUNCTIONS ─────────────────────────────────────────────────────────────
// Realistic collision probabilities based on NASA CARA thresholds:
// Green  < 1:10,000  (0.0001)
// Yellow < 1:1,000   (0.001)
// Red    > 1:1,000   (0.001+)
// Industry standard maneuver threshold: 1:10,000

// primarySatId values MUST match GlobeView.jsx SAT_TLES entity IDs: ISS, HST, SL1, SL2, NOAA18, TERRA, METOP, AQUA
// secondarySatId values reference GlobeView.jsx DEBRIS_STATIC entity IDs: DEB1–DEB28
export const conjunctions = [
  {
    id: "CDM-2026-0411-001",
    primarySatId: "ISS",
    primarySatName: "ISS (ZARYA)",
    secondarySatId: "DEB22",
    secondarySatName: "SL-12 R/B DEB #2",
    probability: 0.00312,       // 1:320 — well above maneuver threshold
    tcaTime: "2026-04-12T03:47:22Z",
    timeToTCA: "4h 32m",
    missDistanceKm: 0.127,      // 127 meters — extremely close
    relativeVelocityKms: 14.8,
    riskScore: 97,
    severity: "CRITICAL",
    doNothingConfidence: 0.04,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T22:15:00Z"
  },
  {
    id: "CDM-2026-0411-002",
    primarySatId: "ISS",
    primarySatName: "ISS (ZARYA)",
    secondarySatId: "DEB9",
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
    primarySatId: "SL1",
    primarySatName: "STARLINK-1007",
    secondarySatId: "DEB9",
    secondarySatName: "COSMOS 1408 DEB",
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
    primarySatId: "SL2",
    primarySatName: "STARLINK-2055",
    secondarySatId: "DEB7",
    secondarySatName: "BREEZE-M DEB",
    probability: 0.00021,
    tcaTime: "2026-04-12T19:08:55Z",
    timeToTCA: "20h 53m",
    missDistanceKm: 1.243,
    relativeVelocityKms: 9.8,
    riskScore: 61,
    severity: "HIGH",
    doNothingConfidence: 0.19,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T20:32:00Z"
  },
  {
    id: "CDM-2026-0411-005",
    primarySatId: "NOAA18",
    primarySatName: "NOAA-18",
    secondarySatId: "DEB2",
    secondarySatName: "FENGYUN 1C DEB",
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
    primarySatId: "TERRA",
    primarySatName: "Terra (EOS AM-1)",
    secondarySatId: "DEB25",
    secondarySatName: "CZ-4B R/B DEB",
    probability: 0.000034,
    tcaTime: "2026-04-13T11:44:21Z",
    timeToTCA: "36h 29m",
    missDistanceKm: 4.112,
    relativeVelocityKms: 7.6,
    riskScore: 28,
    severity: "LOW",
    doNothingConfidence: 0.71,
    operatorWillManeuver: false,
    lastUpdated: "2026-04-11T18:55:00Z"
  },
  {
    id: "CDM-2026-0411-007",
    primarySatId: "METOP",
    primarySatName: "MetOp-A",
    secondarySatId: "DEB17",
    secondarySatName: "FENGYUN 1C DEB #2",
    probability: 0.000012,
    tcaTime: "2026-04-13T22:17:44Z",
    timeToTCA: "47h 2m",
    missDistanceKm: 7.234,
    relativeVelocityKms: 7.2,
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
        threatId: "DEB21",        // SL-12 R/B DEB — nearby at 410km, 51.8° inc
        newProbability: 0.000142,
        severity: "MEDIUM",
        timeToTCA: "6h 12m"
      }
    ]
  },
  {
    maneuverOptionId: "CDM-2026-0411-004-A",
    triggeringSatId: "SL2",
    affectedConjunctions: [
      {
        satId: "SL2",
        threatId: "DEB23",        // PEGASUS DEB at 550km, 28.9° inc
        newProbability: 0.000089,
        severity: "LOW",
        timeToTCA: "22h 44m"
      },
      {
        satId: "SL2",
        threatId: "DEB24",        // COSMOS 3M R/B DEB at 560km, 82.9° inc
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
    summary: "The International Space Station is on a collision course with a SL-12 Proton rocket body fragment (DEB22) at only 127 meters miss distance and 14.8 km/s relative velocity. A collision at this speed would be catastrophic — generating thousands of new debris fragments at ISS orbital altitude. The debris cannot maneuver. ISS must act within the next 94 minutes to maintain maximum execution flexibility. Recommend Option B — balanced maneuver costing $64,800 and 9 days of operational life.",
    recommendedAction: "Execute maneuver Option B within 94 minutes",
    audienceLevel: "executive"
  },
  {
    id: "NLA-002",
    conjunctionId: "CDM-2026-0411-002",
    severity: "CRITICAL",
    satelliteId: "ISS",
    timestamp: "2026-04-11T22:15:12Z",
    headline: "ISS second critical conjunction — COSMOS 1408 debris in 7h 57m",
    summary: "ISS is approaching a COSMOS 1408 debris fragment (DEB9) at 203 meter miss distance. This debris originates from the 2021 Russian ASAT test which created over 1,500 trackable fragments. The debris object cannot maneuver. Note: ISS has a second conjunction (CDM-001) in under 5 hours — maneuver coordination between both events is critical.",
    recommendedAction: "Coordinate with CDM-001 maneuver planning — dual-conjunction window",
    audienceLevel: "operator"
  },
  {
    id: "NLA-003",
    conjunctionId: "CDM-2026-0411-003",
    severity: "HIGH",
    satelliteId: "SL1",
    timestamp: "2026-04-11T21:44:08Z",
    headline: "STARLINK-1007 elevated risk — COSMOS 1408 debris in 15h",
    summary: "STARLINK-1007 faces a 1:2,325 conjunction with a COSMOS 1408 debris fragment (DEB9). This is the same debris cloud threatening ISS — the fragment is crossing multiple orbital planes. SpaceX standard protocol triggers automatic avoidance at 1:1,000,000 — this event is 2,325x above that threshold. Automated maneuver likely.",
    recommendedAction: "Confirm SpaceX automated maneuver — verify no ISS corridor conflict",
    audienceLevel: "executive"
  },
  {
    id: "NLA-004",
    conjunctionId: "CDM-2026-0411-004",
    severity: "HIGH",
    satelliteId: "SL2",
    timestamp: "2026-04-11T20:32:41Z",
    headline: "STARLINK-2055 approaching BREEZE-M debris in 20h 53m",
    summary: "STARLINK-2055 is projected to pass within 1.2 km of a Breeze-M propellant tank fragment (DEB7) at 9.8 km/s relative velocity. The Breeze-M stage originates from a 2010 Proton-M launch and is tumbling. SpaceX automated avoidance system will likely handle this event. Recommend monitoring and confirmation of automated maneuver execution.",
    recommendedAction: "Monitor — confirm SpaceX automated maneuver by 16:00 UTC",
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

// demoManeuvers removed — options are now computed dynamically
// in ManeuverPanel.jsx :: computeManeuverOptions()

// ─── DEMO ORBITAL PARAMS (altitude + inclination for each primary satellite) ──
// TLEs MUST match GlobeView.jsx SAT_TLES exactly — same epoch, same elements
// so ManeuverPanel propagates the same orbit that GlobeView draws.
export const demoPrimaryOrbits = {
  // CDM-001 & CDM-002: ISS (norad 25544) — exact GlobeView TLE
  "CDM-2026-0411-001": {
    alt: 421, inclination: 51.6416,
    tle1: '1 25544U 98067A   24010.51860654  .00015509  00000-0  27915-3 0  9990',
    tle2: '2 25544  51.6416  16.2913 0004381  52.1284  87.2753 15.50117024412214',
    fuelRatio: 0.52, propCostPerKg: 135000, lifeDaysPerMs: 10,
  },
  "CDM-2026-0411-002": {
    alt: 421, inclination: 51.6416,
    tle1: '1 25544U 98067A   24010.51860654  .00015509  00000-0  27915-3 0  9990',
    tle2: '2 25544  51.6416  16.2913 0004381  52.1284  87.2753 15.50117024412214',
    fuelRatio: 0.52, propCostPerKg: 135000, lifeDaysPerMs: 10,
  },
  // CDM-003: SL1 / STARLINK-1007 (norad 44713) — exact GlobeView TLE
  "CDM-2026-0411-003": {
    alt: 551, inclination: 53.0543,
    tle1: '1 44713U 19074A   24010.56525141  .00001064  00000-0  83911-4 0  9991',
    tle2: '2 44713  53.0543 144.1568 0001407  83.2185 276.9030 15.06399142211516',
    fuelRatio: 0.50, propCostPerKg: 55000, lifeDaysPerMs: 6,
  },
  // CDM-004: SL2 / STARLINK-2055 (norad 47526) — exact GlobeView TLE
  "CDM-2026-0411-004": {
    alt: 551, inclination: 53.055,
    tle1: '1 47526U 21006BK  24010.43210000  .00000800  00000-0  60000-4 0  9992',
    tle2: '2 47526  53.0550 220.3456 0001200  90.1234 270.0000 15.06400000200000',
    fuelRatio: 0.50, propCostPerKg: 55000, lifeDaysPerMs: 6,
  },
  // CDM-005: NOAA18 (norad 28654) — exact GlobeView TLE
  "CDM-2026-0411-005": {
    alt: 854, inclination: 99.0,
    tle1: '1 28654U 05018A   24010.50000000  .00000060  00000-0  60000-4 0  9993',
    tle2: '2 28654  99.0000  45.0000 0013000  80.0000 280.0000 14.12000000900000',
    fuelRatio: 0.48, propCostPerKg: 75000, lifeDaysPerMs: 8,
  },
  // CDM-006: TERRA (norad 25994) — exact GlobeView TLE
  "CDM-2026-0411-006": {
    alt: 716, inclination: 98.2,
    tle1: '1 25994U 99068A   24010.50000000  .00000050  00000-0  48000-4 0  9994',
    tle2: '2 25994  98.2000 120.0000 0001200 100.0000 260.0000 14.57000000800000',
    fuelRatio: 0.54, propCostPerKg: 110000, lifeDaysPerMs: 12,
  },
  // CDM-007: METOP (norad 29499) — exact GlobeView TLE
  "CDM-2026-0411-007": {
    alt: 830, inclination: 98.7,
    tle1: '1 29499U 06044A   24010.50000000  .00000040  00000-0  38000-4 0  9995',
    tle2: '2 29499  98.7000 200.0000 0002000 120.0000 240.0000 14.21000000850000',
    fuelRatio: 0.52, propCostPerKg: 90000, lifeDaysPerMs: 7,
  },
}

// ─── DEMO SECONDARY ORBITS (threat object orbital parameters per conjunction) ──
// Coordinates MUST match GlobeView.jsx DEBRIS_STATIC exactly so ManeuverPanel's
// buildDebrisOrbit() produces the same orbit as GlobeView's simulateDebrisOrbit().
export const demoSecondaryOrbits = {
  // DEB22: SL-12 R/B DEB #2 — lat:-30, lon:-30, alt:420, inclination:51.6
  "CDM-2026-0411-001": { alt: 420, inclination: 51.6, lat: -30, lon: -30, type: 'debris' },
  // DEB9: COSMOS 1408 DEB — lat:48, lon:60, alt:470, inclination:82.6
  "CDM-2026-0411-002": { alt: 470, inclination: 82.6, lat:  48, lon:  60, type: 'debris' },
  // DEB9: COSMOS 1408 DEB — same fragment, different conjunction with SL1
  "CDM-2026-0411-003": { alt: 470, inclination: 82.6, lat:  48, lon:  60, type: 'debris' },
  // DEB7: BREEZE-M DEB — lat:-55, lon:-100, alt:495, inclination:49.9
  "CDM-2026-0411-004": { alt: 495, inclination: 49.9, lat: -55, lon: -100, type: 'debris' },
  // DEB2: FENGYUN 1C DEB — lat:15, lon:-60, alt:845, inclination:98.6
  "CDM-2026-0411-005": { alt: 845, inclination: 98.6, lat:  15, lon:  -60, type: 'debris' },
  // DEB25: CZ-4B R/B DEB — lat:55, lon:-130, alt:700, inclination:98.2
  "CDM-2026-0411-006": { alt: 700, inclination: 98.2, lat:  55, lon: -130, type: 'debris' },
  // DEB17: FENGYUN 1C DEB #2 — lat:20, lon:90, alt:860, inclination:98.7
  "CDM-2026-0411-007": { alt: 860, inclination: 98.7, lat:  20, lon:   90, type: 'debris' },
}

// ─── DEMO GLOBE OBJECTS (extra satellites + debris added to globe in demo mode) ─
// Added via window._driftViewer from main.jsx — purely visual, not clickable
export const demoGlobeObjects = [
  // ── Extra satellites ──────────────────────────────────────────────────────
  { id: 'DEMO_SAT_01', name: 'CUBESAT-2025-001',   type: 'satellite', lat:  23, lon: -87, alt: 510 },
  { id: 'DEMO_SAT_02', name: 'IRIDIUM-166',         type: 'satellite', lat: -18, lon: 145, alt: 780 },
  { id: 'DEMO_SAT_03', name: 'LANDSAT-9',           type: 'satellite', lat:  62, lon:  32, alt: 705 },
  { id: 'DEMO_SAT_04', name: 'SUOMI-NPP',           type: 'satellite', lat: -44, lon: -50, alt: 824 },
  { id: 'DEMO_SAT_05', name: 'JASON-3',             type: 'satellite', lat:  11, lon:  20, alt: 1336 },
  { id: 'DEMO_SAT_06', name: 'GOES-18',             type: 'satellite', lat:   5, lon:-137, alt: 35786 },
  { id: 'DEMO_SAT_07', name: 'STARLINK-5102',       type: 'satellite', lat:  38, lon:  72, alt: 548 },
  { id: 'DEMO_SAT_08', name: 'STARLINK-5234',       type: 'satellite', lat: -29, lon: -20, alt: 551 },
  { id: 'DEMO_SAT_09', name: 'ONEWEB-0234',         type: 'satellite', lat:  55, lon: 100, alt: 1200 },
  { id: 'DEMO_SAT_10', name: 'PLANET-FLOCK-4E',    type: 'satellite', lat:  -8, lon:  60, alt: 480 },
  // ── Extra debris ──────────────────────────────────────────────────────────
  { id: 'DEMO_DEB_01', name: 'COSMOS 1408 DEB #4',  type: 'debris', lat:  44, lon:  80, alt: 455 },
  { id: 'DEMO_DEB_02', name: 'COSMOS 1408 DEB #5',  type: 'debris', lat: -22, lon: 120, alt: 490 },
  { id: 'DEMO_DEB_03', name: 'COSMOS 1408 DEB #6',  type: 'debris', lat:  60, lon: -40, alt: 480 },
  { id: 'DEMO_DEB_04', name: 'FY-1C DEB #4',        type: 'debris', lat:  10, lon: -20, alt: 832 },
  { id: 'DEMO_DEB_05', name: 'FY-1C DEB #5',        type: 'debris', lat: -35, lon:  70, alt: 858 },
  { id: 'DEMO_DEB_06', name: 'FY-1C DEB #6',        type: 'debris', lat:  25, lon: 160, alt: 841 },
  { id: 'DEMO_DEB_07', name: 'IRIDIUM 33 DEB #4',   type: 'debris', lat: -55, lon: -80, alt: 763 },
  { id: 'DEMO_DEB_08', name: 'IRIDIUM 33 DEB #5',   type: 'debris', lat:  30, lon:-160, alt: 784 },
  { id: 'DEMO_DEB_09', name: 'COSMOS 2251 DEB #2',  type: 'debris', lat:  16, lon: -60, alt: 812 },
  { id: 'DEMO_DEB_10', name: 'COSMOS 2251 DEB #3',  type: 'debris', lat: -40, lon:  30, alt: 791 },
  { id: 'DEMO_DEB_11', name: 'SL-16 R/B DEB #3',   type: 'debris', lat:  52, lon: -10, alt: 793 },
  { id: 'DEMO_DEB_12', name: 'BREEZE-M DEB #3',     type: 'debris', lat: -12, lon:  50, alt: 502 },
  { id: 'DEMO_DEB_13', name: 'DELTA 4 DEB',         type: 'debris', lat:  35, lon:-110, alt: 660 },
  { id: 'DEMO_DEB_14', name: 'H-2A DEB #2',         type: 'debris', lat: -68, lon:  90, alt: 680 },
  { id: 'DEMO_DEB_15', name: 'CZ-4B DEB #2',        type: 'debris', lat:  48, lon: 140, alt: 710 },
  { id: 'DEMO_DEB_16', name: 'ARIANE 5 DEB',        type: 'debris', lat: -20, lon: -80, alt: 588 },
  { id: 'DEMO_DEB_17', name: 'ATLAS V DEB',         type: 'debris', lat:  18, lon:  -5, alt: 745 },
  { id: 'DEMO_DEB_18', name: 'PSLV-C37 DEB',        type: 'debris', lat:  72, lon:  60, alt: 498 },
  { id: 'DEMO_DEB_19', name: 'SL-14 R/B DEB',       type: 'debris', lat: -50, lon: 170, alt: 830 },
  { id: 'DEMO_DEB_20', name: 'MOLNIYA DEB',         type: 'debris', lat:  65, lon:  20, alt: 620 },
]

// ─── MOCK ROGUE EVENTS (adversarial / suspicious satellites per focused sat) ──
// Keyed by GlobeView entity ID. Format matches RoguePanel's live API shape.
export const mockRogueEvents = {
  "ISS": [
    {
      norad_id: 48915,
      name: "COSMOS 2571 (LUCH-5X)",
      severity: "ADVERSARIAL",
      composite_score: 0.912,
      epoch: "2026-04-11T18:00:00Z",
      summary: "Russian relay satellite conducting pattern-of-life monitoring of ISS. Object has maneuvered 14 times in 90 days maintaining 8–12 km trailing distance. Consistent with known Russian inspector behavior documented in 2022–2024 ESA reports.",
      anomalous_features: ["proximity_approach", "persistent_co_orbital", "repeated_maneuvers", "attitude_anomaly"]
    },
    {
      norad_id: 57161,
      name: "SHIJIAN-21B",
      severity: "SUSPICIOUS",
      composite_score: 0.647,
      epoch: "2026-04-10T12:00:00Z",
      summary: "Chinese experimental satellite that executed 3 burns in 7 days moving from GEO to a lower transfer orbit. Current trajectory intercepts ISS orbital band within 72 hours. Mission is uncharacterized.",
      anomalous_features: ["unexpected_maneuvers", "orbit_change", "unregistered_mission"]
    },
    {
      norad_id: 61234,
      name: "SHIJIAN-23 (PROXIMITY)",
      severity: "SUSPICIOUS",
      composite_score: 0.721,
      epoch: "2026-04-11T22:00:00Z",
      summary: "Chinese experimental satellite at 422 km altitude locked to ISS orbital plane — current separation approximately 2.1 km. No maneuver declared. Maintaining this proximity for 9 consecutive days with active station-keeping signature. Within sensor interference range of ISS communications systems.",
      anomalous_features: ["proximity_approach", "orbit_matching", "active_station_keeping", "unannounced_approach"]
    }
  ],
  "SL1": [
    {
      norad_id: 55343,
      name: "KOSMOS-2576",
      severity: "ADVERSARIAL",
      composite_score: 0.881,
      epoch: "2026-04-11T20:00:00Z",
      summary: "Russian inspector satellite maintaining ~3 km separation from STARLINK-1007 for 18 days. Matches signature of Kosmos nesting-doll class capable of releasing sub-payloads. Pattern matches adversarial rendezvous documented against Starlink Group 4-2 in 2024.",
      anomalous_features: ["persistent_co_orbital", "proximity_approach", "inspector_class", "sub_payload_capable"]
    },
    {
      norad_id: 58821,
      name: "OBJECT 58821 (UNCAT.)",
      severity: "SUSPICIOUS",
      composite_score: 0.534,
      epoch: "2026-04-09T08:00:00Z",
      summary: "Uncatalogued object detected by LeoLabs radar at 551 km, 53° inclination — co-orbital with STARLINK-1007. No launch registration. Estimated cross-section consistent with CubeSat.",
      anomalous_features: ["unregistered_launch", "co_orbital", "unknown_origin"]
    }
  ],
  "SL2": [
    {
      norad_id: 55343,
      name: "KOSMOS-2576",
      severity: "SUSPICIOUS",
      composite_score: 0.612,
      epoch: "2026-04-11T14:00:00Z",
      summary: "Same Russian inspector satellite (KOSMOS-2576) widening surveillance arc to cover both STARLINK-1007 and STARLINK-2055. Current range to SL2 is approximately 18 km. Consistent with dual-target observation pattern.",
      anomalous_features: ["proximity_approach", "multi_target_surveillance", "inspector_class"]
    }
  ],
  "NOAA18": [
    {
      norad_id: 37214,
      name: "FENGYUN-3D",
      severity: "SUSPICIOUS",
      composite_score: 0.598,
      epoch: "2026-04-10T06:00:00Z",
      summary: "Chinese weather satellite in adjacent sun-synchronous orbit. Executed 2 unannounced maneuvers narrowing separation from 45 km to 12 km over 30 days. FY-3D carries imaging payload with resolution potentially applicable to signals intelligence.",
      anomalous_features: ["unannounced_maneuvers", "narrowing_separation", "dual_use_payload"]
    }
  ],
  "TERRA": [
    {
      norad_id: 59012,
      name: "YAOGAN-41",
      severity: "ADVERSARIAL",
      composite_score: 0.857,
      epoch: "2026-04-11T16:00:00Z",
      summary: "Chinese reconnaissance satellite co-orbiting with Terra at 5.2 km separation for 22 consecutive days with no orbital evolution — implying active station-keeping. Terra's MODIS and MISR sensors serve US military environmental intelligence. This proximity is anomalous and unprecedented for this object class.",
      anomalous_features: ["active_station_keeping", "persistent_co_orbital", "intelligence_target", "zero_natural_drift"]
    },
    {
      norad_id: 56781,
      name: "OBJECT 56781 (UNCAT.)",
      severity: "SUSPICIOUS",
      composite_score: 0.501,
      epoch: "2026-04-08T10:00:00Z",
      summary: "Small unregistered object detected at 712 km, 98.1° inclination — within Terra's orbital shell. Origin unknown. Could be fragment or intentionally deployed micro-satellite.",
      anomalous_features: ["unregistered_object", "co_orbital_shell", "unknown_origin"]
    }
  ],
  "METOP": [
    {
      norad_id: 43566,
      name: "LOTOS-S1",
      severity: "ADVERSARIAL",
      composite_score: 0.778,
      epoch: "2026-04-11T10:00:00Z",
      summary: "Russian ELINT satellite maintaining 22 km co-orbital distance from MetOp-A for 41 days. MetOp carries ASCAT and IASI instruments sharing data with NATO meteorological centers. LOTOS-S1 class is known to intercept downlink signals from target satellites.",
      anomalous_features: ["elint_class", "signal_interception", "persistent_co_orbital", "nato_asset_target"]
    }
  ],
  "HST": [],
  "AQUA": [
    {
      norad_id: 43567,
      name: "ZIYUAN-3C",
      severity: "SUSPICIOUS",
      composite_score: 0.442,
      epoch: "2026-04-09T14:00:00Z",
      summary: "Chinese land survey satellite that executed a 0.4 m/s maneuver 6 days ago reducing separation from Aqua to 28 km. No operational justification given ZY-3C's stated mapping mission.",
      anomalous_features: ["unexplained_maneuver", "narrowing_separation"]
    }
  ]
}

// ─── MOCK ASSET IMPACT (ported from backend/rogue/impact.py) ─────────────────
// Economic and strategic value of each focused satellite.
// Keyed by GlobeView entity ID. Shape matches /api/rogue/impact/{norad_id} response.
export const mockAssetImpact = {
  ISS: {
    norad_id: 25544,
    name: "International Space Station",
    constellation: "ISS",
    strategic_tier: "HIGH",
    economic_impact_usd_per_day: 150000000,
    economic_impact_formatted: "$150M",
    users_at_risk: "7 crew members, 15-nation partnership",
    mission_description: "Human spaceflight platform, microgravity research, international cooperation",
    replacement_cost_usd: 150000000000,
    replacement_cost_formatted: "$150B",
    notes: "$150B assembly cost. Loss would end human LEO presence for years."
  },
  HST: {
    norad_id: 20580,
    name: "Hubble Space Telescope",
    constellation: "Science",
    strategic_tier: "HIGH",
    economic_impact_usd_per_day: 10000000,
    economic_impact_formatted: "$10M",
    users_at_risk: "Global scientific community",
    mission_description: "UV/optical astronomy — 30-year mission, 1.5M observations",
    replacement_cost_usd: 10000000000,
    replacement_cost_formatted: "$10B",
    notes: "Irreplaceable scientific asset. No servicing mission currently planned."
  },
  NOAA18: {
    norad_id: 28654,
    name: "NOAA-18",
    constellation: "NOAA",
    strategic_tier: "HIGH",
    economic_impact_usd_per_day: 50000000,
    economic_impact_formatted: "$50M",
    users_at_risk: "300M US residents — weather forecasting, hurricane track",
    mission_description: "Polar-orbiting weather satellite — severe weather monitoring",
    replacement_cost_usd: 500000000,
    replacement_cost_formatted: "$500M",
    notes: "Part of NOAA POES constellation. Loss degrades hurricane forecasting by 12-18 hours."
  },
  TERRA: {
    norad_id: 25994,
    name: "Terra (EOS AM-1)",
    constellation: "NASA EOS",
    strategic_tier: "HIGH",
    economic_impact_usd_per_day: 25000000,
    economic_impact_formatted: "$25M",
    users_at_risk: "Climate scientists, agricultural sector, US military environmental intel",
    mission_description: "Multi-instrument Earth observation — MODIS, MISR, ASTER sensors",
    replacement_cost_usd: 1300000000,
    replacement_cost_formatted: "$1.3B",
    notes: "MODIS data used by US military for weather and terrain analysis."
  },
  METOP: {
    norad_id: 29499,
    name: "MetOp-A",
    constellation: "EUMETSAT",
    strategic_tier: "MEDIUM",
    economic_impact_usd_per_day: 30000000,
    economic_impact_formatted: "$30M",
    users_at_risk: "European aviation, NATO meteorological centers",
    mission_description: "Polar-orbiting operational meteorology for Europe and NATO",
    replacement_cost_usd: 700000000,
    replacement_cost_formatted: "$700M",
    notes: "ASCAT and IASI data shared with NATO. Loss affects EU weather forecasting and military ops."
  },
  SL1: {
    norad_id: 44713,
    name: "STARLINK-1007",
    constellation: "Starlink",
    strategic_tier: "MEDIUM",
    economic_impact_usd_per_day: 500000,
    economic_impact_formatted: "$500K",
    users_at_risk: "Broadband subscribers in coverage zone",
    mission_description: "Broadband internet constellation satellite",
    replacement_cost_usd: 500000,
    replacement_cost_formatted: "$500K",
    notes: "Individual loss absorbed by constellation. Pattern of targeting Starlink is strategically significant."
  },
  SL2: {
    norad_id: 47526,
    name: "STARLINK-2055",
    constellation: "Starlink",
    strategic_tier: "MEDIUM",
    economic_impact_usd_per_day: 500000,
    economic_impact_formatted: "$500K",
    users_at_risk: "Broadband subscribers in coverage zone",
    mission_description: "Broadband internet constellation satellite — v1.5 with laser inter-satellite links",
    replacement_cost_usd: 500000,
    replacement_cost_formatted: "$500K",
    notes: "Starlink provides Ukraine with battlefield internet. KOSMOS-2576 targeting is strategically motivated."
  },
  AQUA: null,
}

// ─── MOCK MISSION MISMATCH (ported from backend/rogue/mission_mismatch.py) ────
// Declared vs actual behavior scoring. Keyed by GlobeView entity ID.
// Shape matches /api/rogue/mismatch/{norad_id} response.
export const mockMissionMismatch = {
  ISS: {
    norad_id: 25544,
    object_name: "ISS",
    declared_mission: "crewed",
    mismatch_score: 0.06,
    verdict: "NORMAL",
    signals: [],
    notes: "Expected maneuvering for debris avoidance. All burns within normal mission profile."
  },
  HST: {
    norad_id: 20580,
    object_name: "Hubble Space Telescope",
    declared_mission: "science",
    mismatch_score: 0.08,
    verdict: "NORMAL",
    signals: [],
    notes: "No propulsion. Station-keeping via gyroscopes only. No anomalous behavior."
  },
  SL1: {
    norad_id: 44713,
    object_name: "STARLINK-1007",
    declared_mission: "communications",
    mismatch_score: 0.15,
    verdict: "NORMAL",
    signals: ["slightly_elevated_proximity_maneuvers"],
    notes: "Normal Starlink behavior — regular orbital maintenance, drag compensation."
  },
  SL2: {
    norad_id: 47526,
    object_name: "STARLINK-2055",
    declared_mission: "communications",
    mismatch_score: 0.18,
    verdict: "NORMAL",
    signals: ["slightly_elevated_proximity_maneuvers"],
    notes: "v1.5 with laser links — expected slightly more maneuvering for inter-sat alignment."
  },
  NOAA18: {
    norad_id: 28654,
    object_name: "NOAA-18",
    declared_mission: "weather",
    mismatch_score: 0.09,
    verdict: "NORMAL",
    signals: [],
    notes: "Minimal station-keeping. Behavior fully consistent with operational weather satellite."
  },
  TERRA: {
    norad_id: 25994,
    object_name: "Terra (EOS AM-1)",
    declared_mission: "science",
    mismatch_score: 0.11,
    verdict: "NORMAL",
    signals: [],
    notes: "Aging spacecraft with declining fuel reserves. Fewer maneuvers than earlier in mission."
  },
  METOP: {
    norad_id: 29499,
    object_name: "MetOp-A",
    declared_mission: "weather",
    mismatch_score: 0.13,
    verdict: "NORMAL",
    signals: [],
    notes: "Operational meteorological satellite. Behavior consistent with EUMETSAT operational norms."
  },
  AQUA: {
    norad_id: 27424,
    object_name: "Aqua (EOS PM-1)",
    declared_mission: "science",
    mismatch_score: 0.10,
    verdict: "NORMAL",
    signals: [],
    notes: "Formation flying with Terra. Controlled orbit lowers periodically for coverage overlap."
  },
}

// ─── MOCK INCIDENTS (ported from backend/rogue/incidents.py) ─────────────────
// Documented historical adversarial satellite incidents.
// Shape matches /api/rogue/incidents response.
// relevantSatIds: which focused satellite entity IDs this incident is relevant to.
export const mockIncidents = [
  {
    id: "cosmos-1408-asat-2021",
    title: "Cosmos 1408 ASAT Destruction",
    date: "2021-11-15",
    classification: "ASAT",
    relevantSatIds: ["ISS"],
    summary: "Russia deliberately destroyed its own Cosmos 1408 satellite with a direct-ascent ASAT missile, generating ~1,500 trackable debris pieces and forcing ISS crew to shelter. The pre-launch maneuvering of the interceptor vehicle is visible in TLE history.",
    actor: { norad_id: 13552, name: "COSMOS 1408", country: "Russia" },
    target: { norad_id: 25544, name: "ISS", country: "International" },
    consequence: "1,500+ trackable debris pieces in ISS-crossing orbit. ISS crew sheltered for 2 hours. Debris field persists for decades — DEB9–DEB11 in this system are Cosmos 1408 fragments.",
    detection_summary: "Drift Zero would have flagged unusual orbital activity 3 days before the event. Debris cloud created conjunction events with ISS within hours.",
  },
  {
    id: "kosmos-2542-shadowing-2020",
    title: "Kosmos 2542/2543 Inspector Campaign",
    date: "2020-02-10",
    classification: "SHADOWING",
    relevantSatIds: ["SL1", "SL2"],
    summary: "Russia's Kosmos 2542 deployed a sub-satellite (Kosmos 2543) which began shadowing a classified US reconnaissance satellite at close range. US Space Force warned this was 'consistent with a space weapons system.'",
    actor: { norad_id: 44878, name: "COSMOS 2542", country: "Russia" },
    target: { norad_id: 45175, name: "COSMOS 2543 (sub-satellite)", country: "Russia" },
    consequence: "US Space Force issued public statement Feb 2020. Demonstrated Russia's ability to deploy inspector satellites that can surveil or threaten US intelligence assets. KOSMOS-2576 currently shadowing Starlink uses the same tactics.",
    detection_summary: "Delta-V spike detected at sub-satellite ejection. Sustained low-level maneuvering confirmed station-keeping near target for 18+ days.",
  },
  {
    id: "shijian-21-relocation-2022",
    title: "SJ-21 Satellite Relocation (Dead BeiDou Tug)",
    date: "2022-01-22",
    classification: "RELOCATION",
    relevantSatIds: ["TERRA", "METOP", "NOAA18"],
    summary: "China's Shijian-21 grappled and moved a dead BeiDou-2 satellite to a graveyard orbit 300 km above GEO, demonstrating a rendezvous and proximity operations capability usable offensively against any GEO or LEO asset.",
    actor: { norad_id: 49395, name: "SHIJIAN-21", country: "China" },
    target: { norad_id: 37256, name: "COMPASS G2 (dead BeiDou)", country: "China" },
    consequence: "Demonstrated China can grapple and move any satellite. Same capability used offensively could disable GPS, comms, or military satellites without leaving debris. YAOGAN-41 near TERRA uses related RPO technology.",
    detection_summary: "Large delta-V proxy spikes detected during rendezvous and relocation burns. Orbital element changes clearly visible in TLE history.",
  },
  {
    id: "kosmos-2576-gps-approach-2024",
    title: "Kosmos 2576 GPS Close Approach",
    date: "2024-05-01",
    classification: "INSPECTION",
    relevantSatIds: ["SL1", "SL2", "ISS"],
    summary: "Russia's Kosmos 2576 maneuvered to within ~30 km of GPS IIR-20 (USA-201). US Space Command characterized it as a 'space-based anti-satellite weapon.' Most recent documented Russian inspector satellite approaching US critical infrastructure.",
    actor: { norad_id: 56217, name: "COSMOS 2576", country: "Russia" },
    target: { norad_id: 26690, name: "GPS IIR-20 (USA-201)", country: "USA" },
    consequence: "US Space Command public statement May 2024. GPS IIR-20 economic impact if disabled: ~$1B/day. Same satellite class (KOSMOS-2576) is currently shadowing Starlink satellites in this system.",
    detection_summary: "Multiple delta-V spikes confirmed active maneuvering to match GPS orbital regime. Drift Zero composite score would have exceeded ADVERSARIAL threshold 14 days before US public disclosure.",
  },
]

// ─── ROGUE ACTOR POSITIONS (adversarial/suspicious satellites on globe) ────────
// These are the threat actors described in mockRogueEvents, given approximate
// positions in the same orbital regime as their target satellites.
// All coordinates derived from the targets' SAT_ORBIT_PARAMS data in satelliteOrbits.js.
// Added to globe in demo mode by main.jsx — same mechanism as demoGlobeObjects.
export const rogueActorPositions = [
  // Near ISS (421km, 51.6°)
  { id: 'ROGUE_01', name: 'COSMOS 2571 (LUCH-5X)',  type: 'rogue', severity: 'ADVERSARIAL', targetId: 'ISS', lat:  32, lon:  18, alt: 429 },
  { id: 'ROGUE_02', name: 'SHIJIAN-21B',            type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'ISS', lat:  20, lon: -76, alt: 430 },
  // DEMO: SHIJIAN-23 placed at 422 km — only 1 km above ISS, same inclination → orbit nearly overlaps ISS on globe
  { id: 'ROGUE_10', name: 'SHIJIAN-23 (PROXIMITY)', type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'ISS', lat:  48, lon:  15, alt: 422 },
  // Near SL1/SL2 (551km, 53°)
  { id: 'ROGUE_03', name: 'KOSMOS-2576',           type: 'rogue', severity: 'ADVERSARIAL', targetId: 'SL1', lat:  46, lon:  36, alt: 554 },
  { id: 'ROGUE_04', name: 'OBJECT 58821 (UNCAT.)', type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'SL1', lat:  53, lon: 122, alt: 551 },
  // Near NOAA18 (854km, 99°)
  { id: 'ROGUE_05', name: 'FENGYUN-3D',            type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'NOAA18', lat:  28, lon: 150, alt: 866 },
  // Near TERRA (716km, 98.2°)
  { id: 'ROGUE_06', name: 'YAOGAN-41',             type: 'rogue', severity: 'ADVERSARIAL', targetId: 'TERRA', lat:  60, lon: -115, alt: 721 },
  { id: 'ROGUE_07', name: 'OBJECT 56781 (UNCAT.)', type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'TERRA', lat:  38, lon:  -25, alt: 712 },
  // Near METOP (830km, 98.7°)
  { id: 'ROGUE_08', name: 'LOTOS-S1',              type: 'rogue', severity: 'ADVERSARIAL', targetId: 'METOP', lat:  57, lon:  74, alt: 852 },
  // Near AQUA (705km, 98.2°)
  { id: 'ROGUE_09', name: 'ZIYUAN-3C',             type: 'rogue', severity: 'SUSPICIOUS',  targetId: 'AQUA', lat: -22, lon: 140, alt: 705 },
]