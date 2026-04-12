import { useState, useEffect } from 'react'
import { fetchCascade } from '../../api/shield'

const RISK_TYPE_COLOR = {
  new:      '#fbbf24',
  worsened: '#f87171',
}

const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH:     '#fb923c',
  MEDIUM:   '#fbbf24',
  LOW:      '#94a3b8',
}

function riskToSeverity(score) {
  if (score >= 80) return 'CRITICAL'
  if (score >= 60) return 'HIGH'
  if (score >= 35) return 'MEDIUM'
  return 'LOW'
}

export default function CascadeAnalysis({ conjunction, conjunctions = [], selectedManeuverLabel }) {
  const [cascadeData, setCascadeData] = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)

  useEffect(() => {
    if (!conjunction || !selectedManeuverLabel) {
      setCascadeData(null)
      return
    }
    let cancelled = false
    setCascadeData(null)
    setError(null)
    setLoading(true)

    fetchCascade(conjunction.primarySatId, conjunction.id, selectedManeuverLabel)
      .then(data => { if (!cancelled) setCascadeData(data) })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [conjunction?.id, selectedManeuverLabel])

  if (!conjunction) return null

  // Fleet-wide secondary conjunctions involving the same primary satellite
  const secondaryHits = conjunctions.filter(c =>
    c.id !== conjunction.id &&
    (c.primarySatId === conjunction.primarySatId || c.secondarySatId === conjunction.primarySatId)
  )

  const cascadeRisks = cascadeData?.cascade_risks ?? []

  return (
    <div style={{
      margin: '0 10px 12px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Cascade Analysis
        </span>
        <span style={{
          fontSize: 9, color: '#64748b',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 3, padding: '2px 6px',
        }}>
          Fleet Impact
        </span>
      </div>

      {/* Maneuver-induced cascade risks (from live API) */}
      {selectedManeuverLabel && (
        <div style={{ marginBottom: cascadeRisks.length > 0 || loading || error ? 10 : 0 }}>
          {loading && (
            <div style={{ fontSize: 11, color: '#475569', padding: '8px 0' }}>
              Computing cascade risks…
            </div>
          )}
          {error && (
            <div style={{ fontSize: 11, color: '#f87171', padding: '8px 0' }}>
              Cascade fetch failed: {error}
            </div>
          )}
          {!loading && !error && cascadeRisks.length > 0 && (
            <>
              <div style={{ fontSize: 10, color: '#fbbf24', fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ fontSize: 11 }}>⚠</span>
                Maneuver-induced secondary conjunctions
                {cascadeData && (
                  <span style={{ fontSize: 9, color: '#475569', fontWeight: 400, marginLeft: 4 }}>
                    ({cascadeData.candidates_screened} screened)
                  </span>
                )}
              </div>
              {cascadeRisks.map((cr, i) => {
                const typeColor = RISK_TYPE_COLOR[cr.risk_type] ?? '#94a3b8'
                return (
                  <div key={i} style={{
                    borderRadius: 4, padding: '8px 10px', marginBottom: 5,
                    background: `${typeColor}0d`,
                    border: `1px solid ${typeColor}30`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>
                        {cr.name || `NORAD ${cr.norad_id}`}
                      </span>
                      <span style={{
                        fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
                        color: typeColor, background: `${typeColor}18`,
                        borderRadius: 3, padding: '1px 5px', textTransform: 'uppercase',
                      }}>
                        {cr.risk_type}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 10, color: '#64748b' }}>
                        Miss <span style={{ color: typeColor, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                          {cr.miss_distance_km.toFixed(2)} km
                        </span>
                      </span>
                      {cr.original_miss_km !== null && (
                        <span style={{ fontSize: 10, color: '#64748b' }}>
                          was <span style={{ color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
                            {cr.original_miss_km.toFixed(2)} km
                          </span>
                        </span>
                      )}
                      <span style={{ fontSize: 10, color: '#64748b' }}>
                        {new Date(cr.tca_utc).toISOString().slice(11, 16)} UTC
                      </span>
                    </div>
                  </div>
                )
              })}
            </>
          )}
          {!loading && !error && cascadeRisks.length === 0 && cascadeData && (
            <div style={{ fontSize: 11, color: '#334155', padding: '4px 0 6px' }}>
              No cascade risks detected for this maneuver option.
            </div>
          )}
        </div>
      )}

      {/* Fleet-wide existing secondary events */}
      {secondaryHits.length > 0 ? (
        <div>
          <div style={{ fontSize: 10, color: '#475569', fontWeight: 600, marginBottom: 6, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
            Other active conjunctions — {conjunction.primarySatName}
          </div>
          {secondaryHits.map(c => {
            const severity = riskToSeverity(c.riskScore)
            const color    = SEVERITY_COLOR[severity]
            return (
              <div key={c.id} style={{
                borderRadius: 4, padding: '7px 10px', marginBottom: 4,
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500, marginBottom: 2 }}>
                    × {c.primarySatId === conjunction.primarySatId ? c.secondarySatName : c.primarySatName}
                  </div>
                  <div style={{ fontSize: 10, color: '#475569' }}>TCA {c.timeToTCA}</div>
                </div>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
                  color, background: `${color}15`,
                  borderRadius: 3, padding: '2px 6px',
                }}>
                  {severity}
                </span>
              </div>
            )
          })}
        </div>
      ) : (
        !selectedManeuverLabel && (
          <div style={{
            textAlign: 'center', padding: '16px 0',
            fontSize: 11, color: '#334155',
          }}>
            Select a maneuver option above to compute cascade risks
          </div>
        )
      )}

      {/* Summary footer */}
      <div style={{
        marginTop: 10, paddingTop: 8,
        borderTop: '1px solid rgba(255,255,255,0.05)',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 9, color: '#334155' }}>
          Fleet conjunctions total: {conjunctions.length}
        </span>
        <span style={{ fontSize: 9, color: '#334155' }}>
          Affecting this sat: {secondaryHits.length + 1}
        </span>
      </div>
    </div>
  )
}
