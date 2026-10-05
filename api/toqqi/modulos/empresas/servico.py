"""Empresas (clientes da conta)."""
from datetime import date

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Contato, Empresa, Grupo, Responsavel, Segmento
from toqqi.modulos.empresas import desfecho
from toqqi.modulos.saude.calculo import saude_das_empresas
from toqqi.modulos.relatorios.regras import data_br, gerar_csv, num, sim_nao

REFERENCIAS = {
    "grupo_id": (Grupo, "Grupo não encontrado."),
    "segmento_id": (Segmento, "Segmento não encontrado."),
    "responsavel_id": (Responsavel, "Responsável não encontrado."),
}


def ref(i, n) -> dict | None:
    return {"id": i, "nome": n} if i is not None else None


def _consulta():
    qtd = (select(Contato.empresa_id, func.count().label("n")).where(Contato.empresa_id.is_not(None))
           .group_by(Contato.empresa_id).subquery())
    return (
        select(Empresa, Grupo.nome, Segmento.nome, Responsavel.nome, func.coalesce(qtd.c.n, 0))
        .outerjoin(Grupo, Grupo.id == Empresa.grupo_id)
        .outerjoin(Segmento, Segmento.id == Empresa.segmento_id)
        .outerjoin(Responsavel, Responsavel.id == Empresa.responsavel_id)
        .outerjoin(qtd, qtd.c.empresa_id == Empresa.id)
    )


def _json(linha) -> dict:
    e, grupo, segmento, responsavel, contatos = linha
    return {
        "id": e.id, "nome": e.nome, "documento": e.documento,
        "grupo": ref(e.grupo_id, grupo), "segmento": ref(e.segmento_id, segmento),
        "responsavel": ref(e.responsavel_id, responsavel),
        "valor_mensal": e.valor_mensal, "cliente_desde": e.cliente_desde, "codigo_externo": e.codigo_externo,
        "ativa": e.ativa, "contatos": contatos, "criada_em": e.criada_em,
        # etapa 5i: desfecho
        "renovacao_em": e.renovacao_em, "situacao": desfecho.situacao(e), "perdida_em": e.perdida_em,
        "motivo_perda": e.motivo_perda, "motivo_perda_rotulo": desfecho.MOTIVOS.get(e.motivo_perda),
        "motivo_detalhe": e.motivo_detalhe,
    }


def _uma(s: Session, empresa_id: int) -> dict:
    linha = s.execute(_consulta().where(Empresa.id == empresa_id)).one_or_none()
    if linha is None:
        raise nao_encontrado("Empresa não encontrada.")
    return _json(linha)


def condicoes(busca: str | None, grupo_id: int | None, segmento_id: int | None, responsavel_id: int | None,
              ativa: str) -> list:
    """Filtros de `GET /empresas` (a lista e o CSV)."""
    filtros = []
    if busca:
        termo = f"%{busca}%"
        documento = "".join(ch for ch in busca if ch.isascii() and ch.isalnum()).upper()  # 12.ABC.345 → 12ABC345
        filtros.append(or_(cast(Empresa.nome, String).ilike(termo), Empresa.documento.ilike(termo),
                           Empresa.codigo_externo.ilike(termo),
                           *([Empresa.documento.ilike(f"%{documento}%")] if documento else [])))
    if grupo_id:
        filtros.append(Empresa.grupo_id == grupo_id)
    if segmento_id:
        filtros.append(Empresa.segmento_id == segmento_id)
    if responsavel_id:
        filtros.append(Empresa.responsavel_id == responsavel_id)
    if ativa in ("true", "false"):
        filtros.append(Empresa.ativa.is_(ativa == "true"))
    return filtros


ORDEM = (func.lower(cast(Empresa.nome, String)), Empresa.id)


def ve_numeros(ctx: Contexto) -> bool:
    """Etapa 5i: a saúde da conta é um número do painel: pede `painel.ver` ou `relatorios.ver`."""
    return "painel.ver" in ctx.permissoes or "relatorios.ver" in ctx.permissoes


def _saude_resumo(sd: dict | None) -> dict | None:
    return None if sd is None else {"faixa": sd["faixa"], "nota": sd["nota"], "destaque": sd["destaque"],
                                    "porque": sd["porques"][0]["texto"] if sd["porques"] else None}


_PESO_FAIXA = {"risco": 0, "atencao": 1, "saudavel": 2, "sem_dados": 3}


def listar(ctx: Contexto, pg: Pagina, busca: str | None, grupo_id: int | None, segmento_id: int | None,
           responsavel_id: int | None, ativa: str, saude: str | None = None, ordem: str = "nome") -> dict:
    """Etapa 5i: cada item ganha `saude` ({faixa, nota, destaque, porque} ou null: pausada, perdida ou sem a permissão
    dos números); `saude=` filtra pela faixa (só ativas) e `ordem=saude` põe Risco (menor nota) primeiro."""
    if saude:
        ativa = "true"
    numeros = ve_numeros(ctx)
    if (saude or ordem == "saude") and not numeros:
        raise AppError(403, "sem_permissao", "Você não tem permissão para ver a saúde das empresas.")
    filtros = [Empresa.conta_id == ctx.conta_id, *condicoes(busca, grupo_id, segmento_id, responsavel_id, ativa)]
    with em_conta(ctx.conta_id) as s:
        if saude or ordem in ("saude", "renovacao"):
            linhas = s.execute(_consulta().where(*filtros).order_by(*ORDEM)).all()
            saudes = saude_das_empresas(s, empresa_ids=[x[0].id for x in linhas]) if numeros else {}
            if saude:
                linhas = [x for x in linhas if saudes.get(x[0].id, {}).get("faixa") == saude]
            if ordem == "saude":
                linhas.sort(key=lambda x: (_PESO_FAIXA[saudes[x[0].id]["faixa"]] if x[0].id in saudes else 9,
                                           saudes.get(x[0].id, {}).get("nota") or 0))
            elif ordem == "renovacao":
                linhas.sort(key=lambda x: (x[0].renovacao_em is None, x[0].renovacao_em or date.max))
            total = len(linhas)
            linhas = linhas[pg.offset:pg.offset + pg.por_pagina]
        else:
            total = s.scalar(select(func.count()).select_from(Empresa).where(*filtros))
            linhas = s.execute(_consulta().where(*filtros).order_by(*ORDEM)
                               .limit(pg.por_pagina).offset(pg.offset)).all()
            saudes = saude_das_empresas(s, empresa_ids=[x[0].id for x in linhas]) if numeros else {}
    return pg.resultado([_json(x) | {"saude": _saude_resumo(saudes.get(x[0].id))} for x in linhas], total)


def saude(ctx: Contexto, empresa_id: int) -> dict:
    """Etapa 5i: a saúde completa de uma empresa (critérios e porquês); null = pausada ou perdida."""
    if not ve_numeros(ctx):
        raise AppError(403, "sem_permissao", "Você não tem permissão para ver a saúde das empresas.")
    with em_conta(ctx.conta_id) as s:
        if s.get(Empresa, empresa_id) is None:
            raise nao_encontrado("Empresa não encontrada.")
        return {"empresa_id": empresa_id, "saude": saude_das_empresas(s, empresa_ids=[empresa_id]).get(empresa_id)}


# ---- "Exportar CSV" (etapa 5f) --------------------------------------------------------------

CABECALHO_CSV = ["Nome", "CPF/CNPJ", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde",
                 "Código externo", "Ativa", "Contatos", "Criada em"]


def exportar_csv(ctx: Contexto, busca: str | None, grupo_id: int | None, segmento_id: int | None,
                 responsavel_id: int | None, ativa: str) -> str:
    """Os filtros, padrões e ordem da lista, sem paginação. Auditoria `exportacao_csv` {lista, linhas} (sem a
    busca)."""
    filtros = [Empresa.conta_id == ctx.conta_id, *condicoes(busca, grupo_id, segmento_id, responsavel_id, ativa)]
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        saida = [[e.nome, e.documento or "", grupo or "", segmento or "", responsavel or "", num(e.valor_mensal),
                  data_br(e.cliente_desde), e.codigo_externo or "", sim_nao(e.ativa), num(contatos),
                  data_br(e.criada_em)]
                 for e, grupo, segmento, responsavel, contatos in s.execute(
                     _consulta().where(*filtros).order_by(*ORDEM).execution_options(yield_per=2000))]
        registrar(s, "exportacao_csv", "info", {"lista": "empresas", "linhas": len(saida)}, usuario_id=ctx.usuario_id)
    return gerar_csv(CABECALHO_CSV, saida)


def nome_csv() -> str:
    return f"empresas-{relogio.hoje().isoformat()}.csv"


def obter(ctx: Contexto, empresa_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _uma(s, empresa_id)


def conferir_referencias(s: Session, valores: dict, referencias: dict) -> None:
    """Ids de outras tabelas precisam existir na conta (RLS: de outra conta = não existe)."""
    campos = {}
    for campo, (modelo, msg) in referencias.items():
        v = valores.get(campo)
        if v is not None and s.get(modelo, v) is None:
            campos[campo] = msg
    if campos:
        raise AppError(422, "dados_invalidos", "Confira os campos destacados.", campos)


def _salvar(s: Session) -> None:
    try:
        with s.begin_nested():
            s.flush()
    except IntegrityError:
        msg = "Já existe uma empresa com este nome."
        raise AppError(409, "nome_em_uso", msg, {"nome": msg})


def criar(ctx: Contexto, dados) -> dict:
    valores = dados.model_dump()
    with em_conta(ctx.conta_id) as s:
        conferir_referencias(s, valores, REFERENCIAS)
        desfecho.marcar(s, "tela", ctx.usuario_id)
        e = Empresa(conta_id=ctx.conta_id, **valores)
        s.add(e)
        _salvar(s)
        return _uma(s, e.id)


def alterar(ctx: Contexto, empresa_id: int, dados) -> dict:
    valores = {c: getattr(dados, c) for c in dados.model_fields_set}
    if valores.get("nome", "") is None:
        del valores["nome"]
    if "ativa" in valores and valores["ativa"] is None:
        del valores["ativa"]
    with em_conta(ctx.conta_id) as s:
        e = s.get(Empresa, empresa_id)
        if e is None:
            raise nao_encontrado("Empresa não encontrada.")
        conferir_referencias(s, valores, REFERENCIAS)
        if e.perdida_em and valores.get("ativa") is True:
            raise AppError(409, "empresa_perdida", "Esta empresa foi marcada como perdida. Use “Voltou a ser cliente”.")
        desfecho.marcar(s, "tela", ctx.usuario_id)
        for campo, valor in valores.items():
            setattr(e, campo, valor)
        _salvar(s)
        return _uma(s, e.id)


def excluir(ctx: Contexto, empresa_id: int) -> None:
    if ctx.perfil != "admin":
        raise AppError(403, "sem_permissao", "Só o administrador da conta pode excluir empresas.")
    with em_conta(ctx.conta_id) as s:
        e = s.get(Empresa, empresa_id)
        if e is None:
            raise nao_encontrado("Empresa não encontrada.")
        contatos = s.scalar(select(func.count()).select_from(Contato).where(Contato.empresa_id == e.id))
        registrar(s, "empresa_excluida", "atencao",
                  {"empresa": {"id": e.id, "nome": e.nome}, "contatos_sem_empresa": contatos},
                  usuario_id=ctx.usuario_id)
        s.delete(e)  # contatos ficam sem empresa (ON DELETE SET NULL)
