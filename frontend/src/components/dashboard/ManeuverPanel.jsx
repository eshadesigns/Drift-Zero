import { useState, useEffect } from 'react'
import { fetchManeuvers } from '../../api/shield'

// Position 0 = highest composite_score, maps to colour slot A, B, C
const OPTION_COLORS = [
  { base: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.25)' },
  { base: '#22d3ee', bg: 'rgba(34,211,238,0.08)',  border: 'rgba(34,211,238,0.25)'  },
  { base: '#86efac', bg: 'rgba(134,239,172,0.08)', border: 'rgba(134,239,172,0.25)' },
]

const OPTION_IDS = ['A', 'B', 'C']

function labelToSlug(label) {
  return label.toLowerCase().replace(/\s+/g, '_')
}

function formatCost(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n}`
}

export default function ManeuverPanel({ conjunction, onManeuverSelect }) {
  const [maneuverData, setManeuverData] = useState(null)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(null)
  const [selected, setSelected]         = useState(null)

  useEffect(() => {
    if (!conjunction) return
    let cancelled = false
    setManeuverData(null)
    setError(null)
    setSelected(null)
    onManeuverSelect?.(null)
    setLoading(true)

    fetchManeuvers(conjunction.primarySatId, conjunction.id)
      .then(data => {
        if (!cancelled) setManeuverData(data)
      })
      .catch(err => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [conjunction?.id])

  const options = maneuverData?.maneuver_options ?? null

  if (!conjunction) return null

  if (loading) return (
    <div style={{ margin: '0 10px 6px', padding: '16px', fontSize: 11, color: '#475569', textAlign: 'center' }}>
      Loading maneuver options…
    </div>
  )

  if (error) return (
    <div style={{ margin: '0 10px 6px', padding: '12px 14px', borderRadius: 6,
      background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)',
      fontSize: 11, color: '#f87171' }}>
      Maneuver fetch failed: {error}
    </div>
  )

  if (!options || options.length === 0) return null

  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Maneuver Options
        </span>
        <span style={{ fontSize: 10, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          current miss {maneuverData?.current_miss_km?.toFixed(2)} km
        </span>
      </div>

      {/* Options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {options.map((opt, idx) => {
          const c        = OPTION_COLORS[idx] ?? OPTION_COLORS[2]
          const optId    = OPTION_IDS[idx] ?? String(idx + 1)
          const slug     = labelToSlug(opt.label)
          const isSelected = selected === idx

          return (
            <div
              key={opt.label}
              onClick={() => {
                const next = isSelected ? null : idx
                setSelected(next)
                onManeuverSelect?.(next === null ? null : slug)
              }}
              style={{
                borderRadius: 5,
                background: isSelected ? c.bg : 'rgba(255,255,255,0.02)',
                border: `1px solid ${isSelected ? c.border : 'rgba(255,255,255,0.06)'}`,
                padding: '9px 11px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {/* Option header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: c.base, background: `${c.base}18`,
                    borderRadius: 3, padding: '1px 6px', letterSpacing: '0.06em',
                  }}>
                    {optId}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                    {opt.label}
                  </span>
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: c.base, fontVariantNumeric: 'tabular-nums' }}>
                  +{opt.miss_increase_km} km
                </span>
              </div>

              {/* Metrics grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px 8px' }}>
                <Metric label="ΔV"         value={`${opt.delta_v_ms} m/s`} />
                <Metric label="Fuel"        value={`${opt.fuel_kg} kg`} />
                <Metric label="Cost"        value={formatCost(opt.fuel_cost_usd)} />
                <Metric label="Lifespan −"  value={`${opt.lifespan_reduction_days}d`} />
                <Metric label="Score"       value={opt.composite_score.toFixed(2)} />
              </div>

              {/* Execute button (only when selected) */}
              {isSelected && (
                <button
                  style={{
                    marginTop: 10, width: '100%',
                    padding: '8px 0', borderRadius: 4,
                    background: c.bg, border: `1px solid ${c.border}`,
                    color: c.base, fontSize: 11, fontWeight: 700,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    cursor: 'pointer',
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    alert(`Maneuver Option ${optId} — ${opt.label}\nΔV: ${opt.delta_v_ms} m/s | Fuel: ${opt.fuel_kg} kg\nCost: ${formatCost(opt.fuel_cost_usd)}\n\n(Demo — no backend connected)`)
                  }}
                >
                  Execute Option {optId}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontSize: 9, color: '#334155', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </div>
  )
}
