// src/api/shield.js
// Fetches conjunction events from the unified Drift Zero API (backend/api.py)
// and normalizes the response shape to match what the dashboard components expect.
// The unified API enriches each event with a Claude-generated summary field.

const BASE_URL = import.meta.env.VITE_SHIELD_API_URL ?? 'http://localhost:8000'

// ── Severity from risk score ──────────────────────────────────────────────────
function riskToSeverity(score) {
  if (score >= 80) return 'CRITICAL'
  if (score >= 60) return 'HIGH'
  if (score >= 35) return 'MEDIUM'
  return 'LOW'
}

// ── Time-to-TCA string ────────────────────────────────────────────────────────
function formatTCA(tcaUtc) {
  const ms = new Date(tcaUtc).getTime() - Date.now()
  if (ms <= 0) return 'past'
  const totalMin = Math.floor(ms / 60000)
  const hours = Math.floor(totalMin / 60)
  const mins = totalMin % 60
  return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
}

// ── Map API event → dashboard conjunction shape ───────────────────────────────
export function normalizeConjunction(event) {
  const riskScore = Math.round(event.risk_score)
  return {
    id:                   event.event_id,
    primarySatId:         String(event.primary.norad_id),
    primarySatName:       event.primary.name,
    secondarySatId:       String(event.secondary.norad_id),
    secondarySatName:     event.secondary.name,
    probability:          event.collision_probability,
    tcaTime:              event.tca_utc,
    timeToTCA:            formatTCA(event.tca_utc),
    missDistanceKm:       event.miss_distance_km,
    relativeVelocityKms:  event.relative_velocity_km_s,
    riskScore,
    severity:             riskToSeverity(riskScore),
    doNothingConfidence:  event.do_nothing_confidence ?? 0.5,
    operatorWillManeuver: false,
    lastUpdated:          event.timestamp_utc,
    confidence:           event.confidence,
    kpIndex:              event.kp_index,
    dataAgeMinutes:       event.data_age_minutes,
    primaryTleLine1:      event.primary.tle_line1  ?? '',
    primaryTleLine2:      event.primary.tle_line2  ?? '',
    secondaryTleLine1:    event.secondary.tle_line1 ?? '',
    secondaryTleLine2:    event.secondary.tle_line2 ?? '',
    secondaryInclinationDeg: event.secondary.inclination_deg ?? null,
    secondaryApoapsisKm:     event.secondary.apoapsis_km     ?? null,
    secondaryPeriapsisKm:    event.secondary.periapsis_km    ?? null,
    secondaryCountryCode:    event.secondary.country_code    ?? '',
    secondaryLaunchDate:     event.secondary.launch_date     ?? '',
  }
}

// ── Derive StatsBar numbers from a normalized conjunction list ─────────────────
export function deriveStats(conjunctions) {
  const n = conjunctions.length
  // Max Pc is more operationally meaningful than average — it surfaces the
  // worst-case event. Average hides signal when most events have Pc near zero.
  const maxPc = n > 0
    ? Math.max(...conjunctions.map(c => c.probability))
    : 0

  return {
    // activeSatellites intentionally omitted — let mockFleetStats provide the
    // fleet-wide count rather than overriding with 1 (single primary satellite).
    activeConjunctions:  n,
    criticalAlerts:      conjunctions.filter(c => c.severity === 'CRITICAL').length,
    maxCollisionProb:    maxPc,
  }
}

// ── Fetch conjunctions from Shield API ───────────────────────────────────────
// Returns { conjunctions, stats } on success, or throws so the caller can fall back.
export async function fetchConjunctions({ minRisk = 0, limit = 100 } = {}) {
  const url = `${BASE_URL}/conjunctions?min_risk=${minRisk}&limit=${limit}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Shield API ${res.status}: ${res.statusText}`)
  const data = await res.json()
  const conjunctions = (data.events ?? []).map(normalizeConjunction)
  return { conjunctions, stats: deriveStats(conjunctions) }
}

// ── Fetch satellite info (name, TLE, orbital params) ─────────────────────────
// Returns the /satellite/{norad_id} response directly.
export async function fetchSatellite(noradId) {
  const url = `${BASE_URL}/satellite/${noradId}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Shield API ${res.status}: ${res.statusText}`)
  return res.json()
}

// ── Fetch maneuver options for a conjunction event ────────────────────────────
// Returns { event_id, norad_id, primary_name, current_miss_km, maneuver_options }
export async function fetchManeuvers(noradId, eventId) {
  const url = `${BASE_URL}/maneuvers/${noradId}/${eventId}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Shield API ${res.status}: ${res.statusText}`)
  return res.json()
}

// ── Fetch cascade risks for a maneuver choice ─────────────────────────────────
// maneuverLabel must be a slug: maximum_safety | balanced | fuel_efficient
// Returns { event_id, norad_id, primary_name, maneuver_label, delta_v_ms,
//           candidates_screened, cascade_risks }
export async function fetchCascade(noradId, eventId, maneuverLabel) {
  const url = `${BASE_URL}/cascade/${noradId}/${eventId}/${maneuverLabel}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Shield API ${res.status}: ${res.statusText}`)
  return res.json()
}
