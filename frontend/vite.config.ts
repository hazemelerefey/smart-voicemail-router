import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

const apiUpstream = process.env.SVR_API_UPSTREAM || 'http://127.0.0.1:8000'

const securityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), geolocation=(), microphone=(self)',
}

export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
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
    },
  },
})
