import { useState, useCallback, useEffect, useRef } from 'react'
import StatsBar from './components/dashboard/StatsBar'
import AlertQueue from './components/dashboard/AlertQueue'
import ManeuverPanel from './components/dashboard/ManeuverPanel'
import NaturalLanguageAlert from './components/dashboard/NaturalLanguageAlert'
import CascadeAnalysis from './components/dashboard/CascadeAnalysis'
import SatelliteModal from './components/SatelliteModal'
import { satStore } from './satStore'
import { fetchConjunctions, fetchSatellite } from './api/shield'

const PANEL_MIN = 15   // % of screen width
const PANEL_MAX = 55
const DEFAULT_PANEL = 30

const EMPTY_STATS = { activeSatellites: 0, activeConjunctions: 0, criticalAlerts: 0, avgCollisionProb: 0 }

export default function DashboardOverlay({ activated = false, noradId = null }) {
  const [selectedConjunction, setSelectedConjunction] = useState(null)
  const [panelPct, setPanelPct] = useState(DEFAULT_PANEL)
  const [collapsed, setCollapsed] = useState('panels') // start hidden, open on activate

  // Slide panels in after activation
  useEffect(() => {
    if (activated) {
      const t = setTimeout(() => setCollapsed(null), 300)
      return () => clearTimeout(t)
    }
  }, [activated])
  const [isDragging, setIsDragging] = useState(false)
  const [dividerHover, setDividerHover] = useState(false)
  const tabDragMoved = useRef(false) // tracks whether tab mousedown became a drag

  // ── Live conjunction data ──────────────────────────────────────────────────
  // Starts null — nothing loads until the user submits a NORAD ID.
  const [selectedNoradId, setSelectedNoradId] = useState(null)
  const [primarySatTle, setPrimarySatTle] = useState(null)

  useEffect(() => {
    if (noradId && noradId !== selectedNoradId) setSelectedNoradId(noradId)
  }, [noradId])
  const [conjunctions, setConjunctions] = useState([])
  const [stats, setStats] = useState(EMPTY_STATS)
  const [loading, setLoading] = useState(false)
  const [selectedManeuverLabel, setSelectedManeuverLabel] = useState(null)

  useEffect(() => {
    if (!selectedNoradId) return   // wait for user to submit a NORAD ID
    let cancelled = false

    const load = async () => {
      setLoading(true)
      try {
        // Step 1 — fetch primary satellite TLE and info independently.
        // This succeeds even if there are 0 active conjunctions, so the globe
        // always renders the primary satellite when a NORAD ID is entered.
        const satInfo = await fetchSatellite(selectedNoradId)
        const primaryTle = {
          name:      satInfo.name,
          norad_id:  selectedNoradId,
          tle_line1: satInfo.tle_line1,
          tle_line2: satInfo.tle_line2,
          // Orbital params forwarded to SatelliteModal via dynMeta
          alt:         (satInfo.apoapsis_km != null && satInfo.periapsis_km != null)
                         ? Math.round((parseFloat(satInfo.apoapsis_km) + parseFloat(satInfo.periapsis_km)) / 2)
                         : null,
          inclination: satInfo.inclination_deg != null ? +parseFloat(satInfo.inclination_deg).toFixed(2) : null,
          period:      satInfo.period_min      != null ? +parseFloat(satInfo.period_min).toFixed(2)      : null,
          country:     satInfo.country_code    || null,
          launched:    satInfo.launch_date     || null,
          object_type: satInfo.object_type     || null,
        }

        // Step 2 — fetch conjunctions for threat satellites.
        const result = await fetchConjunctions({ noradId: selectedNoradId })

        if (!cancelled) {
          setPrimarySatTle(primaryTle)
          setConjunctions(result.conjunctions)
          setStats(result.stats)
          // Reset selection — event_ids from the old run are now invalid
          setSelectedConjunction(null)
          setSelectedManeuverLabel(null)

          // Build threat TLE list from conjunction secondaries (may be empty).
          const seen = new Set()
          const threatTles = result.conjunctions
            .filter(c => c.secondaryTleLine1 && c.secondaryTleLine2)
            .map(c => ({
              name:      c.secondarySatName,
              norad_id:  c.secondarySatId,
              tle_line1: c.secondaryTleLine1,
              tle_line2: c.secondaryTleLine2,
              // Orbital params forwarded to SatelliteModal via dynMeta
              alt:         (c.secondaryApoapsisKm != null && c.secondaryPeriapsisKm != null)
                             ? Math.round((parseFloat(c.secondaryApoapsisKm) + parseFloat(c.secondaryPeriapsisKm)) / 2)
                             : null,
              inclination: c.secondaryInclinationDeg != null ? +parseFloat(c.secondaryInclinationDeg).toFixed(2) : null,
              country:     c.secondaryCountryCode || null,
              launched:    c.secondaryLaunchDate  || null,
              object_type: 'satellite',
            }))
            .filter(t => { if (seen.has(t.norad_id)) return false; seen.add(t.norad_id); return true })

          console.log(
            `[DriftZero] NORAD ${selectedNoradId} — ${result.conjunctions.length} conjunction event(s),`,
            `${threatTles.length} unique threat satellite(s)`
          )

          // Render primary + threats on the globe.
          // threatTles may be [] (0 conjunctions) — _driftRenderConjunction handles
          // that correctly by removing any old threat satellites from the scene.
          // If Cesium is already up (typical on refresh), call directly to avoid
          // a 200ms poll delay and ensure the call isn't lost if `cancelled` flips
          // while a poll interval is still pending.
          const renderGlobe = () => window._driftRenderConjunction(primaryTle, threatTles)

          if (typeof window._driftRenderConjunction === 'function') {
            console.log(
              '[DriftZero] rendering', primaryTle.name, '+', threatTles.length, 'threats'
            )
            renderGlobe()
          } else {
            // First load: Cesium may still be initialising — poll until ready
            const started = Date.now()
            const globePoll = setInterval(() => {
              if (typeof window._driftRenderConjunction === 'function') {
                clearInterval(globePoll)
                console.log(
                  '[DriftZero] _driftRenderConjunction ready — rendering',
                  primaryTle.name, '+', threatTles.length, 'threats'
                )
                renderGlobe()
              } else if (Date.now() - started > 10_000) {
                clearInterval(globePoll)
                console.warn('[DriftZero] _driftRenderConjunction not found after 10s — Cesium may have failed to load')
              }
            }, 200)
          }
        }
      } catch (err) {
        console.error('[DriftZero] load failed:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    const interval = setInterval(load, 60_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [selectedNoradId])

  // Reset maneuver selection when conjunction changes
  const handleSelectConjunction = useCallback((c) => {
    setSelectedConjunction(c)
    setSelectedManeuverLabel(null)
  }, [])

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
      {/* ── StatsBar — top (hidden until activated) ─────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        pointerEvents: activated ? 'auto' : 'none',
        opacity: activated ? 1 : 0,
        transform: activated ? 'translateY(0)' : 'translateY(-100%)',
        transition: 'opacity 0.5s ease 0.4s, transform 0.5s ease 0.4s',
      }}>
        <StatsBar stats={stats} />
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
            /* ── Satellite selected: show satellite info panel ── */
            /* key forces remount + re-animation on each new satellite */
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
            /* ── Default: conjunction queue + detail panels ── */
            <>
              <AlertQueue
                conjunctions={conjunctions}
                selected={selectedConjunction}
                onSelect={handleSelectConjunction}
              />
              {selectedConjunction && (
                <>
                  <NaturalLanguageAlert conjunction={selectedConjunction} />
                  <ManeuverPanel
                    conjunction={selectedConjunction}
                    onManeuverSelect={setSelectedManeuverLabel}
                  />
                  <CascadeAnalysis
                    conjunction={selectedConjunction}
                    conjunctions={conjunctions}
                    selectedManeuverLabel={selectedManeuverLabel}
                  />
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Divider — hidden until activated ────────────────────────────────── */}
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
        {/* Always-visible collapse/expand tab */}
        <button
          onMouseDown={(e) => {
            e.stopPropagation()
            tabDragMoved.current = false
            // Start the drag — if mouse never moves, we treat it as a click
            setIsDragging(true)
            setCollapsed(null)
          }}
          onClick={(e) => {
            // Only toggle if the mousedown didn't turn into a real drag
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

      {/* Cursor style during drag */}
      {isDragging && (
        <style>{`* { cursor: col-resize !important; user-select: none !important; }`}</style>
      )}
    </>
  )
}
