import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendHost = process.env.BACKEND_HOST || '127.0.0.1'
const backendPort = process.env.BACKEND_PORT || '8080'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
