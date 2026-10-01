"""Conteúdo dos e-mails de pesquisa (convite, lembrete, agradecimento) e da mensagem de WhatsApp.

O layout é da plataforma: HTML em tabelas com estilos inline (Gmail, Outlook e celular).
Os textos da conta são texto puro; aqui viram parágrafos escapados. Com logo (o do formulário, senão o da conta),
o e-mail ganha um cabeçalho com a imagem (URL absoluta, até 48 px de altura, `alt` = nome da conta); sem logo,
fica como sempre foi.
"""
import html
import re
from urllib.parse import quote

from toqqi.core.config import config
from toqqi.core.email import Mensagem
from toqqi.modulos.envios.descadastro import link_descadastro, link_um_clique
from toqqi.modulos.formularios.validacao import pergunta_principal, tipo_principal
from toqqi.modulos.respostas.registro import renderizar
from toqqi.modulos.respostas.registro import variaveis as variaveis_formulario

VERMELHO, AMARELO, VERDE, AZUL = "#dc2626", "#d97706", "#16a34a", "#1f6feb"
FONTE = "font-family:Arial,Helvetica,sans-serif"


def variaveis(empresa: str, nome_contato: str | None = None, empresa_cliente: str | None = None,
              link: str | None = None, nota: int | None = None) -> dict:
    """Variáveis dos textos de envio: {nome} (primeiro nome), {empresa}, {empresa_cliente}, {link}, {nota}."""
    primeiro = (nome_contato or "").strip().split(" ")[0] if nome_contato else ""
    return {"nome": primeiro, "empresa": empresa or "", "empresa_cliente": empresa_cliente or "",
            "link": link or "", "nota": "" if nota is None else str(nota)}


def paragrafos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]


def _p(texto: str) -> str:
    corpo = "<br>".join(html.escape(linha) for linha in texto.split("\n"))
    return f'<p style="margin:0 0 16px;{FONTE};font-size:16px;line-height:24px;color:#1f2937">{corpo}</p>'


def _com_nota(link: str, nota: int) -> str:
    return f"{link}{'&' if '?' in link else '?'}nota={nota}"


def _cor(tipo: str, n: int) -> str:
    if tipo == "nps":
        return VERMELHO if n <= 6 else AMARELO if n <= 8 else VERDE
    return VERMELHO if n <= 2 else AMARELO if n == 3 else VERDE


def _botoes_nota(tipo: str, link: str, rotulo_min: str, rotulo_max: str) -> str:
    notas = range(0, 11) if tipo == "nps" else range(1, 6)
    largura = 36 if tipo == "nps" else 52
    celulas = "".join(
        f'<td align="center" style="padding:2px">'
        f'<a href="{html.escape(_com_nota(link, n))}" target="_blank" style="display:block;width:{largura}px;'
        f'height:36px;line-height:36px;background:{_cor(tipo, n)};color:#ffffff;{FONTE};font-size:16px;'
        f'font-weight:bold;text-decoration:none;border-radius:6px;text-align:center">{n}</a></td>'
        for n in notas
    )
    rotulos = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td align="left" style="{FONTE};font-size:12px;color:#6b7280;padding-top:6px">{html.escape(rotulo_min)}</td>'
        f'<td align="right" style="{FONTE};font-size:12px;color:#6b7280;padding-top:6px">{html.escape(rotulo_max)}</td>'
        f"</tr></table>"
    )
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
            f'style="margin:0 auto"><tr>{celulas}</tr><tr><td colspan="{len(notas)}">{rotulos}</td></tr></table>')


def _botao(rotulo: str, link: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr>'
        f'<td align="center" bgcolor="{AZUL}" style="border-radius:6px">'
        f'<a href="{html.escape(link)}" target="_blank" style="display:inline-block;padding:12px 24px;{FONTE};'
        f'font-size:16px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:6px">'
        f"{html.escape(rotulo)}</a></td></tr></table>"
    )


def bloco_da_nota(perguntas: list[dict], link: str, v: dict) -> str:
    """NPS → 0–10; CSAT/estrelas → 1–5; personalizado → um botão."""
    tipo = tipo_principal(perguntas)
    if tipo == "personalizado":
        return _botao("Responder pesquisa", link)
    p = pergunta_principal(perguntas)
    titulo = renderizar(p.get("titulo") or "", v) or ""
    if tipo == "nps":
        rmin, rmax = p.get("rotulo_min") or "Nada provável", p.get("rotulo_max") or "Muito provável"
    else:
        rmin, rmax = p.get("rotulo_min") or "Muito insatisfeito", p.get("rotulo_max") or "Muito satisfeito"
    pergunta = (f'<p style="margin:0 0 12px;{FONTE};font-size:16px;line-height:24px;font-weight:bold;'
                f'color:#111827;text-align:center">{html.escape(titulo)}</p>') if titulo else ""
    return pergunta + _botoes_nota(tipo, link, rmin, rmax)


def _cabecalho(logo_url: str | None, empresa: str) -> str:
    if not logo_url:
        return ""
    # height="48" vale no Outlook (que ignora max-height); a largura acompanha a proporção da imagem
    return (
        '<tr><td align="center" style="padding:28px 28px 0">'
        f'<img src="{html.escape(logo_url)}" alt="{html.escape(empresa or "")}" height="48" '
        'style="display:block;height:48px;max-height:48px;width:auto;max-width:100%;border:0;outline:none;'
        f'text-decoration:none;{FONTE};font-size:16px;font-weight:bold;color:#111827"></td></tr>'
    )


def _layout(conteudo: str, empresa: str, sair: str, logo_url: str | None = None) -> str:
    rodape = (
        f'<p style="margin:0 0 6px;{FONTE};font-size:12px;line-height:18px;color:#6b7280">'
        f"Você recebeu esta pesquisa porque é cliente de {html.escape(empresa)}.</p>"
        f'<p style="margin:0;{FONTE};font-size:12px;line-height:18px">'
        f'<a href="{html.escape(sair)}" target="_blank" style="color:#6b7280;text-decoration:underline">'
        f"Não quero mais receber pesquisas</a></p>"
    )
    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f3f4f6">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f3f4f6">'
        '<tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:600px;background:#ffffff;border-radius:8px">'
        f"{_cabecalho(logo_url, empresa)}"
        f'<tr><td style="padding:32px 28px">{conteudo}</td></tr>'
        f'<tr><td style="padding:16px 28px 28px;border-top:1px solid #e5e7eb">{rodape}</td></tr>'
        "</table></td></tr></table></body></html>"
    )


def _cabecalhos(conta_id: int, email: str) -> dict[str, str]:
    return {"List-Unsubscribe": f"<{link_um_clique(conta_id, email)}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def email_pesquisa(*, conta_id: int, para: str, empresa: str, assunto: str, texto: str, perguntas: list[dict],
                   link: str, v: dict, remetente_nome: str | None, responder_para: str | None,
                   logo_url: str | None = None) -> Mensagem:
    """Convite ou lembrete: texto da conta + bloco da nota + rodapé com descadastro."""
    sair = link_descadastro(conta_id, para)
    partes = paragrafos(renderizar(texto, v))
    conteudo = "".join(_p(x) for x in partes) + bloco_da_nota(perguntas, link, variaveis_formulario(empresa, v["nome"]))
    texto_puro = "\n\n".join(partes + [
        f"Responda aqui: {link}",
        f"Você recebeu esta pesquisa porque é cliente de {empresa}.",
        f"Não quero mais receber pesquisas: {sair}",
    ])
    return Mensagem(para=para, assunto=renderizar(assunto, v), texto=texto_puro,
                    html=_layout(conteudo, empresa, sair, logo_url), remetente_nome=remetente_nome or empresa,
                    responder_para=responder_para, cabecalhos=_cabecalhos(conta_id, para))


def email_agradecimento(*, conta_id: int, para: str, empresa: str, texto: str, v: dict,
                        remetente_nome: str | None, responder_para: str | None,
                        logo_url: str | None = None) -> Mensagem:
    sair = link_descadastro(conta_id, para)
    partes = paragrafos(renderizar(texto, v))
    texto_puro = "\n\n".join(partes + [f"Não quero mais receber pesquisas: {sair}"])
    assunto = f"{empresa} agradece a sua resposta" if empresa else "Obrigado pela sua resposta"
    return Mensagem(para=para, assunto=assunto, texto=texto_puro,
                    html=_layout("".join(_p(x) for x in partes), empresa, sair, logo_url),
                    remetente_nome=remetente_nome or empresa, responder_para=responder_para,
                    cabecalhos=_cabecalhos(conta_id, para))


def whatsapp(telefone: str, texto: str, v: dict) -> tuple[str, str]:
    """(endereço wa.me com a mensagem pronta, mensagem). Telefone só com dígitos, com DDI 55."""
    numero = telefone if len(telefone) > 11 else "55" + telefone
    mensagem = renderizar(texto, v)
    return f"https://wa.me/{numero}?text={quote(mensagem, safe='')}", mensagem


def link_formulario_publico(codigo: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/f/{codigo}?canal=link"
