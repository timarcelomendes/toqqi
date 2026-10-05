/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** Versão do build (o commit curto do Render, ou "local"), posta pelo `define` do vite.config.ts (etapa 5h). */
declare const __TOQQI_VERSAO__: string
