import { fleetStats } from '../../data/mockData'

const S = {
  bar: {
    height: 44,
    background: 'rgba(3, 7, 18, 0.92)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    borderBottom: '1px solid rgba(255,255,255,0.07)',
    display: 'flex',
    alignItems: 'center',
    paddingLeft: 16,
    paddingRight: 16,
    gap: 0,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginRight: 24,
    flexShrink: 0,
  },
  logoText: {
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: '0.12em',
    color: '#e2e8f0',
    textTransform: 'uppercase',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#22d3ee',
    boxShadow: '0 0 6px #22d3ee',
    animation: 'pulse 2s ease-in-out infinite',
  },
  divider: {
    width: 1,
    height: 24,
    background: 'rgba(255,255,255,0.1)',
    marginLeft: 16,
    marginRight: 16,
    flexShrink: 0,
  },
  stats: {
    display: 'flex',
    alignItems: 'center',
    gap: 0,
    flex: 1,
    overflow: 'hidden',
  },
  stat: {
    display: 'flex',
    flexDirection: 'column',
    paddingLeft: 16,
    paddingRight: 16,
    flexShrink: 0,
  },
  statLabel: {
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: '0.1em',
    color: '#475569',
    textTransform: 'uppercase',
    lineHeight: 1,
    marginBottom: 2,
  },
  statValue: {
    fontSize: 15,
    fontWeight: 700,
    lineHeight: 1,
    fontVariantNumeric: 'tabular-nums',
  },
  timestamp: {
    fontSize: 10,
    color: '#334155',
    marginLeft: 'auto',
    flexShrink: 0,
    fontVariantNumeric: 'tabular-nums',
  },
}

const severity = {
  critical: '#f87171',
  high: '#fb923c',
  medium: '#fbbf24',
  normal: '#94a3b8',
}

export default function StatsBar() {
  const probDisplay = (fleetStats.avgCollisionProb * 100).toExponential(2) + '%'

  return (
    <div style={S.bar}>
      {/* Logo */}
      <div style={S.logo}>
        <div style={S.dot} />
        <span style={S.logoText}>Drift Zero</span>
      </div>

      <div style={S.divider} />

      {/* Stats */}
      <div style={S.stats}>
        <div style={S.stat}>
          <span style={S.statLabel}>Active Sats</span>
          <span style={{ ...S.statValue, color: '#94a3b8' }}>{fleetStats.activeSatellites}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Conjunctions</span>
          <span style={{ ...S.statValue, color: severity.high }}>{fleetStats.activeConjunctions}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Critical</span>
          <span style={{ ...S.statValue, color: severity.critical }}>{fleetStats.criticalAlerts}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Avg P(collision)</span>
          <span style={{ ...S.statValue, color: severity.medium }}>{probDisplay}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Tracked Objects</span>
          <span style={{ ...S.statValue, color: '#94a3b8' }}>{fleetStats.totalTrackedObjects.toLocaleString()}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Maneuvers / mo</span>
          <span style={{ ...S.statValue, color: '#94a3b8' }}>{fleetStats.maneuversThisMonth}</span>
        </div>
      </div>

      <span style={S.timestamp}>
        {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC
      </span>
    </div>
  )
}
