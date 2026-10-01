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
| 5. Conta e extras · 6. Troca | depois | — |

## Publicação (Render)
O arquivo `render.yaml` cria tudo de uma vez: no Render, **New > Blueprint** e escolha este repositório.
Na criação, o Render pede `SUPERADMIN_EMAILS`, `ADMIN_INICIAL_EMAIL` e `ADMIN_INICIAL_SENHA` (seu acesso inicial).
A API cria sozinha o papel restrito do banco e aplica as migrações a cada subida.

Dois serviços apontando para este mesmo repositório:
- **API** (Web Service): pasta raiz `api/`; em *Build Filters*, incluir só `api/**`.
- **Site** (Static Site): pasta raiz `web/`; em *Build Filters*, incluir só `web/**`.

Assim, um commit que só mexe no backend republica só a API, e vice-versa. Os testes no GitHub seguem a mesma regra.

Um terceiro serviço, **toqqi-tarefas** (Cron Job), roda `python -m toqqi.tarefas` a cada 15 minutos: robô de envio,
lembretes, envios pendentes, webhooks, análise de comentários com IA, alerta de pico de reclamações e o resumo semanal
(segundas, a partir das 8h). Ele conecta direto no banco (não acorda a API) e recebe as variáveis da API por
`fromService`. Custa por segundo de execução, com mínimo de US$ 1 por mês.

**IA (OpenAI)**: a chave `OPENAI_API_KEY` vai no painel do Render, em *Environment*, nos **dois** serviços (toqqi-api e
toqqi-tarefas), e não no `render.yaml`. Sem ela, tudo funciona e os temas seguem por palavras-chave. Detalhes em
`docs/api-etapa-4b.md` e `api/README.md`.

Variáveis com `value:` no `render.yaml` são reaplicadas a cada sincronização do Blueprint. Para trocar o
`EMAIL_PROVIDER` (ex.: ZeptoMail), altere o arquivo, não o painel do Render, e acrescente `EMAIL_FROM` e
`ZEPTOMAIL_TOKEN` também no toqqi-tarefas.
