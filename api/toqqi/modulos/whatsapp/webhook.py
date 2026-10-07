"""Webhook da Meta (público): verificação (GET) e avisos (POST, assinados com o App Secret).

A conta é descoberta em modo sistema só pelo phone_number_id do aviso; o resto roda em em_conta(conta).
- `statuses`: atualiza o envio pelo wamid (enviado → entregue → lido; `failed` → erro em texto simples,
  devolve a franquia e, com "whatsapp_e_email", manda por e-mail).
- `messages` que pedem para sair (`pede_para_sair`, etapa 5f): a mensagem inteira normalizada (sem acento, minúsculas,
  só letras, números e espaços simples), até 40 caracteres, igual a uma de `FRASES_SAIR` ("sair", "sair da lista",
  "quero sair", "parar", "pare", "stop", "cancelar", "descadastrar", "nao quero mais", "nao quero mais receber",
  "nao quero receber", "nao quero receber mais"); vale texto e resposta de botão (`button.text`,
  `interactive.button_reply.title`; ex.: a resposta rápida "Não quero receber" de um modelo): descadastro do telefone
  (origem `whatsapp`) e confirmação por mensagem de sessão, que ensina o VOLTAR.
- `messages` que pedem para voltar (`pede_para_voltar`, pedido do Marcelo em 07/10/2026), do mesmo jeito, iguais a uma
  de `FRASES_VOLTAR` ("voltar", "quero voltar", "voltar a receber"...): com o telefone (ou um contato com ele) fora da
  lista, volta a receber em todos os canais (`descadastro.desfazer`, origem `whatsapp`) e confirma; sem estar fora,
  é ignorada. Outra mensagem é ignorada, sem resposta.
O que fala com a rede (confirmação, e-mails de reserva, webhooks de saída) fica para depois da resposta.
"""
import hashlib
import hmac
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.errors import AppError
from toqqi.core.segredos import decifrar
from toqqi.core.texto import sem_acento, telefone_canonico
from toqqi.modelos import Conta, Envio, WhatsappConta
from toqqi.modulos.envios.descadastro import desfazer, esta_descadastrado, gravar
from toqqi.modulos.envios.processamento import Pares, falha_whatsapp, processar_lista
from toqqi.modulos.integracoes.webhooks import entregar_lista
from toqqi.modulos.whatsapp import graph, modelo

FRASES_SAIR = frozenset({"sair", "sair da lista", "quero sair", "parar", "pare", "stop", "cancelar", "descadastrar",
                         "nao quero mais", "nao quero mais receber", "nao quero receber", "nao quero receber mais"})
FRASES_VOLTAR = frozenset({"voltar", "quero voltar", "voltar a receber", "quero voltar a receber", "quero receber",
                           "quero receber de novo", "receber de novo", "quero receber novamente", "receber novamente"})
MAX_FRASE = 40
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


def normalizar(texto: str) -> str:
    """Sem acento, minúsculas, só letras, números e espaços simples."""
    return re.sub(r"[^a-z0-9]+", " ", sem_acento(texto).lower()).strip()


def _frase(texto) -> str | None:
    """A mensagem inteira normalizada, se for curta (até `MAX_FRASE`); senão None."""
    if not isinstance(texto, str) or len(texto) > 1000:
        return None
    frase = normalizar(texto)
    return frase if len(frase) <= MAX_FRASE else None


def pede_para_sair(texto) -> bool:
    return _frase(texto) in FRASES_SAIR


def pede_para_voltar(texto) -> bool:
    return _frase(texto) in FRASES_VOLTAR


def _texto(m: dict) -> str | None:
    """O texto da mensagem: texto digitado ou a resposta de um botão (do modelo ou interativo)."""
    tipo = m.get("type")
    if tipo == "text":
        return (m.get("text") or {}).get("body")
    if tipo == "button":
        return (m.get("button") or {}).get("text")
    if tipo == "interactive":
        return ((m.get("interactive") or {}).get("button_reply") or {}).get("title")
    return None


def _mensagem(s: Session, m: dict, phone_number_id: str) -> tuple[str, str, dict] | None:
    texto = _texto(m)
    sair = pede_para_sair(texto)
    if not sair and not pede_para_voltar(texto):
        return None
    de = str(m.get("from") or "")
    telefone = telefone_canonico(de)
    if not 10 <= len(telefone) <= 13:
        return None
    empresa = s.scalar(select(Conta.nome))
    if sair:
        if not esta_descadastrado(s, None, telefone):
            gravar(s, None, "whatsapp", None, telefone=telefone)
        corpo = f"Pronto! Você não vai mais receber pesquisas da {empresa}. Se mudar de ideia, responda VOLTAR."
    else:
        if not desfazer(s, "whatsapp", telefone=telefone):
            return None  # não estava fora da lista: como uma mensagem qualquer, sem resposta
        corpo = f"Pronto! Você volta a receber as pesquisas da {empresa}. Para parar, responda SAIR."
    wc = s.scalar(select(WhatsappConta))
    token = decifrar(wc.token_cifrado)
    if token is None:
        return None
    return token, phone_number_id, modelo.corpo_texto(de, corpo)


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
    """Segundo plano: confirmações de SAIR e VOLTAR, e-mails de reserva e webhooks de saída."""
    for token, phone_number_id, corpo in depois.mensagens:
        try:
            graph.enviar_mensagem(token, phone_number_id, corpo)
        except graph.FalhaGraph:
            pass  # já registrado no log pela chamada; a pessoa já saiu (ou voltou) de qualquer forma
    processar_lista(depois.envios)
    entregar_lista(entregas)
