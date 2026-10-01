"""Efeitos de envio no ponto único "resposta registrada": contato passa a `respondeu` e, se configurado,
um agradecimento é agendado (enviado depois do commit, em segundo plano).

Quem grava respostas envolve a chamada em `coletar_envios()` e agenda os envios coletados depois do
commit; sem coletor, o envio fica pendente e a tarefa de pendentes o retoma.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.modelos import Contato, Resposta
from toqqi.modulos.envios.configuracao import obter, pronto
from toqqi.modulos.envios.descadastro import esta_descadastrado
from toqqi.modulos.envios.processamento import novo_envio
from toqqi.modulos.respostas.eventos import GANCHOS

_coletados: ContextVar[list | None] = ContextVar("envios_apos_commit", default=None)


@contextmanager
def coletar_envios() -> Iterator[list[tuple[int, int]]]:
    """Junta (conta_id, envio_id) criados pelos ganchos durante o bloco."""
    lista: list[tuple[int, int]] = []
    marca = _coletados.set(lista)
    try:
        yield lista
    finally:
        _coletados.reset(marca)


def ao_registrar_resposta(s: Session, r: Resposta) -> None:
    if r.contato_id is None:
        return
    contato = s.get(Contato, r.contato_id)
    cfg = obter(s)
    hoje = relogio.hoje()
    if contato.proximo_envio is None or contato.proximo_envio <= hoje:
        contato.proximo_envio = hoje + timedelta(days=cfg.intervalo_dias)
    if not (cfg.agradecimento_ativo and r.grupo and contato.email) or esta_descadastrado(s, contato.email,
                                                                                         contato.telefone):
        return
    if not pronto(s, cfg):
        return
    e = novo_envio(s, contato, "agradecimento", "resposta", resposta_id=r.id)
    lista = _coletados.get()
    if lista is not None:
        lista.append((e.conta_id, e.id))


GANCHOS.append(ao_registrar_resposta)
