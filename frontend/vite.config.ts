import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],
  // Le pré-bundling casse le chemin du worker de maplibre-gl (import.meta.url).
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  // Dans Docker : API_PROXY_TARGET=http://web:8000.
  server: {
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
        // Garde Host: localhost:5173, accepté par ALLOWED_HOSTS en DEBUG.
        changeOrigin: false,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
