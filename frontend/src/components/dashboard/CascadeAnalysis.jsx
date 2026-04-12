import { useState, useEffect } from 'react'
import { fetchCascade } from '../../api/shield'

const RISK_COLOR = {
  new:      '#f87171',
  worsened: '#fbbf24',
}

export default function CascadeAnalysis({ conjunction, selectedManeuver }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const noradId      = conjunction?.primarySatId
  const eventId      = conjunction?.id
  const maneuverSlug = selectedManeuver ?? 'balanced'

  useEffect(() => {
    if (!noradId || !eventId) return
    setLoading(true)
    setData(null)
    setError(null)
    fetchCascade(noradId, eventId, maneuverSlug)
      .then(d => setData(d))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [noradId, eventId, maneuverSlug])

  return (
    <div style={{
      margin: '0 10px 12px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Cascade Analysis
        </span>
        <span style={{
          fontSize: 9, color: '#64748b',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 3, padding: '2px 6px',
        }}>
          {data ? data.maneuver_label : maneuverSlug.replace(/_/g, ' ')}
        </span>
      </div>

      {loading && (
        <div style={{ fontSize: 11, color: '#64748b', textAlign: 'center', padding: '16px 0' }}>
          Running cascade simulation...
        </div>
      )}

      {error && !loading && (
        <div style={{ fontSize: 11, color: '#ef4444', padding: '8px 0' }}>
          Cascade failed — {error}
        </div>
      )}

      {data && !loading && (
        <>
          {data.cascade_risks?.length === 0 ? (
            <div style={{ fontSize: 11, color: '#334155', textAlign: 'center', padding: '16px 0' }}>
              No cascade risks detected for this maneuver.
            </div>
          ) : (
            <>
              <div style={{ fontSize: 10, color: '#fbbf24', fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
                <span>⚠</span>
                Maneuver-induced secondary conjunctions
              </div>
              {data.cascade_risks.map((cr, i) => {
                const color = RISK_COLOR[cr.risk_type] ?? '#94a3b8'
                return (
                  <div key={i} style={{
                    borderRadius: 4, padding: '8px 10px', marginBottom: 5,
                    background: `${color}0d`,
                    border: `1px solid ${color}30`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>
                        {cr.name || `NORAD ${cr.norad_id}`}
                      </span>
                      <span style={{
                        fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
                        color, background: `${color}18`,
                        borderRadius: 3, padding: '1px 5px', textTransform: 'uppercase',
                      }}>
                        {cr.risk_type}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 12 }}>
                      <span style={{ fontSize: 10, color: '#64748b' }}>
                        Miss <span style={{ color: color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                          {cr.miss_distance_km.toFixed(1)} km
                        </span>
                      </span>
                      {cr.original_miss_km != null && (
                        <span style={{ fontSize: 10, color: '#64748b' }}>
                          was {cr.original_miss_km.toFixed(1)} km
                        </span>
                      )}
                      <span style={{ fontSize: 10, color: '#64748b' }}>
                        {cr.object_type}
                      </span>
                    </div>
                  </div>
                )
              })}
            </>
          )}

          <div style={{
            marginTop: 10, paddingTop: 8,
            borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 9, color: '#334155' }}>
              ΔV: {data.delta_v_ms?.toFixed(3)} m/s
            </span>
            <span style={{ fontSize: 9, color: '#334155' }}>
              Screened: {data.candidates_screened} objects
            </span>
          </div>
        </>
      )}
    </div>
  )
}
