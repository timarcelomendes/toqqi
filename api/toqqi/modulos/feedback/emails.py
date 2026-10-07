"""E-mails do feedback (docs/api-feedback.md §5).

- `avisar_equipe`: feedback novo ou mensagem nova do usuário → a cada superadmin (`SUPERADMIN_EMAILS`) com o e-mail
  confirmado e ativo, com o texto, quem mandou, a conta e o botão para a Plataforma. Não entra no registro de e-mails
  enviados da conta (sai para a equipe Toqqi, não em nome da conta).
- `avisar_usuario`: resposta da equipe → a quem enviou o feedback, com o texto da resposta, a situação nova (se mudou)
  e o botão para a conversa. Entra no registro da conta (tipo `feedback`). Quem chama confere antes se a pessoa ainda
  pode receber (ativa, e-mail confirmado e sem ter retirado o aceite dos termos).
"""
import logging
from dataclasses import dataclass
from datetime import datetime

from toqqi.core import email, relogio
from toqqi.core.config import config
from toqqi.core.db import modo_sistema
from toqqi.core.planos import NOMES as NOMES_PLANOS
from toqqi.modulos.feedback import regras

log = logging.getLogger("toqqi.feedback")

MAX_TEXTO_EMAIL = 3000
VERBOS = {"erro": "relatou um erro", "sugestao": "deu uma sugestão", "melhoria": "pediu uma melhoria",
          "elogio": "fez um elogio"}
O_QUE = {"erro": "o erro que você relatou", "sugestao": "a sugestão que você deu",
         "melhoria": "a melhoria que você pediu", "elogio": "o elogio que você fez"}
SITUACOES_CONTA = {"teste": "em teste", "teste_expirado": "teste encerrado", "ativa": "assinante",
                   "atrasada": "pagamento atrasado", "cancelada": "cancelada", "cortesia": "cortesia"}


@dataclass(frozen=True)
class AvisoEquipe:
    feedback_id: int
    tipo: str
    impacto: str | None
    texto: str
    imagens: int
    autor_nome: str
    autor_email: str
    conta_nome: str
    conta_plano: str | None
    conta_situacao: str | None
    pagina: str | None
    pagina_titulo: str | None
    autoriza_depoimento: bool


@dataclass(frozen=True)
class RespostaUsuario:
    feedback_id: int
    conta_id: int
    tipo: str
    criado_em: datetime
    para: str
    nome: str
    equipe_nome: str
    texto: str
    situacao: str | None  # a situação nova, quando mudou junto


def _url(caminho: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}{caminho}"


def _paragrafos(texto: str) -> list[str]:
    """O texto em parágrafos (separados por linha em branco), cortado em 3.000 caracteres."""
    if len(texto) > MAX_TEXTO_EMAIL:
        texto = texto[: MAX_TEXTO_EMAIL - 1].rstrip() + "…"
    return [p.strip() for p in texto.split("\n\n") if p.strip()]


def _conta(a: AvisoEquipe) -> str:
    detalhes = [x for x in (NOMES_PLANOS.get(a.conta_plano or "", a.conta_plano),
                            SITUACOES_CONTA.get(a.conta_situacao or "", a.conta_situacao)) if x]
    return f"{a.conta_nome} ({', '.join(detalhes)})" if detalhes else a.conta_nome


def conteudo_equipe(a: AvisoEquipe, novo: bool) -> tuple[str, list]:
    """(assunto, parágrafos) do aviso à equipe."""
    rotulo = regras.TIPOS[a.tipo]
    quem = f"{a.autor_nome}, {a.conta_nome}" if a.conta_nome else a.autor_nome
    urgente = "[Impede o trabalho] " if novo and a.impacto == "bloqueia" else ""
    assunto = (f"{urgente}Feedback novo: {rotulo} de {quem}" if novo
               else f"Nova mensagem no feedback #{a.feedback_id} de {quem}")
    abertura = (f"{a.autor_nome} ({a.autor_email}), da conta {_conta(a)}, {VERBOS[a.tipo]}:" if novo
                else f"{a.autor_nome} ({a.autor_email}), da conta {_conta(a)}, escreveu no feedback #{a.feedback_id} "
                     f"({rotulo.lower()}):")
    paragrafos: list = [abertura, *(_paragrafos(a.texto) or ["(só imagens)"])]
    detalhes = []
    if novo and a.impacto:
        detalhes.append(f"Impacto: {regras.IMPACTOS[a.impacto]}.")
    if novo and (a.pagina_titulo or a.pagina):
        tela = " ".join(x for x in (a.pagina_titulo, f"({a.pagina})" if a.pagina else None) if x)
        detalhes.append(f"Tela: {tela}.")
    if a.imagens:
        detalhes.append("1 imagem anexada." if a.imagens == 1 else f"{a.imagens} imagens anexadas.")
    if novo and a.autoriza_depoimento:
        detalhes.append("Autorizou usar este elogio no site do Toqqi, com o nome e a empresa.")
    if detalhes:
        paragrafos += [email.Titulo("Detalhes"), *detalhes]
    return assunto, paragrafos


def avisar_equipe(a: AvisoEquipe, novo: bool) -> int:
    """Manda o aviso a cada superadmin confirmado; devolve quantos e-mails saíram. Nunca levanta."""
    from toqqi.modulos.plataforma.erros import superadmins_confirmados  # evita import circular na carga

    try:
        with modo_sistema() as s:
            para = superadmins_confirmados(s)
        if not para:
            log.warning("Feedback #%s: nenhum superadmin com o e-mail confirmado para avisar (SUPERADMIN_EMAILS).",
                        a.feedback_id)
            return 0
        assunto, paragrafos = conteudo_equipe(a, novo)
        rodape = ("Você recebe este aviso por fazer parte da equipe Toqqi (SUPERADMIN_EMAILS). Responda em Plataforma › "
                  "Feedback: a resposta chega à pessoa no Toqqi e por e-mail.", "Plataforma › Feedback",
                  _url("/plataforma/feedback"))
        for destino in para:
            email.enviar(destino, assunto, paragrafos,
                         ("Abrir na Plataforma", _url(f"/plataforma/feedback/{a.feedback_id}")), rodape,
                         assunto_no_log=f"Feedback #{a.feedback_id}")
        return len(para)
    except Exception:  # noqa: BLE001 - o aviso nunca derruba o envio do feedback
        log.exception("Feedback #%s: falha ao avisar a equipe.", a.feedback_id)
        return 0


def conteudo_usuario(r: RespostaUsuario) -> tuple[str, list]:
    quando = r.criado_em.astimezone(relogio.FUSO).strftime("%d/%m")
    paragrafos: list = [f"Olá, {r.nome}!", f"{r.equipe_nome}, da equipe Toqqi, respondeu {O_QUE[r.tipo]} em {quando}:",
                        *_paragrafos(r.texto)]
    if r.situacao:
        paragrafos.append(f"Situação do seu feedback: {regras.SITUACOES[r.situacao]}.")
    return "A equipe Toqqi respondeu seu feedback", paragrafos


def avisar_usuario(r: RespostaUsuario) -> None:
    assunto, paragrafos = conteudo_usuario(r)
    rodape = ("Você recebe este e-mail porque enviou um feedback ao Toqqi. Para responder, escreva na conversa, em Seus "
              "feedbacks.", "Seus feedbacks", _url("/feedback"))
    email.enviar(r.para, assunto, paragrafos, ("Ver a conversa", _url(f"/feedback/{r.feedback_id}")), rodape,
                 conta_id=r.conta_id, tipo="feedback")
