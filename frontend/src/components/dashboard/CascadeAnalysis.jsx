import { cascadeRisks, conjunctions } from '../../data/mockData'

const SEVERITY_COLOR = {
  CRITICAL: '#f87171',
  HIGH: '#fb923c',
  MEDIUM: '#fbbf24',
  LOW: '#94a3b8',
}

function formatProb(p) {
  return `1:${Math.round(1 / p).toLocaleString()}`
}

export default function CascadeAnalysis({ conjunction }) {
  // Find any cascade risks tied to this conjunction's maneuver options
  const relevant = cascadeRisks.filter(cr =>
    cr.maneuverOptionId.startsWith(conjunction.id)
  )

  // Also show fleet-wide secondary conjunctions involving the same satellites
  const secondaryHits = conjunctions.filter(c =>
    c.id !== conjunction.id &&
    (c.primarySatId === conjunction.primarySatId || c.secondarySatId === conjunction.primarySatId)
  )

  return (
    <div style={{
      margin: '0 10px 12px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Cascade Analysis
        </span>
        <span style={{
          fontSize: 9, color: '#64748b',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 3, padding: '2px 6px',
        }}>
          Fleet Impact
        </span>
      </div>

      {/* Maneuver-induced cascade warnings */}
      {relevant.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 10, color: '#fbbf24', fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontSize: 11 }}>⚠</span>
            Maneuver-induced secondary conjunctions
          </div>
          {relevant.map((cr) =>
            cr.affectedConjunctions.map((ac, i) => (
              <div key={i} style={{
                borderRadius: 4, padding: '8px 10px', marginBottom: 5,
                background: 'rgba(251,191,36,0.07)',
                border: '1px solid rgba(251,191,36,0.18)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>
                    {ac.satId} × {ac.threatId}
                  </span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
                    color: SEVERITY_COLOR[ac.severity],
                    background: `${SEVERITY_COLOR[ac.severity]}18`,
                    borderRadius: 3, padding: '1px 5px',
                  }}>
                    {ac.severity}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                  <span style={{ fontSize: 10, color: '#64748b' }}>
                    P = <span style={{ color: SEVERITY_COLOR[ac.severity], fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                      {formatProb(ac.newProbability)}
                    </span>
                  </span>
                  <span style={{ fontSize: 10, color: '#64748b' }}>
                    TCA <span style={{ color: '#94a3b8' }}>{ac.timeToTCA}</span>
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Fleet-wide existing secondary events */}
      {secondaryHits.length > 0 ? (
        <div>
          <div style={{ fontSize: 10, color: '#475569', fontWeight: 600, marginBottom: 6, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
            Other active conjunctions — {conjunction.primarySatName}
          </div>
          {secondaryHits.map(c => (
            <div key={c.id} style={{
              borderRadius: 4, padding: '7px 10px', marginBottom: 4,
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.05)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500, marginBottom: 2 }}>
                  × {c.primarySatId === conjunction.primarySatId ? c.secondarySatName : c.primarySatName}
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>TCA {c.timeToTCA}</div>
              </div>
              <span style={{
                fontSize: 9, fontWeight: 700, letterSpacing: '0.07em',
                color: SEVERITY_COLOR[c.severity],
                background: `${SEVERITY_COLOR[c.severity]}15`,
                borderRadius: 3, padding: '2px 6px',
              }}>
                {c.severity}
              </span>
            </div>
          ))}
        </div>
      ) : (
        relevant.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '16px 0',
            fontSize: 11, color: '#334155',
          }}>
            No cascade risks detected for this event
          </div>
        )
      )}

      {/* Summary footer */}
      <div style={{
        marginTop: 10, paddingTop: 8,
        borderTop: '1px solid rgba(255,255,255,0.05)',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 9, color: '#334155' }}>
          Fleet conjunctions total: {conjunctions.length}
        </span>
        <span style={{ fontSize: 9, color: '#334155' }}>
          Affecting this sat: {secondaryHits.length + 1}
        </span>
      </div>
    </div>
  )
}
