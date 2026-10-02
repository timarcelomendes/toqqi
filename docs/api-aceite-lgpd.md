# Toqqi · Aceite dos termos e da política de privacidade (LGPD) e aviso de cookies

Mesmas convenções das etapas anteriores (base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, RLS por conta).
Pedido do Marcelo em 02/10 (10:31): aceite de LGPD logo depois de entrar na ferramenta, falando também de cookies.
Respostas dele: **tela que bloqueia** (só usa depois de aceitar; a outra saída é "Sair"); cookies num **aviso na mesma tela**,
sem botão de recusar, porque não há nada opcional; e **rascunho completo** dos Termos de uso e da Política de privacidade
(hoje provisórios), marcado como versão 1 e para revisão de um advogado.

## 0. Decisões
- Uma versão só para os dois documentos: `VERSAO_DOCUMENTOS = 1` (API, `toqqi/modulos/acesso/termos.py`) e o mesmo número em
  `web/src/modulos/geral/legal/versao.ts`, com a data da versão (02/10/2026). Mudar o texto de forma relevante = subir os dois
  juntos no mesmo commit; todo mundo vê a tela de novo na próxima vez que abrir o Toqqi.
- O bloqueio é **no site** (guarda de rotas). A API registra e informa o aceite, mas não recusa as outras rotas de quem não
  aceitou (as integrações usam token próprio e não passam por aqui). O que vale como prova é o registro (quem, quando, versão, IP,
  navegador), guardado no banco e na auditoria.
- Quem cria a conta já marca "Li e aceito" no cadastro: esse aceite passa a ser **gravado** (origem `cadastro`), e a pessoa não vê
  a tela de novo. Convidados, contas antigas e o superadmin veem a tela na primeira vez que entrarem.
- Cookies: o Toqqi não usa cookies. Guarda no navegador só o necessário (sessão, tema, menu recolhido, passos do painel ocultos,
  avisos de cobrança fechados, conversa do assistente). Pela LGPD isso dispensa consentimento, mas precisa ser informado: o aviso
  fica na tela de aceite e numa seção "Cookies e armazenamento no navegador" da política.
- A fonte Plus Jakarta Sans passa a ser servida pelo próprio site (pacote `@fontsource`), em vez do Google Fonts: assim o
  navegador de quem usa o Toqqi não manda o IP ao Google, e o aviso de "nenhum terceiro" fica verdadeiro.

## 1. Banco (migração `0010_aceites`)
Tabela nova `aceites_termos` (conta_id DEFAULT app_conta(), ENABLE + FORCE RLS, política padrão, grants condicionais, como as
outras): `id bigint, conta_id, usuario_id` (aceita nulo; FK composta `(usuario_id, conta_id)` para usuarios com
`ON DELETE SET NULL (usuario_id)`, sintaxe do Postgres 15+), `usuario_email citext NOT NULL` e `usuario_nome text NOT NULL`
(cópias do momento do aceite), `versao int` (≥ 1), `aceito_em timestamptz` default now(), `ip text`, `agente text` (até 400
caracteres, cortado), `origem text` CHECK in ('cadastro','tela'). Único `(usuario_id, versao)`: aceitar de novo a mesma versão
não cria linha (devolve a existente); o índice do único já atende a busca da maior versão aceita. Índice
`aceites_termos_conta_idx (conta_id)`, como as outras tabelas.
Nada é apagado quando o texto muda; o histórico fica. **A prova não some quando um membro é removido em Equipe**: a linha fica,
com `usuario_id` nulo e o e-mail e o nome guardados. A exclusão da conta inteira (Plataforma) continua apagando tudo
(`conta_id` ON DELETE CASCADE). A coluna `contas.termos_versao` fica só como registro da versão aceita no cadastro da conta,
gravada com `str(VERSAO_DOCUMENTOS)` (uma fonte só da versão).

## 2. Rotas
`Aceite` = `{versao_atual: int, versao_aceita: int|null, aceito_em: iso|null, pendente: bool}` — `versao_aceita` é a maior versão
aceita; `pendente` = `versao_aceita` é null ou menor que `versao_atual`.
- `GET /eu` → `usuario` ganha `aceite: Aceite`. Se a resposta de `POST /auth/entrar` traz o usuário, ele vem com `aceite` também,
  e a resposta de `PATCH /eu` (o usuário alterado) também traz `aceite`. (Calcular só nessas rotas, não na leitura do contexto
  feita a cada requisição.)
- `POST /eu/aceite` (qualquer usuário logado, inclusive superadmin), corpo `{versao: int}` → 200 `Aceite`.
  - `versao` 0 ou negativa (ou acima de 1.000.000) → 422 de validação (`dados_invalidos`, campo `versao`).
  - `versao` ≥ 1 e diferente de `VERSAO_DOCUMENTOS` → 409 `versao_desatualizada`, "Os termos foram atualizados. Recarregue a
    página para ver a versão nova." (o site recarrega `/eu` e mostra a tela de novo).
  - Grava `ip` (mesma função `_ip` das rotas de acesso), `agente` (User-Agent), o e-mail e o nome do usuário, origem `tela`;
    auditoria `termos_aceitos`
    `{versao}` (só na primeira vez de cada versão). Idempotente.
- `POST /auth/cadastro`: com `aceite_termos: true` (já obrigatório), grava o aceite da versão atual para o usuário criado
  (origem `cadastro`, mesmo IP e agente), na mesma transação, e a auditoria `termos_aceitos` `{versao, origem: "cadastro"}`.
- Limite: `POST /eu/aceite` 20 por minuto por usuário (o mesmo mecanismo de limite já usado na API). A chave é o id do usuário
  só quando o token tem assinatura válida; um token forjado com o id de outra pessoa conta pelo IP e não bloqueia o dono do id.

## 3. Site
- **Tela "Antes de continuar"** (`/aceite`, layout de acesso, exige estar logado; título da aba "Termos e privacidade"):
  - Logo, título "Antes de continuar", parágrafo curto: "Para usar o Toqqi, leia e aceite os Termos de uso e a Política de
    privacidade. Eles explicam como tratamos os seus dados e os dos seus clientes, seguindo a LGPD." Se `versao_aceita` não é
    null (é uma versão nova): "Atualizamos os Termos de uso e a Política de privacidade em {data da versão}." em vez da primeira frase.
  - Três itens curtos (ícone + uma linha): o que coletamos e para quê; a sua empresa é a controladora dos dados dos clientes dela
    e o Toqqi é o operador; os seus direitos (acesso, correção, exclusão) e o contato `privacidade@toqqi.com`.
  - Caixa **Cookies**: "Não usamos cookies de publicidade nem de análise. Guardamos no seu navegador só o necessário para o Toqqi
    funcionar: a sessão, o tema e preferências da tela. Por isso não há o que recusar." + link "Saiba mais" para
    `/privacidade#cookies`.
  - Caixa de seleção "Li e aceito os [Termos de uso] e a [Política de privacidade]." (links abrem em nova aba).
  - Botões **Aceitar e continuar** (primário; desabilitado até marcar a caixa; com carregando) e **Sair** (secundário; encerra a
    sessão como o "Sair" do menu; enquanto sai, "Aceitar" fica desabilitado). O corpo enviado é sempre `{versao:
    VERSAO_DOCUMENTOS}` de `legal/versao.ts` (a versão do texto que o site mostra), nunca a `versao_atual` vinda da API. Erro
    de rede: aviso na tela, botão volta a funcionar. 409: mostra a mensagem da API, desmarca a caixa e recarrega `/eu`; se a
    `versao_atual` da API for maior que a do site (o site em uso é anterior aos textos novos), o botão "Aceitar e continuar" vira
    **"Recarregar a página"** (`location.reload()`).
  - Versão nova (`versao_aceita` não nulo) e permissão `assinatura.gerenciar`: abaixo dos botões, linha pequena "Não concorda?
    Você pode [cancelar a assinatura]." (link para `/assinatura`).
  - Aceitou: atualiza o usuário na store e vai para o endereço que a pessoa queria (query `de`), ou `/inicio`. O `de` passa
    pela mesma função do "voltar" de Entrar (`destinoSeguro` em `utils/validacao.ts`: começa com `/`, sem `//` nem `\` em
    lugar nenhum, sem caracteres de controle), e `/aceite` não vale como destino.
  - Na store, `atualizarUsuario` (usado depois do `PATCH /eu`) mescla com o usuário atual e mantém o `aceite` quando a
    resposta não traz.
- **Guarda de rotas**: logado com `aceite.pendente` → qualquer rota do app (meta `logado`) vai para `/aceite?de=<caminho>`.
  Ficam livres: `/aceite`, `/termos`, `/privacidade`, `/confirmar-email`, `/redefinir-senha` e `/assinatura` (para o
  administrador poder cancelar sem aceitar a versão nova: o CDC não permite condicionar o cancelamento ao aceite; a rota continua
  exigindo a permissão `assinatura.gerenciar`). Sem pendência, `/aceite` vai para `/inicio`. O assistente flutuante e os avisos
  de cobrança não aparecem na tela de aceite (ela não usa o `AppLayout`); em `/assinatura` o `AppLayout` aparece normalmente, e
  os links do menu para outras telas voltam ao aceite pela guarda.
- **Termos de uso e Política de privacidade** (`/termos`, `/privacidade`): substituem o texto provisório. Conteúdo em
  `web/src/modulos/geral/legal/termos.ts` e `privacidade.ts` como dados estruturados (seções com `id`, título e parágrafos/listas),
  desenhados pelo `DocumentoLegalView`: título, "Versão 1 · vigente desde 02/10/2026", sumário com links para as seções, seções
  com âncora (`/privacidade#cookies` rola até a seção), botão Voltar como hoje. Sem `v-html` (texto puro; links como dados).
  A faixa "Rascunho para revisão jurídica" **não** aparece para o público; os pontos a confirmar ficam como `[a confirmar: ...]`
  no texto, para o Marcelo achar e trocar (razão social, CNPJ, endereço, foro).
- **Minha conta**: cartão "Privacidade" com "Você aceitou os Termos de uso e a Política de privacidade (versão N) em dd/mm/aaaa
  às hh:mm." e os dois links.
- **Auditoria**: nome do evento `termos_aceitos` = "Aceitou os termos e a política de privacidade" (vem pronto da API em
  `rotulo`; o site só acrescenta " no cadastro" quando `detalhe.origem === 'cadastro'`).
- **Fonte**: remover os `<link>` do Google Fonts de `index.html` (e de onde mais houver) e importar a Plus Jakarta Sans de
  `@fontsource/plus-jakarta-sans` (pesos 400, 500, 600, 700, 800, subconjunto latin) no ponto de entrada de cada página que usa a
  fonte. Nenhuma requisição a `fonts.googleapis.com`/`fonts.gstatic.com` ao abrir o site.
- Tudo no celular (390 px) e no computador, claro e escuro, sem erros no console.

## 4. Conteúdo dos documentos (fatos que os textos precisam cobrir)
Português claro, frases curtas, sem juridiquês desnecessário; quem lê é o dono de uma pequena ou média empresa.
- **Quem**: Toqqi, plataforma de pesquisas de satisfação (NPS e CSAT). Razão social, CNPJ e endereço `[a confirmar]`. Contato
  geral `contato@toqqi.com`; encarregado de dados (DPO) pelo e-mail `privacidade@toqqi.com` (nome `[a confirmar]`).
- **Papéis (LGPD)**: dados de quem usa o Toqqi (nome, e-mail, cargo, telefone, senha guardada só como hash (argon2id), IP, navegador, registros de acesso e
  auditoria, dados de cobrança da empresa) → Toqqi é **controlador**. Dados dos clientes que a empresa importa e pesquisa (nome,
  e-mail, telefone, empresa, cargo, valor do contrato, respostas, notas e comentários) → a empresa assinante é **controladora** e o
  Toqqi é **operador**, tratando só conforme as instruções dela (os Termos funcionam como acordo de tratamento de dados). Cabe à
  empresa ter base legal para contatar os clientes e atender os pedidos deles; o Toqqi ajuda (descadastro, exclusão de contato).
- **Para quê**: prestar o serviço (envios por e-mail e WhatsApp, lembretes, relatórios, planos de ação), segurança e prevenção a
  fraude, cobrança, suporte, obrigações legais, e-mails do sistema (confirmação, resumo semanal e alertas, que podem ser desligados
  em Minha conta). Não vendemos dados; sem publicidade.
- **Bases legais** (art. 7º): execução de contrato; cumprimento de obrigação legal; legítimo interesse (segurança, melhoria);
  exercício de direitos. Para os dados dos clientes da empresa, a base é definida pela empresa controladora.
- **Inteligência artificial**: com a IA ligada (Configurações › IA), o texto do comentário (até 500 caracteres), as opções
  marcadas e a nota vão à OpenAI para classificar temas e sentimento; no assistente vão a pergunta, as últimas mensagens e os dados
  consultados, que podem incluir nomes e comentários. Sem guardar na OpenAI para treino (`store: false`). A empresa pode desligar a
  análise.
- **Operadores (suboperadores)** e onde ficam: Render (hospedagem e banco, EUA), OpenAI (IA, EUA), Asaas (cobrança, Brasil),
  ZeptoMail/Zoho (envio de e-mails), Meta (WhatsApp Cloud API, quando a empresa conecta o WhatsApp), GitHub (agendamento das
  tarefas, sem dados pessoais), ViaCEP (consulta de CEP feita pelo navegador; só o CEP). **Transferência internacional** (art. 33):
  para EUA, com cláusulas contratuais e garantias dos fornecedores.
- **Retenção**: dados da conta enquanto ela estiver ativa; depois do cancelamento, `[a confirmar: prazo, sugerido 90 dias]` para
  exportação e então exclusão, salvo o que a lei obriga a guardar (registros de acesso por 6 meses, Marco Civil art. 15; dados
  fiscais pelo prazo legal). Respostas e contatos: a empresa controla e pode apagar.
- **Segurança**: senhas com hash, conexão cifrada (HTTPS), separação dos dados de cada empresa no banco (RLS), segredos cifrados,
  registro de auditoria, controle de acesso por perfil. Incidentes: comunicação à empresa e à ANPD quando a lei exigir.
- **Direitos do titular** (art. 18): confirmação, acesso, correção, anonimização/bloqueio/eliminação, portabilidade, informação
  sobre compartilhamento, revogação do consentimento, petição à ANPD. Como pedir: `privacidade@toqqi.com`; prazo de resposta
  `[a confirmar: 15 dias]`. Cliente de uma empresa assinante: o pedido vai para a empresa; se chegar ao Toqqi, encaminhamos.
- **Cookies e armazenamento no navegador** (seção com `id: "cookies"`): não usamos cookies nem rastreadores de publicidade ou
  análise; nenhum terceiro coloca cookies pelo Toqqi; tabela com o que fica no navegador: `toqqi.sessao` (sessão; localStorage se
  marcar "Lembrar de mim neste aparelho", senão sessionStorage), `toqqi.tema`, `toqqi.menu-recolhido`, passos ocultos do painel, `toqqi.avisos-fechados`
  (sessionStorage), `toqqi.assistente.*` (conversa do assistente, sessionStorage, some ao fechar a aba). Todos necessários; dá para
  apagar pelo navegador (o efeito é sair da conta e perder as preferências). A página da pesquisa respondida pelos clientes não
  guarda nada além do necessário para enviar a resposta `[o agente de conteúdo confere no código de web/src/pesquisa]`.
- **Termos de uso** cobrem: o serviço e os planos (Essencial, Profissional, Empresa; teste grátis; cobrança mensal pelo Asaas; atraso
  → 7 dias e depois pausa dos envios; cancelar vale até o fim do período pago); uso aceitável (sem spam: só contatos com relação de
  cliente, respeitar o descadastro; sem conteúdo ilegal); responsabilidades da empresa como controladora; acordo de tratamento de
  dados (operador, instruções, suboperadores, sigilo, incidentes, devolução e exclusão no fim); disponibilidade sem garantia de
  100%; limitação de responsabilidade `[a confirmar]`; propriedade intelectual; suspensão por violação; mudanças nos termos
  (aviso e novo aceite na tela); lei brasileira e foro `[a confirmar: comarca]`.
