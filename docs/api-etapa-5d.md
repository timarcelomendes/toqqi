# Toqqi · Etapa 5d (IA sob demanda: resumo do painel, parecer dos relatórios, passos das ações, modelo e estilo)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
datas ISO 8601, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`), NPS com meio para cima, RLS por conta em toda
tabela nova. Reaproveite o que já existe: `core.ia` (adaptador, `transporte`, `_erro_http`, `cortar`, `sem_controle`),
`core.ia_conversa` (assistente), `modulos.ia.cota` (cota do plano), `modulos.ia.regras.teto_mensal` e o padrão de reserva da
análise por resposta (`modulos.ia.servico`), `assistente.servico.sem_enderecos`, `assistente.limite.em_andamento`.

## 0. Decisões desta etapa
- Da especificação (IA e assistente): **resumo do painel** só ao clicar, bloqueio de 30 s depois de gerar, 3 frases (o que
  precisa melhorar, o que funciona, próximo passo); **passos da ação** ao criar a ação de uma resposta, até 3 passos a partir
  do comentário e das últimas 5 respostas da empresa, e se a IA falhar a ação fica só com o comentário; **parecer dos
  relatórios** sob demanda: resumo e recomendação da semana para o recorte filtrado; **Configurações › IA**: modelo (Rápido e
  econômico / Equilibrado / Mais detalhado) e estilo (objetiva, equilibrada, criativa).
- Respostas do Marcelo (02/10): o resumo usa **os filtros da tela** e **fica salvo** até alguém gerar de novo; os **passos não
  gastam a cota do plano** (como a análise de cada resposta: só o teto de segurança mensal, `ia_uso_mensal.analises`).
- Resumo e parecer gastam **1 análise da cota do plano** cada geração (como uma pergunta ao assistente); falhou, devolve.
- Modelo e estilo da conta valem para o assistente, o resumo, o parecer e os passos. A análise de cada resposta (4b) continua
  com `IA_MODELO`/`IA_ESFORCO` fixos.
- Streaming de verdade no assistente continua fora (a tela já revela a resposta aos poucos).
- **Decisão do Marcelo (03/10)**: o nível "Mais detalhado" (gpt-5) custa à Toqqi umas 5 vezes o "Equilibrado" (gpt-5-mini),
  então **gasta 2 análises da cota do plano** por geração (resumo, parecer) ou pergunta ao ToqqiAI, em vez de 1; o "Rápido e
  econômico" passa a se chamar **"Rápido"** (a economia era da Toqqi, não do cliente: todo nível gastava 1). Rápido e
  Equilibrado continuam gastando 1. A análise de cada resposta e os passos das ações continuam fora da cota. Detalhes em §9.

## 1. Banco (migração `0013_ia_sob_demanda`, depois da `0012_crescimento`)
- `contas`: `ia_modelo text not null default 'equilibrado'` (CHECK 'rapido' | 'equilibrado' | 'detalhado'), `ia_estilo text
  not null default 'equilibrada'` (CHECK 'objetiva' | 'equilibrada' | 'criativa'), `ia_passos_acoes boolean not null default
  true`.
- `acoes`: `ia_passos jsonb null` (lista de 1 a 3 textos), `ia_passos_situacao text null` (CHECK 'pendente' | 'pronta' |
  'falhou' | 'limite'), `ia_passos_em timestamptz null`, `ia_passos_tentativas smallint not null default 0`,
  `ia_passos_reservada_em timestamptz null`. Índice parcial `(conta_id, criada_em) where ia_passos_situacao = 'pendente'`.
- `ia_pareceres` (o último resumo/parecer gerado para cada recorte): `id`, `conta_id`, `tipo` ('painel' | 'relatorios'),
  `chave text` (filtros canônicos, §2), `filtros jsonb`, `conteudo jsonb`, `modelo text` (o nível: rapido/equilibrado/detalhado),
  `estilo text`, `gerado_por bigint null` (FK `usuarios`, `on delete set null`), `gerado_em timestamptz not null`. Único
  `(conta_id, tipo, chave)` (gerar de novo substitui). Índice `(conta_id, tipo, gerado_em desc)`. RLS forçado + política de
  sempre. Excluir a conta apaga (FK `contas` `on delete cascade`, como as outras).
- Downgrade desfaz tudo.

## 2. Resumo do painel e parecer dos relatórios (sob demanda, gastam a cota)
Os dois funcionam igual; mudam a permissão, os dados (§2.3 e §2.4) e o formato (§2.5).

### 2.1 Rotas
- Painel (`painel.ver`): `GET /painel/resumo-ia?de=&ate=&grupo_id=&so_ativos=` e `POST /painel/resumo-ia` com o corpo
  `{de, ate, grupo_id, so_ativos}` (mesmos tipos e validação dos filtros do `GET /painel`, inclusive o 422 de período invertido).
- Relatórios (`relatorios.ver`): `GET /relatorios/parecer-ia?…` e `POST /relatorios/parecer-ia` com os filtros comuns dos
  relatórios `{de, ate, grupo_id, so_ativos}`.
- `GET` → `{disponivel, motivo, cota, custo, item, pode_gerar_em}`:
  - `disponivel`/`motivo` como `GET /assistente`: sem IA na plataforma `motivo: "ia_indisponivel"` (e `cota: null`, `custo: null`);
    conta não liberada `"conta_pausada"`; nenhuma análise restante `"cota_esgotada"`; restam menos análises que o custo do nível
    (ex.: 1 no Mais detalhado) `"cota_insuficiente"` (§9); senão `disponivel: true, motivo: null`;
  - `custo`: as análises que uma geração gasta no nível atual da conta (1, ou 2 no Mais detalhado; §5.2);
  - `item`: o salvo para a mesma `chave` de filtros, ou `null` (vem mesmo com `disponivel: false`);
  - `pode_gerar_em`: `gerado_em` da última geração deste `tipo` na conta (qualquer chave) + 30 s, se ainda no futuro; senão `null`.
- `POST` → 200 `{item, cota, custo, pode_gerar_em}` (`custo` = o desta geração). Erros, nesta ordem: 409 `ia_indisponivel` ("A
  IA não está disponível no momento."), 409 `conta_pausada` ("A IA volta quando a assinatura estiver em dia."), 429 `aguarde`
  (menos de 30 s desde a última geração deste tipo na conta, ou outra geração deste tipo em andamento na conta: "Aguarde {n} s
  para gerar de novo." com `n` ≥ 1; em andamento: "Já tem um resumo sendo gerado. Aguarde alguns segundos."), 409 `sem_dados`
  (nenhuma resposta NPS nem CSAT no recorte: "Não há respostas neste período para analisar." — não chama a IA, não gasta), 409
  `cota_esgotada` (mesma mensagem do assistente) ou 409 `cota_insuficiente` (§9), 503 `ia_indisponivel` (a IA falhou; as análises
  voltam para a cota).
- Vagas: use `assistente.limite.em_andamento` (2 por usuário, 6 no processo, sem esperar), como uma pergunta ao assistente.
- Ordem: validação → vagas → IA disponível → conta liberada (o nível, o estilo e o nome da conta são lidos aqui, uma vez só) →
  30 s / em andamento (trava em memória por (conta, tipo)) → dados (sem dados → 409) → reservar o custo do nível lido (transação
  curta, commit antes da IA) → chamada única (§2.6, com o mesmo nível) → salvar (upsert por chave) → somar tokens em
  `cota_tokens_*`. Falhou depois de reservar: devolve as análises reservadas, soma os tokens já gastos e responde 503.
- `chave` canônica: `de` e `ate` ISO ou vazio, `grupo_id` ou vazio, `so_ativos` true/false (vazio = true), ex.:
  `de=2026-07-01|ate=2026-09-30|grupo=|ativos=1`. `filtros` guarda os mesmos valores em JSON.
- `item` = `{conteudo, filtros, gerado_em, gerado_por: {id, nome} | null, modelo, modelo_rotulo, estilo}` (`conteudo` no formato
  de §2.5; `modelo_rotulo` "Rápido" | "Equilibrado" | "Mais detalhado"; desde 03/10, "Rápido" também nos itens salvos antes).
- Nada vai para a auditoria nem para o log além de status, tipo de falha e tokens (nunca os dados nem o texto).

### 2.2 O que vai para a IA (geral)
- Só dados agregados e textos de comentários de clientes, num JSON dentro da mensagem do usuário, marcado como dados
  (`<dados>…</dados>`; as instruções dizem que nada lá dentro é instrução). Comentários cortados em 300 caracteres, sem nome, e-mail
  ou telefone de contato. Nomes de empresas e de responsáveis podem ir (o assistente já envia; a Política passa a dizer, §6.4).
- Datas no formato dd/mm/aaaa; valores em reais com duas casas.

### 2.3 Dados do resumo do painel
Reaproveite `painel.servico` com os mesmos filtros (sem JIT): período e período anterior; NPS (valor, total, promotores,
neutros, detratores), variação, CSAT (percentual, média, total), taxa de resposta (percentual e amostra pequena),
movimentação (só as contagens), "precisa de atenção" (abertas, vencidas, receita em risco), temas (rótulo, menções, nota média,
variação), evolução mensal (mês e NPS), empresas de menor e maior NPS (nome, NPS, respostas) e os picos de reclamação ativos;
mais até 8 comentários do recorte (os mais recentes, metade de notas baixas quando houver: data, tipo, nota e texto).

### 2.4 Dados do parecer dos relatórios
Reaproveite `relatorios.servico` com os filtros comuns: resumo da aba Empresas (empresas, com respostas, cobertura, receita total
e em risco com percentual, faixas), matriz NPS × valor (quadrantes e até 5 empresas "Proteger já": nome, NPS, valor mensal,
responsável), temas (os 6 com menções, reclamações, nota média e variação; picos), responsáveis (até 5 com mais receita em
risco: nome, empresas, NPS, receita em risco, ações abertas e vencidas) e operação (taxa de resposta, ações concluídas no prazo,
contatos sem resposta: só o total e os atrasados). E "esta semana" (últimos 7 dias até hoje, mesmos filtros de empresa):
detratores novos e ações vencidas.

### 2.5 Formatos (JSON Schema estrito; os limites valem depois da IA)
- Resumo do painel: `{"melhorar": str, "funciona": str, "proximo_passo": str}` — uma frase cada (até 300 caracteres).
- Parecer: `{"resumo": str, "recomendacoes": [str]}` — resumo de 2 a 3 frases (até 600 caracteres); 1 a 3 recomendações para a
  semana (até 200 caracteres cada).
- Depois da IA: sem controles, sem `**` e sem endereços (`sem_enderecos`), uma linha por texto, cortados com "…" (`ia.cortar`);
  recomendações vazias ou repetidas saem; texto obrigatório vazio → falha transitória (devolve a cota).

### 2.6 Chamada única com formato fixo (`core/ia_texto.py`, novo)
- `gerar(nome_formato, instrucoes, dados, esquema, nivel, tempo_limite) -> (conteudo, tokens_entrada, tokens_saida, modelo)`:
  `POST {IA_BASE_URL}/v1/responses` com `model`/`reasoning` do nível (§5.2), `instructions`, `input` (uma mensagem do usuário com
  o JSON dos dados), `text.format` JSON Schema estrito, `max_output_tokens` 1500, `store: false`. Erros como o adaptador da 4b
  (`ia._erro_http`; recusa = definitiva; incompleta, JSON inválido, sem texto = transitória). Tempo: 45 s.
- Provedor `memoria` (testes e teste integrado): respostas previsíveis por `nome_formato` montadas a partir dos números recebidos
  (ex.: resumo "O NPS do período foi {valor}…"), `programar(...)` para falhas e saídas específicas, e `corpos` guarda o enviado.
- Instruções em português: quem é (analista de satisfação de clientes B2B da conta "{conta}"), hoje, usar só os números dados
  e como vieram, citar período e total, amostra pequena (< 20 respostas NPS) avisada, NPS/CSAT definidos como no assistente,
  sem links, HTML, markdown ou nomes de pessoas de contato, e o estilo da conta (§5.3).

## 3. Passos das ações (automático, não gasta a cota)
- Quando: ao criar uma ação com `resposta_id` (a automática de `acoes.automatica.criar_acao_automatica` e a manual de
  `POST /acoes` com `resposta_id`), se `passos_ativos(conta)` = `ia.disponivel()` e `conta.ia_passos_acoes` e
  `liberada(conta)`, e se houver texto: o comentário do cliente da resposta (3+ letras) ou o de pelo menos uma das últimas 5
  outras respostas da mesma empresa. Então `ia_passos_situacao = 'pendente'` e o par (conta, ação) vai para o coletor
  `coletar_passos()`, usado junto dos outros coletores nas rotas que gravam respostas (`publico/rotas.py` nos dois pontos,
  `respostas/rotas.py` nos dois pontos) e no `POST /acoes`; depois do commit, `sugerir_passos(pares)` em BackgroundTasks.
  Sem texto ou sem IA: `ia_passos_situacao` fica nulo (nada aparece).
- Processamento igual ao da análise por resposta: reserva com marca (`ia_passos_reservada_em`, `FOR UPDATE SKIP LOCKED`, reserva
  vencida em 5 min herda o consumo), consome o **teto de segurança** do mês (`ia_uso_mensal.analises` < `teto_mensal(conta)`;
  sem saldo → `'limite'`), chama a IA fora da transação, grava só se ainda `pendente` e com a mesma marca. Falha devolve o teto
  e solta a reserva; transitória soma tentativa e vira `'falhou'` na 3ª; definitiva vira `'falhou'`; configuração (401/403/404)
  não conta tentativa e para a rodada. Tokens em `ia_uso_mensal.tokens_*` (os da análise por resposta).
- Segundo plano: no máximo 2 ao mesmo tempo por processo, sem esperar vaga (sem vaga fica para a tarefa), 15 s de tempo limite.
  A tarefa `ia` (`python -m toqqi.tarefas ia`, também em `tudo`) processa as pendentes mais antigas depois das respostas, até 100
  por rodada dentro do tempo dela, só de contas com a IA disponível e liberadas; devolve `passos: {prontas, falharam, limite}`.
- Desligar `ia_passos_acoes` cancela as pendentes da conta (situação volta a nulo). Editar ou mover a ação não mexe nos passos.
- Para a IA: tipo, nota e grupo da resposta da ação; o comentário dela (500 caracteres) e as opções marcadas; as últimas 5 outras
  respostas não arquivadas da mesma empresa (data, tipo, nota, comentário em 300 caracteres), mais novas primeiro. **Nunca** nome
  da empresa, do contato, e-mail, telefone ou contexto do pedido. Formato `{"passos": [str]}`; depois da IA: 1 a 3 passos
  imperativos (até 200 caracteres cada, mesma limpeza de §2.5); nenhum → falha transitória. Instruções: passos concretos que a
  equipe pode fazer nesta semana para resolver o que o cliente apontou, sem prometer desconto ou prazo que não esteja nos dados.
- `acao_json` (listas, quadro e `GET /acoes/{id}`) ganha `ia_passos: [str] | null` e `ia_passos_situacao`.

## 4. Assistente
- O corpo da chamada (`ia_conversa.corpo_da_chamada`) passa a usar o modelo e o esforço do nível da conta (§5.2) e as
  instruções ganham a linha do estilo (§5.3). Desde 03/10, cada pergunta gasta o custo do nível (§9): `GET /assistente` e a
  resposta de `POST /assistente/perguntar` trazem `custo`, e o 409 pode ser `cota_insuficiente`. O resto não muda.

## 5. Configurações › IA
### 5.1 Rotas
- `GET /conta/ia` ganha `modelo`, `estilo`, `passos_acoes`, `modelos: [{valor, rotulo, descricao, analises}]` (`analises`: o que
  uma geração ou pergunta gasta da cota no nível, desde 03/10) e `estilos: [{valor, rotulo, descricao}]` (textos de §5.2 e §5.3).
- `PUT /conta/ia` aceita os campos opcionais `analise_respostas`, `modelo`, `estilo`, `passos_acoes` (pelo menos um; 422
  `dados_invalidos` se nenhum ou valor fora da lista) e devolve o estado inteiro. Auditoria `config_ia` com só os campos que mudaram.
### 5.2 Níveis de modelo (config, com padrões)
| Nível | Rótulo | Descrição | Gasta | Modelo | Esforço |
|---|---|---|---|---|---|
| rapido | Rápido | Respostas curtas e rápidas. Gasta 1 análise da cota. | 1 | `IA_MODELO_RAPIDO` = `gpt-5-nano` | `IA_ESFORCO_RAPIDO` = `minimal` |
| equilibrado | Equilibrado | O padrão: bom para o dia a dia. Gasta 1 análise da cota. | 1 | `IA_MODELO_EQUILIBRADO` vazio = `IA_ASSISTENTE_MODELO` | `IA_ESFORCO_EQUILIBRADO` vazio = `IA_ASSISTENTE_ESFORCO` |
| detalhado | Mais detalhado | Análises mais cuidadosas; pode demorar mais. Gasta 2 análises da cota. | 2 | `IA_MODELO_DETALHADO` = `gpt-5` | `IA_ESFORCO_DETALHADO` = `low` |
Esforço vazio = não manda `reasoning`. "Gasta" = análises da cota do plano por geração (resumo, parecer) ou pergunta ao ToqqiAI
(`ia_texto.analises_do_nivel`; decisão de 03/10, §9). Até 02/10 o rápido se chamava "Rápido e econômico" e todo nível gastava 1.
### 5.3 Estilos
| Estilo | Rótulo | Descrição | Linha nas instruções |
|---|---|---|---|
| objetiva | Objetiva | Frases curtas, só o essencial. | "Estilo: objetivo. Frases curtas e diretas, só o essencial, sem adjetivos." |
| equilibrada | Equilibrada | Claro e cordial (padrão). | (nenhuma) |
| criativa | Criativa | Tom mais próximo e ideias práticas. | "Estilo: próximo e caloroso. Proponha ideias práticas e criativas, sem inventar dados." |

## 6. Site
### 6.1 Painel
- Cartão "Resumo da IA" (ícone Sparkles) logo abaixo do `CartaoNps`, para quem vê o painel. Some com `motivo:
  "ia_indisponivel"`. Lê `GET /painel/resumo-ia` com os mesmos filtros do painel a cada troca de filtro.
- Sem item: texto curto ("Três frases sobre o período: o que precisa melhorar, o que está funcionando e o próximo passo. Usa 1
  análise de IA.", com o `custo` do GET desde 03/10: "Usa 2 análises de IA." no Mais detalhado) e botão "Gerar resumo". Com
  item: as 3 frases rotuladas ("Precisa melhorar", "Está funcionando", "Próximo
  passo") e o rodapé "Gerado em dd/mm/aaaa às hh:mm por {nome} · {modelo_rotulo}" e, depois de gerar, "Restam X de Y análises
  este mês". Botão "Gerar de novo".
- Gerando: botão ocupado e `Carregando` "Lendo os números do período…" (até 45 s). Depois de gerar, o botão fica desabilitado
  com a contagem ("Gerar de novo em 25 s") até `pode_gerar_em`. Item salvo de outro modelo continua visível.
- `conta_pausada`: texto "O resumo volta quando a assinatura estiver em dia." sem botão. `cota_esgotada` ou 409 do POST: a
  mensagem da API; administrador vê o link "Configurações › IA". `cota_insuficiente` (§9): a mensagem da API (no GET, a mesma
  montada com `custo` e `restantes`); quem tem `configuracoes.gerenciar` vê o link "Trocar o nível". 409 `sem_dados`, 429 e 503:
  `Alerta` com a mensagem e, no 503, "Tentar de novo".
### 6.2 Relatórios
- Botão "Parecer da IA" (Sparkles) nas ações do cabeçalho de Relatórios abre um `PainelLateral` com o parecer dos filtros
  comuns da tela (período, grupo, só ativos), mesmos estados do cartão do painel: "Resumo" (parágrafo) e "Recomendações da
  semana" (lista numerada); botão "Gerar parecer" / "Gerar de novo" com a contagem. Some sem IA na plataforma.
### 6.3 Plano de ação
- No `PainelAcao`, abaixo da descrição, bloco "Passos sugeridos pela IA": `pendente` → "A IA está sugerindo os passos…" e
  relê a ação a cada 5 s, até 6 vezes; `pronta` → lista numerada, `BotaoCopiar` (copia os passos numerados) e a nota "Sugestão
  da IA. Confira antes de seguir."; `falhou` → "A IA não conseguiu sugerir passos para esta ação."; `limite` → "O limite mensal
  de análises automáticas foi atingido."; nulo → nada.
### 6.4 Configurações › IA, Ajuda e Política
- Seção "Como a IA escreve" em Configurações › IA: modelo (3 opções em cartões de escolha com rótulo e descrição), estilo (3
  opções) e o interruptor "Sugerir passos nas ações" ("Ao criar uma ação a partir de uma resposta, a IA sugere até 3 passos.
  Não gasta a cota do plano."). Salva na hora (aviso de sucesso; erro volta o valor). A tela já exige `configuracoes.gerenciar` (§8).
- Ajuda (`api/toqqi/modulos/ajuda/conteudo.json`): atualizar os tópicos de IA, Painel, Relatórios e Planos de ação com o resumo,
  o parecer, os passos, o modelo e o estilo, e o que gasta ou não a cota.
- Política de privacidade (`web/src/modulos/geral/legal/privacidade.ts`), seção de IA: passam a ser cinco recursos (análise de
  comentários, passos das ações, resumo do painel, parecer dos relatórios e assistente), com o que cada um envia (§2.2, §2.3, §2.4,
  §3) e como desligar (os passos em Configurações › IA; resumo e parecer só rodam quando alguém pede). Mudança relevante:
  `VERSAO_DOCUMENTOS` = 2 nos dois lugares (`api/toqqi/modulos/acesso/termos.py` e `web/src/modulos/geral/legal/versao.ts`).

## 7. Testes
- API: estados do GET; POST com cota (reserva e devolução), 30 s e em andamento, sem dados, chave por filtros (salvo e
  substituído), filtros validados, permissões, RLS de `ia_pareceres`; dados enviados à IA (sem nomes de contato, com
  `<dados>`, comentários cortados); passos (quando ficam pendentes, teto consumido e devolvido, tentativas, definitiva,
  configuração, desligar cancela, nada de nome de empresa ou contato no corpo, coletor nas rotas, tarefa `ia`); modelo e estilo
  no corpo das chamadas do assistente, do resumo, do parecer e dos passos; PUT parcial e auditoria.
- Site (vitest): estados do cartão do painel (sem item, gerando, item, contagem, pausada, cota esgotada, 503 com tentar de
  novo, some sem IA), troca de filtro relê, parecer no painel lateral, passos (pendente relê e para, pronta copia, falhou,
  limite), Configurações › IA (salva modelo/estilo/interruptor, desfaz no erro, só leitura).

## 8. Ajustes depois da construção e da revisão (02/10)
- Vagas: com 2 pedidos à IA em andamento do mesmo usuário (assistente, resumo ou parecer), 429 `aguarde` "Você já tem pedidos
  à IA em andamento. Aguarde alguns segundos e tente de novo."; com as 6 vagas do processo ocupadas, 503 com a mensagem do tipo.
  As mensagens do parecer dizem "parecer" no lugar de "resumo".
- Os 30 s contam do `gerado_em` gravado (lido com a trava); falha e `sem_dados` não começam a espera. Só a trava de "em
  andamento" fica na memória de cada processo.
- Qualquer falha depois de reservar a cota (inclusive o banco recusar a gravação) devolve a análise e responde **503**; o
  detalhe fica só no log.
- O parecer também recebe os totais e valores de NPS e CSAT do recorte (para citar o total e avisar a amostra pequena); temas
  só com menções ou variação; "esta semana" = detratores dos últimos 7 dias e ações abertas vencidas hoje, com os filtros de empresa.
- Passos: as instruções não levam nem o nome da conta; a numeração do começo do passo sai só quando é índice com espaço depois
  ("1. ", "2) ", "3 - ", "- ", "• "), para não cortar "1.500", "10:00" ou "3-5"; o banco exige de 1 a 3 passos de até 200
  caracteres, só com a situação `pronta`; ação que perdeu a resposta fica sem passos. A tarefa divide os 240 s com a análise
  por resposta e também visita as contas com os passos desligados para cancelar o que ficou pendente (marcado ao mesmo tempo
  que alguém desligava); desligar devolve o teto das reservas vencidas. "Analisar comentários dos últimos 90 dias" desconta os
  passos pendentes do saldo do teto.
- As marcas `<dados>`/`<comentario>` saem do texto do cliente até não sobrar nenhuma (a marca aninhada não escapa).
- Provedor `memoria` no teste integrado (a API roda em outro processo): `[ia:falha]`, `[ia:recusa]` e `[ia:demora=N]` no texto
  que vai para a IA (comentário de cliente ou nome da conta) mudam a resposta; no pytest, `ia_texto.memoria.programar(...)`.
- Site: "Como a IA escreve" não tem modo só leitura (a tela e `GET /conta/ia` já exigem `configuracoes.gerenciar`); a contagem
  usa um prazo local de até 30 s (relógio do aparelho adiantado ou atrasado não trava o botão) e fica fora do nome acessível
  do botão; "Gerando" só aparece no recorte que está sendo gerado (terminou em outro recorte → aviso para voltar a ele); o botão
  do parecer some na aba "Histórico de uma empresa" (ela não mostra os filtros comuns); no cartão vazio, "Gerar resumo" fica à
  esquerda (à direita, no pé da tela, cairia sob o botão flutuante do assistente) e o foco por teclado rola acima dele.
- Termos de uso: o parágrafo de IA passou a listar os cinco recursos, como a Política (os dois na versão 2, vigente em 02/10/2026).

## 9. Custo por nível de modelo (03/10)
Decisão do Marcelo (§0): o "Mais detalhado" gasta 2 análises da cota do plano por geração ou pergunta; o "Rápido e
econômico" virou "Rápido". O resto da etapa não muda.
- **Níveis** (`core/ia_texto.py`): cada nível de `MODELOS` tem `analises` (rapido 1, equilibrado 1, detalhado 2), lido por
  `analises_do_nivel(nivel)` (nível desconhecido = equilibrado). Rótulos e descrições como na tabela de §5.2 (cada descrição
  termina com o que o nível gasta). `GET /conta/ia` (e o estado que o `PUT` devolve): cada item de `modelos` traz `analises`;
  os `estilos` não.
- **Cota** (`modulos/ia/cota.py`): `reservar(s, conta, quantidade=1)` reserva as N análises de uma vez só se `cota_usada + N
  <= limite` (`INSERT … ON CONFLICT … DO UPDATE … WHERE cota_usada + N <= limite`; N maior que o limite inteiro nem cria a
  linha do mês): nunca uma parte, e pedidos ao mesmo tempo não passam do limite. `Reserva.quantidade` guarda N (padrão 1) e
  `devolver` devolve exatamente N, no mês da reserva, nunca abaixo de zero. `motivo_sem_saldo(uso, custo)`,
  `mensagem_insuficiente(restantes, nivel)` e `erro_sem_saldo(s, conta, nivel)` montam o motivo e o 409 abaixo.
- **Resumo, parecer e ToqqiAI**: o nível da conta é lido uma vez por pedido; a reserva gasta `analises_do_nivel(nivel)` e a IA
  roda com esse mesmo nível (trocar o nível em Configurações › IA no meio do pedido não cobra 1 e roda o Mais detalhado, nem o
  contrário). Qualquer falha depois de reservar devolve a mesma quantidade. O log leva o nível e as análises gastas ou devolvidas.
- **`custo`**: `GET /painel/resumo-ia`, `GET /relatorios/parecer-ia` e `GET /assistente` trazem `custo` ao lado da `cota` (as
  análises de uma geração ou pergunta no nível atual; `null` sem IA na plataforma, como a `cota`). Os 200 de `POST
  /painel/resumo-ia`, `POST /relatorios/parecer-ia` e `POST /assistente/perguntar` também (`custo` = o que aquele pedido gastou).
- **Sem saldo para o custo**: nenhuma análise restante → `cota_esgotada`, exatamente como antes (GET e 409). Restam análises,
  mas menos que o custo (ex.: 1 no Mais detalhado) → GET `disponivel: false, motivo: "cota_insuficiente"` e POST 409
  `cota_insuficiente` "Resta 1 análise e o nível Mais detalhado gasta 2. Troque para o Equilibrado em Configurações › IA ou
  aguarde o próximo mês." (no plural a partir de 2: "Restam 2 análises …"). Nada é gasto nem vai à IA. A ordem das
  verificações não muda (conta pausada e, no resumo e no parecer, a espera de 30 s e o "sem dados" vêm antes).
- **Fora da cota, sem mudança**: a análise de cada resposta e os passos das ações (só o teto de segurança mensal).
- **Site**: "Como a IA escreve" mostra os rótulos e as descrições da API (nada no site escreve o nome antigo); Configurações ›
  IA diz que o Mais detalhado usa 2; o texto do resumo e do parecer sem item usa o `custo` do GET ("Usa 1 análise de IA." /
  "Usa 2 análises de IA."). `cota_insuficiente` bloqueia como `cota_esgotada` no cartão do painel, no parecer, no painel do
  ToqqiAI e no store do assistente: a mensagem da API (ou a mesma frase montada com `custo` e `restantes`) no lugar do botão ou
  da caixa e, para quem tem `configuracoes.gerenciar`, o link "Trocar o nível" (`/configuracoes/ia`). O store desliga sozinho
  com `restantes < custo` (antes `restantes <= 0`): sem nenhuma, cota esgotada; com alguma, cota insuficiente (o que resta não
  zera). Um 409 `cota_insuficiente` (do ToqqiAI, do resumo ou do parecer) faz o assistente ler o estado de novo, para mostrar
  o que resta e o custo de agora.
- **Textos**: Termos de uso ("usa 1 análise da cota de IA do plano (2 no nível Mais detalhado, que a Empresa escolhe em
  Configurações › IA)"), ainda na versão 4 (não publicada: `VERSAO_DOCUMENTOS` e `VIGENTE_DESDE` não mudam); Ajuda (resumo,
  parecer, modelo, cota e ToqqiAI); site (nota abaixo da tabela de planos: no Mais detalhado, cada pergunta, resumo ou parecer
  conta como 2).
- **Testes**: API `tests/test_ia_custo_nivel.py` (níveis, `analises` em `GET/PUT /conta/ia`, reserva de N no limite e nunca
  parcial, reservas de 2 ao mesmo tempo com e sem a linha do mês, devolução de N no mês da reserva, resumo/parecer/pergunta no
  Mais detalhado gastando e devolvendo 2, `cota_insuficiente` no GET e no POST com 1 restante e `cota_esgotada` com 0,
  mensagem no plural, perguntas simultâneas, nível lido uma vez) e os ajustes de `test_ia_pareceres.py`,
  `test_assistente.py` e `test_ia_modelo_estilo.py`; site (vitest) `etapa5dLogica`, `etapa5bLogica`, `etapa5dComponentes`,
  `etapa5dPassosConfig`, `assistenteComponente`, `ajudaComponente` e `site`.
