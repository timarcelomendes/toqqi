"""Configurações de segurança da conta: duração da sessão e domínios liberados."""
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.validacao import DOMINIOS_GRATUITOS, dominio_valido, normalizar_dominio
from toqqi.modelos import Conta, DominioLiberado


def _estado(s, conta_id: int) -> dict:
    minutos = s.scalar(select(Conta.sessao_minutos).where(Conta.id == conta_id))
    dominios = s.scalars(select(DominioLiberado.dominio).order_by(DominioLiberado.dominio)).all()
    return {"sessao_minutos": minutos, "dominios": list(dominios)}


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _estado(s, ctx.conta_id)


def _erro_dominios(msg: str) -> AppError:
    return AppError(422, "dados_invalidos", msg, {"dominios": msg})


def _juntar(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def salvar(ctx: Contexto, dados) -> dict:
    dominios: list[str] = []
    for bruto in dados.dominios:
        d = normalizar_dominio(bruto)
        if d and d not in dominios:
            dominios.append(d)

    invalidos = [d for d in dominios if not dominio_valido(d)]
    if invalidos:
        raise _erro_dominios(f"Domínio em formato inválido: {_juntar(invalidos)}. Use algo como empresa.com.br.")
    gratuitos = [d for d in dominios if d in DOMINIOS_GRATUITOS]
    if gratuitos:
        raise _erro_dominios(
            f"Não é possível liberar domínios de e-mail gratuito ({_juntar(gratuitos)}): "
            "qualquer pessoa poderia pedir acesso. Use o domínio da sua empresa."
        )
    if dominios:
        # Modo sistema, só leitura: o domínio já pertence a OUTRA conta?
        with modo_sistema() as s:
            de_outras = s.scalars(
                select(DominioLiberado.dominio)
                .where(DominioLiberado.dominio.in_(dominios), DominioLiberado.conta_id != ctx.conta_id)
            ).all()
        if de_outras:
            raise _erro_dominios(f"Este domínio já está liberado por outra conta: {_juntar(sorted(de_outras))}.")

    try:
        with em_conta(ctx.conta_id) as s:
            antes = _estado(s, ctx.conta_id)
            conta = s.get(Conta, ctx.conta_id)
            conta.sessao_minutos = dados.sessao_minutos
            s.execute(delete(DominioLiberado))
            if dominios:
                s.execute(insert(DominioLiberado), [{"conta_id": ctx.conta_id, "dominio": d} for d in dominios])
            s.flush()
            depois = _estado(s, ctx.conta_id)
            if antes != depois:
                registrar(s, "seguranca_alterada", "atencao", {"antes": antes, "depois": depois},
                          usuario_id=ctx.usuario_id)
            return depois
    except IntegrityError:
        raise _erro_dominios("Um dos domínios já está liberado por outra conta.")
