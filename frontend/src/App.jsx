import { useState, useRef, useCallback, useEffect } from 'react'
// GlobeView lives on Kushagra's branch — placeholder here for dev
const GlobeView = () => <div className="w-full h-full bg-gray-900 flex items-center justify-center text-gray-600 text-sm">Globe (Kushagra)</div>
import StatsBar from './components/dashboard/StatsBar'
import AlertQueue from './components/dashboard/AlertQueue'
import ManeuverPanel from './components/dashboard/ManeuverPanel'
import NaturalLanguageAlert from './components/dashboard/NaturalLanguageAlert'
import CascadeAnalysis from './components/dashboard/CascadeAnalysis'

const GLOBE_MIN = 30
const GLOBE_MAX = 85
const DEFAULT_SPLIT = 70

export default function App() {
  const [selectedConjunction, setSelectedConjunction] = useState(null)
  const [splitPct, setSplitPct] = useState(DEFAULT_SPLIT)
  const [collapsed, setCollapsed] = useState(null) // 'globe' | 'panels' | null
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef(null)

  // ── Drag logic ───────────────────────────────────────────────────────────────
  const onDividerMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
    setCollapsed(null)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const onMouseMove = (e) => {
      if (!containerRef.current) return
      const { left, width } = containerRef.current.getBoundingClientRect()
      const pct = ((e.clientX - left) / width) * 100
      setSplitPct(Math.min(GLOBE_MAX, Math.max(GLOBE_MIN, pct)))
    }

    const onMouseUp = () => setIsDragging(false)

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [isDragging])

  // ── Collapse logic ───────────────────────────────────────────────────────────
  const collapseGlobe = () => {
    if (collapsed === 'globe') { setCollapsed(null); setSplitPct(DEFAULT_SPLIT) }
    else setCollapsed('globe')
  }

  const collapsePanels = () => {
    if (collapsed === 'panels') { setCollapsed(null); setSplitPct(DEFAULT_SPLIT) }
    else setCollapsed('panels')
  }

  const globeWidth = collapsed === 'globe'  ? '0%'
                   : collapsed === 'panels' ? '100%'
                   : `${splitPct}%`

  const panelWidth = collapsed === 'panels' ? '0%'
                   : collapsed === 'globe'  ? '100%'
                   : `${100 - splitPct}%`

  const transition = isDragging ? 'none' : 'width 0.25s ease'

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white select-none">

      <StatsBar />

      <div ref={containerRef} className="flex flex-1 overflow-hidden relative">

        {/* ── Globe pane — Kushagra's zone ── */}
        <div style={{ width: globeWidth, transition }} className="h-full overflow-hidden shrink-0">
          <GlobeView />
        </div>

        {/* ── Resizable divider ── */}
        {!collapsed && (
          <div
            onMouseDown={onDividerMouseDown}
            className="relative z-10 flex flex-col items-center justify-center w-[6px] shrink-0 bg-gray-800 hover:bg-blue-500 cursor-col-resize transition-colors group"
          >
            <button
              onMouseDown={(e) => e.stopPropagation()}
              onClick={collapsePanels}
              className="absolute top-[40%] -translate-y-full mb-1 w-5 h-5 rounded-sm bg-gray-700 hover:bg-blue-600 text-gray-300 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              title="Expand globe"
            >›</button>
            <button
              onMouseDown={(e) => e.stopPropagation()}
              onClick={collapseGlobe}
              className="absolute top-[40%] translate-y-full mt-1 w-5 h-5 rounded-sm bg-gray-700 hover:bg-blue-600 text-gray-300 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              title="Expand panels"
            >‹</button>
          </div>
        )}

        {/* Restore button when collapsed */}
        {collapsed && (
          <button
            onClick={() => { setCollapsed(null); setSplitPct(DEFAULT_SPLIT) }}
            className={`absolute top-1/2 -translate-y-1/2 z-20 w-6 h-12 rounded bg-gray-700 hover:bg-blue-600 text-gray-300 text-xs flex items-center justify-center transition-colors ${
              collapsed === 'globe' ? 'left-2' : 'right-2'
            }`}
            title="Restore split"
          >
            {collapsed === 'globe' ? '›' : '‹'}
          </button>
        )}

        {/* ── Dashboard panels ── */}
        <div
          style={{ width: panelWidth, transition }}
          className="h-full flex flex-col border-l border-gray-800 overflow-y-auto overflow-x-hidden shrink-0"
        >
          <AlertQueue
            selected={selectedConjunction}
            onSelect={setSelectedConjunction}
          />
          {selectedConjunction && (
            <>
              <NaturalLanguageAlert conjunction={selectedConjunction} />
              <ManeuverPanel conjunction={selectedConjunction} />
              <CascadeAnalysis conjunction={selectedConjunction} />
            </>
          )}
        </div>

      </div>
    </div>
  )
}
