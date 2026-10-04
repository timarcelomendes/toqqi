# Toqqi · Etapa 5g (Plataforma › Parâmetros: preços, limites, IA, WhatsApp e teste editáveis pela equipe Toqqi)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, listas paginadas
`{itens,total,pagina,por_pagina}`, datas ISO 8601, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`). Rotas da
plataforma com `requer_superadmin` (e-mail em `SUPERADMIN_EMAILS`, confirmado), em modo sistema, como as de hoje. Módulos
novos: `core/parametros.py` (valores, padrões, validação, cache) e `modulos/plataforma/parametros.py` (serviço e rotas).

## 0. Decisões desta etapa
- **Marcelo (03/10):** o que hoje é fixo no código ou no Render passa a ser editado em **Plataforma › Parâmetros**, só por
  superadmin, com histórico (quem, quando, antes → depois); os quatro grupos são editáveis; **preço novo só para assinaturas
  novas** (e trocas de plano): quem já assina mantém o valor contratado até um reajuste com aviso prévio (fora desta etapa).
- **Decididas aqui (Marcelo pode mudar):**
  - O banco guarda só o que difere do padrão (`parametros`) e o histórico, imutável; tabela vazia = tudo como hoje. RLS só
    modo sistema, salvo a leitura dos limites de contatos, que o gatilho faz no contexto da conta (são números públicos).
  - Valor = banco > variável de ambiente (as que existem hoje) > código; salvar igual ao padrão apaga a linha (volta a seguir
    o padrão). Cache de 30 s por processo, limpo na hora por quem salva: nos outros processos (tarefas pela linha de comando,
    outro worker) a mudança vale em até **30 s**; o limite de contatos do banco, na hora.
  - Preços crescentes (Essencial < Profissional < Empresa: a adoção pelo valor da 5a não distingue planos de mesmo preço) e
    limites de contatos que não diminuem nessa ordem; nomes e chaves dos planos não mudam.
  - Limites, cotas, tetos e franquias valem **na hora para todas as contas**, inclusive quem assina (baixar não apaga nem
    devolve nada); por isso os Termos v6 dizem que o preço é o da contratação e que limites podem mudar, com aviso.
  - Confirmação com o número de contas atingidas: preço; baixar contatos, cota, teto ou franquia; mais análises num nível;
    ligar a exclusão. Modelo ou esforço novo: chamada curta à OpenAI antes de salvar (recusou → 422, não respondeu → 503;
    nada salvo); sem IA na plataforma, salva sem testar.
  - Assinar e trocar de plano mandam o preço que a tela mostrou; mudou → 409 `preco_mudou` (ninguém paga o que não viu).
  - Site da raiz: o HTML fica com os padrões do código (buscadores e quem não roda JavaScript) e `GET /publico/planos` troca
    os números depois de abrir; mudança duradoura pede também o padrão no código e o HTML.
  - Ficam fora: `OPENAI_API_KEY`, `IA_PROVEDOR`, `IA_MODELO`/`IA_ESFORCO` (análise de cada resposta), `SUPERADMIN_EMAILS`, o
    excedente do WhatsApp (R$ 1,50) e as regras da exclusão (90 e 7 dias; 20 e 100 por dia).
- **Revisão (03/10; detalhes no §12):**
  - Teste em andamento fica no plano com que começou, mesmo que `teste.plano` mude ("+N dias", conferência diária e virada
    do teste não mexem nele); só quem **perde a assinatura** sem nunca ter pago volta ao `teste.plano` de hoje (a regra da
    5a), na hora em que perde.
  - Cache dos parâmetros por um pool próprio e pequeno (nunca o principal), uma leitura por vez, 5 s de espera depois de
    uma falha (valem os últimos valores) e lido ao subir a API; sem nenhuma leitura boa, erro (nunca o padrão em silêncio).
  - `preco` **obrigatório** em `POST /assinatura` e `PUT /assinatura/plano` (sem ele não há `preco_mudou`).
  - Linha fora do formato (só à mão): preço é erro (último valor bom ou falha), nunca o padrão; banco e Python aceitam as
    mesmas linhas de limite de contatos; o PUT do grupo apaga as linhas ruins dele.
  - `parametros` guarda só chave e valor: quem alterou e quando ficam só no histórico (a conta lê os limites e não deve
    ver o e-mail do superadmin).
  - Adoção de assinatura achada no Asaas pelo valor **e** pela descrição do plano.
  - Análises por nível em ordem (Rápido ≤ Equilibrado ≤ Mais detalhado); a cota insuficiente sugere o nível mais barato
    que cabe no que resta.

## 1. Banco (migração `0016_parametros`, depois da `0015_dados_conta`)
- `parametros` (sem conta): `chave text PRIMARY KEY` (CHECK `^(planos|ia|whatsapp|teste)\.[a-z_]+(\.[a-z_]+)?$`) e `valor
  jsonb NOT NULL` (texto "149.00", inteiro, `null` = sem limite, ou texto). Só isso (revisão: quem alterou e quando ficam
  no histórico).
- `parametros_historico`: `id bigserial PRIMARY KEY`, `criado_em timestamptz NOT NULL DEFAULT now()`, `grupo text NOT NULL`
  (CHECK 'planos' | 'ia' | 'whatsapp' | 'teste'), `por text NOT NULL` (e-mail), `mudancas jsonb NOT NULL` (CHECK array:
  `[{chave, de, para}]`, valores efetivos). Índice `(grupo, id DESC)`. Sem FK: sobrevive à exclusão de quem alterou.
- RLS ENABLE + FORCE nas duas, política `sistema` FOR ALL USING e WITH CHECK (`app_sistema()`); em `parametros`, também
  `ler_limites` FOR SELECT USING (`chave LIKE 'planos.%.contatos'`). Papel da aplicação: SELECT, INSERT, UPDATE, DELETE em
  `parametros`; SELECT e INSERT em `parametros_historico`, com `REVOKE UPDATE, DELETE` (como `registros_acesso` na 5f).
- `limite_contatos(p_plano text, p_situacao text)` (0002) passa de IMMUTABLE a **STABLE** (lê tabela) e devolve: cortesia →
  NULL; com a linha `'planos.' || p_plano || '.contatos'` válida como o Python a aceita (`jsonb_typeof` `null` = sem limite,
  ou `number` escrito só com dígitos, de 1 a 1.000.000) → o valor dela; sem ela (ou com ela fora disso: texto, booleano,
  fração, 0, negativo), os padrões de hoje (essencial 300, profissional 1500, outro NULL). `contatos_checar_limite` (0008) não muda: a trava 740221
  segue antes da leitura, que em conta passa pela `ler_limites`. Downgrade: a função antiga volta e as tabelas saem.

## 2. Parâmetros
| Chave (p = essencial, profissional, empresa; n = rapido, equilibrado, detalhado) | Padrão: onde está hoje | Validação |
|---|---|---|
| `planos.{p}.preco` | 149.00 · 349.00 · 799.00: `core/planos.PLANOS` | até 2 casas, de 5,00 a 99.999,99; Essencial < Profissional < Empresa |
| `planos.{p}.contatos` | 300 · 1500 · null: `PLANOS` e a função `limite_contatos` | inteiro de 1 a 1.000.000 ou null (sem limite); Essencial ≤ Profissional ≤ Empresa (null é o maior) |
| `ia.cota.{p}` · `ia.cota.cortesia` | 100 · 500 · 2000: `ia/cota.COTA_PLANO` · `IA_COTA_CORTESIA` (500) | inteiro de 0 a 100.000 |
| `ia.modelo.{n}` | `IA_MODELO_RAPIDO` (gpt-5-nano), `IA_MODELO_EQUILIBRADO` ou `IA_ASSISTENTE_MODELO` (gpt-5-mini), `IA_MODELO_DETALHADO` (gpt-5), pela regra de `ia_texto.modelo_do_nivel` | `^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$` (espaços das pontas saem) |
| `ia.esforco.{n}` | `IA_ESFORCO_RAPIDO` (minimal), `IA_ESFORCO_EQUILIBRADO` ou `IA_ASSISTENTE_ESFORCO` (low), `IA_ESFORCO_DETALHADO` (low) | "" (não manda `reasoning`), none, minimal, low, medium, high ou xhigh |
| `ia.analises.{n}` | 1 · 1 · 2: `ia_texto.MODELOS` | inteiro de 1 a 10; Rápido ≤ Equilibrado ≤ Mais detalhado |
| `ia.teto.{p}` · `.cortesia` · `.teste` | 1000 · 5000 · 20000 · 5000 · 1000: `ia/regras.py` | inteiro de 0 a 1.000.000 |
| `whatsapp.franquia.{p}` · `.cortesia` · `.teste` | 40 · 90 · 200 · 200 · 20: `whatsapp/franquia.LIMITES` | inteiro de 0 a 100.000 |
| `teste.dias` | 14: `acesso.servico.DIAS_TESTE` | inteiro de 1 a 90 |
| `teste.plano` | profissional: DEFAULT de `contas.plano` (0001), `assinatura.servico.PLANO_DO_TESTE`, `cota.PLANO_PADRAO` | um dos 3 planos |
| `teste.exclusao_automatica` | `EXCLUSAO_AUTOMATICA` (código simular; render.yaml ligada; outro texto vale simular, com o aviso no log) | ligada ou simular |

- Grupo = primeiro pedaço da chave (`teste` = "Teste e cortesia"). Todas as chaves do grupo são obrigatórias. Inteiro: número
  JSON inteiro (texto e booleano recusados); dinheiro: texto com ponto ("149.9") ou número, até 2 casas, devolvido "149.90".
- Mensagens no campo, ex.: "Use um valor entre R$ 5,00 e R$ 99.999,99." e "O preço do Profissional precisa ser maior que o do
  Essencial." (limites: "O limite do Empresa não pode ser menor que o do Profissional.", "Use um número inteiro de 0 a 100.000.";
  níveis: "O Mais detalhado não pode gastar menos análises que o Equilibrado.", no campo do nível mais caro).

## 3. Leitura (`core/parametros.py`) e quem passa a ler
- `CAMPOS` (chave → grupo, tipo, padrão, limites), `valor(chave)`, `grupo(nome) -> dict`, `padrao(chave)` (de `config()`, como
  hoje: variável > código), `origem(chave)` ("banco" | "ambiente" | "codigo"; ambiente = variável definida, por
  `config().model_fields_set`), `validar(grupo, valores) -> dict` (422 `dados_invalidos`, `campos` pela chave), `invalidar()`.
- Cache: as linhas de `parametros` são lidas pelo engine próprio do cache (`db.engine_parametros`: 1 conexão + 1, 3 s de
  espera por ela e para conectar, `statement_timeout` de 3 s; mesma URL do modo sistema e nunca o pool principal nem a
  transação de quem chamou) e valem 30 s (`CACHE_SEGUNDOS`, relógio monotônico). Uma leitura por vez: vencido, uma thread
  lê e as outras seguem com os últimos valores; sem valor nenhum, esperam essa leitura. A API lê ao subir (`aquecer`).
  Falha ao ler: os últimos valores (log de aviso) e nova tentativa só depois de 5 s (`ESPERA_FALHA`); sem nenhuma leitura
  boa, sobe `ParametrosIndisponiveis` (cair no padrão em silêncio cobraria o preço errado), também durante a espera.
  `invalidar()` vale também para a leitura em andamento (ela não conta como nova). Linha fora do formato: chave
  desconhecida ignorada; valor fora do tipo vale o padrão (log de erro), menos o preço (último valor bom lido; sem leitura
  anterior, `ParametroInvalido` ao pedir aquela chave). Tela, prévia e PUT leem o banco direto (a linha ruim aparece como o
  padrão).

| Onde | Hoje | Passa a |
|---|---|---|
| `core/planos.py` | `PRECOS`, `LIMITE_CONTATOS`, `planos_json`, `limite_contatos`, `limite_da_conta` | `PLANOS` só com (chave, nome); `preco(plano)`; `planos_json()` do cache; `limite_contatos(s, plano, situacao)` e `limite_da_conta` perguntam ao banco (`select limite_contatos(...)`, a regra do gatilho) |
| `assinatura/servico.py` | `PRECOS` em `_criar_assinatura` e `trocar_plano`; `plano_do_valor`; `planos_json` em `estado`; `_conferir_limite`; `PLANO_DO_TESTE` em `recalcular` | preço atual; limite do banco; `teste.plano` |
| `assinatura/conferencia.py` | `_adotar`/`conciliar` por `plano_do_valor`; `_conferir_ativa`/`_realinhar` comparam o Asaas com `assinaturas.valor` | adoção pelo preço atual (viva no Asaas, desconhecida aqui e com preço antigo → removida lá como `nao_adotada`, como hoje um valor fora dos planos); a conferência já usa o contratado: só testes |
| `assinatura/rotas.py` · `importacao/servico.py` | `GET /assinatura/planos` · `limite_da_conta` | do cache · do banco |
| `ia/cota.py` | `COTA_PLANO`, `IA_COTA_CORTESIA`, `PLANO_PADRAO` | `ia.cota.*`; plano desconhecido → o de `teste.plano` |
| `core/ia_texto.py` | `MODELOS` (`analises` e "Gasta 1 análise da cota." na descrição), `modelo_do_nivel`, `analises_do_nivel`, `opcoes_json` | `ia.modelo.*`, `ia.esforco.*`, `ia.analises.*`; a frase do custo é montada ("Gasta 1 análise da cota." / "Gasta 3 análises da cota.") |
| `ia/regras.py` · `whatsapp/franquia.py` | `TETO_PLANO`, `TETO_CORTESIA`, `TETO_TESTE` · `LIMITES` | `ia.teto.*` · `whatsapp.franquia.*` |
| `acesso/servico.cadastrar` · `plataforma/servico.criar_conta` | `DIAS_TESTE`; `plano` pelo DEFAULT da coluna | `teste.dias`; `plano = teste.plano` explícito (também na cortesia) |
| `plataforma/esquemas.EstenderTesteIn` · `assinatura/exclusao._modo` | `dias` = 14 · `EXCLUSAO_AUTOMATICA` | sem `dias` → `teste.dias` · `teste.exclusao_automatica` (aviso de valor estranho só sem linha no banco) |

- Logs que mandam conferir `IA_MODELO_*`/`IA_ASSISTENTE_MODELO` (`ia/pareceres.py`, `assistente/servico.py`) citam "os modelos
  em Plataforma › Parâmetros"; `config.py`, `render.yaml` e o README da API: a variável é só o padrão, a tela vale mais.

## 4. Efeitos no que já está rodando
- **Preço:** vale em `POST /assinatura` e `PUT /assinatura/plano` (vai ao Asaas e a `assinaturas.valor`; na troca, também às
  faturas pendentes). Assinatura existente não muda: `assinaturas.valor` já é o contratado (5a), a conferência diária compara
  o Asaas com ele (`valor_realinhado` volta ao contratado, nunca ao preço atual), trocar para o mesmo plano não faz nada e
  salvar um preço não chama o Asaas. Os dois exigem `preco` (o que a tela mostrou; sem ele ou null → 422 `dados_invalidos`
  no campo `preco`, "Recarregue a página para ver o preço atual do plano."): diferente do atual → 409 `preco_mudou` ("O
  preço do plano Profissional mudou para R$ 399,00. Confira e confirme de novo.") antes de chamar o Asaas. A assinatura
  viva no Asaas e desconhecida aqui só é adotada com o valor (preço atual) e a descrição ("Toqqi – plano Profissional") do
  mesmo plano; senão é removida lá (`nao_adotada` na conferência, `duplicada` ao assinar).
- **Limite de contatos:** na hora (banco e API); quem fica acima mantém os contatos e recebe o 402 `limite_do_plano` ao
  cadastrar, importar ou reativar (etapa 2); trocar para um plano que não comporta os ativos segue 422.
- **Cotas, tetos e franquias:** na próxima reserva; o uso do mês não volta: abaixo do já usado, sem saldo até o mês virar (IA
  `cota_esgotada`; teto: temas por palavras-chave; WhatsApp: e-mail ou excedente); a primeira reserva sem franquia manda uma
  vez o aviso de "acabou" (`_avisar` também nesse ramo, pelo `avisou_100`); subir libera na hora. Análises por nível: na
  próxima reserva (a devolução segue `Reserva.quantidade`); modelo e esforço: na próxima chamada.
- **Teste:** `teste.dias` e `teste.plano` valem para contas novas (cadastro e Plataforma) e o "+N dias" (`teste.dias`);
  testes em andamento ficam como estão, também no plano (o "+N dias", a conferência e a virada do teste recalculam a conta
  sem trocar o plano); quem perde a assinatura sem nunca ter pago (cancelou, removida ou não achada no Asaas, descarte do
  sandbox) volta ao `teste.plano` atual, na hora. **Exclusão:** na próxima rodada (9h).

## 5. Rotas
### 5.1 Plataforma (`requer_superadmin`)
- `GET /plataforma/parametros` → `{grupos: [{grupo, rotulo, versao, alterado_em, alterado_por, valores: {chave: valor},
  padroes: {chave: valor}, origens: {chave: "banco" | "ambiente" | "codigo"}}]}`, nesta ordem: `planos` "Planos", `ia` "IA",
  `whatsapp` "WhatsApp automático", `teste` "Teste e cortesia". `versao` = id da última linha do histórico do grupo (0 sem
  nenhuma); `alterado_em`/`alterado_por` vêm dela (null sem nenhuma).
- `POST /plataforma/parametros/{grupo}/previa` `{valores}` → `{mudancas: [{chave, de, para}], precisa_confirmar, impactos:
  [{chave, contas, exemplos: [{id, nome, uso}]}]}` (validação e 422 do PUT; não testa modelo; `exemplos`: até 5, de maior
  uso). Impacto de cada valor que diminui: contatos → contas do plano (não cortesia) com mais ativos que o novo limite (`uso`
  = ativos); cota, teto e franquia → contas a que o valor se aplica (regras de `cota.limite`, `regras.teto_mensal`,
  `franquia.plano_da_franquia`) que já usaram o novo valor ou mais no mês (`uso` = usado); `ia.analises.{n}` que aumenta →
  contas com `ia_modelo` = n (equilibrado: também desconhecido; `uso` 0). `precisa_confirmar`: preço mudou; limite de
  contatos, cota, teto ou franquia diminuiu; análises aumentaram; ou `teste.exclusao_automatica` foi a ligada.
- `PUT /plataforma/parametros/{grupo}` `{versao, valores, confirmar: false}` → 200 com o grupo (como no GET) e, em `ia`,
  `testados: [n]`. Em ordem: (1) valida (422; chave que falta ou sobra → campo `valores`; outro grupo → 404); (2) nada mudou
  → 200 sem gravar; (3) `precisa_confirmar` sem `confirmar: true` → 409 `confirmacao_necessaria` ("Confirme a mudança antes
  de salvar."); (4) em `ia`, o teste de cada nível com modelo ou esforço mudado (§5.3), fora da transação; (5) transação:
  `travar(s, "parametros")`; `versao` ≠ a atual → 409 `parametros_alterados` ("Outra pessoa mudou estes parâmetros enquanto
  você editava. Recarregue para ver os valores atuais."); apaga as linhas do grupo fora do formato (só gravadas à mão; também
  sem outra mudança, sem histórico); grava (igual ao padrão → apaga a linha; senão upsert da chave e do valor), o histórico
  (com o e-mail do superadmin) só com o que mudou e o global `parametros_alterados` "Parâmetros da plataforma alterados"
  (atencao) `{grupo, por, mudancas}`; `apos_commit` → `invalidar()`; log info com o grupo e as chaves.
- `GET /plataforma/parametros/historico?grupo=&pagina=&por_pagina=` → página de `{id, criado_em, grupo, por, mudancas}`, mais
  novos primeiro (`por_pagina` padrão 20, até 100; grupo desconhecido → 422 no campo `grupo`).
### 5.2 Público e assinatura
- `GET /publico/planos` (sem login; 60/min por IP; `Cache-Control: public, max-age=60`) → `{planos: [{chave, nome, preco,
  contatos, whatsapp, ia_cota, ia_teto}], teste: {dias, plano, whatsapp, ia_teto}, ia_analises: {rapido, equilibrado,
  detalhado}}` (`preco` no formato de `GET /assinatura/planos`). Sem modelos nem o modo da exclusão. `GET /assinatura/planos`
  e os `planos` de `GET /assinatura` trazem o preço e o limite atuais; `assinatura.valor` segue o contratado.
### 5.3 Teste do modelo
- `ia_texto.testar(modelo, esforco)`, pelo provedor da IA (`memoria` nos testes, programável): `POST /v1/responses` com
  `model`, `reasoning` (se houver esforço), `input` "Responda apenas: ok", `max_output_tokens` 16, `store: false`, 20 s;
  qualquer 2xx vale (mesmo `incomplete`). Um por nível, parando no primeiro erro: `configuracao` ou `definitiva` → 422 no campo
  `ia.modelo.{n}` ("A OpenAI recusou o modelo “gpt-x” com o esforço “low” (HTTP 400). Confira o nome e o esforço.");
  `transitoria` → 503 `teste_ia_indisponivel` ("Não deu para testar o modelo agora: a OpenAI não respondeu. Nada foi salvo;
  tente de novo em alguns minutos."). Sem `ia.disponivel()`, não testa (`testados: []`). Os tokens não entram em conta alguma.

## 6. Textos com números
- **Ajuda** (`conteudo.json`): marcas `{{chave}}` (do §2) trocadas pela API em `GET /ajuda` e no `buscar` do assistente
  (`ajuda.servico.conteudo()`, refeito quando os valores mudam): dinheiro "R$ 149,00", inteiro "1.500", null "sem limite";
  `validar` recusa marca desconhecida; `max-age` do `GET /ajuda` de 300 para 60. Seções:
  `primeiros-passos/criar-conta-e-entrar` e `assinatura/teste-gratis-e-situacoes-da-conta` (os "14 dias");
  `contatos/contato-ativo-e-limite-do-plano` e `assinatura/planos-precos-e-limite-de-contatos` (preços, limites e o "120 de
  300"); `integracoes/franquia-e-mensagens-extras-do-whatsapp` (franquias; o R$ 1,50 fica); `painel/resumo-da-ia-no-inicio`,
  `relatorios/parecer-da-ia`, `configuracoes/ia-modelo-estilo-e-passos`, `configuracoes/ia-cota-do-plano-e-privacidade` e
  `assistente/cota-de-analises-do-plano` (cotas, o "120 de 500" e as análises dos três níveis: "Rápido {{ia.analises.rapido}},
  Equilibrado … e Mais detalhado …"; "com só 1 análise restante" vira "com menos análises restantes do que o nível gasta";
  revisão: no lugar de "troque para o “Equilibrado”", "o nível mais econômico que cabe no que resta (o aviso diz qual)").
  Saem das `palavras` "14 dias", "300 contatos", "1500 contatos" e "2 análises" (o texto expandido já traz os números).
- **Site da raiz** (`web/index.html`): cada número vira `<span data-p="{chave do §2}">` com o padrão do código: preços dos
  cartões e da tabela (inteiro "149"; com centavos "149,90"), contatos (`data-p-maiuscula` onde está "Sem limite"), WhatsApp,
  perguntas ao ToqqiAI (cota), comentários lidos (teto), a nota do teste, a `data-nota-ia`, os seis "14 dias" e o "de 500" da
  conversa (cota do Profissional: a contagem recomeça nela; `data-restam` parado = cota − 3). `site.ts`, depois de desenhar,
  chama `publicoApi.planos()` (5 s): deu certo → troca todo `[data-p]` (função pura em `site/logica.ts` acha cada chave no
  corpo); falhou → fica o HTML. `og:description`: "… Teste grátis, sem cartão." (robô não roda script); 90/7 dias ficam.
- **App:** Cadastro (os três "14 dias"), `ModalNovaConta` ("N dias para conhecer o Toqqi.") e Plataforma › Contas ("+N dias",
  o diálogo e `dias` no pedido) leem `teste.dias` de `/publico/planos` (carregando ou com falha: 14); Assinatura, Integrações,
  Configurações › IA e ToqqiAI já leem da API. "Trocar de plano": o cartão do plano atual mostra o contratado quando difere
  ("Você paga R$ 349,00; hoje o plano custa R$ 399,00."); assinar e trocar mandam `preco` e, no 409, relêem e avisam.
- **Termos v6** (`VERSAO_DOCUMENTOS` = 6 em `acesso/termos.py` e `legal/versao.ts`; `VIGENTE_DESDE` = dia da entrega): "Os
  preços e limites vigentes são os que aparecem lá no momento da contratação." vira "O preço é o mostrado na contratação e
  só muda por reajuste, como abaixo. Limites e cotas dos planos podem mudar; se diminuírem, avisamos com antecedência
  razoável."; na IA, "usa 1 análise da cota … (2 no nível Mais detalhado …)" vira "usa análises da cota de IA do plano,
  conforme o nível de modelo escolhido em Configurações › IA (a tela mostra quantas)". Política: sem mudança.

## 7. Site: Plataforma › Parâmetros
- Rota `/plataforma/:aba(contas|parametros)?` (`meta.superadmin`): abas "Contas" (a tela de hoje) e "Parâmetros" com `Abas`,
  como a Auditoria; o menu segue com um item "Plataforma". API em `web/src/api/etapa5g.ts`; regras puras (rótulo e formato de
  cada chave, validação, linhas do diálogo e do histórico) em `modulos/plataforma/parametros.ts`.
- Quatro cartões, cada um um `form` com "Descartar" e "Salvar alterações" (desabilitados sem mudança) e "Alterado em
  03/10/2026 às 14:32 por marcelo@toqqi.com" (ou "Nunca alterado: valem os padrões."). Planos: um `fieldset` por plano
  (legenda = nome), "Preço por mês" (R$, "149,00") e "Contatos ativos" + caixa "Sem limite"; nota "O preço novo vale para
  assinaturas novas e trocas de plano. Quem já assina continua com o valor contratado." IA: "Análises por mês (cota do plano)"
  (Essencial, Profissional, Empresa, Cortesia); "Níveis de modelo" (Rápido, Equilibrado, Mais detalhado: "Modelo", "Esforço"
  em `Selecao`, vazio = "Sem raciocínio", e "Análises por uso"); "Teto de segurança por mês (análise dos comentários e passos
  das ações)" (os 3, Cortesia, Teste); nota "Ao salvar um modelo ou esforço novo, o Toqqi faz uma chamada curta à OpenAI para
  conferir." WhatsApp automático: mensagens por mês (os 3, Cortesia, Teste). Teste e cortesia: "Dias de teste", "Plano do
  teste" e "Exclusão automática das contas encerradas" (rádios "Ligada: avisa e exclui", "Simular: só conta e registra no
  log"); nota "Cota, teto e franquia da cortesia e do teste ficam em IA e WhatsApp automático."
- Cada campo: "Padrão: R$ 149,00" (`aria-describedby`), "Usar o padrão" quando difere e a validação do §2 (foco no 1º erro).
- Salvar → prévia; com `precisa_confirmar`, `Modal` alertdialog "Confirmar as mudanças em Planos?", uma linha por mudança com
  o impacto (ex.: "Contatos do Essencial: 300 → 250. 12 contas têm mais de 250 contatos ativos (Alfa, Beta…): ficam com eles,
  mas não cadastram, importam nem reativam contatos."; preço: "Vale para assinaturas novas e trocas de plano."; cota, teto,
  franquia: "3 contas já usaram 300 ou mais neste mês."; análises: "8 contas usam este nível."; exclusão: "Na próxima rodada
  (9h), contas encerradas há 90 dias passam a ser avisadas e excluídas de vez.") e, se algo diminui, "Vale na hora para todas
  as contas, inclusive quem já assina. Os Termos prometem aviso com antecedência razoável." "Confirmar e salvar" → PUT com
  `confirmar` ("Salvando…"; IA: "Testando o modelo…"); sucesso → "Parâmetros salvos." e cartão e histórico relidos; 409
  `parametros_alterados` → `Alerta` com "Recarregar"; 422 → nos campos; 503 → `Alerta`; o foco volta ao botão.
- "Histórico de alterações": lista (data e hora, grupo, quem e uma linha por mudança, ex. "Preço do Essencial: R$ 149,00 → R$
  159,00"), filtro "Grupo" ("Todos"), `Paginacao`, estado vazio. Tudo em 390 px sem rolagem lateral (campos em uma coluna),
  claro e escuro (tokens), pelo teclado, com `aria-live` no "Salvando…"/"Testando o modelo…".

## 8. Testes
- Banco: migração e downgrade (a função IMMUTABLE volta). RLS: em conta, `parametros` só mostra `planos.%.contatos` e nada
  grava nem muda; o histórico, nada; em sistema, tudo; UPDATE e DELETE no histórico recusados mesmo em sistema.
- Padrões e leitura: tabela vazia → cada chave do §2 com o valor de hoje (GET: `valores` = `padroes`) e `limite_contatos` do
  banco = o padrão do Python em cada plano e situação; variável (`IA_COTA_CORTESIA`, `IA_MODELO_DETALHADO`,
  `EXCLUSAO_AUTOMATICA`) vira o padrão (`origem` ambiente) e o banco vence; igual ao padrão apaga a linha; quem salvou vê na
  hora, linha gravada direto no banco só depois de 30 s (relógio falso); falha de leitura usa a última e, sem nenhuma, sobe.
- Contatos: Essencial com 2 → o 3º ativo dá 402 "até 2" ao cadastrar, importar e reativar (gatilho, em conta); Empresa com 5
  vale; null libera; cortesia nunca; a troca de plano usa o novo.
- Preço: o novo em `/assinatura/planos`, `/publico/planos` e no Asaas falso ao assinar e trocar; a assinatura antiga mantém
  `valor` e faturas; conferência com o Asaas no contratado → nada, com outro valor → volta ao contratado (`valor_realinhado`),
  nunca ao preço atual; mesmo plano não muda; `preco` diferente → 409 sem chamar o Asaas; adoção só pelo preço atual.
- IA: cotas; análises por nível (reserva, `mensagem_insuficiente`, descrição dos níveis; a devolução é o reservado mesmo
  depois da mudança); modelo e esforço no corpo (`memoria.corpos`); teste ok, recusa (422) e transitória (503) sem salvar, sem
  IA salva, só os níveis mudados. Tetos e franquias abaixo do uso → sem saldo no mês; o "acabou" sai uma vez. Teste: cadastro
  com 7 dias e Essencial (relógio fixo), Plataforma, "+N" sem `dias`, testes em andamento intactos, `recalcular`. Exclusão:
  banco `ligada` com a variável `simular` age; o contrário simula.
- Rotas: GET (forma, ordem, `versao`, `origens`); prévia (cada impacto, exemplos, `precisa_confirmar`); PUT (cada validação e
  a ordem dos planos, chave a mais ou a menos, nada mudou não grava, 409 de confirmação e depois 200, 409 de `versao`,
  histórico, evento global); histórico (ordem, filtro, páginas); 403 para quem não é superadmin (e com e-mail não confirmado);
  `/publico/planos` (forma, sem login, 429, `Cache-Control`, acompanha a mudança). Ajuda: marcas trocadas em `GET /ajuda` e
  no `buscar`, nenhuma `{{` sobrando, marca desconhecida recusada.
- Site (vitest): Parâmetros (4 seções com padrões e "Alterado em", salvar só com mudança, "Usar o padrão", validação,
  prévia e diálogo com os números, cancelar não salva, 409 com "Recarregar", 422, 503 e "Testando o modelo…", histórico com
  filtro e páginas, abas, só superadmin). Raiz: o teste dos números confere o padrão do código em cada `data-p`; fetch falso
  troca todos no formato certo ("Sem limite", "149,90", "1.500", N dias, a conversa); fetch que falha ou demora mantém o
  HTML. Cadastro, Nova conta e "+N dias" com `teste.dias`; cartão do plano atual com o contratado; 409 `preco_mudou`; v6.

## 12. Ajustes da revisão
Detalhes também na seção "Etapa 5g" de `api/README.md`.
1. **Teste em andamento mantém o plano.** `recalcular` (`assinatura/servico.py`) não põe mais no `teste.plano` toda conta sem
   assinatura ativa que nunca pagou (isso trocava o plano de testes em andamento no "+N dias", na conferência diária e na
   virada do teste). Volta ao `teste.plano` de hoje só quem **perde a assinatura** sem nunca ter pago, na mesma transação:
   `encerrar` (cancelar, removida ou 3 dias sem ser achada no Asaas; na cortesia o plano não muda) e
   `limpar_outro_ambiente` (descarte do sandbox) marcam a conta (`marcar_perda`, em `Session.info`) e o `recalcular`
   seguinte decide, como a 5a queria (§11 da 5a: "Quem nunca pagou volta ao plano Profissional (o do teste)", dito de quem
   fica sem assinatura). Depois disso a conta é um teste como outro: a próxima mudança de `teste.plano` não a atinge. Testes: "+N dias" e `conferir_conta`/`recalcular_pelas_datas` num teste em andamento depois
   de mudar `teste.plano`; cancelar sem pagar e a assinatura removida no Asaas → `teste.plano` atual (e não segue a
   mudança seguinte); `test_assinatura_recalcular` simula a perda com `encerrar` + `recalcular` na mesma transação.
2. **Cache dos parâmetros** (`core/parametros.py`, `core/db.py`, `main.py`). A leitura vencida pegava a trava global e uma
   segunda conexão do pool principal enquanto quem chamou já segurava uma dentro de `em_conta`: com o pool tomado por quem
   esperava, cada leitura esperava o `pool_timeout` (30 s), de novo a cada chamada depois de uma falha. Agora: engine
   próprio (`db.engine_parametros`: `pool_size` 1, `max_overflow` 1, `pool_timeout` 3 s, `connect_timeout` 3 s e
   `statement_timeout` 3 s na transação; segue `usar_url_app`); uma leitura por vez (as outras threads seguem com os
   últimos valores; sem valor nenhum, esperam até 10 s por ela); depois de uma falha, 5 s sem tentar de novo (últimos
   valores; sem nenhuma leitura boa, `ParametrosIndisponiveis`, também na espera); `invalidar()` durante uma leitura faz a
   próxima ler de novo; `aquecer()` no `lifespan` da API (falhou: só o aviso no log). Testes: com o pool principal todo
   preso por quem chama, a leitura vencida não espera conexão; uma leitura por vez; falha → últimos valores e uma tentativa
   só a cada 5 s, sem leitura boa sobe; `invalidar` no meio da leitura; o cache já lido ao subir a API.
3. **`preco` obrigatório** (`assinatura/esquemas.py`, `servico.conferir_preco`): `POST /assinatura` e `PUT
   /assinatura/plano` sem `preco` (ou com null ou vazio) → 422 `dados_invalidos` com `campos: {preco: "Recarregue a página
   para ver o preço atual do plano."}`, antes de chamar o Asaas (omitir pulava o `preco_mudou`). Testes atualizados: os
   utilitários `assinar` e `trocar_plano` mandam o preço atual; teste novo dos dois 422.
4. **Linhas fora do formato** (`core/parametros.py`, migração 0016, `plataforma/parametros.py`): no preço, a leitura não cai
   mais no padrão: fica o último valor bom lido ou, sem leitura anterior, `ParametroInvalido` ao pedir a chave (as outras
   chaves seguem a leitura nova). `limite_contatos` só aceita `jsonb_typeof` `null` ou `number` inteiro (só dígitos) de 1 a
   1.000.000, como o Python; o resto vale o padrão (antes, o texto "2" valia 2 no banco e o padrão no Python, e `true` ou
   2.5 davam erro no gatilho). O PUT do grupo apaga as linhas fora do formato do grupo, mesmo sem outra mudança (sem
   histórico; com a trava e a `versao`). Testes: preço inválido (último bom, sem leitura anterior sobe); banco e Python
   iguais para `2`, `null`, `"2"`, `true`, `2.5`, `2.0`, `0`, `-1`, `1000001`, `[2]` e `{"n": 2}`; PUT apaga as do grupo.
5. **`parametros` sem `alterado_em`/`alterado_por`** (migração 0016 editada, ainda não publicada; `modelos.Parametro`;
   upsert do PUT): a política `ler_limites` deixava a conta ler o e-mail do superadmin. "Alterado em … por …" e a `versao`
   vêm da última linha do histórico de cada grupo, como o GET já fazia (forma do JSON igual). Testes: em conta, `select *
   from parametros` só traz `chave` e `valor` (e a tabela só tem essas colunas); GET com dois superadmins em grupos
   diferentes e uma linha gravada à mão (sem histórico).
6. **Adoção pelo valor e pela descrição** (`assinatura/servico.py`: `da_assinatura`, `plano_da_assinatura`,
   `conciliar_para_assinar(s, conta, plano, valor)`; `assinatura/conferencia.py`): entre mudanças de preço, o preço antigo
   de um plano pode ser o atual de outro (Essencial 149 → 99 e Profissional 349 → 149). Só é adotada a assinatura com o
   preço atual e a descrição "Toqqi – plano X" do mesmo plano; senão, como um valor fora dos planos: removida no Asaas
   (`nao_adotada` na conferência; `duplicada` ao assinar, que cria a nova). Testes: a do Essencial a 149 não vira
   Profissional (conferência e assinar); com a descrição do Profissional, é adotada.
7. **Níveis da IA** (`core/parametros.py`, `ia/cota.py`, `ajuda/conteudo.json`): `ia.analises.rapido` ≤ `equilibrado` ≤
   `detalhado` (422 no campo do nível mais caro: "O Equilibrado não pode gastar menos análises que o Rápido." / "O Mais
   detalhado não pode gastar menos análises que o Equilibrado."). O `cota_insuficiente` sugere o nível mais barato que cabe
   no que resta (empate: o mais completo; com os padrões, segue o Equilibrado) e, se nenhum cabe, "Resta 1 análise e o
   nível Equilibrado gasta 3. Nenhum nível gasta tão pouco: a cota renova no dia 1º do próximo mês."; a Ajuda troca "troque
   para o “Equilibrado”" por "o nível mais econômico que cabe no que resta (o aviso diz qual)" nas três seções. Testes:
   validação, mensagens com vários custos (também pela API) e o texto da Ajuda.
8. **Testes que não cobriam o que diziam:** `tests/test_site_numeros.py` lê o `web/index.html` e confere cada `data-p` (e o
   `data-restam`) com os padrões de `core/parametros.py` (mais a prova de que acha um número trocado); em
   `test_parametros_efeitos.py`, o "+N dias" do teste em andamento usa a conta criada antes da mudança (e confere o plano).
- **Para o site:** `preco` passa a ser obrigatório nos dois pedidos (os tipos em `etapa5a.ts` o deixam opcional); o PUT e
  a prévia do grupo `ia` têm as mensagens novas de ordem das análises; o texto do 409 `cota_insuficiente` muda (a mensagem
  que o site monta sozinho, `mensagemCotaInsuficiente` em `assistente/logica.ts`, ainda fixa "Mais detalhado" e
  "Equilibrado"). `GET /plataforma/parametros` não muda.
