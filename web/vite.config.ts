import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the browser talks to Vite (port 5173), which forwards /api to FastAPI (port 8000).
// Same origin for the browser means the refresh-token cookie works without CORS tricks.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
