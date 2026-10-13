"""Plano Grátis (docs/api-plano-gratis.md; pedido do Marcelo em 13/10/2026: "O que acha de dar uma conta grátis pra
quem tem até 50 clientes? Com limites baixos"; as decisões estão na especificação "Plano Grátis do Toqqi").

Teste reverso: todo mundo continua começando com o teste do Profissional; quem termina o teste sem assinar, quem
cancelou e viu o período pago acabar e quem ficou `gratis.dias_atraso` dias com a fatura vencida passa para o Grátis
(`servico._situacao`), em vez de ter os envios parados e a conta excluída. Nada é apagado por causa de limite: o que
passa do Grátis fica parado, à vista, com o caminho para assinar ao lado.

Limites (Plataforma › Parâmetros: grupo `gratis`; a cota do ToqqiAI, o teto da análise e a franquia do WhatsApp nos
grupos IA e WhatsApp, com os dos outros planos):
- contatos ativos (`gratis.contatos`, 100): a trava do banco (`limite_contatos`); acima disso (quem importou mais no
  teste), os envios param até ficarem dentro do limite (pré-condição `contatos_do_plano`);
- e-mails de pesquisa por mês e por dia (`gratis.envios_mes` 200, `gratis.envios_dia` 100): convites e lembretes por
  e-mail, contados ao agendar (`reservar_email`, em `envios_uso`). Agradecimento, retorno ao cliente, link público,
  link do contato e WhatsApp não contam. Acabou: os próximos esperam o dia ou o mês virar (a fila continua) e, no fim
  do mês, os administradores recebem um e-mail (uma vez por mês);
- usuários (`gratis.usuarios`, 1): só entram os mais antigos ativos com o e-mail confirmado, administradores
  primeiro (`usuarios_que_entram`); os outros veem o aviso no login e as sessões deles são encerradas na passagem;
- formulários: até 2 recebendo respostas; com mais de 2 (vindos do teste), os links já enviados seguem valendo, mas só
  os dois padrão (NPS e CSAT, que o administrador escolhe) entram em envios novos (`formularios_de_envio`);
- integrações (RD Station, Omie, Bling, chave de API e webhooks): desligadas, com a configuração guardada; voltam ao
  assinar (`erro_recurso`, nas rotas delas).

Proteção contra abuso, só no Grátis: nota de risco 60 ou mais (gravada pela tarefa, `plataforma.risco.gravar`) pausa
os envios até a equipe liberar em Plataforma › Contas (`pausada_por_risco`); formulário pedindo senha, cartão, dados
bancários ou código não é enviado; o remetente é o nome da conta e as respostas por e-mail vão para o administrador
mais antigo (`remetente`); o descanso entre duas pesquisas para o mesmo contato é de pelo menos 30 dias.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import parametros, planos, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.avisos import avisar_admins
from toqqi.core.config import config
from toqqi.core.db import travar
from toqqi.core.errors import AppError
from toqqi.modelos import ConfigEnvios, Conta, Contato, EnvioUso, Formulario, IaUsoMensal, Sessao, Usuario

log = logging.getLogger("toqqi.gratis")

GRATIS = "gratis"
FORMULARIOS = 2  # recebendo respostas ao mesmo tempo; com mais (vindos do teste), os dois padrão nos envios novos
DESCANSO_MINIMO = 30  # dias entre duas pesquisas para o mesmo contato
RISCO_PAUSA = 60  # a nota "alta" de plataforma.risco (ALTO)
ROTA_PLANOS = "/assinatura"
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")

MSG_USUARIOS = ("Esta conta está no plano Grátis, que tem {n}. Peça a um administrador para assinar um plano e "
                "liberar a sua entrada.")
MSG_RECURSO = "{o_que} não faz parte do plano Grátis. Disponível a partir do plano Essencial."
MSG_NOVO_USUARIO = ("O plano Grátis tem {n}. Para adicionar pessoas à equipe, assine um plano a partir do "
                    "Essencial.")
MSG_FORMULARIOS = ("No plano Grátis, até {n} formulários recebem respostas ao mesmo tempo. Desative um para usar "
                   "outro, ou assine um plano a partir do Essencial.")
MSG_FORMULARIO_FORA = ("No plano Grátis, os envios usam até {n} formulários. Como a conta tem mais de {n} recebendo "
                       "respostas, valem os padrão (NPS e CSAT): escolha um deles ou desative os outros.")
MSG_SENSIVEL = ("No plano Grátis, a pesquisa não pode pedir senha, número de cartão, dados bancários ou código de "
                "verificação. Mude a pergunta “{trecho}” para enviar.")
MSG_DESCANSO = f"No plano Grátis, o descanso entre pesquisas é de pelo menos {DESCANSO_MINIMO} dias."
MSG_RISCO = ("Os envios estão pausados enquanto a equipe Toqqi confere a conta (costuma levar até 1 dia útil). Se "
             "quiser, conte para a gente pelo Feedback como você usa o Toqqi.")
ASSUNTO_PASSOU = "Sua conta no Toqqi passou para o plano Grátis"
ASSUNTO_FIM_DO_MES = "Os envios por e-mail do mês acabaram"


def eh_gratis(conta: Conta | None) -> bool:
    return conta is not None and conta.situacao == GRATIS


def _url(caminho: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}{caminho}"


def _n(n: int, um: str, varios: str) -> str:
    return f"{planos.numero(n)} {um if n == 1 else varios}"


def limites() -> dict:
    """Os números do Grátis agora (parâmetros, pelo cache)."""
    v = parametros.valor
    return {"contatos": v("gratis.contatos"), "envios_mes": v("gratis.envios_mes"), "envios_dia": v("gratis.envios_dia"),
            "usuarios": v("gratis.usuarios"), "formularios": FORMULARIOS, "ia_cota": v("ia.cota.gratis"),
            "dias_sem_uso": v("gratis.dias_sem_uso"), "descanso_minimo": DESCANSO_MINIMO}


def erro_recurso(o_que: str) -> AppError:
    """403 `recurso_do_plano` (o mesmo do "Pesquisa feita com Toqqi", etapa 5i), com o plano a partir do qual vale."""
    return AppError(403, "recurso_do_plano", MSG_RECURSO.format(o_que=o_que), extra={"plano_minimo": "essencial"})


def exigir_recurso(conta: Conta | None, o_que: str) -> None:
    if eh_gratis(conta):
        raise erro_recurso(o_que)


def exigir_recurso_ctx(ctx, o_que: str) -> None:
    """Rotas da conta (pelo `Contexto`, com a conta lida na requisição): 403 `recurso_do_plano` no Grátis."""
    if (ctx.conta or {}).get("situacao") == GRATIS:
        raise erro_recurso(o_que)


# ---- passagens ---------------------------------------------------------------------------------

def _motivo(anterior: str) -> str:
    return {"teste": "teste", "atrasada": "atraso"}.get(anterior, "cancelamento")


def _contatos_ativos(s: Session, conta_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Contato).where(Contato.conta_id == conta_id,
                                                                    Contato.ativo.is_(True)))


def _paragrafos_passou(conta: Conta, motivo: str, ativos: int) -> list[str]:
    lim = limites()
    primeiro = {
        "teste": f"O teste da conta {conta.nome} no Toqqi terminou e a conta passou para o plano Grátis.",
        "cancelamento": f"O período pago da assinatura da conta {conta.nome} no Toqqi terminou e a conta passou "
                        "para o plano Grátis.",
        "atraso": f"A assinatura da conta {conta.nome} no Toqqi foi cancelada porque a fatura ficou "
                  f"{parametros.valor('gratis.dias_atraso')} dias vencida, e a conta passou para o plano Grátis.",
    }[motivo]
    paragrafos = [
        f"{primeiro} Os contatos, as respostas, os formulários e os planos de ação continuam aqui.",
        f"No Grátis, a conta envia até {_n(lim['envios_mes'], 'pesquisa', 'pesquisas')} por e-mail por mês para até "
        f"{_n(lim['contatos'], 'contato ativo', 'contatos ativos')}, com {_n(lim['usuarios'], 'usuário', 'usuários')}"
        f" e até {lim['formularios']} formulários. O link público, o link de cada contato e o WhatsApp automático "
        "continuam funcionando.",
    ]
    if ativos > lim["contatos"]:
        paragrafos.append(f"A conta tem {planos.numero(ativos)} contatos ativos: os envios voltam quando ficarem até "
                          f"{planos.numero(lim['contatos'])}. Desative os contatos que não quer pesquisar, ou assine "
                          "um plano.")
    paragrafos += [
        "As integrações (RD Station, Omie, Bling, chave de API e webhooks) ficam desligadas no Grátis e voltam como "
        "estavam quando a conta assinar um plano.",
        f"Para enviar sem esses limites, assine um plano a partir de {parametros.reais(planos.preco('essencial'))} "
        "por mês.",
    ]
    return paragrafos


def usuarios_que_entram(s: Session, conta_id: int) -> list[int]:
    """Quem entra na conta Grátis: os `gratis.usuarios` mais antigos ativos e com o e-mail confirmado,
    administradores primeiro."""
    return list(s.scalars(select(Usuario.id).where(Usuario.conta_id == conta_id, Usuario.situacao == "ativo",
                                                   Usuario.email_confirmado.is_(True))
                          .order_by(Usuario.perfil != "admin", Usuario.id).limit(parametros.valor("gratis.usuarios"))))


def ao_entrar(s: Session, conta: Conta, anterior: str) -> None:
    """A conta acabou de passar para o Grátis (em `servico.recalcular`, na transação de quem mudou): marca desde quando
    e por quê, desfaz um aviso de exclusão antigo, sobe o descanso para 30 dias, encerra as sessões de quem não entra
    mais, audita e avisa os administradores por e-mail (depois do commit)."""
    motivo = _motivo(anterior)
    conta.gratis_desde = relogio.agora()
    conta.gratis_motivo = motivo
    conta.exclusao_avisada_para = conta.exclusao_avisada_em = None
    s.execute(update(ConfigEnvios).where(ConfigEnvios.conta_id == conta.id,
                                         ConfigEnvios.descanso_dias < DESCANSO_MINIMO)
              .values(descanso_dias=DESCANSO_MINIMO))
    entram = usuarios_que_entram(s, conta.id)
    encerradas = s.execute(update(Sessao).where(Sessao.conta_id == conta.id, Sessao.revogada_em.is_(None),
                                                Sessao.usuario_id.not_in(entram))
                           .values(revogada_em=func.now())).rowcount
    ativos = _contatos_ativos(s, conta.id)
    registrar(s, "plano_gratis", "atencao", {"de": anterior, "motivo": motivo, "contatos_ativos": ativos,
                                              "sessoes_encerradas": encerradas}, conta_id=conta.id)
    avisar_admins(s, conta.id, ASSUNTO_PASSOU, _paragrafos_passou(conta, motivo, ativos),
                  ("Ver planos", _url(ROTA_PLANOS)))
    log.info("Plano Grátis: a conta %s entrou (%s).", conta.id, motivo)


def ao_sair(s: Session, conta: Conta) -> None:
    """A conta saiu do Grátis (pagou a primeira fatura, ganhou mais dias de teste ou virou cortesia)."""
    dias = (relogio.agora() - conta.gratis_desde).days
    registrar(s, "plano_gratis_saiu", "info", {"para": conta.situacao, "dias": dias}, conta_id=conta.id)
    conta.gratis_desde = conta.gratis_motivo = None
    conta.exclusao_avisada_para = conta.exclusao_avisada_em = None


def usar_conta(s: Session, conta: Conta, usuario_id: int | None) -> None:
    """Alguém usou a conta (entrou, ou abriu o site com a sessão): na conta Grátis avisada de que seria excluída por
    falta de uso, a exclusão é cancelada (`exclusao.py` avisa de novo se ela parar outra vez)."""
    if not eh_gratis(conta) or conta.exclusao_avisada_para is None:
        return
    registrar(s, "exclusao_cancelada", "info", {"exclusao_em": conta.exclusao_avisada_para.isoformat()},
              usuario_id=usuario_id, conta_id=conta.id)
    conta.exclusao_avisada_para = conta.exclusao_avisada_em = None


# ---- envios por e-mail ---------------------------------------------------------------------------

def _mes(dia: date) -> date:
    return dia.replace(day=1)


def proximo_mes(dia: date) -> date:
    return (_mes(dia) + timedelta(days=32)).replace(day=1)


def uso_envios(s: Session, conta_id: int, hoje: date | None = None) -> tuple[int, int]:
    """(e-mails no mês, e-mails hoje) da conta."""
    hoje = hoje or relogio.hoje()
    linha = s.execute(select(EnvioUso.emails, EnvioUso.dia, EnvioUso.emails_dia)
                      .where(EnvioUso.conta_id == conta_id, EnvioUso.mes == _mes(hoje))).one_or_none()
    if linha is None:
        return 0, 0
    return linha.emails, linha.emails_dia if linha.dia == hoje else 0


def tem_email(s: Session, conta: Conta) -> bool:
    """A conta pode agendar mais um e-mail de pesquisa agora (fora do Grátis, sempre)."""
    if not eh_gratis(conta):
        return True
    mes, dia = uso_envios(s, conta.id)
    return mes < parametros.valor("gratis.envios_mes") and dia < parametros.valor("gratis.envios_dia")


def mensagem_envios(s: Session, conta: Conta) -> str | None:
    """Por que a conta Grátis não envia mais e-mails agora (o mês ou o dia acabou); None se ainda pode."""
    if not eh_gratis(conta):
        return None
    hoje = relogio.hoje()
    mes, dia = uso_envios(s, conta.id, hoje)
    lim_mes, lim_dia = parametros.valor("gratis.envios_mes"), parametros.valor("gratis.envios_dia")
    if mes >= lim_mes:
        volta = proximo_mes(hoje)
        return (f"Os envios por e-mail deste mês acabaram ({planos.numero(mes)} de {planos.numero(lim_mes)}). Voltam "
                f"em {volta:%d/%m}, ou assine um plano para continuar agora.")
    if dia >= lim_dia:
        return (f"Os envios por e-mail de hoje acabaram ({planos.numero(dia)} de {planos.numero(lim_dia)}). Voltam "
                "amanhã.")
    return None


def reservar_email(s: Session, conta: Conta) -> bool:
    """Gasta um e-mail de pesquisa (convite ou lembrete) do mês e do dia da conta Grátis; False se acabou (a conta
    fora do Grátis não conta: sempre True). Atômico (um UPDATE com o limite no WHERE): dois agendamentos ao mesmo tempo
    não passam do limite. O que esgota o mês avisa os administradores (uma vez por mês)."""
    if not eh_gratis(conta):
        return True
    hoje = relogio.hoje()
    lim_mes, lim_dia = parametros.valor("gratis.envios_mes"), parametros.valor("gratis.envios_dia")
    t = EnvioUso.__table__
    usados = s.execute(
        insert(EnvioUso).values(conta_id=conta.id, mes=_mes(hoje), emails=1, dia=hoje, emails_dia=1)
        .on_conflict_do_update(
            index_elements=[t.c.conta_id, t.c.mes],
            set_={"emails": t.c.emails + 1, "dia": hoje,
                  "emails_dia": case((t.c.dia == hoje, t.c.emails_dia + 1), else_=1)},
            where=and_(t.c.emails < lim_mes, or_(t.c.dia != hoje, t.c.emails_dia < lim_dia)))
        .returning(t.c.emails)).scalar()
    if usados is None:
        _avisar_fim_do_mes(s, conta, hoje, lim_mes)
        return False
    if usados >= lim_mes:
        _avisar_fim_do_mes(s, conta, hoje, lim_mes)
    return True


def devolver_email(s: Session, conta_id: int, criado_em) -> None:
    """Um e-mail reservado que não chegou a sair (o contato saiu da lista ou foi excluído antes): volta para o mês (e
    para o dia, se ainda é o mesmo)."""
    dia = criado_em.astimezone(relogio.FUSO).date()
    t = EnvioUso.__table__
    s.execute(update(EnvioUso).where(t.c.conta_id == conta_id, t.c.mes == _mes(dia), t.c.emails > 0)
              .values(emails=t.c.emails - 1,
                      emails_dia=case((and_(t.c.dia == dia, t.c.emails_dia > 0), t.c.emails_dia - 1),
                                      else_=t.c.emails_dia)))


def _avisar_fim_do_mes(s: Session, conta: Conta, hoje: date, limite: int) -> None:
    t = EnvioUso.__table__
    marcou = s.execute(update(EnvioUso).where(t.c.conta_id == conta.id, t.c.mes == _mes(hoje),
                                              t.c.emails >= limite, t.c.avisou_fim.is_(False))
                       .values(avisou_fim=True).returning(t.c.conta_id)).first()
    if marcou is None:
        return
    volta = proximo_mes(hoje)
    registrar(s, "envio_limite_mes", "atencao", {"limite": limite, "mes": _mes(hoje).isoformat()},
              conta_id=conta.id)
    avisar_admins(s, conta.id, ASSUNTO_FIM_DO_MES, [
        f"A conta {conta.nome} usou as {planos.numero(limite)} pesquisas por e-mail do plano Grátis em "
        f"{MESES[hoje.month - 1]}. Os próximos convites e lembretes por e-mail saem a partir de "
        f"{volta.day}º de {MESES[volta.month - 1]}; os contatos continuam na fila.",
        "O link público, o link de cada contato e o WhatsApp automático continuam funcionando.",
        "Para continuar enviando por e-mail agora, assine um plano: a partir do Essencial, os envios não têm limite.",
    ], ("Ver planos", _url(ROTA_PLANOS)))


# ---- usuários -------------------------------------------------------------------------------------

def texto_usuarios(n: int | None = None) -> str:
    n = parametros.valor("gratis.usuarios") if n is None else n
    return "1 usuário" if n == 1 else f"até {n} usuários"


def recusa_de_entrada(s: Session, conta: Conta, usuario_id: int) -> AppError | None:
    """403 `plano_gratis` para quem não está entre os que entram na conta Grátis; None para os outros."""
    if not eh_gratis(conta) or usuario_id in usuarios_que_entram(s, conta.id):
        return None
    return AppError(403, "plano_gratis", MSG_USUARIOS.format(n=texto_usuarios()))


def exigir_vaga_de_usuario(s: Session, conta: Conta, novos: int = 1) -> None:
    """Criar (ou aprovar, ou desbloquear) alguém na equipe da conta Grátis: só se couber no limite de usuários."""
    if not eh_gratis(conta):
        return
    travar(s, f"equipe:{conta.id}")  # dois pedidos ao mesmo tempo não passam do limite
    ativos = s.scalar(select(func.count()).select_from(Usuario).where(Usuario.conta_id == conta.id,
                                                                      Usuario.situacao == "ativo"))
    if ativos + novos > parametros.valor("gratis.usuarios"):
        raise AppError(403, "recurso_do_plano", MSG_NOVO_USUARIO.format(n=texto_usuarios()),
                       extra={"plano_minimo": "essencial"})


# ---- formulários ----------------------------------------------------------------------------------

def _ativos(s: Session, conta_id: int):
    return s.execute(select(Formulario.id, Formulario.padrao_nps, Formulario.padrao_csat)
                     .where(Formulario.conta_id == conta_id, Formulario.ativo.is_(True),
                            Formulario.arquivado.is_(False))).all()


def formularios_de_envio(s: Session, conta: Conta) -> frozenset[int] | None:
    """Os formulários que entram em envios novos: None = qualquer um ativo (fora do Grátis, ou até 2 ativos); senão os
    dois padrão (NPS e CSAT). Os links já enviados de todos os ativos seguem valendo."""
    if not eh_gratis(conta):
        return None
    ativos = _ativos(s, conta.id)
    if len(ativos) <= FORMULARIOS:
        return None
    return frozenset(i for i, nps, csat in ativos if nps or csat)


def motivo_sensivel(conta: Conta, f: Formulario) -> str | None:
    """A mensagem de recusa do formulário que pede senha, cartão, dados bancários ou código, na conta Grátis."""
    if not eh_gratis(conta):
        return None
    from toqqi.modulos.plataforma.risco import trecho_sensivel  # import tardio: o risco importa os envios

    achado = trecho_sensivel(f.perguntas or [])
    return MSG_SENSIVEL.format(trecho=achado[1]) if achado is not None else None


def recusa_do_formulario(s: Session, conta: Conta, f: Formulario) -> tuple[str, str] | None:
    """(tipo, mensagem) de por que o formulário não pode ir num envio novo da conta Grátis: `sensivel` (pede senha,
    cartão, dados bancários ou código) ou `fora` (não está entre os que entram nos envios); None se pode (e sempre
    fora do Grátis)."""
    if not eh_gratis(conta):
        return None
    sensivel = motivo_sensivel(conta, f)
    if sensivel is not None:
        return "sensivel", sensivel
    liberados = formularios_de_envio(s, conta)
    if liberados is not None and f.id not in liberados:
        return "fora", MSG_FORMULARIO_FORA.format(n=FORMULARIOS)
    return None


def exigir_formulario(s: Session, conta: Conta, f: Formulario) -> None:
    """422 `dados_invalidos` (campo `formulario_id`) se o formulário não pode ir num envio novo da conta Grátis."""
    recusa = recusa_do_formulario(s, conta, f)
    if recusa:
        raise AppError(422, "dados_invalidos", recusa[1], {"formulario_id": recusa[1]})


def exigir_vaga_de_formulario(s: Session, conta: Conta) -> None:
    """Criar, duplicar ou ativar um formulário na conta Grátis: só com menos de 2 recebendo respostas (com a trava da
    conta: dois pedidos ao mesmo tempo não passam do limite)."""
    if not eh_gratis(conta):
        return
    travar(s, f"formularios:{conta.id}")
    if len(_ativos(s, conta.id)) >= FORMULARIOS:
        raise AppError(403, "recurso_do_plano", MSG_FORMULARIOS.format(n=FORMULARIOS),
                       extra={"plano_minimo": "essencial"})


# ---- remetente, descanso e risco -------------------------------------------------------------------

def remetente(s: Session, conta: Conta, remetente_nome: str | None, responder_para: str | None) -> tuple:
    """(remetente_nome, responder_para) de um e-mail da conta: no Grátis, o nome da conta (None = o nome da empresa)
    e o e-mail do administrador mais antigo ativo, qualquer que seja a configuração."""
    if not eh_gratis(conta):
        return remetente_nome, responder_para
    admin = s.scalar(select(Usuario.email).where(Usuario.conta_id == conta.id, Usuario.perfil == "admin",
                                                 Usuario.situacao == "ativo").order_by(Usuario.id).limit(1))
    return None, admin


def pausada_por_risco(conta: Conta | None) -> bool:
    """Conta Grátis com nota de risco 60 ou mais que a equipe não liberou (ou que subiu acima da liberada)."""
    if not eh_gratis(conta) or conta.risco_pontos is None or conta.risco_pontos < RISCO_PAUSA:
        return False
    return conta.risco_liberado_pontos is None or conta.risco_pontos > conta.risco_liberado_pontos


# ---- resumo (login, /eu e Assinatura) --------------------------------------------------------------

def resumo(s: Session, conta: Conta) -> dict | None:
    """O Grátis da conta para as telas: limites, o que já usou e se está pausada pela nota de risco; null fora dele."""
    if not eh_gratis(conta):
        return None
    lim = limites()
    hoje = relogio.hoje()
    mes, dia = uso_envios(s, conta.id, hoje)
    ia = s.scalar(select(IaUsoMensal.cota_usada).where(IaUsoMensal.conta_id == conta.id,
                                                      IaUsoMensal.mes == _mes(hoje))) or 0
    return {
        "desde": conta.gratis_desde, "motivo": conta.gratis_motivo,
        "contatos": {"ativos": _contatos_ativos(s, conta.id), "limite": lim["contatos"]},
        "envios": {"mes": mes, "limite_mes": lim["envios_mes"], "dia": dia, "limite_dia": lim["envios_dia"],
                   "volta_mes": proximo_mes(hoje), "volta_dia": hoje + timedelta(days=1)},
        "ia": {"usadas": ia, "limite": lim["ia_cota"]},
        "usuarios": lim["usuarios"], "formularios": lim["formularios"], "descanso_minimo": DESCANSO_MINIMO,
        "dias_sem_uso": lim["dias_sem_uso"],
        "pausada_por_risco": pausada_por_risco(conta),
    }
