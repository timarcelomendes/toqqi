"""Situação de cada contato na fila de envios, calculada no banco (serve à fila, aos filtros e a Contatos).

Prioridade: inativo → saiu_da_lista → nao_saiu → enviando → aguardando → respondeu → na_fila →
aguardando_intervalo. "Último convite" = convite mais novo do contato por e-mail ou WhatsApp. Lembrete só
para convite que saiu de fato (o WhatsApp "link pronto" fica `aberto_no_whatsapp` e não recebe lembrete).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, String, and_, case, cast, func, or_, select, true
from sqlalchemy.sql import Select

from toqqi.core.relogio import FUSO, FUSO_NOME
from toqqi.core.texto import so_digitos
from toqqi.modelos import ConfigEnvios, Contato, Convite, Empresa, Envio, Grupo, Responsavel, Resposta
from toqqi.modulos.empresas.servico import ref
from toqqi.modulos.envios.configuracao import prazo_aguardando
from toqqi.modulos.envios.descadastro import descadastrado

# envio que saiu de fato (e-mail enviado; WhatsApp enviado, entregue ou lido)
SAIU = ("enviado", "entregue", "lido")


def data_local(coluna):
    """Data (em São Paulo) de uma coluna timestamptz."""
    return cast(func.timezone(FUSO_NOME, coluna), Date)


def dia_do_lembrete(cfg: ConfigEnvios, enviados):
    """Dias depois do convite para o próximo lembrete (n = enviados + 1); nulo se não houver."""
    dias = list(cfg.dias_lembretes[: cfg.lembretes])
    if not dias:
        return None
    return case(*[(enviados == i, d) for i, d in enumerate(dias)], else_=None)


@dataclass
class Estado:
    """Colunas calculadas da fila para uma configuração e um "hoje"."""
    uc: object          # último convite (lateral)
    ue: object          # último envio desse convite (lateral)
    situacao: object
    proximo_lembrete: object
    descanso_ate: object
    saiu: object

    def juntar(self, consulta: Select) -> Select:
        return consulta.outerjoin(self.uc, true()).outerjoin(self.ue, true())


def estado(cfg: ConfigEnvios, hoje: date) -> Estado:
    # As buscas por contato levam a conta explícita (além do RLS, cuja política tem `OR app_sistema()`): assim o
    # banco usa os índices (conta_id, contato_id, ...) / (conta_id, convite_id, ...) em vez de varrê-los.
    uc = (select(Convite.id, Convite.criado_em, Convite.respondido_em, Convite.lembretes_enviados,
                 Convite.ultimo_lembrete_em)
          .where(Convite.conta_id == Contato.conta_id, Convite.contato_id == Contato.id,
                 Convite.canal.in_(("email", "whatsapp")))
          .order_by(Convite.criado_em.desc(), Convite.id.desc()).limit(1)
          .correlate(Contato).lateral("uc"))
    ue = (select(Envio.id, Envio.situacao, Envio.erro)
          .where(Envio.conta_id == Contato.conta_id, Envio.convite_id == uc.c.id, Envio.tipo == "convite")
          .order_by(Envio.id.desc()).limit(1).correlate(Contato, uc).lateral("ue"))
    # data da resposta (informada ou de entrada); o histórico importado não mexe na fila
    ultima_resposta = (select(func.max(Resposta.data_resposta))
                       .where(Resposta.conta_id == Contato.conta_id, Resposta.contato_id == Contato.id,
                              Resposta.origem != "importacao")
                       .correlate(Contato).scalar_subquery())
    data_convite = data_local(uc.c.criado_em)
    saiu = or_(descadastrado(Contato.email, Contato.telefone), Contato.recebe_pesquisas.is_(False))
    respondeu_ultimo = or_(uc.c.respondido_em.is_not(None),
                           and_(ultima_resposta.is_not(None),
                                or_(uc.c.id.is_(None), ultima_resposta >= uc.c.criado_em)))
    aguardando = and_(uc.c.id.is_not(None), uc.c.respondido_em.is_(None),
                      data_convite >= hoje - timedelta(days=prazo_aguardando(cfg)))
    situacao = case(
        (Contato.ativo.is_(False), "inativo"),
        (saiu, "saiu_da_lista"),
        (ue.c.situacao == "erro", "nao_saiu"),
        (ue.c.situacao == "pendente", "enviando"),
        (aguardando, "aguardando"),
        (and_(respondeu_ultimo, Contato.proximo_envio > hoje), "respondeu"),
        (or_(Contato.proximo_envio.is_(None), Contato.proximo_envio <= hoje), "na_fila"),
        else_="aguardando_intervalo",
    )
    dia = dia_do_lembrete(cfg, uc.c.lembretes_enviados)
    if dia is None:
        proximo_lembrete = cast(None, Date)
    else:
        proximo_lembrete = case(
            (and_(aguardando, ue.c.situacao.in_(SAIU), dia.is_not(None)),
             func.greatest(data_convite + dia, hoje)),
            else_=None,
        )
    fim_descanso = data_local(Contato.ultimo_envio) + cfg.descanso_dias
    descanso_ate = (case((fim_descanso > hoje, fim_descanso), else_=None) if cfg.descanso_dias > 0
                    else cast(None, Date))
    return Estado(uc, ue, situacao, proximo_lembrete, descanso_ate, saiu)


def consulta_fila(cfg: ConfigEnvios, hoje: date) -> Select:
    """Subconsulta com uma linha por contato e as colunas de ContatoEnvio."""
    e = estado(cfg, hoje)
    base = select(
        Contato.id, Contato.nome, Contato.email, Contato.telefone, Contato.ativo, Contato.falhas,
        Contato.empresa_id, Empresa.nome.label("empresa_nome"),
        Empresa.grupo_id, Grupo.nome.label("grupo_nome"),
        Empresa.responsavel_id, Responsavel.nome.label("responsavel_nome"),
        Contato.ultimo_envio, Contato.proximo_envio,
        func.coalesce(e.uc.c.lembretes_enviados, 0).label("lembretes_enviados"),
        e.proximo_lembrete.label("proximo_lembrete"),
        e.descanso_ate.label("descanso_ate"),
        case((e.ue.c.situacao == "erro", e.ue.c.erro), else_=None).label("ultimo_erro"),
        e.situacao.label("situacao"),
        e.saiu.label("saiu"),
    ).select_from(Contato)
    base = (e.juntar(base)
            .outerjoin(Empresa, Empresa.id == Contato.empresa_id)
            .outerjoin(Grupo, Grupo.id == Empresa.grupo_id)
            .outerjoin(Responsavel, Responsavel.id == Empresa.responsavel_id))
    return base.subquery("fila")


def _inicio(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=FUSO)


def filtrar(q, f, hoje: date) -> list:
    """Condições sobre a subconsulta `q` a partir de FiltrosFila."""
    conds = []
    if f.situacao:
        conds.append(q.c.situacao == f.situacao)
    if not f.mostrar_inativos and f.situacao != "inativo":
        conds.append(q.c.ativo.is_(True))
    if f.busca:
        termo = f"%{f.busca.strip()}%"
        alternativas = [q.c.nome.ilike(termo), cast(q.c.email, String).ilike(termo),
                        cast(q.c.empresa_nome, String).ilike(termo)]
        digitos = so_digitos(f.busca)
        if len(digitos) >= 4:
            alternativas.append(q.c.telefone.contains(digitos))
        conds.append(or_(*alternativas))
    for campo in ("grupo_id", "responsavel_id", "empresa_id"):
        if getattr(f, campo):
            conds.append(q.c[campo] == getattr(f, campo))
    if f.proximo_de:
        conds.append(q.c.proximo_envio >= f.proximo_de)
    if f.proximo_ate:
        conds.append(q.c.proximo_envio <= f.proximo_ate)
    if f.ultimo_de:
        conds.append(q.c.ultimo_envio >= _inicio(f.ultimo_de))
    if f.ultimo_ate:
        conds.append(q.c.ultimo_envio < _inicio(f.ultimo_ate + timedelta(days=1)))
    if f.lembrete:
        conds.append(q.c.proximo_lembrete == (hoje if f.lembrete == "hoje" else hoje + timedelta(days=1)))
    return conds


def ordem(q) -> list:
    """Mais atrasado primeiro (sem próximo envio antes de todos)."""
    return [q.c.proximo_envio.asc().nulls_first(), func.lower(q.c.nome), q.c.id]


def contato_envio_json(linha) -> dict:
    return {
        "id": linha.id, "nome": linha.nome, "email": linha.email, "telefone": linha.telefone,
        "empresa": ref(linha.empresa_id, linha.empresa_nome),
        "grupo": ref(linha.grupo_id, linha.grupo_nome),
        "responsavel": ref(linha.responsavel_id, linha.responsavel_nome),
        "ativo": linha.ativo, "situacao": linha.situacao,
        "ultimo_envio": linha.ultimo_envio, "proximo_envio": linha.proximo_envio,
        "lembretes_enviados": linha.lembretes_enviados, "proximo_lembrete": linha.proximo_lembrete,
        "descanso_ate": linha.descanso_ate, "ultimo_erro": linha.ultimo_erro,
        "enviando": linha.situacao == "enviando",
    }
