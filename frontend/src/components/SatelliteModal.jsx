import { useEffect } from 'react'

const TYPE_BADGE = {
  satellite: { label: 'ACTIVE SAT', color: '#22d3ee', bg: 'rgba(34,211,238,0.10)' },
  debris:    { label: 'DEBRIS',     color: '#fb923c', bg: 'rgba(251,146,60,0.10)'  },
}

const STAT_ROWS = [
  { key: 'noradId',     label: 'NORAD ID'                },
  { key: 'alt',         label: 'Altitude',    unit: ' km'  },
  { key: 'velocity',    label: 'Velocity',    unit: ' km/s'},
  { key: 'inclination', label: 'Inclination', unit: '°'   },
  { key: 'period',      label: 'Period',      unit: ' min' },
  { key: 'country',     label: 'Origin'                   },
  { key: 'launched',    label: 'Launch Date'              },
]

const FONT = "ui-monospace, 'SF Mono', Consolas, monospace"

export default function SatelliteModal({ sat, onClose, onAnalyze, analyzed = false, riskCount = 0 }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!sat) return null

  const badge = TYPE_BADGE[sat.type] ?? TYPE_BADGE.debris

  return (
    <>
      {/* Dim overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.45)',
          zIndex: 100,
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Panel */}
      <aside style={{
        position: 'fixed',
        top: 0, right: 0,
        height: '100%',
        width: 'min(380px, 100vw)',
        zIndex: 101,
        background: 'rgba(3, 7, 18, 0.97)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderLeft: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '-16px 0 48px rgba(0,0,0,0.6)',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: FONT,
        color: '#e2e8f0',
        overflowY: 'auto',
        animation: 'slideInRight 0.25s cubic-bezier(0.22,1,0.36,1)',
      }}>

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          padding: '16px 16px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          gap: 10,
        }}>
          <div>
            <span style={{
              display: 'inline-block',
              fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
              color: badge.color,
              background: badge.bg,
              border: `1px solid ${badge.color}33`,
              borderRadius: 3,
              padding: '2px 7px',
              marginBottom: 7,
            }}>
              {badge.label}
            </span>
            <h2 style={{
              margin: 0,
              fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em',
              color: '#e2e8f0', lineHeight: 1.25,
              fontFamily: FONT,
            }}>
              {sat.name}
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              flexShrink: 0,
              width: 28, height: 28,
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 5,
              background: 'rgba(255,255,255,0.04)',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: 14, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s, color 0.15s',
              fontFamily: FONT,
            }}
            onMouseEnter={e => { e.currentTarget.style.background='rgba(255,255,255,0.09)'; e.currentTarget.style.color='#e2e8f0' }}
            onMouseLeave={e => { e.currentTarget.style.background='rgba(255,255,255,0.04)'; e.currentTarget.style.color='#64748b' }}
          >
            ✕
          </button>
        </div>

        {/* ── Description ────────────────────────────────────────────────────── */}
        {sat.description && (
          <p style={{
            margin: 0,
            padding: '12px 16px',
            fontSize: 11, lineHeight: 1.6,
            color: '#64748b',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            {sat.description}
          </p>
        )}

        {/* ── Orbital Parameters ──────────────────────────────────────────────── */}
        <div style={{ padding: '14px 10px', flexGrow: 1 }}>
          <p style={{
            margin: '0 6px 10px',
            fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
            color: '#475569', textTransform: 'uppercase',
          }}>
            Orbital Parameters
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {STAT_ROWS.map(({ key, label, unit = '' }) => (
              sat[key] != null && (
                <div key={key} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px',
                  borderRadius: 5,
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <span style={{ fontSize: 11, color: '#475569', fontWeight: 500 }}>
                    {label}
                  </span>
                  <span style={{
                    fontSize: 13, fontWeight: 700, color: '#e2e8f0',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {sat[key]}{unit}
                  </span>
                </div>
              )
            ))}
          </div>
        </div>

        {/* ── Trajectory Analysis ─────────────────────────────────────────────── */}
        {sat.type === 'satellite' && (
          <div style={{ padding: '0 10px 10px' }}>
            <p style={{
              margin: '0 6px 8px',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
              color: '#475569', textTransform: 'uppercase',
            }}>
              Trajectory Analysis
            </p>

            {!analyzed ? (
              <button
                onClick={onAnalyze}
                style={{
                  width: '100%', padding: '10px 0',
                  border: '1px solid rgba(34,211,238,0.25)',
                  borderRadius: 5,
                  background: 'rgba(34,211,238,0.07)',
                  color: '#22d3ee',
                  cursor: 'pointer',
                  fontFamily: FONT,
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  transition: 'background 0.15s, border-color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background='rgba(34,211,238,0.13)'; e.currentTarget.style.borderColor='rgba(34,211,238,0.45)' }}
                onMouseLeave={e => { e.currentTarget.style.background='rgba(34,211,238,0.07)'; e.currentTarget.style.borderColor='rgba(34,211,238,0.25)' }}
              >
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.5" stroke="#22d3ee" strokeWidth="1.3" strokeDasharray="3 2"/>
                  <circle cx="7" cy="7" r="1.5" fill="#22d3ee"/>
                  <circle cx="11" cy="4" r="1" fill="#22d3ee"/>
                </svg>
                Analyze Trajectory
              </button>
            ) : (
              <>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px', borderRadius: 5,
                  background: riskCount > 0 ? 'rgba(248,113,113,0.08)' : 'rgba(134,239,172,0.08)',
                  border: `1px solid ${riskCount > 0 ? 'rgba(248,113,113,0.25)' : 'rgba(134,239,172,0.2)'}`,
                }}>
                  <span style={{
                    fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1,
                    color: riskCount > 0 ? '#f87171' : '#86efac',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {riskCount}
                  </span>
                  <span style={{
                    fontSize: 11, fontWeight: 500, lineHeight: 1.4,
                    color: riskCount > 0 ? '#f87171' : '#86efac',
                  }}>
                    {riskCount > 0
                      ? `object${riskCount !== 1 ? 's' : ''} within 700 km of orbital path`
                      : 'No close approaches detected'}
                  </span>
                </div>
                {riskCount > 0 && (
                  <p style={{ margin: '7px 2px 0', fontSize: 10, color: '#334155', lineHeight: 1.5 }}>
                    Risk objects marked with red rings on the globe.
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Status ─────────────────────────────────────────────────────────── */}
        <div style={{ padding: '0 10px 16px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 12px',
            borderRadius: 5,
            background: sat.status === 'Active' ? 'rgba(134,239,172,0.07)' : 'rgba(251,146,60,0.07)',
            border: `1px solid ${sat.status === 'Active' ? 'rgba(134,239,172,0.18)' : 'rgba(251,146,60,0.18)'}`,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: sat.status === 'Active' ? '#22c55e' : '#f97316',
              boxShadow: `0 0 5px ${sat.status === 'Active' ? '#22c55e' : '#f97316'}`,
            }} />
            <span style={{
              fontSize: 11, fontWeight: 600,
              color: sat.status === 'Active' ? '#86efac' : '#fdba74',
            }}>
              {sat.status}
            </span>
          </div>
        </div>

      </aside>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </>
  )
}
