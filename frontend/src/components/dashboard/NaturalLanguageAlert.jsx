import { naturalLanguageAlerts } from '../../data/mockData'

const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH: '#fb923c',
  MEDIUM: '#fbbf24',
  LOW: '#94a3b8',
}

export default function NaturalLanguageAlert({ conjunction }) {
  const alert = naturalLanguageAlerts.find(a => a.conjunctionId === conjunction.id)
  if (!alert) return null

  const color = SEVERITY_COLOR[alert.severity] ?? '#94a3b8'
  const ts = new Date(alert.timestamp).toISOString().slice(11, 16) + ' UTC'

  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: `${color}0d`,
      border: `1px solid ${color}33`,
      padding: '12px 14px',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Claude icon placeholder */}
          <div style={{
            width: 20, height: 20, borderRadius: 4,
            background: 'rgba(192, 132, 252, 0.2)',
            border: '1px solid rgba(192, 132, 252, 0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, color: '#c084fc', fontWeight: 700, flexShrink: 0,
          }}>
            AI
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', lineHeight: 1.3 }}>
            {alert.headline}
          </span>
        </div>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
          color, background: `${color}18`,
          borderRadius: 3, padding: '2px 5px', flexShrink: 0,
        }}>
          {alert.severity}
        </span>
      </div>

      {/* Summary */}
      <p style={{
        fontSize: 11, color: '#94a3b8', lineHeight: 1.6,
        margin: 0, marginBottom: 10,
      }}>
        {alert.summary}
      </p>

      {/* Recommended action */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'rgba(34, 211, 238, 0.06)',
        border: '1px solid rgba(34, 211, 238, 0.18)',
        borderRadius: 4, padding: '7px 10px',
      }}>
        <span style={{ fontSize: 9, color: '#22d3ee', fontWeight: 700, letterSpacing: '0.1em', flexShrink: 0 }}>
          ACTION
        </span>
        <span style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 500 }}>
          {alert.recommendedAction}
        </span>
      </div>

      {/* Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        <span style={{ fontSize: 9, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Audience: {alert.audienceLevel}
        </span>
        <span style={{ fontSize: 9, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>{ts}</span>
      </div>
    </div>
  )
}
