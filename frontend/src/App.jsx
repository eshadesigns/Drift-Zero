import { useState, useCallback, useEffect, useRef } from 'react'
import StatsBar from './components/dashboard/StatsBar'
import AlertQueue from './components/dashboard/AlertQueue'
import ManeuverPanel from './components/dashboard/ManeuverPanel'
import NaturalLanguageAlert from './components/dashboard/NaturalLanguageAlert'
import CascadeAnalysis from './components/dashboard/CascadeAnalysis'
import SatelliteModal from './components/SatelliteModal'
import RoguePanel from './components/RoguePanel'
import { satStore } from './satStore'
import { fetchConjunctions } from './api/shield'
import {
  conjunctions as mockConjunctions,
  fleetStats as mockFleetStats,
  naturalLanguageAlerts as mockAlerts,
} from './data/mockData'

const PANEL_MIN = 15   // % of screen width
const PANEL_MAX = 55
const DEFAULT_PANEL = 30

// NORAD ID of the primary satellite to analyse. Override via .env VITE_SHIELD_NORAD_ID.
const PRIMARY_NORAD_ID = Number(import.meta.env.VITE_SHIELD_NORAD_ID ?? 25544)

export default function DashboardOverlay() {
  // ── Live data state — initialised with mock so the UI renders immediately ────
  const [conjunctions, setConjunctions] = useState(mockConjunctions)
  const [stats, setStats] = useState(mockFleetStats)
  // NL alerts come from the Claude API (not yet wired); fall back to mock entries
  // so the panel still renders for known mock conjunction IDs.
  const [alerts, setAlerts] = useState(mockAlerts)
  const [isLive, setIsLive] = useState(false)

  // ── Fetch from Shield API on mount ───────────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const { conjunctions: live, stats: derived } = await fetchConjunctions({
          noradId: PRIMARY_NORAD_ID,
          minRisk: 0,
          limit: 100,
        })
        if (cancelled) return
        // API responded — mark as live regardless of event count.
        setIsLive(true)
        // Only replace mock conjunctions if the pipeline returned real events.
        // An empty response (pipeline ran but found nothing) keeps mock data
        // visible so the UI isn't blank during a demo.
        if (live.length > 0) {
          setConjunctions(live)
          setAlerts([])
        }
        // Always merge stats regardless of event count.
        setStats({ ...mockFleetStats, ...derived })
      } catch {
        // API unreachable or pipeline error — keep mock data already in state.
        setIsLive(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  const [activeMode, setActiveMode] = useState('shield') // 'shield' | 'rogue'
  const [selectedConjunction, setSelectedConjunction] = useState(null)
  const [panelPct, setPanelPct] = useState(DEFAULT_PANEL)
  const [collapsed, setCollapsed] = useState(null) // null | 'panels'
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

  const handleSatClose = useCallback(() => {
    satStore.onClose?.()
  }, [])

  const handleSatAnalyze = useCallback(() => {
    satStore.onAnalyze?.()
  }, [])

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

  // ── Sync CSS vars → globe wrapper reads these to shift itself ───────────────
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

  // ── Derived widths ──────────────────────────────────────────────────────────
  const panelWidth = collapsed === 'panels' ? '0%' : `${panelPct}%`
  const dividerRight = collapsed === 'panels' ? 0 : `${panelPct}%`
  const transition = isDragging ? 'none' : 'width 0.25s ease, right 0.25s ease'

  return (
    <>
      {/* ── StatsBar — top ───────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        pointerEvents: 'auto',
      }}>
        <StatsBar stats={stats} isLive={isLive} />
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
          overflowY: 'auto',
          overflowX: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          {selectedSat ? (
            <SatelliteModal
              key={selectedSat.id}
              sat={selectedSat}
              onClose={handleSatClose}
              onAnalyze={handleSatAnalyze}
              analyzed={satAnalyzed}
              riskCount={satRiskCount}
              inline
            />
          ) : (
            <>
              {/* ── Mode tab bar — sticky so it stays visible while scrolling ── */}
              <div style={{
                position: 'sticky',
                top: 0,
                zIndex: 1,
                display: 'flex',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(3,7,18,0.97)',
                flexShrink: 0,
              }}>
                {['shield', 'rogue'].map(mode => {
                  const active = activeMode === mode
                  return (
                    <button
                      key={mode}
                      onClick={() => {
                        setActiveMode(mode)
                      }}
                      style={{
                        flex: 1,
                        padding: '9px 0',
                        background: 'none',
                        border: 'none',
                        borderBottom: active
                          ? '2px solid #22d3ee'
                          : '2px solid transparent',
                        color: active ? '#22d3ee' : '#475569',
                        fontSize: 10,
                        fontWeight: 700,
                        letterSpacing: '0.12em',
                        textTransform: 'uppercase',
                        cursor: 'pointer',
                        transition: 'color 0.15s, border-color 0.15s',
                      }}
                    >
                      {mode}
                    </button>
                  )
                })}
              </div>

              {/* ── Mode content ─────────────────────────────────────────────── */}
              {/* Both panels stay mounted — display:none preserves fetched data
                  across tab switches and prevents duplicate API/Claude calls. */}
              <div style={{ display: activeMode === 'shield' ? 'contents' : 'none' }}>
                <AlertQueue
                  conjunctions={conjunctions}
                  selected={selectedConjunction}
                  onSelect={setSelectedConjunction}
                />
                {selectedConjunction && (
                  <>
                    <NaturalLanguageAlert
                      conjunction={selectedConjunction}
                      alerts={alerts}
                    />
                    <ManeuverPanel conjunction={selectedConjunction} />
                    <CascadeAnalysis conjunction={selectedConjunction} />
                  </>
                )}
              </div>
              <div style={{ display: activeMode === 'rogue' ? 'contents' : 'none' }}>
                <RoguePanel />
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Divider — drag strip + always-visible collapse tab ───────────────── */}
      <div
        onMouseDown={onDividerMouseDown}
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
          pointerEvents: 'auto',
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
          onClick={(e) => {
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
