// src/api/shield.js
// Fetches conjunction events from the Shield FastAPI backend and normalizes
// the response shape to match what the dashboard components expect.

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

// ── Map Shield API event → dashboard conjunction shape ────────────────────────
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
  }
}

// ── Derive StatsBar numbers from a normalized conjunction list ─────────────────
export function deriveStats(conjunctions) {
  const n = conjunctions.length
  const avgPc = n > 0
    ? conjunctions.reduce((sum, c) => sum + c.probability, 0) / n
    : 0
  const primaryIds = new Set(conjunctions.map(c => c.primarySatId))

  return {
    activeSatellites:    primaryIds.size,
    activeConjunctions:  n,
    criticalAlerts:      conjunctions.filter(c => c.severity === 'CRITICAL').length,
    avgCollisionProb:    avgPc,
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
