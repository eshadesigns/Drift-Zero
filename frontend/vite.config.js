import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Read .env from repo root
  envDir: '../',
  plugins: [react()],
})
