# Toqqi · Etapa 5i (desfecho, saúde da conta e "Pesquisa feita com Toqqi")

Pedido do Marcelo, depois da análise crítica: o Toqqi deixa de ser só "ferramenta de NPS" e passa a ser **ferramenta de
retenção que prova resultado**, mais um canal de aquisição barato. Três frentes, cada uma uma construção em paralelo:
**A** desfecho (§2), **B** saúde da conta (§3), **C** menção "Pesquisa feita com Toqqi" e origem do cadastro (§4). Mesmas
convenções das etapas anteriores (base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, RLS com `em_conta` /
`modo_sistema`, `requer(...)`, dias de São Paulo por `core.relogio`, NPS e percentuais com meio para cima, design-system,
claro e escuro, 360 a 1440 px, nada de `v-html`). Uma migração só, `0018_desfecho_saude_origem`, feita no **passo 0**
(§11) antes de abrir os três worktrees.

## 0. Decisões
- **Três estados da empresa**, sem coluna nova de estado: **ativa** (`ativa` true), **pausada** (`ativa` false, sem perda:
  fora das pesquisas por outra razão, como hoje) e **perdida** (`perdida_em` preenchida; o banco obriga `ativa` false).
  Perdida = deixou de ser cliente. Como já é inativa, sai sozinha de tudo que hoje usa "só ativas" (painel, relatórios,
  receita em risco, planos para detratores, oportunidades). As inativas que já existem continuam pausadas: não temos como
  saber se saíram nem quando.
- **Perda desativa os contatos** da empresa. Hoje os envios olham `contatos.ativo` e não `empresas.ativa`, então desativar
  os contatos é o que garante que nenhuma pesquisa sai, e eles também deixam de contar no limite do plano. Os ids ficam
  na linha da perda; "Voltou a ser cliente" reativa os mesmos (padrão ligado). Contato **ativo** em empresa perdida é
  recusado pelo banco (gatilho, `TQ409` → 409 `empresa_perdida`).
- **Histórico** (`empresa_historico`) gravado por **gatilho no banco**: toda criação de empresa, mudança de valor mensal,
  perda, edição da perda e retorno, venha da tela, da importação, da API ou de outro caminho. A origem e o usuário vêm
  da transação (`app.empresa_origem`, `app.usuario_id`, `app.hoje`; sem eles: `sistema`, nulo e o dia do banco).
- **Retenção de receita** conta os contratos **não perdidos** (ativos e pausados): pausar só tira das pesquisas, não é
  perda. A carteira de cada empresa é reconstruída pelo histórico. A migração grava uma linha `entrada` para as empresas
  **ativas** que já existem (data = criação, valor = o de hoje). Por isso, períodos anteriores à migração mostram o aviso
  "histórico parcial". As pausadas que já existem só entram na retenção a partir da primeira mudança registrada.
- **Saúde da conta**: só para empresas **ativas**, calculada na hora em SQL (sem tarefa, sem IA), com parâmetros fixos
  no código. **Sem dados nunca é Risco.** A renovação próxima só ganha **destaque**: não muda a nota.
- **Regra de ouro do Crescimento passa a excluir empresas em Risco.** O Risco junta sinais que o detrator de 90 dias não
  pega (decisor calado, NPS em queda, convites sem resposta, planos atrasados), e oferecer mais para uma conta nesse
  estado queima a relação. Atenção e Sem dados continuam podendo receber oferta. Na prática as listas quase não mudam,
  porque "Pode crescer" já pede NPS ≥ 0 e "Promotores", promotor nos últimos 30 dias.
- **Quem vê a saúde**: hoje **não existe** restrição por carteira (um usuário com `contatos.ver` vê todas as empresas).
  A saúde segue a mesma regra e exige ainda acesso a números: `contatos.ver` **e** (`painel.ver` ou `relatorios.ver`),
  porque os porquês citam notas. Sem isso, o campo `saude` vem nulo e a coluna some. Restringir por carteira é outra
  etapa (§12).
- **Menção "Pesquisa feita com Toqqi"**: na página da pesquisa (perguntas e tela final, inclusive no link público e no
  botão incorporado) e nos e-mails de convite, lembrete, teste e agradecimento (o agradecimento tem o mesmo layout e
  vai ao mesmo público). Fica fora dos e-mails do sistema e do **WhatsApp**: a mensagem é texto da conta, e um link a
  mais tem cara de spam. Pode ocultar: `cortesia`, ou plano `empresa` em `ativa` ou `atrasada`. Nos demais casos ela
  aparece sempre, então se a conta trocar de plano para baixo a linha volta sozinha, porque a regra é calculada na hora
  de mostrar. A escolha salva é mantida, e se a conta voltar ao plano Empresa a linha some de novo.
- **Origem do cadastro**: só `utm_source`, `utm_medium` e `utm_campaign`, limpos, em minúsculas, sem dados pessoais
  (§4.3). O site guarda a origem no `sessionStorage` (não é cookie). Sobe a versão dos documentos para **7** (§9).
- Nada desta etapa gasta a cota de IA, salvo as perguntas ao ToqqiAI (como hoje).

## 1. Banco: migração `0018_desfecho_saude_origem` (passo 0)
`down_revision = "0017_erros"`. Escrita e testada no passo 0, junto com `modelos.py` e o mapeamento do `TQ409` em
`core/errors.py`.

**`empresas`** ganha:
- `renovacao_em date` (renovação ou fim do contrato; passado permitido), `perdida_em date`,
  `motivo_perda text CHECK IN ('preco','concorrente','atendimento','produto','encerrou','outro')` e
  `motivo_detalhe text CHECK (length ≤ 300)`.
- `CONSTRAINT empresas_perda_check CHECK ((perdida_em IS NULL AND motivo_perda IS NULL AND motivo_detalhe IS NULL) OR
  (perdida_em IS NOT NULL AND motivo_perda IS NOT NULL AND NOT ativa))`.
- Índices: `empresas_renovacao_idx (conta_id, renovacao_em) WHERE renovacao_em IS NOT NULL AND perdida_em IS NULL` e
  `empresas_perdidas_idx (conta_id, perdida_em) WHERE perdida_em IS NOT NULL`.

**`empresa_historico`** (padrão da 0013: `conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas ON DELETE
CASCADE`, ENABLE + FORCE RLS, política `isolamento_conta`, grants condicionais ao papel):
`id bigserial`, `empresa_id bigint NOT NULL` (FK `(empresa_id, conta_id) → empresas(id, conta_id) ON DELETE CASCADE`),
`tipo text CHECK IN ('entrada','valor','perdida','reativada')`, `data date NOT NULL` (o dia que vale para os cálculos),
`valor_antes numeric(12,2)`, `valor_depois numeric(12,2)`, `motivo` (mesmo CHECK), `motivo_detalhe` (≤ 300),
`contatos bigint[]` (só `perdida`: ids desativados), `origem text CHECK IN ('tela','importacao','api','migracao',
'sistema')`, `usuario_id bigint` (FK `(usuario_id, conta_id) → usuarios ON DELETE SET NULL (usuario_id)`),
`criado_em timestamptz DEFAULT now()`. CHECKs: `tipo = 'perdida'` ⇔ `motivo IS NOT NULL`; `contatos` só em `perdida`;
`tipo <> 'valor' OR valor_antes IS DISTINCT FROM valor_depois`. Índices `(conta_id, empresa_id, data, id)` e
`(conta_id, data) WHERE tipo = 'perdida'`; o do SET NULL do usuário como na 0013. O papel da aplicação tem SELECT e
INSERT, e UPDATE só para a edição da perda (o gatilho faz); **sem DELETE nem TRUNCATE** (as linhas saem em cascata
com a empresa ou a conta).

**Gatilho `empresas_historico`** (AFTER INSERT OR UPDATE OF valor_mensal, perdida_em, motivo_perda, motivo_detalhe ON
empresas). `hoje` = `app.hoje` ou o dia do banco em São Paulo; `origem` = `app.empresa_origem` ou `sistema`; `usuario`
= `app.usuario_id` ou nulo (também nulo se o usuário não é da conta da empresa, como a equipe Toqqi pela Plataforma).
- INSERT: `entrada` (data hoje, `valor_depois` = valor). Se já nasce perdida (só pela API), uma `perdida` em seguida, e
  a `entrada` fica com a menor entre hoje e `perdida_em` (para não vir depois da perda na ordem `data, id`).
- UPDATE, nesta ordem:
  - perdida_em nula → preenchida: `perdida` (data = `perdida_em`, `valor_antes` = OLD.valor, a carteira logo antes;
    motivo, detalhe, `contatos` = `app.contatos_desativados`, ids separados por vírgula, como `"7,8"` (chaves
    aceitas), ou vazia). O GUC vale a transação inteira: quem perde duas empresas na mesma transação troca o valor
    antes de cada uma.
  - preenchida → nula: `reativada` (data hoje, `valor_antes` = OLD.valor, `valor_depois` = NEW.valor). Mudar o valor
    no mesmo UPDATE **não** gera também uma linha `valor`.
  - perdida nos dois e data/motivo/detalhe mudaram: atualiza a última `perdida` da empresa. Perdida nos dois e só o
    valor mudou: **nada** (uma linha `valor` com a carteira em zero quebraria a ponte; o valor novo aparece no
    `valor_antes` da `reativada`).
  - senão, valor mudou: `valor` (data hoje, antes, depois).
- A empresa sem nenhuma linha (pausada antiga) ganha antes uma `entrada` com OLD.valor e data = a menor entre hoje e a
  data do evento.

**Gatilho `contatos_empresa_perdida`** (BEFORE INSERT OR UPDATE OF ativo, empresa_id ON contatos): `NEW.ativo` com uma
empresa que tem `perdida_em` → `RAISE ... USING ERRCODE = 'TQ409'`. `core/errors.py` traduz para 409 `empresa_perdida`,
"Esta empresa foi marcada como perdida. Para voltar a pesquisar este contato, marque “Voltou a ser cliente” na empresa."

**Outros**:
- `webhooks.eventos`: o CHECK ganha `'empresa.perdida','empresa.reativada'` (como a 0012).
- `config_envios.ocultar_mencao_toqqi boolean NOT NULL DEFAULT false`.
- `contas.origem jsonb` nula, com CHECK: é objeto não vazio, as chaves estão em `{utm_source, utm_medium,
  utm_campaign}` e cada valor é texto `^[a-z0-9._-]{1,60}$` (`jsonb_path_exists`, como os passos da 0013).
- Índice `convites_empresa_recentes_idx (conta_id, empresa_id, criado_em DESC) WHERE empresa_id IS NOT NULL` (saúde;
  o nome `convites_empresa_idx` já existe desde a 0015, só por `empresa_id`, para o SET NULL da exclusão, e fica). Outros
  índices ficam a critério de quem constrói, provados pelo teste de desempenho (§10).
- Semente, em modo sistema: uma linha `entrada` por empresa **ativa** (data = `criada_em` em São Paulo, `valor_depois`
  = `valor_mensal`, origem `migracao`).

**Down** (funcional, testado): apaga os gatilhos, as funções e `empresa_historico`. Apaga as entregas e os webhooks só
com os eventos novos e tira os eventos dos outros (como a 0012). Volta o CHECK, apaga o índice dos convites e as
colunas de `empresas`, `config_envios` e `contas`. As empresas perdidas ficam inativas.

A exportação de todos os dados (`dados/exportacao.py`) passa a incluir a tabela nova (A). `apagar_conta` (plataforma)
**não** a põe em `_ORDEM_EXCLUSAO`: sem DELETE para o papel, ela sai em cascata quando `Empresa` é apagada (o
`test_etapa5i_migracao` prova pela exclusão da empresa).

## 2. Desfecho (A)

### 2.1 Empresa (JSON e edição)
- O JSON da empresa (`_json`: lista, detalhe, criar, alterar) ganha `renovacao_em`, `situacao` (`ativa` | `pausada` |
  `perdida`), `perdida_em`, `motivo_perda`, `motivo_perda_rotulo` e `motivo_detalhe`.
- Rótulos dos motivos: `preco` "Preço", `concorrente` "Foi para um concorrente", `atendimento` "Atendimento ou
  qualidade", `produto` "O produto não atendeu", `encerrou` "Encerrou a atividade", `outro` "Outro".
- `EmpresaIn` e `EmpresaAlterarIn` aceitam `renovacao_em` (de 2000 a 2100). `PATCH` com `ativa: true` numa perdida dá
  409 `empresa_perdida` ("Use “Voltou a ser cliente”."). Os campos de perda não entram no PATCH.
- Toda escrita de empresa marca a origem antes (`empresas/historico.py: marcar(s, origem, usuario_id)`, com
  `set_config(..., true)` e `app.hoje = relogio.hoje()`): tela = `tela`, importação = `importacao`, chave de
  integração = `api`.

### 2.2 Rotas novas (`empresas/rotas.py`, no fim; serviço em `empresas/desfecho.py`)
- `POST /empresas/{id}/perda` (`contatos.editar`), corpo `{perdida_em: date = hoje, motivo_perda, motivo_detalhe}`.
  Valida `perdida_em` ≤ hoje, ≥ `cliente_desde` (se houver) e ≥ a data da última linha `entrada`/`valor`/`reativada`
  (senão a ordem do histórico quebraria); `motivo_detalhe` é obrigatório (3+ letras) com `outro`. Grava `ativa` =
  false, os campos da perda e desativa os contatos ativos da empresa (o gatilho guarda os ids). Também enfileira o
  webhook `empresa.perdida` e registra a auditoria `empresa_perdida`. Devolve a empresa + `contatos_desativados`.
  Erros: 404; 409 `ja_perdida`; 422 `dados_invalidos` com `campos`.
- `PATCH /empresas/{id}/perda` (`contatos.editar`): corrige data, motivo ou detalhe (mesmas validações). 409
  `nao_perdida`. Sem webhook. Auditoria `empresa_perdida` com `{corrigida: true}`.
- `POST /empresas/{id}/retorno` (`contatos.editar`), corpo `{valor_mensal?: Valor|null, renovacao_em?: date|null,
  reativar_contatos: bool = true}` (ausente = mantém). Limpa a perda, `ativa` = true e reativa os contatos guardados na
  última perda que ainda existem, estão inativos e são desta empresa. Webhook `empresa.reativada`, auditoria
  `empresa_reativada`. Devolve a empresa + `contatos_reativados`. Erros: 409 `nao_perdida`; 402 `limite_do_plano`
  (nada muda).
- `GET /empresas/{id}/historico` (`contatos.ver`) → `{itens: [{id, tipo, data, valor_antes, valor_depois, motivo,
  motivo_rotulo, motivo_detalhe, contatos: n|null, origem, usuario: {id, nome}|null, criado_em}]}`, até 200, do mais
  recente para o mais antigo (data, depois id).

### 2.3 Contatos de empresa perdida
- Contatos (tela): criar ou alterar um contato **ativo** numa empresa perdida dá 409 `empresa_perdida` (pelo gatilho).
- Importação de contatos: a linha que criaria ou reativaria um contato de empresa perdida grava o contato **inativo**
  e o plano ganha o aviso "N contatos de empresas perdidas ficam inativos: A, B e mais 3." O limite do plano conta
  certo.
- `POST /integracao/pesquisas` e `/csat`: se a empresa achada está perdida, não cria contato e devolve
  `situacao: "ignorado_empresa_perdida"`, "A empresa foi marcada como perdida."

### 2.4 Importação
- Campo novo `renovacao_em` "Renovação do contrato" (depois de `cliente_desde`, também no modelo CSV), com os nomes
  `renovacao`, `renovacao_em`, `data_renovacao`, `renovacao_contrato`, `vencimento_contrato`, `fim_contrato`,
  `fim_do_contrato` e `vigencia_ate`. Lido com `interpretar_data` ("Data inválida em renovação do contrato (use
  dd/mm/aaaa)."). Segue a regra das outras colunas da empresa (vale a primeira linha que informa; empresa existente só
  muda com "Atualizar quem já existe").
- Valor mensal mudado pela planilha entra no histórico com origem `importacao` (o gatilho faz; a importação só marca a
  origem). A planilha não marca perda nem retorno.

### 2.5 API de integração e webhooks
`POST /integracao/empresas` (chave, `LIMITE_INTEGRACAO`, `id_evento` com a mesma idempotência de 24 h da pesquisa),
corpo `{codigo_externo?, documento?, nome?, valor_mensal?, renovacao_em?, cliente_desde?, situacao?: "ativa"|"perdida",
perdida_em?, motivo_perda?, motivo_detalhe?, id_evento?}`:
- Procura por código externo, depois documento, depois nome (como `pesquisas._empresa`). Se não achar e vier `nome`,
  cria a empresa (201); se não achar e não vier nome, 404 `empresa_nao_encontrada`. Sem nenhum dos três, 422.
- Campo ausente = não muda; `null` limpa `valor_mensal`, `renovacao_em` e `cliente_desde`.
- `situacao: "perdida"` numa ativa ou pausada = perda (§2.2; sem `motivo_perda`, 422; `perdida_em` padrão hoje). Numa
  que já está perdida, corrige a perda se vierem data, motivo ou detalhe.
- `situacao: "ativa"` numa perdida = retorno, com contatos reativados (402 se passar do limite). Numa pausada,
  `ativa` = true.
- Resposta 200/201: `{empresa: {id, nome, documento, codigo_externo, valor_mensal, renovacao_em, cliente_desde,
  situacao, perdida_em, motivo_perda}, criada, mudancas: ["valor_mensal", …]}`. Auditoria da perda e do retorno com
  `{origem: "api"}` e sem usuário.
- Webhooks: `EVENTOS` ganha `empresa.perdida` e `empresa.reativada`, enfileirados na mesma transação (tela e API). Os
  `dados` levam `{id, nome, documento, codigo_externo, valor_mensal, renovacao_em, origem}`, mais
  `{perdida_em, motivo_perda, motivo_detalhe, contatos_desativados}` na perda e `{contatos_reativados}` no retorno.
- Integrações (site): a documentação na tela ganha a rota, o exemplo e os dois eventos (rótulos em `utils/rotulos.ts`,
  `ModalWebhook`, `SecaoWebhooks`).

### 2.6 Relatórios › Desfecho (`relatorios.ver`)
`GET /relatorios/desfecho?de&ate&grupo_id&segmento_id&responsavel_id&faixa_valor&tempo_cliente`. São os filtros
comuns e os de empresa da 4b, sobre os dados atuais da empresa; `so_ativos` não se aplica (as perdidas são inativas).
Valida `de` ≤ `ate` (422). O fim é `A = min(ate ou hoje, hoje)`; o início `D` é `de`, ou, sem `de`, a menor `data` do
histórico das empresas do filtro. Resposta:
```
{ periodo: {de: D, ate: A},
  perdidas: {empresas, receita_mensal, sem_valor,
             itens: [{empresa: {id, nome}, perdida_em, motivo, motivo_rotulo, motivo_detalhe, valor_mensal,
                      responsavel: {id, nome}|null, antes, ultima_nota: {nota, data}|null, plano_antes}]},
  motivos: [{motivo, rotulo, empresas, receita_mensal}],
  antes_de_sair: {perdidas: {total, detrator, neutro, promotor, sem_resposta, percentuais: {…}},
                  carteira: {total, detrator, neutro, promotor, sem_resposta, percentuais: {…}},
                  amostra_pequena},
  retencao: {inicio: {data, empresas, receita, sem_valor}, perdida, reducao, aumento, fim,
             novas: {empresas, receita}, grr, nrr, historico_parcial} | null }
```
Regras (estado de uma empresa num instante = a última linha do histórico com `data` antes daquele dia, na ordem
`data, id`; `entrada`, `valor` e `reativada` = não perdida, com `valor_depois`; `perdida` = perdida; sem linha = não
existia):
- **Perdidas no período**: empresas com `perdida` de `data` em [D, A] **e** perdidas em A (quem voltou dentro do período
  não conta). `receita_mensal` = soma do `valor_antes` dessas perdas; `sem_valor` = as perdidas sem valor. Itens até
  500, mais recentes primeiro.
- **Motivos**: os 6, na ordem, com zeros.
- **Antes de sair** (por empresa, pela pior nota): `detrator` se teve resposta NPS de detrator (não arquivada) nos 90
  dias até a perda (de `perdida_em − 89` a `perdida_em`); senão `neutro` se teve neutro; senão `promotor`; senão
  `sem_resposta`. `ultima_nota` = a última NPS nessa janela. `plano_antes` = alguma ação criada para a empresa nessa
  janela. A **carteira** é a comparação: empresas ativas e não perdidas do filtro, mesma regra, nos 90 dias até A.
  `percentuais` com 1 casa (null com total 0); `amostra_pequena` = menos de 5 perdidas.
- **Retenção**: C = empresas não perdidas e com valor > 0 no início de D (`sem_valor` conta as não perdidas sem valor).
  `inicio.receita` = Σ valor em D. Para cada empresa de C, o estado em A:
  - perdida → `perdida += valor_D`;
  - não perdida → `Δ = valor_A − valor_D` (com `valor_A` nulo, Δ = 0): `reducao += max(0, −Δ)` e
    `aumento += max(0, Δ)`.
  - `fim` = inicio − perdida − reducao + aumento.
  - `novas` = empresas fora de C com `entrada` ou `reativada` em [D, A], não perdidas e com valor em A (só informação:
    ficam fora da GRR e da NRR).
  - **GRR** = (inicio − perdida − reducao) ÷ inicio.
  - **NRR** = (inicio − perdida − reducao + aumento) ÷ inicio.
  - As duas em %, com 1 casa, ou null se a receita do início for 0; `retencao` é null se não há histórico.
  - `historico_parcial` = D é anterior ao dia (São Paulo) em que foram criadas as linhas `migracao` da conta.
- `GET /relatorios/desfecho.csv` (+ `painel.exportar`): `Empresa;Perdida em;Motivo;Detalhe;Valor mensal;Responsável;
  Grupo;Antes de sair;Última nota;Data da última nota;Plano de ação antes`.
- Desempenho: < 1 s com 1.000 empresas, 20.000 linhas de histórico e 50.000 respostas.

**Exemplo (vira teste)**, período 01/01/2026 a 31/03/2026, todas com `entrada` em 2025:
- E1: 10.000, perdida em 15/02 (preço).
- E2: 5.000, vai a 3.000 em 10/03.
- E3: 4.000, vai a 6.000 em 20/01.
- E4: 1.000, sem mudança.
- E5: 2.000, perdida em 05/01 e reativada em 25/01 com 2.500.
- E6: `entrada` em 10/02 com 3.000.
- E7: sem valor.
- E8: perdida em 20/12/2025.

Resultado:
- C = E1–E5; início 22.000 (5 empresas, `sem_valor` 1).
- Perdida 10.000, redução 2.000, aumento 2.500, fim 12.500.
- GRR = 10.000 ÷ 22.000 = **45,5%**; NRR = 12.500 ÷ 22.000 = **56,8%**.
- Novas: 1 empresa, 3.000. Perdidas no período: só E1 (1 empresa, 10.000); E5 voltou.

Antes de sair:
- P1 teve detrator 30 dias antes da perda → detrator.
- P2 teve só neutro → neutro.
- P3 sem respostas → sem resposta.
- P4 teve detrator 100 dias antes e promotor 20 dias antes → promotor (o detrator ficou fora da janela).
- Resultado: 25% em cada grupo, `amostra_pequena` true. Na carteira de 10 ativas, 2 com detrator → 20%.

### 2.7 Telas (A)
- **Tela da empresa** `/contatos/empresas/:id` (nova, `contatos.ver`; rota no `router`).
  - Cabeçalho: nome e selo da situação (Ativa, Pausada, "Perdida em dd/mm/aaaa"). Botões: "Editar" (`ModalEmpresa`),
    "Marcar como perdida" (ativa ou pausada) e "Voltou a ser cliente" (perdida), com `contatos.editar`; "Histórico de
    respostas" (`relatorios.ver` → `/relatorios/historico?empresa_id=`).
  - Blocos, de cima para baixo: **Dados** (grupo, segmento, responsável, valor mensal, cliente desde e renovação: "em
    23 dias", "hoje", "passou há 5 dias"); **Saúde da conta**, no lugar marcado `<!-- 5i-B: CartaoSaudeEmpresa -->` (B
    entrega o componente); **Contatos** (nome, cargo, perfil e situação, com link); **Linha do tempo** (o histórico:
    "12/03/2026 · Valor mensal de R$ 5.000,00 para R$ 3.000,00 · pela importação", "Perdida · Preço · “Fechou com
    outro fornecedor” · por Ana", "Voltou a ser cliente · 3 contatos reativados").
  - Estados: carregando (esqueleto), erro (alerta + "Tentar de novo"), 404 ("Empresa não encontrada." + voltar) e
    linha do tempo vazia ("Nenhuma mudança registrada ainda."). A 360 px os blocos ficam empilhados e os botões
    secundários vão para o menu "Mais".
- **Modal "Marcar como perdida"**: data (padrão hoje, no máximo hoje), motivo (6 rádios), detalhe (até 300, com
  contador, obrigatório em "Outro") e o aviso "Os N contatos ativos desta empresa ficam inativos e param de receber
  pesquisas. Ela sai do Início, das oportunidades e da carteira ativa." Botão "Marcar como perdida". A correção da perda
  usa o mesmo modal.
- **Modal "Voltou a ser cliente"**: valor mensal (preenchido), renovação e "Reativar os N contatos desativados na
  perda" (ligado). O 402 mostra a mensagem do plano com "Ver planos".
- `ModalEmpresa`: campo "Renovação do contrato" (data, opcional, com a ajuda "Usada para avisar renovações com
  risco."). Numa perdida, "Ativa" fica desligado e travado, com "Perdida em dd/mm/aaaa. Use “Voltou a ser cliente”."
  `ContatoView`: o nome da empresa vira link para a tela da empresa.
- **Relatórios › Desfecho** (`/relatorios/desfecho`, aba depois de Operação, com a descrição "Quem saiu, por quê, o que
  dizia antes e quanto da receita ficou.").
  - Filtros: período (padrão **12 meses**), grupo, segmento, responsável, faixa de valor e tempo como cliente, sem "Só
    empresas ativas".
  - Cartões: Empresas perdidas (n, a receita mensal perdida e "N sem valor"), GRR e NRR (com a fórmula em texto na
    dica), carteira no início → no fim.
  - **O que diziam antes de sair**: duas barras empilhadas (Perdidas × Carteira ativa: detrator, neutro, promotor, sem
    resposta) e a frase-prova "62% das empresas que saíram deram nota de detrator nos 90 dias antes de sair. Na
    carteira ativa, 18%." Com amostra pequena, o aviso "Poucas perdas para comparar.". A tabela ao lado é a
    alternativa acessível.
  - **Ponte da receita** (início − perdida − redução + aumento = fim) e o aviso de histórico parcial.
  - **Motivos**: barras de empresas e receita.
  - **Tabela das perdidas** (cartões no celular; o nome abre a tela da empresa).
  - No fim, o lugar `<!-- 5i-B: RenovacoesProximas -->` (B).
  - Vazio: "Nenhuma empresa perdida neste período. Quando um cliente sair, marque “Marcar como perdida” na tela da
    empresa: é assim que o Toqqi mede a retenção." "Exportar CSV" como nas outras abas.

## 3. Saúde da conta (B)

### 3.1 Regra (`modulos/saude/regras.py` puro + `calculo.py` em SQL)
Hoje = D (São Paulo). Janela atual J = [D − 179, D] ("últimos 6 meses"); anterior = [D − 359, D − 180]. As respostas
contadas são as não arquivadas da empresa (`respostas.empresa_id`). "Convite que saiu" = convite de canal `email` ou
`whatsapp` cujo envio de convite está em `SAIU_CONVITE` (a regra da taxa de resposta). Decisor = contato **ativo** com
perfil de nome "decisor" (sem diferenciar maiúsculas, como o painel). Pontos de cada critério arredondados (meio para
cima); nota = soma (0 a 100).

| Critério | Máx. | Regra |
|---|---|---|
| Satisfação | 40 | n NPS em J ≥ 1: 40 × (NPS_J + 100) ÷ 200. n = 0: 20. |
| Tendência | 10 | n ≥ 2 em J e no anterior: Δ ≥ +10 → 10; −9 a +9 → 6; ≤ −10 → 0. Senão 6. |
| Cobertura | 15 | convidados = contatos ativos com convite que saiu em J; 15 × (convidados com resposta NPS em J ÷ convidados). Sem convidados: 8. |
| Decisor | 15 | sem decisor: 7. A NPS mais recente de um decisor em J: promotor 15, neutro 9, detrator 0. Decisor sem resposta em J: 3. |
| Silêncio | 10 | dias = D − o convite mais antigo, que saiu, criado depois da última resposta (NPS ou CSAT) da empresa. Nenhum: 10; ≤ 30: 10; 31–90: 6; 91–180: 3; > 180: 0. |
| Planos | 10 | 10 − 5 × atrasados (aberto e prazo < D) − 2 × abertos de detrator ou insatisfeito não atrasados; mínimo 0. |

- **Faixas**: **Saudável** ≥ 70; **Atenção** de 45 a 69; **Risco** < 45. **Sem dados** (nota nula) = nenhuma resposta
  NPS ou CSAT, em qualquer data, e (nenhum convite que saiu, ou o primeiro com 30 dias ou menos).
- Pausada ou perdida: sem saúde (`null`).
- **Porquês** (texto e tom por critério; até 3 negativos, do que mais perdeu pontos, e só com 3+ pontos perdidos;
  depois até 2 positivos):

| Critério | Positivo | Neutro | Negativo |
|---|---|---|---|
| Satisfação | NPS ≥ 50: "NPS 67 nos últimos 6 meses (9 respostas)" | o mesmo texto entre 0 e 49; n = 0: "Sem respostas de NPS nos últimos 6 meses" | NPS < 0, mesmo texto |
| Tendência | "NPS subiu 25 pontos em relação aos 6 meses anteriores" | "NPS estável…"; sem dados: sem texto | "NPS caiu 30 pontos…" |
| Cobertura | ≥ 67%: "3 de 4 contatos convidados responderam" | 34 a 66%: o mesmo texto; sem convidados: "Nenhum contato convidado nos últimos 6 meses" | < 34%: o mesmo texto |
| Decisor | "Decisor promotor (nota 9 em 12/08/2026)" | "Decisor neutro (nota 7 em…)"; "Nenhum contato com o perfil Decisor" | "Decisor detrator (nota 4 em…)"; sem resposta em J: "Decisor não responde há 8 meses" (meses completos desde a última resposta de um decisor), "Decisor nunca respondeu" (convidado) ou "Decisor ainda não foi convidado" |
| Silêncio | — | ≤ 30 dias: "Convite recente aguardando resposta" | "Convidada há 45 dias e sem resposta desde então" (mais de 60 dias: "há 4 meses") |
| Planos | — | "1 plano de ação aberto para detrator" | "2 planos de ação atrasados" |

- **Renovação**: `renovacao: {em, dias} | null` (renovacao_em em [D, D + 60]); `destaque` = renovação nessa janela e
  faixa Atenção ou Risco. Não entra na nota.
- **Exemplos (viram teste)**, D = 05/10/2026:
  1. NPS_J 67 (4P, 2N); anterior 25 (2P, 1N, 1D) → Δ 42; 3 de 4 convidados responderam; decisor promotor; sem convite
     pendente; sem planos. Pontos 33 + 10 + 11 + 15 + 10 + 10 = **89, Saudável**.
  2. NPS_J −67 (1N, 2D); anterior 50 (1P, 1N); 2 de 5 responderam; decisor respondeu há 8 meses; convite pendente há 40
     dias; 2 planos atrasados. Pontos 7 + 0 + 6 + 3 + 6 + 0 = **22, Risco**, com os porquês "NPS −67…", "NPS caiu 117
     pontos…" e "2 planos de ação atrasados".
  3. NPS_J 50 (1P, 1N); anterior sem respostas; sem convidados em J; sem decisor; convite pendente há 100 dias; 1 plano
     aberto de detrator. Pontos 30 + 6 + 8 + 7 + 3 + 8 = **62, Atenção**.
  4. Nunca respondeu e o único convite saiu há 10 dias → **Sem dados**. Com o mesmo convite há 100 dias (dentro de J,
     sem decisor e sem planos): 20 + 6 + 0 + 7 + 3 + 10 = **46, Atenção**.
  5. Limites: 70 = Saudável, 69 e 45 = Atenção, 44 = Risco. O convite pendente há exatamente 30 dias vale 10 pontos
     de silêncio.
- Desempenho: um número fixo de consultas agrupadas por empresa (sem N+1), < 1 s com 1.000 empresas, 5.000 contatos,
  50.000 respostas e 100.000 convites.

### 3.2 Rotas (B)
Exigem `contatos.ver` e (`painel.ver` ou `relatorios.ver`), salvo onde indicado. Router novo em
`modulos/saude/rotas.py`, incluído em `main.py`. Não usar o prefixo `/saude`, que já é o health check.
- `GET /empresas/{id}/saude` → `{empresa_id, saude: {faixa, nota, criterios: [{criterio, rotulo, pontos, maximo,
  texto, tom}], porques: [{texto, tom}], renovacao, destaque, janela: {de, ate}} | null}` (`null` = pausada ou
  perdida). 404 se a empresa não é da conta.
- `GET /empresas` e `/empresas.csv` (B: assume os filtros e a ordem da lista):
  - `ativa` aceita `true|false|todas|pausadas|perdidas` (`false` = pausadas e perdidas);
  - `saude=saudavel|atencao|risco|sem_dados` (implica ativas);
  - `ordem=nome` (padrão) `|saude` (Risco pela menor nota, depois Atenção, Saudável e Sem dados por último; empate pelo
    nome) `|renovacao` (a mais próxima primeiro, sem data por último).
  - Cada item ganha `saude: {faixa, nota, destaque} | null` (null também sem a permissão de números). Sem permissão de
    números, `saude` e `ordem=saude` dão 403.
  - CSV com mais colunas: `Renovação;Situação;Perdida em;Motivo da perda;Saúde;Nota de saúde` (as duas últimas vazias
    sem permissão).
- `GET /painel` (`painel.ver`; B) ganha `saude`. Usa o `grupo_id` do filtro e não o período, porque é o estado de
  agora; empresas ativas:
  `{faixas: {saudavel: {empresas, receita}, atencao, risco, sem_dados}, empresas, receita, sem_valor,
  renovacoes_em_risco: {empresas, receita, primeira: {empresa: {id, nome}, renovacao_em, dias, valor_mensal}|null}}`.
  Renovação em risco = faixa Risco e renovação em [D, D + 60]; `primeira` = a mais próxima. Quem vê o painel sem
  `contatos.ver` recebe só os números (é o próprio painel).
- `GET /relatorios/renovacoes?grupo_id&segmento_id&responsavel_id&faixa_valor&tempo_cliente` (`relatorios.ver`) →
  `{ate, itens: [{empresa: {id, nome}, renovacao_em, dias, valor_mensal, responsavel, saude: {faixa, nota, porques:
  [até 2]}|null, destaque}], resumo: {empresas, receita, por_faixa: {saudavel: {empresas, receita}, …}}}`.
  - Entram as empresas ativas com renovação em [D − 30, D + 60]; `dias` negativo = passou.
  - Ordem: destaque primeiro (Risco antes de Atenção), depois `dias` (as que passaram primeiro).
  - `.csv` (+ `painel.exportar`): `Empresa;Renovação;Dias;Valor mensal;Responsável;Saúde;Nota;Porquês`.
- **Crescimento** (`crescimento/oportunidades.py`): `_excluidas` soma as empresas em Risco hoje, e `_fora_da_regra`
  ganha, depois do detrator, "a saúde da conta está em Risco." (o 422 do registro de oferta).

### 3.3 Telas (B)
- **Contatos › Empresas** (`AbaEmpresas.vue`, `exportacao.ts`):
  - Coluna "Saúde" (selo com ícone e texto, mais a nota; a cor nunca é a única pista) a partir de `sm`. No celular, o
    selo vai embaixo do nome.
  - Filtros: "Saúde" (Todas, Saudável, Atenção, Risco, Sem dados) e "Situação" (Ativas, Pausadas, Perdidas,
    Inativas, Todas). Ordenar: Nome, "Pior saúde primeiro", "Renovação mais próxima".
  - `?aba=empresas&saude=risco` abre a lista filtrada (o filtro de saúde fica no endereço).
  - O nome leva a `/contatos/empresas/:id`. Destaque: "Renova em 23 dias" ao lado do selo. Sem a permissão de números,
    a coluna e os controles somem.
- **`CartaoSaudeEmpresa.vue`** (para o lugar marcado da tela da empresa, A): nota grande + selo, os porquês (ícone por
  tom), o destaque da renovação e "Como a nota é calculada" (abre a tabela dos 6 critérios, pontos de máx. e texto).
  Também tem os estados Sem dados ("Ainda não há respostas desta empresa."), Pausada ou Perdida ("A saúde só é
  calculada para empresas ativas."), carregando e erro.
- **Início**:
  - Cartão **"Carteira por saúde"** (agora, com o grupo do filtro), depois do Resumo: 4 linhas (faixa, empresas,
    receita por mês e barra proporcional), cada uma com link para a lista filtrada (com `contatos.ver`) e "N sem
    valor". Some no "Comece por aqui"; no modo exemplo vem de `exemplo.ts`. Sem empresas ativas: "Cadastre as empresas
    dos seus clientes para ver a saúde da carteira."
  - Regra nova no **"O que mudou"** (`painel/logica.ts`), avaliada logo depois do pico. Recebe o número **6**: os
    números de hoje não mudam.
    - Uma empresa: "{Empresa} renova em 12 dias e está em Risco ({R$ 8,5 mil} por mês)." (também "renova hoje" e
      "renova amanhã").
    - Várias: "{n} empresas em Risco renovam nos próximos 60 dias, somando {R$ 42 mil} por mês."
    - Botões: "Ver as renovações" → `/relatorios/desfecho` (`relatorios.ver`); senão, com uma empresa só, "Ver a
      empresa" (`contatos.ver`).
- **`RenovacoesProximas.vue`** (para o lugar marcado da aba Desfecho, A), com os filtros da aba menos o período:
  - lista com empresa, "renova em 12/11/2026 · em 38 dias" (ou "passou há 5 dias — atualize a data"), valor,
    responsável, selo e o primeiro porquê; o destaque vem marcado; CSV;
  - vazio: "Nenhuma renovação nos próximos 60 dias. Preencha “Renovação do contrato” nas empresas para acompanhar
    aqui."

## 4. "Pesquisa feita com Toqqi" e origem do cadastro (C)

### 4.1 Regra e configuração
- `core/planos.py`: `pode_ocultar_mencao(plano, situacao)` = `situacao == "cortesia"` ou (`plano == "empresa"` e
  `situacao in ("ativa", "atrasada")`). `aparece` = not (`ocultar_mencao_toqqi` e `pode_ocultar_mencao`).
- URL: `{FRONTEND_URL sem a barra final}/?utm_source=pesquisa&utm_medium=rodape&utm_campaign=pagina` (página) ou
  `…&utm_campaign=email` (e-mails). Nunca vão ids da conta, do contato, do convite ou da resposta.
- `GET /envios/configuracao` ganha `ocultar_mencao_toqqi` (o salvo) e `mencao_toqqi: {pode_ocultar, aparece}`.
  `PUT /envios/configuracao` aceita `ocultar_mencao_toqqi`. Mudar de false para true sem `pode_ocultar` dá 403
  `recurso_do_plano`, "Só o plano Empresa pode tirar a menção ao Toqqi." Reenviar o valor já salvo nunca dá 403, para a
  tela continuar salvando o resto. A auditoria é a `config_envios` de hoje, com o campo.
- `GET /eu` e o login: `conta.mencao_toqqi` (bool `aparece`), para a prévia do editor e a do e-mail.

### 4.2 Onde aparece
- **Página da pesquisa** (`publico/servico._publico`, usada pelo convite, pelo link público e pelo botão incorporado):
  o formulário ganha `mencao_toqqi: {texto: "Pesquisa feita com Toqqi", url} | null`. A linha fica em
  `pesquisa/RodapeToqqi.vue`:
  - fora e abaixo do cartão, centralizada, a 24 px dele (no modo compacto, no pé do cartão); nunca na linha do botão
    de enviar;
  - texto de 12 px `slate-600` sobre o fundo da página (contraste ≥ 4,5:1), link sublinhado ao focar ou passar o mouse,
    área de toque de ao menos 24 px de altura, `target="_blank" rel="noopener noreferrer"
    referrerpolicy="no-referrer"` (o endereço da pesquisa tem o token e não pode ir no Referer);
  - aparece nas perguntas e na tela final e cabe numa linha a 320 px. A prévia do editor usa `conta.mencao_toqqi`.
- **E-mails** (`envios/mensagens.py`): `Visual.mencao_url: str | None`, preenchido por `configuracao.visual` com a
  regra acima. Vale para convite, lembrete, teste e agradecimento.
  - HTML: depois de "Não quero mais receber pesquisas", `<p style="margin:12px 0 0;…font-size:12px;color:#6b7280">`
    com o link "Pesquisa feita com Toqqi" (`#6b7280`, sublinhado).
  - Texto puro: "Pesquisa feita com Toqqi: {url}" na última linha.
  - `PreviaEmail.vue` mostra a linha.
- Não aparece no WhatsApp, nos e-mails do sistema nem na página de descadastro.

### 4.3 Origem do cadastro
- **Site** (`web/src/site/origem.ts`, novo; chamado em `site.ts`): ao abrir a raiz com `utm_*`, limpa e guarda em
  `sessionStorage['toqqi.origem']` (JSON), **só se ainda não houver** (vale o primeiro link da visita). Tudo em
  try/catch.
- **Limpeza** (igual no site e na API, com testes espelhados):
  - só as 3 chaves; o valor perde os espaços das pontas, vai para minúsculas e espaços ou "+" viram "-";
  - o valor é descartado se não casar com `^[a-z0-9._-]{1,60}$`, se tiver `@` ou se tiver 6 ou mais dígitos seguidos
    (protege contra e-mail e telefone);
  - sem nenhuma chave válida, a origem é nula.
- **Cadastro**: `CadastroView` manda `origem` (a guardada, ou a do próprio endereço `/cadastro?utm_…`) em
  `POST /auth/cadastro`. `CadastroIn.origem: {utm_source?, utm_medium?, utm_campaign?} | null` (campos desconhecidos são
  ignorados; nunca dá 422 por origem). `cadastrar` grava `contas.origem` já limpa. Depois do cadastro aceito, o site
  apaga a chave.
- **Plataforma › Visão geral**: `GET /plataforma/visao?dias_origem=30|90` (padrão 30) ganha
  `origens: {dias, de, ate, itens: [{utm_source, utm_medium, utm_campaign, rotulo, cadastros, pagantes}], sem_origem:
  {cadastros, pagantes}}`.
  - Cadastros = contas criadas no período, agrupadas pelas 3 chaves, da mais cadastros à menos; `rotulo` =
    "pesquisa · rodape · email".
  - Pagantes = com assinatura ativa no ambiente atual (a regra de `totais.pagantes`).
  - Cada conta de `contas` ganha `origem` (rótulo ou null).
  - Tela (`AbaVisao.vue`): cartão "Cadastros por origem" (30 ou 90 dias; tabela Origem, Cadastros, Pagantes e
    Conversão), com a nota "O teste dura {{teste.dias}} dias: a conversão aparece depois." e o vazio "Nenhum cadastro
    nos últimos N dias."
- **Configurações › Envios** (`ConfigEnviosView.vue`, na parte do visual dos e-mails): interruptor "Mostrar “Pesquisa
  feita com Toqqi” na página da pesquisa e nos e-mails", com "Vale para a página e para os e-mails de pesquisa.".
  Sem `pode_ocultar`, fica ligado e travado com "Disponível no plano Empresa." e, com `assinatura.gerenciar`, o link
  "Ver planos".

## 5. Permissões
| O quê | Permissão |
|---|---|
| Ver tela da empresa e histórico | `contatos.ver` |
| Renovação, perda, retorno | `contatos.editar` |
| Saúde (lista, empresa) | `contatos.ver` + (`painel.ver` ou `relatorios.ver`) |
| Cartão "Carteira por saúde" e regra do "O que mudou" | `painel.ver` |
| Desfecho e renovações | `relatorios.ver`; CSV + `painel.exportar` |
| `POST /integracao/empresas` | chave de integração |
| Menção ao Toqqi | `configuracoes.gerenciar` (PUT de envios, como hoje) |
| Origens na Visão geral | superadmin |

Nenhuma permissão nova no catálogo.

## 6. Auditoria (A, `core/auditoria.py`)
- `empresa_perdida` (atenção): `{empresa: {id, nome}, perdida_em, motivo, contatos_desativados, origem, corrigida?}`.
- `empresa_reativada` (info): `{empresa: {id, nome}, contatos_reativados, origem}`.
- Os dois no grupo `dados` (a tupla do `_grupo`); o site formata em `modulos/auditoria/detalhes.ts`.
- Valor e renovação não viram evento: o histórico já registra. A menção usa a `config_envios` de hoje.

## 7. Ajuda (`conteudo.json`; limites de `servico.validar`)
Cada parte põe as suas seções **em pontos diferentes** do arquivo (a junção só soma). Texto puro, nomes de telas entre
aspas curvas, caminhos com "›".
- **A**:
  - `contatos#renovacao-e-cliente-perdido` "Renovação e cliente perdido", logo depois de `empresas-e-responsaveis`
    (renovação, "Marcar como perdida" e o que acontece com os contatos, "Voltou a ser cliente", linha do tempo);
    atalho `contatos`.
  - `relatorios#desfecho-perdas-e-retencao` "Desfecho: perdas e retenção", logo depois de `historico-de-uma-empresa`
    (perdidas, motivos, "o que diziam antes de sair", GRR e NRR em palavras com o exemplo de 22 mil, histórico
    parcial); atalho `relatorios_desfecho`.
  - Ajustes: `contatos#importar-planilha-de-contatos` (coluna de renovação), `integracoes#campos-e-respostas-da-
    integracao` (a rota de empresas) e `integracoes#avisos-webhooks` (os dois eventos).
  - Jornada **`provar-o-resultado`** (ciclo, a **10ª**, depois de `crescer-com-quem-esta-feliz`): onde
    ["Relatórios", "Desfecho"], atalho `relatorios_desfecho`, 4 a 5 passos (preencher renovação e valor; marcar a
    perda com o motivo; abrir Desfecho; ler a frase-prova e a GRR/NRR; exportar), veja
    [`relatorios#desfecho-perdas-e-retencao`, `contatos#renovacao-e-cliente-perdido`].
  - `JORNADAS` em `servico.py`, o `docs/ajuda-jornadas.md` (10 no ciclo, 14 no total) e os testes que contam jornadas
    são ajustados.
- **B**:
  - `contatos#saude-da-conta` "Saúde da conta", logo depois de `contatos-empresas-e-responsaveis` (os 6 critérios
    com pontos, as faixas, Sem dados, destaque da renovação, quem vê); atalho `empresas`.
  - `painel#carteira-por-saude-e-renovacoes`, logo depois de `precisa-de-atencao-e-receita-em-risco`.
  - Ajustes: `crescimento#oportunidades-de-oferta` (regra de ouro com Risco) e `assistente#o-que-o-assistente-
    responde` (saúde, renovações e desfecho, inclusive a ferramenta de A).
- **C**:
  - `configuracoes#mencao-ao-toqqi-nas-pesquisas`, logo depois de `visual-dos-emails` (o que é, onde aparece,
    "Disponível no plano Empresa"); atalho `config_envios`, `somente_admin` true.
  - Ajuste: `assinatura#planos-precos-e-limite-de-contatos` (uma frase sobre a menção).

## 8. ToqqiAI (`assistente/ferramentas.py`, `atalhos.py`)
- **A**: a ferramenta `desfecho`, "Empresas perdidas, motivos, o que diziam antes de sair e a retenção de receita (GRR
  e NRR) de um período."
  - Argumentos `{de, ate}`; nulos = os últimos 365 dias (máximo 366).
  - Exige `relatorios.ver`. Devolve o bloco do §2.6, com até 10 perdidas (nome, data, motivo, valor, antes).
  - O atalho `relatorios_desfecho` ("Desfecho", `/relatorios/desfecho`, `relatorios.ver`) entra logo depois de
    `relatorios`.
- **B**: a ferramenta `saude_empresas`, "Saúde da conta (0 a 100: Saudável, Atenção, Risco ou Sem dados). Com
  empresa_id, a nota, os critérios e os porquês da empresa; sem, a carteira por faixa (empresas e receita), as 10 em
  Risco de maior valor e as renovações dos próximos 60 dias com a saúde."
  - Argumento `{empresa_id: int|null}`; exige a permissão de §5.
  - O atalho `empresas` ("Empresas", `/contatos?aba=empresas`, `contatos.ver`) entra logo depois de `contatos`.
    Conferir se o site navega para caminhos com query.
- Cada parte escreve a sua função num arquivo próprio (`relatorios/desfecho.py`, `saude/assistente.py`). Em
  `ferramentas.py` cada uma soma 1 import, 1 item em `DEFINICOES` (antes de `buscar_ajuda`; na junção, A antes de B) e
  1 entrada em `FERRAMENTAS`. `instrucoes.py` não muda: as descrições bastam.

## 9. Textos legais (C) — versão 7
`VERSAO_DOCUMENTOS = 7` em `acesso/termos.py` e `web/.../legal/versao.ts`, com `VIGENTE_DESDE` = o dia da publicação
e a linha de histórico ("Versão 7 (etapa 5i)…"). Todos aceitam de novo.
- **Termos**, `o-servico`: novo parágrafo "As pesquisas e os e-mails de pesquisa trazem a linha “Pesquisa feita com
  Toqqi”, com um link para o site do Toqqi. O link não leva dados dos seus clientes. No plano Empresa, você pode
  ocultar essa linha em Configurações › Envios."
- **Política**:
  - `dados-que-tratamos`:
    - "Clientes da empresa assinante" soma "data de renovação do contrato, se deixou de ser cliente (data, motivo e
      detalhe) e o histórico do valor mensal";
    - "Empresa assinante" soma "a origem do cadastro (os parâmetros de campanha utm do link pelo qual chegou ao site,
      sem dados pessoais)".
  - `cookies`:
    - linha `toqqi.origem` · "Lembrar por qual link de campanha você chegou ao site (só os parâmetros utm, sem dados
      pessoais), para registrar a origem se você criar uma conta." · sessionStorage · "Até fechar a aba ou criar a
      conta.";
    - no parágrafo da página da pesquisa: "A linha “Pesquisa feita com Toqqi” leva ao site do Toqqi sem nenhum dado
      da pessoa, da pesquisa ou da resposta, e o navegador não envia o endereço da pesquisa."

## 10. Testes esperados
Cada parte: arquivos novos da API (`api/tests/test_etapa5i_*.py`, com os nomes abaixo) e do site
(`web/tests/etapa5i*.test.ts`), mais a suíte dos arquivos que tocou, `npx vitest run` e `npm run build`. O que mudou de
propósito é ajustado e explicado.
- **Passo 0** `test_etapa5i_migracao.py`:
  - up e down e up de novo;
  - RLS e FORCE de `empresa_historico`;
  - os CHECKs (perda × ativa, motivo, origem jsonb);
  - a semente só para as ativas;
  - o gatilho: entrada, valor, perdida com data passada, edição da perda, reativada com valor novo sem linha `valor`,
    `entrada` de pausada antiga, origem e usuário pelos GUCs;
  - `TQ409` → 409;
  - o CHECK dos eventos de webhook.
- **A**:
  - `test_etapa5i_desfecho.py`: perda (validações, contatos desativados, 409, 404, webhook, auditoria); correção;
    retorno (contatos reativados, só os desta empresa, 402 sem mudança); PATCH com `ativa`; contato ativo em perdida
    (tela, planilha, pesquisa por API); permissões; o JSON da empresa; o histórico.
  - `test_etapa5i_integracao.py`: `POST /integracao/empresas` (achar, criar, 404, 422, null limpa, perder, reativar,
    idempotência, origem `api` no histórico).
  - `test_etapa5i_relatorio_desfecho.py`: o exemplo do §2.6 inteiro; "Tudo"; filtros; `historico_parcial`;
    `amostra_pequena`; CSV; permissões; desempenho.
  - `test_etapa5i_importacao.py`: renovação; valor com origem `importacao`; aviso dos contatos de perdidas.
  - Site: `etapa5iDesfechoLogica.test.ts` (rótulos, "em N dias", ponte da receita, frase-prova, filtros da aba) e
    `etapa5iDesfechoComponentes.test.ts` (tela da empresa nos estados, os dois modais, a aba Desfecho vazia e cheia).
- **B**:
  - `test_etapa5i_saude.py`: os 5 exemplos do §3.1; cada critério nas bordas; Sem dados; pausada e perdida nulas;
    porquês e ordem; destaque.
  - `test_etapa5i_saude_telas.py`: lista (filtro, as 3 ordens, `ativa` novos valores, CSV, 403 sem números); painel;
    renovações; regra de ouro (lista e 422).
  - `test_etapa5i_saude_desempenho.py`: < 1 s no volume do §3.1, número fixo de consultas.
  - Site: `etapa5iSaudeLogica.test.ts` (manchete regra 6, cartão, URL da lista) e `etapa5iSaudeComponentes.test.ts`
    (selo, cartão da empresa, cartão do Início, renovações).
- **C**:
  - `test_etapa5i_mencao.py`: matriz plano × situação; 403 só na mudança; HTML e texto dos 4 e-mails com e sem a
    linha; payload público (convite, link público); `/eu`; WhatsApp sem a linha.
  - `test_etapa5i_origem.py`: limpeza (casos espelhados com o site), cadastro com e sem origem, a visão da
    Plataforma.
  - Site: `etapa5iMencao.test.ts` (rodapé na pesquisa e na tela final, `rel`, prévia, interruptor travado) e
    `etapa5iOrigem.test.ts` (limpeza, primeiro link vale, cadastro manda, storage bloqueado).
  - Conferência visual da pesquisa a 320 e 360 px.
- **Junção**: teste integrado na pilha local, a 1280 px no claro e 390 px no escuro.
  - Marcar uma perda e ver a empresa sumir do Início, das oportunidades e dos envios.
  - Abrir Desfecho com renovações e conferir os números contra SQL escrito à parte.
  - Uma empresa em Risco com renovação próxima no "O que mudou".
  - A pesquisa no celular com a linha.
  - Cadastro vindo do link do e-mail aparecendo na Visão geral.

## 11. Divisão do trabalho
**Passo 0** (A, antes de abrir os worktrees; B e C partem deste commit): `api/alembic/versions/0018_desfecho_saude_origem.py`,
`api/toqqi/modelos.py` (colunas novas e `EmpresaHistorico`), `api/toqqi/core/errors.py` (TQ409) e
`api/tests/test_etapa5i_migracao.py`.

**A — Desfecho**
- API: `modulos/empresas/{esquemas.py, desfecho.py (novo), historico.py (novo)}`; `empresas/servico.py` (só `_json`,
  `criar` e `alterar`) e `empresas/rotas.py` (rotas novas no fim do arquivo);
  `modulos/contatos/servico.py` (409);
  `modulos/importacao/{planilha.py, servico.py}`;
  `modulos/integracoes/{esquemas.py, pesquisas.py, empresas.py (novo), rotas.py, webhooks.py}`;
  `modulos/relatorios/{desfecho.py (novo), rotas.py}`;
  `core/auditoria.py`; `modulos/dados/exportacao.py` (a plataforma não muda: o histórico sai em cascata, §1);
  `modulos/ajuda/servico.py` (`JORNADAS`); `docs/ajuda-jornadas.md`.
- Site: `router/` (rota), `modulos/contatos/{EmpresaView.vue, ModalPerda.vue, ModalRetorno.vue, LinhaDoTempo.vue,
  desfecho.ts (novos), ModalEmpresa.vue, ContatoView.vue}`;
  `modulos/relatorios/{AbaDesfecho.vue (novo), RelatoriosView.vue, logica.ts}`;
  `modulos/integracoes/{ModalWebhook.vue, SecaoWebhooks.vue, SecaoComoConectar.vue}`; `utils/rotulos.ts`;
  `modulos/auditoria/detalhes.ts`; `api/etapa5iDesfecho.ts` (novo); `modulos/ajuda` (se a contagem de jornadas
  estiver no código).

**B — Saúde**
- API: `modulos/saude/{regras.py, calculo.py, rotas.py, assistente.py}` (novos); `main.py` (soma `saude` na tupla dos
  routers); `empresas/servico.py` (só `condicoes`, `listar`, `CABECALHO_CSV` e `exportar_csv`) e `empresas/rotas.py`
  (só os parâmetros de `listar` e `exportar_csv`); `modulos/painel/servico.py`; `modulos/crescimento/oportunidades.py`.
- Site: `modulos/contatos/{AbaEmpresas.vue, exportacao.ts, CartaoSaudeEmpresa.vue (novo)}`;
  `components/app/SeloSaude.vue` (novo); `modulos/painel/{PainelView.vue, CartaoCarteiraSaude.vue (novo), logica.ts,
  exemplo.ts}`; `modulos/relatorios/RenovacoesProximas.vue` (novo); `api/etapa5iSaude.ts` (novo, com os próprios tipos;
  não mexe em `tipos.ts`).

**C — Menção e origem**
- API: `core/planos.py`; `modulos/envios/{configuracao.py, esquemas.py, mensagens.py}`; `modulos/publico/servico.py`;
  `apresentacao.py` (`conta_json`); `modulos/acesso/{esquemas.py, servico.py, termos.py}`;
  `modulos/plataforma/{visao.py, rotas.py}`.
- Site: `pesquisa/{RodapeToqqi.vue (novo), Pesquisa.vue, tipos.ts}`; `publico/` (se precisar passar o dado);
  `modulos/formularios/editor/PreVisualizacao.vue`; `modulos/configuracoes/{ConfigEnviosView.vue, PreviaEmail.vue,
  visualEmail.ts}`; `site/{origem.ts (novo), site.ts}`; `modulos/acesso/CadastroView.vue`;
  `modulos/plataforma/{AbaVisao.vue, visao.ts}`; `modulos/geral/legal/{termos.ts, privacidade.ts, versao.ts}`.

**Arquivos compartilhados** (cada parte soma só o seu bloco; a junção é somar):
| Arquivo | A | B | C |
|---|---|---|---|
| `api/toqqi/modulos/empresas/servico.py` | `_json`, `criar`, `alterar` | `condicoes`, `listar`, CSV | — |
| `api/toqqi/modulos/empresas/rotas.py` | rotas novas no fim | parâmetros de `listar`/`exportar_csv` | — |
| `assistente/ferramentas.py` | 1 import, 1 definição, 1 entrada | idem | — |
| `assistente/atalhos.py` | `relatorios_desfecho` depois de `relatorios` | `empresas` depois de `contatos` | — |
| `ajuda/conteudo.json` | seções do §7 A + jornada | seções do §7 B | seções do §7 C |
| `web/src/api/index.ts` | `export * from './etapa5iDesfecho'` | `export * from './etapa5iSaude'` | `authApi.cadastrar` com `origem` |
| `web/src/api/tipos.ts` | `Empresa`, `DadosEmpresa`, `EventoWebhook` | — | `Conta`, `ConfigEnvios`, `VisaoPlataforma` |
| `api/README.md`, `web/README.md` | seção "Etapa 5i (A)" no fim | "(B)" no fim | "(C)" no fim |

Na junção também se trocam os dois comentários `<!-- 5i-B: … -->` (tela da empresa e aba Desfecho) pelo import e pela
tag dos componentes de B. Depois vêm a revisão por quem não escreveu, o teste integrado (§10) e a entrega no Mac em
commits separados por frente.

## 12. Em aberto (precisam do Marcelo)
- Restringir a visão de um usuário à própria carteira (empresas do responsável ligado a ele): hoje não existe. Fica
  para outra etapa?
- A empresa perdida desativa os contatos (padrão desta etapa). Prefere manter os contatos ativos e só bloquear os
  envios pela empresa?
- Faixas e pesos da saúde: os do §3.1 são o ponto de partida; ajustar depois com dados reais.
- O endereço da menção vai para a raiz do `FRONTEND_URL`. Se o site de marketing for mudar de domínio, avisar.

**Respostas provisórias (sessão, 05/10 10h; o Marcelo pode mudar):** 1) por enquanto, quem vê empresas vê todas (como hoje);
restringir por carteira fica para outra etapa. 2) Sim, perder a empresa desativa os contatos. 3) Pesos e faixas valem como
ponto de partida; ajustar depois com dados reais (o Desfecho mostra se a saúde antecipou as perdas). 4) A raiz do
`FRONTEND_URL` é o destino do link.

## 13. Notas da construção (C, versão enxuta, 05/10)
Feito na própria sessão, sem agentes, por custo (pedido do Marcelo). Diferenças do §4/§9:
- Plataforma › Visão geral: janela fixa de 90 dias (sem `?dias_origem`), sem a coluna de conversão; cada conta traz `origem`.
- Sem a menção nas prévias do editor de formulários e do e-mail (aparece na pesquisa e nos e-mails de verdade).
- Textos legais: só a linha `toqqi.origem` na tabela de armazenamento da Política; **sem subir `VERSAO_DOCUMENTOS`**
  (ninguém precisa aceitar de novo). Se o advogado achar a mudança relevante, subir a versão depois.
- Sem `conta.mencao_toqqi` no `GET /eu` (só a tela de Envios usa a regra, por `GET /envios/configuracao`).
- Achado nos testes: `origem=None` no modelo gravava `'null'` em JSONB e o CHECK recusava, o que derrubaria todo cadastro;
  o cadastro grava `NULL` de SQL.
- A e B (desfecho e saúde) ficam para depois; a migração 0018 já sobe com as colunas e o histórico do valor mensal começa a
  ser gravado desde o deploy (útil para o desfecho).

## 14. Notas da construção (A, versão enxuta, 05/10)
Feito na sessão, sem agentes. Entrou: `renovacao_em` na empresa; `POST /empresas/{id}/perda` e `/retorno` (com os
contatos, o limite do plano, a auditoria e as validações do §2.2); `situacao`, perda e motivo no JSON da empresa; 409 ao
reativar pela edição; `GET /relatorios/desfecho` com as regras do §2.6 (o exemplo do contrato virou teste: GRR 45,5% e
NRR 56,8%); no site, "Marcar como perdida"/"Voltou a ser cliente" no menu de cada empresa (Contatos › Empresas), a
renovação no "Editar empresa", o selo "Perdida em …" e a aba Relatórios › Desfecho (período padrão de 12 meses); uma
seção na Ajuda (Relatórios).
Ficou para depois: `PATCH /perda` (corrigir), `GET /historico` e a tela própria da empresa com a linha do tempo; o CSV
do Desfecho; importação e API de integração com renovação/perda e os webhooks `empresa.*`; o ToqqiAI e a jornada na
Ajuda; a regra nova do "O que mudou". Importar um contato ativo de uma empresa perdida hoje para a importação com o 409
`empresa_perdida` (a mensagem explica o que fazer).

## 15. Notas da construção (B, versão enxuta, 05/10)
Feito na sessão, sem agentes. Entrou: `modulos/saude/regras.py` (as regras do §3.1; os exemplos viraram teste — no
exemplo 2, os 3 porquês seguem a regra "do que mais perdeu pontos": satisfação, decisor e tendência; no 4, com o convite
dentro de J o contato conta como convidado, 46) e `calculo.py` (consultas agrupadas por empresa);
`GET /empresas` com `saude` por item, `saude=` e `ordem=nome|saude|renovacao`; `GET /empresas/{id}/saude`;
`GET /painel/saude` (o cartão "Carteira por saúde" no Início, com o aviso das renovações em Risco) e
`GET /relatorios/renovacoes` (a lista no fim da aba Desfecho). No site: coluna, filtro e ordem em Contatos › Empresas,
`?aba=empresas&saude=risco`, o selo abre a saúde com "Como a nota é calculada"; seção na Ajuda (Contatos).
Ficou para depois: a regra no "O que mudou", a saúde no ToqqiAI, o CSV com a saúde e as renovações, os filtros de
segmento/responsável nas renovações, o Crescimento excluir empresas em Risco e o cartão no modo exemplo.

## 16. Notas da construção (desfecho, segunda parte, 05/10)
Entrou: `GET /empresas/{id}/historico` e a tela da empresa (`/contatos/empresas/:id`: dados, saúde com os porquês,
contatos e a linha do tempo; o nome na lista de Empresas leva a ela); `GET /relatorios/desfecho.csv` ("Exportar CSV" na
aba); a coluna "Renovação do contrato" na importação (contato novo ou atualizado de empresa perdida entra inativo, em vez
do 409); `POST /integracao/empresas` (chave; cria ou atualiza pelo código externo, documento ou nome; `situacao`
`perdida` com motivo ou `ativa`; origem `api` no histórico; 201 ao criar); webhooks `empresa.perdida` e
`empresa.reativada` (dados da empresa, sem contatos); ferramentas `desfecho` (sem período: 12 meses) e
`saude_empresas` no ToqqiAI.
Fora: marcar a perda pela planilha (a planilha só traz a renovação; perda pela tela ou pela API) e `PATCH /perda`.
