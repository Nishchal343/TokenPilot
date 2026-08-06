import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  appType: 'spa',
  server: {
    port: 5173,
    proxy: {
      '^/(auth|api|dashboard|organization|token-budgets|notifications|invitations|profile|settings|security|support|workspace|uploads)': {
        // Pin the proxy to IPv4. On Windows, `localhost` can resolve to ::1
        // while uvicorn is listening on 127.0.0.1, causing ECONNREFUSED.
        target: 'http://127.0.0.1:8000',
        bypass: (req, res, proxyOptions) => {
          const browserRoute = /^\/dashboard\/(company\/(teams|budget-approval|invitations|ai-workspace)|team-leader\/(my-team|team-budget|ai-workspace)|member\/(requests|ai-workspace))/.test(req.url || '')
          if (browserRoute || (req.headers.accept && req.headers.accept.indexOf('html') !== -1)) {
            return '/index.html'
          }
        }
      }
    }
  }
})
