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
| 5e. E-mails: visual guiado, banco de imagens, e-mails do sistema na cor da marca, registro de e-mails enviados | pronta | `docs/api-etapa-5e.md` |
| 5f. Dados da conta: exportação completa e CSV das listas, zona de risco, auditoria por grupo, registros de acesso (6 meses), exclusão automática depois do encerramento, IP real atrás do proxy | pronta | `docs/api-etapa-5f.md` |
| 6. Lançamento (sem migração: não há clientes no Rakiti): backup diário cifrado no Cloudflare R2 com restauração testada | pronta (falta criar o bucket e os segredos) | `docs/backup.md` |
| Extra: Ajuda em jornadas (onde, como e resultado das 13 principais funcionalidades), abertura da Ajuda e respostas do ToqqiAI | pronta | `docs/ajuda-jornadas.md` |
| 5k. Preços: Pix com 3% de desconto, anual com 10%, plano Personalizado (calculadora), WhatsApp sem franquia, IA no GPT-6 Luna/Sol, limites novos (Empresa 5.000 contatos, cota do teste) | pronta | `docs/api-etapa-5k.md` |

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

## Conector do Bling (aplicativo do Toqqi)
O Bling exige um aplicativo do Toqqi no portal do desenvolvedor do Bling (developer.bling.com.br › Aplicativos):
1. Crie o aplicativo (tipo público, se for listar na loja do Bling; privado serve para testar com a sua conta).
   - **URL de redirecionamento**: `https://<API_PUBLIC_URL>/api/v1/publico/conectores/bling/retorno`
   - **Escopos**: contatos (leitura), notas fiscais (leitura) e dados básicos da empresa.
   - **Webhooks**: servidor `https://<API_PUBLIC_URL>/api/v1/publico/conectores/bling/aviso`, recursos `invoice` e
     `consumer_invoice` com a ação `created`.
2. No Render (toqqi-api › Environment), ponha `BLING_CLIENT_ID` e `BLING_CLIENT_SECRET` (só no painel, nunca no
   repositório). Sem eles, o cartão do Bling aparece como "Em breve".
3. Teste: Integrações › CRM e ERP › Bling › "Conectar com o Bling", autorize, "Sincronizar agora" e emita uma nota de
   um cliente com o seu e-mail.

## Monitor externo
`GET /api/v1/saude` (sem login) responde `{"ok": true, "banco": true, "versao": "a1b2c3d"}` quando a API e o banco
respondem (um `SELECT 1` de até 3 s); com o banco fora, **503** com `ok` e `banco` em `false`. `versao` é o commit
publicado (`RENDER_GIT_COMMIT`, curto; "local" fora do Render): mostra se o deploy subiu. Ligue um monitor grátis que
confira a cada 5 minutos e mande e-mail quando cair (ação do Marcelo; escolha um dos dois):
- **UptimeRobot** (uptimerobot.com, plano grátis): *New monitor* › tipo *HTTP(s)*, URL
  `https://api.toqqi.com/api/v1/saude`, intervalo de 5 minutos e tempo limite de 30 s; em *Alert contacts*, o
  seu e-mail. Para o site, outro monitor do tipo *Keyword* em `https://toqqi.com/`
  com a palavra `Toqqi`, alertando quando ela **não** aparecer (assim uma página de erro do Render também conta como
  fora do ar).
- **Better Stack Uptime** (betterstack.com, plano grátis): *Monitors* › *Create monitor* › "Alert us when the URL
  becomes unavailable", a mesma URL da API, verificação a cada 3 minutos; outro para o site com "URL doesn't contain
  keyword" e `Toqqi`. O e-mail vai em *On-call* (ou no próprio monitor).

Observações:
- A API no plano grátis do Render dorme depois de 15 minutos sem uso; com o monitor a cada 3 ou 5 minutos ela fica
  acordada (as 750 horas grátis por mês dão para uma instância o mês todo). Se ela dormir, a primeira resposta leva uns
  30 s: por isso o tempo limite de 30 s.
- O *health check* do Render continua em `/api/v1/auth/regras-senha`, que não depende do banco: com o banco fora, o
  Render não reinicia a API à toa (quem avisa é o monitor).
- Os erros da própria aplicação (API, site e tarefas) ficam em Plataforma › Erros, e os superadmins recebem um e-mail por
  dia, a partir das 8h, quando há erro aberto nas últimas 24 h. O monitor externo cobre o que eles não alcançam: a API
  ou o site inteiros fora do ar.
- `GET /api/v1/saude` aceita até 60 pedidos por minuto de cada IP.

## Backup
Todo dia às 03:23 (Brasília), a rotina do GitHub `.github/workflows/backup.yml` copia o banco de produção, criptografa e guarda no
Cloudflare R2 por 30 dias (sempre ficam pelo menos 7 cópias). Em cada execução a cópia é baixada, decifrada e restaurada num banco
de teste, e a rotina só fica verde se tabelas, migrações e número de linhas baterem. O log é público, então nada do banco aparece
nele. Precisa de 6 segredos no GitHub (`BACKUP_DATABASE_URL`, `BACKUP_PASSPHRASE`, `R2_ACCOUNT_ID`, `R2_BUCKET`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`); sem eles, a rotina avisa que ainda não está configurada e termina sem erro. A senha da
criptografia também vai para o gerenciador de senhas: sem ela, as cópias não abrem. Passo a passo, restauração numa emergência e
ensaio de restauração em `docs/backup.md`.
