import { useState, useEffect } from 'react'

const BASE_URL = import.meta.env.VITE_SHIELD_API_URL ?? 'http://localhost:8000'
const DEFAULT_ROGUE_NORADS = [59773, 25544, 48274, 44713, 28190]

const SEV_COLOR = {
  ADVERSARIAL: '#ef4444',
  SUSPICIOUS:  '#f59e0b',
  NOMINAL:     '#22d3ee',
}

export default function RoguePanel({ visible, noradId = null }) {
  const [events, setEvents]   = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  // Re-fetch whenever the tracked satellite changes or the panel becomes visible
  useEffect(() => {
    if (!visible) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setEvents([])

    const url = (() => {
      if (!noradId) return `${BASE_URL}/api/rogue/events`
      const id = parseInt(noradId, 10)
      // If the tracked satellite is already in the default watch list, use the
      // default endpoint so all 5 adversarial watch satellites are included.
      if (DEFAULT_ROGUE_NORADS.includes(id)) return `${BASE_URL}/api/rogue/events`
      // Otherwise query the full default list plus the tracked satellite.
      const allIds = [...DEFAULT_ROGUE_NORADS, id]
      return `${BASE_URL}/api/rogue/events?${allIds.map(n => `norad_ids=${n}`).join('&')}`
    })()

    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(data => { if (!cancelled) setEvents(data) })
      .catch(err => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [visible, noradId])

  return (
    <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#94a3b8', textTransform: 'uppercase' }}>
          Rogue Intelligence
        </span>
        {!loading && events.length > 0 && (
          <span style={{ fontSize: 10, color: '#22d3ee' }}>
            {events.filter(e => e.severity !== 'NOMINAL').length} flagged
          </span>
        )}
      </div>

      {loading && (
        <div style={{ color: '#64748b', fontSize: 12, padding: '24px 0', textAlign: 'center' }}>
          Running anomaly pipeline...
        </div>
      )}

      {error && !loading && (
        <div style={{ color: '#ef4444', fontSize: 12, padding: '8px 0' }}>
          AI unreachable — {error}
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div style={{ color: '#64748b', fontSize: 12, padding: '24px 0', textAlign: 'center' }}>
          No suspicious or adversarial events detected.
        </div>
      )}

      {events.map((ev, i) => {
        const color = SEV_COLOR[ev.severity] ?? '#94a3b8'
        return (
          <div
            key={i}
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${color}33`,
              borderRadius: 8,
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {/* Top row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
                color, background: `${color}22`,
                border: `1px solid ${color}55`,
                borderRadius: 4, padding: '2px 7px',
              }}>
                {ev.severity}
              </span>
              <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>
                NORAD {ev.norad_id}
              </span>
              <span style={{ fontSize: 10, color: '#64748b', marginLeft: 'auto' }}>
                score {ev.composite_score?.toFixed(3)}
              </span>
            </div>

            {/* Epoch */}
            <div style={{ fontSize: 10, color: '#64748b' }}>
              {ev.epoch ? new Date(ev.epoch).toUTCString().replace('GMT', 'UTC') : ''}
            </div>

            {/* Summary (OpenAI) or fallback description */}
            {(ev.summary || ev.description) && (
              <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.5 }}>
                {ev.summary || ev.description}
              </div>
            )}

            {/* Anomalous feature pills */}
            {ev.anomalous_features?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {ev.anomalous_features.map(f => (
                  <span key={f} style={{
                    fontSize: 9, color: '#94a3b8',
                    background: 'rgba(148,163,184,0.1)',
                    border: '1px solid rgba(148,163,184,0.2)',
                    borderRadius: 3, padding: '1px 6px',
                  }}>
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
