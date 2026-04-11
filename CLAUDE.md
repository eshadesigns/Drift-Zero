# Drift Zero — Claude Code Context

## Project
Space Domain Intelligence Platform. SCI Hackathon 2026.
Stack: React 19 + Vite 8, CesiumJS via CDN, satellite.js via CDN, no npm Cesium.

## Repo layout
```
frontend/          ← all frontend code, run `npm run dev` from HERE (not root)
  src/
    main.jsx       ← entry point — GlobeView OUTSIDE StrictMode, DashboardOverlay inside
    App.jsx        ← DashboardOverlay, absolute-positioned panels overlay on globe
    index.css      ← minimal reset, #root is 100vw/100vh
    components/
      GlobeView.jsx        ← Kushagra's — DO NOT MODIFY
      SatelliteModal.jsx   ← Kushagra's — DO NOT MODIFY
      dashboard/
        StatsBar.jsx          ← Madhu
        AlertQueue.jsx        ← Madhu
        NaturalLanguageAlert.jsx ← Madhu
        ManeuverPanel.jsx     ← Madhu
        CascadeAnalysis.jsx   ← Madhu
    data/
      mockData.js    ← realistic orbital mock data (NASA CARA / SpaceX / ESA)
pipeline/            ← Python TLE ingestion scripts
backend/             ← separate backend
```

## Critical rules

### Never touch GlobeView.jsx or SatelliteModal.jsx
Kushagra owns these. Any change risks breaking the globe. If a feature needs globe interaction, coordinate with Kushagra first.

### GlobeView must stay OUTSIDE React StrictMode
StrictMode double-mounts components. Cesium viewer init runs twice on same container = crash.
`main.jsx` structure must stay:
```jsx
<div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
  <GlobeView />          {/* outside StrictMode — intentional */}
  <StrictMode>
    <DashboardOverlay />
  </StrictMode>
</div>
```

### Dashboard panels are overlays, not layout children
All dashboard panels use `position: absolute` on top of the full-screen globe.
Do NOT wrap GlobeView in a flex container or change its dimensions.

### npm must run from frontend/
There is no `package.json` at repo root. Always:
```bash
cd frontend
npm run dev
```

### SSL on this network
Git pull requires: `git config http.sslVerify false` (already set globally).
This is a known network/proxy issue — not a code problem.

## Styling
Pure inline styles throughout dashboard components — no Tailwind, no CSS modules.
Color palette:
- Background: `rgba(3, 7, 18, 0.92)`
- Border: `rgba(255,255,255,0.07)`
- Text primary: `#e2e8f0`
- Text muted: `#94a3b8`
- Text dim: `#475569`
- Cyan accent: `#22d3ee`
- Critical: `#f87171`
- High: `#fb923c`
- Medium: `#fbbf24`
- Low: `#94a3b8`

## Team split
- **Madhu**: App.jsx, StatsBar, AlertQueue, ManeuverPanel, NaturalLanguageAlert, CascadeAnalysis, mockData.js
- **Kushagra**: GlobeView.jsx, SatelliteModal.jsx, globe rendering/interaction
- **Others**: backend, pipeline

## Branches
- `main` — working base, deploy target
- `feat/globeview` — Kushagra's globe work
- `backend` — backend team
