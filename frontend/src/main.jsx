import { StrictMode, useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import GlobeView from './components/GlobeView'
import DashboardOverlay from './App.jsx'
import LandingOverlay from './components/LandingOverlay.jsx'

function App() {
  const [activated, setActivated] = useState(false)
  const [landingMounted, setLandingMounted] = useState(true)
  const [activeNoradId, setActiveNoradId] = useState(25544)

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
      spinning = false
      clearInterval(poll)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  useEffect(() => {
    if (activated) window._driftSpinning = false
  }, [activated])

  const handleActivate = (noradId) => {
    // Show all entities when user hits Track
    const viewer = window._driftViewer
    if (viewer && !viewer.isDestroyed()) {
      viewer.entities.values.forEach(e => { e.show = true })
    }
    // Zoom to satellite if a NORAD ID was entered
    if (noradId) {
      setTimeout(() => window._driftFocusSat?.(noradId), 100)
      setActiveNoradId(Number(noradId))
    }
    setActivated(true)
    // Unmount landing after transition fully completes
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
      </div>

      {/* Dashboard — slides in after activation */}
      <StrictMode>
        <DashboardOverlay activated={activated} noradId={activeNoradId} />
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
