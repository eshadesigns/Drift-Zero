import { useState, useEffect } from 'react'

const BASE_URL = import.meta.env.VITE_SHIELD_API_URL ?? 'http://localhost:8000'

const SEVERITY = {
  ADVERSARIAL: { color: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.18)' },
  SUSPICIOUS:  { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)',  border: 'rgba(251,191,36,0.18)'  },
  ROUTINE:     { color: '#4ade80', bg: 'rgba(74,222,128,0.06)',  border: 'rgba(74,222,128,0.14)'  },
}

function severityStyle(s) {
  return SEVERITY[s] ?? SEVERITY.ROUTINE
}

export default function RoguePanel() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch(`${BASE_URL}/api/rogue/events`)
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const data = await res.json()
        if (!cancelled) {
          setEvents(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  const adversarialCount = events.filter(e => e.severity === 'ADVERSARIAL').length

  return (
    <div style={{ padding: '12px 0 4px' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
          color: '#475569', textTransform: 'uppercase',
        }}>
          Anomaly Events
        </span>
        {adversarialCount > 0 && (
          <span style={{
            fontSize: 10, fontWeight: 600, color: '#f87171',
            background: 'rgba(248,113,113,0.12)', borderRadius: 10,
            padding: '2px 8px', letterSpacing: '0.05em',
          }}>
            {adversarialCount} ADVERSARIAL
          </span>
        )}
      </div>

      {/* Body */}
      {loading && (
        <div style={{ padding: '24px 16px', textAlign: 'center', fontSize: 11, color: '#334155' }}>
          Analysing orbital behaviour...
        </div>
      )}

      {!loading && error && (
        <div style={{
          margin: '10px', padding: '12px 14px', borderRadius: 6,
          background: 'rgba(248,113,113,0.06)',
          border: '1px solid rgba(248,113,113,0.18)',
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#f87171', marginBottom: 4, letterSpacing: '0.08em' }}>
            API UNREACHABLE
          </div>
          <div style={{ fontSize: 11, color: '#64748b' }}>{error}</div>
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div style={{ padding: '24px 16px', textAlign: 'center', fontSize: 11, color: '#334155' }}>
          No anomalous events detected
        </div>
      )}

      {!loading && !error && events.map((ev, i) => {
        const s = severityStyle(ev.severity)
        const score = Math.round((ev.composite_score ?? 0) * 100)

        return (
          <div
            key={`${ev.norad_id}-${i}`}
            style={{
              margin: '6px 10px',
              padding: '10px 12px',
              borderRadius: 6,
              background: s.bg,
              border: `1px solid ${s.border}`,
            }}
          >
            {/* Top row — NORAD ID, severity badge, score */}
            <div style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', marginBottom: 5,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                  color: s.color, background: `${s.color}18`,
                  borderRadius: 3, padding: '1px 5px',
                }}>
                  {ev.severity}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, color: '#e2e8f0',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  NORAD {ev.norad_id}
                </span>
              </div>
              {/* Composite score 0–100 */}
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: score > 72 ? '#f87171' : score > 50 ? '#fbbf24' : '#4ade80',
                fontVariantNumeric: 'tabular-nums',
              }}>
                {score}
              </span>
            </div>

            {/* Epoch */}
            {ev.epoch && (
              <div style={{ fontSize: 9, color: '#475569', marginBottom: 5, fontVariantNumeric: 'tabular-nums' }}>
                {String(ev.epoch).slice(0, 19).replace('T', ' ')} UTC
              </div>
            )}

            {/* Description */}
            <div style={{
              fontSize: 11, color: '#94a3b8', lineHeight: 1.5,
              wordBreak: 'break-word',
            }}>
              {ev.summary ?? ev.description}
            </div>

            {/* Anomalous features */}
            {ev.anomalous_features?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 7 }}>
                {ev.anomalous_features.map(f => (
                  <span
                    key={f}
                    style={{
                      fontSize: 9, color: '#64748b',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: 3, padding: '1px 5px',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
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
