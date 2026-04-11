import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import GlobeView from './components/GlobeView'
import DashboardOverlay from './App.jsx'

createRoot(document.getElementById('root')).render(
  <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
    {/*
      Globe wrapper: shifts left by half the panel width so the globe center
      stays centred in the visible (non-panel) area. GlobeView is always 100vw
      internally — we never touch it. The outer overflow:hidden clips the edges.
      CSS vars --panel-pct and --panel-transition are set by DashboardOverlay.
    */}
    <div style={{
      position: 'absolute', inset: 0,
      transform: 'translateX(calc(var(--panel-pct, 30) * -0.5vw))',
      transition: 'var(--panel-transition, transform 0.25s ease)',
    }}>
      <GlobeView />
    </div>
    {/* Dashboard panels overlay on top */}
    <StrictMode>
      <DashboardOverlay />
    </StrictMode>
  </div>
)
