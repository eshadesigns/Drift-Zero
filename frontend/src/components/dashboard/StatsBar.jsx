import { useState } from 'react'
import { fleetStats as mockFleetStats } from '../../data/mockData'

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

export default function StatsBar({ stats: propStats, isLive = false, onRetarget, trackedId }) {
  const fleetStats = propStats ?? mockFleetStats
  const [searchVal, setSearchVal] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const prob = fleetStats.maxCollisionProb ?? fleetStats.avgCollisionProb ?? 0
export default function StatsBar({ stats = {}, isLive = false }) {
  const {
    activeSatellites   = 0,
    activeConjunctions = 0,
    criticalAlerts     = 0,
    maxCollisionProb   = 0,
    avgCollisionProb   = 0,
  } = stats

  const prob = maxCollisionProb || avgCollisionProb
  const probDisplay = prob < 1e-12 ? '< 1e-10%' : (prob * 100).toExponential(2) + '%'

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
          <span style={{ ...S.statValue, color: '#94a3b8' }}>{activeSatellites}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Conjunctions</span>
          <span style={{ ...S.statValue, color: severity.high }}>{activeConjunctions}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Critical</span>
          <span style={{ ...S.statValue, color: severity.critical }}>{criticalAlerts}</span>
        </div>
        <div style={S.divider} />
        <div style={S.stat}>
          <span style={S.statLabel}>Avg P(collision)</span>
          <span style={{ ...S.statValue, color: severity.medium }}>{probDisplay}</span>
        </div>
      </div>

      {/* Satellite search */}
      {onRetarget && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8, flexShrink: 0 }}>
          {searchOpen ? (
            <form
              onSubmit={e => {
                e.preventDefault()
                const val = searchVal.trim()
                if (val) { onRetarget(val); setSearchOpen(false); setSearchVal('') }
              }}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <input
                autoFocus
                value={searchVal}
                onChange={e => setSearchVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Escape') { setSearchOpen(false); setSearchVal('') } }}
                placeholder="NORAD ID…"
                style={{
                  width: 100, height: 26,
                  background: 'rgba(3,7,18,0.9)',
                  border: '1px solid rgba(34,211,238,0.4)',
                  borderRadius: 5, outline: 'none',
                  color: '#e2e8f0', fontSize: 11,
                  fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
                  padding: '0 8px',
                }}
              />
              <button type="submit" style={{
                height: 26, padding: '0 10px', borderRadius: 5,
                background: 'rgba(34,211,238,0.15)',
                border: '1px solid rgba(34,211,238,0.4)',
                color: '#22d3ee', fontSize: 11, fontWeight: 700,
                cursor: 'pointer', fontFamily: 'inherit',
              }}>Go</button>
              <button type="button" onClick={() => { setSearchOpen(false); setSearchVal('') }} style={{
                height: 26, width: 26, borderRadius: 5,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#64748b', fontSize: 13,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>×</button>
            </form>
          ) : (
            <button
              onClick={() => setSearchOpen(true)}
              title="Track a different satellite"
              style={{
                height: 26, padding: '0 10px', borderRadius: 5,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#64748b', fontSize: 11, fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
                fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
                transition: 'color 0.15s, border-color 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color='#94a3b8'; e.currentTarget.style.borderColor='rgba(255,255,255,0.25)' }}
              onMouseLeave={e => { e.currentTarget.style.color='#64748b'; e.currentTarget.style.borderColor='rgba(255,255,255,0.12)' }}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <circle cx="4.5" cy="4.5" r="3.5" stroke="currentColor" strokeWidth="1.2"/>
                <line x1="7.2" y1="7.2" x2="9.5" y2="9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
              {trackedId ?? 'Track'}
            </button>
          )}
        </div>
      )}

      {/* Live/Mock badge */}
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
        color: isLive ? '#22d3ee' : '#64748b',
        background: isLive ? 'rgba(34,211,238,0.1)' : 'rgba(100,116,139,0.1)',
        border: `1px solid ${isLive ? 'rgba(34,211,238,0.3)' : 'rgba(100,116,139,0.3)'}`,
        borderRadius: 4,
        padding: '2px 7px',
        marginLeft: 8,
        flexShrink: 0,
      }}>
        {isLive ? 'LIVE' : 'MOCK'}
      </span>

      <span style={S.timestamp}>
        {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC
      </span>
    </div>
  )
}
