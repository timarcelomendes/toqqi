"""Webhook da Meta (público): verificação (GET) e avisos (POST, assinados com o App Secret).

A conta é descoberta em modo sistema só pelo phone_number_id do aviso; o resto roda em em_conta(conta).
- `statuses`: atualiza o envio pelo wamid (enviado → entregue → lido; `failed` → erro em texto simples,
  devolve a franquia e, com "whatsapp_e_email", manda por e-mail).
- `messages` de texto "SAIR", "PARAR", "STOP" ou "CANCELAR" (sem diferenciar maiúsculas/acentos):
  descadastro do telefone (origem `whatsapp`) e confirmação por mensagem de sessão.
O que fala com a rede (confirmação, e-mails de reserva, webhooks de saída) fica para depois da resposta.
"""
import hashlib
import hmac
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.errors import AppError
from toqqi.core.segredos import decifrar
from toqqi.core.texto import sem_acento, telefone_canonico
from toqqi.modelos import Conta, Envio, WhatsappConta
from toqqi.modulos.envios.descadastro import esta_descadastrado, gravar
from toqqi.modulos.envios.processamento import Pares, falha_whatsapp, processar_lista
from toqqi.modulos.integracoes.webhooks import entregar_lista
from toqqi.modulos.whatsapp import graph, modelo

PALAVRAS_SAIR = frozenset({"SAIR", "PARAR", "STOP", "CANCELAR"})
ORDEM = {"enviado": 0, "entregue": 1, "lido": 2}
SITUACAO = {"delivered": "entregue", "read": "lido"}


def desafio(modo: str | None, token: str | None, challenge: str | None) -> str:
    esperado = config().WHATSAPP_VERIFY_TOKEN
    if modo != "subscribe" or not esperado or not token or not challenge \
            or not hmac.compare_digest(token.encode(), esperado.encode()):
        raise AppError(403, "token_invalido", "Token de verificação inválido.")
    return challenge


def conferir_assinatura(corpo: bytes, cabecalho: str | None) -> None:
    """X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(App Secret, corpo cru)."""
    segredo = config().WHATSAPP_APP_SECRET
    esperado = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    if not segredo or not cabecalho or not hmac.compare_digest(cabecalho.encode(), esperado.encode()):
        raise AppError(401, "assinatura_invalida", "Assinatura inválida.")


@dataclass
class Depois:
    """Trabalho para depois da resposta à Meta."""
    envios: Pares = field(default_factory=list)
    mensagens: list[tuple[str, str, dict]] = field(default_factory=list)  # (token, phone_number_id, corpo)


def _dicts(v) -> list[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _status(s: Session, st: dict) -> Pares:
    e = s.scalar(select(Envio).where(Envio.wamid == str(st.get("id") or "")).with_for_update())
    if e is None or e.situacao not in ORDEM:
        return []
    if st.get("status") == "failed":
        codigo = next((x.get("code") for x in _dicts(st.get("errors"))), None)
        e.situacao = "erro"
        e.erro, da_conta = graph.traduzir(400, codigo if isinstance(codigo, int) else None)
        return falha_whatsapp(s, e, da_conta)
    nova = SITUACAO.get(st.get("status"))
    if nova and ORDEM[nova] > ORDEM[e.situacao]:  # os avisos podem chegar fora de ordem
        e.situacao = nova
    return []


def _mensagem(s: Session, m: dict, phone_number_id: str) -> tuple[str, str, dict] | None:
    texto = (m.get("text") or {}).get("body") if m.get("type") == "text" else None
    if not isinstance(texto, str) or sem_acento(texto).strip(" .!\n\t").upper() not in PALAVRAS_SAIR:
        return None
    de = str(m.get("from") or "")
    telefone = telefone_canonico(de)
    if not 10 <= len(telefone) <= 13:
        return None
    if not esta_descadastrado(s, None, telefone):
        gravar(s, None, "whatsapp", None, telefone=telefone)
    wc = s.scalar(select(WhatsappConta))
    token = decifrar(wc.token_cifrado)
    if token is None:
        return None
    empresa = s.scalar(select(Conta.nome))
    return token, phone_number_id, modelo.corpo_texto(
        de, f"Pronto! Você não vai mais receber pesquisas da {empresa}.")


def receber(dados: dict) -> Depois:
    depois = Depois()
    for entrada in _dicts(dados.get("entry")):
        for mudanca in _dicts(entrada.get("changes")):
            valor = mudanca.get("value") if isinstance(mudanca.get("value"), dict) else {}
            meta = valor.get("metadata") if isinstance(valor.get("metadata"), dict) else {}
            phone_number_id = str(meta.get("phone_number_id") or "")
            with modo_sistema() as s:  # só descobre a conta pelo número
                conta_id = s.scalar(select(WhatsappConta.conta_id)
                                    .where(WhatsappConta.phone_number_id == phone_number_id))
            if conta_id is None:
                continue
            with em_conta(conta_id) as s:
                for st in _dicts(valor.get("statuses")):
                    depois.envios += _status(s, st)
                for m in _dicts(valor.get("messages")):
                    if (resposta := _mensagem(s, m, phone_number_id)) is not None:
                        depois.mensagens.append(resposta)
    return depois


def concluir(depois: Depois, entregas: list) -> None:
    """Segundo plano: confirmações de descadastro, e-mails de reserva e webhooks de saída."""
    for token, phone_number_id, corpo in depois.mensagens:
        try:
            graph.enviar_mensagem(token, phone_number_id, corpo)
        except graph.FalhaGraph:
            pass  # já registrado no log pela chamada; a pessoa já saiu da lista de qualquer forma
    processar_lista(depois.envios)
    entregar_lista(entregas)
