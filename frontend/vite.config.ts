import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Alias } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const pwaEnabled = process.env.BUILD_PWA === '1'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Keep PWA generation out of ordinary development; stale dev service
      // workers produce misleading results. Enable with BUILD_PWA=1 for
      // manual service-worker testing.
      disable: !pwaEnabled,
      strategies: 'generateSW',
      registerType: 'prompt',
      includeAssets: ['favicon.png', 'apple-touch-icon.png', 'pwa-maskable-512.png'],
      manifest: {
        name: 'Runestone',
        short_name: 'Runestone',
        description: 'Swedish textbook analysis service',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#060b26',
        theme_color: '#060b26',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'pwa-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Precache the versioned static app shell only. No runtime caching:
        // /api/, uploads, WebSockets, and media stay network-only so
        // authenticated responses never enter a shared cache. The fallback
        // serves the application shell for navigation requests offline.
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  // When the plugin is disabled the virtual registration module does not
  // exist; alias it to a no-op stub so development and tests still resolve.
  resolve: pwaEnabled
    ? undefined
    : {
        alias: [
          {
            find: 'virtual:pwa-register/react',
            replacement: fileURLToPath(
              new URL('./src/test/pwa-register-stub.ts', import.meta.url),
            ),
          } satisfies Alias,
        ],
      },
  css: {
    postcss: './postcss.config.js',
  },
})
