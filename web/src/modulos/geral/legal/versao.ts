// Versão dos Termos de uso e da Política de privacidade (uma só para os dois). Precisa ser igual a
// VERSAO_DOCUMENTOS em api/toqqi/modulos/acesso/termos.py: ao mudar um texto de forma relevante, suba os dois
// no mesmo commit, junto com VIGENTE_DESDE, e todo mundo vê a tela de aceite de novo (docs/api-aceite-lgpd.md §0).
// Versão 2 (etapa 5d), vigente desde 02/10/2026: os Termos de uso e a Política de privacidade passam a descrever os
// cinco recursos de IA (passos das ações, resumo do painel e parecer dos relatórios, além da análise de comentários e do
// assistente).
// Versão 3 (etapa 5e), vigente desde 02/10/2026: a Política de privacidade passa a descrever o registro de e-mails
// enviados (endereço de quem recebeu, assunto, situação e erro; guardado por 90 dias).
// Versão 4 (etapa 5f), vigente desde 03/10/2026: registros de acesso (data, hora e IP, por 6 meses, à parte), exclusão
// automática 90 dias depois do fim do período pago ou do teste (com aviso 7 dias antes), exportação de todos os dados
// em Configurações › Dados da conta e, nos Termos, as mesmas regras no teste e no fim do contrato.
// Versão 5, vigente desde 03/10/2026: nos Termos, o nível "Mais detalhado" da IA gasta 2 análises da cota por resumo,
// parecer ou pergunta ao ToqqiAI (os outros níveis, 1).
export const VERSAO_DOCUMENTOS = 5
/** Data em que a versão atual (VERSAO_DOCUMENTOS) passou a valer (AAAA-MM-DD). */
export const VIGENTE_DESDE = '2026-10-03'
