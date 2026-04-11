import { useState } from 'react'
import { maneuvers } from '../../data/mockData'

const OPTION_COLORS = {
  A: { base: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.25)' },
  B: { base: '#22d3ee', bg: 'rgba(34,211,238,0.08)', border: 'rgba(34,211,238,0.25)' },
  C: { base: '#86efac', bg: 'rgba(134,239,172,0.08)', border: 'rgba(134,239,172,0.25)' },
}

function formatCost(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n}`
}

function formatProb(p) {
  return p.toExponential(2)
}

export default function ManeuverPanel({ conjunction }) {
  const entry = maneuvers.find(m => m.conjunctionId === conjunction.id)
  const [selected, setSelected] = useState(null)

  if (!entry) return null

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
          {conjunction.id.slice(-3)}
        </span>
      </div>

      {/* Options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entry.options.map((opt) => {
          const c = OPTION_COLORS[opt.id]
          const isSelected = selected === opt.id
          return (
            <div
              key={opt.id}
              onClick={() => setSelected(isSelected ? null : opt.id)}
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
                    {opt.id}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                    {opt.label}
                  </span>
                  {opt.cascadeRiskCreated && (
                    <span style={{
                      fontSize: 9, color: '#fbbf24',
                      background: 'rgba(251,191,36,0.12)',
                      borderRadius: 3, padding: '1px 5px', letterSpacing: '0.06em',
                    }}>
                      CASCADE
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 13, fontWeight: 700, color: c.base }}>
                  {opt.riskReductionPct}%
                </span>
              </div>

              {/* Metrics grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px 8px' }}>
                <Metric label="ΔV" value={`${opt.deltaVms} m/s`} />
                <Metric label="Fuel" value={`${opt.fuelKg} kg`} />
                <Metric label="Cost" value={formatCost(opt.costUSD)} />
                <Metric label="New P(c)" value={formatProb(opt.newProbability)} />
                <Metric label="Lifespan −" value={`${opt.lifespanImpactDays}d`} />
                <Metric label="Window" value={`${opt.executionWindowMin}m`} />
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
                    alert(`Maneuver Option ${opt.id} — ${opt.label}\nΔV: ${opt.deltaVms} m/s | Fuel: ${opt.fuelKg} kg\nCost: ${formatCost(opt.costUSD)}\n\n(Demo — no backend connected)`)
                  }}
                >
                  Execute Option {opt.id}
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
