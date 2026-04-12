const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH: '#fb923c',
  MEDIUM: '#fbbf24',
  LOW: '#94a3b8',
}

export default function NaturalLanguageAlert({ conjunction, alerts = [] }) {
  // Prefer a matched mock/pre-built alert (has headline + recommended action).
  // Fall back to the Claude summary embedded directly in the live conjunction.
  const alert = alerts.find(a => a.conjunctionId === conjunction.id)
  const liveSummary = conjunction.summary ?? null

  if (!alert && !liveSummary) return null

  const severity = alert?.severity ?? conjunction.severity
  const color = SEVERITY_COLOR[severity] ?? '#94a3b8'

  // ── Render using a full pre-built alert (mock fallback path) ─────────────────
  if (alert) {
    const ts = new Date(alert.timestamp).toISOString().slice(11, 16) + ' UTC'
    return (
      <div style={{
        margin: '0 10px 6px',
        borderRadius: 6,
        background: `${color}0d`,
        border: `1px solid ${color}33`,
        padding: '12px 14px',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <ClaudeIcon />
            <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', lineHeight: 1.3 }}>
              {alert.headline}
            </span>
          </div>
          <Pill color={color} label={alert.severity} />
        </div>

        <p style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.6, margin: 0, marginBottom: 10 }}>
          {alert.summary}
        </p>

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

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <span style={{ fontSize: 9, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Audience: {alert.audienceLevel}
          </span>
          <span style={{ fontSize: 9, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>{ts}</span>
        </div>
      </div>
    )
  }

  // ── Render using the live Claude summary embedded in the conjunction ──────────
  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: `${color}0d`,
      border: `1px solid ${color}33`,
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <ClaudeIcon />
          <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', lineHeight: 1.3 }}>
            AI Threat Assessment
          </span>
        </div>
        <Pill color={color} label={severity} />
      </div>

      <p style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
        {liveSummary}
      </p>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
        <span style={{ fontSize: 9, color: '#334155' }}>
          claude-sonnet · live
        </span>
      </div>
    </div>
  )
}

function ClaudeIcon() {
  return (
    <div style={{
      width: 20, height: 20, borderRadius: 4,
      background: 'rgba(192, 132, 252, 0.2)',
      border: '1px solid rgba(192, 132, 252, 0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 10, color: '#c084fc', fontWeight: 700, flexShrink: 0,
    }}>
      AI
    </div>
  )
}

function Pill({ color, label }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
      color, background: `${color}18`,
      borderRadius: 3, padding: '2px 5px', flexShrink: 0,
    }}>
      {label}
    </span>
  )
}
