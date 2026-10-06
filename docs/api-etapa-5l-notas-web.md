# Etapa 5l — notas do site (decisões, desvios e ganchos)

Complementa `docs/api-etapa-5l.md` (o contrato continua valendo; aqui ficam o que o site decidiu onde o contrato deixou
aberto, os desvios e os ganchos `data-*` para o teste integrado). Tudo em `web/`, mais os cabeçalhos de CSP no
`render.yaml`.

## 1. Onde está cada parte

| Contrato | Arquivos |
|---|---|
| §2 motor (caminho, finais, legado, citações) | `src/pesquisa/logica.ts`, `src/pesquisa/tipos.ts`; validação da resposta em `src/pesquisa/validacao.ts` |
| §3.3 HTML seguro | `src/pesquisa/html.ts` (`limparHtml`, DOMPurify por import dinâmico), `src/pesquisa/BlocoHtml.vue` (o único `v-html`) |
| §3.4 CSP | `render.yaml` (`headers` de `/r/*`, `/f/*`, `/sair/*`), `web/README.md` |
| §5.2 página pública | `src/pesquisa/Pesquisa.vue`, `src/pesquisa/CampoPergunta.vue`, `src/pesquisa/variaveis.ts` |
| §5.3 editor | `src/modulos/formularios/EditorFormularioView.vue` e `src/modulos/formularios/editor/*` (controle do documento em `editor/documento.ts`); regras e frases da lógica em `logicaEditor.ts`; validação local em `validacaoFormulario.ts`; tipos e menu de adicionar em `tiposPergunta.ts` |
| §5.4–5.7 | `FormulariosView.vue`, `respostas/PainelAnalise.vue`, `editor/AbaRespostas.vue`, `auditoria/detalhes.ts`, `src/api/etapa2.ts` e `src/api/tipos.ts` |

O TipTap (`editor/EditorVisual.vue`) e o SortableJS só entram por `import()` dentro do editor; a página pública
(`responder.html`) não leva nada do editor, e o DOMPurify só desce quando a pesquisa tem HTML.

## 2. Decisões e desvios

1. **Ações da linha na estrutura:** num menu "Mais ações" (⋯), que aparece ao passar o mouse, com o foco na linha ou
   no item selecionado; dentro dele, Duplicar, "Mover para…" e Excluir (nos finais: Subir, Descer, Duplicar e
   Excluir). Três ícones fixos tiravam quase metade da largura do título na coluna de ~300 px (e, invisíveis, ainda
   pegavam o clique). O ícone do tipo é a alça de arrastar (vira a "pegada" ao passar o mouse).
2. **Renomear opção:** vale ao sair do campo (com o texto de quando ele ganhou o foco), não a cada tecla. No meio da
   digitação o texto pode bater com o de outra opção ("Sim, muito" → "Sim" → "Si…") e levaria as condições dela.
   Apagar uma opção esvaziada com Backspace usa o texto que ela tinha (as condições ainda usam esse).
3. **Problemas do rascunho:** os `problemas` do PUT só aparecem enquanto o documento está como foi enviado (mudou:
   esperam a próxima resposta, para não ficar um ponto vermelho velho) e só nos campos em que a validação do site não
   achou nada (a mesma falha com outras palavras não aparece duas vezes). Os `avisos` do PUT marcam o que não bloqueia
   o "Publicar".
4. **`tem_rascunho` do PUT** decide a etiqueta "Alterações não publicadas" (sem ele, compara o normalizado com o
   publicado).
5. **Sem PUT à toa:** se o documento volta a ser o que o servidor já tem (mover e voltar, desfazer tudo), não grava.
6. **Descartar** guarda o que estava na tela no desfazer: "Desfazer" logo depois traz as alterações de volta (e grava
   um rascunho novo). "Recarregar" (conflito) limpa o histórico.
7. **Prévia do editor:** "Reiniciar" volta ao começo, como quem abre o link (não ao item selecionado). "Computador"
   mostra a página em 1024 px reduzida numa janela de navegador.
8. **Aba Visual travada** só por HTML que a limpeza mantém e o TipTap não representa (tabela, div, figure…).
   Script, iframe, estilos e afins não travam: saem nas duas abas, e o aviso "Removemos por segurança: …" diz o quê.
9. **Escala:** a validação do site mantém a regra antiga, mais estrita que a da API ("O fim da escala vai de N a 10.",
   fim ≥ início + 2; a API aceita 2 a 10). O seletor do editor só oferece valores válidos; vale para dado antigo.
10. **Menu de adicionar:** Esc fecha o menu mesmo com a busca preenchida (a lista fica sempre à mostra; não é um popup
    da busca).
11. **Rota do editor:** de um formulário direto para outro, a tela monta de novo (`AppLayout` dá `key` por id), para o
    documento nunca ficar preso ao formulário anterior.
12. **Menu lateral:** o editor recolhe o menu lateral só enquanto está aberto (sem mudar a preferência guardada); a
    rota tem `meta.larguraTotal` para usar a largura toda.

## 3. O que o site usa da API

- `GET /formularios/{id}`: `perguntas`, `tema`, `finais`, `versao`, `publicado_em`, `publicado_por_nome`,
  `rascunho` (`{perguntas, tema, finais, salvo_em, salvo_por_nome}` | null), `rascunho_rev`, `prefixo_imagens`.
- `PUT /formularios/{id}/rascunho` `{rev, perguntas, tema, finais}` → `{rev, salvo_em, problemas, avisos,
  tem_rascunho, rascunho}`; 409 `rascunho_desatualizado` com `rev`, `salvo_em`, `salvo_por_nome` no `erro`; 422 com
  `campos`.
- `POST /formularios/{id}/publicar` `{rev}` → o formulário completo; 409 `rascunho_desatualizado`, `sem_rascunho`,
  `formulario_padrao`; 422 com `campos` (chaves de §2.6; botão em `finais.<i>.botao.texto`/`.url`).
- `DELETE /formularios/{id}/rascunho` → 204 (o editor busca o formulário de novo).
- `POST /formularios/{id}/imagens` (multipart `arquivo`) → `{url, largura, altura}`.
- `GET /formularios` (lista): `tem_rascunho`, `perguntas_total`.
- Página pública: `formulario.prefixo_imagens`, `formulario.tem_finais`; no envio, `final_id`, `html_final`,
  `botao_final`.
- Auditoria: `formulario_publicado` com `{formulario: {nome}, versao, perguntas, finais}`.

## 4. Ganchos para o teste integrado

- Cabeçalho: `[data-nome-formulario]`, `[data-situacao]`, `[data-alteracoes-nao-publicadas]`, `[data-salvamento]`
  (valor = `salvo` | `pendente` | `salvando` | `erro` | `conflito`), `[data-tentar-salvar]`, `[data-desfazer]`,
  `[data-refazer]`, `[data-botao-problemas]`, `[data-descartar]`, `[data-publicar]`, `[data-faixa-conflito]`,
  `[data-recarregar]`.
- Estrutura: `[data-estrutura]`, linhas `[data-item="<id>"]` (com `data-tipo`) e `[data-final="<id>"]`, o botão da
  linha `[data-linha]`, a alça `[data-alca]`, `[data-numero]`, `[data-titulo-linha]`, `[data-marca-logica]`,
  `[data-marca-problema]`, `[data-mais-acoes]` e, dentro do menu, `[data-acao="duplicar|mover-para|excluir|subir|descer"]`;
  `[data-inserir-entre]`, `[data-adicionar]`, `[data-final-padrao]`, `[data-adicionar-final]`, `[data-condicao-final]`,
  `[data-aviso-logica]`.
- Menu de adicionar: `[data-menu-adicionar]`, `[data-busca-adicionar]`, opções `[data-opcao="<chave>"]` (`nps`, `csat`,
  `estrelas`, `escala`, `escolha_unica`, `escolha_multipla`, `sim_nao`, `texto`, `comentario`, `email`, `telefone`,
  `numero`, `data`, `conteudo`, `html`, `quebra`). "Mover para…": `select[data-mover-destino]`,
  `[data-confirmar-mover]`.
- Edição: `[data-painel-edicao]`, campos `[data-campo="titulo|descricao|opcoes|html|nome|botao|botao.texto|botao.url|…"]`,
  `[data-menu-tipo]`, `[data-secao-logica]`, `[data-logica-onde="mostrar_se|pular"]`, `[data-condicao="N"]`
  (`select[data-fonte]`, `select[data-operador]`, `[data-valor]`, `[data-grupo-valor]`, `[data-opcao-valor]`,
  `[data-remover-condicao]`), `select[data-juncao]`, `[data-adicionar-condicao]`, `[data-regra="N"]`,
  `select[data-destino]`, `[data-adicionar-regra]`, `[data-remover-regra]`, `[data-criar-acompanhamento]`,
  `[data-criar-finais]`. Texto formatado: `[data-editor-html="<id>"]`, `[data-aba-visual]`, `[data-aba-html]`,
  `[data-so-no-html]`, `[data-previa-html]`, `[data-aviso-removido]`, `[data-formatar="…"]` (barra do Visual).
- Problemas: `[data-painel-problemas]`, `[data-grupo-problema="item:<id>|final:<id>|tema|formulario"]`,
  `[data-ir-problema]`.
- Prévia: `[data-coluna-previa]` (≥ 1280 px) ou `[data-abrir-previa]`; `[data-aparelho-opcao="celular|computador"]`,
  `[data-aparelho-atual]`, `[data-reiniciar]`; dentro da pesquisa, `[data-faixa-foco]`, `[data-tela-final]`
  (`data-final` = id ou `padrao`), `[data-html-final]`, `[data-botao-final]`.
- Página pública: `[data-nota="N"]`, `[data-conteudo]`, `[data-titulo-pergunta]`, `[data-lista-opcoes]`,
  `[data-dica-multipla]`, `[data-tela-final]`, `[data-html-final]`, `[data-botao-final]`, `[data-reiniciar-previa]`
  (só na prévia).
- Celular: `[data-voltar-lista]`.

## 5. Casos que faltam no JSON compartilhado (descritos, não editados)

1. Grupo `{juncao, condicoes: []}` com "todas" e com "qualquer" (os dois motores: verdadeiro).
2. Valor de resposta inválido para o tipo contando como sem resposta (nota fora da faixa ou não inteira, `true` numa
   nota, opção fora da lista, data impossível, texto só com espaços, lista vazia na múltipla) — inclusive para os
   operadores negativos (`diferente`, `nenhum_de`, `nao_inclui_nenhum`, `nao_contem`: falso).
3. Condição com `fonte` que não existe ou que é um bloco de conteúdo.
4. Regra de `pular` para trás, para um id desconhecido e para "fim" (para trás e desconhecido: ignorada).
5. `numero_do_texto`: "1e3", "nan", "inf", "1_000", "1.250" sem vírgula, espaços nas pontas.
6. Ids repetidos nos itens (vale o último).
7. `condicao` antiga com `grupos` que não é lista.
8. Citações: valor com `<`, `&` e aspas no HTML (escapado), id desconhecido ou de conteúdo (""), pergunta fora do
   caminho (""), data fora do formato.
