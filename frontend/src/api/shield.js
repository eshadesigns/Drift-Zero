// src/api/shield.js
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
  const riskScore = Math.round(event.risk_score ?? 0)
  return {
    id:                   event.event_id,
    primarySatId:         String(event.primary?.norad_id ?? ''),
    primarySatName:       event.primary?.name ?? '',
    secondarySatId:       String(event.secondary?.norad_id ?? ''),
    secondarySatName:     event.secondary?.name ?? '',
    probability:          event.collision_probability ?? 0,
    tcaTime:              event.tca_utc,
    timeToTCA:            formatTCA(event.tca_utc),
    missDistanceKm:       event.miss_distance_km ?? 0,
    relativeVelocityKms:  event.relative_velocity_km_s ?? 0,
    riskScore,
    severity:             riskToSeverity(riskScore),
    doNothingConfidence:  event.do_nothing_confidence ?? 0.5,
    lastUpdated:          event.timestamp_utc,
    dataAgeMinutes:       event.data_age_minutes,
    summary:              event.summary ?? '',
  }
}

// ── Derive StatsBar numbers from a normalized conjunction list ─────────────────
export function deriveStats(conjunctions) {
  const n = conjunctions.length
  const maxPc = n > 0
    ? Math.max(...conjunctions.map(c => c.probability))
    : 0

  return {
    activeConjunctions: n,
    criticalAlerts:     conjunctions.filter(c => c.severity === 'CRITICAL').length,
    maxCollisionProb:   maxPc,
  }
}

// ── Fetch conjunctions from Shield API ────────────────────────────────────────
export async function fetchConjunctions(noradId, { minRisk = 0, limit = 100 } = {}, signal) {
  const url = `${BASE_URL}/api/conjunctions/${noradId}?min_risk=${minRisk}&limit=${limit}`
  const res = await fetch(url, signal ? { signal } : undefined)
  if (!res.ok) throw new Error(`Shield API ${res.status}: ${res.statusText}`)
  const data = await res.json()
  const conjunctions = (data.events ?? []).map(normalizeConjunction)
  return { conjunctions, stats: deriveStats(conjunctions) }
}

// ── Mock fallbacks (used when backend has no pipeline cache for this event) ────
// Shape matches the live API response so components need no special handling.
const _MOCK_MANEUVERS = {
  event_id: 'mock',
  primary_name: 'Primary Satellite',
  current_miss_km: 0.127,
  maneuver_options: [
    { label: 'Maximum Safety',  delta_v_ms: 1.82, fuel_kg: 0.94, fuel_cost_usd: 127400, lifespan_reduction_days: 18, composite_score: 0.91, miss_increase_km: 48.2 },
    { label: 'Balanced',        delta_v_ms: 0.94, fuel_kg: 0.48, fuel_cost_usd: 64800,  lifespan_reduction_days: 9,  composite_score: 0.84, miss_increase_km: 24.1 },
    { label: 'Fuel Efficient',  delta_v_ms: 0.41, fuel_kg: 0.21, fuel_cost_usd: 28300,  lifespan_reduction_days: 4,  composite_score: 0.71, miss_increase_km: 10.5 },
  ],
}

const _MOCK_CASCADE = {
  event_id: 'mock',
  maneuver_label: 'Balanced',
  delta_v_ms: 0.94,
  candidates_screened: 847,
  cascade_risks: [
    { norad_id: 48274, name: 'ISS DEB-051',     object_type: 'DEBRIS',  risk_type: 'new',      miss_distance_km: 12.4, original_miss_km: null },
    { norad_id: 44713, name: 'STARLINK-5021',   object_type: 'PAYLOAD', risk_type: 'worsened', miss_distance_km: 3.1,  original_miss_km: 8.7  },
  ],
}

// ── Fetch maneuver options for a specific conjunction event ───────────────────
export async function fetchManeuvers(noradId, eventId) {
  const url = `${BASE_URL}/api/maneuvers/${noradId}/${eventId}`
  try {
    const res = await fetch(url)
    if (!res.ok) return { ..._MOCK_MANEUVERS, event_id: eventId }
    return res.json()
  } catch {
    return { ..._MOCK_MANEUVERS, event_id: eventId }
  }
}

// ── Fetch cascade analysis for a conjunction + maneuver ───────────────────────
// maneuverLabel: 'maximum_safety' | 'balanced' | 'fuel_efficient'
export async function fetchCascade(noradId, eventId, maneuverLabel = 'balanced') {
  const url = `${BASE_URL}/api/cascade/${noradId}/${eventId}/${maneuverLabel}`
  try {
    const res = await fetch(url)
    if (!res.ok) return { ..._MOCK_CASCADE, event_id: eventId, maneuver_label: maneuverLabel.replace(/_/g, ' ') }
    return res.json()
  } catch {
    return { ..._MOCK_CASCADE, event_id: eventId, maneuver_label: maneuverLabel.replace(/_/g, ' ') }
  }
}
