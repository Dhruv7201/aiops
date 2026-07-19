import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Builds into the python package so FastAPI can serve it (make frontend).
// In dev, /api is proxied to the aiops annotate server; `aiops annotate start`
// sets AIOPS_API_PORT to keep the proxy in sync with the backend port.
const apiPort = process.env.AIOPS_API_PORT ?? '8765'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/aiops/annotate/static',
    emptyOutDir: true,
  },
  server: {
    host: true, // bind 0.0.0.0 so the dev UI is reachable on the LAN
    proxy: {
      '/api': `http://localhost:${apiPort}`,
    },
  },
})
