# Toqqi

Plataforma para empresas B2B medirem e tratarem a satisfação dos clientes (NPS e CSAT).

| Pasta | O que é |
|---|---|
| `api/` | Backend em Python (FastAPI + PostgreSQL), com isolamento entre contas feito pelo próprio banco (RLS) |
| `web/` | Frontend em Vue 3 + TypeScript |
| `docs/` | Contrato da API e decisões |
| `design-system/` | Marca (logo e ícone oficiais), cores, tipografia e guia dos componentes |

A especificação funcional (o que o sistema faz) fica no documento "Rakiti: especificação funcional" e é a única fonte para o código novo.

## Rodar localmente
1. Banco: `psql -U postgres -f api/scripts/preparar_banco.sql` (cria os papéis `toqqi` e `toqqi_app` e os bancos).
2. API: `cd api && cp .env.example .env` (ajuste `JWT_SECRET`), `pip install -r requirements.txt`, `uvicorn toqqi.main:app --port 8000`.
3. Web: `cd web && cp .env.example .env && npm install && npm run dev`.

## Testes
- API: `cd api && python -m pytest -q`
- Web: `cd web && npm run build && npm test`

Os testes rodam no GitHub a cada envio (`.github/workflows/testes.yml`).

## Etapas
| Etapa | Situação | Contrato |
|---|---|---|
| 1. Fundação: contas, acesso, perfis e permissões, sessões, auditoria, plataforma | pronta | `docs/api-etapa-1.md` |
| 2. Cadastros e pesquisas: contatos, empresas, importação, formulários, páginas de resposta | pronta | `docs/api-etapa-2.md` |
| 3a. Envios: e-mail, robô, lembretes, WhatsApp por link, descadastro | pronta | `docs/api-etapa-3.md` |
| 3b. Integrações: chave da conta, disparo por evento, webhooks, WhatsApp automático | pronta | `docs/api-etapa-3b.md` |
| 4a. Respostas, planos de ação e painel | pronta | `docs/api-etapa-4a.md` |
| Extra: dados da empresa e logo (Configurações › Empresa) | pronta | `docs/api-dados-empresa.md` |
| 4b. Relatórios, IA por resposta, picos de reclamação e resumo semanal | pronta | `docs/api-etapa-4b.md` |
| 5a. Assinatura e cobrança pelo Asaas | pronta (testada no sandbox) | `docs/api-etapa-5a.md` |
| 5b. Ajuda e assistente (chat com os dados da conta e a cota de IA do plano) | pronta (falta conferir com a chave da OpenAI) | `docs/api-etapa-5b.md` |
| Extra: aceite dos Termos e da Política de privacidade (LGPD) e aviso de cookies | pronta (textos são rascunho: revisar com advogado e preencher os `[a confirmar]`) | `docs/api-aceite-lgpd.md` |
| 5c. Crescimento: indicações dos promotores e oportunidades de oferta | pronta | `docs/api-etapa-5c.md` |
| 5d. IA sob demanda: resumo do painel, parecer dos relatórios, passos das ações, modelo e estilo | pronta | `docs/api-etapa-5d.md` |
| 5. Resto: e-mails com visual guiado, auditoria completa, zona de risco, exportação (LGPD) · 6. Lançamento (sem migração: não há clientes no Rakiti) | depois | — |

## Publicação (Render)
O arquivo `render.yaml` cria tudo de uma vez: no Render, **New > Blueprint** e escolha este repositório.
Na criação, o Render pede `SUPERADMIN_EMAILS`, `ADMIN_INICIAL_EMAIL` e `ADMIN_INICIAL_SENHA` (seu acesso inicial).
A conta inicial só é criada com o banco vazio: trocar `ADMIN_INICIAL_EMAIL` depois não cria outra conta (crie as
demais pela Plataforma). Quem está em `SUPERADMIN_EMAILS` (separados por vírgula, e-mail confirmado) vê a Plataforma.
A API cria sozinha o papel restrito do banco e aplica as migrações a cada subida.

Dois serviços apontando para este mesmo repositório:
- **API** (Web Service): pasta raiz `api/`; em *Build Filters*, incluir só `api/**`.
- **Site** (Static Site): pasta raiz `web/`; em *Build Filters*, incluir só `web/**`.

Assim, um commit que só mexe no backend republica só a API, e vice-versa. Os testes no GitHub seguem a mesma regra.

**Tarefas agendadas** (robô de envio, lembretes, envios pendentes, webhooks, fila da IA, alerta de pico de reclamações,
resumo semanal e rotinas da assinatura): a rotina do GitHub `.github/workflows/tarefas.yml` chama
`POST /api/v1/interno/tarefas` a cada 30 minutos, sem custo. Ela precisa do segredo `TAREFAS_TOKEN` no GitHub
(*Settings › Secrets and variables › Actions*), com o mesmo valor da variável `TAREFAS_TOKEN` da toqqi-api no Render; dá
para rodar à mão em *Actions › Tarefas agendadas › Run workflow*. Cada conta decide se é hora, então os atrasos do GitHub
não fazem mal. O GitHub desliga a rotina depois de 60 dias sem commits (avisa por e-mail; religar em *Actions*).
O Cron Job do Render (`toqqi-tarefas`, `python -m toqqi.tarefas` direto no banco, mais pontual, mínimo de US$ 1 por mês)
está comentado no `render.yaml` com o passo a passo para voltar, quando a API estiver no plano pago.

**IA (OpenAI)**: a chave `OPENAI_API_KEY` vai no painel do Render, em *Environment*, na toqqi-api (e no toqqi-tarefas,
se o Cron Job estiver ligado), e não no `render.yaml`. Sem ela, tudo funciona e os temas seguem por palavras-chave. Detalhes em
`docs/api-etapa-4b.md` e `api/README.md`. A mesma chave liga o **assistente** (botão no canto das telas): modelo e esforço
em `IA_ASSISTENTE_MODELO` e `IA_ASSISTENTE_ESFORCO`, cota da cortesia em `IA_COTA_CORTESIA` (no `render.yaml`). Ele manda à
OpenAI a pergunta, as últimas mensagens e os dados consultados (inclusive nomes e comentários): cite na política de
privacidade. Detalhes em `docs/api-etapa-5b.md`. Para o usuário, o assistente se chama **ToqqiAI** e usa o ícone da
marca (`web/src/components/app/IconeToqqiAI.vue`, 02/10); rotas, chaves e variáveis seguem com "assistente".

**Cobrança (Asaas)**: `ASAAS_API_KEY` no painel do Render na toqqi-api (e no toqqi-tarefas, se o Cron Job estiver ligado); `ASAAS_WEBHOOK_TOKEN` só na
toqqi-api (32 a 255 caracteres, sem espaços). No Asaas, o webhook de cobranças aponta para
`https://<api>/api/v1/asaas/webhook` com o mesmo token. Comece pelo sandbox (chave `$aact_hmlg_…`); ao trocar para a chave
de produção, as assinaturas de teste são canceladas sozinhas. Sem as chaves, a tela de Assinatura avisa que a cobrança online
ainda não está disponível. Detalhes em `docs/api-etapa-5a.md` e `api/README.md`.

Variáveis com `value:` no `render.yaml` são reaplicadas a cada sincronização do Blueprint. Para trocar o
`EMAIL_PROVIDER` (ex.: ZeptoMail), altere o arquivo, não o painel do Render, e acrescente `EMAIL_FROM` e
`ZEPTOMAIL_TOKEN` na toqqi-api (e no toqqi-tarefas, se o Cron Job estiver ligado).
