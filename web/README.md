# toqqi-web

Frontend do **Toqqi** (toqqi.com).

- **Etapa 1:** acesso, equipe, sessões, segurança da conta, auditoria e área da plataforma.
- **Etapa 2:** contatos, empresas, responsáveis e cadastros auxiliares; importação de planilha; formulários
  (editor com pré-visualização, aparência, compartilhamento, resultados); páginas públicas de resposta; widget e QR Code.
- **Etapa 3:** envios por e-mail, lembretes, robô de envio e descadastro (3a); integrações e WhatsApp automático (3b).
- **Etapa 4a:** painel no Início, Respostas (análise, arquivo, registro à mão, exportação), Planos de ação (quadro),
  importação de respostas antigas e configurações dos planos de ação. Detalhes em [Etapa 4a](#etapa-4a).

Vite + Vue 3 (`<script setup lang="ts">`) + TypeScript estrito + Vue Router + Pinia + Tailwind CSS v4. Ícones: `lucide-vue-next`.
Contrato da API: [`../docs/api-etapa-1.md`](../docs/api-etapa-1.md), [`../docs/api-etapa-2.md`](../docs/api-etapa-2.md),
[`../docs/api-etapa-3.md`](../docs/api-etapa-3.md), [`../docs/api-etapa-3b.md`](../docs/api-etapa-3b.md) e
[`../docs/api-etapa-4a.md`](../docs/api-etapa-4a.md).

## Configuração

Copie `.env.example` para `.env` e ajuste se precisar:

| Variável | Padrão | Para quê |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Endereço base da API (sem barra no final) |

## Scripts

```bash
npm install
npm run dev        # servidor de desenvolvimento
npm run build      # vue-tsc --noEmit + vite build (saída em dist/)
npm run typecheck  # só a checagem de tipos
npm run preview    # serve o dist/ localmente
npm test           # testes unitários (Vitest + @vue/test-utils, jsdom)
```

## Duas entradas (multi-page) e regras do servidor

O build gera **duas páginas**:

| Arquivo | O que é | Carrega |
|---|---|---|
| `dist/index.html` | na raiz (`/`), a **página do site**; em qualquer outro endereço, o app (área logada e telas de acesso) | na raiz, só `site.ts` e `site.css` (sem Vue); nos outros, Vue, router, Pinia, ícones, telas |
| `dist/responder.html` | a pesquisa pública (`/r/:token` e `/f/:codigo`) e a página para sair da lista (`/sair/:token`) | só Vue, o cliente fetch e o componente da pesquisa (~45 KB gzip de JS) |

A página pública é separada de propósito: abre rápido no 4G e não baixa nada da área logada.

**Página do site.** O HTML da página de apresentação do Toqqi está pronto dentro de `index.html` (`<div id="site">`),
para abrir rápido, aparecer para buscadores e funcionar sem JavaScript. A entrada `src/entrada.ts` olha o endereço: na
raiz carrega `src/site/site.ts` (animações, tabela de comparação dos planos, "Abrir o Toqqi" para quem já entrou); fora
dela, apaga o site e carrega o app (`src/main.ts`). Um script no `<head>` esconde o site antes de desenhar quando o
endereço não é a raiz, então o servidor não muda: tudo que não for arquivo continua indo para `index.html`. O site é só
claro, usa a fonte servida pelo próprio site e não faz requisição a terceiros. Com "reduzir movimento" ligado no
sistema, as animações param e a conversa de exemplo aparece completa. Os números da página são de exemplo (os mesmos
dos dados fictícios); preços e limites dos planos precisam acompanhar `api/toqqi/core/planos.py`,
`api/toqqi/modulos/whatsapp/franquia.py`, `api/toqqi/modulos/ia/regras.py` e a cota da etapa 5b (o teste
`tests/site.test.ts` confere os valores escritos na página).
**Guias do site.** Três páginas de conteúdo para a busca e para os anúncios: `/reduzir-churn`,
`/clientes-insatisfeitos` e `/customer-success`. Cada uma é um HTML pronto na raiz de `web/` (`reduzir-churn.html` etc.),
com a entrada leve `src/site/guia.ts` (fonte, `site.css` + `guia.css`, origem da visita e "Abrir o Toqqi"), sem Vue, sem
chamar a API e sem nada de terceiros. A lista fica em `src/site/guias.ts` e alimenta as entradas do build, o
redirecionamento do Vite, o `robots.txt` e o `sitemap.xml`; no Render, as regras do `render.yaml` mandam cada endereço ao
seu HTML **antes** da regra geral do app. Os botões levam a `/cadastro?utm_source=toqqi&utm_medium=guia&utm_campaign=<guia>`;
quem chegou por anúncio mantém a origem do anúncio (vale o primeiro link da visita). Números marcados "Exemplo" são os dos
dados fictícios; os guias não citam preços nem dias de teste (mudam em Plataforma › Parâmetros). Texto novo: só recurso que
existe no código. `tests/guias.test.ts` confere o HTML, as regras do Render e os links.
O endereço público vai no `<link rel="canonical">` (marca `<!-- canonical -->`, também no `index.html`) e no sitemap:
`SITE_URL` ou, sem ela, o `RENDER_EXTERNAL_URL` do build. Quando o domínio toqqi.com estiver no ar, ponha
`SITE_URL=https://toqqi.com` no toqqi-web e publique de novo. Para um guia novo: o HTML, uma linha em `GUIAS` e uma regra
no `render.yaml`.

Em `npm run dev` e `npm run preview` o próprio Vite já faz o redirecionamento. **Em produção, configure no servidor:**

1. `/r/*`, `/f/*` e `/sair/*` → servir `responder.html` (sem mudar a URL);
2. arquivos existentes (`/assets/*`, `/widget.js`, `/favicon.svg`) → servir o arquivo;
3. qualquer outra rota → `index.html` (SPA com histórico HTML5).

Exemplo com nginx:

```nginx
location ~ ^/(r|f|sair)/ { try_files $uri /responder.html; }
location / { try_files $uri $uri/ /index.html; }
location = /widget.js { add_header Cache-Control "public, max-age=3600"; }
```

Exemplo Netlify (`public/_redirects`) ou equivalente em outro host:

```
/r/*  /responder.html  200
/f/*  /responder.html  200
/sair/*  /responder.html  200
/*    /index.html      200
```

`/widget.js` não leva hash no nome (é colado no site dos clientes): sirva com cache curto (ex.: 1 hora).
A página pública pode ser aberta dentro de um iframe (widget, `embed=1`): não envie `X-Frame-Options: DENY`
nem `frame-ancestors` restritivo para `responder.html`.

## Widget no site do cliente

```html
<script src="https://SEU-APP/widget.js" data-toqqi="CODIGO_PUBLICO" async></script>
```

| Atributo | Padrão | Para quê |
|---|---|---|
| `data-toqqi` | — (obrigatório) | código público do formulário (8 caracteres) |
| `data-texto` | `Avalie-nos` | texto do botão flutuante |
| `data-cor` | `#d63a18` | cor do botão (`#rgb` ou `#rrggbb`) |
| `data-posicao` | `direita` | `direita` ou `esquerda` |

O botão abre `/f/{codigo}?canal=widget&embed=1` numa janela sobreposta (tela cheia no celular), que fecha com Esc,
clique fora ou no ×. Sem dependências, menos de 4 KB. `window.Toqqi.abrir()` / `fechar()` também funcionam.
A tela **Formulários → Compartilhar** monta o código pronto, o QR Code (PNG e SVG) e links com contexto.

## Parâmetros da página pública

| Parâmetro | Efeito |
|---|---|
| `?nota=N` | já marca a nota principal e começa na pergunta seguinte (use em e-mails com os botões 0–10) |
| `?canal=link\|qr\|widget` | de onde veio a resposta (só em `/f/`) |
| `?ref=` | referência (vira `{referencia}` e vai para a resposta) |
| `?pedido=` `?nota_fiscal=` `?rota=` `?motorista=` `?filial=` `?transportadora=` | contexto gravado junto da resposta (só em `/f/`) |
| `?embed=1` | modo compacto para iframe, sem margens |

## Estrutura

```
src/
  api/            cliente fetch tipado (token, erros {erro:{codigo,mensagem,campos}}, multipart, download de
                  arquivos com token), endpoints (index.ts, etapa2.ts, etapa3.ts…, etapa4a.ts, etapa4b.ts,
                  etapa5a.ts, empresa.ts, publico.ts) e tipos
  pesquisa/       núcleo da pesquisa SEM dependências do app: tipos, lógica (nota principal, grupos,
                  condições, páginas), variáveis ({nome}, {empresa}...), validação das respostas,
                  parâmetros/links com contexto, e os componentes Pesquisa.vue + CampoPergunta.vue
                  (os mesmos na página pública e na pré-visualização do editor)
  publico/        entrada leve da página pública (main.ts, PublicoApp.vue, publico.css)
  stores/         sessao.ts (token, usuário, conta, permissões, pode()); cadastros.ts (grupos, segmentos,
                  perfis, cargos e responsáveis em cache para filtros e formulários)
  router/         rotas + guards (visitante / logado / meta.permissao / meta.superadmin)
  layouts/        AcessoLayout (páginas públicas) e AppLayout (menu lateral, barra superior)
  components/ui/  componentes próprios: Botao, Campo, CampoSenha, Selecao, CaixaSelecao, Modal,
                  DialogoConfirmacao, Avisos (toasts), Tabela, Etiqueta, EstadoVazio, Carregando,
                  Alerta, Abas, CampoChips, MenuSuspenso, Medidor
  components/app/ marca, botão de tema, cabeçalho de página, item de menu, aviso da assinatura no topo
                  (AvisoCobranca) e a mensagem de limite de contatos (AlertaLimitePlano)
  composables/    avisos, confirmação, tema, foco preso (modais), formulário, regras de senha
  modulos/<área>/ telas: acesso, inicio, conta, equipe, configuracoes, auditoria, plataforma, geral,
                  contatos, importacao, formularios (editor/ com as abas e a pré-visualização), envios,
                  integracoes, painel, respostas, acoes, relatorios, assinatura (cada uma com a sua logica.ts,
                  testada à parte)
  utils/          datas (dd/mm/aaaa, America/Sao_Paulo), períodos (7/30/90 dias, 12 meses, tudo, datas), senha,
                  rótulos, validação, imagens (conferência do logo antes de enviar, logo do formulário ou da empresa)
  styles/main.css Tailwind v4 + tokens (@theme) + modo escuro (classe .dark)
public/widget.js  widget para sites de clientes (JS puro, sem build)
responder.html    HTML da página pública
tests/            testes unitários (lógica/condições, variáveis, validação, importação, links, widget, componente)
```

## Comportamentos importantes

- **Sessão:** com "Lembrar de mim" o token fica no `localStorage`; sem, no `sessionStorage` (some ao fechar o navegador).
- **Menu lateral recolhível** (computador): "Recolher menu", no pé da barra, deixa só os ícones (72 px); o nome aparece numa
  dica ao passar o mouse ou chegar pelo teclado e continua para leitores de tela. A escolha fica no `localStorage`
  (`toqqi.menu-recolhido`, com try/catch). A gaveta do celular fica sempre aberta. Estado em `composables/menuLateral.ts`.
  Ao abrir o app, `GET /eu` atualiza usuário, conta e permissões.
- **401 `sessao_invalida`:** apaga a sessão, volta para `/entrar` e mostra a mensagem da API.
- **403 `sem_permissao`:** mostra um aviso e continua logado.
- **409/422:** mostra `mensagem` e, se houver, cada `campos.<campo>` ao lado do campo.
- **429:** "Muitas tentativas. Aguarde um minuto."
- **Permissões:** itens do menu e rotas são filtrados por `pode(permissao)`; sem permissão, a rota volta para `/inicio` com aviso.
- **402 `limite_do_plano`** (criar, reativar e importar contatos): aviso amigável; quem tem `assinatura.gerenciar` vê
  "Ver planos" (leva para `/assinatura`), os outros leem que precisam pedir ao administrador da conta.
- **Editor de formulário:** alterações ficam num rascunho; barra "não salvo", Ctrl/⌘+S, aviso ao sair da página ou fechar a aba.
  Erros 422 com `perguntas.<i>.<campo>` abrem a pergunta certa e aparecem no campo. "Recebendo respostas" e
  "link público" salvam na hora (não entram no rascunho).
- **Pesquisa pública:** no modo "uma por vez", tocar numa nota avança sozinho (com teclado, as setas só trocam a
  opção; Enter avança; no NPS as teclas 0–9 marcam a nota e "1" seguido de "0" marca 10).

## Etapa 4a

Contrato: [`../docs/api-etapa-4a.md`](../docs/api-etapa-4a.md). Endpoints em `src/api/etapa4a.ts` (`respostasApi`,
`acoesApi`, `painelApi`); a importação de respostas usa `importacaoApi` (`src/api/etapa2.ts`) com o campo `tipo`.

### Início = Painel (`painel.ver`)

Quem tem `painel.ver` vê o painel no Início (`src/modulos/painel/`); os outros continuam com as boas-vindas.

- **Filtros** numa linha só, valendo para todos os blocos: período (7, 30 ou 90 dias, 12 meses, todo o período ou
  datas escolhidas; padrão 90 dias), grupo de empresas e "Só empresas ativas" (ligado). As datas vão para a API já em
  dias de São Paulo (`de`/`ate`). Trocar um filtro mantém o painel na tela (mais apagado) até chegar o novo.
- **"Escolher as datas"** pede as duas datas, válidas e a inicial antes da final (vale também em Respostas e Planos de
  ação). Enquanto não estiverem certas, o campo avisa, nada é buscado de novo e os títulos dos cartões e os atalhos
  continuam com o período dos números que estão na tela.
- **Atalhos para Respostas** levam os mesmos filtros, para os números baterem: as datas que o painel pediu (`de`/`ate`),
  `grupo_id` e `so_ativos`. Os blocos que só contam NPS (barra dos grupos, assuntos, empresas) levam também `tipo_nota=nps`.
- **Cartões:** NPS (número grande, faixa com nome e cor, barra dos três grupos com nome, % e quantidade, total e NPS
  dos decisores), variação sobre o período anterior, CSAT, taxa de resposta (com aviso de amostra pequena) e
  movimentação (resgatados / deixaram de ser promotores, com a lista "o que mudou").
- **Precisa de atenção:** ações abertas e vencidas, até 5 empresas com "Tratar" (abre `/planos-de-acao/{acao_id}`),
  receita em risco em R$ e "Tudo em dia" quando não há nada aberto.
- **Blocos:** assuntos mais citados (com nota média), comentários recentes (abrem a análise), evolução mensal do NPS,
  empresas com menor e maior NPS, 12 palavras mais citadas, "Como ler o painel".
- **Primeiros passos:** os 4 passos vêm da API; some sozinho quando todos estão feitos. "Ocultar" guarda a escolha em
  `localStorage` (`toqqi.painel.passos-ocultos.{contaId}`, sempre dentro de try/catch); "Mostrar primeiros passos"
  desfaz. Sem armazenamento (aba anônima bloqueada), esconde só até sair e avisa.
- **Exportar CSV** (`painel.exportar`): `GET /painel/exportar.csv` com os mesmos filtros.
- **Gráficos sem biblioteca:** SVG feito à mão com as cores do tema (`--color-grafico-*`). A evolução tem dica ao
  passar o mouse, navegação pelas setas do teclado (com leitura para leitor de tela) e "Ver em tabela". As cores dos
  grupos sempre vêm com o nome escrito ao lado. A API manda só os meses com dados: os meses sem respostas entre o
  primeiro e o último entram vazios, e a linha se interrompe ali (não liga meses distantes como se fossem vizinhos).

### Respostas (`/respostas`, `respostas.ver`)

Números do filtro no topo (NPS, CSAT, total e a barra dos grupos; tocar num grupo filtra por ele), tabela no
computador (≥ 1280 px) e cartões no celular. Os filtros ficam **no endereço**, então dá para compartilhar o link:

| Parâmetro | Valores |
|---|---|
| `busca` | texto (contato, empresa, comentário, referência), até 100 caracteres (o limite da API) |
| `periodo` | `7`, `30`, `90`, `365`, `personalizado` (sem ele: todo o período) |
| `de`, `ate` | `AAAA-MM-DD` (qualquer um dos dois já vale como período personalizado) |
| `data_por` | `entrada` = conta o período pela data em que a resposta chegou ao Toqqi |
| `categoria` | `detrator`, `neutro`, `promotor`, `insatisfeito`, `satisfeito` (só as do tipo escolhido) |
| `tipo_nota` | `nps` ou `csat` |
| `grupo_id`, `empresa_id`, `perfil_id`, `contato_id` | id |
| `tema` | chave do tema (`GET /respostas/temas`) |
| `arquivadas` | `true` (só arquivadas) ou `todas`; sem ele, só as ativas |
| `so_ativos` | `true` = só respostas de empresas ativas (as sem empresa continuam), como no painel; padrão desligado |
| `pagina` | número |
| `analisar` | id da resposta: abre o painel "Analisar" |

- **Analisar** (painel lateral): tudo o que o cliente respondeu, contexto do pedido, análise da equipe (nota,
  comentário, o que faltou, o que combinamos, temas; só manda o que mudou), ações ligadas (abrir ou criar).
- **Arquivar/Restaurar** (`respostas.editar`): arquivada sai de todos os números.
- **Excluir de vez** (só perfil admin): a confirmação busca o detalhe e diz quantas ações somem junto.
- **Registrar resposta** (`respostas.editar`): contato (busca), nota 0–10, canal, data (até hoje) e comentário. A data só
  vai para a API quando não é hoje: sem ela, a resposta fica com a hora do registro (com ela, o servidor guarda o dia
  ao meio-dia, e as telas mostram só o dia).
- Depois de salvar a análise, a lista é buscada de novo quando nota, comentário, temas ou arquivamento mudaram (a
  resposta pode entrar ou sair do filtro atual).
- **Exportar CSV** (`painel.exportar`) e **Importar respostas antigas** (`importacao.usar`).
- Na ficha do contato: "Ver respostas" (`/respostas?contato_id=`) e "Registrar resposta". O histórico mostra a origem
  ("Registrada à mão", "Importada"), o canal e as arquivadas; a aba Respostas do formulário também mostra a origem e
  usa a data da resposta (`data`, ou `criada_em` no servidor antigo).

### Planos de ação (`/planos-de-acao` e `/planos-de-acao/:id`, `acoes.ver`)

- Quadro **A fazer → Em andamento → Concluído**: arrastar e soltar no computador ou "Mover" no cartão (teclado e toque).
  No celular, uma coluna por vez (abas). O cartão muda de coluna na hora; se o servidor recusar, volta, a ação é
  buscada de novo (`GET /acoes/{id}`) e o cartão e o painel passam a mostrar o que vale (ex.: o responsável que foi
  removido em outra sessão). Salvar no painel recusado faz o mesmo, sem perder o que a pessoa mudou.
- Depois de mover pelo menu, o foco vai para o cartão na coluna nova (computador) ou fica na coluna atual, no cartão
  seguinte ou na aba de destino (celular); o leitor de tela ouve "Ação movida para …".
- Cartão: título, empresa, responsável, prioridade, selo de prazo ("Prazo vencido", "Vence hoje", "Vence amanhã",
  "Até dd/mm/aaaa") e a nota que deu origem. Abertas ordenadas por vencidas, prazo, prioridade e criação.
- **Concluir** pede responsável e "o que foi feito": se faltar, não grava, abre o painel da ação já em "Concluída",
  com o campo à vista e o aviso; um 422 do servidor mostra os `campos` que ele pediu.
- Painel lateral (o link `/planos-de-acao/:id` abre direto): editar tudo, ver a resposta de origem, excluir (`acoes.excluir`).
- Filtros no endereço (`busca`, `categoria`, `tipo_nota`, `responsavel_id` — `0` = sem responsável —, `empresa_id`,
  `grupo_id`, `periodo`/`de`/`ate` da criação, `so_vencidas=true`), "Nova ação" (`acoes.tratar`) e "Ver todas as
  concluídas" (lista paginada; o quadro mostra só as 15 mais recentes).

### Outras telas

- **Importar respostas antigas:** `/contatos/importar?tipo=respostas` (o primeiro passo também deixa escolher entre
  Contatos e Respostas antigas). Textos, planilha modelo (`GET /importacao/modelo?tipo=respostas`), colunas
  obrigatórias (e-mail, data, nota) e opções ("Atualizar as que já existem") mudam com o tipo.
- **Configurações › Planos de ação** (`/configuracoes/acoes`): prazo de detrator, neutro e promotor (1 a 90 dias) e
  "Criar ação também para promotores". Sem `configuracoes.gerenciar`, só leitura.
- Menu: Respostas e Planos de ação deixaram de ser "em breve". "Importar respostas antigas" marca Respostas no menu.
- **Sem `contatos.ver`** (matriz de permissões personalizada): nada de chamar listas que pedem esse acesso. Os campos de
  empresa e contato (`CampoEmpresa`, `CampoContato`) mostram o valor atual só para ler, com um aviso curto; o
  responsável fica travado; filtros de grupo e perfil só aparecem se vierem no endereço; "Registrar resposta" explica e
  só envia com o contato já escolhido.
- Links de dentro dos painéis (abrir a ação, a ficha do contato, "Ver a resposta completa") passam pela pergunta de
  "sair sem salvar" (`onBeforeRouteLeave` nos painéis).

### Componentes compartilhados que mudaram

- `useFocoPreso`: janelas umas sobre as outras (ex.: confirmação por cima do painel lateral) — o Esc e o Tab ficam
  com a de cima. Esc dentro de uma lista aberta (busca com sugestões, menu) fecha só a lista, não a janela. Ao fechar,
  o foco volta para quem abriu (se foi um item de menu, para o botão do menu). `travarRolagem`/`liberarRolagem`
  contam quantas janelas estão abertas.
- `Modal` ganhou `elevado` (a confirmação fica por cima de painéis); novo `PainelLateral` (painel que entra pela
  direita; tela cheia no celular) com confirmação antes de fechar sem salvar.
- `MenuSuspenso` com `fixo`: calcula a posição antes de aparecer e acompanha a rolagem (fecha se o botão sair da tela).
  Ao escolher um item, o foco volta ao botão do menu (a não ser que a ação já tenha levado o foco para outro lugar);
  Esc no botão também fecha o menu.
- `Tabela`: o contêiner com rolagem ficou `relative` (nada posicionado dentro das células escapa e cria rolagem na página).
- Tokens novos de gráfico em `styles/main.css` (`--color-grafico-serie`, `-promotor`, `-neutro`, `-detrator`), com
  valores próprios no modo escuro, e os canais "Telefone" e "Reunião" em `utils/rotulos.ts`.
- Telas antigas: em Contatos, no celular, o botão "Filtros" desce de linha em vez de vazar do cartão; na fila de Envios,
  as ações da linha ficam só com ícone (nome no leitor de tela e na dica) e o contato tem largura máxima, para a tabela
  caber no cartão em 1280 px.

## Dados da empresa e logo

Contrato: [`../docs/api-dados-empresa.md`](../docs/api-dados-empresa.md). Endpoints em `src/api/empresa.ts`
(`empresaApi`: `GET`/`PUT /conta/dados`, `PUT`/`DELETE /conta/logo`; `logoFormularioApi`: `POST /formularios/{id}/logo`).
O tipo se chama `DadosEmpresaConta` (no contrato, `DadosEmpresa`, nome que no front já é o corpo das empresas dos
contatos). `GET /eu` traz `conta.logo_url`, que a sessão guarda junto.

### Configurações › Empresa (`/configuracoes/empresa`, `configuracoes.gerenciar`)

Primeira seção de Configurações (o item "Configurações" do menu e `/configuracoes` abrem nela, para quem pode). Regras
puras em `src/modulos/configuracoes/empresa.ts` (testadas à parte), tela em `EmpresaView.vue`, logo em `LogoEmpresa.vue`.

- **Identificação** (nome, obrigatório, que é o `{empresa}` das pesquisas e dos e-mails; razão social; CNPJ com
  máscara, que também aceita CPF), **Contato** (telefone/WhatsApp com máscara, e-mail, site) e **Endereço**.
- **Máscaras:** a tela mostra formatado; para a API vão só os dígitos (documento, telefone, CEP), os vazios como `null`
  e sem espaços nas pontas. O telefone salvo com o 55 volta para o campo sem ele; começando com "+", fica como número
  de outro país (sem a máscara brasileira, que cortaria dígitos). Máscara ou espaço a mais não contam como alteração.
- **Conferência antes de enviar**, com as mesmas regras e mensagens do servidor: CPF/CNPJ pelos dígitos verificadores,
  telefone com DDD (sem o zero da operadora), e-mail, site (sem `https://` vale; só http/https; domínio com ponto; até
  200 caracteres), CEP com 8 números, UF da lista e limites de tamanho. O que o servidor disser (422 `campos`) também
  aparece no campo, e o foco vai para o primeiro campo com erro.
- **CEP → endereço (ViaCEP):** com os 8 números, busca `https://viacep.com.br/ws/{cep}/json/` e preenche só
  logradouro, bairro, cidade e UF que estiverem vazios ("Endereço preenchido pelo CEP. Confira e complete o número.").
  Tempo limite de 4 s; CEP que não existe, sem internet ou demora: nada acontece e a pessoa segue à mão. Mudar o CEP
  no meio da busca cancela a anterior.
- **Barra "Salvar alterações / Descartar"** e pergunta ao sair com alterações não salvas (trocar de página ou fechar a
  aba), como nas outras seções de Configurações.
- **Salvou:** nome e logo mudam na sessão na hora (`sessao.atualizarConta`), então o topo do app já mostra o nome novo.
- **Logo:** prévia em fundo claro e escuro, "Enviar logo"/"Trocar logo" (`PUT /conta/logo`, multipart `arquivo`) e
  "Remover" com confirmação (`DELETE /conta/logo`). Vale na hora, sem esperar o "Salvar alterações" (o que está sendo
  editado nos outros cartões continua lá). Antes de enviar, o arquivo é conferido pelos primeiros bytes (PNG ou JPG de
  verdade, não pela extensão) e pelo tamanho (até 300 KB), com a mesma mensagem da API (`src/utils/imagens.ts`).

### Editor de formulário › Aparência

- "Enviar imagem" manda o arquivo para `POST /formularios/{id}/logo` (só PNG/JPG até 300 KB, conferidos antes; SVG,
  WebP e GIF saíram) e põe a URL devolvida em `tema.logo_url`. Nunca guarda `data:`. A pesquisa só muda quando o
  formulário é salvo (o aviso diz isso). Com imagem enviada, o campo "Endereço da imagem" some (a URL é interna) e o
  botão vira "Trocar imagem"; "Tirar logo" volta ao campo de endereço (`https://`).
- Sem logo no formulário, vale o da empresa, como a API faz na página pública e nos e-mails (`logoParaCliente` em
  `src/utils/imagens.ts`): a aba mostra o logo da empresa com "Usando o logo da empresa." (e o link para trocá-lo, para
  quem tem `configuracoes.gerenciar`), e a pré-visualização (ao lado e no "Pré-visualizar" do celular) mostra a pesquisa
  com ele e o aviso "Usando o logo da empresa". A prévia dos modelos em "Novo formulário" segue a mesma regra.
- Imagem que não abre (endereço errado, ou trocada sem salvar e depois descartada) ganha um aviso.
- As cores prontas ganharam borda (a "Grafite" sumia no modo escuro) e o "Tirar logo" saiu de cima do fundo branco
  da prévia (no modo escuro, o vermelho claro do botão ficava sem contraste).

## Etapa 4b

Contrato: [`../docs/api-etapa-4b.md`](../docs/api-etapa-4b.md) (§8, telas). Endpoints em `src/api/etapa4b.ts`
(`relatoriosApi`: as 7 abas, os CSV e as empresas de uma carteira; `iaApi`: `GET`/`PUT /conta/ia` e
`POST /conta/ia/analisar-recentes`). Os filtros novos de Respostas e os picos do painel usam `respostasApi` e `painelApi`;
`euApi.atualizar` aceita `recebe_resumo_semanal` e `recebe_alertas`. Tipos no fim de `src/api/tipos.ts` (valores em reais
podem chegar como número ou texto: `ValorDecimal`).

### Relatórios (`/relatorios/:aba`, `relatorios.ver`)

Uma tela (`src/modulos/relatorios/RelatoriosView.vue`) com 7 abas. Regras puras em `logica.ts` (testadas à parte); a
carga de cada aba em `usarRelatorio.ts` (espera 200 ms, cancela o pedido anterior e deixa os números na tela, mais
apagados, até chegar o novo).

- **Endereço:** `/relatorios` abre `/relatorios/empresas`; aba que não existe volta para Empresas. Filtros comuns:
  `periodo` (`7`, `30`, `90`, `365`, `tudo`, `personalizado`; padrão 90 dias e, no histórico, todo o período) ou
  `de`/`ate`, `grupo_id` e `so_ativos=false` (padrão: só empresas ativas). Cada aba lê e escreve só os filtros dela:

  | Aba | Parâmetros |
  |---|---|
  | `empresas` | `segmento_id` e `responsavel_id` (`0` = sem), `faixa_valor`, `tempo_cliente`, `busca`, `respostas` (`com`/`sem`), `quadrante`, `ordem`, `pagina` |
  | `grupos` | `segmento_id`, `faixa_valor`, `tempo_cliente` |
  | `entregas` | `dimensao` (`motorista`, padrão, `rota`, `filial`, `transportadora`), `busca`, `ordem`, `pagina` |
  | `historico` | `empresa_id` |

  Trocar de aba leva o grupo e "só ativas"; o período só vai junto se a pessoa escolheu um. Filtro novo volta para a
  página 1. A troca de aba entra no histórico do navegador; mudar um filtro, não. O título da aba do navegador acompanha
  a aba ("Temas · Relatórios · Toqqi").
- **Exportar CSV** (`painel.exportar`): Empresas, Entregas e Responsáveis com os filtros da tela (sem a página);
  Operação exporta os contatos sem resposta ("Exportar contatos sem resposta (CSV)"); Histórico, com a empresa
  escolhida e o período.
- **Rolagem:** mudar filtro, ordem, busca ou quadrante não mexe na rolagem (a URL muda só na query); trocar de página
  leva a tela ao começo da lista; outra aba ou outra página vai para o topo; voltar e avançar devolvem a posição (mesmo
  com os dados chegando depois da navegação).
- **Empresas:** cartões (empresas com respostas, cobertura, receita em risco — número curto no cartão, valor exato na
  dica e para leitor de tela —, empresas por faixa de NPS); **matriz NPS × valor** em SVG (valor em escala logarítmica
  1-2-5, NPS de −100 a 100, linhas na mediana e no 0, nome dos quadrantes por cima dos pontos; dica no ponto mais perto
  do mouse, até 24 px; setas, Home e End no teclado, com leitura para leitor de tela). Clique ou toque abre o histórico
  da empresa **embaixo do ponteiro** (num espaço vazio, nada); Enter abre a escolhida pelas setas. Só o foco que vem do
  teclado escolhe a primeira empresa sozinho (`composables/focoGrafico.ts`, usado também nos outros gráficos; no toque,
  a dica fica na tela depois de levantar o dedo). A contagem por quadrante é a alternativa em texto e filtra a tabela
  (`aria-pressed`). Tabela a partir de 1280 px (`Tabela densa`), cartões abaixo. Sem responsável ou sem valor, a tabela
  e o cartão dizem isso ("Sem responsável", "sem valor").
- **Grupos de clientes:** barras detratores/neutros/promotores por segmento, grupo, tempo como cliente e valor ("Ver em
  tabela" em cada uma; na tabela, a primeira coluna tem o nome do recorte) e **O que resolver primeiro** (dispersão
  menções × nota média, com os nomes posicionados para não se cobrirem, e a lista em ordem, com o nome inteiro do tema
  e link para Respostas com `tema` e `tipo_nota=nps`).
- **Temas:** de onde vêm os temas ("X de Y comentários analisados pela IA"; os outros usam as palavras-chave — na fila,
  importados, curtos demais ou que não deu para analisar —, e o admin vê como pedir a análise dos últimos 90 dias; sem
  IA, "Temas por palavras-chave"), picos, sentimento dos comentários (só com análises), gráfico semanal (uma linha por
  tema, menções ou reclamações em `BotoesSegmentados`; a legenda destaca a linha; a dica lista os 6 temas da semana;
  "Ver em tabela") e os 6 temas (tabela a partir de 1280 px, cartões abaixo; as reclamações levam a
  `/respostas?tema=…&reclamacao=true`; a coluna de sentimento só aparece com IA).
- **Entregas:** escolha da dimensão (`BotoesSegmentados`), tabela com NPS, CSAT, reclamações, principais temas, "Amostra pequena" (menos de 5
  respostas) e "Ver respostas" (`/respostas?motorista=…` com o período, o grupo e "só ativas"). Sem dados, explica como
  mandar essas informações: o campo `contexto` da integração ou o link da pesquisa com `?motorista=…&rota=…` (a
  importação de respostas não traz o contexto, então a planilha não entra na explicação).
- **Responsáveis:** tabela das carteiras a partir de 1280 px (cartões abaixo disso; se faltar espaço, a tabela rola
  dentro do cartão, nunca a página). Abrir uma linha busca `GET /relatorios/responsaveis/{id}/empresas` (0 = sem
  responsável) e guarda o resultado com os filtros do pedido. Mudar período, grupo ou "só ativas" busca de novo as
  carteiras abertas (as fechadas, ao abrir); um pedido novo cancela o anterior e resposta atrasada é ignorada. O nome da
  empresa abre o histórico.
- **Operação:** taxa de resposta (contatos que receberam a pesquisa no período e, desses, os que responderam no
  período), convites por canal, ações (concluídas, tempo médio e % no prazo no período; abertas e vencidas de agora) e os
  contatos sem resposta (até 1.000 da API, de 50 em 50 na tela, atrasados em destaque; essa lista não depende do
  período).
- **Histórico de uma empresa:** busca da empresa na linha dos filtros (sem `contatos.ver`, a busca usa o próprio
  relatório de empresas); cabeçalho com os dados do cadastro, NPS, CSAT, cobertura e ações; evolução mensal (o gráfico
  do painel, com "Ver em tabela") e a linha do tempo por mês (nota, contato com cargo e perfil, canal, origem,
  comentário, temas, sentimento e resumo da IA, ação e "Abrir a resposta"). A API manda até 500 respostas; a tela avisa quando
  há mais. Empresa de outra conta (404): "Empresa não encontrada".
- **Cores:** grupos da nota com `grafico-promotor`/`-neutro`/`-detrator`, série única com `grafico-serie` e temas com
  `grafico-tema-1…6` (cor fixa por tema, nos dois modos; ver `design-system/README.md`). Sentimento igual em todas as
  telas (selos e barras): positivo verde, neutro cinza (`grafico-cinza`), misto âmbar e negativo vermelho. A cor nunca
  aparece sem o nome.

### IA nas Respostas

- `conta.ia_ativa` (sessão, vinda de `GET /eu` e do login) liga as partes de IA. Os filtros "Sentimento (IA)"
  (`sentimento`) e "Só reclamações" (`reclamacao=true`) aparecem com a IA ativa, quando a lista já tem respostas
  analisadas ou quando já vieram no endereço.
- Selo do sentimento do comentário na lista (positivo, neutro, misto ou negativo, sempre escrito). No Analisar, a caixa
  "Análise da IA" (com a IA ativa na conta ou quando a análise já está pronta): resumo, sentimento, temas com
  "elogio"/"reclamação" e a data, ou a situação ("Aguardando análise", "Não foi possível analisar", "Limite do mês
  atingido").
- Filtros de contexto vindos de Entregas (`motorista`, `rota`, `filial`, `transportadora`, até 120 caracteres) viram
  chips em "Mostrando", com X para tirar; "Limpar filtros" não mexe neles.

### Painel

- Faixa de picos acima dos cartões ("Pico de reclamações em Prazo e entrega: 7 nos últimos 7 dias; a média era 1,5 por
  semana." e "Ver respostas", que abre as reclamações do tema nos 7 dias, de empresas ativas). Não depende dos filtros
  da tela. A mesma faixa aparece em Relatórios › Temas.
- Assuntos mais citados: as reclamações e a variação das menções contra o período anterior (seta e "+9 em relação ao
  período anterior").

### Minha conta e Configurações

- **Minha conta › E-mails do Toqqi** (só com `painel.ver`): "Resumo semanal" e "Alerta de pico de reclamações", salvos
  na hora (`PATCH /eu`); se não salvar, voltam como estavam e avisam.
- **Configurações › IA** (`/configuracoes/ia`, `configuracoes.gerenciar`): situação na plataforma, "Analisar comentários
  com IA" (desligar com comentários na fila pede confirmação; depois de mudar, a sessão é buscada de novo para atualizar
  `ia_ativa`), uso do mês (`Medidor`, X de Y), fila, falhas e quanto ainda dá para analisar, "Analisar comentários dos
  últimos 90 dias" (com confirmação; o 409 mostra a mensagem do servidor; no celular, o botão ocupa a largura e quebra
  linha) e o que é enviado à IA.
- Menu: Relatórios deixou de ser "em breve". Contatos › Empresas: "Ver histórico" no menu de cada empresa
  (`relatorios.ver`).

### Componentes que mudaram

- `Tabela`: `densa` (células mais justas e títulos que quebram linha), para as tabelas largas caberem em 1280 px.
- `Paginacao`: trocar de página leva a tela ao começo da lista (o bloco onde a paginação está), não ao topo da página;
  numa caixa com rolagem própria (a janela "Ações concluídas"), é a caixa que volta ao começo. O `html` tem
  `scroll-padding-top` (o topo fixo do app não cobre o que é trazido à vista).
- Rolagem do roteador (`rolagemAoNavegar` em `src/router/index.ts`): voltar/avançar → posição salva; só a query mudou
  (filtros, página, "Analisar") → não rola; outra página → topo. Rotas com `meta.manterRolagem` (Planos de ação) também
  não rolam ao trocar só o parâmetro (abrir e fechar o painel de uma ação). Ao voltar, `quandoCouber` espera a página
  crescer até caber a posição salva (até 2 s; se a pessoa rolar ou tocar antes, desiste).
- `BotoesSegmentados` (novo, em `ui/`): rádios nativos com cara de botões lado a lado (setas trocam a opção).
- Gráficos (`GraficoEvolucao` do painel e os dos relatórios): clique e toque valem pelo ponto embaixo do ponteiro; só o
  foco do teclado escolhe um ponto sozinho (`composables/focoGrafico.ts`).
- `Abas`: quando as abas não cabem, a borda do lado que tem mais esmaece; a aba ativa fica sempre à vista (rola só a lista).
- `Medidor` (novo, em `ui/`): quanto de um limite já foi usado (`role="meter"`).
- `BarraGrupos`: `legenda="nenhuma"` e `fina` (linhas de tabela). `CampoEmpresa`: `fonte` opcional (outra origem para a
  busca). Tokens `--color-grafico-tema-1…6` e `--color-grafico-cinza`, documentados no design system.

## Etapa 5a

Contrato: [`../docs/api-etapa-5a.md`](../docs/api-etapa-5a.md) (§8, telas; §0, §3, §4 e §7, regras e formatos).
Endpoints em `src/api/etapa5a.ts` (`assinaturaApi`: planos, `GET /assinatura`, assinar, trocar de plano, dados de
cobrança e cancelar); a Plataforma continua em `plataformaApi`. Tipos no fim de `src/api/tipos.ts` (`EstadoAssinatura`,
`CobrancaConta`, `AvisoCobranca`…; valores em reais como número ou texto). Regras puras (datas, avisos, primeira fatura,
limite de contatos, formulário) em `src/modulos/assinatura/logica.ts`.

### Assinatura (`/assinatura`, `assinatura.gerenciar`)

- Entrada no menu da conta (canto de cima) e em Administração › Assinatura.
- **Sem assinatura:** a situação (teste com o último dia, teste encerrado, cancelada ainda no período pago ou não), os
  contatos ativos contra o limite do plano em uso (o do teste) e os 3 planos em cartões (preço, limite, "Envios,
  formulários e usuários ilimitados"). Os planos são rádios nativos (Tab entra, setas trocam); o que não comporta os
  contatos ativos de hoje fica bloqueado, com o motivo escrito. Escolhido um plano, aparece o formulário de cobrança
  preenchido com `dados_sugeridos` (razão social, CPF/CNPJ e telefone com as máscaras de Configurações › Empresa,
  e-mail de cobrança), com as mesmas mensagens da API, e o resumo da primeira fatura: no último dia do teste (se ele
  ainda vale), no dia seguinte ao fim do período pago ou amanhã ("Primeira fatura de R$ 349,00 com vencimento em
  15/10/2026, no fim do teste. Depois, todo dia 15."). Escolher com mouse ou toque leva a tela até o formulário; com o
  teclado, não (o Tab chega lá).
- **Com assinatura:** "Plano X" com o selo da situação (Em teste, Ativa, Atrasada, Aguardando pagamento), o valor, os
  contatos ativos, o próximo vencimento e a data da assinatura; a fatura em aberto com "Pagar" (abre a fatura do
  Asaas em nova aba: Pix, boleto ou cartão) e "Atualizar"; os dados de cobrança (editar numa janela: sem mudança,
  "Salvar" fica travado); "Trocar de plano" (janela com os 3 planos, o novo valor, a fatura pendente que muda junto e o
  limite; plano menor com contatos demais avisa e não deixa trocar); "Cancelar assinatura" (confirmação com até quando
  usa, ou a volta para o teste, "Sem multa"); o histórico (vencimento, valor, forma, situação, pago em e "Ver fatura";
  tabela a partir de 640 px, cartões no celular). O histórico continua depois de cancelar.
- **Cortesia:** só a situação ("não precisa assinar"). **`disponivel: false`:** "A cobrança online ainda não está
  disponível. Fale com a equipe Toqqi." e as ações que dependem do Asaas travadas.
- **Esperar o pagamento:** depois de assinar (ou de clicar em "Pagar"), busca `GET /assinatura` de 10 em 10 s por até
  2 min enquanto a fatura estiver em aberto (e de novo ao voltar para a aba, no máximo a cada 10 s). Quando a situação
  da conta muda, busca a sessão (`GET /eu`) de novo; quando a fatura aparece paga, avisa "Pagamento confirmado".
- **Erros:** 422 (campos e `cobranca_recusada`) no campo; `limite_do_plano` em âmbar; 503 `cobranca_indisponivel` com a
  mensagem da API; 409 `ja_assinada`/`cortesia` avisam e recarregam a tela.

### Aviso no topo das telas

- `AvisoCobranca` (no `AppLayout`, abaixo da barra de cima) lê `conta.cobranca.aviso` da sessão: teste acabando ("Seu
  teste grátis termina em 3 dias."), teste encerrado, atrasada ("A fatura venceu em 10/10. Os envios param em 18/10 se
  ela não for paga."), pausada, cancelada ("Você usa até 14/11.") e cancelada encerrada; tipo novo da API vira um aviso
  genérico. Quem tem `assinatura.gerenciar` vê "Escolher plano" ou "Pagar agora" (na própria tela de Assinatura, sem o
  botão); os outros, "Fale com o administrador da conta.". Os informativos (teste acabando e cancelada) podem ser
  fechados até a próxima sessão do navegador (`sessionStorage`, com try/catch); voltam quando o aviso muda. O selo de
  teste no cabeçalho continua.

### Plataforma

- Selos das situações novas (Teste encerrado, Atrasada, com "Vencida em"), a assinatura (plano e valor, ou "Sem
  assinatura" e o plano da conta) e as datas (teste até, pago até); usuários e "criada em" viram coluna só a partir de
  1536 px (antes, embaixo do nome). "+14 dias" travado com assinatura ativa ou cortesia (o motivo vai para o leitor de
  tela); com o teste já acabado, a confirmação diz que os dias contam a partir de hoje. "Cortesia" numa conta com
  assinatura avisa que a assinatura no Asaas será cancelada; "Excluir" também.

### Componentes que mudaram

- `Botao`: `href` (link para outro site, abre em nova aba e avisa o leitor de tela).
- `AlertaLimitePlano`: "Ver planos" só para `assinatura.gerenciar`.
- `situacaoConta` (rótulos): `teste_expirado` e `atrasada`. A rota `/assinatura` saiu do "Em construção".
