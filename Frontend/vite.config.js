import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '^/(auth|dashboard|organization|token-budgets|notifications|invitations|profile|settings|security|support|uploads)': {
        // Pin the proxy to IPv4. On Windows, `localhost` can resolve to ::1
        // while uvicorn is listening on 127.0.0.1, causing ECONNREFUSED.
        target: 'http://127.0.0.1:8000',
        bypass: (req, res, proxyOptions) => {
          if (req.headers.accept && req.headers.accept.indexOf('html') !== -1) {
            return '/index.html'
          }
        }
      }
    }
  }
})
