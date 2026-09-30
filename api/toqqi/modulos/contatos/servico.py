"""Contatos (pessoas das empresas clientes que recebem as pesquisas)."""
import secrets

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.paginacao import Pagina
from toqqi.core.texto import so_digitos
from toqqi.modelos import Cargo, Contato, Empresa, Formulario, PerfilContato, Resposta
from toqqi.modulos.empresas.servico import conferir_referencias, ref
from toqqi.modulos.respostas.convites import criar_convite, link_do_convite

REFERENCIAS = {
    "empresa_id": (Empresa, "Empresa não encontrada."),
    "cargo_id": (Cargo, "Cargo não encontrado."),
    "perfil_id": (PerfilContato, "Perfil não encontrado."),
}


def novo_codigo(usados: set[str]) -> str:
    while True:
        c = str(secrets.randbelow(900_000_000) + 100_000_000)
        if c not in usados:
            usados.add(c)
            return c


def codigo_livre(s: Session) -> str:
    for _ in range(20):
        c = novo_codigo(set())
        if not s.scalar(select(exists().where(Contato.codigo == c))):
            return c
    return novo_codigo(set())


def situacao(ativo: bool, respondeu: bool) -> str:
    if not ativo:
        return "inativo"
    return "respondeu" if respondeu else "nunca_enviado"


def _consulta():
    respondeu = exists().where(Resposta.contato_id == Contato.id).correlate(Contato).label("respondeu")
    return (
        select(Contato, Empresa.nome, Cargo.nome, PerfilContato.nome, respondeu)
        .outerjoin(Empresa, Empresa.id == Contato.empresa_id)
        .outerjoin(Cargo, Cargo.id == Contato.cargo_id)
        .outerjoin(PerfilContato, PerfilContato.id == Contato.perfil_id)
    )


def _json(linha) -> dict:
    c, empresa, cargo, perfil, respondeu = linha
    return {
        "id": c.id, "codigo": c.codigo, "nome": c.nome, "email": c.email, "telefone": c.telefone,
        "empresa": ref(c.empresa_id, empresa), "cargo": ref(c.cargo_id, cargo), "perfil": ref(c.perfil_id, perfil),
        "codigo_externo": c.codigo_externo, "recebe_pesquisas": c.recebe_pesquisas, "ativo": c.ativo,
        "situacao": situacao(c.ativo, respondeu), "ultimo_envio": None, "proximo_envio": None,
        "ultima_nota": c.ultima_nota, "criado_em": c.criado_em,
    }


def _um(s: Session, contato_id: int) -> dict:
    linha = s.execute(_consulta().where(Contato.id == contato_id)).one_or_none()
    if linha is None:
        raise nao_encontrado("Contato não encontrado.")
    return _json(linha)


def listar(ctx: Contexto, pg: Pagina, busca: str | None, empresa_id: int | None, grupo_id: int | None,
           responsavel_id: int | None, perfil_id: int | None, ativo: str) -> dict:
    filtros = []
    if busca:
        termo = f"%{busca}%"
        conds = [Contato.nome.ilike(termo), cast(Contato.email, String).ilike(termo), Contato.codigo == busca,
                 Contato.codigo_externo.ilike(termo), cast(Empresa.nome, String).ilike(termo)]
        digitos = so_digitos(busca)
        if len(digitos) >= 4:
            conds.append(Contato.telefone.contains(digitos))
        filtros.append(or_(*conds))
    if empresa_id:
        filtros.append(Contato.empresa_id == empresa_id)
    if grupo_id:
        filtros.append(Empresa.grupo_id == grupo_id)
    if responsavel_id:
        filtros.append(Empresa.responsavel_id == responsavel_id)
    if perfil_id:
        filtros.append(Contato.perfil_id == perfil_id)
    if ativo in ("true", "false"):
        filtros.append(Contato.ativo.is_(ativo == "true"))
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(select(func.count()).select_from(Contato)
                         .outerjoin(Empresa, Empresa.id == Contato.empresa_id).where(*filtros))
        linhas = s.execute(_consulta().where(*filtros).order_by(func.lower(Contato.nome), Contato.id)
                           .limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([_json(x) for x in linhas], total)


def obter(ctx: Contexto, contato_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        dados = _um(s, contato_id)
        linhas = s.execute(
            select(Resposta, Formulario.nome)
            .join(Formulario, Formulario.id == Resposta.formulario_id)
            .where(Resposta.contato_id == contato_id)
            .order_by(Resposta.criada_em.desc(), Resposta.id.desc())
            .limit(100)
        ).all()
    dados["historico"] = [
        {"tipo": "resposta", "data": r.criada_em, "nota": r.nota, "grupo": r.grupo, "comentario": r.comentario,
         "formulario": {"id": r.formulario_id, "nome": nome}}
        for r, nome in linhas
    ]
    return dados


def erro_email_em_uso() -> AppError:
    msg = "Já existe um contato com este e-mail."
    return AppError(409, "email_em_uso", msg, {"email": msg})


def _exigir_canal(email, telefone) -> None:
    if not email and not telefone:
        msg = "Informe o e-mail ou o telefone."
        raise AppError(422, "dados_invalidos", msg, {"email": msg, "telefone": msg})


def _salvar(s: Session) -> None:
    try:
        with s.begin_nested():
            s.flush()
    except IntegrityError as e:
        if "email" in str(e.orig):
            raise erro_email_em_uso()
        raise


def criar(ctx: Contexto, dados) -> dict:
    valores = dados.model_dump()
    _exigir_canal(valores["email"], valores["telefone"])
    with em_conta(ctx.conta_id) as s:
        conferir_referencias(s, valores, REFERENCIAS)
        c = Contato(conta_id=ctx.conta_id, codigo=codigo_livre(s), **valores)
        s.add(c)
        _salvar(s)
        return _um(s, c.id)


def alterar(ctx: Contexto, contato_id: int, dados) -> dict:
    valores = {c: getattr(dados, c) for c in dados.model_fields_set}
    for campo in ("nome", "recebe_pesquisas", "ativo"):
        if campo in valores and valores[campo] is None:
            del valores[campo]
    with em_conta(ctx.conta_id) as s:
        c = s.get(Contato, contato_id)
        if c is None:
            raise nao_encontrado("Contato não encontrado.")
        conferir_referencias(s, valores, REFERENCIAS)
        _exigir_canal(valores.get("email", c.email), valores.get("telefone", c.telefone))
        for campo, valor in valores.items():
            setattr(c, campo, valor)
        _salvar(s)
        return _um(s, c.id)


def excluir(ctx: Contexto, contato_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        c = s.get(Contato, contato_id)
        if c is None:
            raise nao_encontrado("Contato não encontrado.")
        respostas = s.scalar(select(func.count()).select_from(Resposta).where(Resposta.contato_id == c.id))
        registrar(s, "contato_excluido", "atencao",
                  {"contato": {"id": c.id, "nome": c.nome, "email": c.email}, "respostas_apagadas": respostas},
                  usuario_id=ctx.usuario_id)
        s.delete(c)  # respostas e convites dele vão junto (ON DELETE CASCADE)


def formulario_para_envio(s: Session, formulario_id: int | None) -> Formulario:
    if formulario_id is None:
        f = s.scalar(select(Formulario).where(Formulario.padrao_nps.is_(True)))
        if f is None:
            msg = "Escolha o formulário da pesquisa."
            raise AppError(422, "dados_invalidos", msg, {"formulario_id": msg})
        return f
    f = s.get(Formulario, formulario_id)
    if f is None or f.arquivado:
        raise AppError(422, "dados_invalidos", "Formulário não encontrado.",
                       {"formulario_id": "Formulário não encontrado."})
    if not f.ativo:
        msg = "Este formulário está desativado."
        raise AppError(422, "dados_invalidos", msg, {"formulario_id": msg})
    return f


def link_pesquisa(ctx: Contexto, contato_id: int, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = s.get(Contato, contato_id)
        if c is None:
            raise nao_encontrado("Contato não encontrado.")
        f = formulario_para_envio(s, dados.formulario_id)
        contexto = dados.contexto.model_dump() if dados.contexto else {}
        token = criar_convite(s, f.id, contato_id=c.id, canal="link_manual", assunto=dados.assunto,
                              referencia=dados.referencia, contexto=contexto, empresa_id=c.empresa_id)
    return {"link": link_do_convite(token), "token": token, "expira_em": None}
