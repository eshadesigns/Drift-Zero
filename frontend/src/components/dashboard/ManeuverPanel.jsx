import { useState, useEffect } from 'react'
import { fetchManeuvers } from '../../api/shield'

const OPTION_STYLES = [
  { id: 'A', base: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.25)' },
  { id: 'B', base: '#22d3ee', bg: 'rgba(34,211,238,0.08)',  border: 'rgba(34,211,238,0.25)'  },
  { id: 'C', base: '#86efac', bg: 'rgba(134,239,172,0.08)', border: 'rgba(134,239,172,0.25)' },
]

const LABEL_TO_SLUG = {
  'Maximum Safety': 'maximum_safety',
  'Balanced':       'balanced',
  'Fuel Efficient': 'fuel_efficient',
}

function fmtCost(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}

export default function ManeuverPanel({ conjunction, onSelectManeuver }) {
  const [options, setOptions]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [selected, setSelected] = useState(null)

  const noradId = conjunction?.primarySatId
  const eventId = conjunction?.id

  useEffect(() => {
    if (!noradId || !eventId) return
    setLoading(true)
    setOptions(null)
    setError(null)
    setSelected(null)
    fetchManeuvers(noradId, eventId)
      .then(data => setOptions(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [noradId, eventId])

  if (loading) return (
    <div style={{ margin: '0 10px 6px', padding: '16px', fontSize: 11, color: '#64748b', textAlign: 'center' }}>
      Computing maneuver options...
    </div>
  )

  if (error) return (
    <div style={{ margin: '0 10px 6px', padding: '12px', fontSize: 11, color: '#ef4444' }}>
      Maneuver compute failed — {error}
    </div>
  )

  if (!options) return null

  const handleSelect = (opt, styleId) => {
    const isSelected = selected === styleId
    const next = isSelected ? null : styleId
    setSelected(next)
    onSelectManeuver?.(next ? LABEL_TO_SLUG[opt.label] : null)
  }

  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Maneuver Options
        </span>
        <span style={{ fontSize: 10, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          current miss {options.current_miss_km?.toFixed(1)} km
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {options.maneuver_options.map((opt, i) => {
          const c = OPTION_STYLES[i]
          const isSelected = selected === c.id
          return (
            <div
              key={c.id}
              onClick={() => handleSelect(opt, c.id)}
              style={{
                borderRadius: 5,
                background: isSelected ? c.bg : 'rgba(255,255,255,0.02)',
                border: `1px solid ${isSelected ? c.border : 'rgba(255,255,255,0.06)'}`,
                padding: '9px 11px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: c.base, background: `${c.base}18`,
                    borderRadius: 3, padding: '1px 6px', letterSpacing: '0.06em',
                  }}>
                    {c.id}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                    {opt.label}
                  </span>
                </div>
                <span style={{ fontSize: 13, fontWeight: 700, color: c.base }}>
                  +{opt.miss_increase_km} km
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px 8px' }}>
                <Metric label="ΔV"        value={`${opt.delta_v_ms.toFixed(2)} m/s`} />
                <Metric label="Fuel"      value={`${opt.fuel_kg.toFixed(3)} kg`} />
                <Metric label="Cost"      value={fmtCost(opt.fuel_cost_usd)} />
                <Metric label="Lifespan−" value={`${opt.lifespan_reduction_days.toFixed(1)}d`} />
                <Metric label="Score"     value={`${(opt.composite_score * 100).toFixed(0)}%`} />
              </div>

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
                    alert(
                      `Maneuver Option ${c.id} — ${opt.label}\n` +
                      `ΔV: ${opt.delta_v_ms.toFixed(2)} m/s | Fuel: ${opt.fuel_kg.toFixed(3)} kg\n` +
                      `Cost: ${fmtCost(opt.fuel_cost_usd)} | Lifespan −${opt.lifespan_reduction_days.toFixed(1)}d\n\n` +
                      `(Demo — no uplink connected)`
                    )
                  }}
                >
                  Execute Option {c.id}
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
