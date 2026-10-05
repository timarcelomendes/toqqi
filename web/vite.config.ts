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

/**
 * Etapa 5h (aviso de erros): a versão do site vai junto de cada erro mandado à API (`src/utils/erros.ts`). No Render, o
 * commit do build (`RENDER_GIT_COMMIT`, curto, como a da API em GET /saude); fora dele, "local".
 */
const versaoSite = (process.env.RENDER_GIT_COMMIT ?? '').replace(/[^0-9A-Za-z]/g, '').slice(0, 7) || 'local'

export default defineConfig({
  plugins: [paginasPublicas(), vue(), tailwindcss()],
  define: { __TOQQI_VERSAO__: JSON.stringify(versaoSite) },
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
