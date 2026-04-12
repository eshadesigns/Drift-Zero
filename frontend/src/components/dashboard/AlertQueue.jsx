const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH: '#fb923c',
  MEDIUM: '#fbbf24',
  LOW: '#94a3b8',
}

const SEVERITY_BG = {
  CRITICAL: 'rgba(248, 113, 113, 0.08)',
  HIGH: 'rgba(251, 146, 60, 0.08)',
  MEDIUM: 'rgba(251, 191, 36, 0.08)',
  LOW: 'rgba(148, 163, 184, 0.05)',
}


export default function AlertQueue({
  conjunctions = [],
  loading = false,
  selected,
  onSelect,
}) {
  const criticalCount = loading
    ? null
    : conjunctions.filter(c => c.severity === 'CRITICAL').length

  return (
    <div style={{ padding: '12px 0 4px' }}>
      <style>{`
        @keyframes drift-queue-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Conjunction Queue
        </span>
        <span style={{
          fontSize: 10, fontWeight: 600,
          color: loading ? '#64748b' : '#f87171',
          background: loading ? 'rgba(100,116,139,0.15)' : 'rgba(248,113,113,0.12)',
          borderRadius: 10,
          padding: '2px 8px', letterSpacing: '0.05em',
        }}>
          {loading ? '…' : `${criticalCount} CRITICAL`}
        </span>
      </div>

      {loading ? (
        <div
          role="status"
          aria-live="polite"
          aria-busy="true"
          style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 14,
          padding: '36px 24px 48px',
          textAlign: 'center',
        }}
        >
          <div
            aria-hidden
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              border: '2px solid rgba(34, 211, 238, 0.2)',
              borderTopColor: '#22d3ee',
              animation: 'drift-queue-spin 0.75s linear infinite',
            }}
          />
          <p style={{
            margin: 0,
            fontSize: 12,
            color: '#94a3b8',
            lineHeight: 1.5,
            maxWidth: 220,
          }}>
            Fetching live conjunction data...
          </p>
          <span style={{ fontSize: 10, color: '#475569' }}>
            Space-Track · Shield pipeline
          </span>
        </div>
      ) : (
      /* List */
      <div>
        {conjunctions.map((c) => {
          const isSelected = selected?.id === c.id
          const color = SEVERITY_COLOR[c.severity]
          const bg = isSelected ? 'rgba(34, 211, 238, 0.06)' : SEVERITY_BG[c.severity]
          const border = isSelected ? '1px solid rgba(34, 211, 238, 0.25)' : '1px solid transparent'

          return (
            <div
              key={c.id}
              onClick={() => onSelect(isSelected ? null : c)}
              style={{
                margin: '6px 10px',
                padding: '10px 12px',
                borderRadius: 6,
                background: bg,
                border,
                cursor: 'pointer',
                transition: 'background 0.15s, border 0.15s',
              }}
            >
              {/* Top row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {/* Severity badge */}
                  <span style={{
                    fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                    color, background: `${color}18`,
                    borderRadius: 3, padding: '1px 5px',
                  }}>
                    {c.severity}
                  </span>
                  {/* Score circle */}
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: c.riskScore > 80 ? '#f87171' : c.riskScore > 50 ? '#fb923c' : '#94a3b8',
                  }}>
                    {c.riskScore}
                  </span>
                </div>
                <span style={{ fontSize: 10, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
                  TCA {c.timeToTCA}
                </span>
              </div>

              {/* Satellite names */}
              <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 3, lineHeight: 1.3 }}>
                {c.primarySatName}
                <span style={{ color: '#475569', fontWeight: 400, margin: '0 5px' }}>×</span>
                {c.secondarySatName}
              </div>

              {/* Bottom row — miss distance */}
              <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
                <span style={{ fontSize: 10, color: '#64748b' }}>
                  Miss distance: <span style={{ color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
                    {c.missDistanceKm < 1
                      ? `${(c.missDistanceKm * 1000).toFixed(0)} m`
                      : `${c.missDistanceKm.toFixed(2)} km`}
                  </span>
                </span>
              </div>
            </div>
          )
        })}
      </div>
      )}
    </div>
  )
}
