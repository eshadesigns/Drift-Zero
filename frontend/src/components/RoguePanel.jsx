import { useState, useEffect } from 'react'
import { mockRogueEvents } from '../data/mockData'

const BASE_URL = import.meta.env.VITE_SHIELD_API_URL ?? 'http://localhost:8000'

const SEV_COLOR = {
  ADVERSARIAL: '#ef4444',
  SUSPICIOUS:  '#f59e0b',
  NOMINAL:     '#22d3ee',
}

export default function RoguePanel({ visible, demo = false, focusedSatId = null }) {
  const [events, setEvents]   = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [fetched, setFetched] = useState(false)

  // In demo mode, derive events from mock data keyed by focusedSatId
  useEffect(() => {
    if (!demo) return
    if (focusedSatId && mockRogueEvents[focusedSatId]) {
      setEvents(mockRogueEvents[focusedSatId])
    } else {
      setEvents([])
    }
    setFetched(true)
    setLoading(false)
    setError(null)
  }, [demo, focusedSatId])

  // Live API fetch (only when not demo)
  useEffect(() => {
    if (demo || !visible || fetched) return
    setLoading(true)
    fetch(`${BASE_URL}/api/rogue/events`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(data => {
        setEvents(data)
        setFetched(true)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [visible, fetched, demo])

  const flaggedCount = events.filter(e => e.severity !== 'NOMINAL').length

  return (
    <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#94a3b8', textTransform: 'uppercase' }}>
          Rogue Intelligence
        </span>
        {fetched && !loading && (
          <span style={{ fontSize: 10, color: flaggedCount > 0 ? '#ef4444' : '#22d3ee' }}>
            {flaggedCount > 0 ? `${flaggedCount} flagged` : 'nominal'}
          </span>
        )}
      </div>

      {/* Focused satellite label */}
      {focusedSatId && (
        <div style={{
          fontSize: 10, color: '#475569', fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
          letterSpacing: '0.06em', marginBottom: 2,
        }}>
          ANALYZING: <span style={{ color: '#64748b' }}>{focusedSatId}</span>
        </div>
      )}

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

      {!loading && !error && fetched && events.length === 0 && (
        <div style={{ color: '#334155', fontSize: 12, padding: '24px 0', textAlign: 'center', lineHeight: 1.6 }}>
          No suspicious or adversarial objects<br />detected near {focusedSatId ?? 'this satellite'}.
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
                color, background: `${color}22`,
                border: `1px solid ${color}55`,
                borderRadius: 4, padding: '2px 7px',
                flexShrink: 0,
              }}>
                {ev.severity}
              </span>
              <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>
                {ev.name ?? `NORAD ${ev.norad_id}`}
              </span>
              <span style={{ fontSize: 10, color: '#64748b', marginLeft: 'auto' }}>
                score {ev.composite_score?.toFixed(3)}
              </span>
            </div>

            {/* Epoch */}
            <div style={{ fontSize: 10, color: '#475569' }}>
              {ev.epoch ? new Date(ev.epoch).toUTCString().replace('GMT', 'UTC') : ''}
              {ev.norad_id && <span style={{ marginLeft: 8, color: '#334155' }}>NORAD {ev.norad_id}</span>}
            </div>

            {/* Summary */}
            {(ev.summary || ev.description) && (
              <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.55 }}>
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
                    {f.replace(/_/g, ' ')}
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
