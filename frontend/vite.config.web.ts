import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

// Read the version from package.json
const packageJson = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))
const version = packageJson.version

export default defineConfig({
  root: 'src/renderer',
  base: './',
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(version)
  },
  resolve: {
    alias: {
      '@renderer': resolve(__dirname, 'src/renderer/src'),
      '@': resolve(__dirname, 'src/renderer/src')
    }
  },
  plugins: [
    vue(),
    {
      name: 'html-transform',
      transformIndexHtml(html) {
        // Update CSP:
        // - Allow connecting to GitHub API
        // - Relax connect-src to support accessing any backend host (for LAN / server deployment)
        return html.replace(
          /<meta\s+http-equiv=["']Content-Security-Policy["'].*?>/i,
          '<meta http-equiv="Content-Security-Policy" content="' +
          "default-src 'self'; " +
          "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; " +
          "style-src 'self' 'unsafe-inline'; " +
          // Use connect-src * here for local and LAN deployment; tighten later if a stricter policy is needed
          "connect-src * https://api.github.com;" +
          '">'
        )
      }
    }
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:54321',
        changeOrigin: true,
      },
      '/imgs': {
        target: 'http://127.0.0.1:54321',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: '../../dist-web',
    emptyOutDir: true
  }
})
