"""E-mails do painel: alerta de pico de reclamações (tarefa `picos`) e resumo semanal (tarefa `resumo`).

Destinatários: usuários ativos, com e-mail confirmado e permissão `painel.ver` (admin sempre), com a preferência
ligada (`recebe_alertas` / `recebe_resumo_semanal`, em Minha conta). Só com provedor de e-mail real (`provedor_ok`)
e conta com a assinatura em dia. São e-mails do sistema (`core.email.enviar`, o visual do "Alerta de risco"), um por
pessoa, e não entram no histórico de envios.

As tarefas rodam por conta (a lista vem do modo sistema, o trabalho de cada conta em em_conta); uma conta com erro
não derruba as outras.
- Alerta de pico: um por tema a cada 7 dias, garantido no banco (trava por conta e tema + conferência na mesma
  transação, então duas rodadas ao mesmo tempo não duplicam). Grava `alertas_pico` e depois manda.
- Resumo semanal: segunda-feira a partir das 8h de Brasília (se não rodar na segunda, até terça 23:59; depois, a
  semana é pulada). Uma vez por conta e semana (`resumos_semanais`, gravado antes de enviar; o UNIQUE impede
  duplicar). Pula a conta sem respostas na semana e sem ações abertas.
"""
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from toqqi.core import email, relogio
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema, travar
from toqqi.core.email import Link, Titulo
from toqqi.core.filtros import inicio_do_dia
from toqqi.core.ia import cortar
from toqqi.modelos import (
    Acao,
    AlertaPico,
    Conta,
    Contato,
    Empresa,
    PerfilPermissao,
    Responsavel,
    Resposta,
    ResumoSemanal,
    Usuario,
)
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.envios.configuracao import assinatura_ok, provedor_ok
from toqqi.modulos.painel.servico import Filtro, _com_empresa
from toqqi.modulos.relatorios import picos as picos_mod
from toqqi.modulos.relatorios.regras import ROTULOS_FAIXA_NPS
from toqqi.modulos.respostas import indicadores as ind
from toqqi.modulos.respostas.temas import CHAVES, ROTULOS

log = logging.getLogger("toqqi.relatorios")

JANELA_ALERTA = timedelta(days=7)
MAX_EXEMPLOS_PICO = 5
MAX_ACOES_RESUMO = 5
MAX_TEMAS_RESUMO = 3
MAX_COMENTARIOS_RESUMO = 3
MAX_TEXTO = 200
RESUMO_A_PARTIR = time(8, 0)
SEM_CADASTRO = "Cliente sem cadastro"


# ---- comum ----------------------------------------------------------------------

def _url(caminho: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}{caminho}"


def rodape(conta_nome: str) -> tuple[str, str, str]:
    return (f"Você recebe este e-mail porque acompanha o painel da {conta_nome}. Para parar, desligue em "
            "Minha conta.", "Minha conta", _url("/minha-conta"))


def destinatarios(s: Session, preferencia: str) -> list[str]:
    """E-mails de quem recebe: ativo, e-mail confirmado, `painel.ver` (admin sempre) e a preferência ligada."""
    pode_ver = (select(PerfilPermissao.perfil)
                .where(PerfilPermissao.conta_id == Usuario.conta_id, PerfilPermissao.perfil == Usuario.perfil,
                       PerfilPermissao.permissao == "painel.ver").exists())
    return list(s.scalars(select(Usuario.email).where(
        Usuario.situacao == "ativo", Usuario.email_confirmado.is_(True), getattr(Usuario, preferencia).is_(True),
        or_(Usuario.perfil == "admin", pode_ver)).order_by(Usuario.id)))


def _contas_em_dia() -> list[int]:
    agora = relogio.agora()
    with modo_sistema() as s:  # só ids; o trabalho de cada conta roda em em_conta(conta)
        return list(s.scalars(select(Conta.id).where(or_(
            Conta.situacao.in_(("cortesia", "ativa")), and_(Conta.situacao == "teste", Conta.teste_ate > agora)))
            .order_by(Conta.id)))


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _decimal_br(v, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def _quem(empresa: str | None, contato: str | None) -> str:
    return empresa or contato or SEM_CADASTRO


def _texto_resposta(resumo_ia: str | None, comentario: str | None) -> str:
    return resumo_ia or cortar(" ".join((comentario or "").split()), MAX_TEXTO)


# ---- alerta de pico -------------------------------------------------------------

def _exemplos_pico(s: Session, conta_id: int, tema: str, de: date, ate: date) -> list[str]:
    linhas = s.execute(
        select(Resposta.nota, Resposta.ia_resumo, Resposta.ia_situacao, Resposta.comentario_cliente,
               Empresa.nome.label("empresa"), Contato.nome.label("contato"))
        .select_from(Resposta).outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
        .outerjoin(Contato, Contato.id == Resposta.contato_id)
        .where(Resposta.conta_id == conta_id, Resposta.arquivada.is_(False), Resposta.temas_reclamacao.any(tema),
               Resposta.tipo_nota.in_(("nps", "csat")), or_(Resposta.empresa_id.is_(None), Empresa.ativa.is_(True)),
               Resposta.data_resposta >= inicio_do_dia(de),
               Resposta.data_resposta < inicio_do_dia(ate + timedelta(days=1)))
        .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(MAX_EXEMPLOS_PICO)).all()
    saida = []
    for x in linhas:
        texto = _texto_resposta(x.ia_resumo if x.ia_situacao == "analisada" else None, x.comentario_cliente)
        saida.append(" · ".join(p for p in (_quem(x.empresa, x.contato), f"nota {x.nota}", texto) if p))
    return saida


def _email_pico(conta_nome: str, pico: dict, exemplos: list[str]) -> tuple[str, list, tuple[str, str]]:
    rotulo = pico["rotulo"]
    paragrafos: list = [
        f"Nos últimos 7 dias, {pico['reclamacoes']} respostas reclamaram de {rotulo.lower()}. Nas 4 semanas "
        f"anteriores, a média era de {_decimal_br(pico['media_anterior'])} por semana."]
    if exemplos:
        paragrafos += [Titulo("Reclamações recentes"), *exemplos]
    link = _url(f"/respostas?tema={pico['tema']}&reclamacao=true&so_ativos=true&de={pico['de'].isoformat()}"
                f"&ate={pico['ate'].isoformat()}")
    return f"Pico de reclamações: {rotulo}", paragrafos, ("Ver as respostas", link)


def picos_conta(conta_id: int) -> dict:
    """Alerta os picos novos da conta (sem alerta do mesmo tema nos últimos 7 dias). {picos, emails}."""
    agora, hoje = relogio.agora(), relogio.hoje()
    novos = []
    with em_conta(conta_id) as s:
        conta = s.get(Conta, conta_id)
        if conta is None or not assinatura_ok(conta):
            return {"picos": 0, "emails": 0}
        for pico in picos_mod.calcular(s, conta_id, hoje):
            travar(s, f"alerta_pico:{conta_id}:{pico['tema']}")  # duas rodadas ao mesmo tempo esperam aqui
            ja_alertado = s.scalar(select(exists().where(AlertaPico.conta_id == conta_id,
                                                         AlertaPico.tema == pico["tema"],
                                                         AlertaPico.detectado_em > agora - JANELA_ALERTA)))
            if ja_alertado:
                continue
            alerta = AlertaPico(conta_id=conta_id, tema=pico["tema"], reclamacoes=pico["reclamacoes"],
                                media_anterior=pico["media_anterior"], detectado_em=agora)
            s.add(alerta)
            s.flush()
            novos.append((alerta.id, pico, _exemplos_pico(s, conta_id, pico["tema"], pico["de"], pico["ate"])))
        para = destinatarios(s, "recebe_alertas") if novos else []
        conta_nome = conta.nome
    emails = 0
    for alerta_id, pico, exemplos in novos:  # depois do commit: o alerta já está gravado
        assunto, paragrafos, botao = _email_pico(conta_nome, pico, exemplos)
        for destino in para:
            email.enviar(destino, assunto, paragrafos, botao, rodape(conta_nome))
        emails += len(para)
        with em_conta(conta_id) as s:
            s.execute(update(AlertaPico).where(AlertaPico.id == alerta_id)
                      .values(enviado_em=relogio.agora(), destinatarios=len(para)))
    return {"picos": len(novos), "emails": emails}


def picos() -> dict:
    """Tarefa `picos`. Devolve {picos, emails}."""
    total = {"picos": 0, "emails": 0}
    if not provedor_ok():
        return total
    for conta_id in _contas_em_dia():
        try:
            r = picos_conta(conta_id)
        except Exception:  # noqa: BLE001 - uma conta não derruba as outras
            log.exception("Falha nos alertas de pico da conta %s", conta_id)
            continue
        total["picos"] += r["picos"]
        total["emails"] += r["emails"]
    return total


# ---- resumo semanal ---------------------------------------------------------------

def semana_a_resumir(agora: datetime) -> date | None:
    """A segunda-feira da semana anterior, se é segunda depois das 8h ou terça (até 23:59); senão None."""
    dia = agora.date()
    if (dia.weekday() == 0 and agora.time() >= RESUMO_A_PARTIR) or dia.weekday() == 1:
        return dia - timedelta(days=dia.weekday() + 7)
    return None


def _nps(s: Session, f: Filtro) -> dict:
    p, n, d = s.execute(_com_empresa(select(
        *[func.count().filter(Resposta.tipo_nota == "nps", Resposta.grupo == g)
          for g in ("promotor", "neutro", "detrator")]).select_from(Resposta)).where(*f.respostas())).one()
    return ind.bloco_nps(p, n, d)


def _prazo_texto(prazo: date | None, hoje: date) -> str:
    if prazo is None:
        return "sem prazo"
    dias = (prazo - hoje).days
    if dias < 0:
        return f"vencida há {-dias} dia{'s' if dias < -1 else ''}"
    if dias == 0:
        return "vence hoje"
    if dias == 1:
        return "vence amanhã"
    return f"vence em {dias} dias"


def _conteudo_resumo(s: Session, conta_id: int, semana: date) -> tuple[str, list] | None:
    """(assunto, parágrafos) do resumo da semana, ou None se a conta ficou parada (sem respostas e sem ações)."""
    fim = semana + timedelta(days=6)
    hoje = relogio.hoje()
    f = Filtro(conta_id, semana, fim, None, True)
    respostas = s.scalar(_com_empresa(select(func.count()).select_from(Resposta)).where(*f.respostas()))
    # ações como no painel ("só empresas ativas"): as de empresa inativa ficam de fora; as sem empresa contam
    da_acao = aliased(Empresa)  # alias: a lista abaixo também junta Empresa (sem ele, a subconsulta seria correlacionada)
    empresa_ativa = or_(Acao.empresa_id.is_(None),
                        exists().where(da_acao.id == Acao.empresa_id, da_acao.conta_id == conta_id, da_acao.ativa))
    abertas = s.scalar(select(func.count()).select_from(Acao).where(Acao.conta_id == conta_id, aberta(),
                                                                     empresa_ativa))
    if not respostas and not abertas:
        return None
    paragrafos: list = []
    # 1. NPS da semana
    nps = _nps(s, f)
    paragrafos.append(Titulo("NPS da semana"))
    if nps["valor"] is None:
        paragrafos.append("Nenhuma resposta de NPS na semana.")
    else:
        paragrafos.append(f"NPS {nps['valor']} ({ROTULOS_FAIXA_NPS[nps['faixa']]}) · "
                          f"{_plural(nps['total'], 'resposta', 'respostas')}: "
                          f"{_plural(nps['promotores'], 'promotor', 'promotores')}, "
                          f"{_plural(nps['neutros'], 'neutro', 'neutros')} e "
                          f"{_plural(nps['detratores'], 'detrator', 'detratores')}.")
        anterior = _nps(s, Filtro(conta_id, semana - timedelta(days=7), semana - timedelta(days=1), None, True))
        if anterior["valor"] is not None:
            variacao = nps["valor"] - anterior["valor"]
            paragrafos.append(f"Variação: {variacao:+d} em relação à semana anterior (NPS {anterior['valor']})."
                              if variacao else f"Sem variação em relação à semana anterior (NPS {anterior['valor']}).")
    noventa = _nps(s, Filtro(conta_id, fim - timedelta(days=89), fim, None, True))
    paragrafos.append(f"Últimos 90 dias: NPS {noventa['valor']}." if noventa["valor"] is not None
                      else "Últimos 90 dias: sem respostas de NPS.")
    # 2. detratores sem tratamento
    paragrafos.append(Titulo("Detratores sem tratamento"))
    de_detrator = [Acao.conta_id == conta_id, aberta(), Acao.grupo.in_(("detrator", "insatisfeito")), empresa_ativa]
    total, vencidas = s.execute(select(func.count(), func.count().filter(Acao.prazo < hoje))
                                .where(*de_detrator)).one()
    if not total:
        paragrafos.append("Nenhum detrator esperando tratamento.")
    else:
        paragrafos.append(f"{_plural(total, 'ação aberta', 'ações abertas')} de detratores"
                          + (f", {_plural(vencidas, 'vencida', 'vencidas')}." if vencidas else "."))
        acoes = s.execute(
            select(Acao.id, Acao.nota, Acao.prazo, Empresa.nome.label("empresa"), Contato.nome.label("contato"),
                   Responsavel.nome.label("responsavel"))
            .select_from(Acao).outerjoin(Empresa, Empresa.id == Acao.empresa_id)
            .outerjoin(Contato, Contato.id == Acao.contato_id)
            .outerjoin(Responsavel, Responsavel.id == Acao.responsavel_id).where(*de_detrator)
            .order_by(case((Acao.prazo < hoje, 0), else_=1), Acao.prazo.asc().nulls_last(), Acao.criada_em, Acao.id)
            .limit(MAX_ACOES_RESUMO)).all()
        for a in acoes:
            partes = [_quem(a.empresa, a.contato), f"nota {a.nota}" if a.nota is not None else None,
                      a.responsavel or "sem responsável", _prazo_texto(a.prazo, hoje)]
            paragrafos.append(Link(" · ".join(p for p in partes if p), _url(f"/planos-de-acao/{a.id}")))
    # 3. temas em alta
    paragrafos.append(Titulo("Temas em alta"))
    contagem = picos_mod.contar(s, conta_id, fim)
    em_alta = sorted(((t, rec, ant) for t, (rec, ant) in contagem.items() if rec and t in ROTULOS),
                     key=lambda x: (-x[1], CHAVES.index(x[0])))[:MAX_TEMAS_RESUMO]
    if not em_alta:
        paragrafos.append("Nenhuma reclamação na semana.")
    for tema, rec, ant in em_alta:
        media = picos_mod.media_semanal(ant)
        selo = " · pico" if picos_mod.eh_pico(rec, media) else ""
        paragrafos.append(f"{ROTULOS[tema]}: {_plural(rec, 'reclamação', 'reclamações')} (média de "
                          f"{_decimal_br(media)} por semana nas 4 semanas anteriores){selo}")
    # 4. o que disseram
    comentarios = s.execute(_com_empresa(
        select(Resposta.nota, Resposta.ia_resumo, Resposta.ia_situacao, Resposta.comentario_cliente,
               Empresa.nome.label("empresa"), Contato.nome.label("contato"))
        .select_from(Resposta).outerjoin(Contato, Contato.id == Resposta.contato_id))
        .where(*f.respostas(), Resposta.comentario_cliente != "")
        .order_by(case((Resposta.grupo.in_(("detrator", "insatisfeito")), 0), else_=1),
                  Resposta.data_resposta.desc(), Resposta.id.desc())
        .limit(MAX_COMENTARIOS_RESUMO)).all()
    if comentarios:
        paragrafos.append(Titulo("O que disseram"))
        for x in comentarios:
            texto = _texto_resposta(x.ia_resumo if x.ia_situacao == "analisada" else None, x.comentario_cliente)
            nota = f" · nota {x.nota}" if x.nota is not None else ""
            paragrafos.append(f"{_quem(x.empresa, x.contato)}{nota}: {texto}")
    periodo = f"{semana.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
    assunto = f"Resumo da semana ({periodo})" + (f": NPS {nps['valor']}" if nps["valor"] is not None else "")
    return assunto, paragrafos


def resumo_conta(conta_id: int, semana: date) -> dict | None:
    """Monta, registra (uma vez por semana) e manda o resumo da conta. None se não era o caso."""
    with em_conta(conta_id) as s:
        conta = s.get(Conta, conta_id)
        if conta is None or not assinatura_ok(conta):
            return None
        conteudo = _conteudo_resumo(s, conta_id, semana)
        if conteudo is None:
            return None  # conta parada: sem respostas na semana e sem ações abertas
        resumo_id = s.scalar(insert(ResumoSemanal).values(conta_id=conta_id, semana=semana)
                             .on_conflict_do_nothing(index_elements=[ResumoSemanal.conta_id, ResumoSemanal.semana])
                             .returning(ResumoSemanal.id))
        if resumo_id is None:
            return None  # já saiu nesta semana
        para = destinatarios(s, "recebe_resumo_semanal")
        conta_nome = conta.nome
    assunto, paragrafos = conteudo
    for destino in para:  # depois do commit: o resumo já está registrado
        email.enviar(destino, assunto, paragrafos, ("Abrir o painel", _url("/inicio")), rodape(conta_nome))
    with em_conta(conta_id) as s:
        s.execute(update(ResumoSemanal).where(ResumoSemanal.id == resumo_id)
                  .values(enviado_em=relogio.agora(), destinatarios=len(para)))
    return {"emails": len(para)}


def resumo() -> dict:
    """Tarefa `resumo`. Devolve {contas, emails}."""
    total = {"contas": 0, "emails": 0}
    semana = semana_a_resumir(relogio.agora())
    if semana is None or not provedor_ok():
        return total
    for conta_id in _contas_em_dia():
        try:
            r = resumo_conta(conta_id, semana)
        except Exception:  # noqa: BLE001 - uma conta não derruba as outras
            log.exception("Falha no resumo semanal da conta %s", conta_id)
            continue
        if r is not None:
            total["contas"] += 1
            total["emails"] += r["emails"]
    return total
