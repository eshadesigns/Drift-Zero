import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import GlobeView from './components/GlobeView'
import DashboardOverlay from './App.jsx'

createRoot(document.getElementById('root')).render(
  <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
    {/* GlobeView outside StrictMode — prevents Cesium double-init crash */}
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
