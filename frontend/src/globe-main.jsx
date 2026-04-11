import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import GlobeView from './components/GlobeView'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GlobeView />
  </StrictMode>,
)
