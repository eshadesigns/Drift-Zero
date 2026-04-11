import { useState, useCallback, useEffect } from 'react'
import StatsBar from './components/dashboard/StatsBar'
import AlertQueue from './components/dashboard/AlertQueue'
import ManeuverPanel from './components/dashboard/ManeuverPanel'
import NaturalLanguageAlert from './components/dashboard/NaturalLanguageAlert'
import CascadeAnalysis from './components/dashboard/CascadeAnalysis'

const PANEL_MIN = 15   // % of screen width
const PANEL_MAX = 55
const DEFAULT_PANEL = 30

export default function DashboardOverlay() {
  const [selectedConjunction, setSelectedConjunction] = useState(null)
  const [panelPct, setPanelPct] = useState(DEFAULT_PANEL)
  const [collapsed, setCollapsed] = useState(null) // null | 'panels'
  const [isDragging, setIsDragging] = useState(false)
  const [dividerHover, setDividerHover] = useState(false)

  // ── Drag-to-resize ──────────────────────────────────────────────────────────
  const onDividerMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
    setCollapsed(null)
  }, [])

  useEffect(() => {
    if (!isDragging) return
    const onMouseMove = (e) => {
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
      {/* ── StatsBar — top ───────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        pointerEvents: 'auto',
      }}>
        <StatsBar />
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

      {/* ── Divider / toggle tab ─────────────────────────────────────────────── */}
      <div
        onMouseDown={onDividerMouseDown}
        onMouseEnter={() => setDividerHover(true)}
        onMouseLeave={() => setDividerHover(false)}
        style={{
          position: 'absolute',
          top: 44,
          bottom: 0,
          right: dividerRight,
          width: collapsed === 'panels' ? 20 : 6,
          zIndex: 11,
          cursor: collapsed === 'panels' ? 'pointer' : 'col-resize',
          transition,
          pointerEvents: 'auto',
          background: isDragging
            ? 'rgba(34,211,238,0.3)'
            : dividerHover
              ? 'rgba(34,211,238,0.12)'
              : 'rgba(255,255,255,0.04)',
          borderLeft: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
        }}
      >
        {/* Collapse / expand button */}
        <button
          onMouseDown={(e) => e.stopPropagation()}
          onClick={toggleCollapse}
          style={{
            width: 18,
            height: 18,
            borderRadius: 3,
            background: dividerHover || collapsed === 'panels'
              ? 'rgba(34,211,238,0.15)'
              : 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#94a3b8',
            cursor: 'pointer',
            fontSize: 13,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
            padding: 0,
            opacity: dividerHover || collapsed === 'panels' ? 1 : 0,
            transition: 'opacity 0.15s',
          }}
          title={collapsed === 'panels' ? 'Expand panels' : 'Collapse panels'}
        >
          {collapsed === 'panels' ? '‹' : '›'}
        </button>

        {/* Drag handle dots — visible on hover */}
        {collapsed !== 'panels' && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 3,
            opacity: dividerHover ? 0.6 : 0.2,
            transition: 'opacity 0.15s',
          }}>
            {[0,1,2,3,4].map(i => (
              <div key={i} style={{
                width: 3,
                height: 3,
                borderRadius: '50%',
                background: '#94a3b8',
              }} />
            ))}
          </div>
        )}
      </div>

      {/* Cursor style during drag */}
      {isDragging && (
        <style>{`* { cursor: col-resize !important; user-select: none !important; }`}</style>
      )}
    </>
  )
}
