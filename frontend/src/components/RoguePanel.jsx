import { useState, useEffect } from 'react'
import {
  mockRogueEvents,
  mockAssetImpact,
  mockMissionMismatch,
  mockIncidents,
} from '../data/mockData'

const BASE_URL = import.meta.env.VITE_SHIELD_API_URL ?? 'http://localhost:8000'

const SEV_COLOR = {
  ADVERSARIAL: '#ef4444',
  SUSPICIOUS:  '#f59e0b',
  NOMINAL:     '#22d3ee',
}
const VERDICT_COLOR = {
  ADVERSARIAL: '#ef4444',
  SUSPICIOUS:  '#f59e0b',
  ANOMALOUS:   '#fb923c',
  NORMAL:      '#22d3ee',
}
const TIER_COLOR = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#22d3ee' }
const CLASS_COLOR = { ASAT: '#ef4444', SHADOWING: '#f59e0b', INSPECTION: '#f59e0b', RELOCATION: '#fb923c' }

function SectionHeader({ label, count, countColor }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, marginBottom: 4 }}>
      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
        {label}
      </span>
      {count != null && (
        <span style={{ fontSize: 10, color: countColor ?? '#64748b', marginLeft: 'auto' }}>
          {count}
        </span>
      )}
      <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)', marginLeft: 6 }} />
    </div>
  )
}

export default function RoguePanel({ visible, demo = false, focusedSatId = null, compact = false }) {
  const [events, setEvents]     = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [fetched, setFetched]   = useState(false)
  const [openIncident, setOpenIncident] = useState(null)

  // Demo mode: derive all data from mock data keyed by focusedSatId
  useEffect(() => {
    if (!demo) return
    setEvents(focusedSatId && mockRogueEvents[focusedSatId] ? mockRogueEvents[focusedSatId] : [])
    setFetched(true)
    setLoading(false)
    setError(null)
  }, [demo, focusedSatId])

  // Live API fetch
  useEffect(() => {
    if (demo || !visible || fetched) return
    setLoading(true)
    fetch(`${BASE_URL}/api/rogue/events`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then(data => { setEvents(data); setFetched(true) })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [visible, fetched, demo])

  const assetImpact    = demo ? (focusedSatId ? mockAssetImpact[focusedSatId] : null) : null
  const missionData    = demo ? (focusedSatId ? mockMissionMismatch[focusedSatId] : null) : null
  const relatedIncidents = demo
    ? mockIncidents.filter(inc => !focusedSatId || inc.relevantSatIds?.includes(focusedSatId))
    : []

  const flaggedCount = events.filter(e => e.severity !== 'NOMINAL').length

  return (
    <div style={{ padding: compact ? '8px 12px' : '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#94a3b8', textTransform: 'uppercase' }}>
          Rogue Intelligence
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {focusedSatId && (
            <span style={{ fontSize: 10, color: '#475569', fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace" }}>
              {focusedSatId}
            </span>
          )}
          {fetched && !loading && (
            <span style={{ fontSize: 10, color: flaggedCount > 0 ? '#ef4444' : '#22d3ee' }}>
              {flaggedCount > 0 ? `${flaggedCount} flagged` : 'nominal'}
            </span>
          )}
        </div>
      </div>

      {loading && <div style={{ color: '#64748b', fontSize: 12, padding: '16px 0', textAlign: 'center' }}>Running anomaly pipeline…</div>}
      {error && !loading && <div style={{ color: '#ef4444', fontSize: 12 }}>Unreachable — {error}</div>}

      {/* ── Asset Intelligence ───────────────────────────────────────────────── */}
      {assetImpact && (
        <>
          <SectionHeader label="Asset Intelligence" />
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid ${TIER_COLOR[assetImpact.strategic_tier] ?? '#334155'}44`,
            borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 5,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: TIER_COLOR[assetImpact.strategic_tier] ?? '#94a3b8',
                background: `${TIER_COLOR[assetImpact.strategic_tier] ?? '#94a3b8'}22`,
                border: `1px solid ${TIER_COLOR[assetImpact.strategic_tier] ?? '#94a3b8'}44`,
                borderRadius: 4, padding: '2px 7px',
              }}>
                {assetImpact.strategic_tier}
              </span>
              <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>{assetImpact.name}</span>
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ fontSize: 10, color: '#64748b' }}>
                Impact/day: <span style={{ color: '#f59e0b', fontWeight: 600 }}>{assetImpact.economic_impact_formatted}</span>
              </div>
              <div style={{ fontSize: 10, color: '#64748b' }}>
                Replace: <span style={{ color: '#94a3b8', fontWeight: 600 }}>{assetImpact.replacement_cost_formatted}</span>
              </div>
            </div>
            <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.5 }}>{assetImpact.mission_description}</div>
            <div style={{ fontSize: 10, color: '#475569', lineHeight: 1.4 }}>{assetImpact.users_at_risk}</div>
            {assetImpact.notes && (
              <div style={{ fontSize: 10, color: '#334155', lineHeight: 1.4, marginTop: 2, fontStyle: 'italic' }}>{assetImpact.notes}</div>
            )}
          </div>
        </>
      )}

      {/* ── Nearby Threats ──────────────────────────────────────────────────── */}
      {fetched && !loading && (
        <>
          <SectionHeader
            label="Nearby Threats"
            count={flaggedCount > 0 ? `${flaggedCount} object${flaggedCount > 1 ? 's' : ''}` : 'none detected'}
            countColor={flaggedCount > 0 ? '#ef4444' : '#334155'}
          />
          {events.length === 0 ? (
            <div style={{ color: '#334155', fontSize: 11, padding: '8px 0', textAlign: 'center' }}>
              No suspicious objects detected near {focusedSatId ?? 'this satellite'}.
            </div>
          ) : events.map((ev, i) => {
            const color = SEV_COLOR[ev.severity] ?? '#94a3b8'
            return (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${color}33`,
                borderRadius: 8, padding: '10px 12px',
                display: 'flex', flexDirection: 'column', gap: 5,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, color,
                    background: `${color}22`, border: `1px solid ${color}55`,
                    borderRadius: 4, padding: '2px 7px', flexShrink: 0,
                  }}>{ev.severity}</span>
                  <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>
                    {ev.name ?? `NORAD ${ev.norad_id}`}
                  </span>
                  <span style={{ fontSize: 10, color: '#64748b', marginLeft: 'auto' }}>
                    score {ev.composite_score?.toFixed(3)}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>
                  {ev.epoch ? new Date(ev.epoch).toUTCString().replace(' GMT', ' UTC') : ''}
                  {ev.norad_id && <span style={{ marginLeft: 8, color: '#334155' }}>NORAD {ev.norad_id}</span>}
                </div>
                {(ev.summary || ev.description) && (
                  <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.55 }}>
                    {ev.summary || ev.description}
                  </div>
                )}
                {ev.anomalous_features?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {ev.anomalous_features.map(f => (
                      <span key={f} style={{
                        fontSize: 9, color: '#94a3b8',
                        background: 'rgba(148,163,184,0.1)',
                        border: '1px solid rgba(148,163,184,0.2)',
                        borderRadius: 3, padding: '1px 6px',
                      }}>{f.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </>
      )}

      {/* ── Mission Analysis ────────────────────────────────────────────────── */}
      {missionData && (
        <>
          <SectionHeader label="Mission Analysis" />
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid ${VERDICT_COLOR[missionData.verdict] ?? '#334155'}33`,
            borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 5,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, color: '#475569', marginBottom: 3 }}>Mismatch Score</div>
                <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                  <div style={{
                    height: '100%',
                    width: `${missionData.mismatch_score * 100}%`,
                    background: VERDICT_COLOR[missionData.verdict] ?? '#94a3b8',
                    borderRadius: 2,
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                  {(missionData.mismatch_score * 100).toFixed(0)}% deviation from declared mission
                </div>
              </div>
              <span style={{
                fontSize: 11, fontWeight: 700,
                color: VERDICT_COLOR[missionData.verdict] ?? '#94a3b8',
                flexShrink: 0,
              }}>{missionData.verdict}</span>
            </div>
            <div style={{ fontSize: 10, color: '#64748b' }}>
              Declared: <span style={{ color: '#94a3b8' }}>{missionData.declared_mission}</span>
            </div>
            {missionData.notes && (
              <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>{missionData.notes}</div>
            )}
            {missionData.signals?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {missionData.signals.map(s => (
                  <span key={s} style={{
                    fontSize: 9, color: '#f59e0b',
                    background: 'rgba(245,158,11,0.1)',
                    border: '1px solid rgba(245,158,11,0.2)',
                    borderRadius: 3, padding: '1px 6px',
                  }}>{s.replace(/_/g, ' ')}</span>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Historical Incidents ─────────────────────────────────────────────── */}
      {relatedIncidents.length > 0 && (
        <>
          <SectionHeader label="Historical Precedents" count={`${relatedIncidents.length} incident${relatedIncidents.length > 1 ? 's' : ''}`} />
          {relatedIncidents.map(inc => {
            const color = CLASS_COLOR[inc.classification] ?? '#94a3b8'
            const isOpen = openIncident === inc.id
            return (
              <div key={inc.id} style={{
                background: 'rgba(255,255,255,0.02)',
                border: `1px solid ${color}22`,
                borderRadius: 8, overflow: 'hidden',
              }}>
                <button
                  onClick={() => setOpenIncident(isOpen ? null : inc.id)}
                  style={{
                    width: '100%', padding: '9px 12px', background: 'transparent',
                    border: 'none', cursor: 'pointer', textAlign: 'left',
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}
                >
                  <span style={{
                    fontSize: 9, fontWeight: 700, color,
                    background: `${color}22`, border: `1px solid ${color}44`,
                    borderRadius: 3, padding: '1px 6px', flexShrink: 0,
                  }}>{inc.classification}</span>
                  <span style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 600, flex: 1, textAlign: 'left' }}>
                    {inc.title}
                  </span>
                  <span style={{ fontSize: 10, color: '#475569', flexShrink: 0 }}>{inc.date.slice(0, 7)}</span>
                  <span style={{ fontSize: 10, color: '#475569' }}>{isOpen ? '▲' : '▼'}</span>
                </button>
                {isOpen && (
                  <div style={{ padding: '0 12px 10px', display: 'flex', flexDirection: 'column', gap: 5 }}>
                    <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.55 }}>{inc.summary}</div>
                    <div style={{ fontSize: 10, color: '#64748b', lineHeight: 1.5, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 5, marginTop: 2 }}>
                      <span style={{ color: '#475569', fontWeight: 600 }}>Actor:</span> {inc.actor.name} ({inc.actor.country})
                      {inc.target && <> · <span style={{ color: '#475569', fontWeight: 600 }}>Target:</span> {inc.target.name}</>}
                    </div>
                    <div style={{ fontSize: 10, color: '#f59e0b', lineHeight: 1.5 }}>{inc.detection_summary}</div>
                    <div style={{ fontSize: 10, color: '#475569', lineHeight: 1.5 }}>{inc.consequence}</div>
                  </div>
                )}
              </div>
            )
          })}
        </>
      )}

    </div>
  )
}
