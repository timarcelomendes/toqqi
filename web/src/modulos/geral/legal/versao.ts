// Versão dos Termos de uso e da Política de privacidade (uma só para os dois). Precisa ser igual a
// VERSAO_DOCUMENTOS em api/toqqi/modulos/acesso/termos.py: ao mudar um texto de forma relevante, suba os dois
// no mesmo commit, junto com VIGENTE_DESDE, e todo mundo vê a tela de aceite de novo (docs/api-aceite-lgpd.md §0).
// Versão 2 (etapa 5d), vigente desde 02/10/2026: os Termos de uso e a Política de privacidade passam a descrever os
// cinco recursos de IA (passos das ações, resumo do painel e parecer dos relatórios, além da análise de comentários e do
// assistente).
// Versão 3 (etapa 5e), vigente desde 02/10/2026: a Política de privacidade passa a descrever o registro de e-mails
// enviados (endereço de quem recebeu, assunto, situação e erro; guardado por 90 dias).
export const VERSAO_DOCUMENTOS = 3
/** Data em que a versão atual (VERSAO_DOCUMENTOS) passou a valer (AAAA-MM-DD). */
export const VIGENTE_DESDE = '2026-10-02'
