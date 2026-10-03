"""Exclusão automática das contas encerradas (etapa 5f): passo diário da tarefa `limpeza`.

Decisão (Marcelo): a conta encerrada é excluída 90 dias depois do fim do período pago (ou do teste não assinado), com
e-mail aos administradores 7 dias antes; o backup do banco fica fora. As datas saem das funções puras de
`regras` (`encerramento`: encerrada_em e prevista; `exclusao_em`).

- Encerrada: `teste_expirado` ou `cancelada`, sem assinatura ativa (`primeiro_vencimento` nulo e nenhuma 'ativa' em
  `assinaturas`, de qualquer ambiente) e não liberada. Nunca: cortesia, ativa, atrasada, teste ou com assinatura
  ativa. Quem assinou e não paga só entra no log (`em_atraso_90_dias`: `atrasada_desde` antes de hoje − 90); sem fim
  do teste nem `pago_ate`, nunca (`sem_data`).
- Aviso, uma vez por encerramento: `exclusao_avisada_para` nulo ou antes da `prevista` e hoje ≥ `prevista` − 7 →
  data = max(`prevista`, hoje + 7); grava `exclusao_avisada_para` e `exclusao_avisada_em` (relógio do banco),
  auditoria `exclusao_avisada` (atenção) `{exclusao_em, encerrada_em, admins}` e e-mail aos administradores ativos
  (`avisar_admins`, tipo `aviso`), com o botão "Baixar os dados".
- Exclusão: `exclusao_avisada_para` ≥ `prevista`, hoje ≥ `exclusao_avisada_para` e, pelo relógio do banco, aviso
  com 7 dias e conta criada há pelo menos 100 dias. Em modo sistema, com a conta travada (a trava da assinatura e a
  linha) e tudo conferido de novo:
  - o aviso precisa ter chegado (`_aviso_entregue`): um e-mail `aviso` aceito pelo provedor (`enviado`) com o assunto
    do aviso, gravado em `emails_enviados` depois de `exclusao_avisada_em`. Sem ele (o provedor falhou), com algum
    administrador ativo, o aviso é desfeito (`exclusao_avisada_para`/`_em` nulos) e a próxima rodada avisa de novo
    (data = max(`prevista`, hoje + 7)): `adiadas`. Sem nenhum administrador ativo (ninguém a avisar), vale sem o
    e-mail, depois dos mesmos 7 dias;
  - as assinaturas vivas no Asaas precisam poder ser conferidas (`_asaas_conferivel`): cliente lá sem a chave do
    mesmo ambiente → `adiadas` (exceto cliente de sandbox com a chave de produção: as de sandbox são só de teste e a
    troca para produção já as cancela, decisão da 5a); `assinaturas.remover_vivas_no_asaas` (falhou → fica para
    amanhã: `adiadas`);
  - `plataforma.apagar_conta` e o evento global `conta_excluida_automatica` `{conta_id, situacao, encerrada_em,
    avisada_em, exclusao_em, admins}` (`admins`: administradores ativos na hora; 0 = ninguém a avisar), sem dado
    pessoal (o log também). Ficam os registros de acesso e os eventos globais.
- Rodada: a partir das 9h, uma vez por dia (já há `exclusao_automatica` global de hoje → pula; rodadas simultâneas
  → a segunda pula, pela trava `exclusao_automatica`). Conta e registra no log; `EXCLUSAO_AUTOMATICA=ligada` age;
  qualquer outro valor só simula (`simular`, o padrão; um valor desconhecido também deixa um aviso no log). Limites do
  dia (São Paulo), contados pelos eventos já gravados hoje e não pela rodada: até 100 avisos (`exclusao_avisada`) e
  20 exclusões (`conta_excluida_automatica`), das mais antigas; uma rodada que caiu no meio (sem o evento do dia), ou o
  evento do dia apagado à mão, roda de novo sem passar do limite. Cada aviso e cada exclusão na sua transação e no seu
  try/except: um erro numa conta vai para o log só com o id e o tipo do erro (a mensagem pode ter dado pessoal), a
  conta fica para outro dia e as outras seguem. `adiadas`: as que ficaram para outro dia (passaram do limite do dia,
  erro, aviso que não chegou, Asaas sem conferência ou fora do ar). No fim, o evento global `exclusao_automatica`
  `{modo, avisadas, excluidas, adiadas, em_atraso_90_dias, sem_data}`, que é o que a tarefa devolve em `encerradas`
  (null quando pulou).
"""
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import exists, func, literal_column, select, text

from toqqi.core import asaas, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.avisos import admins_a_avisar, avisar_admins
from toqqi.core.config import config
from toqqi.core.db import engine, modo_sistema
from toqqi.core.errors import AppError
from toqqi.modelos import Assinatura, Auditoria, Conta, EmailEnviado
from toqqi.modulos.assinatura import regras
from toqqi.modulos.assinatura import servico as assinaturas
from toqqi.modulos.plataforma.servico import apagar_conta

log = logging.getLogger("toqqi.exclusao")

A_PARTIR_DE = time(9, 0)
MAX_AVISOS = 100
MAX_EXCLUSOES = 20
DIAS_AVISO = 7
DIAS_EM_ATRASO = 90
TRAVA = "exclusao_automatica"
CAMINHO_DADOS = "/configuracoes/dados-da-conta"
ASSUNTO_AVISO = "Sua conta no Toqqi será excluída em"  # + " dd/mm/aaaa"
FEITAS = ("avisada", "excluida")
# pelo relógio do banco (não pelo das regras): o aviso saiu há 7 dias e a conta tem 100 dias
PRONTA = literal_column(
    "((contas.exclusao_avisada_em AT TIME ZONE 'America/Sao_Paulo')::date"
    " <= (now() AT TIME ZONE 'America/Sao_Paulo')::date - 7"
    " AND contas.criada_em <= now() - interval '100 days')")


def _sem_assinatura_ativa():
    return ~exists().where(Assinatura.conta_id == Conta.id, Assinatura.situacao == "ativa")


def _encerradas(s) -> list[Conta]:
    return list(s.scalars(select(Conta).where(Conta.situacao.in_(regras.ENCERRADAS),
                                              Conta.primeiro_vencimento.is_(None), _sem_assinatura_ativa())
                          .order_by(Conta.id)))


def _quer_aviso(c: Conta, prevista: date, hoje: date) -> bool:
    return (c.exclusao_avisada_para is None or c.exclusao_avisada_para < prevista) \
        and hoje >= prevista - timedelta(days=DIAS_AVISO)


def _quer_exclusao(c: Conta, prevista: date, hoje: date) -> bool:
    return c.exclusao_avisada_para is not None and c.exclusao_avisada_para >= prevista \
        and hoje >= c.exclusao_avisada_para


def _paragrafos(c: Conta, encerrada_em: date, data: date) -> list[str]:
    fim_pago = regras.fim_do_periodo_pago_em(c)
    periodo = "o período de teste" if c.teste_ate is not None and (fim_pago is None or c.teste_ate >= fim_pago) \
        else "o período pago"
    return [
        f"A conta {c.nome} no Toqqi está encerrada desde {encerrada_em:%d/%m/%Y}, quando terminou {periodo}.",
        f"Em {data:%d/%m/%Y}, todos os dados da conta serão excluídos de forma definitiva: contatos, empresas, "
        "respostas, planos de ação, formulários, configurações e os acessos da equipe. Depois disso, não dá para "
        "recuperar.",
        "Para guardar uma cópia, entre no Toqqi como administrador e vá em Configurações › Dados da conta › "
        "Baixar todos os dados.",
        "Se quiser continuar usando o Toqqi, é só assinar um plano antes dessa data: a exclusão é cancelada.",
    ]


def _avisar(conta_id: int, agora: datetime) -> str:
    """Avisa uma conta (conferida de novo com a conta travada): 'avisada' ou 'ignorada' (deixou de valer)."""
    hoje = agora.date()
    with modo_sistema() as s:
        c = assinaturas.travar_conta(s, conta_id)
        ativa = s.scalar(select(exists().where(Assinatura.conta_id == conta_id, Assinatura.situacao == "ativa")))
        enc = regras.encerramento(c, agora) if c is not None and not ativa else None
        if enc is None or not _quer_aviso(c, enc[1], hoje):
            return "ignorada"
        encerrada_em, prevista = enc
        data = max(prevista, hoje + timedelta(days=DIAS_AVISO))
        c.exclusao_avisada_para = data
        c.exclusao_avisada_em = func.now()
        admins = len(admins_a_avisar(s, conta_id))
        registrar(s, "exclusao_avisada", "atencao",
                  {"exclusao_em": data.isoformat(), "encerrada_em": encerrada_em.isoformat(), "admins": admins},
                  conta_id=conta_id)
        avisar_admins(s, conta_id, f"{ASSUNTO_AVISO} {data:%d/%m/%Y}", _paragrafos(c, encerrada_em, data),
                      ("Baixar os dados", f"{config().FRONTEND_URL.rstrip('/')}{CAMINHO_DADOS}"))
    log.info("Exclusão automática: conta %s avisada (exclusão em %s).", conta_id, data.isoformat())
    return "avisada"


def _aviso_entregue(s, c: Conta) -> bool:
    """O aviso deste encerramento chegou a algum administrador: um e-mail `aviso` aceito pelo provedor (`enviado`),
    com o assunto do aviso, gravado depois de `exclusao_avisada_em` (o registro é gravado depois do envio; um de um
    aviso anterior não vale)."""
    return bool(s.scalar(select(exists().where(
        EmailEnviado.conta_id == c.id, EmailEnviado.tipo == "aviso", EmailEnviado.situacao == "enviado",
        EmailEnviado.assunto.startswith(ASSUNTO_AVISO, autoescape=True),
        EmailEnviado.criado_em >= c.exclusao_avisada_em))))


def _asaas_conferivel(c: Conta) -> bool:
    """Dá para conferir no Asaas as assinaturas vivas da conta (`remover_vivas_no_asaas` não confere nada sem a chave
    do ambiente do cliente): sem cliente lá, ou com a chave do mesmo ambiente. Cliente de sandbox com a chave de
    produção também passa: as assinaturas de sandbox são só de teste (a troca para produção já as cancela, 5a)."""
    if not c.asaas_cliente_id:
        return True
    atual = asaas.ambiente()
    return c.asaas_ambiente == atual or (c.asaas_ambiente == "sandbox" and atual == "producao")


def _excluir(conta_id: int, agora: datetime) -> str:
    """Exclui uma conta (conferida de novo com a conta travada): 'excluida', 'adiada' (fica para outro dia: o aviso
    não chegou, as assinaturas no Asaas não dão para conferir ou a cobrança não respondeu) ou 'ignorada' (deixou de
    valer)."""
    hoje = agora.date()
    with modo_sistema() as s:
        c = assinaturas.travar_conta(s, conta_id)
        if c is None:
            return "ignorada"
        ativa = s.scalar(select(exists().where(Assinatura.conta_id == conta_id, Assinatura.situacao == "ativa")))
        enc = regras.encerramento(c, agora) if not ativa else None
        pronta = s.scalar(select(PRONTA).select_from(Conta).where(Conta.id == conta_id))
        if enc is None or not _quer_exclusao(c, enc[1], hoje) or not pronta:
            return "ignorada"
        admins = len(admins_a_avisar(s, conta_id))
        if admins and not _aviso_entregue(s, c):
            c.exclusao_avisada_para = c.exclusao_avisada_em = None  # desfaz o aviso: a próxima rodada avisa de novo
            log.warning("Exclusão automática: conta %s adiada (o aviso não chegou a nenhum administrador; vai de novo "
                        "na próxima rodada).", conta_id)
            return "adiada"
        if not _asaas_conferivel(c):
            log.warning("Exclusão automática: conta %s adiada (sem a chave do Asaas do ambiente do cliente para "
                        "conferir as assinaturas).", conta_id)
            return "adiada"
        try:
            assinaturas.remover_vivas_no_asaas(c)  # nenhuma assinatura segue cobrando no Asaas
        except AppError:
            log.warning("Exclusão automática: conta %s adiada (a cobrança não respondeu).", conta_id)
            return "adiada"
        detalhe = {"conta_id": c.id, "situacao": c.situacao, "encerrada_em": enc[0].isoformat(),
                   "avisada_em": c.exclusao_avisada_em.isoformat(), "exclusao_em": c.exclusao_avisada_para.isoformat(),
                   "admins": admins}
        apagar_conta(s, c.id)
        registrar(s, "conta_excluida_automatica", "atencao", detalhe)  # global (sem conta)
    log.info("Exclusão automática: conta %s excluída.", conta_id)
    return "excluida"


def _ja_rodou_hoje(hoje: date) -> bool:
    with modo_sistema() as s:
        return bool(s.scalar(select(exists().where(Auditoria.conta_id.is_(None),
                                                   Auditoria.evento == "exclusao_automatica",
                                                   Auditoria.criado_em >= regras.inicio_do_dia(hoje)))))


def _feitos_hoje(s, evento: str, hoje: date, global_: bool = False) -> int:
    """Eventos `evento` já gravados hoje (São Paulo), por qualquer rodada: os limites são do dia, não da rodada."""
    consulta = select(func.count()).select_from(Auditoria).where(Auditoria.evento == evento,
                                                                  Auditoria.criado_em >= regras.inicio_do_dia(hoje))
    if global_:
        consulta = consulta.where(Auditoria.conta_id.is_(None))
    return s.scalar(consulta)


def _modo() -> str:
    """`ligada` age; qualquer outro valor só simula (um que não seja `simular` também deixa um aviso no log)."""
    valor = config().EXCLUSAO_AUTOMATICA
    if valor == "ligada":
        return "ligada"
    if valor != "simular":
        log.warning("Exclusão automática: EXCLUSAO_AUTOMATICA=%r não é 'ligada' nem 'simular'; a rodada só simula "
                    "(conta e registra no log, sem avisar nem excluir).", valor)
    return "simular"


def _uma_por_vez(contas: list[tuple[date, int]], limite: int, passo, etapa: str) -> tuple[int, int]:
    """`passo(conta_id)` nas contas, em ordem, até `limite` feitos. Cada uma na sua transação (a do passo) e no seu
    try/except: um erro numa conta (mesmo permanente) não para as outras; o log leva só o id e o tipo do erro.
    Devolve (feitas, adiadas): adiadas = as que o passo adiou, as que deram erro e as que passaram do limite."""
    feitas = adiadas = 0
    for n, (_, conta_id) in enumerate(contas):
        if feitas >= limite:
            adiadas += len(contas) - n  # ficam para outro dia
            break
        try:
            r = passo(conta_id)
        except Exception as e:  # noqa: BLE001 - uma conta com problema não pode parar a rodada (nem as outras contas)
            log.error("Exclusão automática: erro ao %s a conta %s (%s); fica para outro dia.", etapa, conta_id,
                      type(e).__name__)
            r = "adiada"
        feitas += r in FEITAS
        adiadas += r == "adiada"
    return feitas, adiadas


def _rodada(agora: datetime) -> dict:
    hoje = agora.date()
    modo = _modo()
    a_avisar: list[tuple[date, int]] = []
    a_excluir: list[tuple[date, int]] = []
    sem_data = 0
    with modo_sistema() as s:
        for c in _encerradas(s):
            if regras.liberada(c, agora):
                continue
            enc = regras.encerramento(c, agora)
            if enc is None:
                sem_data += 1  # encerrada sem fim do teste nem período pago: nunca é excluída
                continue
            if _quer_aviso(c, enc[1], hoje):
                a_avisar.append((enc[1], c.id))
            elif _quer_exclusao(c, enc[1], hoje):
                a_excluir.append((c.exclusao_avisada_para, c.id))
        prontas = set(s.scalars(select(Conta.id).where(Conta.id.in_([i for _, i in a_excluir]), PRONTA)))
        em_atraso = list(s.scalars(select(Conta.id).where(
            Conta.atrasada_desde < hoje - timedelta(days=DIAS_EM_ATRASO)).order_by(Conta.id)))
        restam_avisos = max(0, MAX_AVISOS - _feitos_hoje(s, "exclusao_avisada", hoje))
        restam_exclusoes = max(0, MAX_EXCLUSOES - _feitos_hoje(s, "conta_excluida_automatica", hoje, global_=True))
    a_avisar.sort()
    a_excluir = sorted(x for x in a_excluir if x[1] in prontas)
    log.info("Exclusão automática (%s): %d conta(s) a avisar, %d a excluir, %d sem data; hoje ainda cabem %d aviso(s) "
             "e %d exclusão(ões); em atraso há mais de %d dias (só registro): %s.", modo, len(a_avisar),
             len(a_excluir), sem_data, restam_avisos, restam_exclusoes, DIAS_EM_ATRASO, em_atraso or "nenhuma")
    if modo == "ligada":
        avisadas, adiadas = _uma_por_vez(a_avisar, restam_avisos, lambda i: _avisar(i, agora), "avisar")
        excluidas, adiadas_exclusao = _uma_por_vez(a_excluir, restam_exclusoes, lambda i: _excluir(i, agora),
                                                   "excluir")
        adiadas += adiadas_exclusao
    else:  # simular: só conta o que caberia hoje
        avisadas = min(len(a_avisar), restam_avisos)
        excluidas = min(len(a_excluir), restam_exclusoes)
        adiadas = len(a_avisar) - avisadas + len(a_excluir) - excluidas
    resumo = {"modo": modo, "avisadas": avisadas, "excluidas": excluidas, "adiadas": adiadas,
              "em_atraso_90_dias": len(em_atraso), "sem_data": sem_data}
    with modo_sistema() as s:
        registrar(s, "exclusao_automatica", "info", resumo)  # global (sem conta)
    log.info("Exclusão automática (%s) concluída: %s.", modo, resumo)
    return resumo


def executar(agora: datetime | None = None) -> dict | None:
    """A rodada do dia (null se ainda não deu 9h, se já rodou hoje ou se outra rodada está em andamento)."""
    agora = (agora or relogio.agora()).astimezone(relogio.FUSO)  # hora e dia de São Paulo
    if agora.time() < A_PARTIR_DE:
        return None
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conexao:
        if not conexao.scalar(text("select pg_try_advisory_lock(hashtextextended(:k, 0))"), {"k": TRAVA}):
            log.info("Exclusão automática: outra rodada em andamento; esta pula.")
            return None
        try:
            if _ja_rodou_hoje(agora.date()):
                return None
            return _rodada(agora)
        finally:
            conexao.execute(text("select pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": TRAVA})
