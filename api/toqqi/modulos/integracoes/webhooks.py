"""Webhooks de saída: cadastro, fila de entregas (`webhook_entregas`) e entrega assinada.

O evento entra na fila dentro da transação que o gerou (`enfileirar`); a entrega acontece fora dela: logo
depois da resposta (quem gerou o evento envolve o trabalho em `coletar_entregas()` e agenda `entregar_lista`)
ou na rotina de tarefas (`entregar_devidas`). Cada tentativa reserva a entrega por 10 min, faz o POST no IP
público conferido (core.rede, sem redirecionamento, timeout 10 s) e grava o resultado.

Exclusão a pedido da pessoa (LGPD) de um registro que foi para os webhooks (`esquecer_entregas`, ex.: uma indicação):
as entregas pendentes somem (não saem mais) e as que já terminaram ficam no histórico com o corpo sem os dados.
"""
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

import httpx
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from toqqi.core import rede, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.avisos import avisar_admins
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema, travar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.segredos import cifrar, decifrar
from toqqi.modelos import Contato, Conta, Convite, Empresa, Formulario, Resposta, Webhook, WebhookEntrega
from toqqi.modulos.formularios.servico import resposta_json
from toqqi.modulos.respostas.eventos import GANCHOS

log = logging.getLogger("toqqi.webhooks")

EVENTOS = ("resposta.criada", "contato.descadastrado", "indicacao.criada", "indicacao.atualizada")
MAX_POR_CONTA = 5
ESPERAS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2), timedelta(hours=6))
MAX_FALHAS_SEGUIDAS = 10
RESERVA = timedelta(minutes=10)
LIMITE_RODADA = 500
DIAS_ENTREGAS = 30
POR_PAGINA_ENTREGAS = 50

MSG_DESATIVADO = f"O webhook foi desativado depois de {MAX_FALHAS_SEGUIDAS} falhas seguidas."


# ---- segredo e assinatura ---------------------------------------------------

def novo_segredo() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def prefixo_segredo(segredo: str) -> str:
    return segredo[:10] + "…"


def assinatura(segredo: str, t: int, corpo: bytes) -> str:
    """Hex do HMAC-SHA256(segredo, "<t>.<corpo>")."""
    return hmac.new(segredo.encode(), f"{t}.".encode() + corpo, hashlib.sha256).hexdigest()


def _postar(url: str, segredo: str, evento: str, entrega_id: str, corpo: dict) -> tuple[int | None, str | None]:
    """POST assinado. Devolve (status HTTP, erro em texto simples); erro None = 2xx."""
    bruto = json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode()
    t = int(relogio.agora().timestamp())
    cabecalhos = {"X-Toqqi-Evento": evento, "X-Toqqi-Entrega": entrega_id,
                  "X-Toqqi-Assinatura": f"t={t},v1={assinatura(segredo, t, bruto)}",
                  "User-Agent": "Toqqi-Webhooks/1.0"}
    try:
        r = rede.post_json_seguro(url, bruto, cabecalhos)
    except rede.EnderecoProibido as e:
        return None, str(e)
    except httpx.TimeoutException:
        return None, "O endereço demorou mais de 10 segundos para responder."
    except httpx.HTTPError as e:
        log.info("Falha de rede no webhook %s: %r", url, e)
        return None, "Não foi possível conectar ao endereço."
    if 200 <= r.status_code < 300:
        return r.status_code, None
    if 300 <= r.status_code < 400:
        return r.status_code, "O endereço pediu redirecionamento, que não é seguido. Use o endereço final."
    return r.status_code, f"O endereço respondeu com erro (HTTP {r.status_code})."


def _conta_json(s: Session) -> dict:
    conta_id, nome = s.execute(select(Conta.id, Conta.nome)).one()
    return {"id": conta_id, "nome": nome}


def _corpo(entrega_id: uuid.UUID, evento: str, conta: dict, dados: dict) -> dict:
    return jsonable_encoder({"id": str(entrega_id), "evento": evento, "criado_em": relogio.agora(),
                             "conta": conta, "dados": dados})


# ---- fila -------------------------------------------------------------------

_coletadas: ContextVar[list | None] = ContextVar("entregas_apos_commit", default=None)


@contextmanager
def coletar_entregas() -> Iterator[list[tuple[int, uuid.UUID]]]:
    """Junta (conta_id, entrega_id) enfileiradas durante o bloco, para entregar logo depois do commit."""
    lista: list[tuple[int, uuid.UUID]] = []
    marca = _coletadas.set(lista)
    try:
        yield lista
    finally:
        _coletadas.reset(marca)


def enfileirar(s: Session, evento: str, dados: dict) -> None:
    """Uma entrega por webhook ativo da conta (da transação) inscrito no evento."""
    assert evento in EVENTOS
    ids = s.scalars(select(Webhook.id).where(Webhook.ativo.is_(True), Webhook.eventos.any(evento))).all()
    if not ids:
        return
    conta = _conta_json(s)
    agora = relogio.agora()
    novas = []
    for webhook_id in ids:
        entrega_id = uuid.uuid4()
        s.add(WebhookEntrega(id=entrega_id, webhook_id=webhook_id, evento=evento, criado_em=agora,
                             proxima_tentativa=agora, corpo=_corpo(entrega_id, evento, conta, dados)))
        novas.append((conta["id"], entrega_id))
    s.flush()
    lista = _coletadas.get()
    if lista is not None:
        lista.extend(novas)


def _ao_registrar_resposta(s: Session, r: Resposta) -> None:
    if r.origem == "importacao":
        return  # histórico importado não vira evento
    if not s.scalar(select(func.count()).select_from(Webhook)
                    .where(Webhook.ativo.is_(True), Webhook.eventos.any("resposta.criada"))):
        return
    linha = s.execute(
        select(Resposta, Formulario.nome, Contato.nome, Contato.email, Empresa.nome)
        .join(Formulario, Formulario.id == Resposta.formulario_id)
        .outerjoin(Contato, Contato.id == Resposta.contato_id)
        .outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
        .where(Resposta.id == r.id)).one()
    convite = s.get(Convite, r.convite_id) if r.convite_id else None
    enfileirar(s, "resposta.criada", {
        **resposta_json(linha),
        "convite": {"evento": convite.evento, "referencia": convite.referencia} if convite else None})


GANCHOS.append(_ao_registrar_resposta)


ENVELOPE = ("id", "evento", "criado_em", "conta")  # o que fica no corpo de uma entrega esquecida (sem os dados)


def esquecer_entregas(s: Session, conta_id: int, prefixo_evento: str, dados_id: int) -> None:
    """Pedido de exclusão (LGPD) do registro `dados_id` dos eventos `prefixo_evento*` (o corpo leva o registro em
    `dados`, com `dados.id`), na transação de quem exclui. As entregas pendentes somem: não saem mais (uma tentativa
    já em andamento termina sem gravar o resultado). As que já terminaram (entregues ou desistidas, que não saem de
    novo) ficam no histórico de Integrações — data, evento, HTTP — com o corpo reduzido ao envelope e
    `dados: {id, excluido: true}`."""
    do_registro = [WebhookEntrega.conta_id == conta_id,
                   WebhookEntrega.evento.startswith(prefixo_evento, autoescape=True),
                   WebhookEntrega.corpo["dados"]["id"].astext == str(dados_id)]
    s.execute(delete(WebhookEntrega).where(*do_registro, WebhookEntrega.status == "pendente")
              .execution_options(synchronize_session=False))
    for e in s.scalars(select(WebhookEntrega).where(*do_registro, WebhookEntrega.status != "pendente")
                       .with_for_update()):
        e.corpo = {**{k: e.corpo[k] for k in ENVELOPE if k in e.corpo}, "dados": {"id": dados_id, "excluido": True}}
    s.flush()


# ---- entrega ----------------------------------------------------------------

def _desativar(s: Session, w: Webhook) -> None:
    w.ativo = False
    s.flush()
    s.execute(update(WebhookEntrega).where(WebhookEntrega.webhook_id == w.id, WebhookEntrega.status == "pendente")
              .values(status="falhou", erro=MSG_DESATIVADO).execution_options(synchronize_session=False))
    registrar(s, "webhook_desativado", "erro", {"webhook_id": w.id, "url": w.url})
    avisar_admins(s, w.conta_id, "Um webhook da Toqqi foi desativado", [
        f"O webhook {w.url} falhou {MAX_FALHAS_SEGUIDAS} vezes seguidas e foi desativado.",
        "Confira se o endereço está no ar e ligue o webhook de novo em Integrações.",
    ], ("Abrir Integrações", f"{config().FRONTEND_URL.rstrip('/')}/integracoes"))


def _gravar_tentativa(s: Session, e: WebhookEntrega, w: Webhook, status: int | None, erro: str | None) -> None:
    agora = relogio.agora()
    e.tentativas += 1
    e.status_http, e.erro = status, erro
    w.ultima_entrega_em, w.ultimo_status_http, w.ultima_ok = agora, status, erro is None
    if erro is None:
        e.status = "ok"
        w.falhas_seguidas = 0
        return
    w.falhas_seguidas += 1
    if e.tentativas > len(ESPERAS):
        e.status = "falhou"
    else:
        e.proxima_tentativa = agora + ESPERAS[e.tentativas - 1]
    if w.falhas_seguidas >= MAX_FALHAS_SEGUIDAS and w.ativo:
        _desativar(s, w)


def entregar(conta_id: int, entrega_id: uuid.UUID) -> bool | None:
    """Uma tentativa de entrega. True = entregue, False = falhou, None = não era a hora (ou já resolvida)."""
    agora = relogio.agora()
    with em_conta(conta_id) as s:
        linha = s.execute(
            select(WebhookEntrega, Webhook).join(Webhook, Webhook.id == WebhookEntrega.webhook_id)
            .where(WebhookEntrega.id == entrega_id, WebhookEntrega.status == "pendente",
                   WebhookEntrega.proxima_tentativa <= agora, Webhook.ativo.is_(True))
            .with_for_update(of=WebhookEntrega, skip_locked=True)).one_or_none()
        if linha is None:
            return None
        e, w = linha
        e.proxima_tentativa = agora + RESERVA  # outro processo não pega a mesma entrega enquanto esta tenta
        url, evento, corpo, segredo = w.url, e.evento, e.corpo, decifrar(w.segredo_cifrado)
    if segredo is None:
        status, erro = None, "O segredo do webhook precisa ser gerado de novo."
    else:
        status, erro = _postar(url, segredo, evento, str(entrega_id), corpo)
    with em_conta(conta_id) as s:
        e = s.get(WebhookEntrega, entrega_id, with_for_update=True)
        if e is None:  # esquecida durante a tentativa (`esquecer_entregas`): não há o que gravar
            return erro is None
        _gravar_tentativa(s, e, s.get(Webhook, e.webhook_id, with_for_update=True), status, erro)
    return erro is None


def entregar_lista(pares: Iterable[tuple[int, uuid.UUID]]) -> dict:
    """Tenta entregar (conta_id, entrega_id) uma a uma. Não levanta exceção (roda em segundo plano)."""
    total = {"entregues": 0, "falharam": 0}
    for conta_id, entrega_id in pares:
        try:
            ok = entregar(conta_id, entrega_id)
        except Exception:  # noqa: BLE001 - segue para a próxima; a rotina de tarefas tenta de novo
            log.exception("Falha ao entregar o webhook %s da conta %s", entrega_id, conta_id)
            continue
        if ok is not None:
            total["entregues" if ok else "falharam"] += 1
    return total


def entregar_devidas() -> dict:
    """Rotina de tarefas: entregas pendentes cuja hora chegou (de webhooks ativos), em todas as contas."""
    with modo_sistema() as s:  # só os ids; cada entrega roda em em_conta(conta)
        pares = s.execute(
            select(WebhookEntrega.conta_id, WebhookEntrega.id).join(Webhook, Webhook.id == WebhookEntrega.webhook_id)
            .where(WebhookEntrega.status == "pendente", WebhookEntrega.proxima_tentativa <= relogio.agora(),
                   Webhook.ativo.is_(True))
            .order_by(WebhookEntrega.proxima_tentativa).limit(LIMITE_RODADA)).all()
    return entregar_lista([(c, i) for c, i in pares])


# ---- cadastro (perfil admin) ------------------------------------------------

def _json(w: Webhook) -> dict:
    ultima = ({"quando": w.ultima_entrega_em, "status_http": w.ultimo_status_http, "ok": bool(w.ultima_ok)}
              if w.ultima_entrega_em else None)
    return {"id": w.id, "url": w.url, "eventos": list(w.eventos), "ativo": w.ativo,
            "segredo_prefixo": w.segredo_prefixo, "criado_em": w.criado_em, "ultima_entrega": ultima,
            "falhas_seguidas": w.falhas_seguidas}


def _conferir_url(url: str) -> str:
    try:
        return rede.conferir_url_https(url)
    except rede.EnderecoProibido as e:
        raise AppError(422, "dados_invalidos", "Confira os campos destacados.", {"url": str(e)})


def _webhook(s: Session, webhook_id: int, travar_linha: bool = False) -> Webhook:
    w = s.get(Webhook, webhook_id, with_for_update=travar_linha)
    if w is None:
        raise nao_encontrado("Webhook não encontrado.")
    return w


def listar(ctx: Contexto) -> list[dict]:
    with em_conta(ctx.conta_id) as s:
        return [_json(w) for w in s.scalars(select(Webhook).order_by(Webhook.id))]


def criar(ctx: Contexto, dados) -> dict:
    url = _conferir_url(dados.url)
    segredo = novo_segredo()
    with em_conta(ctx.conta_id) as s:
        travar(s, f"webhooks:{ctx.conta_id}")
        if s.scalar(select(func.count()).select_from(Webhook)) >= MAX_POR_CONTA:
            raise AppError(409, "limite_webhooks", f"Cada conta pode ter até {MAX_POR_CONTA} webhooks.")
        w = Webhook(url=url, eventos=dados.eventos, segredo_cifrado=cifrar(segredo),
                    segredo_prefixo=prefixo_segredo(segredo), criado_em=relogio.agora())
        s.add(w)
        s.flush()
        return {**_json(w), "segredo": segredo}


def alterar(ctx: Contexto, webhook_id: int, dados) -> dict:
    novos = {c: getattr(dados, c) for c in dados.model_fields_set if getattr(dados, c) is not None}
    if "url" in novos:
        novos["url"] = _conferir_url(novos["url"])
    with em_conta(ctx.conta_id) as s:
        w = _webhook(s, webhook_id, travar_linha=True)
        if novos.get("ativo") and not w.ativo:
            w.falhas_seguidas = 0
        for campo, valor in novos.items():
            setattr(w, campo, valor)
        s.flush()
        return _json(w)


def excluir(ctx: Contexto, webhook_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        s.delete(_webhook(s, webhook_id))


def trocar_segredo(ctx: Contexto, webhook_id: int) -> dict:
    segredo = novo_segredo()
    with em_conta(ctx.conta_id) as s:
        w = _webhook(s, webhook_id, travar_linha=True)
        w.segredo_cifrado, w.segredo_prefixo = cifrar(segredo), prefixo_segredo(segredo)
    return {"segredo": segredo}


def testar(ctx: Contexto, webhook_id: int) -> dict:
    """POST de teste (evento "teste"), na hora; não entra na fila nem conta como falha."""
    with em_conta(ctx.conta_id) as s:
        w = _webhook(s, webhook_id)
        url, segredo = w.url, decifrar(w.segredo_cifrado)
        entrega_id = uuid.uuid4()
        corpo = _corpo(entrega_id, "teste", _conta_json(s), {"mensagem": "Teste de webhook da Toqqi."})
    if segredo is None:
        return {"ok": False, "status_http": None, "mensagem": "O segredo do webhook precisa ser gerado de novo."}
    status, erro = _postar(url, segredo, "teste", str(entrega_id), corpo)
    if erro:
        return {"ok": False, "status_http": status, "mensagem": erro}
    return {"ok": True, "status_http": status, "mensagem": f"O endereço recebeu o teste (HTTP {status})."}


def entregas(ctx: Contexto, webhook_id: int, pagina: int) -> list[dict]:
    """Entregas dos últimos 30 dias, mais novas primeiro (50 por página)."""
    with em_conta(ctx.conta_id) as s:
        _webhook(s, webhook_id)
        linhas = s.scalars(
            select(WebhookEntrega)
            .where(WebhookEntrega.webhook_id == webhook_id,
                   WebhookEntrega.criado_em >= relogio.agora() - timedelta(days=DIAS_ENTREGAS))
            .order_by(WebhookEntrega.criado_em.desc(), WebhookEntrega.id)
            .limit(POR_PAGINA_ENTREGAS).offset((pagina - 1) * POR_PAGINA_ENTREGAS)).all()
    return [{"id": e.id, "evento": e.evento, "criado_em": e.criado_em, "tentativas": e.tentativas,
             "status_http": e.status_http, "ok": e.status == "ok", "erro": e.erro} for e in linhas]
