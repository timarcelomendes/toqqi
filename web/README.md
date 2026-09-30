# toqqi-web

Frontend do **Toqqi** (toqqi.com), etapa 1: acesso, equipe, sessões, segurança da conta, auditoria e área da plataforma.

Vite + Vue 3 (`<script setup lang="ts">`) + TypeScript estrito + Vue Router + Pinia + Tailwind CSS v4. Ícones: `lucide-vue-next`.
Contrato da API: [`../docs/api-etapa-1.md`](../docs/api-etapa-1.md).

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

O app é uma SPA com histórico HTML5: no servidor, redirecione rotas desconhecidas para `index.html`.

## Estrutura

```
src/
  api/            cliente fetch tipado (token, erros {erro:{codigo,mensagem,campos}}), endpoints e tipos
  stores/         sessao.ts (token, usuário, conta, permissões, pode())
  router/         rotas + guards (visitante / logado / meta.permissao / meta.superadmin)
  layouts/        AcessoLayout (páginas públicas) e AppLayout (menu lateral, barra superior)
  components/ui/  componentes próprios: Botao, Campo, CampoSenha, Selecao, CaixaSelecao, Modal,
                  DialogoConfirmacao, Avisos (toasts), Tabela, Etiqueta, EstadoVazio, Carregando,
                  Alerta, Abas, CampoChips, MenuSuspenso
  components/app/ marca, botão de tema, cabeçalho de página, item de menu
  composables/    avisos, confirmação, tema, foco preso (modais), formulário, regras de senha
  modulos/<área>/ telas: acesso, inicio, conta, equipe, configuracoes, auditoria, plataforma, geral
  utils/          datas (dd/mm/aaaa, America/Sao_Paulo), senha, rótulos, validação
  styles/main.css Tailwind v4 + tokens (@theme) + modo escuro (classe .dark)
tests/            testes unitários
```

## Comportamentos importantes

- **Sessão:** com "Lembrar de mim" o token fica no `localStorage`; sem, no `sessionStorage` (some ao fechar o navegador).
  Ao abrir o app, `GET /eu` atualiza usuário, conta e permissões.
- **401 `sessao_invalida`:** apaga a sessão, volta para `/entrar` e mostra a mensagem da API.
- **403 `sem_permissao`:** mostra um aviso e continua logado.
- **409/422:** mostra `mensagem` e, se houver, cada `campos.<campo>` ao lado do campo.
- **429:** "Muitas tentativas. Aguarde um minuto."
- **Permissões:** itens do menu e rotas são filtrados por `pode(permissao)`; sem permissão, a rota volta para `/inicio` com aviso.
- Contatos, Envios, Formulários, Respostas, Planos de ação e Relatórios ainda mostram "Em construção".
