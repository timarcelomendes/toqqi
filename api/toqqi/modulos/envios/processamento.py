"""Criação e processamento dos envios (e-mail e WhatsApp automático).

Um envio nasce `pendente` dentro da transação que o decidiu; o envio de fato acontece depois do commit
(`processar`), fora da transação: primeiro marca a tentativa, depois chama o provedor (e-mail) ou a Graph API
(WhatsApp) e por fim grava o resultado. Um envio pendente há mais de 10 minutos (queda do processo) é retomado
pela tarefa de pendentes.

Canal: `ConfigEnvios.canal` define a ordem (WhatsApp antes do e-mail quando não é "email"). O WhatsApp reserva
a franquia ao criar o envio; se a mensagem não sai, a reserva volta e, com "whatsapp_e_email", um envio por
e-mail substitui o que falhou.
"""
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import em_conta
from toqqi.core.email import FalhaEnvio, Mensagem, enviar_mensagem
from toqqi.core.segredos import decifrar
from toqqi.modelos import ConfigEnvios, Conta, Contato, Convite, Empresa, Envio, Formulario, Resposta, WhatsappConta
from toqqi.modulos.envios import mensagens
from toqqi.modulos.envios.configuracao import obter, provedor_ok
from toqqi.modulos.envios.descadastro import esta_descadastrado
from toqqi.modulos.imagens.servico import logo_para_cliente
from toqqi.modulos.respostas.convites import link_do_convite, novo_convite, token_do_convite
from toqqi.modulos.whatsapp import franquia, graph, modelo

log = logging.getLogger("toqqi.envios")

Pares = list[tuple[int, int]]
RETOMAR_APOS = timedelta(minutes=10)
TEXTO_AGRADECIMENTO = {"promotor": "promotor", "satisfeito": "promotor", "neutro": "neutro",
                       "detrator": "detrator", "insatisfeito": "detrator"}


def ordem_canais(cfg: ConfigEnvios) -> tuple[str, ...]:
    return ("whatsapp", "email") if cfg.canal != "email" else ("email",)


def whatsapp_da_config(s: Session, cfg: ConfigEnvios) -> WhatsappConta | None:
    """Conta de WhatsApp para o robô, o envio manual e os lembretes (None se o canal configurado é só e-mail)."""
    return franquia.disponivel(s) if cfg.canal != "email" else None


def escolher_canal(s: Session, contato: Contato, canais: Iterable[str],
                   wa: WhatsappConta | None) -> tuple[str, str | None] | None:
    """(canal, cobrança) do primeiro canal possível para o contato; no WhatsApp, reserva a franquia."""
    for canal in canais:
        if canal == "whatsapp" and wa is not None and contato.telefone:
            cobranca = franquia.reservar(s, wa)
            if cobranca:
                return canal, cobranca
        elif canal == "email" and contato.email:
            return canal, None
    return None


def novo_envio(s: Session, contato: Contato, tipo: str, origem: str, canal: str = "email", **campos) -> Envio:
    e = Envio(contato_id=contato.id, canal=canal, tipo=tipo, origem=origem, criado_em=relogio.agora(),
              para=contato.telefone if canal == "whatsapp" else contato.email, **campos)
    s.add(e)
    s.flush()
    return e


def criar_convite(s: Session, cfg: ConfigEnvios, contato: Contato, origem: str, canais: Iterable[str],
                  wa: WhatsappConta | None, usuario_id: int | None = None, formulario_id: int | None = None,
                  **convite) -> Envio | None:
    """Convite + envio pendente pelo primeiro canal possível (na conta da transação); None se nenhum serve.
    `convite` leva campos extras do convite (evento, referencia, contexto, assunto)."""
    escolha = escolher_canal(s, contato, canais, wa)
    if escolha is None:
        return None
    canal, cobranca = escolha
    c, _ = novo_convite(s, formulario_id or cfg.formulario_id, contato_id=contato.id, canal=canal,
                        empresa_id=contato.empresa_id, criado_em=relogio.agora(), **convite)
    return novo_envio(s, contato, "convite", origem, canal=canal, convite_id=c.id, usuario_id=usuario_id,
                      cobranca=cobranca)


def marcar_convite_enviado(cfg: ConfigEnvios, contato: Contato) -> None:
    """Convite saiu (e-mail ou WhatsApp): conta para intervalo e descanso e zera as falhas."""
    contato.ultimo_envio = relogio.agora()
    contato.proximo_envio = relogio.hoje() + timedelta(days=cfg.intervalo_dias)
    contato.falhas = 0


# ---- montagem da mensagem ---------------------------------------------------

class NaoEnviar(Exception):
    """O envio não pode mais sair (ex.: a pessoa saiu da lista depois de agendado)."""


@dataclass
class MensagemWhatsapp:
    token: str
    phone_number_id: str
    corpo: dict


def _montar(s: Session, e: Envio) -> Mensagem | MensagemWhatsapp:
    contato = s.get(Contato, e.contato_id) if e.contato_id else None
    if contato is None:
        raise NaoEnviar("O contato foi excluído antes do envio.")
    whatsapp = e.canal == "whatsapp"
    if esta_descadastrado(s, contato.email if whatsapp else e.para, e.para if whatsapp else contato.telefone):
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
        f = s.get(Formulario, r.formulario_id)  # o formulário respondido
        logo = logo_para_cliente(s, e.conta_id, (f.tema or {}).get("logo_url") if f else None)
        return mensagens.email_agradecimento(texto=cfg.agradecimento[TEXTO_AGRADECIMENTO[r.grupo]], v=v,
                                             logo_url=logo, **comum)
    convite = s.get(Convite, e.convite_id) if e.convite_id else None
    if convite is None or convite.token_semente is None:
        raise NaoEnviar("O convite foi excluído antes do envio.")
    f = s.get(Formulario, convite.formulario_id)
    if f is None or not f.ativo or f.arquivado:
        raise NaoEnviar("O formulário da pesquisa foi desativado.")
    token = token_do_convite(convite.token_semente)
    if whatsapp:
        wc = franquia.disponivel(s)
        if wc is None:
            raise NaoEnviar("O WhatsApp automático foi desligado antes do envio.")
        token_meta = decifrar(wc.token_cifrado)
        if token_meta is None:
            raise NaoEnviar(graph.MSG_TOKEN)
        return MensagemWhatsapp(token_meta, wc.phone_number_id, modelo.corpo_modelo(
            nome_modelo=wc.modelo_nome, idioma=wc.modelo_idioma, botao=wc.modelo_botao, telefone=e.para,
            primeiro_nome=v["nome"], empresa=empresa, referencia=modelo.referencia_texto(convite.referencia),
            token=token))
    lembrete = e.tipo == "lembrete"
    return mensagens.email_pesquisa(
        assunto=cfg.assunto_lembrete if lembrete else cfg.assunto_convite,
        texto=cfg.texto_lembrete if lembrete else cfg.texto_convite,
        perguntas=f.perguntas, link=link_do_convite(token), v=v,
        logo_url=logo_para_cliente(s, e.conta_id, (f.tema or {}).get("logo_url")), **comum)


# ---- resultado --------------------------------------------------------------

def falha_whatsapp(s: Session, e: Envio, erro_da_conta: bool = False) -> Pares:
    """WhatsApp que não saiu (na hora ou avisado depois pela Meta): devolve a franquia, guarda o erro da
    conexão e, com "whatsapp_e_email", agenda o mesmo convite/lembrete por e-mail. Devolve o envio novo."""
    if e.cobranca:
        franquia.devolver(s, e.cobranca)
        e.cobranca = None
    wc = franquia.conectada(s)
    if erro_da_conta and wc is not None:
        wc.ultimo_erro = e.erro
    contato = s.get(Contato, e.contato_id) if e.contato_id else None
    cfg = obter(s)
    reserva = (contato is not None and contato.email and cfg.canal == "whatsapp_e_email" and cfg.envios_ativos
               and provedor_ok() and not esta_descadastrado(s, contato.email, contato.telefone))
    if not reserva:
        if e.tipo == "convite" and contato is not None:
            contato.falhas += 1
        return []
    if e.tipo == "convite" and e.convite_id:
        s.get(Convite, e.convite_id).canal = "email"
    novo = novo_envio(s, contato, e.tipo, e.origem, convite_id=e.convite_id, lembrete=e.lembrete,
                      usuario_id=e.usuario_id)
    return [(e.conta_id, novo.id)]


def _gravar_resultado(s: Session, e: Envio, erro: str | None, wamid: str | None = None,
                      erro_da_conta: bool = False) -> Pares:
    """Grava o resultado; devolve envios novos a processar (e-mail de reserva de um WhatsApp que falhou)."""
    if erro:
        e.situacao, e.erro = "erro", erro
        if e.canal == "whatsapp":
            return falha_whatsapp(s, e, erro_da_conta)
        contato = s.get(Contato, e.contato_id) if e.contato_id else None
        if e.tipo == "convite" and contato is not None:
            contato.falhas += 1
        return []
    e.situacao, e.erro, e.enviado_em, e.wamid = "enviado", None, relogio.agora(), wamid
    if e.canal == "whatsapp" and (wc := franquia.conectada(s)) is not None:
        wc.ultimo_erro = None
    contato = s.get(Contato, e.contato_id) if e.contato_id else None
    if e.tipo == "convite" and contato is not None:
        marcar_convite_enviado(obter(s), contato)
    elif e.tipo == "lembrete" and e.convite_id:
        convite = s.get(Convite, e.convite_id)
        if convite is not None:
            convite.lembretes_enviados = max(convite.lembretes_enviados, e.lembrete or 0)
    return []


# ---- processamento ----------------------------------------------------------

def _processar(conta_id: int, envio_id: int) -> Pares:
    with em_conta(conta_id) as s:
        e = s.get(Envio, envio_id, with_for_update=True)
        agora = relogio.agora()
        if e is None or e.situacao != "pendente" or (e.tentativa_em and agora - e.tentativa_em < RETOMAR_APOS):
            return []  # já resolvido, ou outro processo está enviando
        e.tentativa_em = agora
        try:
            mensagem = _montar(s, e)
        except NaoEnviar as motivo:
            return _gravar_resultado(s, e, str(motivo))
    wamid, erro, erro_da_conta = None, None, False
    if isinstance(mensagem, MensagemWhatsapp):
        try:
            wamid = graph.enviar_mensagem(mensagem.token, mensagem.phone_number_id, mensagem.corpo)
        except graph.FalhaGraph as f:
            erro, erro_da_conta = graph.traduzir(f.status, f.codigo)
    else:
        try:
            enviar_mensagem(mensagem)
        except FalhaEnvio as f:
            erro = f.mensagem
    with em_conta(conta_id) as s:
        return _gravar_resultado(s, s.get(Envio, envio_id, with_for_update=True), erro, wamid, erro_da_conta)


def processar(conta_id: int, envio_id: int) -> None:
    """Envia um envio pendente e grava o resultado. Não levanta exceção (roda em segundo plano)."""
    try:
        novos = _processar(conta_id, envio_id)
    except Exception:  # noqa: BLE001 - segundo plano: registra e segue; a tarefa de pendentes retoma
        log.exception("Falha ao processar o envio %s da conta %s", envio_id, conta_id)
        return
    processar_lista(novos)


def processar_lista(pares: Iterable[tuple[int, int]]) -> None:
    """Processa (conta_id, envio_id) um a um."""
    for conta_id, envio_id in pares:
        processar(conta_id, envio_id)
