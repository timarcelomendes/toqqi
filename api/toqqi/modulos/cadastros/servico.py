"""Cadastros auxiliares (grupos, segmentos, perfis, cargos) e responsáveis."""
import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from toqqi.core import rede
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.modelos import Cargo, Contato, Empresa, Grupo, PerfilContato, Responsavel, Segmento

# tipo → (modelo, coluna que usa o item, rótulo no singular)
TIPOS = {
    "grupos": (Grupo, Empresa.grupo_id, "grupo"),
    "segmentos": (Segmento, Empresa.segmento_id, "segmento"),
    "perfis": (PerfilContato, Contato.perfil_id, "perfil"),
    "cargos": (Cargo, Contato.cargo_id, "cargo"),
}


def erro_nome_em_uso(msg: str = "Já existe um item com este nome.") -> AppError:
    return AppError(409, "nome_em_uso", msg, {"nome": msg})


def _em_uso_subq(coluna):
    return (select(coluna, func.count().label("n")).where(coluna.is_not(None)).group_by(coluna).subquery())


def _itens(s: Session, tipo: str, ids: list[int] | None = None) -> list[dict]:
    modelo, coluna, _ = TIPOS[tipo]
    uso = _em_uso_subq(coluna)
    q = (select(modelo.id, modelo.nome, func.coalesce(uso.c.n, 0))
         .outerjoin(uso, uso.c[coluna.key] == modelo.id)
         .order_by(func.lower(modelo.nome), modelo.id))
    if ids is not None:
        q = q.where(modelo.id.in_(ids))
    return [{"id": i, "nome": n, "em_uso": u} for i, n, u in s.execute(q)]


def listar(ctx: Contexto, tipo: str) -> list[dict]:
    with em_conta(ctx.conta_id) as s:
        return _itens(s, tipo)


def _salvar(s: Session, obj) -> None:
    try:
        with s.begin_nested():
            s.flush()
    except IntegrityError:
        raise erro_nome_em_uso()


def criar(ctx: Contexto, tipo: str, nome: str) -> dict:
    modelo = TIPOS[tipo][0]
    with em_conta(ctx.conta_id) as s:
        obj = modelo(conta_id=ctx.conta_id, nome=nome)
        s.add(obj)
        _salvar(s, obj)
        return _itens(s, tipo, [obj.id])[0]


def _item_ou_404(s: Session, tipo: str, item_id: int):
    obj = s.get(TIPOS[tipo][0], item_id)
    if obj is None:
        raise nao_encontrado("Item não encontrado.")
    return obj


def alterar(ctx: Contexto, tipo: str, item_id: int, nome: str) -> dict:
    with em_conta(ctx.conta_id) as s:
        obj = _item_ou_404(s, tipo, item_id)
        obj.nome = nome
        _salvar(s, obj)
        return _itens(s, tipo, [obj.id])[0]


def excluir(ctx: Contexto, tipo: str, item_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        obj = _item_ou_404(s, tipo, item_id)
        registrar(s, "cadastro_excluido", "atencao", {"tipo": TIPOS[tipo][2], "nome": obj.nome},
                  usuario_id=ctx.usuario_id)
        s.delete(obj)  # FK: quem usava fica sem o item (ON DELETE SET NULL)


def buscar_ou_criar(s: Session, tipo: str, nome: str, cache: dict[str, int] | None = None) -> int:
    """Id do item com esse nome (sem diferenciar maiúsculas); cria se não existir."""
    modelo = TIPOS[tipo][0]
    chave = nome.strip().lower()
    if cache is not None and chave in cache:
        return cache[chave]
    item_id = s.scalar(select(modelo.id).where(modelo.nome == nome.strip()))  # citext
    if item_id is None:
        obj = modelo(nome=nome.strip()[:80])
        s.add(obj)
        s.flush()
        item_id = obj.id
    if cache is not None:
        cache[chave] = item_id
    return item_id


# ---- responsáveis -----------------------------------------------------------

def _responsaveis(s: Session, ids: list[int] | None = None) -> list[dict]:
    uso = _em_uso_subq(Empresa.responsavel_id)
    q = (select(Responsavel, func.coalesce(uso.c.n, 0))
         .outerjoin(uso, uso.c.responsavel_id == Responsavel.id)
         .order_by(func.lower(Responsavel.nome), Responsavel.id))
    if ids is not None:
        q = q.where(Responsavel.id.in_(ids))
    return [
        {"id": r.id, "nome": r.nome, "funcao": r.funcao, "email": r.email, "foto_url": r.foto_url,
         "teams_webhook": r.teams_webhook, "empresas": n}
        for r, n in s.execute(q)
    ]


def listar_responsaveis(ctx: Contexto) -> list[dict]:
    with em_conta(ctx.conta_id) as s:
        return _responsaveis(s)


def criar_responsavel(ctx: Contexto, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        r = Responsavel(conta_id=ctx.conta_id, **dados.model_dump())
        s.add(r)
        s.flush()
        return _responsaveis(s, [r.id])[0]


def _responsavel_ou_404(s: Session, rid: int) -> Responsavel:
    r = s.get(Responsavel, rid)
    if r is None:
        raise nao_encontrado("Responsável não encontrado.")
    return r


def alterar_responsavel(ctx: Contexto, rid: int, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        r = _responsavel_ou_404(s, rid)
        for campo in dados.model_fields_set:
            valor = getattr(dados, campo)
            if campo == "nome" and not valor:
                continue
            setattr(r, campo, valor)
        s.flush()
        return _responsaveis(s, [r.id])[0]


def excluir_responsavel(ctx: Contexto, rid: int) -> None:
    with em_conta(ctx.conta_id) as s:
        r = _responsavel_ou_404(s, rid)
        registrar(s, "responsavel_excluido", "atencao", {"nome": r.nome}, usuario_id=ctx.usuario_id)
        s.delete(r)


def testar_teams(ctx: Contexto, rid: int) -> str:
    with em_conta(ctx.conta_id) as s:
        r = _responsavel_ou_404(s, rid)
        nome, webhook = r.nome, r.teams_webhook
    if not webhook:
        msg = "Cadastre o endereço do webhook do Teams antes de testar."
        raise AppError(422, "dados_invalidos", msg, {"teams_webhook": msg})
    corpo = {"text": f"Teste do Toqqi: os alertas da carteira de {nome} vão chegar neste canal."}
    try:
        resp = rede.post_json_seguro(webhook, corpo)
    except rede.EnderecoProibido as e:
        raise AppError(422, "dados_invalidos", str(e), {"teams_webhook": str(e)})
    except httpx.HTTPError:
        msg = "Não conseguimos falar com o Teams. Confira o endereço do webhook e tente de novo."
        raise AppError(422, "teams_recusou", msg, {"teams_webhook": msg})
    if not 200 <= resp.status_code < 300:
        msg = f"O Teams recusou a mensagem (código {resp.status_code}). Confira o endereço do webhook."
        raise AppError(422, "teams_recusou", msg, {"teams_webhook": msg})
    return "Mensagem de teste enviada ao Teams."
