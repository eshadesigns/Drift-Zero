import { useEffect } from 'react'

const TYPE_BADGE = {
  satellite: { label: 'ACTIVE SAT', color: '#8dd8ff', bg: 'rgba(141,216,255,0.12)' },
  debris:    { label: 'DEBRIS',     color: '#f97316', bg: 'rgba(249,115,22,0.12)'  },
}

const STAT_ROWS = [
  { key: 'noradId',     label: 'NORAD ID'       },
  { key: 'alt',         label: 'Altitude',    unit: ' km'  },
  { key: 'velocity',    label: 'Velocity',    unit: ' km/s'},
  { key: 'inclination', label: 'Inclination', unit: '°'   },
  { key: 'period',      label: 'Period',      unit: ' min' },
  { key: 'country',     label: 'Origin'               },
  { key: 'launched',    label: 'Launch Date'          },
]

export default function SatelliteModal({ sat, onClose, onAnalyze, analyzed = false, riskCount = 0 }) {
  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!sat) return null

  const badge = TYPE_BADGE[sat.type] ?? TYPE_BADGE.debris

  return (
    <>
      {/* Dim overlay (click to close) */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.35)',
          zIndex: 10,
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Panel */}
      <aside
        style={{
          position: 'fixed',
          top: 0, right: 0,
          height: '100%',
          width: 'min(400px, 100vw)',
          zIndex: 11,
          background: 'linear-gradient(180deg, rgba(10,18,32,0.97) 0%, rgba(6,12,22,0.97) 100%)',
          borderLeft: '1px solid rgba(255,255,255,0.10)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          boxShadow: '-20px 0 80px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          fontFamily: "'Manrope', 'Space Grotesk', system-ui, sans-serif",
          color: '#f4f7fb',
          overflowY: 'auto',
          animation: 'slideInRight 0.28s cubic-bezier(0.22,1,0.36,1)',
        }}
      >
        {/* Header bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '20px 22px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          gap: 12,
        }}>
          <div>
            <span style={{
              display: 'inline-block',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
              color: badge.color,
              background: badge.bg,
              border: `1px solid ${badge.color}33`,
              borderRadius: 4,
              padding: '2px 8px',
              marginBottom: 8,
            }}>
              {badge.label}
            </span>
            <h2 style={{
              margin: 0,
              fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em',
              color: '#f4f7fb',
              lineHeight: 1.2,
            }}>
              {sat.name}
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              flexShrink: 0,
              width: 34, height: 34,
              border: '1px solid rgba(255,255,255,0.14)',
              borderRadius: 8,
              background: 'rgba(255,255,255,0.06)',
              color: 'rgba(244,247,251,0.7)',
              cursor: 'pointer',
              fontSize: 18, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.12)'
              e.currentTarget.style.color = '#f4f7fb'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
              e.currentTarget.style.color = 'rgba(244,247,251,0.7)'
            }}
          >
            ✕
          </button>
        </div>

        {/* Description */}
        {sat.description && (
          <p style={{
            margin: 0,
            padding: '14px 22px',
            fontSize: 13, lineHeight: 1.6,
            color: 'rgba(244,247,251,0.6)',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            {sat.description}
          </p>
        )}

        {/* Orbital stats */}
        <div style={{ padding: '18px 22px', flexGrow: 1 }}>
          <p style={{
            margin: '0 0 14px',
            fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
            color: 'rgba(244,247,251,0.38)',
            textTransform: 'uppercase',
          }}>
            Orbital Parameters
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {STAT_ROWS.map(({ key, label, unit = '' }) => (
              sat[key] != null && (
                <div
                  key={key}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 14px',
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.05)',
                  }}
                >
                  <span style={{ fontSize: 12, color: 'rgba(244,247,251,0.5)', fontWeight: 500 }}>
                    {label}
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#f4f7fb', letterSpacing: '-0.01em' }}>
                    {sat[key]}{unit}
                  </span>
                </div>
              )
            ))}
          </div>
        </div>

        {/* Trajectory analysis — satellites only */}
        {sat.type === 'satellite' && (
          <div style={{ padding: '0 22px 14px' }}>
            <p style={{
              margin: '0 0 10px',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
              color: 'rgba(244,247,251,0.38)', textTransform: 'uppercase',
            }}>
              Trajectory Analysis
            </p>

            {!analyzed ? (
              /* ── Analyze button ── */
              <button
                onClick={onAnalyze}
                style={{
                  width: '100%', padding: '11px 0',
                  border: '1px solid rgba(141,216,255,0.3)',
                  borderRadius: 10,
                  background: 'rgba(141,216,255,0.07)',
                  color: '#8dd8ff',
                  cursor: 'pointer', fontFamily: 'inherit',
                  fontSize: 12, fontWeight: 700, letterSpacing: '0.04em',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  transition: 'background 0.15s, border-color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background='rgba(141,216,255,0.14)'; e.currentTarget.style.borderColor='rgba(141,216,255,0.55)' }}
                onMouseLeave={e => { e.currentTarget.style.background='rgba(141,216,255,0.07)'; e.currentTarget.style.borderColor='rgba(141,216,255,0.3)' }}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.5" stroke="#8dd8ff" strokeWidth="1.3" strokeDasharray="3 2"/>
                  <circle cx="7" cy="7" r="1.5" fill="#8dd8ff"/>
                  <circle cx="11" cy="4" r="1" fill="#8dd8ff"/>
                </svg>
                Analyze Trajectory
              </button>
            ) : (
              /* ── Risk results ── */
              <>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '12px 14px', borderRadius: 10,
                  background: riskCount > 0 ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
                  border: `1px solid ${riskCount > 0 ? 'rgba(239,68,68,0.25)' : 'rgba(34,197,94,0.2)'}`,
                }}>
                  <span style={{
                    fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1,
                    color: riskCount > 0 ? '#f87171' : '#86efac',
                  }}>
                    {riskCount}
                  </span>
                  <span style={{
                    fontSize: 12, fontWeight: 500, lineHeight: 1.4,
                    color: riskCount > 0 ? 'rgba(248,113,113,0.85)' : 'rgba(134,239,172,0.85)',
                  }}>
                    {riskCount > 0
                      ? `object${riskCount !== 1 ? 's' : ''} within 700 km of orbital path`
                      : 'No close approaches detected'}
                  </span>
                </div>
                {riskCount > 0 && (
                  <p style={{ margin: '8px 0 0', fontSize: 11, color: 'rgba(244,247,251,0.35)', lineHeight: 1.5 }}>
                    Risk objects marked with red rings on the globe. Pan freely to explore.
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* Status pill */}
        <div style={{ padding: '0 22px 24px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '12px 14px',
            borderRadius: 10,
            background: sat.status === 'Active'
              ? 'rgba(34,197,94,0.08)'
              : 'rgba(249,115,22,0.08)',
            border: `1px solid ${sat.status === 'Active' ? 'rgba(34,197,94,0.2)' : 'rgba(249,115,22,0.2)'}`,
          }}>
            <span style={{
              width: 7, height: 7,
              borderRadius: '50%',
              background: sat.status === 'Active' ? '#22c55e' : '#f97316',
              boxShadow: `0 0 6px ${sat.status === 'Active' ? '#22c55e' : '#f97316'}`,
              flexShrink: 0,
            }} />
            <span style={{
              fontSize: 12, fontWeight: 600,
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
          to   { transform: translateX(0);   opacity: 1; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </>
  )
}
