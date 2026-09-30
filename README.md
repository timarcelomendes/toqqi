# Toqqi

Plataforma para empresas B2B medirem e tratarem a satisfação dos clientes (NPS e CSAT).

| Pasta | O que é |
|---|---|
| `api/` | Backend em Python (FastAPI + PostgreSQL), com isolamento entre contas feito pelo próprio banco (RLS) |
| `web/` | Frontend em Vue 3 + TypeScript |
| `docs/` | Contrato da API e decisões |

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
1. **Fundação** (esta): contas, acesso, perfis e permissões, sessões, auditoria, plataforma.
2. Cadastros e pesquisas · 3. Envios · 4. Respostas e análise · 5. Conta e extras · 6. Troca.

## Publicação (Render)
O arquivo `render.yaml` cria tudo de uma vez: no Render, **New > Blueprint** e escolha este repositório.
Na criação, o Render pede `SUPERADMIN_EMAILS`, `ADMIN_INICIAL_EMAIL` e `ADMIN_INICIAL_SENHA` (seu acesso inicial).
A API cria sozinha o papel restrito do banco e aplica as migrações a cada subida.

Dois serviços apontando para este mesmo repositório:
- **API** (Web Service): pasta raiz `api/`; em *Build Filters*, incluir só `api/**`.
- **Site** (Static Site): pasta raiz `web/`; em *Build Filters*, incluir só `web/**`.

Assim, um commit que só mexe no backend republica só a API, e vice-versa. Os testes no GitHub seguem a mesma regra.
