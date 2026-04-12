import { useState, useCallback, useEffect, useRef } from 'react'
import StatsBar from './components/dashboard/StatsBar'
import AlertQueue from './components/dashboard/AlertQueue'
import ManeuverPanel from './components/dashboard/ManeuverPanel'
import NaturalLanguageAlert from './components/dashboard/NaturalLanguageAlert'
import CascadeAnalysis from './components/dashboard/CascadeAnalysis'
import SatelliteModal from './components/SatelliteModal'
import RoguePanel from './components/RoguePanel'
import { satStore } from './satStore'
import { fetchConjunctions, deriveStats } from './api/shield'
import { fleetStats as mockFleetStats, conjunctions as mockConjunctions } from './data/mockData.js'

const PANEL_MIN = 15   // % of screen width
const PANEL_MAX = 55
const DEFAULT_PANEL = 30

// Maps NORAD IDs to the primarySatId strings used in conjunctions
// Must match GlobeView.jsx SAT_TLES entity IDs exactly
const NORAD_TO_SAT_ID = {
  25544: 'ISS',
  20580: 'HST',
  44713: 'SL1',
  47526: 'SL2',
  28654: 'NOAA18',
  25994: 'TERRA',
  29499: 'METOP',
  27424: 'AQUA',
}

export default function DashboardOverlay({ activated = false, noradId = 25544, demo = false, showAll = false, onRetarget }) {
  const [activeMode, setActiveMode] = useState('shield')   // 'shield' | 'rogue'
  const [selectedConjunction, setSelectedConjunction] = useState(null)
  const [selectedManeuver, setSelectedManeuver] = useState(null)  // slug for cascade
  const [panelPct, setPanelPct] = useState(DEFAULT_PANEL)
  const [collapsed, setCollapsed] = useState('panels') // start hidden, open on activate

  // ── Shield data ─────────────────────────────────────────────────────────────
  const [conjunctions, setConjunctions] = useState([])
  const [conjunctionsLoading, setConjunctionsLoading] = useState(true)
  const [stats, setStats] = useState(mockFleetStats)
  const [isLive, setIsLive] = useState(false)

  useEffect(() => {
    let cancelled = false
    setConjunctionsLoading(true)
    setConjunctions([])
    setSelectedConjunction(null)
    setIsLive(false)

    if (demo) {
      setConjunctions(mockConjunctions ?? [])
      setIsLive(false)
      setConjunctionsLoading(false)
      setStats(mockFleetStats)
      return
    }

    const controller = new AbortController()
    fetchConjunctions(noradId, { minRisk: 0, limit: 100 }, controller.signal)
      .then(({ conjunctions: live, stats: liveStats }) => {
        if (cancelled) return
        setIsLive(true)
        if (live.length > 0) {
          setConjunctions(live)
          setStats(prev => ({ ...prev, ...liveStats }))
        } else {
          setConjunctions(mockConjunctions ?? [])
        }
      })
      .catch((err) => {
        if (cancelled || err.name === 'AbortError') return
        setConjunctions(mockConjunctions ?? [])
      })
      .finally(() => {
        if (!cancelled) setConjunctionsLoading(false)
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [noradId, demo])

  // Slide panels in after activation
  useEffect(() => {
    if (activated) {
      const t = setTimeout(() => setCollapsed(null), 300)
      return () => clearTimeout(t)
    }
  }, [activated])

  const [isDragging, setIsDragging] = useState(false)
  const [dividerHover, setDividerHover] = useState(false)
  const tabDragMoved = useRef(false)

  // ── Satellite selection from GlobeView ────────────────────────────────────
  const [selectedSat, setSelectedSat] = useState(null)
  const [satAnalyzed, setSatAnalyzed] = useState(false)
  const [satRiskCount, setSatRiskCount] = useState(0)

  useEffect(() => {
    return satStore.subscribe(({ sat, analyzed, riskCount }) => {
      setSelectedSat(sat)
      setSatAnalyzed(analyzed)
      setSatRiskCount(riskCount)
    })
  }, [])

  // When user clicks a satellite on the globe → make it the persistent active target
  useEffect(() => {
    if (selectedSat?.noradId && onRetarget) {
      onRetarget(selectedSat.noradId, selectedSat.id)
    }
  }, [selectedSat?.noradId])

  const handleSatClose = useCallback(() => { satStore.onClose?.() }, [])
  const handleSatAnalyze = useCallback(() => { satStore.onAnalyze?.() }, [])

  // ── Conjunction filtering ─────────────────────────────────────────────────
  // Determine which satellite's conjunctions to show:
  //   • selectedSat (clicked from globe) takes priority — match by entity id
  //   • otherwise use noradId (from Track input) mapped to primarySatId
  const focusedSatId = selectedSat?.id || NORAD_TO_SAT_ID[noradId] || null

  const filteredConjunctions = (showAll || !focusedSatId)
    ? conjunctions
    : conjunctions.filter(c => c.primarySatId === focusedSatId)

  // Reset selected conjunction when the focus changes to avoid stale state
  useEffect(() => {
    setSelectedConjunction(null)
    setSelectedManeuver(null)
  }, [focusedSatId, showAll])

  // ── Drag-to-resize ──────────────────────────────────────────────────────────
  const onDividerMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
    setCollapsed(null)
  }, [])

  useEffect(() => {
    if (!isDragging) return
    const onMouseMove = (e) => {
      tabDragMoved.current = true
      const pct = ((window.innerWidth - e.clientX) / window.innerWidth) * 100
      setPanelPct(Math.min(PANEL_MAX, Math.max(PANEL_MIN, pct)))
    }
    const onMouseUp = () => setIsDragging(false)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [isDragging])

  // ── Sync CSS vars ───────────────────────────────────────────────────────────
  useEffect(() => {
    const activePct = collapsed === 'panels' ? 0 : panelPct
    document.documentElement.style.setProperty('--panel-pct', activePct)
    document.documentElement.style.setProperty('--panel-transition', isDragging ? 'none' : 'transform 0.25s ease')
  }, [panelPct, collapsed, isDragging])

  // ── Collapse helpers ────────────────────────────────────────────────────────
  const toggleCollapse = () => {
    if (collapsed === 'panels') {
      setCollapsed(null)
      setPanelPct(DEFAULT_PANEL)
    } else {
      setCollapsed('panels')
    }
  }

  const panelWidth   = collapsed === 'panels' ? '0%' : `${panelPct}%`
  const dividerRight = collapsed === 'panels' ? 0 : `${panelPct}%`
  const transition   = isDragging ? 'none' : 'width 0.25s ease, right 0.25s ease'

  return (
    <>
      {/* ── StatsBar ─────────────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        pointerEvents: activated ? 'auto' : 'none',
        opacity: activated ? 1 : 0,
        transform: activated ? 'translateY(0)' : 'translateY(-100%)',
        transition: 'opacity 0.5s ease 0.4s, transform 0.5s ease 0.4s',
      }}>
        <StatsBar stats={stats} isLive={isLive} onRetarget={onRetarget} trackedId={focusedSatId} />
      </div>

      {/* ── Right panel ──────────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute',
        top: 44,
        right: 0,
        bottom: 0,
        width: panelWidth,
        transition,
        zIndex: 10,
        overflow: 'hidden',
        pointerEvents: 'auto',
      }}>
        <div style={{
          width: '100%',
          height: '100%',
          background: 'rgba(3, 7, 18, 0.92)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderLeft: '1px solid rgba(255,255,255,0.07)',
          display: 'flex',
          flexDirection: 'column',
        }}>
          {selectedSat ? (
            /* ── Satellite selected from globe: show modal + its conjunctions ── */
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
              <SatelliteModal
                key={selectedSat.id}
                sat={selectedSat}
                onClose={handleSatClose}
                onAnalyze={handleSatAnalyze}
                analyzed={satAnalyzed}
                riskCount={satRiskCount}
                inline
              />
              {/* Divider */}
              <div style={{ margin: '0 10px', borderTop: '1px solid rgba(255,255,255,0.07)', paddingTop: 8 }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: '#334155', textTransform: 'uppercase', paddingLeft: 4 }}>
                  Conjunction Events
                </span>
              </div>
              <AlertQueue
                conjunctions={filteredConjunctions}
                loading={conjunctionsLoading}
                selected={selectedConjunction}
                onSelect={(c) => { setSelectedConjunction(c); setSelectedManeuver(null) }}
              />
              {selectedConjunction && (
                <>
                  <NaturalLanguageAlert conjunction={selectedConjunction} />
                  <ManeuverPanel
                    conjunction={selectedConjunction}
                    demo={demo}
                    onSelectManeuver={setSelectedManeuver}
                  />
                  <CascadeAnalysis
                    conjunction={selectedConjunction}
                    selectedManeuver={selectedManeuver}
                  />
                </>
              )}
            </div>
          ) : (
            <>
              {/* ── Mode tab bar ──────────────────────────────────────────────── */}
              <div style={{
                display: 'flex',
                borderBottom: '1px solid rgba(255,255,255,0.07)',
                flexShrink: 0,
              }}>
                {['shield', 'rogue'].map(mode => {
                  const active = activeMode === mode
                  return (
                    <button
                      key={mode}
                      onClick={() => setActiveMode(mode)}
                      style={{
                        flex: 1,
                        padding: '10px 0',
                        background: 'transparent',
                        border: 'none',
                        borderBottom: active ? '2px solid #22d3ee' : '2px solid transparent',
                        color: active ? '#22d3ee' : '#64748b',
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        cursor: 'pointer',
                        transition: 'color 0.15s, border-color 0.15s',
                      }}
                    >
                      {mode === 'shield' ? 'Shield' : 'Rogue'}
                    </button>
                  )
                })}
              </div>

              {/* ── Shield panel (keep mounted, hide when rogue active) ───────── */}
              <div style={{
                display: activeMode === 'shield' ? 'flex' : 'none',
                flexDirection: 'column',
                flex: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
              }}>
                <AlertQueue
                  conjunctions={filteredConjunctions}
                  loading={conjunctionsLoading}
                  selected={selectedConjunction}
                  onSelect={(c) => { setSelectedConjunction(c); setSelectedManeuver(null) }}
                />
                {selectedConjunction && (
                  <>
                    <NaturalLanguageAlert conjunction={selectedConjunction} />
                    <ManeuverPanel
                      conjunction={selectedConjunction}
                      demo={demo}
                      onSelectManeuver={setSelectedManeuver}
                    />
                    <CascadeAnalysis
                      conjunction={selectedConjunction}
                      selectedManeuver={selectedManeuver}
                    />
                  </>
                )}
              </div>

              {/* ── Rogue panel (keep mounted, hide when shield active) ───────── */}
              <div style={{
                display: activeMode === 'rogue' ? 'flex' : 'none',
                flexDirection: 'column',
                flex: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
              }}>
                <RoguePanel visible={activeMode === 'rogue'} demo={demo} focusedSatId={focusedSatId} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Divider ──────────────────────────────────────────────────────────── */}
      <div
        onMouseDown={activated ? onDividerMouseDown : undefined}
        onMouseEnter={() => setDividerHover(true)}
        onMouseLeave={() => setDividerHover(false)}
        style={{
          position: 'absolute',
          top: 44,
          bottom: 0,
          right: dividerRight,
          width: 6,
          zIndex: 11,
          cursor: 'col-resize',
          transition,
          opacity: activated ? 1 : 0,
          pointerEvents: activated ? 'auto' : 'none',
          background: isDragging
            ? 'rgba(34,211,238,0.3)'
            : dividerHover
              ? 'rgba(34,211,238,0.12)'
              : 'transparent',
        }}
      >
        <button
          onMouseDown={(e) => {
            e.stopPropagation()
            tabDragMoved.current = false
            setIsDragging(true)
            setCollapsed(null)
          }}
          onClick={() => {
            if (!tabDragMoved.current) toggleCollapse()
          }}
          style={{
            position: 'absolute',
            top: '50%',
            left: '-14px',
            transform: 'translateY(-50%)',
            width: 20,
            height: 52,
            borderRadius: '6px 0 0 6px',
            background: dividerHover || isDragging
              ? 'rgba(34,211,238,0.18)'
              : 'rgba(15,22,40,0.92)',
            border: '1px solid rgba(255,255,255,0.18)',
            borderRight: 'none',
            color: dividerHover ? '#22d3ee' : '#94a3b8',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
            boxShadow: '-3px 0 12px rgba(0,0,0,0.4)',
            transition: 'background 0.15s, color 0.15s',
          }}
          title={collapsed === 'panels' ? 'Expand panels' : 'Collapse panels'}
        >
          <svg width="10" height="18" viewBox="0 0 10 18" fill="none">
            {collapsed === 'panels' ? (
              <polyline points="2,2 8,9 2,16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            ) : (
              <polyline points="8,2 2,9 8,16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            )}
          </svg>
        </button>
      </div>

      {isDragging && (
        <style>{`* { cursor: col-resize !important; user-select: none !important; }`}</style>
      )}
    </>
  )
}
