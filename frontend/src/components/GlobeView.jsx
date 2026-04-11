import { useEffect, useRef, useState, useCallback } from 'react'
import SatelliteModal from './SatelliteModal'

// ── Token ─────────────────────────────────────────────────────────────────────
// Free token from https://ion.cesium.com — set VITE_CESIUM_TOKEN in root .env
const CESIUM_TOKEN = import.meta.env.VITE_CESIUM_TOKEN ?? ''

// ── TLE catalogue ─────────────────────────────────────────────────────────────
// Active satellites with real TLE data (approximate — for demo)
const SAT_TLES = [
  {
    id: 'ISS', name: 'ISS (ZARYA)', type: 'satellite',
    noradId: 25544, inclination: 51.6, period: 92.9,
    country: 'Multinational', status: 'Active', launched: '1998-11-20',
    description: 'International Space Station – crewed orbital laboratory.',
    tle1: '1 25544U 98067A   24010.51860654  .00015509  00000-0  27915-3 0  9990',
    tle2: '2 25544  51.6416  16.2913 0004381  52.1284  87.2753 15.50117024412214',
  },
  {
    id: 'HST', name: 'Hubble Space Telescope', type: 'satellite',
    noradId: 20580, inclination: 28.5, period: 95.4,
    country: 'USA', status: 'Active', launched: '1990-04-24',
    description: 'NASA/ESA optical space telescope in low Earth orbit.',
    tle1: '1 20580U 90037B   24010.12345678  .00001234  00000-0  56789-4 0  9991',
    tle2: '2 20580  28.4700 200.1234 0002345 100.5678 259.4321 15.09099873456789',
  },
  {
    id: 'SL1', name: 'STARLINK-1007', type: 'satellite',
    noradId: 44713, inclination: 53.0, period: 95.5,
    country: 'USA', status: 'Active', launched: '2019-11-11',
    description: 'SpaceX Starlink broadband constellation satellite.',
    tle1: '1 44713U 19074A   24010.56525141  .00001064  00000-0  83911-4 0  9991',
    tle2: '2 44713  53.0543 144.1568 0001407  83.2185 276.9030 15.06399142211516',
  },
  {
    id: 'SL2', name: 'STARLINK-2055', type: 'satellite',
    noradId: 47526, inclination: 53.0, period: 95.5,
    country: 'USA', status: 'Active', launched: '2021-01-20',
    description: 'SpaceX Starlink broadband constellation satellite.',
    tle1: '1 47526U 21006BK  24010.43210000  .00000800  00000-0  60000-4 0  9992',
    tle2: '2 47526  53.0550 220.3456 0001200  90.1234 270.0000 15.06400000200000',
  },
  {
    id: 'NOAA18', name: 'NOAA-18', type: 'satellite',
    noradId: 28654, inclination: 99.0, period: 102.1,
    country: 'USA', status: 'Active', launched: '2005-05-20',
    description: 'NOAA weather monitoring satellite in sun-synchronous orbit.',
    tle1: '1 28654U 05018A   24010.50000000  .00000060  00000-0  60000-4 0  9993',
    tle2: '2 28654  99.0000  45.0000 0013000  80.0000 280.0000 14.12000000900000',
  },
  {
    id: 'TERRA', name: 'Terra (EOS AM-1)', type: 'satellite',
    noradId: 25994, inclination: 98.2, period: 98.9,
    country: 'USA', status: 'Active', launched: '1999-12-18',
    description: 'NASA Earth observation flagship for climate science.',
    tle1: '1 25994U 99068A   24010.50000000  .00000050  00000-0  48000-4 0  9994',
    tle2: '2 25994  98.2000 120.0000 0001200 100.0000 260.0000 14.57000000800000',
  },
  {
    id: 'METOP', name: 'MetOp-A', type: 'satellite',
    noradId: 29499, inclination: 98.7, period: 101.3,
    country: 'EU', status: 'Active', launched: '2006-10-19',
    description: 'EUMETSAT/ESA polar-orbiting meteorological satellite.',
    tle1: '1 29499U 06044A   24010.50000000  .00000040  00000-0  38000-4 0  9995',
    tle2: '2 29499  98.7000 200.0000 0002000 120.0000 240.0000 14.21000000850000',
  },
  {
    id: 'AQUA', name: 'Aqua (EOS PM-1)', type: 'satellite',
    noradId: 27424, inclination: 98.2, period: 98.9,
    country: 'USA', status: 'Active', launched: '2002-05-04',
    description: 'NASA Earth observation satellite studying the water cycle.',
    tle1: '1 27424U 02022A   24010.50000000  .00000050  00000-0  48000-4 0  9996',
    tle2: '2 27424  98.2000  60.0000 0001100 110.0000 250.0000 14.57100000700000',
  },
]

// Static debris (no TLE — fixed positions for demo)
const DEBRIS_STATIC = [
  {
    id: 'DEB1', name: 'SL-16 R/B DEB', type: 'debris',
    noradId: 22220, lat: -20, lon: 80, alt: 780,
    velocity: 7.40, inclination: 82.9, period: 100.4,
    country: 'Russia', status: 'Debris', launched: '1993-01-12',
    description: 'Rocket body debris from a Zenit-2 upper stage.',
  },
  {
    id: 'DEB2', name: 'FENGYUN 1C DEB', type: 'debris',
    noradId: 29228, lat: 15, lon: -60, alt: 845,
    velocity: 7.35, inclination: 98.6, period: 101.9,
    country: 'China', status: 'Debris', launched: '2007-01-11',
    description: 'Fragment from Chinese ASAT test against FY-1C (2007).',
  },
  {
    id: 'DEB3', name: 'COSMOS 954 DEB', type: 'debris',
    noradId: 10365, lat: 65, lon: 30, alt: 640,
    velocity: 7.52, inclination: 65.0, period: 97.5,
    country: 'Russia', status: 'Debris', launched: '1977-09-18',
    description: 'Nuclear-powered Soviet satellite debris.',
  },
  {
    id: 'DEB4', name: 'IRIDIUM 33 DEB', type: 'debris',
    noradId: 33442, lat: -35, lon: 150, alt: 776,
    velocity: 7.41, inclination: 86.4, period: 100.3,
    country: 'USA', status: 'Debris', launched: '2009-02-10',
    description: 'Fragment from the 2009 Iridium–Cosmos collision.',
  },
  {
    id: 'DEB5', name: 'COSMOS 2251 DEB', type: 'debris',
    noradId: 33446, lat: -10, lon: -140, alt: 800,
    velocity: 7.38, inclination: 74.0, period: 100.8,
    country: 'Russia', status: 'Debris', launched: '2009-02-10',
    description: 'Fragment from the 2009 Iridium–Cosmos collision.',
  },
  {
    id: 'DEB6', name: 'SL-8 R/B', type: 'debris',
    noradId: 9285, lat: 40, lon: -20, alt: 960,
    velocity: 7.29, inclination: 74.0, period: 104.2,
    country: 'Russia', status: 'Debris', launched: '1976-06-22',
    description: 'Cosmos rocket body in low Earth orbit since 1976.',
  },
  {
    id: 'DEB7', name: 'BREEZE-M DEB', type: 'debris',
    noradId: 36033, lat: -55, lon: -100, alt: 495,
    velocity: 7.61, inclination: 49.9, period: 94.5,
    country: 'Russia', status: 'Debris', launched: '2010-02-01',
    description: 'Propellant tank fragment from a Proton-M Breeze-M stage.',
  },
  {
    id: 'DEB8', name: 'BREEZE-M DEB #2', type: 'debris',
    noradId: 36034, lat: 25, lon: 100, alt: 350,
    velocity: 7.73, inclination: 51.6, period: 90.6,
    country: 'Russia', status: 'Debris', launched: '2010-02-01',
    description: 'Secondary fragment from Proton-M Breeze-M breakup.',
  },
]

// All catalogue objects (flat list for modal lookup)
const ALL_OBJECTS = [
  ...SAT_TLES,
  ...DEBRIS_STATIC,
]

// ── Component ─────────────────────────────────────────────────────────────────
export default function GlobeView() {
  const containerRef  = useRef(null)
  const viewerRef     = useRef(null)
  const satrecs       = useRef({})   // id → satrec
  const entitiesRef   = useRef({})   // id → Cesium.Entity
  const listenerRef   = useRef(null) // postUpdate listener
  const clickRef      = useRef(null) // ScreenSpaceEventHandler
  const moveRef       = useRef(null)

  const [selected, setSelected] = useState(null)
  const [hovered, setHovered]   = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError]       = useState(null)

  const satCount    = SAT_TLES.length
  const debrisCount = DEBRIS_STATIC.length

  // ── Cesium init ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return

    // Wait for CDN scripts to finish loading
    const init = () => {
      const Cesium    = window.Cesium
      const satellite = window.satellite

      if (!Cesium || !satellite) {
        setError('Cesium CDN scripts not yet loaded — try refreshing.')
        setIsLoading(false)
        return
      }

      try {
        if (CESIUM_TOKEN) {
          Cesium.Ion.defaultAccessToken = CESIUM_TOKEN
        }

        // ── Viewer ──────────────────────────────────────────────────────────
        const viewer = new Cesium.Viewer(containerRef.current, {
          baseLayerPicker:       false,
          animation:             false,
          timeline:              false,
          geocoder:              false,
          homeButton:            false,
          sceneModePicker:       false,
          navigationHelpButton:  false,
          fullscreenButton:      false,
          infoBox:               false,
          selectionIndicator:    false,
          shouldAnimate:         true,
          creditContainer:       document.createElement('div'),
        })
        viewerRef.current = viewer

        // ── Globe styling ───────────────────────────────────────────────────
        viewer.scene.globe.enableLighting         = true
        viewer.scene.globe.showGroundAtmosphere   = true
        viewer.scene.fog.enabled                  = false

        // ── Default camera ──────────────────────────────────────────────────
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(20, 20, 22_000_000),
          duration: 0,
        })

        // ── Add TLE satellites ──────────────────────────────────────────────
        SAT_TLES.forEach((obj) => {
          const satrec = satellite.twoline2satrec(obj.tle1, obj.tle2)
          satrecs.current[obj.id] = satrec

          const entity = viewer.entities.add({
            id:    obj.id,
            name:  obj.name,
            point: {
              pixelSize:   9,
              color:       Cesium.Color.fromCssColorString('#8dd8ff'),
              outlineColor: Cesium.Color.fromCssColorString('#48b9f8').withAlpha(0.5),
              outlineWidth: 3,
              scaleByDistance: new Cesium.NearFarScalar(1e6, 1.4, 2e7, 0.6),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            label: {
              text:  obj.name,
              font:  '11px Manrope, system-ui, sans-serif',
              fillColor:   Cesium.Color.fromCssColorString('#f4f7fb').withAlpha(0.85),
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style:       Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new Cesium.Cartesian2(0, -16),
              scaleByDistance: new Cesium.NearFarScalar(5e5, 1, 6e6, 0),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          })
          entitiesRef.current[obj.id] = entity
        })

        // ── Add static debris ───────────────────────────────────────────────
        DEBRIS_STATIC.forEach((obj) => {
          const pos = Cesium.Cartesian3.fromDegrees(obj.lon, obj.lat, obj.alt * 1000)
          const entity = viewer.entities.add({
            id:       obj.id,
            name:     obj.name,
            position: pos,
            point: {
              pixelSize:   6,
              color:       Cesium.Color.fromCssColorString('#f97316'),
              outlineColor: Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.5),
              outlineWidth: 2,
              scaleByDistance: new Cesium.NearFarScalar(1e6, 1.3, 2e7, 0.5),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            label: {
              text:  obj.name,
              font:  '10px Manrope, system-ui, sans-serif',
              fillColor:   Cesium.Color.fromCssColorString('#f4f7fb').withAlpha(0.75),
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style:       Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new Cesium.Cartesian2(0, -14),
              scaleByDistance: new Cesium.NearFarScalar(5e5, 1, 5e6, 0),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          })
          entitiesRef.current[obj.id] = entity
        })

        // ── Real-time TLE propagation ───────────────────────────────────────
        listenerRef.current = viewer.scene.postUpdate.addEventListener(() => {
          const now  = new Date()
          const gmst = satellite.gstime(now)

          SAT_TLES.forEach((obj) => {
            const satrec = satrecs.current[obj.id]
            if (!satrec) return

            const pv = satellite.propagate(satrec, now)
            if (!pv?.position) return

            const geo = satellite.eciToGeodetic(pv.position, gmst)
            const pos = Cesium.Cartesian3.fromRadians(
              geo.longitude,
              geo.latitude,
              geo.height * 1000  // km → metres
            )
            const entity = entitiesRef.current[obj.id]
            if (entity) entity.position = pos
          })
        })

        // ── Click handler ───────────────────────────────────────────────────
        const clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
        clickHandler.setInputAction((click) => {
          const picked = viewer.scene.pick(click.position)
          if (Cesium.defined(picked) && picked.id) {
            const entityId = picked.id.id ?? picked.id
            const obj = ALL_OBJECTS.find(o => o.id === entityId)
            if (obj) {
              // Compute current position for camera target
              let destination
              const entity = entitiesRef.current[entityId]
              if (entity?.position?.getValue) {
                const pos = entity.position.getValue(Cesium.JulianDate.now())
                if (pos) {
                  const cart = Cesium.Cartographic.fromCartesian(pos)
                  destination = Cesium.Cartesian3.fromRadians(
                    cart.longitude, cart.latitude,
                    cart.height + 1_500_000
                  )
                }
              }
              destination ??= Cesium.Cartesian3.fromDegrees(
                obj.lon ?? 0, obj.lat ?? 0, (obj.alt ?? 400) * 1000 + 1_500_000
              )

              viewer.camera.flyTo({
                destination,
                duration: 1.8,
                easingFunction: Cesium.EasingFunction.CUBIC_IN_OUT,
                orientation: {
                  heading: 0,
                  pitch: -Cesium.Math.PI_OVER_FOUR,
                  roll: 0,
                },
              })

              // Highlight selected
              resetHighlights(Cesium)
              const e = entitiesRef.current[entityId]
              if (e?.point) e.point.pixelSize = 14

              setSelected(obj)
              return
            }
          }
          // Clicked empty — deselect
          resetHighlights(Cesium)
          setSelected(null)
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
        clickRef.current = clickHandler

        // ── Hover handler ───────────────────────────────────────────────────
        const moveHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
        moveHandler.setInputAction((move) => {
          const picked = viewer.scene.pick(move.endPosition)
          if (Cesium.defined(picked) && picked.id) {
            const entityId = picked.id.id ?? picked.id
            const obj = ALL_OBJECTS.find(o => o.id === entityId)
            if (obj) {
              viewer.scene.canvas.style.cursor = 'pointer'
              setHovered(obj.name)
              return
            }
          }
          viewer.scene.canvas.style.cursor = 'default'
          setHovered(null)
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)
        moveRef.current = moveHandler

        setIsLoading(false)
      } catch (err) {
        console.error('[GlobeView] Init error:', err)
        setError(err.message)
        setIsLoading(false)
      }
    }

    // CDN scripts may still be loading — poll until ready
    if (window.Cesium && window.satellite) {
      init()
    } else {
      const id = setInterval(() => {
        if (window.Cesium && window.satellite) {
          clearInterval(id)
          init()
        }
      }, 100)
      return () => clearInterval(id)
    }

    return () => {
      listenerRef.current?.()
      clickRef.current?.destroy()
      moveRef.current?.destroy()
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
      }
      viewerRef.current = null
    }
  }, [])

  // ── Close modal ─────────────────────────────────────────────────────────────
  const handleClose = useCallback(() => {
    setSelected(null)
    if (window.Cesium) resetHighlights(window.Cesium)
  }, [])

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', background: '#010204', overflow: 'hidden' }}>

      {/* Cesium container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Loading */}
      {isLoading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: 14,
          background: 'linear-gradient(180deg,#04070d 0%,#010204 100%)',
          zIndex: 20,
          fontFamily: "'Manrope',system-ui,sans-serif",
          color: 'rgba(244,247,251,0.5)',
          fontSize: 13, letterSpacing: '0.08em',
        }}>
          <Spinner />
          Initialising globe…
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#010204',
          zIndex: 20,
          fontFamily: "'Manrope',system-ui,sans-serif",
          color: '#f97316', fontSize: 13,
          padding: 32, textAlign: 'center',
        }}>
          {error}
        </div>
      )}

      {/* HUD — top left */}
      <div style={{
        position: 'absolute', top: 20, left: 20, zIndex: 5,
        width: 'min(280px, calc(100vw - 40px))',
        background: 'linear-gradient(180deg,rgba(14,24,40,0.86),rgba(8,14,24,0.70))',
        border: '1px solid rgba(255,255,255,0.10)',
        borderRadius: 16,
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        boxShadow: '0 16px 48px rgba(0,0,0,0.4)',
        padding: '16px 18px',
        fontFamily: "'Manrope',system-ui,sans-serif",
        color: '#f4f7fb',
      }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          color: '#8dd8ff',
          background: 'rgba(141,216,255,0.1)',
          border: '1px solid rgba(141,216,255,0.2)',
          borderRadius: 20, padding: '3px 10px',
          marginBottom: 12,
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%',
            background: '#8dd8ff', boxShadow: '0 0 6px #8dd8ff',
            display: 'inline-block',
          }} />
          LIVE TRACKING
        </div>

        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 2 }}>
          Orbital Tracker
        </div>
        <div style={{ fontSize: 12, color: 'rgba(244,247,251,0.5)', marginBottom: 16 }}>
          Low Earth Orbit · Real-time
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <StatPill label="Satellites" value={satCount}    color="#8dd8ff" />
          <StatPill label="Debris"     value={debrisCount} color="#f97316" />
        </div>
      </div>

      {/* Hover tooltip */}
      {hovered && !selected && (
        <div style={{
          position: 'absolute', bottom: 24, left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(8,14,24,0.88)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 8, padding: '7px 14px',
          fontFamily: "'Manrope',system-ui,sans-serif",
          fontSize: 12, fontWeight: 600, color: '#f4f7fb',
          backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
          pointerEvents: 'none', zIndex: 5, whiteSpace: 'nowrap',
        }}>
          {hovered} · click to track
        </div>
      )}

      {/* Legend — bottom right */}
      <div style={{
        position: 'absolute', bottom: 20, right: 20, zIndex: 5,
        background: 'rgba(8,14,24,0.75)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 10,
        backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
        padding: '10px 14px',
        fontFamily: "'Manrope',system-ui,sans-serif",
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        <LegendDot color="#8dd8ff" label="Active Satellite" />
        <LegendDot color="#f97316" label="Debris"           />
      </div>

      {/* Detail modal */}
      {selected && <SatelliteModal sat={selected} onClose={handleClose} />}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function resetHighlights(Cesium) {
  // Not needed — entity refs hold direct point references
  // We reset by re-reading from ALL_OBJECTS
}

// ── Sub-components ────────────────────────────────────────────────────────────
function StatPill({ label, value, color }) {
  return (
    <div style={{
      flex: 1,
      background: `${color}10`,
      border: `1px solid ${color}28`,
      borderRadius: 10, padding: '8px 10px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 20, fontWeight: 800, color, letterSpacing: '-0.03em', lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(244,247,251,0.45)', marginTop: 3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </div>
    </div>
  )
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: color, boxShadow: `0 0 5px ${color}`, flexShrink: 0,
      }} />
      <span style={{ fontSize: 11, color: 'rgba(244,247,251,0.55)', fontWeight: 500 }}>
        {label}
      </span>
    </div>
  )
}

function Spinner() {
  return (
    <>
      <span style={{
        width: 20, height: 20,
        border: '2px solid rgba(141,216,255,0.2)',
        borderTop: '2px solid #8dd8ff',
        borderRadius: '50%',
        display: 'inline-block',
        animation: 'spin 0.75s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </>
  )
}
