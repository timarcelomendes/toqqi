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
| `dist/index.html` | o app (área logada e telas de acesso) | Vue, router, Pinia, ícones, telas |
| `dist/responder.html` | a pesquisa pública (`/r/:token` e `/f/:codigo`) e a página para sair da lista (`/sair/:token`) | só Vue, o cliente fetch e o componente da pesquisa (~45 KB gzip de JS) |

A página pública é separada de propósito: abre rápido no 4G e não baixa nada da área logada.
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
                  arquivos com token), endpoints (index.ts, etapa2.ts, etapa3.ts…, etapa4a.ts, publico.ts) e tipos
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
                  Alerta, Abas, CampoChips, MenuSuspenso
  components/app/ marca, botão de tema, cabeçalho de página, item de menu
  composables/    avisos, confirmação, tema, foco preso (modais), formulário, regras de senha
  modulos/<área>/ telas: acesso, inicio, conta, equipe, configuracoes, auditoria, plataforma, geral,
                  contatos, importacao, formularios (editor/ com as abas e a pré-visualização), envios,
                  integracoes, painel, respostas, acoes (cada uma com a sua logica.ts, testada à parte)
  utils/          datas (dd/mm/aaaa, America/Sao_Paulo), períodos (7/30/90 dias, 12 meses, tudo, datas), senha,
                  rótulos, validação
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
- **402 `limite_do_plano`** (contatos e importação): aviso amigável com link para `/assinatura` (ainda "Em construção").
- **Editor de formulário:** alterações ficam num rascunho; barra "não salvo", Ctrl/⌘+S, aviso ao sair da página ou fechar a aba.
  Erros 422 com `perguntas.<i>.<campo>` abrem a pergunta certa e aparecem no campo. "Recebendo respostas" e
  "link público" salvam na hora (não entram no rascunho).
- **Pesquisa pública:** no modo "uma por vez", tocar numa nota avança sozinho (com teclado, as setas só trocam a
  opção; Enter avança; no NPS as teclas 0–9 marcam a nota e "1" seguido de "0" marca 10).
- Relatórios e Assinatura ainda mostram "Em construção".

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
