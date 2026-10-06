# Etapa 5l — Construtor de formulários: lógica, conteúdo/HTML, editor novo, rascunho e publicação

Pedido do Marcelo (06/10/2026): "a criação de formulários precisa ser incrível, possibilitar adicionar HTML, fornecer
condições baseadas nas perguntas, olhar os melhores players do mercado e construir". Decisões dele:
- Entram as três frentes (lógica, conteúdo/HTML, editor) **mais rascunho e publicação**: o editor salva sozinho num
  rascunho e o que está no ar só muda ao clicar em **Publicar**.
- **Sem CSS próprio**: o visual continua só cor + logo.

Referências de mercado usadas: Typeform, Tally, SurveyMonkey, Qualtrics, Jotform, Google Forms, Formbricks, Fillout,
Survicate, Retently e AskNicely. O resumo está em §9.

Casos compartilhados da lógica: **`docs/casos-logica-5l.json`**. Os dois motores (Python e TypeScript) leem esse arquivo
nos testes e precisam dar o mesmo resultado em todos os casos (§2.7).

---

## 0. Princípios

1. **Um documento, dois motores iguais.**
   - A lógica é avaliada no navegador (mostrar/esconder ao vivo e prévia) e de novo na API ao receber a resposta.
   - A API decide o que vale: descarta respostas de itens fora do caminho, cobra obrigatória só no caminho e escolhe o
     final.
2. **Só para frente.**
   - Condições só olham itens anteriores (os finais olham qualquer pergunta).
   - Pular só vai para itens posteriores ou para o fim.
   - Não há laços, e o caminho sai em uma passada.
3. **A nota principal é sagrada.** Ela não pode ter condição e não pode ser pulada (§2.6). Isso protege `nota`/`grupo`,
   o painel, os relatórios, o `?nota=` do e-mail e a régua do e-mail.
4. **HTML sim, script nunca.**
   - O HTML é limpo por lista permitida na API, ao salvar, e de novo no navegador antes de desenhar.
   - A página da pesquisa fica no mesmo endereço do app (`toqqi.com`), onde está a sessão de quem usa o app; por isso
     também entra CSP nas páginas de pesquisa.
5. **Nada quebra para quem já usa.**
   - `condicao` antiga continua aceita na entrada e é convertida (§2.8).
   - `PATCH /formularios/{id}` com `perguntas`/`tema` continua funcionando e publica direto (§4.2).
   - Os testes existentes continuam passando. Quando a semântica mudou de propósito, o teste é ajustado e a mudança é
     registrada no relatório.

---

## 1. Modelo de dados

### 1.1 Itens (`formularios.perguntas`, lista ordenada)

Cada elemento da lista é um **item**: pergunta, bloco de conteúdo ou quebra de página.

Campos comuns:

| campo | regra |
|---|---|
| `id` | `^[A-Za-z0-9_-]{1,32}$`, único no formulário. Novos ids: `p_` + 6 caracteres `[a-z0-9]` na API **e no site** (hoje o site gera `p`+6; passa a gerar `p_`+6; ids antigos continuam válidos). |
| `tipo` | um de §1.2 |
| `titulo` | ≤300; obrigatório para perguntas; opcional (≤120, nome interno) em `conteudo`; pode ser vazio em `quebra_pagina` |
| `descricao` | ≤1000 ou null (perguntas) |
| `obrigatoria` | bool (forçado `false` em `conteudo` e `quebra_pagina`) |
| `logica` | §1.3 (opcional; ausente/vazio = sem lógica; nunca em `quebra_pagina`) |

### 1.2 Tipos

Perguntas (respondíveis): `nps`, `csat`, `estrelas`, `escala`, `texto_curto`, `comentario`, `escolha_unica`,
`escolha_multipla`, `sim_nao`, `data`.

Os campos de hoje continuam. Campos novos, todos opcionais:

| tipo | campo novo | regra |
|---|---|---|
| `escolha_unica`, `escolha_multipla` | `aleatorizar` | bool. Embaralha a ordem das opções para quem responde, uma vez por visita (a ordem salva não muda). |
| `escolha_unica` | `exibicao` | `"botoes"` (padrão) ou `"lista"` (lista suspensa, boa para muitas opções). |
| `escolha_multipla` | `max_selecoes` | inteiro entre 2 e o nº de opções, ou null. Quem responde não marca mais que isso; a API recusa com "Escolha no máximo N opções." |
| `texto_curto`, `comentario` | `placeholder` | ≤120 ou null. Texto de exemplo dentro do campo. |

Não respondíveis:

| tipo | campos | uso |
|---|---|---|
| `conteudo` (**novo**) | `html` (string já limpa, §3; ≤20000 caracteres depois da limpeza; obrigatória e não vazia no publicar); `modo` (`"visual"` ou `"html"`, só dica para o editor abrir na aba certa); `titulo` (opcional, ≤120, nome interno mostrado só no editor); `logica.mostrar_se` permitido, `logica.pular` **não** | Texto formatado, imagens, avisos, termos, links. |
| `quebra_pagina` | como hoje | Separa páginas no modo `paginas`; no modo `uma_por_vez` não faz nada. |

### 1.3 Lógica de um item

```jsonc
"logica": {
  "mostrar_se": Grupo | null,          // item aparece só se o grupo for verdadeiro (perguntas e conteudo)
  "pular": [ Regra, ... ]              // só perguntas; avaliado depois do item; vale a 1ª regra verdadeira
}
Grupo     = { "juncao": "todas" | "qualquer", "condicoes": [ Condicao, ... ] }   // 1..10 condições, sem aninhar
Condicao  = { "fonte": "<id de pergunta>", "op": "<operador §2.2>", "valor": <conforme o operador; ausente em respondida/nao_respondida> }
Regra     = { "id": "r_xxxxxx", "se": Grupo, "para": "<id de item posterior>" | "fim" }   // até 10 regras por item
```

### 1.4 Finais (`formularios.finais`, coluna nova, lista ordenada)

```jsonc
{ "id": "f_xxxxxx",                 // único; `f_` + 6
  "nome": "Promotores",             // ≤60, nome interno (editor e relatórios), obrigatório
  "titulo": "Que bom que gostou!",  // ≤120, obrigatório; aceita variáveis {empresa}… e citações {{id}}
  "html": "<p>…</p>",               // opcional, limpo (§3), ≤20000
  "botao": { "texto": "Avaliar no Google", "url": "https://…" } | null,   // texto ≤40; url https, ≤500
  "mostrar_se": Grupo | null }      // null = sempre vale (fica por último; o editor avisa se não estiver)
```

- Até 10 finais.
- O **final padrão** continua sendo `tema.titulo_final` + `tema.texto_final`. Ele vale quando nenhum final da lista vale.
  No editor aparece como "Final padrão" (não dá para excluir).

### 1.5 Rascunho e publicação (colunas novas em `formularios`)

| coluna | tipo | uso |
|---|---|---|
| `finais` | jsonb not null default `'[]'` | finais publicados |
| `rascunho` | jsonb null | `{perguntas, tema, finais}` em edição; null = sem alterações pendentes |
| `rascunho_rev` | int not null default 0 | sobe a cada gravação do rascunho, ao publicar e ao descartar (controle de concorrência) |
| `rascunho_em` | timestamptz null | quando o rascunho foi salvo pela última vez |
| `rascunho_por` | FK usuário (mesmo padrão das outras FKs de usuário da conta), null | quem salvou o rascunho por último |
| `versao` | int not null default 1 | versão publicada; sobe a cada publicação (incluindo `PATCH` com conteúdo) |
| `publicado_em` | timestamptz null | quando publicou |
| `publicado_por` | FK usuário, null | quem publicou |

Também entra `respostas.formulario_versao int null`: a versão publicada no momento da resposta, para o futuro histórico
de versões.

`nome`, `descricao`, `ativo`, `publico`, padrão e código **não** entram no rascunho; mudam na hora, como hoje.

### 1.6 Limites

| item | limite |
|---|---|
| perguntas respondíveis | ≤60 (como hoje) |
| blocos `conteudo` | ≤30 |
| total de itens | ≤120 (como hoje) |
| condições por grupo | ≤10 |
| regras `pular` por item | ≤10 |
| finais | ≤10 |
| `html` | ≤50000 caracteres recebidos e ≤20000 depois da limpeza; acima disso, 422 "Este conteúdo está grande demais (máx. 20.000 caracteres)." |
| corpo das rotas de formulário | entrada em `LIMITES_DE_CORPO` (`main.py`): `POST/PATCH /formularios…` e `PUT …/rascunho` até **1 MB**; upload de imagem segue o limite de imagens (1 MB) |

---

## 2. Semântica da lógica (igual nos dois motores)

### 2.1 Normalização de texto (para operadores de texto)

`norm(s)`:
1. Unicode NFD.
2. Remove as marcas combinantes (categoria Mn).
3. Minúsculas (`lower()` / `toLowerCase()`).
4. Apara as pontas.
5. Junta espaços repetidos (`\s+` → um espaço).

O valor da condição passa pela mesma normalização.

**Número de texto** (`texto_curto` com `formato: "numero"`): se tem vírgula, tira os pontos e troca a vírgula por ponto;
senão, usa como está. Depois converte para float. Exemplos: "1.250,5" → 1250.5, "12.5" → 12.5. Se não der número, a
condição é falsa.

### 2.2 Operadores por tipo da fonte

| fonte | operadores (valor) |
|---|---|
| `nps`, `csat`, `estrelas`, `escala` | `igual`, `diferente`, `menor`, `menor_igual`, `maior`, `maior_igual` (número inteiro dentro da faixa da fonte); `entre` (`[a, b]`, inclusivo, a ≤ b, dentro da faixa); `grupo_e` (lista não vazia de grupos; **só nps/csat/estrelas**); `respondida`, `nao_respondida` |
| `escolha_unica` | `um_de`, `nenhum_de` (lista não vazia de opções existentes, texto exato) |
| `escolha_multipla` | `inclui_algum`, `inclui_todos`, `nao_inclui_nenhum` (lista não vazia de opções existentes) |
| `sim_nao` | `igual` (`true`/`false`) |
| `texto_curto` (formatos texto, email, telefone) e `comentario` | `contem`, `nao_contem`, `igual`, `diferente`, `comeca_com`, `termina_com` (texto 1..200, comparado com `norm`) |
| `texto_curto` formato `numero` | `igual`, `diferente`, `menor`, `menor_igual`, `maior`, `maior_igual` (número), `entre` (`[a, b]`) |
| `data` | `igual`, `diferente`, `menor` (antes de), `menor_igual`, `maior` (depois de), `maior_igual`, `entre` (`"AAAA-MM-DD"`; compara como texto) |
| todas as perguntas | `respondida`, `nao_respondida` (sem valor) |

Grupos:
- NPS: 0–6 `detrator`, 7–8 `neutro`, 9–10 `promotor`.
- CSAT e estrelas: 1–2 `insatisfeito`, 3 `neutro`, 4–5 `satisfeito`.

### 2.3 Sem resposta

Uma fonte **não respondida** conta como sem resposta. Também contam assim uma fonte **fora do caminho** (escondida ou
pulada) e uma fonte com valor inválido.

Nesses casos:
- `nao_respondida` é verdadeira e `respondida` é falsa.
- **Todo** outro operador é **falso**, inclusive `diferente`, `nenhum_de`, `nao_contem` e `nao_inclui_nenhum`.

Um grupo `todas` é verdadeiro se todas as condições forem, e um grupo `qualquer` se alguma for. Grupo null ou ausente
vale como verdadeiro.

### 2.4 Caminho

```
caminho(itens, respostas) -> lista de ids, em ordem, sem as quebras de página
  vistos = []; valores = {}            # valores: só respostas de itens já no caminho
  i = 0
  enquanto i < len(itens):
    it = itens[i]
    se it.tipo == quebra_pagina: i += 1; continue
    se não avaliar(it.logica.mostrar_se, valores): i += 1; continue     # escondido: não entra, nem dispara regras
    vistos.append(it.id)
    se it é pergunta e it.id em respostas: valores[it.id] = respostas[it.id]
    destino = primeira regra de it.logica.pular cujo `se` é verdadeiro (avaliado com `valores`), senão nenhum
    se destino == "fim": pare
    se destino: i = índice(destino); continue
    i += 1
```

- No navegador o caminho é recalculado a cada mudança de resposta. Itens à frente aparecem e somem conforme a pessoa
  responde. Por isso, no modo `paginas`, uma regra `pular` com `nao_respondida` esconde os itens seguintes da mesma
  página enquanto a pergunta estiver vazia. Isso é esperado e está no caso "regra de pular de pergunta opcional sem
  resposta".
- **Respostas fora do caminho são descartadas** (no envio do navegador e na API).

### 2.5 Final

```
escolher_final(finais, itens, respostas) -> id | null
  valores = respostas dos itens do caminho
  devolve o id do 1º final cujo mostrar_se (avaliado com `valores`) é verdadeiro; null se nenhum
```

`null` = final padrão do tema.

### 2.6 Regras de validação (publicar e PATCH com conteúdo)

As mensagens são em português simples, e as chaves de erro vão em `campos` (422 `dados_invalidos`).

1. **Fonte.**
   - Precisa ser uma **pergunta** (não `conteudo` nem `quebra_pagina`).
   - Em `mostrar_se` de um item, a fonte vem **antes** do item.
   - Em `pular`, a fonte vem antes ou é o próprio item.
   - Em finais, a fonte pode ser qualquer pergunta.
   - Mensagens: "A condição N usa uma pergunta que vem depois desta." / "…que não existe mais." / "…um bloco de conteúdo (só perguntas servem de condição)."
2. **Operador e valor.**
   - O operador precisa valer para o tipo (e o formato) da fonte (§2.2).
   - O valor precisa ser válido: número inteiro na faixa (`entre` com a ≤ b); grupos válidos para o tipo; opções
     existentes ("A condição N usa a opção 'X', que não existe mais."); texto de 1 a 200 caracteres; data AAAA-MM-DD
     válida; bool em `sim_nao`.
   - `respondida` e `nao_respondida` não levam valor (se vier, é ignorado e removido).
3. **Pular.**
   - Só em perguntas.
   - `para` = id de item **posterior** que não seja `quebra_pagina`, ou `"fim"`. Mensagem: "A regra N manda para uma pergunta que vem antes desta (só dá para pular para frente)."
   - Ids de regra `r_` + 6, únicos no formulário. Se vierem faltando, a API gera.
4. **Nota principal** (a 1ª `nps`; senão a 1ª `csat`/`estrelas`; como hoje).
   - Não pode ter `mostrar_se`: "A nota principal sempre aparece; tire a condição dela."
   - Itens **antes** dela não podem ter `pular`: "Perguntas antes da nota principal não podem pular (a nota principal não pode ficar de fora)."
5. **Conteúdo.** `html` não vazio depois da limpeza: "Escreva o conteúdo do bloco." Sem `pular`.
6. **Finais.**
   - `nome`, `titulo` e o tamanho do `html` (§1.4).
   - `botao.url` https e ≤500. `botao.texto` obrigatório se houver botão.
   - Condições como em finais (item 1).
   - Ids `f_` + 6 únicos.
7. **Limites** de §1.6.
8. **Padrão.** Formulário padrão não muda o tipo da nota principal (regra de hoje, 409 `formulario_padrao`). Vale no
   publicar e no PATCH.

**Chaves de erro.** Valem também para `problemas` do rascunho.

| erro | chave |
|---|---|
| campo de item | `perguntas.<i>.<campo>` (como hoje) |
| lógica de item | `perguntas.<i>.logica` (a mensagem diz qual condição ou regra) |
| final | `finais.<i>.<campo>` ou `finais.<i>.mostrar_se` |
| tema | `tema.<campo>` |
| formulário | `perguntas` (mensagem geral, ex.: limite) |

### 2.7 Citações (piping)

- Token **`{{ID}}`**, onde ID é o id de uma **pergunta anterior**. Vale em `titulo`/`descricao` de perguntas, no `html`
  de conteúdo e no `titulo`/`html` dos finais (estes podem citar qualquer pergunta).
- Quem renderiza é o **navegador**, com as respostas que tem.
  - A API não troca os tokens. As funções de variáveis da API (`renderizar`) não podem estragar `{{…}}`.
  - Nas telas internas (resultados, detalhe da resposta, CSV), a API troca `{{ID}}` por "…" no título.
- Formato por tipo (casos `citacoes` do JSON):
  - números: o próprio número;
  - escolha única: a opção;
  - múltipla: "A", "A e B", "A, B e C";
  - sim/não: "Sim" / "Não";
  - data: "DD/MM/AAAA";
  - texto: aparado, cortado em 200 + "…";
  - sem resposta ou fora do caminho: "" (vazio).
- Em texto puro (títulos), o token vira texto por interpolação normal do Vue. No HTML, o valor entra **escapado** (`& < > " '`) e depois o HTML todo passa pelo DOMPurify (§3.3).
- Token com id desconhecido vira "". Na validação, um token que aponta para pergunta inexistente ou posterior gera
  **aviso** (não erro): `perguntas.<i>.titulo` = "A citação {{ID}} não aponta para uma pergunta anterior; ela vai sair
  vazia." Só no rascunho (`problemas`); não bloqueia publicar.

### 2.8 Formato antigo (`condicao`)

- Na entrada (criar, PATCH, rascunho, modelos), `condicao` é convertida para `logica.mostrar_se`, com a fonte na nota
  principal (casos `legado`):
  - `{"tipo":"grupo","grupos":[…]}` → `grupo_e`;
  - `{"tipo":"nota","operador":"<=","valor":v}` → `menor_igual`;
  - `">="` → `maior_igual`.
  - Se o item já tem `logica.mostrar_se`, `condicao` é ignorada.
  - Converte antes de validar. Se não houver nota principal **antes** do item, a condição antiga é recusada com a
    mensagem de hoje ("A condição só pode ser usada em perguntas depois da nota principal.", chave
    `perguntas.<i>.condicao`), para manter o contrato antigo.
- A saída nunca tem `condicao`.
- Migração `0026` converte os formulários gravados: `perguntas` publicadas e `rascunho` (vazio hoje).
- Os testes antigos que comparam `condicao` passam a comparar a forma nova; registre no relatório quais mudaram.

---

## 3. HTML: lista permitida e onde limpar

### 3.1 Lista permitida (API com **nh3**; site com **DOMPurify**, mesma lista)

**Tags:** `p br strong b em i u s a ul ol li h2 h3 h4 blockquote hr img span div table thead tbody tr th td caption
small sub sup code pre figure figcaption`.

**Atributos:**

| tag | atributos |
|---|---|
| `a` | `href` (`https:`, `http:`, `mailto:`, `tel:`), `title`. Sempre com `target="_blank"` e `rel="noopener noreferrer nofollow ugc"` (forçados). |
| `img` | `src` **só de imagens da plataforma** (prefixo `imagens.prefixo_publico()` = `API_PUBLIC_URL` + `/api/v1/publico/imagens/` + chave válida; no site, o prefixo vem da API: §4.6), `alt`, `width`, `height` (inteiros 1–2000). Outras imagens são **removidas** (privacidade: a página da pesquisa não chama outros sites). |
| `td`, `th` | `colspan`, `rowspan` (1–20) |
| `p h2 h3 h4 div td th` | `style` só com `text-align: left/center/right/justify`. Qualquer outra propriedade cai. |

**Cai tudo o mais:** `class`, `id`, `name`, `on*`, `style` com outras coisas, `script`, `style`, `iframe`, `object`,
`embed`, `form`, `input`, `button`, `svg`, `math`, `video`, `audio`, `meta`, `link`, `base`, comentários, `data:` e
`javascript:`.

### 3.2 Onde a API limpa

Em toda entrada de `html` (itens `conteudo` e finais): criar, PATCH, rascunho, publicar, duplicar e modelos.
- Grava sempre o HTML **limpo**.
- Dependência nova: `nh3` em `api/requirements.txt`, versão atual estável.
- Módulo `api/toqqi/core/html_seguro.py` com `limpar_html(html: str) -> str` e as listas.

Variáveis `{empresa} {nome} {assunto} {referencia}` dentro de HTML:
- Função **nova** `renderizar_html(texto, variaveis)`: troca **escapando** o valor (`html.escape`) e **não** junta
  espaços.
- Usada no payload público para `conteudo.html` e no `html` do final.
- `renderizar` (texto puro) continua para títulos e textos, e não pode tocar em `{{…}}`.

### 3.3 Onde o site limpa

Antes de **todo** `v-html`, sempre com o mesmo helper: `web/src/pesquisa/html.ts`, `limparHtml(html, prefixoImagens)`.
O helper usa DOMPurify com a lista de §3.1, mais um gancho para `style` (só `text-align`), `img src` (prefixo) e
`a target/rel`.

Ordem no navegador: variáveis (já vieram trocadas da API, ou trocadas na prévia com escape), depois citações
**escapadas**, depois `limparHtml`, depois `v-html`.

- O DOMPurify entra por **import dinâmico** só quando o formulário tem `conteudo` ou final com `html`, para não pesar a
  página de quem não usa.
- `v-html` só no componente `BlocoHtml.vue` (pasta `src/pesquisa`), que sempre chama `limparHtml`.
- Teste novo: nenhum outro `v-html` em `web/src` fora desse componente (varre os `.vue`).
- O editor mostra o que foi tirado: DOMPurify expõe `DOMPurify.removed`. Aviso no bloco: "Removemos por segurança:
  script, onclick, iframe…".

### 3.4 CSP nas páginas de pesquisa

No `render.yaml`, em `headers`, para `/r/*`, `/f/*` e `/sair/*`:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://api.toqqi.com; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors *
```

- `img-src https:` mantém os logos externos que já são aceitos hoje.
- `frame-ancestors *` mantém o widget.
- Conferir com o build de produção servido localmente com esse cabeçalho (Playwright): a pesquisa abre, responde e
  envia sem erro de CSP no console, e o widget abre em iframe.
- Documentar no README do site.

---

## 4. API (pasta `api/`)

### 4.1 Módulos novos

`api/toqqi/modulos/formularios/logica.py`:
- `norm`, `numero_do_texto`, `grupo_da_nota`;
- `avaliar_condicao`, `avaliar_grupo(grupo, valores, itens_por_id)`;
- `caminho(itens, respostas)`, `escolher_final(finais, itens, respostas)`;
- `converter_condicao_legada(condicao, id_principal)`;
- `descrever_grupo(grupo, itens)`, que gera a frase em português: "NPS é detrator ou neutro" etc. Usada só em mensagens
  e na Ajuda; opcional.

`validacao.py` passa a validar o formato novo: `normalizar_perguntas`, `normalizar_tema` e o novo
`normalizar_finais`. Uma função `normalizar_documento(perguntas, tema, finais, estrito: bool)` devolve
`(doc_normalizado, problemas)`:
- `estrito=True` (publicar, PATCH, criar): problemas viram 422.
- `estrito=False` (rascunho): grava mesmo com problemas. Aplica só o estrutural: tipos conhecidos, campos permitidos,
  limites de tamanho, HTML limpo. Devolve `problemas` (mesmas chaves de §2.6), mais os avisos de citação.

### 4.2 Rotas de formulário

| rota | mudança |
|---|---|
| `GET /formularios` | Cada item ganha `tem_rascunho` (bool), `versao` e `publicado_em`. `perguntas_total` conta só perguntas (sem conteúdo nem quebra). |
| `GET /formularios/{id}` | Ganha `finais`, `versao`, `publicado_em`, `publicado_por_nome`, `rascunho` (`{perguntas, tema, finais, salvo_em, salvo_por_nome}` ou null), `rascunho_rev` e `prefixo_imagens` (§4.6). |
| `POST /formularios` | Como hoje. Aceita também `finais`. Cria publicado (`versao` 1, `publicado_em` agora). Os modelos novos (§4.8) já vêm com lógica e finais. |
| `PATCH /formularios/{id}` | Como hoje. Aceita `finais`. Com `perguntas`/`tema`/`finais`: valida estrito e **publica direto** (versão +1, `publicado_*`, auditoria `formulario_publicado`). Não mexe no rascunho. |
| **`PUT /formularios/{id}/rascunho`** | Corpo `{rev, perguntas, tema, finais}`. `rev` ≠ `rascunho_rev` → 409 `rascunho_desatualizado`, com `{rev, salvo_em, salvo_por_nome}` no `erro` para o editor avisar. Salva com `estrito=False`; se o rascunho normalizado for **igual** ao publicado, grava `rascunho = null`. Responde `{rev, salvo_em, problemas, rascunho: {perguntas, tema, finais}}`, já normalizado (o editor aplica ids gerados e o HTML limpo). 422 só para estrutural. |
| **`POST /formularios/{id}/publicar`** | Corpo `{rev}`. Rev diferente → 409 `rascunho_desatualizado`. Sem rascunho → 409 `sem_rascunho` ("Não há alterações para publicar."). Valida estrito: 422 com `campos`. Copia para as colunas publicadas, versão +1, `rascunho = null`, `rascunho_rev` +1, `publicado_*` e auditoria `formulario_publicado` `{versao, perguntas, finais}` (contagens). Responde o formulário completo. |
| **`DELETE /formularios/{id}/rascunho`** | `rascunho = null`, `rascunho_rev` +1. 204. Sem auditoria. |
| `POST /formularios/{id}/duplicar` | Copia o publicado e o rascunho (se houver). As imagens de conteúdo e de logo do original são copiadas para o novo formulário (o `copiar_para_formulario` de hoje faz isso para o logo) e as URLs no HTML são trocadas. |
| `POST /formularios/{id}/logo` | **Não apaga** a imagem do logo publicado ao trocar (o rascunho pode trocar o logo sem quebrar o que está no ar). A limpeza é feita no publicar e no descartar (§4.6). |

Permissões como hoje: ler com `formularios.ver`, editar e publicar com a permissão de edição de formulários.

### 4.3 Página pública

**`GET` (convite ou link)**, em `formulario.perguntas`:
- vai a lógica (`logica`);
- os itens `conteudo` levam `html` com `renderizar_html`;
- títulos e descrições levam `renderizar` (variáveis) e preservam `{{…}}`.

Também vão `prefixo_imagens` (§4.6) e `tem_finais` (bool, para o navegador saber se carrega o DOMPurify para o final).
Os `finais` **não** vão: quem decide é a API ao enviar.

**`POST …/responder`**:
1. Valida o tipo de cada valor enviado. Ignora ids desconhecidos e itens não respondíveis.
2. Calcula o caminho com os valores válidos.
3. Gera erro só para itens do caminho (valor inválido, ou obrigatória sem resposta).
4. Descarta valores fora do caminho.
5. `nota`, `tipo_nota` e `grupo` saem da nota principal, como hoje (ela está sempre no caminho, por §2.6).
6. Escolhe o final com `escolher_final` e grava `formulario_versao`.

A resposta mantém `titulo_final`, `texto_final`, `indicacao` e `depoimento`, e ganha:
- `final_id` (id ou null);
- `html_final` (html do final, com variáveis escapadas; null no final padrão);
- `botao_final` (`{texto, url}` ou null).

No final escolhido, `titulo_final` é o título dele e `texto_final` é `""`.

`max_selecoes` é validado na API ("Escolha no máximo N opções.").

O registro manual e a importação usam a mesma validação. Formulários sem lógica se comportam exatamente como hoje.

### 4.4 Quem lê perguntas: pular `conteudo`

Tratar `conteudo` como trata `quebra_pagina`, com um helper `respondivel(tipo)`, em:
- `resultados` e `respostas_csv` (`formularios/servico.py`);
- `_perguntas` e `_detalhe` (`respostas/servico.py`);
- `resumo` e `comentario_do_cliente` (`registro.py`);
- `dados/exportacao.py` (`respostas-perguntas.csv`);
- `perguntas_total`;
- o e-mail (`mensagens.py`: só usa a nota principal; conferir).

Títulos com `{{ID}}` saem com "…" nessas telas.

### 4.5 Auditoria

- Evento novo `formulario_publicado` em `core/auditoria.py`, com rótulo "Formulário publicado", gravidade info, e
  detalhe `{formulario: {id, nome}, versao, perguntas, finais}`.
- A web formata o detalhe (§5.7).

### 4.6 Imagens no conteúdo

- **`POST /formularios/{id}/imagens`** (multipart `arquivo`, PNG/JPEG ≤1 MB, mesma conferência de bytes do logo) grava
  `imagens` com `uso = 'conteudo_formulario'` e `formulario_id`, e responde `{url, largura, altura}`.
- Migração: o CHECK de `imagens.uso` aceita `'conteudo_formulario'`, e a regra `(uso='logo_formulario') =
  (formulario_id IS NOT NULL)` passa a valer para os dois usos de formulário.
- `prefixo_imagens` vai no GET do formulário e no payload público, para o DOMPurify do site aceitar só essas imagens.
- Limpeza:
  - Ao **publicar** e ao **descartar**, apagar as imagens `logo_formulario`/`conteudo_formulario` do formulário que não
    aparecem nem no publicado nem no rascunho (URL no `tema.logo_url` ou em algum `html`).
  - Excluir o formulário apaga as imagens dele (o cascade de hoje).
- O HTML pode usar imagens do **banco de imagens** da conta (`uso='banco'`), que estão no mesmo prefixo.
  - `banco.em_uso` também passa a olhar os formulários: uma imagem do banco citada no `html` publicado ou no rascunho de
    algum formulário não pode ser excluída (409 `imagem_em_uso`, mensagem citando o formulário).

### 4.7 Migração `0026_formularios_v2`

- Cria as colunas de §1.5 e `respostas.formulario_versao`.
- Ajusta o CHECK de `imagens` (§4.6).
- Converte `condicao` → `logica` nos formulários existentes, com conversor próprio dentro da migração (não importar
  código vivo).
- `versao` = 1 e `publicado_em = atualizado_em` nos existentes.
- `downgrade` simétrico. As colunas novas não podem quebrar a RLS (mesma política da tabela).

### 4.8 Modelos (`modelos.py`)

Os 6 de hoje passam para o formato novo (`logica`). Entram 3 modelos novos:

**`nps_segmentos`** — "NPS com acompanhamento e finais por segmento":
- Perguntas:
  - NPS;
  - detratores e neutros: "O que podemos melhorar?";
  - promotores: "O que você mais valoriza na {empresa}?";
  - opcional, só detratores: "Podemos entrar em contato para entender melhor?" (sim/não).
- Finais:
  - **Promotores** — "Obrigado por recomendar a {empresa}!", com HTML curto. **Sem botão**: um endereço fixo não serve
    para todas as contas. No editor, o campo de botão de todo final tem a dica "Ex.: o link para avaliarem a sua
    empresa no Google".
  - **Detratores** — "Obrigado pela sinceridade", com "Vamos usar o que você contou para melhorar.".

**`ces_atendimento`** — "Esforço do cliente (CES)":
- escala de 1 a 7: "A {empresa} facilitou a resolução da sua solicitação?";
- comentário para nota ≤3;
- csat do atendimento.

**`csat_motivo`** — "CSAT com motivo":
- CSAT;
- múltipla "O que mais pesou?", com opções diferentes para insatisfeitos e satisfeitos (duas perguntas, cada uma com
  `mostrar_se`);
- comentário opcional.

Vale para todos:
- `FORMULARIOS_INICIAIS` continua igual (contas novas recebem os mesmos 2).
- A migração 0002 importa `modelos.py` vivo: ela precisa continuar funcionando do zero (`test_migracao*`).

### 4.9 Ajuda (`conteudo.json`, tópico `formularios`)

Manter os ids das seções. `criar-um-formulario`, `perguntas-do-formulario` e `aparencia-do-formulario` estão nas
jornadas e nos testes.

Reescrever:
- `perguntas-do-formulario`: editor novo, adicionar, arrastar, desfazer e atalhos.
- `variaveis-condicoes-e-nota-principal`: título "Lógica: mostrar se, pular, finais e citações". Explica regras,
  operadores, finais por condição, citações `{{…}}` e por que a nota principal não tem condição.

Seções novas:
- `blocos-de-conteudo-e-html`: o que é permitido, o que é removido e o porquê (segurança), e as imagens.
- `rascunho-e-publicacao`: salva sozinho, Publicar, Descartar, o que muda para quem já recebeu o link.

Os rótulos citados precisam bater com §5. As regras da Ajuda são as de hoje: limites, sem `<`, sem `http` etc. Rodar
`test_ajuda.py`.

### 4.10 Testes da API (novos; os antigos continuam passando)

- `tests/test_logica_formularios.py`: lê `docs/casos-logica-5l.json`; todos os casos de `caminho`, `finais` e
  `legado`.
- `tests/test_formularios_v2.py`:
  - validação de cada regra de §2.6, com chaves e mensagens;
  - limites;
  - conversão do legado na entrada;
  - normalização e ids gerados (`r_`, `f_`);
  - `aleatorizar`, `exibicao`, `max_selecoes`, `placeholder`;
  - finais;
  - rascunho: 409 por rev; `problemas` sem bloquear; rascunho igual ao publicado vira null;
  - publicar: 422 com campos, 409 `sem_rascunho`, versão e auditoria;
  - descartar;
  - PATCH publica direto e preserva o rascunho;
  - duplicar copia o rascunho e as imagens;
  - permissões.
- `tests/test_html_seguro.py`:
  - lista permitida, e cada tipo de ataque removido: script, on*, javascript:, data:, style perigoso, iframe, svg, img
    externa, class/id;
  - `target`/`rel` forçados;
  - tamanho;
  - `renderizar_html` escapa as variáveis e mantém espaços e `{{…}}`.
- `tests/test_publico_logica.py`:
  - envio com pular e com escondidos: respostas fora do caminho descartadas; obrigatória só no caminho; erro de valor
    inválido fora do caminho ignorado;
  - final escolhido (`final_id`, `html_final`, `botao_final`);
  - final padrão sem lista;
  - `formulario_versao` gravada;
  - `max_selecoes`;
  - payload público com `html` renderizado e escapado;
  - conteúdo nunca vira resposta.
- Resultados, CSV, detalhe e exportação pulam `conteudo`, e o título com `{{…}}` sai com "…".
- Imagens: upload, prefixo, limpeza no publicar e no descartar, banco em uso por formulário.
- Migração 0026: upgrade e downgrade; o legado convertido.

Rode a suíte inteira no fim. As 40 falhas antigas de IA e Plataforma (5k) continuam; nenhuma falha nova.

---

## 5. Site (pasta `web/`)

### 5.1 Motor (`web/src/pesquisa/logica.ts`, sem dependências; vai na página pública)

Mesmas funções e semântica de §2:
- `norm`, `numeroDoTexto`, `grupoDaNota`;
- `avaliarCondicao`, `avaliarGrupo`;
- `caminho(itens, respostas)`, `escolherFinal(finais, itens, respostas)`;
- `converterCondicaoLegada`;
- `formatarResposta(item, valor)` e `citar(texto, itens, respostas)` (texto puro);
- `citarHtml(html, itens, respostas)` (escapado).

Também:
- `indicePrincipal`, `perguntaPrincipal`, `tipoPrincipal` e `faixa` continuam;
- `respostasParaEnvio` passa a usar o caminho;
- `paginasVisiveis` agrupa o caminho pelas quebras.

`descreverGrupo(grupo, itens)` gera a frase em português para o editor e para a prévia, por exemplo:
- "Mostrar se: NPS é detrator ou neutro";
- "Se 'É cliente?' é Não → ir para 'Comentário'".

Ela fica em módulo **do editor** (não precisa ir na página pública).

Tipos (`tipos.ts`):
- `TipoPergunta` ganha `'conteudo'`.
- Entram `Logica`, `Grupo`, `Condicao`, `Regra` e `Final`.
- `Pergunta` ganha `logica`, `html`, `modo`, `aleatorizar`, `exibicao`, `max_selecoes` e `placeholder`.
- `CondicaoPergunta` antiga continua como tipo de entrada (legado).
- `TelaFinal` ganha `final_id`, `html_final` e `botao_final`.

### 5.2 Página pública (`Pesquisa.vue`, `CampoPergunta.vue`, `BlocoHtml.vue`, `publico/*`)

**Navegação:**
- `uma_por_vez`: o próximo item é o seguinte no **caminho atual**.
- Um bloco `conteudo` é um passo próprio, com o botão "Continuar". Se for o último do caminho, mostra o botão de enviar
  (`tema.texto_botao`).
- O avanço automático das notas (320 ms) continua e respeita o caminho.
- `paginas`: as páginas são o caminho agrupado pelas quebras. Itens aparecem e somem ao vivo, e "Próxima" vai para a
  próxima página que tem itens no caminho.
- Progresso = posição no caminho / tamanho do caminho, recalculado.

**Citações:**
- `{{ID}}` em título e descrição saem com `citar`.
- No `BlocoHtml` (conteúdo), a ordem é `citarHtml`, depois `limparHtml`, depois `v-html`.

**Opções:**
- `aleatorizar` embaralha uma vez por montagem (estável na visita).
- `exibicao: 'lista'` usa um `<select>` acessível com rótulo.
- `max_selecoes` desabilita as outras opções ao atingir o limite e anuncia "Você pode escolher até N opções.".
- `placeholder` vai no campo de texto.

**`?nota=`:** preenche a nota principal e vai para o próximo item do caminho depois dela. Se houver perguntas
obrigatórias **antes** da nota principal, começa pela primeira delas, com a nota já marcada. Isso corrige a
inconsistência H9 do mapa: hoje elas são puladas sem validar.

**Final:**
- Se a resposta da API trouxer `html_final`, desenha o título, depois o `BlocoHtml` do `html_final` (com `citarHtml`
  das respostas enviadas), depois `botao_final` (link que abre em nova aba, com `rel="noopener noreferrer"`).
- Senão, mostra `texto_final` como hoje.
- Indicação e depoimento continuam abaixo.

**Prévia** (`previa=true`, sem API):
- O final é escolhido com `escolherFinal(finais, …)`, usando a prop nova `finais`. `null` = final padrão do tema.
- Prop nova **`focoId`**: abre a prévia direto nesse item.
  - Se o item não estiver no caminho com as respostas da prévia, mostra-o assim mesmo, com a faixa "Na pesquisa, este
    item só aparece quando: …" (frase de `descreverGrupo`, recebida pronta numa prop `motivoFoco` para não levar o
    descritor para a página pública).
- Botão "Reiniciar prévia".

**Acessibilidade:** o foco vai para o título a cada passo, e o anúncio `aria-live` diz "Pergunta N de M". O bloco de
conteúdo é anunciado pelo início do texto.

**Peso:** o DOMPurify é carregado sob demanda (§3.3). A página pública não pode importar nada do editor. Teste: build e
conferir que o chunk de `responder` não inclui código do editor nem TipTap.

### 5.3 Editor (`web/src/modulos/formularios/**`) — o centro desta etapa

#### Layout

- **Cabeçalho:**
  - nome do formulário (editável, salva na hora via PATCH `nome`);
  - situação: "Publicado · versão N · há X" e, quando há rascunho, a etiqueta "Alterações não publicadas";
  - estado do salvamento: "Salvando…" / "Rascunho salvo" / "Não foi possível salvar — tentar de novo";
  - botões "Desfazer" e "Refazer" (ícones com dica e atalho);
  - "Descartar alterações", só com rascunho e com confirmação;
  - **"Publicar"**, primário, desabilitado sem alterações. Com problemas, abre o painel de problemas em vez de publicar.
- **Abas:** "Perguntas" (padrão), "Aparência", "Compartilhar", "Respostas". A aba "Respostas" usa o **publicado**.
- **Aba Perguntas** com 3 colunas a partir de 1280 px:
  - **estrutura** à esquerda, ~300 px;
  - **edição** do item selecionado ao centro;
  - **prévia** à direita, ~400 px, com seletor "Celular" / "Computador". Na largura de celular, a prévia simula 390 px
    dentro de uma moldura.
- Entre 768 e 1279 px são 2 colunas (estrutura + edição), e a prévia abre por botão em painel lateral.
- Abaixo de 768 px: a lista; tocar num item abre a edição em tela cheia, com "Voltar"; a prévia abre por botão.

#### Estrutura (lista à esquerda)

- **Linha de cada item:**
  - alça de arrastar, ícone do tipo e número (só perguntas: P1, P2…);
  - título com as citações mostradas como "[resposta de P2]";
  - marcas: asterisco de obrigatória, ícone de lógica (com dica dizendo as regras) e ponto vermelho se tiver problema;
  - ações ao passar o mouse ou com foco: duplicar, excluir e "Mover para…".
- A quebra de página aparece como divisória "Página 2".
- Depois dos itens, a seção **"Finais"**:
  - "Final padrão" sempre;
  - os finais da lista, com a condição resumida;
  - "+ Adicionar final".
- **Adicionar:**
  - botão "+ Adicionar" no fim da lista, e um "+" que aparece entre dois itens;
  - os dois abrem um **menu com busca** agrupado em Notas (NPS, CSAT, Estrelas, Escala), Escolhas (Única, Múltipla,
    Sim ou não), Texto (Resposta curta, Comentário, E-mail, Telefone, Número), Data, Conteúdo (Texto e imagem, HTML) e
    Estrutura (Quebra de página);
  - cada opção tem descrição de uma linha;
  - setas e Enter navegam no menu;
  - o item novo entra **depois do selecionado** (ou no fim) e já fica selecionado, com o foco no título.
  - E-mail, Telefone e Número são `texto_curto` com o formato.
- **Arrastar e soltar:** com mouse **e toque** (SortableJS, ou equivalente leve, só no chunk do editor). Pelo teclado,
  Alt+↑/↓ no item focado.
- **Reordenar quebrando a lógica:** o item é movido mesmo assim, o problema aparece no item e no painel de problemas,
  e um aviso diz "A lógica de N itens precisa de ajuste" com "Ver".
- **Excluir item que é fonte de lógica:** a confirmação diz quais itens e finais usam esse item, e oferece "Excluir e
  remover as condições que usam este item".
- **Duplicar:** a cópia ganha ids novos; a lógica da cópia aponta para as mesmas fontes; as regras de `pular` da cópia
  vêm vazias (evita saltos duplicados).
- **Renomear uma opção** de escolha atualiza automaticamente as condições que usam a opção. **Excluir uma opção usada**
  avisa e remove a opção das condições, e a condição que ficar vazia é removida.

#### Edição de pergunta (centro)

- **Título:** campo com contador e um menu "Inserir":
  - Variáveis: Nome da empresa, Nome do contato, Assunto, Referência;
  - Respostas anteriores: lista das perguntas anteriores, que insere `{{ID}}`.
  - Abaixo do campo, a linha "Assim aparece:" mostra o título com as variáveis de exemplo e as citações como
    "[resposta de P2]".
- **Descrição:** área de texto com o mesmo "Inserir".
- **Configurações do tipo:**
  - rótulos;
  - faixa da escala;
  - opções (editor de hoje, mais "Embaralhar a ordem" e "Mostrar como lista suspensa" na única, e "Máximo de opções" na
    múltipla);
  - formato;
  - texto de exemplo (placeholder).
  - Trocar o tipo da pergunta pelo menu "Tipo" mantém título, descrição e lógica compatível, e avisa quando a lógica
    deixa de valer.
- **"Obrigatória":** interruptor.
- **Seção "Lógica"** (recolhível, aberta se o item tiver lógica):
  - **"Quando mostrar":** "Sempre" ou "Só se…". O construtor monta frases em linhas:
    `[pergunta anterior ▾] [operador ▾] [valor]`. O valor muda conforme o tipo: número, faixa "entre", chips de grupos
    (Detratores 0–6 …), seleção de opções com várias, sim/não, texto ou data.
    - Acima das linhas, "Mostrar quando **todas** / **qualquer uma** destas condições valerem".
    - "+ Condição", e remover a linha.
    - Os operadores aparecem em português: "é", "não é", "é menor que", "é no máximo", "é maior que", "é pelo menos",
      "está entre", "está no grupo", "foi respondida", "não foi respondida", "é uma de", "não é nenhuma de",
      "inclui alguma de", "inclui todas", "não inclui nenhuma de", "contém", "não contém", "começa com",
      "termina com", "antes de", "depois de".
  - **"Depois desta pergunta"** (só perguntas que podem pular): lista de regras
    "Se [condições] → Ir para [item posterior ▾ | Fim da pesquisa]", com "+ Regra" e reordenação. Rodapé: "Senão:
    segue para a próxima".
  - Na **nota principal** a seção mostra "A nota principal sempre aparece" e oferece os atalhos:
    - **"Criar acompanhamento por segmento":** insere logo depois as perguntas de comentário com `mostrar_se` por
      grupo, nos textos do modelo `nps_segmentos`, ou no equivalente de CSAT;
    - **"Criar finais por segmento":** cria os finais Promotores/Detratores (ou Satisfeitos/Insatisfeitos).
- Os erros do item aparecem no topo da edição e em cada linha da lógica.

#### Edição de conteúdo

- Nome interno opcional.
- Abas **"Visual"** e **"HTML"**.
  - **Visual:** **TipTap** (`@tiptap/vue-3` + StarterKit + Link + Image + TextAlign + Placeholder; só no chunk do
    editor). Barra com negrito, itálico, sublinhado, título (H2/H3), listas, citação, link, alinhamento, linha
    horizontal, imagem e desfazer.
  - **Imagem:** "Enviar imagem" (upload §4.6) ou, para quem tem acesso ao banco de imagens, "Escolher do banco"
    (reaproveitar o componente do banco).
  - **HTML:** área de código monoespaçada com quebra de linha. Embaixo, uma prévia **já limpa**, e o aviso do que foi
    removido (§3.3).
    - Ao voltar para Visual com HTML que o TipTap não representa (ex.: tabela), avisar "Parte deste HTML só pode ser
      editada na aba HTML" e **manter** o HTML: o bloco fica em `modo: 'html'` e a aba Visual fica desabilitada com
      essa explicação. Não perder conteúdo.
- Nota fixa: "Por segurança, scripts, estilos, formulários e conteúdo de outros sites são removidos. Imagens: envie aqui
  ou use o banco de imagens."
- Inserir variáveis e citações no texto, pelo menu "Inserir".
- Lógica: só "Quando mostrar".

#### Edição de final

- Campos:
  - nome interno;
  - título (com "Inserir");
  - texto: o mesmo editor do conteúdo (Visual/HTML);
  - botão opcional (texto + endereço https, conferido no campo);
  - "Mostrar este final quando…": o mesmo construtor; a fonte pode ser qualquer pergunta.
- A ordem importa ("vale o primeiro que combinar"): setas ou arrastar dentro da seção Finais. Aviso quando um final
  sem condição não é o último ("Os finais abaixo deste nunca aparecem").
- **Final padrão:** edita `tema.titulo_final` e `tema.texto_final` (texto puro, como hoje). Esses dois campos **saem da
  aba Aparência**.

#### Rascunho, salvamento e conflito

- **Documento de trabalho:**
  - ao abrir, é o `rascunho`, se houver, ou uma cópia do publicado;
  - cada mudança grava com debounce de ~1,2 s (`PUT …/rascunho`), em fila (nunca dois PUT ao mesmo tempo);
  - a resposta atualiza `rev` e aplica o normalizado (ids gerados, HTML limpo) **sem mexer no cursor** do campo em
    edição (merge por id);
  - `problemas` vão para o painel.
- **409 `rascunho_desatualizado`:** faixa "Este formulário foi alterado em outra aba ou por outra pessoa (por NOME, às
  HH:MM)" com "Recarregar", que carrega o servidor e perde as mudanças locais (com confirmação).
- **Sem rede:** "Não foi possível salvar" com "Tentar de novo". Ao fechar ou sair com mudança não salva, a confirmação
  de hoje.
- **Publicar:**
  1. salva o rascunho pendente;
  2. chama `publicar`;
  3. sucesso: aviso "Publicado. Quem abrir o link agora vê esta versão.", documento = publicado, sem rascunho;
  4. 422: abre o **painel de problemas**, com a lista agrupada por item e clicável (seleciona o item e foca o campo).
- **Descartar:** confirmação, depois `DELETE …/rascunho`, e o documento volta ao publicado.
- **Desfazer/refazer:**
  - pilha de instantâneos do documento de trabalho (até 100);
  - digitação agrupada (entradas a menos de ~800 ms no mesmo campo viram um passo);
  - atalhos Ctrl/Cmd+Z e Ctrl/Cmd+Shift+Z (e Ctrl+Y);
  - desfazer também grava o rascunho.
  - Dentro do TipTap, o desfazer do próprio TipTap vale enquanto o foco estiver nele.
- **Atalhos:**
  - Ctrl/Cmd+S salva o rascunho na hora;
  - Ctrl/Cmd+D duplica o item;
  - Alt+↑/↓ move;
  - "/" (fora de campo de texto) abre o menu de adicionar;
  - "?" abre a lista de atalhos;
  - Delete na lista exclui (com confirmação).
- **Painel "Problemas":** botão no cabeçalho com o número de problemas, mais os problemas que o próprio site calcula
  (`validacaoFormulario.ts`, com as mesmas regras de §2.6) para aparecer antes do PUT voltar.
- **Prévia (à direita):**
  - mostra o documento de trabalho;
  - segue o item selecionado (`focoId` + `motivoFoco`);
  - mostra o final escolhido pela lógica ao terminar;
  - "Reiniciar";
  - seletor Celular/Computador.

#### Aparência

Como hoje, menos o final padrão (que foi para Finais). Continuam: cor, logo, modo, abertura e texto do botão. Tudo
entra no rascunho. O upload do logo não muda o publicado (§4.2).

#### Novo formulário

- Galeria de modelos (`ModalNovoFormulario`) com os 9 modelos, em cartões com prévia.
- Etiqueta "Com lógica" nos modelos que têm `logica` ou `finais`.

### 5.4 Lista de formulários

Etiqueta "Alterações não publicadas" quando `tem_rascunho`. "N perguntas" conta só perguntas.

### 5.5 Respostas e resultados

- A aba Respostas e o detalhe da resposta ignoram `conteudo`.
- Títulos com `{{…}}` aparecem com "…", vindos da API.
- Na tela da resposta, dizer qual final a pessoa viu? Não nesta etapa.

### 5.6 CSP

`render.yaml` (§3.4) e README do site.

### 5.7 Auditoria

Detalhe legível de `formulario_publicado` em `web/src/modulos/auditoria/detalhes.ts`: "Versão N · X perguntas ·
Y finais".

### 5.8 Testes do site (vitest; os antigos continuam passando)

- `tests/formulariosLogica.test.ts` lê `../docs/casos-logica-5l.json`, por `fs` e caminho relativo ao arquivo do teste,
  e roda todos os casos (`caminho`, `finais`, `legado`, `citacoes`) com o motor do site.
- `tests/pesquisaLogicaV2.test.ts`, com a página pública:
  - uma por vez com pular, escondidos aparecendo e sumindo, e conteúdo como passo;
  - páginas com itens ao vivo;
  - progresso;
  - `?nota=` com e sem obrigatórias antes;
  - final com `html_final` e botão;
  - `aleatorizar` estável, lista suspensa e `max_selecoes`;
  - citações em título e em HTML escapado;
  - envio só com o caminho.
- `tests/htmlSeguro.test.ts`: `limparHtml` com cada ataque (§3.1), imagem de fora removida, `target`/`rel`,
  `text-align` mantido e cor removida, e o varredor de `v-html` (§3.3).
- `tests/editorFormularioV2.test.ts`, com `apiFalsa`:
  - adicionar pelo menu (busca e teclado);
  - mover, arrastar e Alt+setas; duplicar; excluir com dependências;
  - renomear e excluir opção atualiza condições;
  - construtor de lógica (operadores por tipo, todas/qualquer);
  - regras de pular; atalhos da nota principal;
  - finais (ordem e aviso);
  - autosave (debounce, fila, aplica normalizado, 409 com faixa);
  - publicar (sucesso, e 422 abre problemas com clique que seleciona o item);
  - descartar;
  - desfazer/refazer e atalhos;
  - prévia seguindo o item.
- Ajustar `pesquisaLogica.test.ts`, `editorFormulario.test.ts` e os demais que pinam a semântica antiga só onde a
  mudança é proposital. Listar no relatório.

**Teste integrado** (Playwright em `/opt/pw-browsers/chromium`, contra a API local com banco de teste, como nas etapas
anteriores):
1. criar pelo modelo `nps_segmentos`;
2. editar no editor: adicionar conteúdo com imagem, lógica e um final com botão; arrastar; desfazer;
3. ver a prévia em celular e computador;
4. publicar;
5. responder pelo link público como promotor e como detrator: caminhos e finais certos; CSP aplicada com um servidor
   estático com o cabeçalho de §3.4.

Fotos em `/home/claude/capturas/5l/`: editor em 1280 claro e escuro, editor em 390, construtor de lógica, painel de
problemas, menu de adicionar, bloco HTML com aviso de remoção, pesquisa pública com conteúdo e final.

---

## 6. Divisão do trabalho

**Agente API**
- Tudo em `api/` (inclui `conteudo.json` da Ajuda e `requirements.txt`).
- Não mexe em `web/`, `render.yaml` nem nos dois arquivos de `docs/` deste contrato. Pode criar
  `docs/api-etapa-5l-notas-api.md` com decisões e desvios.

**Agente site**
- Tudo em `web/`, mais `render.yaml` (só os cabeçalhos de CSP) e o README do site.
- Não mexe em `api/`. Pode criar `docs/api-etapa-5l-notas-web.md`.

**Regras para os dois**
- Quem descobrir um caso que falta no JSON compartilhado **não edita o arquivo**: descreve o caso no relatório.
- Não fazer commit. Não fazer push.
- O repositório tem mudanças de outras pessoas: não reverter nada que não seja seu.
- Português do Brasil em textos e mensagens, no mesmo tom do produto (frases curtas, sem jargão).
- Seguir o estilo do código vizinho.

**Relatório final de cada agente**
- O que foi feito, por seção deste contrato.
- Desvios e por quê.
- Testes rodados e resultado (contagem).
- Testes antigos alterados (e por quê).
- Casos que faltam no JSON.
- Pendências.

---

## 7. Fora desta etapa

- Matriz, ranking e upload de arquivo para quem responde.
- Formulário gerado por IA.
- Mapa visual do fluxo.
- Condições por dados do contato, da empresa ou de parâmetros do link.
- Variáveis de cálculo e pontuação.
- Idiomas.
- Respostas parciais.
- Histórico de versões navegável: a coluna `formulario_versao` já fica pronta.
- CSS próprio (decisão do Marcelo).
- Script de terceiros (nunca).

## 8. Critérios de pronto

1. Todos os casos de `docs/casos-logica-5l.json` passam nos dois motores.
2. Formulário criado em versões anteriores abre, edita, publica e recebe respostas como antes, com a lógica antiga
   convertida.
3. Editor: criar o modelo `nps_segmentos` e montar, sem tocar em código, uma pesquisa com:
   - conteúdo com imagem;
   - pergunta que só aparece para detratores;
   - pular para o fim se "não é cliente";
   - final para promotores com botão;
   - citação da nota no título;

   e publicar.
4. A página pública com CSP responde nos dois modos, mostra os finais certos e não tem `v-html` fora do `BlocoHtml`.
5. Suítes da API e do site verdes (fora as 40 falhas antigas da 5k), build do site ok, Ajuda válida.

## 9. Mercado

Resumo da pesquisa de 06/10/2026, nas fontes oficiais:

| tema | Typeform | Tally | SurveyMonkey | Qualtrics | Jotform | Survicate |
|---|---|---|---|---|---|---|
| Lógica | "Ir para X quando Y", 1ª que vale, finais múltiplos | mostrar/esconder blocos e páginas, pular, E/OU | pular, mostrar/esconder, regras avançadas | display, skip, branch | mostrar/esconder, pular página, mudar a tela final | display e branch, árvore |
| Citações | `@` recall | `@` mentions | piping (pago) | piped text | campo no parágrafo | merge tags |
| HTML | só negrito, itálico e link | embed só por URL; CSS no Pro | — | HTML liberado por permissão do admin | HTML com `<script>` removido | — |

Nenhum dos líderes roda script do cliente por padrão. O desenho de §1 a §3 segue o melhor de cada um:
- regras em frases (Tally/Typeform);
- E/OU e "primeira que vale" (Typeform/Formbricks);
- finais por condição (Typeform/Survicate);
- HTML com lista permitida (Jotform), sem script.
