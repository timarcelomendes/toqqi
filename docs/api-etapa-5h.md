# Toqqi · Etapa 5h (primeiro dia do teste, taxa de resposta, aviso de erros e visão do negócio)

Pedido do Marcelo (04/10, 20:18): "olhe para o projeto e me ajude a melhorar". Depois de um tour como cliente novo (cadastro,
importação de 41 contatos e 164 respostas, pesquisa respondida no celular, ação, relatórios, ToqqiAI e Plataforma), ele
escolheu as quatro frentes propostas (21h20). Mesmas convenções das etapas anteriores (base `/api/v1`, Bearer, erro
`{"erro":{codigo,mensagem,campos}}`, RLS, `requer(...)`, design-system, claro e escuro, 390 a 1440 px, nada de `v-html`).
Três construções em paralelo, cada uma em seu worktree e com o seu banco de testes: **A** (§1 e §2), **B** (§3) e **C** (§4
e §5). Só a C cria migração (`0017_erros`, depois da `0016_parametros`).

## 0. Decisões
- Nada aqui gasta a cota de IA do plano. A análise dos comentários importados usa só o teto de segurança (como hoje).
- Dados de exemplo só na tela: nada fictício é gravado na conta.
- Erros: guardamos só o que diagnostica (tipo, mensagem limpa, onde, versão, contagem), **sem dados pessoais** (sem corpo,
  sem query string, sem e-mail, telefone, documento ou IP); 30 dias. Não muda os Termos nem a Política.
- Na Plataforma, `/plataforma` passa a abrir na **Visão geral**; Contas vai para `/plataforma/contas`.

## 1. Primeiro dia: o Início antes da primeira resposta (A)
- Conta **sem nenhuma resposta** (`primeiros_passos.primeira_resposta` falso; a importada conta como resposta): o Início
  (para quem tem `painel.ver`) troca o painel por **"Comece por aqui"**: saudação, "Em 4 passos você recebe as primeiras
  respostas", os 4 passos de `montarPassos` como uma lista grande (número, título, descrição, feito/a fazer, botão do passo
  quando o perfil abre a tela; o próximo a fazer em destaque), o cartão do teste grátis como hoje, e dois cartões:
  - **"Sua marca nas pesquisas"** (só `configuracoes.gerenciar`; opcional, não conta nos 4 passos): mostra se já há logo e
    cor; botão "Escolher logo e cor" abre um modal com o logo (envio pelo `PUT /conta/logo` que já existe) e a cor (paleta
    com 8 sugestões + campo #RRGGBB, com a prévia de um botão da pesquisa) → `PUT /conta/marca {cor}` (abaixo). Feito =
    tem logo ou cor própria.
  - **"Veja como fica com dados"**: botão "Ver com dados de exemplo" liga o **modo exemplo**: o mesmo painel de hoje,
    alimentado por um `Painel` fictício do site (`web/src/modulos/painel/exemplo.ts`; datas relativas a hoje; nomes e
    números inventados, coerentes entre si), com uma faixa fixa no topo "Você está vendo dados de exemplo." + "Voltar para
    os meus dados". No modo exemplo, links e botões do painel ficam desativados (o cartão de resumo da IA não gera), salvo
    "Como ler o painel". O modo não fica salvo (recarregar volta ao normal); `?exemplo=1` no endereço abre direto nele.
- Com a primeira resposta, o Início volta a ser o painel (com a linha dos primeiros passos, como hoje).
- `PUT /conta/marca` (`configuracoes.gerenciar`) `{cor: "#RRGGBB"}` → grava `config_envios.email_cor` (a cor dos e-mails)
  e troca `tema.cor` dos formulários da conta que ainda estão na cor dos modelos (`#1f6feb`, sem diferenciar maiúsculas) pela
  nova; formulário novo criado depois nasce com `email_cor` se houver. Devolve `{cor, formularios_atualizados}`. Auditoria
  `marca_alterada`. `GET /conta/marca` → `{cor, tem_logo}` (para quem vê o Início).

## 2. Primeiro dia: depois de importar o histórico (A)
- **IA nos importados**: ao concluir a importação de respostas, se a IA está disponível, a conta tem
  `ia_analise_respostas` e está liberada, as respostas importadas dos últimos 90 dias com comentário de 3+ letras viram
  `pendente` (mesma regra e mesmo saldo de `ia.servico.analisar_recentes`, refatorada para um núcleo sem erros) e uma tarefa
  em segundo plano (BackgroundTasks, depois do commit) processa a fila **desta conta** já: até 100 análises ou 120 s, no
  máximo 4 ao mesmo tempo; o resto fica para a tarefa `ia`. A resposta da importação ganha `ia_marcadas` (número).
  A tela final da importação diz "A IA vai ler os N comentários dos últimos 90 dias: o tom e os temas aparecem no Início em
  alguns minutos." quando N > 0.
- **Tom dos comentários** (`BlocoTom`): hoje, com comentários e nada analisado nem pendente, manda "Ligue a análise por IA"
  mesmo com ela ligada. O painel ganha `tom.ia_ligada` (IA disponível e `ia_analise_respostas`) e `tom.sem_analise`
  (comentários do período sem análise e não pendentes). Ligada e `sem_analise` > 0: "N comentários ainda não foram lidos pela
  IA." + botão "Analisar agora" (só `configuracoes.gerenciar`; chama `POST /conta/ia/analisar-recentes` e passa ao estado
  "analisando"); desligada: o texto de hoje.
- **Planos para os detratores sem plano**: `POST /acoes/detratores` (`acoes.tratar`) com os filtros do painel (`de`, `ate`,
  `grupo_id`, `so_ativos`) → para cada empresa (ou contato sem empresa) com resposta NPS de detrator no período e **sem
  ação aberta** (a fazer ou em andamento), cria **uma** ação a partir da resposta de detrator mais recente: mesmo título,
  prioridade, prazo, responsável e descrição da ação automática (`acoes.automatica`), `origem = "manual"`, `criado_por` =
  quem pediu, passos da IA como hoje. Até 100 por chamada (a mais urgente primeiro: menor nota, depois a mais recente);
  devolve `{criadas, restantes}`. Auditoria `acoes_detratores_criadas` com o número.
- O painel ganha `atencao.detratores_sem_plano` (quantas seriam criadas agora, com os mesmos filtros). Em "O que mudou",
  quando > 0 e a pessoa tem `acoes.tratar`, o botão "Criar planos para N empresas" (ou "para 1 empresa") chama o endpoint,
  mostra "N planos criados" e leva a Planos de ação. A tela final da importação de respostas mostra o mesmo convite (últimos
  90 dias).

## 3. Taxa de resposta (B)
- **E-mail** (`envios/mensagens.py`, `_botoes_nota`): a régua cabe em 320 px. Tabela com 100% de largura (máx. a do
  cartão), cada nota em célula de largura percentual (NPS 11 notas, CSAT 5), link em bloco com 40 px de altura e fonte 15 px,
  cores e `bgcolor` como hoje (Outlook), rótulos embaixo. Conferir no Chromium a 320, 360 e 600 px: sem rolagem lateral.
- **Página da pesquisa** (`web/src/pesquisa`):
  - NPS em telas estreitas (< 420 px de largura do cartão): duas linhas (0–5 e 6–10), cada nota com pelo menos 44 × 44 px;
    "Nada provável" embaixo do 0 e "Muito provável" embaixo do 10. Telas largas: uma linha, como hoje.
  - **Sem a tela "Começar"**: com título ou texto de abertura, eles aparecem no topo da primeira pergunta (mesma tela); o
    botão "Voltar" da primeira pergunta some. `?nota=N` continua começando depois da nota. A prévia do editor segue a página.
  - Acessibilidade: no fim, o anúncio para leitores de tela passa a ser o título final (hoje fica "Pergunta 2 de 2").
- Ajuda: se algum texto citar a tela "Começar" ou a abertura como tela separada, ajustar (só `conteudo.json`, seções de
  Formulários).

## 4. Aviso de erros (C)
- Migração `0017_erros`: tabela `erros` (sem conta na RLS: só modo sistema; o papel da aplicação lê e grava): `id`,
  `impressao text UNIQUE` (sha256 de origem + tipo + local + primeira linha útil da pilha), `origem` (`api` | `site` |
  `tarefa`), `tipo` (≤ 80), `mensagem` (≤ 300, já limpa), `local` (≤ 200: `GET /api/v1/acoes/{acao_id}` com o modelo da
  rota, o caminho da tela sem query/hash, ou o nome da tarefa), `pilha` (≤ 1.000, limpa), `versao` (`RENDER_GIT_COMMIT`
  curto ou a do site), `ocorrencias int`, `primeira_em`, `ultima_em`, `ultimo_request_id`, `conta_id` (nullable, sem FK),
  `resolvido_em` (nullable; nova ocorrência reabre).
- `core/erros.py`: `registrar(origem, tipo, mensagem, local, pilha, versao, conta_id, request_id)` → upsert pela impressão
  (+1, `ultima_em`), em conexão própria do modo sistema, **nunca** lança (falha só vai ao log). Limpeza: e-mails
  (`\S+@\S+`), sequências de 4+ dígitos, tokens longos (20+ letras/números) e texto entre aspas viram `…`. No máximo 200
  registros por minuto por processo (o resto só conta no log).
- API: os handlers de 500 (`_inesperado` e o de banco) registram; a tarefa (`toqqi.tarefas`) registra a exceção de cada
  tarefa (origem `tarefa`, local = nome) sem parar as outras. `POST /publico/erros` (sem login; 10 por minuto por IP; corpo
  ≤ 4 KB: `tipo`, `mensagem`, `local`, `pilha`, `versao`) → origem `site`. `GET /saude` (sem login) → `{ok, banco, versao}`
  com `SELECT 1` (503 se o banco falhar), para monitor externo.
- Site: `web/src/utils/erros.ts` liga `app.config.errorHandler`, `window.onerror` e `unhandledrejection` no `main.ts` (e na
  página da pesquisa): manda uma vez por mensagem por carregamento, no máximo 5 por carregamento; ignora erros de rede e
  respostas da API (`ApiError` com status), erros de extensões (pilha fora do nosso domínio) e `ResizeObserver loop`.
- E-mail diário: tarefa `erros` (no `tudo`, uma vez por dia a partir das 8h de São Paulo, marcada como na `limpeza`): se
  houve ocorrência não resolvida nas últimas 24 h, manda aos superadmins (e-mails de `SUPERADMIN_EMAILS` com usuário
  confirmado) "Toqqi: N erros nas últimas 24 h" com os 10 mais frequentes (tipo, onde, quantas vezes, última vez) e o link para
  Plataforma › Erros. Limpeza apaga `erros` com `ultima_em` > 30 dias.
- `GET /plataforma/erros` (superadmin) `?origem=&situacao=abertos|resolvidos|todos&dias=7|30` → lista ordenada por
  `ultima_em`; `POST /plataforma/erros/{id}/resolver` e `/reabrir`.
- README: como ligar um monitor externo grátis (UptimeRobot ou Better Stack) em `/api/v1/saude` e no site, com alerta por
  e-mail (ação do Marcelo).

## 5. Visão do negócio na Plataforma (C)
- `GET /plataforma/visao` (superadmin, modo sistema) →
  - `totais`: contas por situação (`teste`, `teste_expirado`, `ativa`, `atrasada`, `pausada`, `cancelada`, `cortesia`, e as
    que existirem em `assinatura.regras`), `pagantes` (assinatura ativa no ambiente atual do Asaas), `receita_mensal` (soma
    do `valor` dessas assinaturas), `ambiente` (sandbox | producao | null), `novas_7d`, `novas_30d`;
  - `conversao`: das contas criadas entre 60 e 15 dias atrás, quantas assinaram (assinatura criada, mesmo cancelada depois) ÷
    total;
  - `testes_acabando`: contas em teste com `teste_ate` nos próximos 7 dias (id, nome, e-mail do administrador mais antigo,
    `teste_ate`, ativação);
  - `contas`: todas, com `id`, `nome`, `situacao`, `plano`, `criada_em`, `teste_ate`, `ultimo_acesso` (o mais recente dos
    usuários), `usuarios`, `contatos_ativos`, `convites_30d`, `respostas_30d`, `respostas_total`, `ativacao` (os 4 passos de
    `_primeiros_passos`: contatos, envios ligados, primeiro envio, primeira resposta), `ia_analises_mes` (teto usado no mês)
    e `assinatura` (`{plano, valor}` ou null). Consultas agregadas (sem N+1); a superadmin nunca vê nomes de contatos.
- Site: Plataforma com 4 abas, nesta ordem e endereços: **Visão geral** (`/plataforma`), **Contas** (`/plataforma/contas`),
  **Parâmetros** (`/plataforma/parametros`), **Erros** (`/plataforma/erros`). Visão geral: indicadores (Em teste, Pagantes,
  Receita mensal — com "sandbox" quando for —, Testes acabando em 7 dias, Novas em 30 dias, Conversão do teste), a lista
  "Testes acabando" (nome, e-mail do administrador com botão copiar, dias que faltam, os 4 marcadores de ativação, último
  acesso) e a tabela de contas (busca, filtro por situação, ordenar por último acesso, criação ou respostas; os 4 marcadores
  de ativação). Erros: a lista do §4 com filtros, "Resolver"/"Reabrir", e um aviso vazio "Nenhum erro nos últimos N dias".

## 6. Testes e entrega
- Cada construção: testes da API do que mudou (arquivos novos `test_etapa5h_*.py`) e do site (`*.test.ts` novos), a suíte da
  API dos arquivos que tocou e `npx vitest run` + `npm run build`; os testes que já existem continuam passando (mudou o
  comportamento de propósito → ajustar e explicar).
- Depois: revisão por quem não escreveu, junção dos três ramos, teste integrado (pilha local, 1280 claro e 390 escuro) e
  entrega no Mac em commits separados por frente.

## 7. Feito (04/10, noite) — decisões tomadas na construção
- **A (primeiro dia)**: `GET /conta/marca` para qualquer usuário logado (só leitura); o cartão da marca conta como feito com
  logo ou cor própria; formulário novo e a lista de modelos já vêm com a cor da marca. `ia.servico` ganhou o núcleo
  `marcar_recentes` (o "analisar os últimos 90 dias" e a importação usam o mesmo), `marcar_importadas` e `processar_conta`
  (até 100 análises ou 120 s, 4 ao mesmo tempo, pela mesma `processar` com reserva, teto e tentativas). Planos para
  detratores: um por empresa (contato sem empresa: um por contato), a resposta mais urgente (menor nota; no empate, a mais
  recente), até 100 por chamada com `restantes`, trava por conta, origem manual, **sem** o e-mail "Alerta de risco" (são
  respostas antigas) e com os passos da IA depois do commit; corpo vazio = todo o histórico, só empresas ativas. O convite
  da tela final da importação usa os últimos 90 dias e só aparece para quem trata planos e vê o painel. Tom: com a IA
  ligada e nada lido por ser tudo curto demais, "Os comentários deste período são curtos demais para a IA ler o tom.";
  com parte lida e parte não, "Analisar os N que faltam" (quem administra). Modo exemplo: botões desligados e links viram
  texto, o foco vai à faixa ao entrar e volta ao botão ao sair, `?exemplo=1` liga o modo e sai do endereço; só no Início.
  Fica para depois: na reimportação, respostas que já tinham análise e mudaram de comentário esperam a tarefa `ia`.
- **B (taxa de resposta)**: régua do e-mail com células de 9,09% (NPS) ou 20% (CSAT; o CSAT fica limitado a 320 px e
  centralizado, salvo no Outlook); escalas de 8 a 11 notas também vão para duas linhas no cartão estreito; a abertura só com
  texto não usa mais o nome do formulário como título (ele é interno); a primeira e a última nota da escala levam os
  rótulos no nome para leitores de tela. A 320 px as notas da página ficam com 37,7 × 48 px (os 44 px valem a partir de 360).
- **C (erros e visão)**: impressão = origem + tipo + local + primeiro quadro útil sem número de linha (no site, sem o hash do
  build); a pilha da API guarda só `funcao (arquivo:linha)` dos quadros do Toqqi e o mais interno; o SQLSTATE fica na
  mensagem. `/publico/erros` sempre 204 e guarda a conta quando vem token válido; `/saude` 503 no mesmo formato, 60/min (o
  health check do Render continua em `/auth/regras-senha`). E-mail diário: a marca do dia (`erros_avisados`) só depois de
  enviar; só superadmin confirmado e ativo; precisa de provedor configurado. Tarefa que falha fica `{erro: "Tipo"}` no
  resumo e a linha de comando sai com 1 (`/interno/tarefas` continua 200). Visão: "pausada" = atrasada há mais de 7 dias;
  conversão só de contas com teste criadas de 60 a 15 dias atrás; "testes acabando" sem conta com assinatura ativa; a
  tabela de contas só a partir de 1280 px (lista abaixo disso). Fica para depois: falha de uma conta dentro de uma tarefa
  (o robô captura e segue) continua só no log.
- Junção: os três ramos entraram no `main` sem conflito de código (só dois testes do site com o mesmo nome; o da C virou
  `etapa5hPlataformaLogica.test.ts`). Teste integrado (pilha local): "Criar planos para 11 empresas" criou os planos e levou
  ao quadro; Tom parcial com "Analisar os N que faltam"; Plataforma com Visão geral e Erros (mensagem e local limpos);
  conta nova com "Comece por aqui", modal da marca e modo exemplo; pesquisa no celular em duas linhas e sem "Começar".
