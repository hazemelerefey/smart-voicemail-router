import path from 'path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

const apiUpstream = process.env.SVR_API_UPSTREAM || 'http://127.0.0.1:8000'

const securityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), geolocation=(), microphone=(self)',
  'Content-Security-Policy':
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self';",
}

const BLOCKED_PATH_RE = /(?:^|\/)\.|(?:\.(?:env|ini|log|bak|sql|sqlite|sqlite3|db|pem|key|enc))(?:$|\?)/i

function blockSensitiveFiles(): Plugin {
  const handler = (req: { url?: string }, res: { statusCode: number; end: (b?: string) => void }, next: () => void) => {
    const reqPath = (req.url || '/').split('?')[0]
    if (reqPath !== '/' && BLOCKED_PATH_RE.test(reqPath)) {
      res.statusCode = 404
      res.end('Not Found')
      return
    }
    next()
  }
  return {
    name: 'svr-block-sensitive-files',
    configureServer(server) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler)
    },
  }
}

export default defineConfig({
  plugins: [
    blockSensitiveFiles(),
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 3000,
    headers: securityHeaders,
    proxy: {
      '/api': {
        target: apiUpstream,
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: apiUpstream,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 3000,
    headers: securityHeaders,
    proxy: {
      '/api': {
        target: apiUpstream,
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: apiUpstream,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
