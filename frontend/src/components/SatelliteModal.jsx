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

export default function SatelliteModal({ sat, onClose }) {
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
