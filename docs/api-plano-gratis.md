# Plano Grátis

Pedido do Marcelo (13/10/2026): "O que acha de dar uma conta grátis pra quem tem até 50 clientes? Com limites
baixos..". As decisões estão na especificação "Plano Grátis do Toqqi" (Docs), respondida por ele no mesmo dia.

**Teste reverso.** Toda conta continua começando com o teste do Profissional. Quem termina o teste sem assinar, quem
cancelou e viu o período pago acabar e quem ficou `gratis.dias_atraso` dias (30) com a fatura vencida passa para o
**Grátis** (situação `gratis`), em vez de ter os envios parados e a conta excluída 90 dias depois (etapa 5f). Nada é
apagado por causa de limite: o que passa dele fica parado, à vista, com o caminho para assinar ao lado. A conta Grátis
que ninguém usa por `gratis.dias_sem_uso` dias (180) é excluída, com aviso `gratis.dias_aviso` dias (30) antes.

Código: `api/toqqi/modulos/assinatura/gratis.py` (o núcleo), `exclusao.py` (contas paradas),
`plataforma/risco.py` (`gravar`), `plataforma/denuncias.py`, `plataforma/avisos_equipe.py`; no site,
`web/src/modulos/assinatura/gratis.ts` e `components/app/AvisoPlanoGratis.vue`. Migração `0030_plano_gratis`.

## Limites (Plataforma › Parâmetros)

Grupo novo **Plano Grátis** (`gratis`); a cota do ToqqiAI (`ia.cota.gratis`, 10), o teto da análise automática dos
comentários (`ia.teto.gratis`, 100) e a franquia do WhatsApp (`whatsapp.franquia.gratis`, sem franquia) ficam nos
grupos IA e WhatsApp, com os dos outros planos.

| Chave | Padrão | Mín.–máx. | O que é |
| --- | --- | --- | --- |
| `gratis.contatos` | 100 | 1–1.000.000 | contatos ativos (a trava do banco, `limite_contatos`) |
| `gratis.envios_mes` | 200 | 1–100.000 | e-mails de pesquisa (convites e lembretes) por mês |
| `gratis.envios_dia` | 100 | 1–100.000 | ... e por dia (não passa do mês) |
| `gratis.usuarios` | 1 | 1–10 | quem entra: os mais antigos, administradores primeiro |
| `gratis.dias_sem_uso` | 180 | 60–730 | conta parada é excluída depois disso |
| `gratis.dias_aviso` | 30 | 7–60 | ... com o e-mail este tanto de dias antes (menor que o anterior) |
| `gratis.dias_atraso` | 30 | 10–120 | fatura vencida há este tanto de dias: a assinatura é cancelada |

Fixos no código: até **2 formulários** recebendo respostas (`FORMULARIOS`), descanso de **30 dias** entre duas
pesquisas para o mesmo contato (`DESCANSO_MINIMO`) e nota de risco **60** para pausar (`RISCO_PAUSA`). Diminuir um
número do Grátis pede confirmação na tela, com as contas Grátis atingidas (contatos, envios do mês ou do dia,
usuários). `GET /publico/planos` ganhou `gratis: {contatos, envios_mes, envios_dia, usuarios, formularios, ia_cota,
ia_teto, whatsapp}` (site e cadastro; `formularios` é o fixo do código).

## Passagens

- `assinatura.servico._situacao` devolve `gratis` sempre que a conta não tem cobertura (sem teste valendo, sem período
  pago, sem cortesia). `teste_expirado` não existe mais (a migração converteu as contas: com `pago_ate`, motivo
  `cancelamento`; sem, `teste`). `cancelada` agora só vale enquanto o período pago corre.
- `recalcular`: entrou no Grátis (`gratis_desde` nulo) → `gratis.ao_entrar`: grava `gratis_desde` e `gratis_motivo`
  (`teste`, `cancelamento` ou `atraso`), desfaz um aviso de exclusão antigo, sobe o descanso para 30 dias, encerra as
  sessões de quem não entra mais, auditoria `plano_gratis` (atenção) `{de, motivo, contatos_ativos,
  sessoes_encerradas}` e e-mail aos administradores "Sua conta no Toqqi passou para o plano Grátis" (o motivo, os
  limites, os contatos acima do limite, as integrações desligadas e o preço a partir do Essencial; botão "Ver
  planos"). Saiu (`gratis_desde` preenchido) → `ao_sair`: auditoria `plano_gratis_saiu` `{para, dias}`.
- A tarefa `assinaturas` (`conferencia.recalcular_pelas_datas`) pega o teste que acabou, a primeira fatura vencida e o
  cancelamento cujo período pago acabou. `cancelar_por_atraso` (só com o Asaas configurado): `atrasada_desde` há
  `gratis.dias_atraso` dias ou mais e não cortesia → remove a assinatura no Asaas, encerra, auditoria
  `assinatura_cancelada` `{plano, motivo: "atraso", vencida_em}` e recalcula (vai ao Grátis). O resumo da tarefa:
  `contas_ao_gratis`, `canceladas_por_atraso`.
- Assinar saindo do Grátis: a conta segue no Grátis até a primeira fatura ser paga (aviso `gratis_aguardando`). O
  limite de contatos conferido na escolha do plano é o do plano escolhido (`_conferir_limite`).

## Regras no Grátis

- **Contatos**: `limite_contatos(plano, 'gratis')` lê `gratis.contatos` (a política `ler_limites` deixa o papel da
  aplicação ler essa chave); o gatilho `contatos_checar_limite` não usa o limite contratado do Personalizado no Grátis
  (`limite_da_conta` também não). Acima do limite (vindo do teste), a pré-condição `contatos_do_plano` para os envios.
- **E-mails de pesquisa**: contados ao agendar (`reservar_email`, um upsert em `envios_uso` com o limite no WHERE: dois
  agendamentos ao mesmo tempo não passam), em `escolher_canal`, no reenvio por e-mail quando o WhatsApp falha e em
  `tentar_de_novo`; o que não chega a sair (`NaoEnviar`) volta (`devolver_email`). Agradecimento, retorno ao cliente,
  link público, link do contato e WhatsApp não contam. Acabou: os próximos esperam o dia ou o mês virar (a fila
  continua); no fim do mês, os administradores recebem "Os envios por e-mail do mês acabaram" (uma vez por mês,
  auditoria `envio_limite_mes`). A pré-condição `envios_do_mes` falha sem e-mail no mês ou no dia (fica ok com o canal
  WhatsApp disponível). O agradecimento ignora as duas pré-condições do Grátis (`pronto(..., ignorar=SO_PESQUISAS)`).
- **Usuários**: entram os `gratis.usuarios` mais antigos ativos com o e-mail confirmado, administradores primeiro
  (`usuarios_que_entram`). Os outros recebem 403 `plano_gratis` no login ("Esta conta está no plano Grátis, que tem 1
  usuário. Peça a um administrador para assinar um plano e liberar a sua entrada."). Criar, aprovar ou desbloquear
  alguém além do limite: 403 `recurso_do_plano`.
- **Formulários**: criar, duplicar ou ativar com 2 recebendo respostas → 403 `recurso_do_plano`. Com mais de 2 (do
  teste), os links já enviados valem, mas os envios novos usam só os padrão NPS e CSAT (`formularios_de_envio`; o item
  `formulario` das pré-condições e 422 em `formulario_id`).
- **Integrações**: RD Station, Omie e Bling (conectar, alterar, sincronizar), chave de API (gerar e usar), webhooks
  (criar, testar, ligar; a fila não enfileira) e o disparo de pesquisas pela API → 403 `recurso_do_plano` com
  `extra.plano_minimo = "essencial"` ("… não faz parte do plano Grátis. Disponível a partir do plano Essencial."). A
  configuração fica guardada e volta ao assinar. O WhatsApp automático continua.
- **Proteção contra abuso** (só no Grátis): o remetente é o nome da conta e as respostas vão para o administrador mais
  antigo (`gratis.remetente`, nos envios e no e-mail de teste); o descanso é de pelo menos 30 dias (422
  `descanso_dias`; o disparo manual não ignora o descanso); formulário que pede senha, cartão, dados bancários ou
  código não sai (`motivo_sensivel`, pré-condição `formulario` com "Editar o formulário"); a nota de risco pausa.

## Nota de risco e denúncias

- A tarefa `riscos` (depois de `assinaturas`) grava `contas.risco_pontos` e `risco_em` (`plataforma.risco.gravar`). A
  conta Grátis com 60 pontos ou mais que a equipe não liberou (ou que subiu acima da nota liberada) fica com os envios
  pausados (`pausada_por_risco`; pré-condição `revisao`; convites e lembretes viram `NaoEnviar`; o link do WhatsApp
  também para). Entrou em pausa: auditoria `risco_pausou` e e-mail aos superadmins "Conta Grátis pausada pela nota de
  risco" (botão para `/plataforma/contas?suspeitas=1`).
- `POST /plataforma/contas/{id}/liberar-envios` (superadmin) grava `risco_liberado_pontos` (a maior entre a gravada e a
  de agora) e `risco_liberado_em`, auditoria `risco_liberado`; 409 `nao_pausada` se não está pausada.
- **Denúncias**: a pesquisa da conta Grátis vai com `formulario.denuncia: true`, e a página mostra "Denunciar esta
  pesquisa" embaixo de "Pesquisa feita com Toqqi". `POST /publico/convites/{token}/denuncia` e
  `/publico/formularios/{codigo}/denuncia` `{motivo: dados_pessoais|golpe|spam|ofensa|outro, detalhe?}` → 201
  `{mensagem}` (limite 3 por minuto, 10 por hora, 20 por dia; a mesma pessoa no mesmo formulário no mesmo dia, pelo
  código do IP com sal diário, volta 201 sem gravar). Tabela `denuncias` (só o modo sistema lê: a conta não vê); e-mail
  aos superadmins "Denúncia de pesquisa no plano Grátis". Sinal de risco `denuncias`: 60 pontos com 2 ou mais pessoas
  diferentes em 30 dias, 30 com 1 (as descartadas não contam).
- Plataforma › Feedback › Denúncias: `GET /plataforma/denuncias?situacao=abertas|todas` → `{itens, abertas}` (até
  300, das mais novas) e `PATCH /plataforma/denuncias/{id}` `{situacao?: aberta|procedente|descartada,
  nota_interna?}`.

## Conta parada (exclusão)

A rotina diária da etapa 5f (`assinatura/exclusao.py`, na tarefa `limpeza`) agora cuida só da conta Grátis parada:
último uso = o mais tarde entre `gratis_desde`, o último login e o último uso de uma sessão; prevista = último uso +
`gratis.dias_sem_uso`. O aviso sai `gratis.dias_aviso` dias antes (e-mail "Sua conta no Toqqi será excluída em
dd/mm/aaaa", botão "Entrar no Toqqi", auditoria `exclusao_avisada`). Usar o Toqqi (entrar, ou abrir o site com a
sessão) cancela na hora (`gratis.usar_conta`, auditoria `exclusao_cancelada`). As travas da 5f continuam (aviso
entregue, Asaas conferível, limites do dia, `teste.exclusao_automatica` ligada ou simular).

## Telas

- **Topo**: nos 7 primeiros dias, o aviso `gratis` (`{data, dias, motivo}`: "Seu teste acabou e a conta passou para o
  Grátis: até 100 contatos e 200 envios por e-mail por mês."); com a primeira fatura em aberto, `gratis_aguardando`.
  Passou de um limite (`conta.gratis`, em GET /eu e no login): envios pausados pela nota, contatos acima do limite,
  e-mails do mês ou do dia acabaram, do mais grave ao mais leve. O selo do topo vira "Plano Grátis" ("Ver planos").
- **Assinatura**: "Plano Grátis", R$ 0, os medidores (contatos ativos, envios por e-mail no mês, ToqqiAI no mês) e o
  que muda; `GET /assinatura` ganhou `gratis` e `limites_gratis`.
- **Travas**: aviso "Plano Grátis" (`AvisoPlanoGratis`) em Integrações (Sistemas e API e avisos), Equipe ("Novo
  usuário" desligado com 1 usuário), Formulários ("Novo formulário" desligado com 2 ativos) e Configurações de envio
  (remetente e "Respostas por e-mail vão para" desligados; descanso com mínimo de 30). As pré-condições ganharam
  `revisao`, `contatos_do_plano` e `envios_do_mes`.
- **Plataforma**: situação "Grátis" e "Envios pausados" (com "Liberar envios") em Contas (`?suspeitas=1`, `?busca=`),
  o cartão "Plano Grátis" na Visão geral (`gratis: {contas, assinaram_30d, pausadas, entraram_30d}`), o grupo Plano
  Grátis em Parâmetros e Feedback › Denúncias (`?denuncias=1`).
- **Site e cadastro**: no topo e na chamada do fim, "Depois do teste, continue grátis com até 100 contatos"; em "Tudo
  incluído", o que fica de fora no Grátis; em Planos, o texto de abertura (continue no Grátis ou assine; o cancelamento
  volta ao Grátis), o cartão "Grátis" (R$ 0, os limites, "Criar conta grátis", que leva ao cadastro e ao teste) e a
  coluna Grátis na tabela de comparação (no celular, a tabela rola de lado com o nome do recurso fixo); as dúvidas "O
  que acontece quando o teste acaba?" e "O plano Grátis tem prazo?"; no guia de customer success, a frase dos planos.
  Embaixo do botão do cadastro, "Depois do teste, se não assinar, a conta continua no plano Grátis: …".
- **Termos e Política, versão 9** (`acesso/termos.py` e `web/src/modulos/geral/legal/`): o plano Grátis, o uso justo,
  a exclusão da conta Grátis sem uso (no lugar dos 90 dias), as denúncias e a nova retenção. Todo mundo vê a tela de
  aceite de novo.
- **Ajuda** (`ajuda/conteudo.json`, versão 2): a seção "Plano Grátis: limites e o que muda", as situações e os avisos,
  o cancelamento, a conta Grátis sem uso e as pré-condições.
