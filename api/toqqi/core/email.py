"""Envio de e-mail com provedores trocáveis por EMAIL_PROVIDER.

- console: imprime no terminal (desenvolvimento);
- memory: guarda em `caixa_memoria` (testes);
- zeptomail / resend: envio real via HTTP.

Dois caminhos:
- `enviar()`: e-mails do sistema (confirmação, senha...), no coral da marca (botão `#D63A18` com texto branco, links
  `#B02F13`). Falha vai para o log e não derruba o fluxo.
- `enviar_mensagem()`: pesquisas. Falha vira `FalhaEnvio` com um texto simples para o histórico
  (o detalhe técnico do provedor vai só para o log).

Registro de e-mails enviados (etapa 5e): todo e-mail que sai em nome de uma conta grava uma linha em
`emails_enviados` depois da tentativa — quem chama passa `conta_id` e `tipo` (`TIPOS`); sem os dois (e-mail sem conta
conhecida), não grava. Situação `enviado` (o provedor aceitou; com `console`/`memory` também) ou `falhou`, com o texto
simples de `traduzir_falha` (nunca o corpo do provedor). O assunto vai como saiu, cortado em 300; nada do corpo. A
gravação usa uma transação própria (`em_conta`), depois da tentativa: nunca derruba o envio — falha ao gravar só vai
para o log.
"""
import html as html_lib
import logging
from dataclasses import dataclass, field
from email.utils import parseaddr

import httpx
from sqlalchemy import insert

from toqqi.core.config import config
from toqqi.core.db import em_conta
from toqqi.modelos import EmailEnviado

log = logging.getLogger("toqqi.email")

MSG_ENDERECO = "O endereço de e-mail não existe ou recusou a mensagem."
MSG_FORA_DO_AR = "O provedor de e-mail está fora do ar; tentaremos de novo."
MSG_LIMITE = "Limite de envio do provedor atingido; tentaremos de novo."
MSG_CONFIGURACAO = "O envio de e-mails da plataforma está com problema de configuração. A equipe Toqqi foi avisada."

# cores dos e-mails do sistema (design-system: coral-600 no botão, contraste AA com branco; coral-700 nos links)
COR_BOTAO = "#D63A18"
COR_LINK = "#B02F13"

# tipos do registro de e-mails enviados (Auditoria › E-mails enviados) e os rótulos da tela
TIPOS = {
    "convite": "Convite de pesquisa",
    "lembrete": "Lembrete",
    "agradecimento": "Agradecimento",
    "retorno": "Retorno ao cliente",
    "teste": "E-mail de teste",
    "confirmacao": "Confirmação de e-mail",
    "senha": "Redefinição de senha",
    "boas_vindas": "Boas-vindas",
    "alerta_risco": "Alerta de risco",
    "resumo_semanal": "Resumo semanal",
    "pico": "Pico de reclamações",
    "indicacao": "Nova indicação",
    "aviso": "Aviso aos administradores",
    "cobranca": "Cobrança",
    "feedback": "Resposta da equipe Toqqi",  # feedback: a equipe respondeu o feedback da pessoa
}
MAX_ASSUNTO_REGISTRO = 300
MAX_ERRO_REGISTRO = 500


@dataclass
class Mensagem:
    para: str
    assunto: str
    texto: str
    html: str
    remetente_nome: str | None = None      # vira "{remetente_nome} via Toqqi"
    responder_para: str | None = None
    cabecalhos: dict[str, str] = field(default_factory=dict)


class FalhaEnvio(Exception):
    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


caixa_memoria: list[Mensagem] = []


def _limpar_nome(nome: str) -> str:
    """Nome de exibição seguro para cabeçalho (sem aspas, <>, quebras de linha)."""
    return " ".join("".join(c for c in nome if c not in '"<>\\\r\n').split())[:120]


def remetente(m: Mensagem) -> tuple[str, str]:
    nome, endereco = parseaddr(config().EMAIL_FROM)
    if m.remetente_nome:
        nome = f"{_limpar_nome(m.remetente_nome)} via Toqqi"
    return nome or "Toqqi", endereco


class Provedor:
    def enviar(self, m: Mensagem) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class Console(Provedor):
    def enviar(self, m: Mensagem) -> None:
        extras = "".join(f"{k}: {v}\n" for k, v in m.cabecalhos.items())
        print(f"\n--- e-mail para {m.para} ---\nAssunto: {m.assunto}\n{extras}\n{m.texto}\n--- fim ---\n", flush=True)


class Memoria(Provedor):
    def enviar(self, m: Mensagem) -> None:
        caixa_memoria.append(m)


class ZeptoMail(Provedor):
    URL = "https://api.zeptomail.com/v1.1/email"

    def enviar(self, m: Mensagem) -> None:
        nome, endereco = remetente(m)
        corpo = {
            "from": {"address": endereco, "name": nome},
            "to": [{"email_address": {"address": m.para}}],
            "subject": m.assunto,
            "htmlbody": m.html,
            "textbody": m.texto,
        }
        if m.responder_para:
            corpo["reply_to"] = [{"address": m.responder_para}]
        if m.cabecalhos:
            corpo["mime_headers"] = m.cabecalhos
        token = config().ZEPTOMAIL_TOKEN
        if not token.lower().startswith("zoho-enczapikey"):
            token = f"Zoho-enczapikey {token}"
        r = httpx.post(self.URL, json=corpo, headers={"Authorization": token}, timeout=10)
        r.raise_for_status()


class Resend(Provedor):
    URL = "https://api.resend.com/emails"

    def enviar(self, m: Mensagem) -> None:
        nome, endereco = remetente(m)
        corpo = {"from": f'"{nome}" <{endereco}>', "to": [m.para], "subject": m.assunto,
                 "html": m.html, "text": m.texto}
        if m.responder_para:
            corpo["reply_to"] = [m.responder_para]
        if m.cabecalhos:
            corpo["headers"] = m.cabecalhos
        r = httpx.post(
            self.URL, json=corpo, headers={"Authorization": f"Bearer {config().RESEND_API_KEY}"}, timeout=10
        )
        r.raise_for_status()


_PROVEDORES = {"console": Console, "memory": Memoria, "zeptomail": ZeptoMail, "resend": Resend}


def provedor() -> Provedor:
    return _PROVEDORES[config().EMAIL_PROVIDER]()


def traduzir_falha(e: Exception) -> str:
    """Erro do provedor → texto simples para quem usa o sistema."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 429:
            return MSG_LIMITE
        if status in (401, 403):
            return MSG_CONFIGURACAO
        if status >= 500:
            return MSG_FORA_DO_AR
        return MSG_ENDERECO
    return MSG_FORA_DO_AR


def registrar_envio(conta_id: int | None, tipo: str | None, para: str, assunto: str | None,
                    erro: str | None = None) -> None:
    """Grava a tentativa em `emails_enviados` (transação própria, na conta). Sem conta ou sem tipo, não grava. Nunca
    levanta: falha ao gravar vai só para o log (sem o destinatário nem o assunto)."""
    if conta_id is None or tipo is None:
        return
    try:
        if tipo not in TIPOS:
            raise ValueError(f"tipo de e-mail desconhecido: {tipo}")
        with em_conta(conta_id) as s:
            s.execute(insert(EmailEnviado).values(
                conta_id=conta_id, tipo=tipo, destinatario=para, assunto=(assunto or "")[:MAX_ASSUNTO_REGISTRO],
                situacao="falhou" if erro else "enviado", erro=erro[:MAX_ERRO_REGISTRO] if erro else None))
    except Exception:  # noqa: BLE001 - o registro nunca derruba o envio
        log.exception("Falha ao registrar o e-mail enviado (conta %s, tipo %s)", conta_id, tipo)


def enviar_mensagem(m: Mensagem, *, conta_id: int | None = None, tipo: str | None = None) -> None:
    """Envia uma pesquisa. Levanta FalhaEnvio com o texto simples do erro. Com `conta_id` e `tipo` (convite,
    lembrete, agradecimento ou teste), registra a tentativa em `emails_enviados`."""
    try:
        provedor().enviar(m)
    except Exception as e:  # noqa: BLE001 - qualquer falha do provedor vira FalhaEnvio
        detalhe = e.response.text[:500] if isinstance(e, httpx.HTTPStatusError) else repr(e)
        log.warning("Falha do provedor de e-mail ao enviar '%s' para %s: %s", m.assunto, m.para, detalhe)
        falha = FalhaEnvio(traduzir_falha(e))
        registrar_envio(conta_id, tipo, m.para, m.assunto, falha.mensagem)
        raise falha from e
    registrar_envio(conta_id, tipo, m.para, m.assunto)


@dataclass(frozen=True)
class Titulo:
    """Título de seção num e-mail do sistema (ex.: resumo semanal)."""
    texto: str


@dataclass(frozen=True)
class Link:
    """Parágrafo que é um link (ex.: uma ação do plano, no resumo semanal)."""
    texto: str
    url: str


Paragrafo = str | Titulo | Link


def _parte_html(p: Paragrafo) -> str:
    if isinstance(p, Titulo):
        return f'<p style="margin:20px 0 6px;font-size:16px;font-weight:bold">{html_lib.escape(p.texto)}</p>'
    if isinstance(p, Link):
        return f'<p><a href="{html_lib.escape(p.url)}" style="color:{COR_LINK}">{html_lib.escape(p.texto)}</a></p>'
    return f"<p>{html_lib.escape(p)}</p>"


def _parte_texto(p: Paragrafo) -> str:
    if isinstance(p, Titulo):
        return p.texto.upper()
    if isinstance(p, Link):
        return f"{p.texto}: {p.url}"
    return p


def _html(paragrafos: list[Paragrafo], botao: tuple[str, str] | None,
          rodape: tuple[str, str, str] | None = None) -> str:
    partes = [_parte_html(p) for p in paragrafos]
    if botao:
        rotulo, link = botao
        endereco = html_lib.escape(link)
        partes.append(
            f'<p><a href="{endereco}" style="background:{COR_BOTAO};color:#ffffff;'
            f'padding:10px 16px;border-radius:6px;text-decoration:none">{html_lib.escape(rotulo)}</a></p>'
            # o endereço quebra em qualquer ponto: links longos (com filtros) não alargam o e-mail no celular; vai num
            # link com a cor da marca (sem ele, o Gmail transforma o endereço num link azul)
            f'<p style="color:#666;font-size:13px;overflow-wrap:anywhere;word-break:break-all">'
            f'Se o botão não funcionar, copie este endereço: '
            f'<a href="{endereco}" style="color:{COR_LINK}">{endereco}</a></p>'
        )
    if rodape:
        texto, rotulo, link = rodape
        ancora = f'<a href="{html_lib.escape(link)}" style="color:#666">{html_lib.escape(rotulo)}</a>'
        corpo = html_lib.escape(texto)
        corpo = corpo.replace(html_lib.escape(rotulo), ancora, 1) if rotulo in texto else f"{corpo} {ancora}"
        partes.append(f'<p style="color:#666;font-size:12px;border-top:1px solid #e5e7eb;padding-top:12px">{corpo}</p>')
    return '<div style="font-family:Arial,sans-serif;font-size:15px;color:#222">' + "".join(partes) + "</div>"


def enviar(para: str, assunto: str, paragrafos: list[Paragrafo], botao: tuple[str, str] | None = None,
           rodape: tuple[str, str, str] | None = None, assunto_no_log: str | None = None, *,
           conta_id: int | None = None, tipo: str | None = None) -> None:
    """E-mail do sistema. `paragrafos`: textos (ou Titulo/Link); `botao` = (rótulo, link); `rodape` = (texto,
    trecho do texto que vira link, link), ex.: o "Minha conta" dos e-mails do painel. `assunto_no_log`: o que vai para
    o log e para o registro de e-mails enviados no lugar do assunto (assunto com dados de pessoas, como o aviso de
    indicação: excluir a indicação a pedido da pessoa não pode deixar o nome dela no registro). `conta_id` e `tipo`
    (`TIPOS`): a conta em nome de quem o e-mail sai, para o registro de e-mails enviados."""
    texto = "\n\n".join(_parte_texto(p) for p in paragrafos)
    if botao:
        texto += f"\n\n{botao[0]}: {botao[1]}"
    texto += "\n\nEquipe Toqqi"
    if rodape:
        texto += f"\n\n{rodape[0]} {rodape[2]}"
    m = Mensagem(para=para, assunto=assunto, texto=texto, html=_html(paragrafos, botao, rodape))
    erro = None
    try:
        provedor().enviar(m)
    except Exception as e:  # noqa: BLE001 - e-mail não pode derrubar o fluxo
        log.exception("Falha ao enviar e-mail '%s' para %s", assunto_no_log or assunto, para)
        erro = traduzir_falha(e)
    registrar_envio(conta_id, tipo, para, assunto_no_log or assunto, erro)
