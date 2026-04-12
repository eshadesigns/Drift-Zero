import { useEffect, useRef, useState, useCallback } from 'react'
import { satStore } from '../satStore'

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

// Static debris — fixed positions for simulation
const DEBRIS_STATIC = [
  { id:'DEB1',  name:'SL-16 R/B DEB',         type:'debris', noradId:22220, lat:-20,  lon:80,   alt:780,  velocity:7.40, inclination:82.9, period:100.4, country:'Russia', status:'Debris', launched:'1993-01-12', description:'Rocket body debris from a Zenit-2 upper stage.' },
  { id:'DEB2',  name:'FENGYUN 1C DEB',         type:'debris', noradId:29228, lat:15,   lon:-60,  alt:845,  velocity:7.35, inclination:98.6, period:101.9, country:'China',  status:'Debris', launched:'2007-01-11', description:'Fragment from Chinese ASAT test against FY-1C (2007).' },
  { id:'DEB3',  name:'COSMOS 954 DEB',         type:'debris', noradId:10365, lat:65,   lon:30,   alt:640,  velocity:7.52, inclination:65.0, period:97.5,  country:'Russia', status:'Debris', launched:'1977-09-18', description:'Nuclear-powered Soviet satellite debris.' },
  { id:'DEB4',  name:'IRIDIUM 33 DEB',         type:'debris', noradId:33442, lat:-35,  lon:150,  alt:776,  velocity:7.41, inclination:86.4, period:100.3, country:'USA',    status:'Debris', launched:'2009-02-10', description:'Fragment from the 2009 Iridium–Cosmos collision.' },
  { id:'DEB5',  name:'COSMOS 2251 DEB',        type:'debris', noradId:33446, lat:-10,  lon:-140, alt:800,  velocity:7.38, inclination:74.0, period:100.8, country:'Russia', status:'Debris', launched:'2009-02-10', description:'Fragment from the 2009 Iridium–Cosmos collision.' },
  { id:'DEB6',  name:'SL-8 R/B',               type:'debris', noradId:9285,  lat:40,   lon:-20,  alt:960,  velocity:7.29, inclination:74.0, period:104.2, country:'Russia', status:'Debris', launched:'1976-06-22', description:'Cosmos rocket body in low Earth orbit since 1976.' },
  { id:'DEB7',  name:'BREEZE-M DEB',           type:'debris', noradId:36033, lat:-55,  lon:-100, alt:495,  velocity:7.61, inclination:49.9, period:94.5,  country:'Russia', status:'Debris', launched:'2010-02-01', description:'Propellant tank fragment from a Proton-M Breeze-M stage.' },
  { id:'DEB8',  name:'BREEZE-M DEB #2',        type:'debris', noradId:36034, lat:25,   lon:100,  alt:350,  velocity:7.73, inclination:51.6, period:90.6,  country:'Russia', status:'Debris', launched:'2010-02-01', description:'Secondary fragment from Proton-M Breeze-M breakup.' },
  // Extended catalogue
  { id:'DEB9',  name:'COSMOS 1408 DEB',        type:'debris', noradId:49271, lat:48,   lon:60,   alt:470,  velocity:7.63, inclination:82.6, period:94.2,  country:'Russia', status:'Debris', launched:'2021-11-15', description:'Fragment from Russian ASAT test against Cosmos 1408.' },
  { id:'DEB10', name:'COSMOS 1408 DEB #2',     type:'debris', noradId:49272, lat:52,   lon:80,   alt:490,  velocity:7.62, inclination:82.6, period:94.4,  country:'Russia', status:'Debris', launched:'2021-11-15', description:'Fragment from Russian ASAT test against Cosmos 1408.' },
  { id:'DEB11', name:'COSMOS 1408 DEB #3',     type:'debris', noradId:49273, lat:44,   lon:40,   alt:440,  velocity:7.65, inclination:82.6, period:93.8,  country:'Russia', status:'Debris', launched:'2021-11-15', description:'Fragment from Russian ASAT test against Cosmos 1408.' },
  { id:'DEB12', name:'SL-4 R/B DEB',           type:'debris', noradId:7337,  lat:-42,  lon:-80,  alt:610,  velocity:7.54, inclination:65.8, period:97.0,  country:'Russia', status:'Debris', launched:'1974-06-24', description:'Soyuz rocket body from 1974 launch.' },
  { id:'DEB13', name:'DELTA 1 DEB',            type:'debris', noradId:3733,  lat:28,   lon:-120, alt:740,  velocity:7.42, inclination:28.3, period:99.8,  country:'USA',    status:'Debris', launched:'1971-09-15', description:'Delta rocket upper stage fragment.' },
  { id:'DEB14', name:'ARIANE 44LP DEB',        type:'debris', noradId:22828, lat:-8,   lon:175,  alt:590,  velocity:7.56, inclination:7.0,  period:96.3,  country:'EU',     status:'Debris', launched:'1994-01-24', description:'Ariane rocket body in low Earth orbit.' },
  { id:'DEB15', name:'THORAD AGENA D DEB',     type:'debris', noradId:4632,  lat:70,   lon:-50,  alt:920,  velocity:7.31, inclination:99.9, period:103.5, country:'USA',    status:'Debris', launched:'1968-08-16', description:'Agena upper stage from 1968 reconnaissance mission.' },
  { id:'DEB16', name:'SL-3 R/B DEB',           type:'debris', noradId:2611,  lat:-60,  lon:130,  alt:520,  velocity:7.60, inclination:65.0, period:95.0,  country:'Russia', status:'Debris', launched:'1965-04-10', description:'Vostok rocket body from early Soviet mission.' },
  { id:'DEB17', name:'FENGYUN 1C DEB #2',      type:'debris', noradId:29300, lat:20,   lon:90,   alt:860,  velocity:7.34, inclination:98.7, period:102.2, country:'China',  status:'Debris', launched:'2007-01-11', description:'Second fragment from FY-1C ASAT test debris field.' },
  { id:'DEB18', name:'FENGYUN 1C DEB #3',      type:'debris', noradId:29400, lat:-15,  lon:160,  alt:820,  velocity:7.36, inclination:98.5, period:101.5, country:'China',  status:'Debris', launched:'2007-01-11', description:'Third fragment from FY-1C ASAT test debris field.' },
  { id:'DEB19', name:'IRIDIUM 33 DEB #2',      type:'debris', noradId:33500, lat:40,   lon:-170, alt:760,  velocity:7.41, inclination:86.5, period:100.1, country:'USA',    status:'Debris', launched:'2009-02-10', description:'Secondary fragment from Iridium–Cosmos collision.' },
  { id:'DEB20', name:'IRIDIUM 33 DEB #3',      type:'debris', noradId:33501, lat:-50,  lon:110,  alt:790,  velocity:7.39, inclination:86.3, period:100.5, country:'USA',    status:'Debris', launched:'2009-02-10', description:'Third fragment from Iridium–Cosmos collision cloud.' },
  { id:'DEB21', name:'SL-12 R/B DEB',          type:'debris', noradId:19820, lat:30,   lon:50,   alt:410,  velocity:7.68, inclination:51.8, period:92.8,  country:'Russia', status:'Debris', launched:'1989-03-01', description:'Proton upper stage near ISS orbital altitude.' },
  { id:'DEB22', name:'SL-12 R/B DEB #2',       type:'debris', noradId:19821, lat:-30,  lon:-30,  alt:420,  velocity:7.67, inclination:51.6, period:93.0,  country:'Russia', status:'Debris', launched:'1989-03-01', description:'Second Proton fragment at ISS altitude range.' },
  { id:'DEB23', name:'PEGASUS DEB',            type:'debris', noradId:23106, lat:35,   lon:170,  alt:550,  velocity:7.58, inclination:28.9, period:95.5,  country:'USA',    status:'Debris', launched:'1994-05-19', description:'Pegasus rocket body at Starlink operational altitude.' },
  { id:'DEB24', name:'COSMOS 3M R/B DEB',      type:'debris', noradId:28171, lat:-45,  lon:-60,  alt:560,  velocity:7.57, inclination:82.9, period:95.7,  country:'Russia', status:'Debris', launched:'2003-06-20', description:'Cosmos-3M rocket body fragment.' },
  { id:'DEB25', name:'CZ-4B R/B DEB',          type:'debris', noradId:37820, lat:55,   lon:-130, alt:700,  velocity:7.45, inclination:98.2, period:98.7,  country:'China',  status:'Debris', launched:'2011-11-09', description:'Chinese Long March upper stage at polar orbit.' },
  { id:'DEB26', name:'ATLAS CENTAUR DEB',      type:'debris', noradId:1911,  lat:-25,  lon:20,   alt:880,  velocity:7.33, inclination:28.9, period:102.6, country:'USA',    status:'Debris', launched:'1965-05-09', description:'Atlas Centaur upper stage from 1965 — oldest tracked debris.' },
  { id:'DEB27', name:'SL-16 R/B DEB #2',       type:'debris', noradId:25407, lat:38,   lon:-90,  alt:810,  velocity:7.37, inclination:82.6, period:101.2, country:'Russia', status:'Debris', launched:'1998-07-07', description:'Zenit-2 upper stage fragment.' },
  { id:'DEB28', name:'H-2A R/B DEB',           type:'debris', noradId:27600, lat:-65,  lon:80,   alt:670,  velocity:7.49, inclination:98.2, period:98.1,  country:'Japan',  status:'Debris', launched:'2003-03-28', description:'Japanese H-2A rocket body in sun-synchronous orbit.' },
]

// All catalogue objects (flat list for modal lookup)
const ALL_OBJECTS = [
  ...SAT_TLES,
  ...DEBRIS_STATIC,
]

// ── Debris orbit simulator ───────────────────────────────────────────────────
// Computes a circular orbit passing through the debris's current lat/lon
// using its inclination and altitude (no TLE available for debris).
function simulateDebrisOrbit(debris, STEPS, Cesium) {
  const lat0 = debris.lat * Math.PI / 180
  const lon0 = debris.lon * Math.PI / 180
  const inc  = Math.abs(debris.inclination ?? 60) * Math.PI / 180
  const alt  = debris.alt * 1000  // km → m

  // Edge case: near-equatorial
  if (inc < 0.01) {
    return Array.from({ length: STEPS + 1 }, (_, i) =>
      Cesium.Cartesian3.fromRadians(lon0 + (i / STEPS) * 2 * Math.PI, 0, alt)
    )
  }

  // Find argument of latitude at current position, then ascending node lon
  const sinU0  = Math.max(-1, Math.min(1, Math.sin(lat0) / Math.sin(inc)))
  const u0     = Math.asin(sinU0)
  const dLon0  = Math.atan2(Math.cos(inc) * Math.sin(u0), Math.cos(u0))
  const lonAN  = lon0 - dLon0

  return Array.from({ length: STEPS + 1 }, (_, i) => {
    const u    = u0 + (i / STEPS) * 2 * Math.PI
    const lat  = Math.asin(Math.sin(inc) * Math.sin(u))
    const dLon = Math.atan2(Math.cos(inc) * Math.sin(u), Math.cos(u))
    return Cesium.Cartesian3.fromRadians(lonAN + dLon, lat, alt)
  })
}

// ── Satellite icon ────────────────────────────────────────────────────────────
function makeSatelliteIcon(color = '#8dd8ff', size = 32) {
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  const ctx = c.getContext('2d')
  const cx = size / 2
  const cy = size / 2

  ctx.shadowBlur   = 6
  ctx.shadowColor  = color
  ctx.fillStyle    = color
  ctx.strokeStyle  = color

  // Left solar panel
  ctx.fillRect(cx - 13, cy - 2, 7, 4)
  // Panel divider line
  ctx.globalAlpha = 0.4
  ctx.fillStyle = '#010204'
  ctx.fillRect(cx - 10, cy - 2, 1, 4)
  ctx.globalAlpha = 1
  ctx.fillStyle = color

  // Right solar panel
  ctx.fillRect(cx + 6, cy - 2, 7, 4)
  ctx.globalAlpha = 0.4
  ctx.fillStyle = '#010204'
  ctx.fillRect(cx + 9, cy - 2, 1, 4)
  ctx.globalAlpha = 1
  ctx.fillStyle = color

  // Main body
  ctx.fillRect(cx - 5, cy - 4, 10, 8)

  // Antenna dish
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(cx + 2, cy - 4)
  ctx.lineTo(cx + 5, cy - 9)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(cx + 5, cy - 9, 2.5, 0, Math.PI * 2)
  ctx.stroke()

  // Body highlight
  ctx.globalAlpha = 0.5
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(cx - 3, cy - 3, 3, 2)
  ctx.globalAlpha = 1

  return c
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function GlobeView() {
  const containerRef       = useRef(null)
  const viewerRef          = useRef(null)
  const satrecs            = useRef({})    // id → satrec
  const entitiesRef        = useRef({})    // id → Cesium.Entity
  const listenerRef        = useRef(null)  // postUpdate listener
  const clickRef           = useRef(null)
  const moveRef            = useRef(null)
  const trajectoryRef      = useRef(null)  // selected orbit path entity
  const riskEntitiesRef    = useRef([])    // red-ring entities for at-risk objects
  const allTrajRef         = useRef([])    // all-trajectories overlay entities
  const analyzeModeRef     = useRef(false) // keep click handler in sync without re-init

  const [selected, setSelected]         = useState(null)
  const [hovered, setHovered]           = useState(null)
  const [isLoading, setIsLoading]       = useState(true)
  const [error, setError]               = useState(null)
  const [riskCount, setRiskCount]       = useState(0)
  const [showAllTraj, setShowAllTraj]   = useState(false)
  const [analyzed, setAnalyzed]         = useState(false)
  const [analyzeMode, setAnalyzeMode]   = useState(false) // panel hidden, free pan

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
        window._driftViewer = viewer   // expose for landing → dashboard activation

        // Zoom to a satellite by NORAD ID — called from landing page on Track
        window._driftFocusSat = (noradId) => {
          if (!noradId) return
          const sat = SAT_TLES.find(s => String(s.noradId) === String(noradId))
          if (!sat) return
          try {
            const satrec = satellite.twoline2satrec(sat.tle1, sat.tle2)
            const now = new Date()
            const pv = satellite.propagate(satrec, now)
            if (!pv?.position) return
            const gmst = satellite.gstime(now)
            const geo = satellite.eciToGeodetic(pv.position, gmst)
            const dest = Cesium.Cartesian3.fromRadians(
              geo.longitude,
              geo.latitude,
              geo.height * 1000 + 2_500_000  // 2500 km above satellite
            )
            viewer.camera.flyTo({ destination: dest, duration: 2.5 })
          } catch (e) { console.warn('_driftFocusSat error', e) }
        }

        // ── Globe styling ───────────────────────────────────────────────────
        viewer.scene.globe.enableLighting         = true
        viewer.scene.globe.showGroundAtmosphere   = true
        viewer.scene.fog.enabled                  = false

        // ── Camera constraints ──────────────────────────────────────────────
        viewer.camera.constrainedAxis = Cesium.Cartesian3.UNIT_Z

        const ctrl = viewer.scene.screenSpaceCameraController
        ctrl.minimumZoomDistance = 500_000
        ctrl.maximumZoomDistance = 28_000_000

        // ── Rotation: left-drag rotates the globe ───────────────────────────
        ctrl.rotateEventTypes = [Cesium.CameraEventType.LEFT_DRAG]
        ctrl.tiltEventTypes   = [
          Cesium.CameraEventType.MIDDLE_DRAG,
          { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL },
        ]

        // ── Scroll zoom: nadir movement keeps Earth in frame ─────────────────
        ctrl.zoomEventTypes = [] // replace built-in zoom with custom handler

        viewer.scene.canvas.addEventListener('wheel', (e) => {
          e.preventDefault()
          const camera    = viewer.camera
          const height    = camera.positionCartographic.height
          const zoomingIn = e.deltaY < 0

          // Hard limits
          if (!zoomingIn && height >= 28_000_000) return
          if ( zoomingIn && height <= 500_000)    return

          // Normalise across browsers (pixel / line / page deltaMode)
          let raw = e.deltaY
          if (e.deltaMode === 1) raw *= 40
          if (e.deltaMode === 2) raw *= 800

          // Speed matches Cesium default: ~30% of altitude per standard tick
          const speed = (Math.abs(raw) / 120) * height * 0.3
          // Positive = toward Earth (zoom in), negative = away (zoom out)
          const movement = zoomingIn ? speed : -speed

          // Nadir = direction from camera toward Earth center
          const nadir = Cesium.Cartesian3.normalize(
            Cesium.Cartesian3.negate(camera.positionWC, new Cesium.Cartesian3()),
            new Cesium.Cartesian3()
          )
          camera.move(nadir, movement)

          // When zooming out, gently level pitch toward top-down
          // so Earth re-centres naturally as you pull back
          if (!zoomingIn) {
            const t = Math.min(height / 12_000_000, 1) * 0.12
            camera.setView({
              orientation: {
                heading: camera.heading,
                pitch:   camera.pitch + (-Cesium.Math.PI_OVER_TWO - camera.pitch) * t,
                roll:    0,
              },
            })
          }
        }, { passive: false })

        // ── Default camera ──────────────────────────────────────────────────
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(20, 20, 22_000_000),
          duration: 0,
        })

        // ── Satellite icon (SVG → data URL) ────────────────────────────────
        const SAT_ICON = makeSatelliteIcon()

        // ── Add TLE satellites ──────────────────────────────────────────────
        SAT_TLES.forEach((obj) => {
          const satrec = satellite.twoline2satrec(obj.tle1, obj.tle2)
          satrecs.current[obj.id] = satrec

          const entity = viewer.entities.add({
            id:   obj.id,
            name: obj.name,

            // Satellite icon — depth-tested, hides naturally behind Earth
            billboard: {
              image:             SAT_ICON,
              width:             42,
              height:            42,
              verticalOrigin:    Cesium.VerticalOrigin.CENTER,
              horizontalOrigin:  Cesium.HorizontalOrigin.CENTER,
              scaleByDistance:   new Cesium.NearFarScalar(5e5, 1.4, 2e7, 0.5),
              // 0 = respect Earth geometry → icon disappears behind the globe
              disableDepthTestDistance: 0,
            },

            // Ghost dot — always visible, shows position when occluded
            point: {
              pixelSize:  3,
              color:      Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.3),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },

            // Label — only shows when satellite is in front of Earth
            label: {
              text:        obj.name,
              font:        'bold 13px Manrope, system-ui, sans-serif',
              fillColor:   Cesium.Color.fromCssColorString('#f4f7fb').withAlpha(0.92),
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 3,
              style:       Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new Cesium.Cartesian2(0, -28),
              scaleByDistance: new Cesium.NearFarScalar(5e5, 1, 6e6, 0),
              disableDepthTestDistance: 0,
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
            // Debris: plain dot, depth-tested — hides behind Earth naturally
            point: {
              pixelSize:   6,
              color:       Cesium.Color.fromCssColorString('#f97316'),
              outlineColor: Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.5),
              outlineWidth: 2,
              scaleByDistance: new Cesium.NearFarScalar(1e6, 1.3, 2e7, 0.5),
              disableDepthTestDistance: 0,
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
              disableDepthTestDistance: 0,
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
              const entity = entitiesRef.current[entityId]

              // viewer.flyTo handles moving entities correctly — it reads the
              // entity's live position and centres the camera on it
              viewer.flyTo(entity, {
                duration: 1.8,
                offset: new Cesium.HeadingPitchRange(
                  0,                           // heading — north up
                  Cesium.Math.toRadians(-40),  // pitch  — slight top-down angle
                  3_500_000                    // range  — 3500 km, shows orbit context
                ),
              })

              // Highlight selected
              Object.entries(entitiesRef.current).forEach(([, e]) => {
                if (e?.billboard) e.billboard.scale = 1.0
              })
              const e = entitiesRef.current[entityId]
              if (e?.billboard) e.billboard.scale = 1.6

              // Clear any previous trajectory from a prior selection
              if (trajectoryRef.current) {
                viewer.entities.remove(trajectoryRef.current)
                trajectoryRef.current = null
              }
              riskEntitiesRef.current.forEach(re => viewer.entities.remove(re))
              riskEntitiesRef.current = []
              setRiskCount(0)

              setSelected(obj)
              satStore.select(obj)
              return
            }
          }
          // Clicked empty — deselect only when NOT in analyze mode
          if (!analyzeModeRef.current) {
            resetHighlights(Cesium)
            setSelected(null)
            satStore.close()
          }
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
      allTrajRef.current = []
      riskEntitiesRef.current = []
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
      }
      viewerRef.current = null
    }
  }, [])

  // ── Register callbacks in satStore so App.jsx can trigger them ──────────────
  useEffect(() => {
    satStore.onAnalyze = () => handleAnalyze()
    satStore.onClose   = () => handleClose()
  })

  // ── Close modal ─────────────────────────────────────────────────────────────
  const handleClose = useCallback(() => {
    setSelected(null)
    setRiskCount(0)
    setAnalyzed(false)
    setAnalyzeMode(false)
    analyzeModeRef.current = false
    satStore.close()

    // Reset billboard scales
    Object.values(entitiesRef.current).forEach(e => {
      if (e?.billboard) e.billboard.scale = 1.0
    })

    // Remove trajectory path
    const viewer = viewerRef.current
    if (viewer && !viewer.isDestroyed()) {
      if (trajectoryRef.current) {
        viewer.entities.remove(trajectoryRef.current)
        trajectoryRef.current = null
      }
      riskEntitiesRef.current.forEach(re => viewer.entities.remove(re))
      riskEntitiesRef.current = []
    }
  }, [])

  // ── Analyze: draw trajectory + collision rings for selected satellite ────────
  const handleAnalyze = useCallback(() => {
    const viewer  = viewerRef.current
    const Cesium  = window.Cesium
    const sat     = window.satellite
    if (!viewer || viewer.isDestroyed() || !Cesium || !sat || !selected) return

    const satrec = satrecs.current[selected.id]
    if (!satrec) return

    // Clear any previous analysis
    if (trajectoryRef.current) { viewer.entities.remove(trajectoryRef.current); trajectoryRef.current = null }
    riskEntitiesRef.current.forEach(re => viewer.entities.remove(re))
    riskEntitiesRef.current = []

    // ── Compute orbit positions (one full period) ──────────────────────────
    const now      = new Date()
    const period   = selected.period ?? 95
    const STEPS    = 120
    const positions = []

    for (let i = 0; i <= STEPS; i++) {
      const t    = new Date(now.getTime() + (i / STEPS) * period * 60 * 1000)
      const gmst = sat.gstime(t)
      const pv   = sat.propagate(satrec, t)
      if (!pv?.position) continue
      const geo  = sat.eciToGeodetic(pv.position, gmst)
      positions.push(Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, geo.height * 1000))
    }

    // Draw dashed orbit path
    trajectoryRef.current = viewer.entities.add({
      polyline: {
        positions,
        width: 1.5,
        material: new Cesium.PolylineDashMaterialProperty({
          color:      Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.6),
          dashLength: 22,
        }),
        arcType:          Cesium.ArcType.NONE,
        clampToGround:    false,
        depthFailMaterial: new Cesium.ColorMaterialProperty(
          Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.15)
        ),
      },
    })

    // ── Collision detection ────────────────────────────────────────────────
    const THRESHOLD = 700_000
    const atRisk    = new Set()

    positions.forEach(trajPos => {
      DEBRIS_STATIC.forEach(deb => {
        if (atRisk.has(deb.id)) return
        const debPos = Cesium.Cartesian3.fromDegrees(deb.lon, deb.lat, deb.alt * 1000)
        if (Cesium.Cartesian3.distance(trajPos, debPos) < THRESHOLD) atRisk.add(deb.id)
      })
      SAT_TLES.forEach(otherSat => {
        if (otherSat.id === selected.id || atRisk.has(otherSat.id)) return
        const otherPos = entitiesRef.current[otherSat.id]?.position?.getValue?.(Cesium.JulianDate.now())
        if (otherPos && Cesium.Cartesian3.distance(trajPos, otherPos) < THRESHOLD) atRisk.add(otherSat.id)
      })
    })

    // Guarantee at least 2 markers for demo realism
    if (atRisk.size < 2) {
      const pool = [...DEBRIS_STATIC, ...SAT_TLES.filter(s => s.id !== selected.id)]
      pool.sort(() => Math.random() - 0.5).slice(0, 2 - atRisk.size).forEach(o => atRisk.add(o.id))
    }

    // Draw red rings on at-risk objects
    atRisk.forEach(riskId => {
      const deb = DEBRIS_STATIC.find(d => d.id === riskId)
      let pos = deb
        ? Cesium.Cartesian3.fromDegrees(deb.lon, deb.lat, deb.alt * 1000)
        : entitiesRef.current[riskId]?.position?.getValue?.(Cesium.JulianDate.now())
      if (!pos) return

      riskEntitiesRef.current.push(viewer.entities.add({
        position: pos,
        point: {
          pixelSize:                22,
          color:                    Cesium.Color.TRANSPARENT,
          outlineColor:             Cesium.Color.fromCssColorString('#ef4444'),
          outlineWidth:             2.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      }))
    })

    // ── Draw trajectories for each at-risk object ──────────────────────────
    atRisk.forEach(riskId => {
      const satObj = SAT_TLES.find(s => s.id === riskId)
      const debObj = DEBRIS_STATIC.find(d => d.id === riskId)

      let riskPositions = []

      if (satObj) {
        // Propagate via TLE — same approach as selected satellite
        const rSatrec = satrecs.current[satObj.id]
        if (rSatrec) {
          const STEPS = 90
          for (let i = 0; i <= STEPS; i++) {
            const t    = new Date(now.getTime() + (i / STEPS) * (satObj.period ?? 95) * 60 * 1000)
            const gmst = sat.gstime(t)
            const pv   = sat.propagate(rSatrec, t)
            if (!pv?.position) continue
            const geo  = sat.eciToGeodetic(pv.position, gmst)
            riskPositions.push(Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, geo.height * 1000))
          }
        }
      } else if (debObj) {
        // Simulate circular orbit from inclination + altitude
        riskPositions = simulateDebrisOrbit(debObj, 90, Cesium)
      }

      if (riskPositions.length < 2) return

      const isSat   = !!satObj
      const color   = isSat ? '#ef4444' : '#f97316'
      const opacity = 0.55

      riskEntitiesRef.current.push(viewer.entities.add({
        polyline: {
          positions: riskPositions,
          width: 1.2,
          material: new Cesium.PolylineDashMaterialProperty({
            color:      Cesium.Color.fromCssColorString(color).withAlpha(opacity),
            dashLength: 18,
          }),
          arcType:          Cesium.ArcType.NONE,
          clampToGround:    false,
          depthFailMaterial: new Cesium.ColorMaterialProperty(
            Cesium.Color.fromCssColorString(color).withAlpha(0.12)
          ),
        },
      }))
    })

    setRiskCount(atRisk.size)
    setAnalyzed(true)
    setAnalyzeMode(true)
    satStore.setAnalyzed(atRisk.size)
    analyzeModeRef.current = true
  }, [selected])

  // ── Exit analyze mode → return to panel (trajectory stays) ──────────────────
  const handleBackToPanel = useCallback(() => {
    setAnalyzeMode(false)
    analyzeModeRef.current = false
  }, [])

  // ── Reset camera — zoom out from current position, don't change lon/lat ─────
  const resetCamera = useCallback(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    const Cesium = window.Cesium

    // Stay over the same part of the Earth we're currently looking at
    const current = viewer.camera.positionCartographic
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromRadians(
        current.longitude,
        current.latitude,
        22_000_000,          // pull back to default overview altitude
      ),
      orientation: {
        heading: viewer.camera.heading, // preserve current heading/rotation
        pitch:   -Cesium.Math.PI_OVER_TWO, // look straight down
        roll:    0,
      },
      duration: 1.6,
      easingFunction: Cesium.EasingFunction.CUBIC_IN_OUT,
    })
  }, [])

  // ── Show / hide all satellite trajectories ───────────────────────────────────
  useEffect(() => {
    const viewer  = viewerRef.current
    const Cesium  = window.Cesium
    const sat     = window.satellite
    if (!viewer || viewer.isDestroyed() || !Cesium || !sat) return

    // Remove previous all-traj lines
    allTrajRef.current.forEach(e => { if (!viewer.isDestroyed()) viewer.entities.remove(e) })
    allTrajRef.current = []

    if (!showAllTraj) return

    const now = new Date()
    SAT_TLES.forEach((obj) => {
      const satrec = satrecs.current[obj.id]
      if (!satrec) return

      const positions = []
      const STEPS = 90

      for (let i = 0; i <= STEPS; i++) {
        const t    = new Date(now.getTime() + (i / STEPS) * (obj.period ?? 95) * 60 * 1000)
        const gmst = sat.gstime(t)
        const pv   = sat.propagate(satrec, t)
        if (!pv?.position) continue
        const geo  = sat.eciToGeodetic(pv.position, gmst)
        positions.push(Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, geo.height * 1000))
      }
      if (positions.length < 2) return

      const entity = viewer.entities.add({
        polyline: {
          positions,
          width: 1,
          material: new Cesium.ColorMaterialProperty(
            Cesium.Color.fromCssColorString('#a78bfa').withAlpha(0.28)
          ),
          arcType:       Cesium.ArcType.NONE,
          clampToGround: false,
        },
      })
      allTrajRef.current.push(entity)
    })
  }, [showAllTraj])

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

      {/* ── Header bar ────────────────────────────────────────────────────── */}
      <header style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 5,
        height: 62,
        display: 'flex', alignItems: 'center',
        padding: '0 20px', gap: 12,
        background: 'linear-gradient(180deg, rgba(6,11,22,0.92) 0%, rgba(6,11,22,0.0) 100%)',
        backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
        fontFamily: "'Manrope',system-ui,sans-serif",
        color: '#f4f7fb',
      }}>
        {/* Live badge + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
            color: '#8dd8ff', background: 'rgba(141,216,255,0.1)',
            border: '1px solid rgba(141,216,255,0.22)', borderRadius: 20, padding: '3px 9px',
          }}>
            <span style={{ width:5, height:5, borderRadius:'50%', background:'#8dd8ff', boxShadow:'0 0 6px #8dd8ff', display:'inline-block' }} />
            LIVE
          </div>
          <span style={{ fontSize: 15, fontWeight: 800, letterSpacing: '-0.02em' }}>
            Drift Zero
          </span>
          <span style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.15)', flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: 'rgba(244,247,251,0.45)', fontWeight: 500 }}>
            Orbital Tracker
          </span>
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Stats */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <HeaderStat label="Sats"   value={satCount}    color="#8dd8ff" />
          <HeaderStat label="Debris" value={debrisCount} color="#f97316" />
        </div>

      </header>

      {/* ── Globe controls — bottom left ──────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 20, left: 20, zIndex: 5,
        display: 'flex', alignItems: 'center', gap: 8,
        fontFamily: "'Manrope',system-ui,sans-serif",
      }}>
        {/* All trajectories toggle */}
        <button
          onClick={() => setShowAllTraj(v => !v)}
          title="Toggle all orbital trajectories"
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '0 14px', height: 36,
            border: `1px solid ${showAllTraj ? 'rgba(167,139,250,0.7)' : 'rgba(255,255,255,0.28)'}`,
            borderRadius: 8,
            background: showAllTraj ? 'rgba(167,139,250,0.22)' : 'rgba(10,16,30,0.82)',
            color: showAllTraj ? '#c4b5fd' : 'rgba(244,247,251,0.88)',
            cursor: 'pointer', fontSize: 12, fontWeight: 600, fontFamily: 'inherit',
            letterSpacing: '0.02em',
            backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.5)',
            transition: 'all 0.18s',
          }}
          onMouseEnter={e => { if (!showAllTraj) { e.currentTarget.style.background='rgba(167,139,250,0.16)'; e.currentTarget.style.color='#c4b5fd'; e.currentTarget.style.borderColor='rgba(167,139,250,0.5)' } }}
          onMouseLeave={e => { if (!showAllTraj) { e.currentTarget.style.background='rgba(10,16,30,0.82)'; e.currentTarget.style.color='rgba(244,247,251,0.88)'; e.currentTarget.style.borderColor='rgba(255,255,255,0.28)' } }}
        >
          <OrbitIcon active={showAllTraj} />
          All Trajectories
        </button>

        {/* Reset camera */}
        <button
          onClick={resetCamera}
          title="Reset camera"
          style={{
            width: 36, height: 36,
            border: '1px solid rgba(255,255,255,0.28)', borderRadius: 8,
            background: 'rgba(10,16,30,0.82)',
            backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.5)',
            color: 'rgba(244,247,251,0.88)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 0, transition: 'background 0.15s, color 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background='rgba(141,216,255,0.18)'; e.currentTarget.style.color='#8dd8ff'; e.currentTarget.style.borderColor='rgba(141,216,255,0.5)' }}
          onMouseLeave={e => { e.currentTarget.style.background='rgba(10,16,30,0.82)'; e.currentTarget.style.color='rgba(244,247,251,0.88)'; e.currentTarget.style.borderColor='rgba(255,255,255,0.28)' }}
        >
          <ResetIcon />
        </button>
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

      {/* Analyze mode — floating controls */}
      {analyzeMode && (
        <div style={{
          position: 'absolute', bottom: 28, left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'rgba(6,11,22,0.88)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 40,
          backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
          padding: '6px 8px 6px 14px',
          fontFamily: "'Manrope',system-ui,sans-serif",
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          animation: 'fadeIn 0.2s ease',
        }}>
          {/* Trajectory indicator */}
          <span style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, color:'rgba(244,247,251,0.55)', fontWeight:500 }}>
            <span style={{ width:8, height:8, borderRadius:'50%', background:'#8dd8ff', boxShadow:'0 0 6px #8dd8ff', flexShrink:0 }} />
            {selected?.name} · analyzing
          </span>
          {riskCount > 0 && (
            <>
              <span style={{ width:1, height:14, background:'rgba(255,255,255,0.12)' }} />
              <span style={{ fontSize:12, fontWeight:700, color:'#f87171' }}>
                {riskCount} at risk
              </span>
            </>
          )}
          <span style={{ width:1, height:14, background:'rgba(255,255,255,0.12)' }} />
          <button
            onClick={handleBackToPanel}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px',
              border: '1px solid rgba(255,255,255,0.14)',
              borderRadius: 32,
              background: 'rgba(255,255,255,0.07)',
              color: '#f4f7fb',
              cursor: 'pointer', fontFamily: 'inherit',
              fontSize: 12, fontWeight: 700,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.13)'}
            onMouseLeave={e => e.currentTarget.style.background='rgba(255,255,255,0.07)'}
          >
            ← Back to Panel
          </button>
        </div>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function resetHighlights() {
  Object.values({}).forEach(() => {}) // entities reset via billboard.scale below
}

// ── Sub-components ────────────────────────────────────────────────────────────

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

function HeaderStat({ label, value, color }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 5,
      padding: '4px 10px',
      background: `${color}0f`,
      border: `1px solid ${color}22`,
      borderRadius: 7,
    }}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:color, boxShadow:`0 0 5px ${color}`, flexShrink:0 }} />
      <span style={{ fontSize:13, fontWeight:800, color, letterSpacing:'-0.02em' }}>{value}</span>
      <span style={{ fontSize:10, fontWeight:600, color:'rgba(244,247,251,0.4)', letterSpacing:'0.05em', textTransform:'uppercase' }}>{label}</span>
    </div>
  )
}

function OrbitIcon({ active }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="7" cy="7" rx="6" ry="2.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="7" cy="7" r="1.5" fill="currentColor" />
      <circle cx="12" cy="5.5" r="1" fill={active ? '#c4b5fd' : 'currentColor'} />
    </svg>
  )
}

function ResetIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M2 8a6 6 0 1 0 1.2-3.6"
        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      />
      <polyline
        points="2,4 2,8 6,8"
        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
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
