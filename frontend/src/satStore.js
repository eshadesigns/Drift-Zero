// Shared satellite selection state between GlobeView and DashboardOverlay
// (they live in separate React trees, so we use a simple pub/sub store)

const listeners = new Set()

const state = {
  sat: null,
  analyzed: false,
  riskCount: 0,
  // Callbacks registered by GlobeView
  onClose: null,
  onAnalyze: null,
}

export const satStore = {
  select(sat) {
    state.sat = sat
    state.analyzed = false
    state.riskCount = 0
    listeners.forEach(fn => fn({ ...state }))
  },

  setAnalyzed(riskCount) {
    state.analyzed = true
    state.riskCount = riskCount
    listeners.forEach(fn => fn({ ...state }))
  },

  close() {
    state.sat = null
    state.analyzed = false
    state.riskCount = 0
    listeners.forEach(fn => fn({ ...state }))
  },

  subscribe(fn) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },

  getState() {
    return { ...state }
  },
}
