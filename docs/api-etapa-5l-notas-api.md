# Etapa 5l — notas da API (decisões, desvios e superfície)

Complementa `docs/api-etapa-5l.md` (o contrato continua valendo; aqui ficam só o que a API decidiu onde o contrato
deixou aberto e os acréscimos). Tudo em `api/`.

## 1. Superfície da API (para o site conferir)

### Documento do formulário (perguntas, tema, finais)

- Item (saída): `id`, `tipo`, `titulo`, `obrigatoria` e, por tipo:
  - perguntas: `descricao` (texto ou null); notas: `min`, `max`, `rotulo_min`, `rotulo_max`; `texto_curto`:
    `formato`; escolhas: `opcoes`;
  - campos novos **só quando diferentes do padrão**: `aleatorizar: true`, `exibicao: "lista"`, `max_selecoes`,
    `placeholder` (o site trata a falta como o padrão);
  - `conteudo`: `titulo` (nome interno, pode ser ""), `html` (limpo), `modo` (`visual` | `html`), `obrigatoria: false`
    (sem `descricao`);
  - `quebra_pagina`: como antes (`titulo`, `descricao`, `obrigatoria: false`), nunca com `logica`.
- `logica` (só quando há alguma): `{"mostrar_se": Grupo | null, "pular": [Regra]}` — sempre as duas chaves.
  - Grupo: `{"juncao": "todas" | "qualquer", "condicoes": [{"fonte", "op", "valor"}]}`; `valor` não vem em
    `respondida`/`nao_respondida`.
  - Regra: `{"id": "r_xxxxxx", "se": Grupo, "para": "<id>" | "fim"}`.
- Valores normalizados: `grupo_e` na ordem dos grupos (detrator, neutro, promotor; insatisfeito, neutro, satisfeito),
  sem repetir; listas de opções sem repetir (na ordem que vieram), aparadas; texto aparado; nota inteira.
- Final: `{"id": "f_xxxxxx", "nome", "titulo", "html" (limpo; "" quando vazio), "botao": {"texto", "url"} | null,
  "mostrar_se": Grupo | null}`. Botão com texto e endereço vazios vira `null`.
- Ids que faltam são gerados: itens `p_` + 6, regras `r_` + 6, finais `f_` + 6. Id de regra ou de final inválido ou
  repetido **ganha outro** (é interno; não dá erro). Id de item inválido ou repetido continua erro (estrutural).

### Rotas de formulário (login; ler com `formularios.ver`, o resto com `formularios.editar`)

| rota | o que mudou |
|---|---|
| `GET /formularios` | cada item ganha `tem_rascunho`, `versao`, `publicado_em`; `perguntas_total` conta só perguntas. |
| `GET /formularios/{id}` | ganha `finais`, `versao`, `publicado_em`, `publicado_por_nome`, `rascunho` (`{perguntas, tema, finais, salvo_em, salvo_por_nome}` ou null), `rascunho_rev`, `prefixo_imagens` (e os campos da lista). |
| `GET /formularios/modelos` | cada modelo ganha `finais` (9 modelos; os 3 novos antes de "Em branco"). |
| `POST /formularios` | aceita `finais`; nasce publicado (versão 1, `publicado_em`, `publicado_por`). Com `modelo` e sem `perguntas`, vêm também os finais do modelo. Resposta: o formulário completo. |
| `PATCH /formularios/{id}` | aceita `finais`. Com `perguntas`, `tema` ou `finais`: valida o documento inteiro (estrito) e publica direto (versão +1, `publicado_*`, auditoria); o conteúdo do rascunho fica como está, mas o `rascunho_rev` sobe (como em toda publicação: o editor aberto recebe 409 e recarrega, em vez de publicar por cima). Só `tema`: mescla sobre o publicado, como antes. `nome`, `descricao`, `ativo` e `publico` não publicam nem mexem no `rev`. |
| `PUT /formularios/{id}/rascunho` | corpo `{rev, perguntas?, tema?, finais?}` (o que faltar vem do rascunho atual, ou do publicado; `tema` parcial mescla). Resposta 200 `{rev, salvo_em, problemas, avisos, tem_rascunho, rascunho: {perguntas, tema, finais}}`. |
| `POST /formularios/{id}/publicar` | corpo `{rev}`. Resposta 200: o formulário completo (já sem rascunho). |
| `DELETE /formularios/{id}/rascunho` | 204 (também sem rascunho); sobe o `rascunho_rev`. |
| `POST /formularios/{id}/imagens` | multipart `arquivo` (PNG/JPEG até 1 MB, conferido pelos bytes). **201** `{url, largura, altura}` (largura/altura null se não der para ler). |
| `POST /formularios/{id}/logo` | igual (200 `{logo_url}`), mas não apaga o logo anterior. |
| `POST /formularios/{id}/duplicar` | copia o publicado, o rascunho e as imagens (com as URLs trocadas). |

Erros novos:

| status | `erro.codigo` | quando |
|---|---|---|
| 409 | `rascunho_desatualizado` | `rev` diferente do atual (PUT e publicar). O objeto `erro` traz também `rev` (o atual), `salvo_em` e `salvo_por_nome` (a última gravação: rascunho, publicação ou descarte). Mensagem: "Este formulário foi alterado em outra aba ou por outra pessoa. Recarregue para continuar." |
| 409 | `sem_rascunho` | publicar sem rascunho: "Não há alterações para publicar." |
| 409 | `formulario_padrao` | publicar (ou PATCH) mudando o tipo da nota principal do formulário padrão (como antes). |
| 409 | `limite_imagens` | o formulário já guarda 60 imagens (logos + conteúdo) entre uma limpeza e outra. |
| 422 | `dados_invalidos` | estrito: `campos` com as chaves de §2.6. No PUT do rascunho, só o estrutural (ver §2). |
| 413 | `pedido_grande_demais` | corpo acima de 1 MB em `POST/PATCH /formularios…` e `PUT …/rascunho` (1 MB + folga no envio de imagem). |

`problemas` e `avisos` do PUT: objetos `{chave: mensagem}` (uma mensagem por chave, a primeira). `problemas` traz os
erros que impedem publicar **e** os avisos de citação (§2.7); `avisos` repete só as chaves de `problemas` que são
avisos (não bloqueiam publicar). Para saber se dá para publicar: `chaves(problemas) − chaves(avisos)` vazio. O padrão
da conta que muda de tipo também aparece em `problemas` (chave `perguntas`).

`tem_rascunho` do PUT: false quando o documento normalizado ficou igual ao publicado (aí nada fica guardado e o
"Publicar" pode ficar desabilitado).

### Página pública

- `GET /publico/convites/{token}` e `GET /publico/formularios/{codigo}`: `formulario.perguntas` com a `logica`;
  `conteudo.html` com as variáveis trocadas e escapadas (`renderizar_html`); o `titulo` do bloco de conteúdo vai vazio
  (nome interno); títulos e descrições com as variáveis e as citações `{{ID}}` intactas. `prefixo_imagens` e
  `tem_finais` (true se a lista de finais tem algum) vão **dentro de `formulario`** e repetidos no topo da resposta.
  Os finais não vão.
- `POST …/responder`: além de `titulo_final` e `texto_final` (e, no convite, `indicacao` e `depoimento`), vêm
  `final_id`, `html_final` e `botao_final`. No final escolhido: `titulo_final` = título dele (variáveis trocadas,
  citações intactas), `texto_final` = "", `html_final` = HTML dele com variáveis escapadas (**"" se o final não tem
  HTML**), `botao_final` = `{texto, url}` (texto com variáveis; o endereço como gravado) ou null. No final padrão:
  `final_id`, `html_final` e `botao_final` null.
- Erros de envio: como antes, por id de pergunta, só das perguntas do caminho; `max_selecoes` → "Escolha no máximo N
  opções.".

### Banco de imagens

`em_uso` também fica true para imagem citada num formulário não arquivado (logo do tema ou HTML, publicado ou
rascunho). Excluir uma assim: 409 `imagem_em_uso` "Esta imagem está no formulário “NOME”. Tire a imagem do formulário
antes de excluir.".

### Auditoria

`formulario_publicado` ("Formulário publicado", info, grupo `configuracoes`), detalhe `{formulario: {id, nome}, versao,
perguntas, finais}` (perguntas = só perguntas; finais = quantos).

## 2. Decisões e desvios

1. **Estrutural × problema no rascunho.** Dá 422 mesmo no rascunho: formato (lista/objeto/tipo do valor), `tipo`
   desconhecido, id de item inválido ou repetido, textos acima do tamanho (título 300, nome interno 120, descrição 1000,
   rótulos 60, opção 200, placeholder 120, nome do final 60, título do final 120, botão 40/500, texto de condição 200),
   HTML acima de 50.000 recebidos ou 20.000 limpo, mais de 120 itens, `modo` do tema e `exibicao` fora da lista,
   `formato` desconhecido, número que não é número (`min`, `max`, `max_selecoes`). Todo o resto é problema e fica
   gravado como a pessoa fez (título vazio, opções, faixa da escala, lógica incompleta ou errada, finais, limites de
   quantidade, cor e logo do tema). Cor ou logo inválidos: problema, e o rascunho guarda o valor anterior.
2. **Quebras de página**: no rascunho ficam como estão (o editor não perde a quebra que acabou de pôr); no estrito
   (criar, PATCH, publicar) saem as do começo, do fim e as repetidas, como antes.
3. **Grupo sem condições**: o motor trata como verdadeiro (como null), qualquer que seja a junção; a validação recusa
   ("Adicione pelo menos uma condição."). Regra sem `se` ou com grupo vazio: "Adicione pelo menos uma condição à regra
   N.".
4. **Mensagens além das do contrato** (mesmo tom): "Escolha a pergunta da condição N." / "Escolha a comparação da
   condição N." (com "Na regra R, …" dentro de regras), "… usa uma comparação que não vale para este tipo de
   pergunta.", "… precisa de um número inteiro de A a B.", "… precisa de dois números de A a B, o primeiro menor ou
   igual ao segundo.", "… precisa de grupos válidos: …", "… precisa de pelo menos uma opção.", "… precisa de Sim ou
   Não.", "… precisa de um texto de 1 a 200 caracteres.", "… precisa de um número.", "… precisa de uma data válida
   (AAAA-MM-DD).", "… usa esta mesma pergunta (só as anteriores servem de condição).", "… usa uma quebra de página (só
   perguntas servem de condição).", "A regra N manda para um item que não existe mais.", "A regra N manda para uma
   quebra de página; escolha uma pergunta ou o fim.", "Escolha para onde a regra N manda.", "Blocos de conteúdo não
   podem pular; a regra fica na pergunta.", "Use no máximo 10 condições em cada grupo.", "Use no máximo 10 regras em
   cada pergunta.", "Use no máximo 30 blocos de conteúdo.", "Use no máximo 10 finais.", "Dê um nome ao final (só a sua
   equipe vê).", "Escreva o título do final.", "Escreva o texto do botão.", "O máximo de opções precisa ficar entre 2 e
   N.". Na regra de pular, a fonte que vem depois sai como "Na regra R, a condição N usa uma pergunta que vem depois
   desta.".
5. **Chaves do botão do final**: `finais.<i>.botao.texto` e `finais.<i>.botao.url` (o contrato fala em
   `finais.<i>.<campo>`).
6. **Avisos de citação** na chave do campo onde está o token: `perguntas.<i>.titulo`, `.descricao` ou `.html`;
   `finais.<i>.titulo` ou `.html` (nos finais a mensagem diz "…não aponta para uma pergunta do formulário…").
7. **Formato antigo**: além do caso do contrato (sem nota principal antes), os outros erros da `condicao` antiga
   continuam com a chave e a mensagem de antes (`perguntas.<i>.condicao`: grupos inválidos, operador, faixa da nota),
   validados antes de converter. No rascunho, `condicao` que não dá para converter é problema e sai.
8. **Imagens dos formulários**: o índice único "um logo por formulário" saiu (o rascunho guarda outro logo sem apagar o
   publicado). A limpeza (publicar, PATCH com conteúdo e descartar) só apaga imagens do formulário que **nenhum
   formulário da conta** cita (HTML copiado de um formulário para outro não quebra). Entre limpezas, até 60 imagens por
   formulário (409 `limite_imagens`), para o envio não crescer sem fim. Salvar o rascunho não apaga nada (desfazer no
   editor ainda acha a imagem).
9. **Duplicar**: copia as imagens da plataforma citadas no publicado e no rascunho (logo e HTML), menos as do banco de
   imagens (essas ficam compartilhadas), com o mesmo uso (logo → logo; conteúdo → conteúdo; logo da conta → logo do
   formulário).
10. **`formulario_versao`**: gravada em toda resposta que passa por `gravar_resposta` (páginas públicas e registro à
    mão); nula nas importadas e nas antigas.
11. **`publicado_em`** ganhou `DEFAULT now()` (depois de preencher os antigos com `atualizado_em`): os formulários
    semeados nas contas novas também nascem com a data.
12. **E-mail**: o título da nota principal sai sem as citações (vazias, como na página antes de qualquer resposta).
13. **Resumo da resposta** (`respostas.comentario`) também mostra "…" no lugar das citações.
14. **Exportação da conta**: `formularios.csv` ganhou a coluna "Finais (JSON)" (a versão publicada).
15. **`AppError`** ganhou `extra` (campos a mais no objeto `erro`), usado pelo 409 `rascunho_desatualizado`.
16. **Título do bloco de conteúdo** não vai para a página pública (vai ""), por ser nome interno.
17. **`html_final`** do final escolhido sem HTML é "" (null fica só para o final padrão).
18. **Ajuda**: a jornada `preparar-a-pesquisa` (passos e resultado) foi atualizada para o rascunho e o "Publicar";
    seções novas entraram depois de `perguntas-do-formulario` (`rascunho-e-publicacao`) e de
    `variaveis-condicoes-e-nota-principal` (`blocos-de-conteudo-e-html`). A Ajuda não aceita `{{`, `<` nem "http":
    as citações e o "endereço seguro" do botão são descritos sem esses caracteres.
19. **`rascunho_rev` no PATCH com conteúdo**: sobe (o contrato diz que o PATCH "não mexe no rascunho"; o conteúdo do
    rascunho não muda, mas o editor aberto precisa saber que o publicado mudou). `rascunho_em`/`rascunho_por` também
    passam a ser de quem publicou, para a mensagem do 409.

## 3. Casos que faltam no JSON compartilhado (descritos, não editados)

1. Grupo com `condicoes: []` e `juncao: "qualquer"` (a API trata como verdadeiro, igual a null).
2. Condição com `fonte` que não existe nos itens (a API: sem resposta — `nao_respondida` verdadeira, o resto falso).
3. Valor inválido para o tipo contando como sem resposta: nota fora da faixa (11), `true` numa nota, opção que não
   existe, data impossível ("2026-02-30"), texto só com espaços, múltipla com lista vazia.
4. `pular` com `para` para trás ou para um id desconhecido (a API ignora a regra e segue para o próximo item).
5. `numero_do_texto`: "1.250" (sem vírgula) = 1,25; expoente ("1e3"), "nan" e "1_000" não são número; espaços nas pontas
   aparados.
6. `grupo_e` numa fonte `estrelas` (grupos do CSAT).
7. Final com `mostrar_se: null` antes de outros (pega tudo, os de baixo nunca valem).
8. Resposta para o id de um bloco `conteudo` (ignorada; nunca entra em `valores`).
9. `sim_nao` com operador `diferente` (não vale para o tipo: a API dá falso).

## 4. Testes

- Novos: `test_logica_formularios.py` (todos os casos de `caminho`, `finais` e `legado` do JSON, mais as peças do
  motor), `test_html_seguro.py`, `test_formularios_v2.py` (cada regra de §2.6 com chave e mensagem, limites, legado,
  ids, campos novos, finais, rascunho, publicar, descartar, PATCH, duplicar, permissões, imagens e corpo grande),
  `test_publico_logica.py` (envio com pular e escondidos, finais, versão, `max_selecoes`, página pública, telas
  internas) e `test_migracao_etapa5l.py` (objetos, restrições, legado convertido, descer e subir).
- Antigos ajustados (semântica mudada de propósito):
  - `test_formularios.py`: `test_conta_nova_recebe_formularios_padrao` e `test_condicao_so_depois_da_nota_principal`
    comparam `logica.mostrar_se` no lugar de `condicao`; `test_modelos` com os 9 modelos.
  - `test_migracao_dados_empresa.py::test_restricoes_de_imagens`: mais de um logo por formulário passa a valer.
  - `test_dados_empresa.py`: `test_logo_do_formulario_e_salvar_o_formulario` (enviar logo não apaga o publicado; a
    limpeza é ao publicar e respeita outro formulário que cita a imagem), `test_copiar_formulario_copia_o_logo` (3
    logos: 2 no original até publicar, 1 na cópia) e `test_pagina_da_pesquisa_usa_o_logo_do_formulario_ou_o_da_conta`
    (enviar logo não muda o que está no ar; a volta para o logo da conta é testada apagando a imagem).
  - `test_dados_exportacao.py`: cabeçalho de `formularios.csv` com "Finais (JSON)".

## 5. Pendências

- O site precisa ler `avisos` (ou comparar as chaves) para não travar o "Publicar" por um aviso de citação.
- `tem_finais` é "a lista tem algum final", não "algum final tem HTML".
- Troca do domínio da API: as imagens no HTML só passam pela limpeza com o prefixo atual (`API_PUBLIC_URL`); HTML
  gravado com outro domínio perde as imagens na próxima gravação.
