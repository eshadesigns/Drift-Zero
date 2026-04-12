export default function NaturalLanguageAlert({ conjunction }) {
  if (!conjunction) return null

  return (
    <div style={{
      margin: '0 10px 6px',
      borderRadius: 6,
      background: 'rgba(192, 132, 252, 0.05)',
      border: '1px solid rgba(192, 132, 252, 0.18)',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <div style={{
          width: 20, height: 20, borderRadius: 4,
          background: 'rgba(192, 132, 252, 0.2)',
          border: '1px solid rgba(192, 132, 252, 0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, color: '#c084fc', fontWeight: 700, flexShrink: 0,
        }}>
          AI
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>
          AI Alert
        </span>
      </div>
      <p style={{
        fontSize: 11, color: '#475569', lineHeight: 1.6,
        margin: 0, fontStyle: 'italic',
      }}>
        AI alert generation coming soon — Claude API integration in progress.
      </p>
    </div>
  )
}
