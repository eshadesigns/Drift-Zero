import { useState, useEffect, useRef } from 'react'

const EXAMPLE_IDS = ['25544', '44713', '47526', '28654', '40115', '46984']
const GROTESK = "'Space Grotesk', system-ui, sans-serif"

export default function LandingOverlay({ onActivate }) {
  const [satId, setSatId] = useState('')
  const [phase, setPhase] = useState('idle')
  const [placeholder, setPlaceholder] = useState('')
  const [exampleIdx, setExampleIdx] = useState(0)
  const inputRef = useRef(null)
  const typingRef = useRef(null)

  // Typing animation for placeholder
  useEffect(() => {
    const target = EXAMPLE_IDS[exampleIdx]
    let i = 0
    let deleting = false
    let pauseFrames = 0

    typingRef.current = setInterval(() => {
      if (pauseFrames > 0) { pauseFrames--; return }
      if (!deleting) {
        i++
        setPlaceholder(target.slice(0, i))
        if (i === target.length) { deleting = true; pauseFrames = 14 }
      } else {
        i--
        setPlaceholder(target.slice(0, i))
        if (i === 0) {
          clearInterval(typingRef.current)
          setTimeout(() => setExampleIdx(prev => (prev + 1) % EXAMPLE_IDS.length), 200)
        }
      }
    }, 90)
    return () => clearInterval(typingRef.current)
  }, [exampleIdx])

  const handleSubmit = (e) => {
    e?.preventDefault()
    setPhase('dissolving')
    setTimeout(() => onActivate(satId.trim(), false), 900)
  }

  const handleDemo = () => {
    setPhase('dissolving')
    setTimeout(() => onActivate('25544', true), 900)
  }

  const dissolving = phase === 'dissolving'

  return (
    <div style={{
      position: 'absolute', inset: 0,
      zIndex: 50,
      pointerEvents: 'none',
      display: 'flex',
    }}>

      {/* Left half — fully pass-through so globe is interactive */}
      <div style={{ flex: 1, pointerEvents: 'none' }} />

      {/* Right half — dark panel with text */}
      <div style={{
        width: '48%',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '0 6% 0 4%',
        pointerEvents: dissolving ? 'none' : 'auto',
        opacity: dissolving ? 0 : 1,
        transform: dissolving ? 'translateX(40px)' : 'translateX(0)',
        transition: 'opacity 0.6s ease, transform 0.6s ease',
      }}>

        {/* Gradient backdrop — only behind the right text panel */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to right, transparent 0%, rgba(1,4,12,0.75) 18%, rgba(1,4,12,0.96) 45%)',
          opacity: dissolving ? 0 : 1,
          transition: 'opacity 0.9s ease',
          pointerEvents: 'none',
        }} />

        {/* Content */}
        <div style={{ position: 'relative' }}>

          {/* Drift Zero wordmark */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            marginBottom: 32,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#22d3ee',
              boxShadow: '0 0 10px #22d3ee, 0 0 20px rgba(34,211,238,0.4)',
            }} />
            <span style={{
              fontSize: 12, fontWeight: 700, letterSpacing: '0.2em',
              color: '#475569', textTransform: 'uppercase',
              fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
            }}>
              Drift Zero
            </span>
          </div>

          {/* Headline */}
          <h1 style={{
            margin: '0 0 20px',
            fontSize: 'clamp(32px, 3.6vw, 56px)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            lineHeight: 1.08,
            color: '#f1f5f9',
            fontFamily: GROTESK,
          }}>
            Space Domain<br />
            <span style={{
              background: 'linear-gradient(90deg, #22d3ee 0%, #818cf8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>
              Intelligence
            </span>
          </h1>

          {/* Subtext */}
          <p style={{
            margin: '0 0 36px',
            fontSize: 15, lineHeight: 1.65,
            color: 'rgba(148,163,184,0.75)',
            maxWidth: 380,
            fontFamily: GROTESK,
          }}>
            Real-time conjunction analysis, maneuver planning,
            and cascade risk assessment for your orbital assets.
          </p>

          {/* Input + Button */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 10, maxWidth: 400 }}>
            <div style={{
              flex: 1,
              background: 'rgba(3,7,18,0.7)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 8,
              backdropFilter: 'blur(12px)',
              transition: 'border-color 0.2s',
            }}>
              <input
                ref={inputRef}
                value={satId}
                onChange={e => setSatId(e.target.value)}
                onFocus={e => e.currentTarget.parentElement.style.borderColor = 'rgba(34,211,238,0.5)'}
                onBlur={e => e.currentTarget.parentElement.style.borderColor = 'rgba(255,255,255,0.12)'}
                placeholder={placeholder || 'Satellite ID…'}
                style={{
                  width: '100%', padding: '12px 16px',
                  background: 'transparent', border: 'none', outline: 'none',
                  color: '#e2e8f0', fontSize: 13, fontWeight: 500,
                  fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
                  letterSpacing: '0.04em', boxSizing: 'border-box',
                }}
              />
            </div>
            <button
              type="submit"
              style={{
                padding: '12px 20px',
                borderRadius: 8,
                background: 'linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)',
                border: 'none', color: '#fff',
                fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
                cursor: 'pointer', textTransform: 'uppercase',
                fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
                whiteSpace: 'nowrap',
                boxShadow: '0 0 20px rgba(99,102,241,0.4)',
                transition: 'opacity 0.15s, transform 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity='0.85'; e.currentTarget.style.transform='scale(1.03)' }}
              onMouseLeave={e => { e.currentTarget.style.opacity='1'; e.currentTarget.style.transform='scale(1)' }}
            >
              Track →
            </button>
          </form>

          <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={handleDemo}
              style={{
                padding: '10px 18px',
                borderRadius: 8,
                background: 'transparent',
                border: '1px solid rgba(99,102,241,0.4)',
                color: '#818cf8',
                fontSize: 12, fontWeight: 700, letterSpacing: '0.08em',
                cursor: 'pointer', textTransform: 'uppercase',
                fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace",
                transition: 'border-color 0.15s, color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background='rgba(99,102,241,0.1)'; e.currentTarget.style.borderColor='rgba(99,102,241,0.7)' }}
              onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.borderColor='rgba(99,102,241,0.4)' }}
            >
              ◈ Demo Mode
            </button>
            <span style={{ fontSize: 11, color: '#334155', fontFamily: "ui-monospace, 'SF Mono', Consolas, monospace" }}>
              or press Enter to track
            </span>
          </div>

        </div>
      </div>
    </div>
  )
}
