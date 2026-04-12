const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH:     '#fb923c',
  MEDIUM:   '#fbbf24',
  LOW:      '#94a3b8',
}

const PLACEHOLDER_SUMMARY =
  'Select a conjunction event to generate an AI threat assessment.'

export default function NaturalLanguageAlert({ conjunction }) {
  if (!conjunction) return null

  const summaryRaw = conjunction.summary
  const hasSummary =
    typeof summaryRaw === 'string' && summaryRaw.trim().length > 0
  const summary    = hasSummary ? summaryRaw.trim() : PLACEHOLDER_SUMMARY
  const severity   = conjunction.severity ?? 'LOW'
  const color      = SEVERITY_COLOR[severity] ?? '#94a3b8'

  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: `${color}0d`,
      border: `1px solid ${color}33`,
      padding: '12px 14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <div style={{
          width: 20, height: 20, borderRadius: 4,
          background: 'rgba(192, 132, 252, 0.2)',
          border: '1px solid rgba(192, 132, 252, 0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, color: '#c084fc', fontWeight: 700, flexShrink: 0,
        }}>
          AI
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', flex: 1, lineHeight: 1.3 }}>
          Threat Assessment
        </span>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
          color, background: `${color}18`,
          borderRadius: 3, padding: '2px 5px', flexShrink: 0,
        }}>
          {severity}
        </span>
      </div>

      {/* Summary — placeholder when API/LLM did not return text */}
      <p style={{
        fontSize: 11,
        color: hasSummary ? '#94a3b8' : '#64748b',
        fontStyle: hasSummary ? 'normal' : 'italic',
        lineHeight: 1.6,
        margin: 0, marginBottom: 10,
      }}>
        {summary}
      </p>

      {/* Key metrics row */}
      <div style={{
        display: 'flex', gap: 12,
        background: 'rgba(34,211,238,0.06)',
        border: '1px solid rgba(34,211,238,0.18)',
        borderRadius: 4, padding: '7px 10px',
      }}>
        <Stat label="Miss distance" value={
          conjunction.missDistanceKm < 1
            ? `${(conjunction.missDistanceKm * 1000).toFixed(0)} m`
            : `${conjunction.missDistanceKm.toFixed(1)} km`
        } />
        <Stat label="P(collision)" value={
          conjunction.probability < 1e-12
            ? '< 1e-10'
            : (conjunction.probability).toExponential(2)
        } />
        <Stat label="TCA" value={conjunction.timeToTCA} />
        <Stat label="Do-nothing" value={`${Math.round((conjunction.doNothingConfidence ?? 0.5) * 100)}%`} />
      </div>

      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 9, color: '#334155' }}>
          {conjunction.secondarySatName}
        </span>
        <span style={{ fontSize: 9, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          Risk score {conjunction.riskScore}/100
        </span>
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <span style={{ fontSize: 9, color: '#22d3ee', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </div>
  )
}
