# Design system da Toqqi

Este diretório é a referência da identidade visual da Toqqi: marca, cores, tipografia e componentes. O **código** do design system continua no app web. Aqui ficam as regras e os arquivos oficiais da marca.

| O quê | Onde fica |
|---|---|
| Regras e referência (este arquivo) | `design-system/README.md` |
| Arquivos oficiais da marca (SVG e PNG) | `design-system/marca/` |
| Tokens (cores, fonte, raio, sombra, modo escuro) | `web/src/styles/main.css` |
| Componentes básicos reutilizáveis | `web/src/components/ui/` |
| Peças específicas do produto (marca, menu, cabeçalho) | `web/src/components/app/` |

Se um valor mudar no código, atualize este documento no mesmo commit.

---

## 1. Marca

### Conceito
A Toqqi mede a satisfação de clientes (NPS e CSAT). Na logo, os dois "q" funcionam como **olhos** e um **sorriso** fica logo abaixo deles: o nome sorri, que é o resultado que o produto busca.

### Arquivos

| Arquivo | Uso |
|---|---|
| `marca/toqqi-logo.svg` | Logo principal, para fundos claros |
| `marca/toqqi-logo-escuro.svg` | Logo para fundos escuros |
| `marca/toqqi-logo-mono-preto.svg` | Uma cor só, para impressão em P&B, carimbos e documentos |
| `marca/toqqi-logo-mono-branco.svg` | Uma cor só, sobre fotos ou fundos coloridos |
| `marca/toqqi-icone.svg` | Ícone principal: app, favicon, avatar em redes sociais |
| `marca/toqqi-icone-escuro.svg` | Ícone sobre fundo escuro |
| `marca/toqqi-simbolo.svg` | Só o símbolo (qq + sorriso) em coral, sem fundo |
| `marca/png/` | Versões em PNG (ícone 512 e 180 px, logo 1200 px) para quem não aceita SVG |

As letras da logo estão convertidas em contornos, então não dependem da fonte instalada. No app, a logo é desenhada pelo componente `Marca.vue` e muda de cor sozinha no modo escuro.

### Regras de uso
- **Área de respiro**: deixe livre em volta da logo, no mínimo, a altura do "o".
- **Tamanho mínimo**: logo com 96 px de largura na tela (25 mm impressa). Abaixo disso, use o ícone.
- **Ícone**: funciona a partir de 16 px (favicon).
- **Favicon do site**: `web/public/favicon.svg` (cópia do ícone), `favicon.ico` (16 e 32 px) e `apple-touch-icon.png` (180 px), ligados em `web/index.html` e `web/responder.html` com `?v=2`. Ao trocar o ícone, atualize os três e suba o `v`, senão os navegadores continuam mostrando o antigo guardado no cache.
- **Fundos**: logo principal em fundos claros (branco, `#F8FAFC`) e versão escura sobre `#0F172A` ou mais escuro. Sobre fotos, use a mono branca com contraste suficiente.

### O que não fazer
- **Não curvar as hastes dos "q" até o sorriso.** Com a perninha curva, os "qq" passam a ser lidos como "gg". As hastes são retas e o sorriso fica solto, sem encostar nelas.
- Não encostar o sorriso nos "q" nem mudar o formato da curva.
- Não trocar o coral por outra cor nem pintar o "to" e o "i" de coral.
- Não esticar, inclinar, contornar ou aplicar sombra.
- Não reescrever "toqqi" com outra fonte. Use sempre os arquivos ou o componente.
- O nome é sempre em minúsculas na logo: **toqqi**. Em texto corrido, escreva "Toqqi".

---

## 2. Cores

### Paleta da marca (coral)

| Token | Hex | Uso principal |
|---|---|---|
| `coral-50` | `#FFF4F1` | Fundos suaves de destaque |
| `coral-100` | `#FFE5DD` | |
| `coral-200` | `#FFC9B8` | Seleção de texto |
| `coral-300` | `#FFA68D` | |
| `coral-400` | `#FF7C5C` | Marca no modo escuro, anel de foco |
| `coral-500` | `#FF5A36` | **Cor da marca** (logo, ícone, destaques) |
| `coral-600` | `#D63A18` | Fundo de botão primário (contraste AA com branco) |
| `coral-700` | `#B02F13` | Hover do botão, links sobre branco |
| `coral-800` | `#8C2814` | |
| `coral-900` | `#6E2415` | |

O `#FF5A36` **não** tem contraste suficiente para texto pequeno sobre branco nem para texto branco em cima dele. Para botões use `marca-forte` e para links use `marca-texto`.

### Tokens semânticos (mudam no modo escuro)

Use sempre estes nomes no código (`bg-superficie`, `text-texto-suave`…), nunca o hex direto.

| Token | Claro | Escuro |
|---|---|---|
| `fundo` | `#F8FAFC` | `#0B1120` |
| `superficie` | `#FFFFFF` | `#111827` |
| `superficie-2` | `#F1F5F9` | `#1E293B` |
| `borda` | `#E2E8F0` | `#1F2A3C` |
| `borda-forte` | `#CBD5E1` | `#334155` |
| `texto` | `#0F172A` | `#F1F5F9` |
| `texto-suave` | `#475569` | `#CBD5E1` |
| `texto-fraco` | `#64748B` | `#94A3B8` |
| `marca` | `#FF5A36` | `#FF7C5C` |
| `marca-forte` | `#D63A18` | `#D63A18` |
| `marca-hover` | `#B02F13` | `#E84A26` |
| `marca-texto` | `#B02F13` | `#FFA68D` |
| `marca-suave` | `#FFF4F1` | `#2A1712` |
| `foco` | `#FF7C5C` | `#FFA68D` |
| `sucesso` / `sucesso-suave` | `#047857` / `#ECFDF5` | `#6EE7B7` / `#06281F` |
| `atencao` / `atencao-suave` | `#B45309` / `#FFFBEB` | `#FCD34D` / `#2B1E05` |
| `erro` / `erro-suave` | `#B91C1C` / `#FEF2F2` | `#FCA5A5` / `#2D0F0F` |
| `info` / `info-suave` | `#1D4ED8` / `#EFF6FF` | `#93C5FD` / `#0C1D3D` |

O modo escuro é ligado pela classe `.dark` no `<html>`.

### Cores de gráfico

Só para as marcas dos gráficos (barras, linhas, pontos), nunca para texto: valores e nomes ficam nas cores de texto, ao lado de uma marca colorida.

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `grafico-serie` | `#2A78D6` | `#3987E5` | Série única (evolução do NPS, barras de um valor) |
| `grafico-promotor` | `#059669` | `#059669` | Promotores e positivo |
| `grafico-neutro` | `#F59E0B` | `#F59E0B` | Neutros |
| `grafico-detrator` | `#DC2626` | `#EF4444` | Detratores e negativo |
| `grafico-tema-1` | `#2A78D6` | `#3987E5` | Tema Prazo e entrega |
| `grafico-tema-2` | `#EB6834` | `#D95926` | Tema Produto e avarias |
| `grafico-tema-3` | `#1BAF7A` | `#199E70` | Tema Atendimento |
| `grafico-tema-4` | `#EDA100` | `#C98500` | Tema Preço e condições |
| `grafico-tema-5` | `#E87BA4` | `#D55181` | Tema Comunicação |
| `grafico-tema-6` | `#008300` | `#008300` | Tema Sistema e pedidos |
| `grafico-cinza` | `#94A3B8` | `#8B95A5` | Neutro do sentimento (nem elogio nem reclamação) |

- **A cor segue o tema (ou o grupo da nota), nunca a posição**: filtrar ou reordenar não troca a cor de ninguém.
- **Sentimento** (análise da IA), igual nos selos e nas barras: positivo verde (`grafico-promotor`), neutro cinza
  (`grafico-cinza`), misto âmbar (`grafico-neutro`) e negativo vermelho (`grafico-detrator`), sempre com o nome escrito.
  O cinza é de propósito (o meio da escala) e fica separado do verde e do âmbar vizinhos no validador.
- As seis cores dos temas foram conferidas com o validador de paleta nos dois modos (separação para daltonismo entre vizinhas e brilho). No claro, as dos temas 3, 4 e 5 ficam abaixo de 3:1 com a superfície: todo gráfico que as usa tem legenda escrita e a mesma informação em tabela.

---

## 3. Tipografia

- **Fonte**: Plus Jakarta Sans, para tudo (interface e marca). Se ela não carregar, entra a fonte do sistema.
- **Pesos**: 400 no corpo, 600 em botões, rótulos e links, 700 em títulos de página e 800 só na marca.
- **Título de página**: classe `.titulo-pagina` (24 px, 28 px a partir de telas `sm`, negrito, espaçamento justo).
- Texto de interface em 14 px (`text-sm`) e texto de leitura em 16 px.

---

## 4. Forma, profundidade e movimento

| Item | Valor |
|---|---|
| Raio de cartão | `rounded-cartao` = 1rem (16 px) |
| Raio de botão e campo | `rounded-xl` (12 px) |
| Sombra de cartão | `shadow-cartao` (bem leve, em duas camadas) |
| Cartão pronto | classe `.cartao` (superfície, borda, raio e sombra) |
| Animações | `animate-surgir` (160 ms) e `animate-deslizar` (200 ms) |

Quem pede movimento reduzido no sistema operacional tem todas as animações praticamente desligadas.

---

## 5. Acessibilidade

- **Foco visível**: contorno de 2 px na cor `foco` em todo elemento focável. Não remova.
- **Contraste**: texto mínimo de 4,5:1. Por isso existem `marca-forte` (botões) e `marca-texto` (links) separados de `marca`.
- **Botão só com ícone**: passe `somenteIcone="texto para leitor de tela"` no `Botao`.
- Use sempre elementos nativos (`<button>`, `<a>`, `<input>` com `<label>`). Os componentes de `ui/` já fazem isso.

---

## 6. Componentes (`web/src/components/ui/`)

| Componente | Quando usar |
|---|---|
| `Botao` | Qualquer ação. Variantes: `primario` (uma por tela), `secundario`, `fantasma`, `perigo`, `perigo-suave`. Tamanhos: `sm`, `md`, `lg`. Com `para`, vira link do app; com `href`, link para outro site que abre em nova aba (o leitor de tela ouve "abre em nova aba"). Tem estado `carregando`. |
| `BotaoCopiar` | Copiar um texto (link de pesquisa, token) com aviso de "Copiado!". |
| `Campo` | Campo de texto com rótulo, ajuda e erro. Com `mascara` (CPF/CNPJ, telefone, CEP), mostra sempre o valor formatado, inclusive o que foi colado; não use `maxlength` nesses campos (cortaria o colado antes da máscara). |
| `CampoSenha` | Senha com botão de mostrar/ocultar. Use com `RegrasSenha`. |
| `RegrasSenha` | Lista as regras de senha e marca as já atendidas. |
| `AreaTexto` | Texto longo (comentários, descrições). |
| `CampoChips` | Lista de valores digitados (e-mails, etiquetas). |
| `Selecao` | Escolher um valor numa lista. |
| `CaixaSelecao` | Marcar/desmarcar uma opção (aceite, filtros). |
| `Interruptor` | Liga/desliga com efeito imediato (configurações). |
| `BotoesSegmentados` | Escolher uma opção entre poucas, todas à vista, com cara de botões lado a lado (ex.: Motorista / Rota / Filial). São rádios nativos: o Tab entra na opção escolhida e as setas trocam a opção. |
| `Abas` | Alternar entre seções da mesma tela. Com muitas abas, a lista rola de lado (celular) e a borda esmaece onde há mais abas. |
| `MenuSuspenso` | Ações secundárias agrupadas (menu "⋯"). |
| `Modal` | Tarefa curta que bloqueia a tela. Tamanhos `sm`, `md`, `lg`. |
| `DialogoConfirmacao` | Confirmar ações, sobretudo as destrutivas. |
| `Alerta` | Mensagem fixa na página. Tons: `info`, `sucesso`, `atencao`, `erro`. |
| `Avisos` | Avisos temporários (toasts) depois de uma ação. |
| `Etiqueta` | Status curto (ativa, pausada, rascunho), com ponto opcional. |
| `Tabela` | Listas de registros. Com `densa`, células mais justas e títulos que quebram linha (tabelas com muitas colunas, como as dos relatórios). |
| `Paginacao` | Navegar entre páginas de uma lista. Trocar de página leva a tela ao começo da lista (o bloco onde a paginação está), não ao topo da página; dentro de uma caixa com rolagem própria (corpo de uma janela modal), a caixa volta ao começo. |
| `Medidor` | Quanto de um limite já foi usado (X de Y), como as análises de IA do mês. `role="meter"`; fica âmbar perto do limite e vermelho no limite. Os números ficam escritos ao lado. `fino` deixa a barra mais baixa (cabeçalho do assistente). |
| `TextoEmail` | Um e-mail que pode quebrar linha em tabelas e cartões estreitos: quebra depois do "@" e dos pontos, e só no meio da palavra como último recurso. |
| `Carregando` | Esqueleto enquanto os dados chegam. |
| `EstadoVazio` | Lista sem itens: título, descrição, ícone e ação. |

**Regra**: um componente genérico, que poderia existir em qualquer produto, vai para `ui/`. Um componente que conhece regras da Toqqi vai para `app/` ou para o módulo que o usa.

Ícones: biblioteca **Lucide** (`lucide-vue-next`), em traço. Não misture com outras bibliotecas nem com emoji.
