import { StrictMode, useState, useEffect, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import GlobeView from './components/GlobeView'
import DashboardOverlay from './App.jsx'
import LandingOverlay from './components/LandingOverlay.jsx'
import { demoGlobeObjects, rogueActorPositions } from './data/mockData.js'
import { satStore } from './satStore.js'

// Map NORAD ID → GlobeView entity ID (from SAT_TLES in GlobeView.jsx)
const NORAD_TO_ENTITY_ID = {
  25544: 'ISS',
  20580: 'HST',
  44713: 'SL1',
  47526: 'SL2',
  28654: 'NOAA18',
  25994: 'TERRA',
  29499: 'METOP',
  27424: 'AQUA',
}

// All entity IDs that belong to GlobeView (sats + debris)
// ManeuverPanel/analysis entities have auto-generated UUID ids and won't match these
// NOTE: rogue actor IDs (ROGUE_*) are intentionally excluded — their visibility is
// controlled entirely by DashboardOverlay during conjunction analysis.
const GLOBE_ENTITY_IDS = new Set([
  'ISS', 'HST', 'SL1', 'SL2', 'NOAA18', 'TERRA', 'METOP', 'AQUA',
  ...Array.from({ length: 28 }, (_, i) => `DEB${i + 1}`),
  ...demoGlobeObjects.map(o => o.id),
])

// Debris entity IDs (static DEB1-DEB28 + demo DEMO_DEB_* objects)
const isDebrisId = (id) => /^DEB\d+$/.test(id) || id.startsWith('DEMO_DEB_')

function App() {
  const [activated, setActivated] = useState(false)
  const [landingMounted, setLandingMounted] = useState(true)
  const [activeNoradId, setActiveNoradId] = useState(25544)
  const [demoMode, setDemoMode] = useState(false)
  const [focusedEntityId, setFocusedEntityId] = useState(null)
  const [showAllSats, setShowAllSats] = useState(false)
  const demoEntitiesRef = useRef([])
  const rogueEntitiesRef = useRef([])
  const selectedRogueIdRef = useRef(null)  // currently highlighted rogue entity ID
  const [trackedNoradId, setTrackedNoradId] = useState(null)

  // Hide entities + start globe rotation on load, stop on activate
  useEffect(() => {
    let rafId = null

    const poll = setInterval(() => {
      if (window._driftViewer) {
        clearInterval(poll)
        const viewer = window._driftViewer
        viewer.entities.values.forEach(e => { e.show = false })
        window._driftSpinning = true
        const spin = () => {
          if (window._driftSpinning && !viewer.isDestroyed()) {
            viewer.camera.rotateRight(0.003)
            rafId = requestAnimationFrame(spin)
          }
        }
        rafId = requestAnimationFrame(spin)
      }
    }, 200)

    return () => {
      window._driftSpinning = false
      clearInterval(poll)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  useEffect(() => {
    if (activated) window._driftSpinning = false
  }, [activated])

  // Sync entity visibility whenever showAllSats or focusedEntityId changes
  useEffect(() => {
    if (!activated) return
    const viewer = window._driftViewer
    if (!viewer || viewer.isDestroyed()) return
    viewer.entities.values.forEach(e => {
      if (!GLOBE_ENTITY_IDS.has(e.id)) return // leave ManeuverPanel/analysis + rogue entities alone
      e.show = showAllSats || !focusedEntityId || e.id === focusedEntityId || isDebrisId(e.id)
    })
  }, [showAllSats, focusedEntityId, activated])

  // Add extra satellites + debris to globe in demo mode
  useEffect(() => {
    if (!activated || !demoMode) return
    const viewer = window._driftViewer
    const Cesium = window.Cesium
    if (!viewer || viewer.isDestroyed() || !Cesium) return

    // Remove any previously added demo entities
    demoEntitiesRef.current.forEach(e => {
      if (!viewer.isDestroyed()) try { viewer.entities.remove(e) } catch {}
    })
    demoEntitiesRef.current = []

    demoGlobeObjects.forEach(obj => {
      const pos = Cesium.Cartesian3.fromDegrees(obj.lon, obj.lat, obj.alt * 1000)
      const isSat = obj.type === 'satellite'
      const entity = viewer.entities.add({
        id:       obj.id,
        name:     obj.name,
        position: pos,
        point: {
          pixelSize:                isSat ? 8 : 6,
          color:                    isSat
            ? Cesium.Color.fromCssColorString('#8dd8ff')
            : Cesium.Color.fromCssColorString('#f97316'),
          outlineColor:             isSat
            ? Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.4)
            : Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.4),
          outlineWidth:             2,
          scaleByDistance:          new Cesium.NearFarScalar(1e6, 1.2, 2e7, 0.5),
          disableDepthTestDistance: 0,
        },
        label: isSat ? {
          text:             obj.name,
          font:             '10px Manrope, system-ui, sans-serif',
          fillColor:        Cesium.Color.fromCssColorString('#f4f7fb').withAlpha(0.75),
          outlineColor:     Cesium.Color.BLACK,
          outlineWidth:     2,
          style:            Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset:      new Cesium.Cartesian2(0, -14),
          scaleByDistance:  new Cesium.NearFarScalar(5e5, 1, 5e6, 0),
          disableDepthTestDistance: 0,
        } : undefined,
      })
      // In non-showAll mode, hide demo objects by default unless they're the focused one
      entity.show = showAllSats || !focusedEntityId
      demoEntitiesRef.current.push(entity)
    })
  }, [activated, demoMode])

  // Add adversarial/suspicious rogue actors to globe in demo mode
  useEffect(() => {
    if (!activated || !demoMode) return
    const viewer = window._driftViewer
    const Cesium = window.Cesium
    if (!viewer || viewer.isDestroyed() || !Cesium) return

    rogueEntitiesRef.current.forEach(e => {
      if (!viewer.isDestroyed()) try { viewer.entities.remove(e) } catch {}
    })
    rogueEntitiesRef.current = []

    rogueActorPositions.forEach(obj => {
      const pos = Cesium.Cartesian3.fromDegrees(obj.lon, obj.lat, obj.alt * 1000)
      const isAdversarial = obj.severity === 'ADVERSARIAL'
      const dotColor   = isAdversarial ? '#ef4444' : '#f59e0b'
      const labelColor = isAdversarial ? '#fca5a5' : '#fde68a'
      const entity = viewer.entities.add({
        id:       obj.id,
        name:     obj.name,
        position: pos,
        point: {
          pixelSize:                isAdversarial ? 16 : 12,
          color:                    Cesium.Color.fromCssColorString(dotColor),
          outlineColor:             Cesium.Color.fromCssColorString(dotColor).withAlpha(0.55),
          outlineWidth:             isAdversarial ? 5 : 3,
          scaleByDistance:          new Cesium.NearFarScalar(1e6, 1.4, 2e7, 0.6),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text:                     `${obj.name}\n${obj.severity}`,
          font:                     `${isAdversarial ? 'bold ' : ''}10px Manrope, system-ui, sans-serif`,
          fillColor:                Cesium.Color.fromCssColorString(labelColor).withAlpha(0.92),
          outlineColor:             Cesium.Color.BLACK,
          outlineWidth:             2,
          style:                    Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset:              new Cesium.Cartesian2(0, -18),
          scaleByDistance:          new Cesium.NearFarScalar(5e5, 1, 8e6, 0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          showBackground:           isAdversarial,
          backgroundColor:          isAdversarial
            ? Cesium.Color.fromCssColorString('#ef4444').withAlpha(0.15)
            : undefined,
          backgroundPadding: isAdversarial ? new Cesium.Cartesian2(5, 3) : undefined,
        },
      })
      entity.show = false  // hidden by default; DashboardOverlay shows them during analysis
      rogueEntitiesRef.current.push(entity)
    })
  }, [activated, demoMode])

  // Click handler for rogue actor entities — highlight + dispatch event to dashboard
  useEffect(() => {
    if (!activated) return
    const viewer = window._driftViewer
    const Cesium = window.Cesium
    if (!viewer || viewer.isDestroyed() || !Cesium) return

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)

    handler.setInputAction((click) => {
      const picked = viewer.scene.pick(click.position)
      const entityId = picked?.id?.id
      if (!entityId) return

      const rogue = rogueActorPositions.find(r => r.id === entityId)
      if (!rogue) return

      const isAdv = rogue.severity === 'ADVERSARIAL'
      const dotColor = isAdv ? '#ef4444' : '#f59e0b'

      // Unhighlight previous selection
      const prevId = selectedRogueIdRef.current
      if (prevId && prevId !== entityId) {
        const prevRogue = rogueActorPositions.find(r => r.id === prevId)
        const prevEnt   = viewer.entities.getById(prevId)
        if (prevEnt && prevRogue) {
          const wasAdv = prevRogue.severity === 'ADVERSARIAL'
          prevEnt.point.pixelSize   = wasAdv ? 16 : 12
          prevEnt.point.outlineWidth = wasAdv ? 5 : 3
          prevEnt.point.color = Cesium.Color.fromCssColorString(wasAdv ? '#ef4444' : '#f59e0b')
        }
      }

      // Highlight selected entity — white ring + enlarged
      const ent = viewer.entities.getById(entityId)
      if (ent) {
        ent.point.pixelSize    = isAdv ? 24 : 20
        ent.point.outlineWidth = 8
        ent.point.outlineColor = Cesium.Color.WHITE.withAlpha(0.9)
        ent.point.color        = Cesium.Color.fromCssColorString(dotColor)
      }
      selectedRogueIdRef.current = entityId

      // Notify DashboardOverlay
      window.dispatchEvent(new CustomEvent('drift-rogue-click', { detail: rogue }))
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    return () => { try { handler.destroy() } catch {} }
  }, [activated])

  const handleRetarget = (noradId, entityId = null) => {
    const numId = Number(noradId)
    if (!numId || isNaN(numId)) return
    const newEntityId = entityId ?? (NORAD_TO_ENTITY_ID[numId] ?? null)
    setActiveNoradId(numId)
    setFocusedEntityId(newEntityId)
    // Zoom globe to new satellite
    setTimeout(() => window._driftFocusSat?.(numId), 100)
    // If called from the search bar (no entityId from globe click), clear the
    // previously selected satellite so focusedSatId derives from the new noradId,
    // not from a stale globe-click selection.
    if (!entityId) {
      satStore.close()
    }
  }

  const handleActivate = (noradId, demo = false) => {
    setDemoMode(demo)
    const entityId = noradId ? (NORAD_TO_ENTITY_ID[Number(noradId)] ?? null) : null
    setFocusedEntityId(entityId)

    const viewer = window._driftViewer
    if (viewer && !viewer.isDestroyed()) {
      viewer.entities.values.forEach(e => {
        if (!GLOBE_ENTITY_IDS.has(e.id)) { e.show = true; return }
        // Show the focused satellite + all debris; hide other sats
        e.show = !entityId || e.id === entityId || isDebrisId(e.id)
      })
    }

    if (noradId) {
      setTimeout(() => window._driftFocusSat?.(noradId), 100)
    }
    // Store the entered NORAD ID so DashboardOverlay can run the pipeline for it
    const parsed = parseInt(noradId, 10)
    if (!isNaN(parsed) && parsed > 0) setTrackedNoradId(parsed)
    setActivated(true)
    setTimeout(() => setLandingMounted(false), 1000)
  }

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>

      {/* Globe — rotates on landing, shifts left when dashboard panels open */}
      <div style={{
        position: 'absolute', inset: 0,
        transform: activated
          ? 'translateX(calc(var(--panel-pct, 30) * -0.5vw))'
          : 'translateX(-18vw)',
        transition: activated
          ? 'var(--panel-transition, transform 0.8s ease)'
          : 'transform 1s ease',
      }}>
        <GlobeView />

        {/* Show All Satellites button — positioned after GlobeView's bottom-left controls */}
        {activated && (
          <div style={{
            position: 'absolute', bottom: 20, left: 244, zIndex: 10,
            fontFamily: "'Manrope',system-ui,sans-serif",
          }}>
            <button
              onClick={() => setShowAllSats(v => !v)}
              title={showAllSats ? 'Show only tracked satellite' : 'Show all satellites and debris'}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '0 14px', height: 36,
                border: `1px solid ${showAllSats ? 'rgba(34,211,238,0.7)' : 'rgba(255,255,255,0.28)'}`,
                borderRadius: 8,
                background: showAllSats ? 'rgba(34,211,238,0.15)' : 'rgba(10,16,30,0.82)',
                color: showAllSats ? '#22d3ee' : 'rgba(244,247,251,0.88)',
                cursor: 'pointer', fontSize: 12, fontWeight: 600, fontFamily: 'inherit',
                letterSpacing: '0.02em',
                backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
                boxShadow: '0 2px 12px rgba(0,0,0,0.5)',
                transition: 'all 0.18s',
              }}
              onMouseEnter={e => {
                if (!showAllSats) {
                  e.currentTarget.style.background = 'rgba(34,211,238,0.1)'
                  e.currentTarget.style.color = '#22d3ee'
                  e.currentTarget.style.borderColor = 'rgba(34,211,238,0.5)'
                }
              }}
              onMouseLeave={e => {
                if (!showAllSats) {
                  e.currentTarget.style.background = 'rgba(10,16,30,0.82)'
                  e.currentTarget.style.color = 'rgba(244,247,251,0.88)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.28)'
                }
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.4" />
                <circle cx="7" cy="7" r="2.5" fill="currentColor" />
                <line x1="7" y1="1" x2="7" y2="3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="7" y1="10.5" x2="7" y2="13" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="1" y1="7" x2="3.5" y2="7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="10.5" y1="7" x2="13" y2="7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              {showAllSats ? 'Focused Only' : 'All Satellites'}
            </button>
          </div>
        )}
      </div>

      {/* Dashboard — slides in after activation */}
      <StrictMode>
        <DashboardOverlay activated={activated} noradId={activeNoradId} demo={demoMode} showAll={showAllSats} onRetarget={handleRetarget} />
        <DashboardOverlay activated={activated} noradId={trackedNoradId} />
      </StrictMode>

      {/* Mask GlobeView's own UI chrome during landing */}
      {landingMounted && !activated && (
        <>
          {/* Top bar mask */}
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0,
            height: 52, zIndex: 49,
            background: 'rgba(1,4,12,0.96)',
            pointerEvents: 'none',
          }} />
          {/* Bottom-left controls mask */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0,
            width: 220, height: 60, zIndex: 49,
            background: 'rgba(1,4,12,0.96)',
            pointerEvents: 'none',
          }} />
          {/* Bottom-right controls mask */}
          <div style={{
            position: 'absolute', bottom: 0, right: 0,
            width: 160, height: 60, zIndex: 49,
            background: 'rgba(1,4,12,0.96)',
            pointerEvents: 'none',
          }} />
        </>
      )}

      {/* Landing overlay — unmounts after transition */}
      {landingMounted && (
        <LandingOverlay onActivate={handleActivate} />
      )}

    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
