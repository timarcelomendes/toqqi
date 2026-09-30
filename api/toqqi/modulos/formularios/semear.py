"""Dados que toda conta recebe ao nascer: perfis de contato e os dois formulários padrão."""
import secrets

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from toqqi.modulos.formularios.modelos import (
    FORMULARIOS_INICIAIS,
    MODELOS,
    PERFIS_INICIAIS,
    perguntas_do_modelo,
    tema_do_modelo,
)
from toqqi.modulos.formularios.validacao import normalizar_perguntas

_ALFABETO_CODIGO = "abcdefghjkmnpqrstuvwxyz23456789"


def novo_codigo_publico() -> str:
    return "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(8))


def codigo_publico_livre(s: Session) -> str:
    """Código de 8 caracteres ainda não usado (a busca é global: modo sistema não é necessário
    para a unicidade, que o índice garante; aqui só evitamos a colisão comum)."""
    from toqqi.modelos import Formulario

    for _ in range(10):
        c = novo_codigo_publico()
        if not s.scalar(select(exists().where(Formulario.codigo_publico == c))):
            return c
    return novo_codigo_publico()


def dados_iniciais() -> tuple[list[str], list[dict]]:
    formularios = []
    for nome, chave, padrao in FORMULARIOS_INICIAIS:
        formularios.append({
            "nome": nome,
            "descricao": MODELOS[chave]["descricao"],
            "perguntas": normalizar_perguntas(perguntas_do_modelo(chave)),
            "tema": tema_do_modelo(chave),
            "codigo_publico": novo_codigo_publico(),
            "padrao_nps": padrao == "nps",
            "padrao_csat": padrao == "csat",
        })
    return list(PERFIS_INICIAIS), formularios


def semear_conta(s: Session, conta_id: int) -> None:
    from toqqi.modelos import Formulario, PerfilContato

    perfis, formularios = dados_iniciais()
    for nome in perfis:
        s.add(PerfilContato(conta_id=conta_id, nome=nome))
    for f in formularios:
        s.add(Formulario(conta_id=conta_id, **f))
    s.flush()
