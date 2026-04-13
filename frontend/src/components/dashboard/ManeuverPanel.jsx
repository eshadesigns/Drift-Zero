import { useState, useEffect, useRef } from 'react'
import { fetchManeuvers } from '../../api/shield'
import { SAT_ORBIT_PARAMS, DEBRIS_ORBIT_PARAMS } from '../../data/satelliteOrbits'

// Position 0 = highest composite_score, maps to colour slot A, B, C
const OPTION_COLORS = [
  { base: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.25)' },
  { base: '#22d3ee', bg: 'rgba(34,211,238,0.08)',  border: 'rgba(34,211,238,0.25)'  },
  { base: '#86efac', bg: 'rgba(134,239,172,0.08)', border: 'rgba(134,239,172,0.25)' },
]

const OPTION_IDS = ['A', 'B', 'C']

// ── Physics helpers ───────────────────────────────────────────────────────────

function orbitalVelocity(altKm) {
  return Math.sqrt(398600 / (6371 + altKm))
}

function deltaAltKm(deltaVMs, altKm) {
  const a  = 6371 + altKm
  const vc = orbitalVelocity(altKm)
  return (2 * a * (deltaVMs / 1000)) / vc
}

function burnDurationS(fuelKg) {
  // Approximate burn duration: fuel / (thrust / (Isp * g0))
  // Using typical small thruster: 22N at Isp=220s
  return fuelKg / (22 / (220 * 9.80665)) * 1000
}

function fmtDuration(s) {
  if (s < 60) return `${Math.round(s)}s`
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return r > 0 ? `${m}m ${r}s` : `${m}m`
}

function fmtCost(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}

// ── Orbit builders ────────────────────────────────────────────────────────────

// Build real ground track from TLE using satellite.js propagation
// altOffsetKm: add an altitude offset (for post-maneuver raised orbit)
function buildOrbitFromTLE(Cesium, sat, tle1, tle2, altOffsetKm = 0) {
  try {
    const satrec = sat.twoline2satrec(tle1, tle2)
    const now = new Date()
    // satrec.no is mean motion in rad/min; period in minutes
    const periodMs = (2 * Math.PI / satrec.no) * 60 * 1000
    const STEPS = 120
    const positions = []
    for (let k = 0; k <= STEPS; k++) {
      const t = new Date(now.getTime() + (k / STEPS) * periodMs)
      const pv = sat.propagate(satrec, t)
      if (!pv?.position) continue
      const gmst = sat.gstime(t)
      const geo = sat.eciToGeodetic(pv.position, gmst)
      positions.push(Cesium.Cartesian3.fromRadians(
        geo.longitude,
        geo.latitude,
        geo.height * 1000 + altOffsetKm * 1000,
      ))
    }
    return positions
  } catch {
    return []
  }
}

// Simulate a circular orbit for debris (no TLE) — mirrors GlobeView's simulateDebrisOrbit
function buildDebrisOrbit(Cesium, { alt, inclination, lat = 0, lon = 0 }) {
  const STEPS = 90
  const altM  = alt * 1000
  const inc   = Math.abs(inclination ?? 60) * Math.PI / 180
  const lat0  = lat * Math.PI / 180
  const lon0  = lon * Math.PI / 180

  if (inc < 0.01) {
    return Array.from({ length: STEPS + 1 }, (_, i) =>
      Cesium.Cartesian3.fromRadians(lon0 + (i / STEPS) * 2 * Math.PI, 0, altM)
    )
  }

  const sinU0  = Math.max(-1, Math.min(1, Math.sin(lat0) / Math.sin(inc)))
  const u0     = Math.asin(sinU0)
  const dLon0  = Math.atan2(Math.cos(inc) * Math.sin(u0), Math.cos(u0))
  const lonAN  = lon0 - dLon0

  return Array.from({ length: STEPS + 1 }, (_, i) => {
    const u    = u0 + (i / STEPS) * 2 * Math.PI
    const lat  = Math.asin(Math.sin(inc) * Math.sin(u))
    const dLon = Math.atan2(Math.cos(inc) * Math.sin(u), Math.cos(u))
    return Cesium.Cartesian3.fromRadians(lonAN + dLon, lat, altM)
  })
}

// Fallback static circle (ECI-frame, used only if satellite.js not available)
function buildStaticOrbit(Cesium, altKm, inclDeg, raanDeg) {
  const R  = 6_371_000
  const a  = R + altKm * 1000
  const i  = inclDeg * Math.PI / 180
  const ra = raanDeg * Math.PI / 180
  const pts = []
  for (let k = 0; k <= 120; k++) {
    const theta = (k / 120) * 2 * Math.PI
    const xO = a * Math.cos(theta)
    const yO = a * Math.sin(theta)
    pts.push(new Cesium.Cartesian3(
       xO * Math.cos(ra) - yO * Math.cos(i) * Math.sin(ra),
       xO * Math.sin(ra) + yO * Math.cos(i) * Math.cos(ra),
       yO * Math.sin(i)
    ))
  }
  return pts
}

// ── Maneuver physics ──────────────────────────────────────────────────────────
// Compute 3 maneuver strategies from conjunction data using orbital mechanics.
//
// Physics model (Clohessy-Wiltshire linearization):
//   A prograde ΔV raises the orbit, changing the period. Over time t, the
//   satellite drifts along-track by:  Δs ≈ 3 · (ΔV km/s) · t_seconds
//
//   New miss distance:  newMiss = √(currentMiss² + Δs²)
//   Required ΔV for target miss:  ΔV = √(target² - currentMiss²) / (3·t_s)  × 1000 m/s
//
// Altitude change (vis-viva linearized):
//   Δa ≈ 2a·ΔV/v,  Δalt ≈ Δa

function computeManeuverOptions(conjunction, orbParams) {
  const { missDistanceKm, tcaTime } = conjunction
  const {
    alt,
    fuelRatio    = 0.52,   // kg fuel per m/s of ΔV
    propCostPerKg = 100000, // USD per kg propellant on-orbit
    lifeDaysPerMs  = 8,     // lifespan reduction days per m/s of ΔV
  } = orbParams

  const tcaSec = Math.max((new Date(tcaTime) - new Date()) / 1000, 1800)
  // k: km of cross-track displacement per m/s of ΔV
  const k = (3 * tcaSec) / 1000

  const v_orb = orbitalVelocity(alt)  // km/s
  const a     = 6371 + alt            // km

  const targets   = [50, 25, 10]
  const labels    = ['Maximum Safety', 'Balanced', 'Fuel Efficient']
  const scores    = [0.91, 0.84, 0.71]

  return labels.map((label, i) => {
    const targetMiss = Math.max(targets[i], missDistanceKm + 3)

    // ΔV needed
    const disp = Math.sqrt(Math.max(0, targetMiss ** 2 - missDistanceKm ** 2))
    const dV   = Math.max(0.01, disp / k)               // m/s

    // Achieved miss after maneuver
    const newMiss = Math.sqrt(missDistanceKm ** 2 + (k * dV) ** 2)

    // Altitude increase from prograde burn (vis-viva)
    const dAlt = 2 * a * (dV / 1000) / v_orb           // km

    // Fuel (rocket equation small-ΔV approximation, empirical ratio matches real ops data)
    const fuel = dV * fuelRatio                          // kg

    return {
      label,
      miss_increase_km:       parseFloat((newMiss - missDistanceKm).toFixed(3)),
      delta_v_ms:             parseFloat(dV.toFixed(2)),
      fuel_kg:                parseFloat(fuel.toFixed(4)),
      fuel_cost_usd:          Math.round(fuel * propCostPerKg),
      lifespan_reduction_days: parseFloat((dV * lifeDaysPerMs).toFixed(1)),
      composite_score:        scores[i],
      altDelta:               parseFloat(dAlt.toFixed(3)),
    }
  })
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ManeuverPanel({ conjunction, demo = false, onSelectManeuver, showDebrisOrbits = true }) {
  const [options, setOptions]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [selected, setSelected] = useState(null)

  // Globe entity refs
  const primaryOrbitRef   = useRef(null)  // primary sat orbit (drawn on conjunction select)
  const secondaryOrbitRef = useRef(null)  // threat orbit     (drawn on conjunction select)
  const secLabelRef       = useRef(null)  // threat label     (drawn on conjunction select)
  const originalOrbitRef  = useRef(null)  // pre-maneuver orbit (drawn on option select)
  const entityRef         = useRef(null)  // post-maneuver orbit (drawn on option select)
  const labelRef          = useRef(null)  // info label         (drawn on option select)
  const secAltOrbitRef    = useRef(null)  // secondary sat alt maneuver (purple, drawn on option select)

  const noradId = conjunction?.primarySatId
  const eventId = conjunction?.id
function labelToSlug(label) {
  return label.toLowerCase().replace(/\s+/g, '_')
}

function formatCost(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n}`
}

export default function ManeuverPanel({ conjunction, onManeuverSelect }) {
  const [maneuverData, setManeuverData] = useState(null)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(null)
  const [selected, setSelected]         = useState(null)

  // Satellite-only guard: disable maneuvers for debris primaries
  const primaryIsDebris = conjunction?.primarySatName?.toUpperCase().includes('DEB')
    || conjunction?.primarySatName?.toUpperCase().includes('DEBRIS')
    || conjunction?.primarySatName?.toUpperCase().includes('R/B')

  // Look up orbit params by satellite entity ID (e.g. 'ISS', 'SL1') — NOT conjunction ID.
  // This is the single source of truth: same data as GlobeView, always consistent.
  const orbitParams = demo
    ? (SAT_ORBIT_PARAMS[conjunction?.primarySatId] ?? { alt: 420, inclination: 51.6 })
    : { alt: 420, inclination: 51.6 }

  // ── Secondary maneuverability check (computed early so effects can access) ──
  // Is the secondary a maneuverable satellite (has an entry in SAT_ORBIT_PARAMS)?
  const secSatId      = conjunction?.secondarySatId ?? null
  const secOrbParams  = SAT_ORBIT_PARAMS[secSatId] ?? null
  const secCanManeuver = !!secOrbParams
  // If secondary can maneuver, compute its cheapest avoidance for comparison
  let secCheapestDV = null
  if (secCanManeuver && secOrbParams && conjunction) {
    try {
      const secOpts = computeManeuverOptions(conjunction, secOrbParams)
      secCheapestDV = secOpts[2]  // index 2 = Fuel Efficient (cheapest)
    } catch {}
  }

  // ── Load / compute maneuver options ────────────────────────────────────────
  useEffect(() => {
    if (!noradId || !eventId) return
    setSelected(null)
    setOptions(null)
    setError(null)

    if (demo) {
      const orb = SAT_ORBIT_PARAMS[conjunction?.primarySatId]
      if (conjunction && orb) {
        const computed = computeManeuverOptions(conjunction, orb)
        setOptions({
          event_id:         eventId,
          norad_id:         noradId,
          primary_name:     conjunction.primarySatName,
          current_miss_km:  conjunction.missDistanceKm,
          maneuver_options: computed,
        })
      }
      return
    }

    setLoading(true)
    fetchManeuvers(noradId, eventId)
      .then(data => setOptions(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [noradId, eventId, demo, conjunction])

  // ── Draw primary + secondary orbits when conjunction selected (demo mode) ──
  useEffect(() => {
    const viewer  = window._driftViewer
    const Cesium  = window.Cesium
    const sat     = window.satellite

    // Always clean up previous primary/secondary and any leftover maneuver entities
    const cleanup = (ref) => {
      if (ref.current && viewer) {
        try { viewer.entities.remove(ref.current) } catch {}
        ref.current = null
      }
    }
    cleanup(primaryOrbitRef)
    cleanup(secondaryOrbitRef)
    cleanup(secLabelRef)
    cleanup(originalOrbitRef)
    cleanup(entityRef)
    cleanup(labelRef)

    if (!demo || !eventId || !Cesium || !viewer || !conjunction) return

    // Look up by satellite entity ID — same source as GlobeView, always consistent
    const primarySatId  = conjunction.primarySatId
    const secondarySatId = conjunction.secondarySatId
    const orb    = SAT_ORBIT_PARAMS[primarySatId]
    // Secondary can be debris (DEB1–DEB28) or another satellite
    const secOrb = DEBRIS_ORBIT_PARAMS[secondarySatId] ?? SAT_ORBIT_PARAMS[secondarySatId] ?? null

    try {
      // ── Primary satellite orbit (blue dashed — like "analyze trajectory") ──
      const primaryPositions = (orb?.tle1 && sat)
        ? buildOrbitFromTLE(Cesium, sat, orb.tle1, orb.tle2, 0)
        : buildStaticOrbit(Cesium, orb?.alt ?? 420, orb?.inclination ?? 51.6, 0)

      if (primaryPositions.length >= 2) {
        primaryOrbitRef.current = viewer.entities.add({
          polyline: {
            positions: primaryPositions,
            width: 1.5,
            material: new Cesium.PolylineDashMaterialProperty({
              color:      Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.65),
              dashLength: 22,
            }),
            arcType:           Cesium.ArcType.NONE,
            depthFailMaterial: new Cesium.ColorMaterialProperty(
              Cesium.Color.fromCssColorString('#8dd8ff').withAlpha(0.12)
            ),
          },
        })
      }

      // ── Secondary / threat orbit (orange = uncontrolled debris, red = sat) ──
      if (secOrb && showDebrisOrbits) {
        const secIsSat   = !!SAT_ORBIT_PARAMS[secondarySatId]   // maneuverable satellite?
        const secColor   = secIsSat ? '#ef4444' : '#f97316'
        const secPositions = secOrb.tle1 && sat
          ? buildOrbitFromTLE(Cesium, sat, secOrb.tle1, secOrb.tle2, 0)
          : buildDebrisOrbit(Cesium, secOrb)
        if (secPositions.length >= 2) {
          secondaryOrbitRef.current = viewer.entities.add({
            polyline: {
              positions: secPositions,
              width: 1.2,
              material: new Cesium.PolylineDashMaterialProperty({
                color:      Cesium.Color.fromCssColorString(secColor).withAlpha(0.55),
                dashLength: 16,
              }),
              arcType: Cesium.ArcType.NONE,
            },
          })

          // ── Label on the threat orbit identifying it and its maneuverability ──
          const midIdx  = Math.floor(secPositions.length / 2)
          const midPos  = secPositions[midIdx]
          if (midPos) {
            secLabelRef.current = viewer.entities.add({
              position: midPos,
              label: {
                text: secIsSat
                  ? `⚠ ${conjunction.secondarySatName}\nCAN MANEUVER — see cost comparison below`
                  : `${conjunction.secondarySatName}\nUNCONTROLLED · CANNOT MANEUVER`,
                font:             'bold 11px "SF Mono", Consolas, monospace',
                fillColor:        Cesium.Color.fromCssColorString(secColor).withAlpha(0.9),
                outlineColor:     Cesium.Color.BLACK,
                outlineWidth:     2,
                style:            Cesium.LabelStyle.FILL_AND_OUTLINE,
                showBackground:   true,
                backgroundColor:  new Cesium.Color(0.02, 0.04, 0.1, 0.82),
                backgroundPadding: new Cesium.Cartesian2(8, 6),
                pixelOffset:      new Cesium.Cartesian2(14, 0),
                horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
                verticalOrigin:   Cesium.VerticalOrigin.CENTER,
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30_000_000),
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
              },
            })
          }
        }
      }
    } catch (e) {
      console.warn('ManeuverPanel: orbit draw error', e)
    }
  }, [demo, eventId, conjunction?.primarySatId, conjunction?.secondarySatId, showDebrisOrbits])

  // ── Draw original + post-maneuver orbits when option selected ───────────────
  useEffect(() => {
    const viewer  = window._driftViewer
    const Cesium  = window.Cesium
    const sat     = window.satellite

    const cleanup = (ref) => {
      if (ref.current && viewer) {
        try { viewer.entities.remove(ref.current) } catch {}
        ref.current = null
      }
    }
    cleanup(originalOrbitRef)
    cleanup(entityRef)
    cleanup(labelRef)
    cleanup(secAltOrbitRef)

    if (!selected || !options || !Cesium || !viewer) return

    const idx   = OPTION_STYLES.findIndex(s => s.id === selected)
    const opt   = options.maneuver_options?.[idx]
    const style = OPTION_STYLES[idx]
    if (!opt || !style) return

    const orb         = demo ? SAT_ORBIT_PARAMS[conjunction?.primarySatId] : null
    const { alt, inclination = 51.6 } = orbitParams
    const dAlt        = opt.altDelta ?? deltaAltKm(opt.delta_v_ms, alt)
    const newAlt      = alt + dAlt
    const newVel      = orbitalVelocity(newAlt)
    const burn        = burnDurationS(opt.fuel_kg)

    // Visual altitude offset for globe drawing — the real dAlt is only 0.4–5 km which is
    // invisible at globe scale (~420 km altitude). We exaggerate per-option so the three
    // routes are clearly distinct. The panel still displays the real computed numbers.
    // Option A (Maximum Safety) = highest visual orbit, C (Fuel Efficient) = lowest.
    const VIZ_ALT_OFFSETS = [180, 110, 55]  // km visual offset indexed by option [A, B, C]
    const vizDalt = VIZ_ALT_OFFSETS[idx] ?? Math.max(50, dAlt * 60)

    try {
      // Original orbit — dashed white, real current altitude for reference
      const origPositions = (demo && orb?.tle1 && sat)
        ? buildOrbitFromTLE(Cesium, sat, orb.tle1, orb.tle2, 0)
        : buildStaticOrbit(Cesium, alt, inclination, 0)

      if (origPositions.length >= 2) {
        originalOrbitRef.current = viewer.entities.add({
          polyline: {
            positions: origPositions,
            width: 2,
            material: new Cesium.PolylineDashMaterialProperty({
              color:      Cesium.Color.WHITE.withAlpha(0.38),
              dashLength: 18,
            }),
            arcType:           Cesium.ArcType.NONE,
            depthFailMaterial: new Cesium.ColorMaterialProperty(
              Cesium.Color.WHITE.withAlpha(0.08)
            ),
          },
        })
      }

      // Post-maneuver orbit — same ground track at visually exaggerated altitude
      const maneuverPositions = (demo && orb?.tle1 && sat)
        ? buildOrbitFromTLE(Cesium, sat, orb.tle1, orb.tle2, vizDalt)
        : buildStaticOrbit(Cesium, alt + vizDalt, inclination, lon)

      if (maneuverPositions.length >= 2) {
        entityRef.current = viewer.entities.add({
          polyline: {
            positions: maneuverPositions,
            width: 3,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.25,
              color: Cesium.Color.fromCssColorString(style.base).withAlpha(0.85),
            }),
            arcType:           Cesium.ArcType.NONE,
            depthFailMaterial: new Cesium.ColorMaterialProperty(
              Cesium.Color.fromCssColorString(style.base).withAlpha(0.12)
            ),
          },
        })
      }

      // Info label positioned at the visual orbit altitude (not real altitude)
      const labelAlt = (alt + vizDalt + 120) * 1000  // 120 km above the visual orbit
      const labelLat = Math.min((inclination ?? 51.6) - 5, 85) * Math.PI / 180
      const labelLon = (lon ?? 0) * Math.PI / 180
      const labelPos = Cesium.Cartesian3.fromRadians(labelLon, labelLat, labelAlt)

      labelRef.current = viewer.entities.add({
        position: labelPos,
        label: {
          text: [
            `${conjunction?.primarySatName ?? conjunction?.primarySatId} MANEUVERS`,
            `OPTION ${selected} · ${opt.label.toUpperCase()}`,
            `ΔV   +${opt.delta_v_ms.toFixed(2)} m/s  prograde`,
            `ALT  ${Math.round(alt)} → ${Math.round(newAlt)} km  (+${dAlt.toFixed(2)} km)`,
            `VEL  ${orbitalVelocity(alt).toFixed(3)} → ${newVel.toFixed(3)} km/s`,
            `BURN ${fmtDuration(burn)}   COST ${fmtCost(opt.fuel_cost_usd)}`,
          ].join('\n'),
          font:             'bold 12px "SF Mono", Consolas, monospace',
          fillColor:        Cesium.Color.fromCssColorString(style.base),
          outlineColor:     Cesium.Color.BLACK,
          outlineWidth:     2,
          style:            Cesium.LabelStyle.FILL_AND_OUTLINE,
          showBackground:   true,
          backgroundColor:  new Cesium.Color(0.02, 0.04, 0.1, 0.88),
          backgroundPadding: new Cesium.Cartesian2(10, 7),
          pixelOffset:      new Cesium.Cartesian2(14, 0),
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          verticalOrigin:   Cesium.VerticalOrigin.CENTER,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 40_000_000),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      })
      // ── If secondary can maneuver: draw its cheapest option in purple ────────
      if (demo && secOrbParams && secCheapestDV) {
        try {
          const secAlt     = secOrbParams.alt
          const secVizDalt = 70  // fixed visual offset for secondary's alternate path
          const secPositions = secOrbParams.tle1 && sat
            ? buildOrbitFromTLE(Cesium, sat, secOrbParams.tle1, secOrbParams.tle2, secVizDalt)
            : buildStaticOrbit(Cesium, secAlt + secVizDalt, secOrbParams.inclination ?? 51.6, 0)

          if (secPositions.length >= 2) {
            secAltOrbitRef.current = viewer.entities.add({
              polyline: {
                positions: secPositions,
                width: 2.5,
                material: new Cesium.PolylineGlowMaterialProperty({
                  glowPower: 0.3,
                  color: Cesium.Color.fromCssColorString('#a855f7').withAlpha(0.8),
                }),
                arcType:           Cesium.ArcType.NONE,
                depthFailMaterial: new Cesium.ColorMaterialProperty(
                  Cesium.Color.fromCssColorString('#a855f7').withAlpha(0.12)
                ),
              },
            })
          }
        } catch {}
      }
    } catch (e) {
      console.warn('ManeuverPanel: maneuver draw error', e)
    }
  }, [selected, options, orbitParams, demo, eventId, secOrbParams, secCheapestDV])

  // ── Cleanup on unmount ─────────────────────────────────────────────────────
  useEffect(() => () => {
    const viewer = window._driftViewer
    const remove = (ref) => {
      if (ref.current && viewer) try { viewer.entities.remove(ref.current) } catch {}
    }
    remove(primaryOrbitRef)
    remove(secondaryOrbitRef)
    remove(secLabelRef)
    remove(originalOrbitRef)
    remove(entityRef)
    remove(labelRef)
    remove(secAltOrbitRef)
  }, [])

  // ── Early returns ──────────────────────────────────────────────────────────

  if (primaryIsDebris) return (
    <div style={{ margin: '0 10px 6px', padding: '14px', borderRadius: 6, background: 'rgba(249,115,22,0.06)', border: '1px solid rgba(249,115,22,0.2)' }}>
      <span style={{ fontSize: 11, color: '#f97316', fontWeight: 600 }}>
        ⚠ Cannot maneuver — primary object is uncontrolled debris
      </span>
    </div>
  )

  if (loading) return (
    <div style={{ margin: '0 10px 6px', padding: '16px', fontSize: 11, color: '#64748b', textAlign: 'center' }}>
      Computing maneuver options…
    if (!conjunction) return
    let cancelled = false
    setManeuverData(null)
    setError(null)
    setSelected(null)
    onManeuverSelect?.(null)
    setLoading(true)

    fetchManeuvers(conjunction.primarySatId, conjunction.id)
      .then(data => {
        if (!cancelled) setManeuverData(data)
      })
      .catch(err => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [conjunction?.id])

  const options = maneuverData?.maneuver_options ?? null

  if (!conjunction) return null

  if (loading) return (
    <div style={{ margin: '0 10px 6px', padding: '16px', fontSize: 11, color: '#475569', textAlign: 'center' }}>
      Loading maneuver options…
    </div>
  )
  if (error) return (
    <div style={{ margin: '0 10px 6px', padding: '12px 14px', borderRadius: 6,
      background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)',
      fontSize: 11, color: '#f87171' }}>
      Maneuver fetch failed: {error}
    </div>
  )
  if (!options) return null

  const handleSelect = (opt, styleId) => {
    const next = selected === styleId ? null : styleId
    setSelected(next)
    onSelectManeuver?.(next ? LABEL_TO_SLUG[opt.label] : null)
  }

  if (!options || options.length === 0) return null

  const { alt } = orbitParams

  return (
    <div style={{ margin: '0 10px 6px', borderRadius: 6, background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.07)', padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: 'rgba(15, 23, 42, 0.6)',
      border: '1px solid rgba(255,255,255,0.07)',
      padding: '12px 14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#475569', textTransform: 'uppercase' }}>
          Avoidance Strategies
        </span>
        <span style={{ fontSize: 10, color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          current miss {options.current_miss_km?.toFixed(3)} km
        </span>
      </div>

      {/* ── Who maneuvers banner ─────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        marginBottom: 10, padding: '6px 10px',
        borderRadius: 5,
        background: 'rgba(34,211,238,0.06)',
        border: '1px solid rgba(34,211,238,0.2)',
      }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
          <circle cx="5" cy="5" r="4" stroke="#22d3ee" strokeWidth="1.4"/>
          <circle cx="5" cy="5" r="1.8" fill="#22d3ee"/>
        </svg>
        <span style={{ fontSize: 10, color: '#94a3b8', letterSpacing: '0.06em' }}>MANEUVERING OBJECT</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#22d3ee', marginLeft: 2 }}>
          {conjunction?.primarySatName ?? conjunction?.primarySatId}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#475569', fontFamily: "ui-monospace,'SF Mono',Consolas,monospace" }}>
          {conjunction?.primarySatId}
        </span>
      </div>

      {/* ── Secondary cannot maneuver notice ────────────────────────────────── */}
      {!secCanManeuver && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          marginBottom: 10, padding: '5px 10px',
          borderRadius: 5,
          background: 'rgba(249,115,22,0.05)',
          border: '1px solid rgba(249,115,22,0.18)',
        }}>
          <span style={{ fontSize: 10, color: '#f97316', letterSpacing: '0.04em' }}>
            ✕ THREAT OBJECT
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, color: '#fb923c' }}>
            {conjunction?.secondarySatName ?? conjunction?.secondarySatId}
          </span>
          <span style={{ fontSize: 10, color: '#64748b', marginLeft: 'auto' }}>
            uncontrolled · cannot maneuver
          </span>
        </div>
      )}

      {/* ── Secondary CAN maneuver — show cost comparison ────────────────────── */}
      {secCanManeuver && secCheapestDV && (
        <div style={{
          marginBottom: 10, padding: '8px 10px',
          borderRadius: 5,
          background: 'rgba(168,85,247,0.07)',
          border: '1px solid rgba(168,85,247,0.35)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#a855f7', letterSpacing: '0.06em' }}>
              ⚠ SECONDARY CAN ALSO MANEUVER
            </span>
          </div>
          <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.55 }}>
            <span style={{ color: '#c084fc', fontWeight: 600 }}>{conjunction?.secondarySatName}</span>
            {' '}could execute a cheaper avoidance burn instead.
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 5 }}>
            <div style={{ fontSize: 10, color: '#64748b' }}>
              Secondary cheapest: <span style={{ color: '#a855f7', fontWeight: 600 }}>
                {secCheapestDV.delta_v_ms.toFixed(2)} m/s · {fmtCost(secCheapestDV.fuel_cost_usd)}
              </span>
            </div>
            <div style={{ fontSize: 10, color: '#64748b' }}>
              Primary cheapest: <span style={{ color: '#86efac', fontWeight: 600 }}>
                {options.maneuver_options[2]?.delta_v_ms.toFixed(2)} m/s · {fmtCost(options.maneuver_options[2]?.fuel_cost_usd)}
              </span>
            </div>
          </div>
          <div style={{ fontSize: 10, color: '#7c3aed', marginTop: 3, fontStyle: 'italic' }}>
            Purple paths on globe = secondary satellite's alternate maneuver trajectories
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {options.maneuver_options.map((opt, i) => {
          const c      = OPTION_STYLES[i]
          const isSel  = selected === c.id
          const burn   = burnDurationS(opt.fuel_kg)
          const dAlt   = opt.altDelta ?? deltaAltKm(opt.delta_v_ms, alt)
          const newAlt = alt + dAlt
          const newMiss = options.current_miss_km + opt.miss_increase_km

          return (
            <div key={c.id} onClick={() => handleSelect(opt, c.id)} style={{
              borderRadius: 5,
              background: isSel ? c.bg : 'rgba(255,255,255,0.02)',
              border: `1px solid ${isSel ? c.border : 'rgba(255,255,255,0.06)'}`,
              padding: '9px 11px', cursor: 'pointer', transition: 'all 0.15s',
            }}>
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: c.base, background: `${c.base}18`, borderRadius: 3, padding: '1px 6px', letterSpacing: '0.06em' }}>{c.id}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>{opt.label}</span>
                  {isSel && <span style={{ fontSize: 9, color: c.base, letterSpacing: '0.08em' }}>● ON GLOBE</span>}
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: c.base }}>+{opt.miss_increase_km.toFixed(1)} km</span>
              </div>

              {/* Primary metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '5px 8px', marginBottom: 8 }}>
                <Metric label="ΔV"        value={`${opt.delta_v_ms.toFixed(2)} m/s`} />
                <Metric label="Fuel"      value={`${opt.fuel_kg.toFixed(3)} kg`} />
                <Metric label="Cost"      value={fmtCost(opt.fuel_cost_usd)} />
                <Metric label="Burn Time" value={fmtDuration(burn)} />
                <Metric label="Lifespan−" value={`${opt.lifespan_reduction_days.toFixed(1)}d`} />
                <Metric label="Score"     value={`${(opt.composite_score * 100).toFixed(0)}%`} color={c.base} />
              </div>

              {/* Trajectory comparison */}
              <div style={{ borderTop: `1px solid ${isSel ? c.border : 'rgba(255,255,255,0.05)'}`, paddingTop: 7, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px 8px' }}>
                <TrajRow label="Miss Dist"  from={`${options.current_miss_km.toFixed(3)} km`}    to={`${newMiss.toFixed(3)} km`}                          color={c.base} />
                <TrajRow label="Speed Δ"    from="baseline"                                       to={`+${opt.delta_v_ms.toFixed(2)} m/s`}                 color={c.base} />
                <TrajRow label="Altitude"   from={`${Math.round(alt)} km`}                        to={`${Math.round(newAlt)} km (+${dAlt.toFixed(2)} km)`} color={c.base} />
                <TrajRow label="Orb. Vel"   from={`${orbitalVelocity(alt).toFixed(3)} km/s`}      to={`${orbitalVelocity(newAlt).toFixed(3)} km/s`}        color={c.base} />
              </div>

              {isSel && (
          current miss {maneuverData?.current_miss_km?.toFixed(2)} km
        </span>
      </div>

      {/* Options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {options.map((opt, idx) => {
          const c        = OPTION_COLORS[idx] ?? OPTION_COLORS[2]
          const optId    = OPTION_IDS[idx] ?? String(idx + 1)
          const slug     = labelToSlug(opt.label)
          const isSelected = selected === idx

          return (
            <div
              key={opt.label}
              onClick={() => {
                const next = isSelected ? null : idx
                setSelected(next)
                onManeuverSelect?.(next === null ? null : slug)
              }}
              style={{
                borderRadius: 5,
                background: isSelected ? c.bg : 'rgba(255,255,255,0.02)',
                border: `1px solid ${isSelected ? c.border : 'rgba(255,255,255,0.06)'}`,
                padding: '9px 11px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {/* Option header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: c.base, background: `${c.base}18`,
                    borderRadius: 3, padding: '1px 6px', letterSpacing: '0.06em',
                  }}>
                    {optId}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                    {opt.label}
                  </span>
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: c.base, fontVariantNumeric: 'tabular-nums' }}>
                  +{opt.miss_increase_km} km
                </span>
              </div>

              {/* Metrics grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px 8px' }}>
                <Metric label="ΔV"         value={`${opt.delta_v_ms} m/s`} />
                <Metric label="Fuel"        value={`${opt.fuel_kg} kg`} />
                <Metric label="Cost"        value={formatCost(opt.fuel_cost_usd)} />
                <Metric label="Lifespan −"  value={`${opt.lifespan_reduction_days}d`} />
                <Metric label="Score"       value={opt.composite_score.toFixed(2)} />
              </div>

              {/* Execute button (only when selected) */}
              {isSelected && (
                <button
                  style={{ marginTop: 10, width: '100%', padding: '8px 0', borderRadius: 4, background: c.bg, border: `1px solid ${c.border}`, color: c.base, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer' }}
                  onClick={e => {
                    e.stopPropagation()
                    alert(`Option ${c.id} — ${opt.label}\nΔV: +${opt.delta_v_ms.toFixed(2)} m/s prograde\nAlt: ${Math.round(alt)} → ${Math.round(newAlt)} km (+${dAlt.toFixed(2)} km)\nBurn: ${fmtDuration(burn)} | Cost: ${fmtCost(opt.fuel_cost_usd)}\nFuel: ${opt.fuel_kg.toFixed(3)} kg | Lifespan −${opt.lifespan_reduction_days.toFixed(1)}d\nNew miss: ${newMiss.toFixed(3)} km\n\n(Demo — no uplink connected)`)
                    alert(`Maneuver Option ${optId} — ${opt.label}\nΔV: ${opt.delta_v_ms} m/s | Fuel: ${opt.fuel_kg} kg\nCost: ${formatCost(opt.fuel_cost_usd)}\n\n(Demo — no backend connected)`)
                  }}
                >
                  Execute Option {optId}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Metric({ label, value, color }) {
  return (
    <div>
      <span style={{ fontSize: 9, color: '#334155', letterSpacing: '0.08em', textTransform: 'uppercase', display: 'block' }}>{label}</span>
      <span style={{ fontSize: 11, color: color ?? '#94a3b8', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

function TrajRow({ label, from, to, color }) {
  return (
    <div>
      <span style={{ fontSize: 9, color: '#334155', letterSpacing: '0.07em', textTransform: 'uppercase', display: 'block', marginBottom: 2 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>{from}</span>
        <span style={{ fontSize: 9, color: '#334155' }}>→</span>
        <span style={{ fontSize: 10, color, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{to}</span>
      </div>
    </div>
  )
}
