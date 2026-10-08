/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Connect, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { PAGINAS, paginaDoEndereco, robots, sitemap, urlDoSite } from './src/site/guias'

const raiz = (caminho: string) => fileURLToPath(new URL(caminho, import.meta.url))

/**
 * Páginas públicas (/r/:token, /f/:codigo, /sair/:token e /sair) são servidas por responder.html, uma entrada
 * separada e leve. Em produção, configure o mesmo no servidor (veja o README).
 */
function paginasPublicas(): Plugin {
  const reescrever: Connect.NextHandleFunction = (req, _res, next) => {
    if (req.url && (/^\/(r|f|sair)\/[^/]/.test(req.url) || /^\/sair\/?(\?|$)/.test(req.url))) {
      const i = req.url.indexOf('?')
      req.url = '/responder.html' + (i >= 0 ? req.url.slice(i) : '')
    } else if (req.url) {
      // Guias do site: /guias → guias.html, /reduzir-churn → reduzir-churn.html (no Render, as regras do render.yaml).
      const guia = paginaDoEndereco(req.url)
      if (guia && !(req.url.split('?')[0] ?? '').endsWith('.html')) {
        const i = req.url.indexOf('?')
        req.url = `/${guia.caminho}.html` + (i >= 0 ? req.url.slice(i) : '')
      }
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
 * Guias do site: o endereço público (SITE_URL ou, no Render, RENDER_EXTERNAL_URL) entra no `<link rel="canonical">`
 * de cada HTML (marca `<!-- canonical -->`) e no `sitemap.xml`; o `robots.txt` sai sempre. Sem endereço (build local),
 * a marca some e não há sitemap.
 */
function guiasDoSite(): Plugin {
  const site = urlDoSite(process.env)
  return {
    name: 'toqqi-guias',
    transformIndexHtml(html, ctx) {
      const guia = paginaDoEndereco(ctx.path)
      const caminho = guia ? `/${guia.caminho}` : ctx.path === '/index.html' ? '/' : null
      const tag = site && caminho ? `<link rel="canonical" href="${site}${caminho}" />` : ''
      return html.replace('<!-- canonical -->', tag)
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots(site) })
      if (site) {
        const hoje = new Date().toISOString().slice(0, 10)
        this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap(site, hoje) })
      }
    },
  }
}

/**
 * Etapa 5h (aviso de erros): a versão do site vai junto de cada erro mandado à API (`src/utils/erros.ts`). No Render, o
 * commit do build (`RENDER_GIT_COMMIT`, curto, como a da API em GET /saude); fora dele, "local".
 */
const versaoSite = (process.env.RENDER_GIT_COMMIT ?? '').replace(/[^0-9A-Za-z]/g, '').slice(0, 7) || 'local'

/**
 * Site atualizado (src/utils/atualizacao.ts): o build grava `/versao.json` com a versão dele; o app aberto numa aba
 * confere esse arquivo e, com versão nova no ar, avisa e abre a próxima tela já na versão nova.
 */
function versaoDoSite(): Plugin {
  return {
    name: 'toqqi-versao',
    apply: 'build',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'versao.json', source: `${JSON.stringify({ versao: versaoSite })}\n` })
    },
  }
}

export default defineConfig({
  plugins: [paginasPublicas(), guiasDoSite(), versaoDoSite(), vue(), tailwindcss()],
  define: { __TOQQI_VERSAO__: JSON.stringify(versaoSite) },
  resolve: {
    alias: { '@': raiz('./src') },
  },
  build: {
    rollupOptions: {
      input: {
        app: raiz('./index.html'),
        responder: raiz('./responder.html'),
        ...Object.fromEntries(PAGINAS.map((g) => [g.caminho, raiz(`./${g.caminho}.html`)])),
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
  },
})
