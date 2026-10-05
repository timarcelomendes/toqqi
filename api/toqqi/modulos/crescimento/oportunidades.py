"""Oportunidades (etapa 5c; ver com `crescimento.ver`, registrar oferta com `crescimento.tratar`): clientes felizes para
receber uma oferta, em duas listas; as ofertas feitas (com o resultado); e o resumo do Crescimento.

- `pode_crescer`: o quadrante "Pode crescer" da matriz NPS × valor de Relatórios › Empresas (NPS >= 0 e valor abaixo da
  mediana) nos últimos 90 dias, pela mesma função do relatório (`relatorios.servico._dados_empresas`) com o filtro
  padrão da tela de Relatórios (últimos 90 dias, só empresas ativas, sem outros filtros). Grupo e responsável só
  filtram a lista: o quadrante é o da carteira toda, como na matriz sem filtros. Ordem: maior NPS, depois menor valor.
- `promotores`: empresas ativas com resposta de promotor (NPS 9–10) nos últimos 30 dias; ordem: promotor mais recente.
- Regra de ouro (as duas listas): fora as empresas inativas, com detrator (NPS 0–6) nos últimos 90 dias ou com plano
  de ação aberto; o contato sugerido nunca é inativo nem descadastrado.

Por empresa: `nps` = o do período da lista (90 ou 30 dias); `ultima_resposta` = a resposta mais recente que conta para
a lista (NPS do período em `pode_crescer`; de promotor em `promotores`); `contato` = quem deu a resposta mais recente
que conta para a lista, entre os contatos ativos, não descadastrados e com telefone ou e-mail (senão null);
`ultima_oferta` = {id, criada_em, resultado, valor} da oferta mais recente feita à empresa (de qualquer lista).
Respostas arquivadas não contam. Dias de São Paulo (`relogio`), hoje incluído ("últimos 90 dias" = de hoje − 89 até
hoje, como os períodos das telas).

Oferta registrada (`criar_oferta`): vale a mesma regra de ouro, conferida na hora (a lista da tela pode estar velha):
empresa inativa, com plano de ação aberto ou com detrator nos últimos 90 dias é 422 com o motivo para a tela ("Esta
empresa saiu das oportunidades: …"), assim como contato de outra empresa, inativo ou descadastrado.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, not_, or_, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.filtros import entre_datas
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Acao, Contato, Empresa, Indicacao, Oferta, Resposta, Usuario
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.crescimento.indicacoes import telefone_legivel
from toqqi.modulos.empresas.servico import conferir_referencias, ref
from toqqi.modulos.envios.descadastro import descadastrado, esta_descadastrado
from toqqi.modulos.painel.servico import _validar_periodo
from toqqi.modulos.relatorios import servico as relatorios
from toqqi.modulos.relatorios.regras import FiltroEmpresas, carregar_empresas, chave_nome, data_br, gerar_csv, num
from toqqi.modulos.respostas import indicadores as ind

DIAS_PODE_CRESCER = 90
DIAS_PROMOTORES = 30
DIAS_DETRATOR = 90
DIAS_RESUMO = 90
ROTULOS_RESULTADO = {"aceitou": "Aceitou", "recusou": "Recusou", "sem_resposta": "Sem resposta"}
REFERENCIAS_OFERTA = {"empresa_id": (Empresa, "Empresa não encontrada."),
                      "contato_id": (Contato, "Contato não encontrado.")}
PROMOTOR = Resposta.grupo == "promotor"


def desde(hoje: date, dias: int) -> date:
    """Primeiro dia dos "últimos `dias` dias" (hoje incluído)."""
    return hoje - timedelta(days=dias - 1)


@dataclass
class _FiltroRelatorio:
    """O filtro padrão de Relatórios › Empresas: o período, só empresas ativas e nenhum outro filtro."""
    de: date
    ate: date
    grupo_id: int | None = None
    so_ativos: bool | None = None  # vazio = true, como na tela


@dataclass
class _Candidata:
    id: int
    nome: str
    valor_mensal: Decimal | None
    grupo: dict | None
    responsavel: dict | None
    nps: dict


# ---- as duas listas -----------------------------------------------------------------------

def _com_detrator(conta_id: int, hoje: date, *extra):
    """Ids das empresas com detrator (NPS 0–6) nos últimos 90 dias."""
    p = relatorios.Periodo(conta_id, desde(hoje, DIAS_DETRATOR), hoje)
    return select(Resposta.empresa_id).distinct().where(
        *p.respostas(relatorios.NPS, Resposta.grupo == "detrator", Resposta.empresa_id.is_not(None), *extra))


def _com_acao_aberta(conta_id: int, *extra):
    """Ids das empresas com plano de ação aberto."""
    return select(Acao.empresa_id).distinct().where(
        Acao.conta_id == conta_id, aberta(), Acao.empresa_id.is_not(None), *extra)


def _em_risco(s: Session, hoje: date, empresa_ids: list[int] | None = None) -> set[int]:
    """Etapa 5i: empresas com a saúde da conta em Risco."""
    from toqqi.modulos.saude.calculo import saude_das_empresas

    return {i for i, sd in saude_das_empresas(s, hoje, empresa_ids).items() if sd and sd["faixa"] == "risco"}


def _excluidas(s: Session, conta_id: int, hoje: date) -> set[int]:
    """Regra de ouro: empresas com detrator (NPS 0–6) nos últimos 90 dias, com plano de ação aberto ou (etapa 5i) com
    a saúde em Risco."""
    return set(s.scalars(_com_detrator(conta_id, hoje))) | set(s.scalars(_com_acao_aberta(conta_id))) | \
        _em_risco(s, hoje)


def _fora_da_regra(s: Session, conta_id: int, e: Empresa, hoje: date) -> str | None:
    """Por que a empresa saiu das oportunidades pela regra de ouro (o fim da frase para a tela), ou None."""
    if not e.ativa:
        return "ela está inativa."
    if s.scalar(_com_acao_aberta(conta_id, Acao.empresa_id == e.id).limit(1)) is not None:
        return "ela tem um plano de ação aberto."
    if s.scalar(_com_detrator(conta_id, hoje, Resposta.empresa_id == e.id).limit(1)) is not None:
        return f"ela deu uma nota de detrator (0 a 6) nos últimos {DIAS_DETRATOR} dias."
    if _em_risco(s, hoje, [e.id]):
        return "a saúde da conta está em Risco."
    return None


def _periodo_da_lista(conta_id: int, lista: str, hoje: date) -> tuple[relatorios.Periodo, list]:
    """(período da lista, condições extras das respostas que contam para ela)."""
    if lista == "pode_crescer":
        return relatorios.Periodo(conta_id, desde(hoje, DIAS_PODE_CRESCER), hoje), [relatorios.NPS]
    return relatorios.Periodo(conta_id, desde(hoje, DIAS_PROMOTORES), hoje), [relatorios.NPS, PROMOTOR]


def _pode_crescer(s: Session, ctx: Contexto, hoje: date) -> list[_Candidata]:
    itens, _, _ = relatorios._dados_empresas(s, ctx, _FiltroRelatorio(desde(hoje, DIAS_PODE_CRESCER), hoje))
    fora = _excluidas(s, ctx.conta_id, hoje)
    candidatas = [_Candidata(x["empresa"]["id"], x["empresa"]["nome"], x["valor_mensal"], x["grupo"],
                             x["responsavel"], x["nps"])
                  for x in itens if x["quadrante"] == "crescer" and x["empresa"]["id"] not in fora]
    return sorted(candidatas, key=lambda c: (-c.nps["valor"], c.valor_mensal, chave_nome(c.nome), c.id))


def _promotores(s: Session, ctx: Contexto, hoje: date) -> list[_Candidata]:
    p, extras = _periodo_da_lista(ctx.conta_id, "promotores", hoje)
    ultimo = dict(s.execute(
        select(Resposta.empresa_id, func.max(Resposta.data_resposta))
        .where(*p.respostas(*extras, Resposta.empresa_id.is_not(None))).group_by(Resposta.empresa_id)).all())
    if not ultimo:
        return []
    fora = _excluidas(s, ctx.conta_id, hoje)
    nps = relatorios._nps_empresas(s, p)
    candidatas = []
    for e in carregar_empresas(s, ctx.conta_id, FiltroEmpresas(so_ativos=True), hoje):
        if e.id in ultimo and e.id not in fora:
            pr, ne, de, _ = nps.get(e.id, (0, 0, 0, 0))
            candidatas.append((ultimo[e.id], _Candidata(e.id, e.nome, e.valor_mensal, e.grupo, e.responsavel,
                                                         ind.bloco_nps(pr, ne, de))))
    candidatas.sort(key=lambda x: (-x[0].timestamp(), chave_nome(x[1].nome), x[1].id))
    return [c for _, c in candidatas]


def _filtrar(candidatas: list[_Candidata], f) -> list[_Candidata]:
    if f.grupo_id is not None:
        candidatas = [c for c in candidatas if (c.grupo or {}).get("id") == f.grupo_id]
    if f.responsavel_id is not None:
        alvo = None if f.responsavel_id == 0 else f.responsavel_id
        candidatas = [c for c in candidatas if (c.responsavel or {}).get("id") == alvo]
    return candidatas


def _candidatas(s: Session, ctx: Contexto, f, hoje: date) -> list[_Candidata]:
    lista = f.lista or "pode_crescer"
    escolhidas = _pode_crescer(s, ctx, hoje) if lista == "pode_crescer" else _promotores(s, ctx, hoje)
    return _filtrar(escolhidas, f)


# ---- detalhes por empresa (resposta, contato sugerido e última oferta) --------------------

def _detalhes(s: Session, conta_id: int, lista: str, hoje: date, ids: list[int]) -> tuple[dict, dict, dict]:
    if not ids:
        return {}, {}, {}
    p, extras = _periodo_da_lista(conta_id, lista, hoje)
    conds = p.respostas(*extras, Resposta.empresa_id.in_(ids))
    ordem = (Resposta.empresa_id, Resposta.data_resposta.desc(), Resposta.id.desc())
    ultimas = {e: {"data": d, "nota": n, "tipo_nota": t} for e, d, n, t in s.execute(
        select(Resposta.empresa_id, Resposta.data_resposta, Resposta.nota, Resposta.tipo_nota)
        .distinct(Resposta.empresa_id).where(*conds).order_by(*ordem))}
    contatos = {e: {"id": i, "nome": n, "telefone": tel, "email": em} for e, i, n, tel, em in s.execute(
        select(Resposta.empresa_id, Contato.id, Contato.nome, Contato.telefone, Contato.email)
        .distinct(Resposta.empresa_id).join(Contato, Contato.id == Resposta.contato_id)
        .where(*conds, Contato.ativo.is_(True), or_(Contato.telefone.is_not(None), Contato.email.is_not(None)),
               not_(descadastrado(Contato.email, Contato.telefone)))
        .order_by(*ordem))}
    ofertas = {e: {"id": i, "criada_em": c, "resultado": r, "valor": v} for e, i, c, r, v in s.execute(
        select(Oferta.empresa_id, Oferta.id, Oferta.criada_em, Oferta.resultado, Oferta.valor)
        .distinct(Oferta.empresa_id).where(Oferta.conta_id == conta_id, Oferta.empresa_id.in_(ids))
        .order_by(Oferta.empresa_id, Oferta.criada_em.desc(), Oferta.id.desc()))}
    return ultimas, contatos, ofertas


def _item(c: _Candidata, ultimas: dict, contatos: dict, ofertas: dict) -> dict:
    return {"empresa": {"id": c.id, "nome": c.nome, "valor_mensal": c.valor_mensal}, "grupo": c.grupo,
            "responsavel": c.responsavel, "nps": {"valor": c.nps["valor"], "total": c.nps["total"]},
            "contato": contatos.get(c.id), "ultima_resposta": ultimas.get(c.id),
            "ultima_oferta": ofertas.get(c.id)}


def listar(ctx: Contexto, f, pg: Pagina) -> dict:
    hoje = relogio.hoje()
    lista = f.lista or "pode_crescer"
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        candidatas = _candidatas(s, ctx, f, hoje)
        pagina = candidatas[pg.offset:pg.offset + pg.por_pagina]
        detalhes = _detalhes(s, ctx.conta_id, lista, hoje, [c.id for c in pagina])
    return pg.resultado([_item(c, *detalhes) for c in pagina], len(candidatas))


CABECALHO_CSV = ["Empresa", "Grupo", "Responsável", "Valor mensal", "NPS", "Respostas", "Contato", "Telefone",
                 "E-mail", "Última resposta", "Última oferta"]


def exportar_csv(ctx: Contexto, f) -> str:
    hoje = relogio.hoje()
    lista = f.lista or "pode_crescer"
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        candidatas = _candidatas(s, ctx, f, hoje)
        ultimas, contatos, ofertas = _detalhes(s, ctx.conta_id, lista, hoje, [c.id for c in candidatas])
    linhas = []
    for c in candidatas:
        contato, ultima, oferta = contatos.get(c.id) or {}, ultimas.get(c.id), ofertas.get(c.id)
        texto_oferta = ""
        if oferta:
            texto_oferta = data_br(oferta["criada_em"])
            if oferta["resultado"]:
                texto_oferta += f" ({ROTULOS_RESULTADO[oferta['resultado']]})"
        linhas.append([c.nome, (c.grupo or {}).get("nome", ""), (c.responsavel or {}).get("nome", ""),
                       num(c.valor_mensal), num(c.nps["valor"]), num(c.nps["total"]), contato.get("nome") or "",
                       telefone_legivel(contato.get("telefone")), contato.get("email") or "",
                       data_br(ultima["data"]) if ultima else "", texto_oferta])
    return gerar_csv(CABECALHO_CSV, linhas)


def nome_csv(lista: str | None) -> str:
    return f"oportunidades-{(lista or 'pode_crescer').replace('_', '-')}-{relogio.hoje().isoformat()}.csv"


# ---- ofertas ------------------------------------------------------------------------------

def _oferta_json(s: Session, o: Oferta) -> dict:
    empresa = s.get(Empresa, o.empresa_id)
    contato = s.get(Contato, o.contato_id) if o.contato_id else None
    usuario = s.get(Usuario, o.usuario_id) if o.usuario_id else None
    return {"id": o.id, "empresa": ref(o.empresa_id, empresa.nome if empresa else None),
            "contato": ref(o.contato_id, contato.nome if contato else None), "lista": o.lista, "canal": o.canal,
            "texto": o.texto, "usuario": ref(o.usuario_id, usuario.nome if usuario else None),
            "criada_em": o.criada_em, "resultado": o.resultado, "valor": o.valor, "resultado_em": o.resultado_em}


def _recusada(campo: str, motivo: str) -> AppError:
    """422 com o motivo na mensagem e no campo (a tela mostra o do campo)."""
    return AppError(422, "dados_invalidos", motivo, {campo: motivo})


def _conferir_regra_de_ouro(s: Session, conta_id: int, dados) -> None:
    empresa = s.get(Empresa, dados.empresa_id)
    motivo = _fora_da_regra(s, conta_id, empresa, relogio.hoje())
    if motivo is not None:
        raise _recusada("empresa_id", f"Esta empresa saiu das oportunidades: {motivo}")
    if dados.contato_id is None:
        return
    contato = s.get(Contato, dados.contato_id)
    if contato.empresa_id != empresa.id:
        raise _recusada("contato_id", "Este contato não é desta empresa.")
    if not contato.ativo:
        raise _recusada("contato_id", "Este contato está inativo e não recebe ofertas.")
    if esta_descadastrado(s, contato.email, contato.telefone):
        raise _recusada("contato_id", "Este contato saiu da lista e não recebe ofertas.")


def criar_oferta(ctx: Contexto, dados) -> dict:
    """A tela registra a oferta ao abrir o WhatsApp (ou o e-mail). A regra de ouro vale na hora (a lista da tela pode
    estar velha): empresa inativa, com plano de ação aberto ou detrator nos últimos 90 dias não recebe oferta, nem
    contato de outra empresa, inativo ou descadastrado (422 com o motivo)."""
    with em_conta(ctx.conta_id) as s:
        conferir_referencias(s, dados.model_dump(), REFERENCIAS_OFERTA)
        _conferir_regra_de_ouro(s, ctx.conta_id, dados)
        o = Oferta(empresa_id=dados.empresa_id, contato_id=dados.contato_id, lista=dados.lista, canal=dados.canal,
                   texto=dados.texto, usuario_id=ctx.usuario_id, criada_em=relogio.agora())
        s.add(o)
        s.flush()
        s.refresh(o)  # relê do banco: datas no mesmo formato das listas
        return _oferta_json(s, o)


def alterar_oferta(ctx: Contexto, oferta_id: int, dados) -> dict:
    """Resultado (null = sem resultado) e valor, que só existe com 'aceitou': os outros resultados limpam o valor. Com
    'aceitou', o valor só muda quando vem um número; ausente ou null mantém o que já havia (a tela reabre o resultado
    com o campo vazio e não pode apagar o valor sem querer). Quem passa a 'aceitou' sem valor fica sem valor; para
    tirar o valor de uma oferta aceita, troque o resultado."""
    enviados = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        o = s.get(Oferta, oferta_id, with_for_update=True)
        if o is None:
            raise nao_encontrado("Oferta não encontrada.")
        resultado = dados.resultado if "resultado" in enviados else o.resultado
        valor = dados.valor if dados.valor is not None else o.valor  # o.valor só existe com 'aceitou'
        if resultado != "aceitou":
            valor = None
        if resultado != o.resultado:
            o.resultado_em = relogio.agora() if resultado is not None else None
        o.resultado, o.valor = resultado, valor
        s.flush()
        s.refresh(o)
        return _oferta_json(s, o)


# ---- resumo -------------------------------------------------------------------------------

def resumo(ctx: Contexto, de: date | None, ate: date | None) -> dict:
    """Indicações recebidas no período (as que viraram cliente e a receita mensal delas) e ofertas feitas no período
    (aceitas e a receita). Sem `de` nem `ate`: os últimos 90 dias. `taxa` em % inteiro (null sem base)."""
    _validar_periodo(de, ate)
    if de is None and ate is None:
        ate = relogio.hoje()
        de = desde(ate, DIAS_RESUMO)
    with em_conta(ctx.conta_id) as s:
        i = s.execute(select(func.count(), func.count().filter(Indicacao.situacao == "cliente"),
                             func.coalesce(func.sum(Indicacao.valor_mensal), 0))
                      .where(Indicacao.conta_id == ctx.conta_id, *entre_datas(Indicacao.criada_em, de, ate))).one()
        o = s.execute(select(func.count(), func.count().filter(Oferta.resultado == "aceitou"),
                             func.coalesce(func.sum(Oferta.valor), 0))
                      .where(Oferta.conta_id == ctx.conta_id, *entre_datas(Oferta.criada_em, de, ate))).one()
    return {"periodo": {"de": de, "ate": ate},
            "indicacoes": {"recebidas": i[0], "clientes": i[1], "taxa": ind.percentual(i[1], i[0]),
                           "receita_mensal": i[2]},
            "ofertas": {"feitas": o[0], "aceitas": o[1], "taxa": ind.percentual(o[1], o[0]), "receita": o[2]}}
