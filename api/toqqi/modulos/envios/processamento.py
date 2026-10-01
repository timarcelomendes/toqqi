"""Criação e processamento dos envios.

Um envio nasce `pendente` dentro da transação que o decidiu; o envio de fato acontece depois do commit
(`processar`), fora da transação: primeiro marca a tentativa, depois chama o provedor e por fim grava o
resultado. Um envio pendente há mais de 10 minutos (queda do processo) é retomado pela tarefa de pendentes.
"""
import logging
from collections.abc import Iterable
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import em_conta
from toqqi.core.email import FalhaEnvio, Mensagem, enviar_mensagem
from toqqi.modelos import ConfigEnvios, Conta, Contato, Convite, Empresa, Envio, Formulario, Resposta
from toqqi.modulos.envios import mensagens
from toqqi.modulos.envios.configuracao import obter
from toqqi.modulos.envios.descadastro import esta_descadastrado
from toqqi.modulos.respostas.convites import link_do_convite, novo_convite, token_do_convite

log = logging.getLogger("toqqi.envios")

RETOMAR_APOS = timedelta(minutes=10)
TEXTO_AGRADECIMENTO = {"promotor": "promotor", "satisfeito": "promotor", "neutro": "neutro",
                       "detrator": "detrator", "insatisfeito": "detrator"}


def novo_envio(s: Session, contato: Contato, tipo: str, origem: str, **campos) -> Envio:
    e = Envio(contato_id=contato.id, canal="email", tipo=tipo, origem=origem, para=contato.email,
              criado_em=relogio.agora(), **campos)
    s.add(e)
    s.flush()
    return e


def criar_convite_email(s: Session, cfg: ConfigEnvios, contato: Contato, origem: str,
                        usuario_id: int | None = None) -> Envio:
    """Convite por e-mail + envio pendente (na conta da transação)."""
    convite, _ = novo_convite(s, cfg.formulario_id, contato_id=contato.id, canal="email",
                              empresa_id=contato.empresa_id, criado_em=relogio.agora())
    return novo_envio(s, contato, "convite", origem, convite_id=convite.id, usuario_id=usuario_id)


def marcar_convite_enviado(cfg: ConfigEnvios, contato: Contato) -> None:
    """Convite saiu (e-mail ou WhatsApp): conta para intervalo e descanso e zera as falhas."""
    contato.ultimo_envio = relogio.agora()
    contato.proximo_envio = relogio.hoje() + timedelta(days=cfg.intervalo_dias)
    contato.falhas = 0


# ---- montagem da mensagem ---------------------------------------------------

class NaoEnviar(Exception):
    """O envio não pode mais sair (ex.: a pessoa saiu da lista depois de agendado)."""


def _montar(s: Session, e: Envio) -> Mensagem:
    contato = s.get(Contato, e.contato_id) if e.contato_id else None
    if contato is None:
        raise NaoEnviar("O contato foi excluído antes do envio.")
    if esta_descadastrado(s, e.para):
        raise NaoEnviar("A pessoa saiu da lista antes do envio.")
    cfg = obter(s)
    empresa = s.scalar(select(Conta.nome))
    empresa_cliente = s.scalar(select(Empresa.nome).where(Empresa.id == contato.empresa_id))
    v = mensagens.variaveis(empresa, contato.nome, empresa_cliente)
    comum = {"conta_id": e.conta_id, "para": e.para, "empresa": empresa,
             "remetente_nome": cfg.remetente_nome, "responder_para": cfg.responder_para}
    if e.tipo == "agradecimento":
        r = s.get(Resposta, e.resposta_id) if e.resposta_id else None
        if r is None or r.grupo is None:
            raise NaoEnviar("A resposta foi excluída antes do envio.")
        v["nota"] = str(r.nota)
        return mensagens.email_agradecimento(texto=cfg.agradecimento[TEXTO_AGRADECIMENTO[r.grupo]], v=v, **comum)
    convite = s.get(Convite, e.convite_id) if e.convite_id else None
    if convite is None or convite.token_semente is None:
        raise NaoEnviar("O convite foi excluído antes do envio.")
    f = s.get(Formulario, convite.formulario_id)
    if f is None or not f.ativo or f.arquivado:
        raise NaoEnviar("O formulário da pesquisa foi desativado.")
    lembrete = e.tipo == "lembrete"
    return mensagens.email_pesquisa(
        assunto=cfg.assunto_lembrete if lembrete else cfg.assunto_convite,
        texto=cfg.texto_lembrete if lembrete else cfg.texto_convite,
        perguntas=f.perguntas, link=link_do_convite(token_do_convite(convite.token_semente)), v=v, **comum)


# ---- processamento ----------------------------------------------------------

def _gravar_resultado(s: Session, e: Envio, erro: str | None) -> None:
    contato = s.get(Contato, e.contato_id) if e.contato_id else None
    if erro:
        e.situacao, e.erro = "erro", erro
        if e.tipo == "convite" and contato is not None:
            contato.falhas += 1
        return
    e.situacao, e.erro, e.enviado_em = "enviado", None, relogio.agora()
    if e.tipo == "convite" and contato is not None:
        marcar_convite_enviado(obter(s), contato)
    elif e.tipo == "lembrete" and e.convite_id:
        convite = s.get(Convite, e.convite_id)
        if convite is not None:
            convite.lembretes_enviados = max(convite.lembretes_enviados, e.lembrete or 0)


def processar(conta_id: int, envio_id: int) -> None:
    """Envia um envio pendente e grava o resultado. Não levanta exceção (roda em segundo plano)."""
    try:
        with em_conta(conta_id) as s:
            e = s.get(Envio, envio_id, with_for_update=True)
            agora = relogio.agora()
            if e is None or e.situacao != "pendente" or (e.tentativa_em and agora - e.tentativa_em < RETOMAR_APOS):
                return  # já resolvido, ou outro processo está enviando
            e.tentativa_em = agora
            try:
                mensagem = _montar(s, e)
            except NaoEnviar as motivo:
                _gravar_resultado(s, e, str(motivo))
                return
        try:
            enviar_mensagem(mensagem)
            erro = None
        except FalhaEnvio as f:
            erro = f.mensagem
        with em_conta(conta_id) as s:
            _gravar_resultado(s, s.get(Envio, envio_id, with_for_update=True), erro)
    except Exception:  # noqa: BLE001 - segundo plano: registra e segue; a tarefa de pendentes retoma
        log.exception("Falha ao processar o envio %s da conta %s", envio_id, conta_id)


def processar_lista(pares: Iterable[tuple[int, int]]) -> None:
    """Processa (conta_id, envio_id) um a um."""
    for conta_id, envio_id in pares:
        processar(conta_id, envio_id)
