# toqqi-web

Frontend do **Toqqi** (toqqi.com).

- **Etapa 1:** acesso, equipe, sessões, segurança da conta, auditoria e área da plataforma.
- **Etapa 2:** contatos, empresas, responsáveis e cadastros auxiliares; importação de planilha; formulários
  (editor com pré-visualização, aparência, compartilhamento, resultados); páginas públicas de resposta; widget e QR Code.

Vite + Vue 3 (`<script setup lang="ts">`) + TypeScript estrito + Vue Router + Pinia + Tailwind CSS v4. Ícones: `lucide-vue-next`.
Contrato da API: [`../docs/api-etapa-1.md`](../docs/api-etapa-1.md) e [`../docs/api-etapa-2.md`](../docs/api-etapa-2.md).

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
| `dist/responder.html` | a pesquisa pública (`/r/:token` e `/f/:codigo`) | só Vue, o cliente fetch e o componente da pesquisa (~45 KB gzip de JS) |

A página pública é separada de propósito: abre rápido no 4G e não baixa nada da área logada.
Em `npm run dev` e `npm run preview` o próprio Vite já faz o redirecionamento. **Em produção, configure no servidor:**

1. `/r/*` e `/f/*` → servir `responder.html` (sem mudar a URL);
2. arquivos existentes (`/assets/*`, `/widget.js`, `/favicon.svg`) → servir o arquivo;
3. qualquer outra rota → `index.html` (SPA com histórico HTML5).

Exemplo com nginx:

```nginx
location ~ ^/(r|f)/ { try_files $uri /responder.html; }
location / { try_files $uri $uri/ /index.html; }
location = /widget.js { add_header Cache-Control "public, max-age=3600"; }
```

Exemplo Netlify (`public/_redirects`) ou equivalente em outro host:

```
/r/*  /responder.html  200
/f/*  /responder.html  200
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
                  arquivos com token), endpoints (index.ts, etapa2.ts, publico.ts) e tipos
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
                  contatos, importacao, formularios (editor/ com as abas e a pré-visualização)
  utils/          datas (dd/mm/aaaa, America/Sao_Paulo), senha, rótulos, validação
  styles/main.css Tailwind v4 + tokens (@theme) + modo escuro (classe .dark)
public/widget.js  widget para sites de clientes (JS puro, sem build)
responder.html    HTML da página pública
tests/            testes unitários (lógica/condições, variáveis, validação, importação, links, widget, componente)
```

## Comportamentos importantes

- **Sessão:** com "Lembrar de mim" o token fica no `localStorage`; sem, no `sessionStorage` (some ao fechar o navegador).
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
- Envios, Respostas, Planos de ação e Relatórios ainda mostram "Em construção".
