/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Connect, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const raiz = (caminho: string) => fileURLToPath(new URL(caminho, import.meta.url))

/**
 * Páginas públicas (/r/:token, /f/:codigo e /sair/:token) são servidas por responder.html, uma entrada
 * separada e leve. Em produção, configure o mesmo no servidor (veja o README).
 */
function paginasPublicas(): Plugin {
  const reescrever: Connect.NextHandleFunction = (req, _res, next) => {
    if (req.url && /^\/(r|f|sair)\/[^/]/.test(req.url)) {
      const i = req.url.indexOf('?')
      req.url = '/responder.html' + (i >= 0 ? req.url.slice(i) : '')
    }
    next()
  }
  return {
    name: 'toqqi-paginas-publicas',
    configureServer(server) {
      server.middlewares.use(reescrever)
    },
    configurePreviewServer(server) {
      server.middlewares.use(reescrever)
    },
  }
}

export default defineConfig({
  plugins: [paginasPublicas(), vue(), tailwindcss()],
  resolve: {
    alias: { '@': raiz('./src') },
  },
  build: {
    rollupOptions: {
      input: {
        app: raiz('./index.html'),
        responder: raiz('./responder.html'),
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
  },
})
