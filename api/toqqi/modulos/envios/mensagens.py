"""Conteúdo dos e-mails de pesquisa (convite, lembrete, agradecimento e o e-mail de teste) e da mensagem de WhatsApp.

O layout é da plataforma: HTML em tabelas com estilos inline (Gmail, Outlook e celular), num cartão de 600 px. Os
textos da conta são texto puro; aqui viram parágrafos escapados. Nenhum HTML da conta entra no e-mail.

Visual guiado (etapa 5e): a conta escolhe em Configurações › Envios a cor de destaque, se o logo aparece, a imagem de
topo (do banco de imagens), a assinatura e o rodapé; `configuracao.visual` junta isso num `Visual` para cada envio.
Ordem no cartão:
1. faixa de 4 px na cor de destaque;
2. logo (o do formulário, senão o da conta; URL absoluta, até 48 px de altura, `alt` = nome da conta), se houver e
   se `email_mostrar_logo`;
3. imagem de topo: largura do cartão (`width="544"`, `max-width:100%`), altura proporcional, `alt` vazio, sem link;
4. textos; 5. bloco da nota; 6. assinatura (parágrafos escapados, cor #4b5563);
7. rodapé: o da conta (escapado; quebras de linha viram <br>) e, sempre, as duas linhas fixas (por que a pessoa
   recebeu e o descadastro).
Cor de destaque: `email_cor`; nula, a cor do tema do formulário do envio; nenhuma válida, #D63A18 (o coral da marca).
Vale para a faixa e para o botão "Responder pesquisa" (formulário personalizado) — o corpo não tem outros links: os
textos são texto puro. Texto do botão: branco se o contraste com a cor for de 4,5:1 ou mais (luminância relativa da
WCAG), senão #111827. Os botões de nota continuam vermelho/amarelo/verde.
Texto puro: a assinatura e o rodapé da conta entram antes das linhas fixas.
"""
import html
import re
from dataclasses import dataclass
from urllib.parse import quote

from toqqi.core.config import config
from toqqi.core.email import Mensagem
from toqqi.modulos.envios.descadastro import link_descadastro, link_um_clique
from toqqi.modulos.formularios.validacao import pergunta_principal, tipo_principal
from toqqi.modulos.respostas.registro import renderizar
from toqqi.modulos.respostas.registro import variaveis as variaveis_formulario

VERMELHO, AMARELO, VERDE = "#dc2626", "#d97706", "#16a34a"
COR_PADRAO = "#D63A18"  # coral da marca: sem cor da conta nem do formulário
BRANCO, TEXTO_ESCURO = "#ffffff", "#111827"
COR_ASSINATURA = "#4b5563"
CONTRASTE_MINIMO = 4.5  # WCAG AA para texto normal
MARGEM = 28  # margem lateral do conteúdo no cartão de 600 px
LARGURA_IMAGEM = 600 - 2 * MARGEM  # 544: a imagem de topo ocupa a largura do conteúdo
ALTURA_NOTA, FONTE_NOTA = 40, 15  # régua de notas (px): altura de cada nota e tamanho do número
ESPACO_NOTAS = 2  # px entre as notas (cellspacing): a 320 px de tela, cada nota do NPS fica com ~20 px de largura
LARGURA_MAXIMA_CSAT = 320  # px: as 5 notas do CSAT ficam juntas, no meio do cartão
FONTE = "font-family:Arial,Helvetica,sans-serif"
_RE_COR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class ImagemTopo:
    url: str
    largura: int | None = None
    altura: int | None = None


@dataclass(frozen=True)
class Visual:
    """O visual de um e-mail de pesquisa, já resolvido para o envio (`configuracao.visual`)."""
    cor: str = COR_PADRAO
    logo_url: str | None = None  # None também quando a conta desligou "Mostrar o logo"
    imagem_topo: ImagemTopo | None = None
    assinatura: str | None = None
    rodape: str | None = None


# ---- cores ------------------------------------------------------------------------------

def cor_valida(cor) -> bool:
    return isinstance(cor, str) and _RE_COR.fullmatch(cor) is not None


def cor_de_destaque(cor_da_conta: str | None, cor_do_formulario: str | None) -> str:
    """A cor da conta (`email_cor`); nula ou inválida, a do tema do formulário; nenhuma válida, o coral da marca.
    Sempre `#RRGGBB` em maiúsculas (o tema do formulário guarda em minúsculas)."""
    for cor in (cor_da_conta, cor_do_formulario):
        if cor_valida(cor):
            return cor.upper()
    return COR_PADRAO


def _canal(valor: int) -> float:
    c = valor / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(cor: str) -> float:
    """Luminância relativa (WCAG) de uma cor #RRGGBB."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(a: str, b: str) -> float:
    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def cor_do_texto(fundo: str) -> str:
    """Texto sobre `fundo`: branco se o contraste for de 4,5:1 ou mais; senão #111827."""
    return BRANCO if contraste(fundo, BRANCO) >= CONTRASTE_MINIMO else TEXTO_ESCURO


# ---- textos -----------------------------------------------------------------------------

def variaveis(empresa: str, nome_contato: str | None = None, empresa_cliente: str | None = None,
              link: str | None = None, nota: int | None = None) -> dict:
    """Variáveis dos textos de envio: {nome} (primeiro nome), {empresa}, {empresa_cliente}, {link}, {nota}. O
    agradecimento ganha {motivo} (processamento), sempre por último: o comentário do cliente não passa por outra troca."""
    primeiro = (nome_contato or "").strip().split(" ")[0] if nome_contato else ""
    return {"nome": primeiro, "empresa": empresa or "", "empresa_cliente": empresa_cliente or "",
            "link": link or "", "nota": "" if nota is None else str(nota)}


def paragrafos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]


def _linhas(texto: str) -> str:
    """Texto escapado, com as quebras de linha em <br>."""
    return "<br>".join(html.escape(linha) for linha in texto.split("\n"))


def _p(texto: str) -> str:
    return f'<p style="margin:0 0 16px;{FONTE};font-size:16px;line-height:24px;color:#1f2937">{_linhas(texto)}</p>'


def _assinatura(texto: str | None) -> str:
    return "".join(f'<p style="margin:{24 if i == 0 else 8}px 0 0;{FONTE};font-size:16px;line-height:24px;'
                   f'color:{COR_ASSINATURA}">{_linhas(parte)}</p>' for i, parte in enumerate(paragrafos(texto)))


def _extras_texto(visual: Visual) -> list[str]:
    """Assinatura e rodapé da conta na versão em texto puro (antes das linhas fixas)."""
    return paragrafos(visual.assinatura) + ([visual.rodape] if visual.rodape else [])


# ---- bloco da nota ----------------------------------------------------------------------

def _com_nota(link: str, nota: int) -> str:
    return f"{link}{'&' if '?' in link else '?'}nota={nota}"


def _cor(tipo: str, n: int) -> str:
    if tipo == "nps":
        return VERMELHO if n <= 6 else AMARELO if n <= 8 else VERDE
    return VERMELHO if n <= 2 else AMARELO if n == 3 else VERDE


def _botoes_nota(tipo: str, link: str, rotulo_min: str, rotulo_max: str) -> str:
    """A régua de notas (etapa 5h): cabe em 320 px sem rolagem lateral e continua boa nos 600 px do cartão.

    Tabela com 100% da largura do conteúdo (no máximo os 544 px do cartão), uma célula de largura percentual por nota
    (NPS 11, CSAT 5) e nenhuma largura fixa. A cor vai no `bgcolor` da célula (o Outlook só pinta a célula) e no fundo
    do link, em bloco com 40 px de altura e fonte de 15 px (o toque vale na nota inteira); `table-layout:fixed`
    segura a largura mesmo com a fonte aumentada no celular. Os rótulos vêm embaixo, nas pontas.
    O CSAT fica em até 320 px, no meio (5 notas na largura toda do cartão ficariam com 100 px cada; o Outlook ignora o
    `max-width` e usa os 100%)."""
    notas = range(0, 11) if tipo == "nps" else range(1, 6)
    fracao = 100 / len(notas)
    limite = "" if tipo == "nps" else f";max-width:{LARGURA_MAXIMA_CSAT}px;margin:0 auto"
    centro = "" if tipo == "nps" else ' align="center"'
    celulas = "".join(
        f'<td width="{int(fracao)}%" height="{ALTURA_NOTA}" align="center" valign="middle" bgcolor="{_cor(tipo, n)}" '
        f'style="width:{fracao:.2f}%;height:{ALTURA_NOTA}px;padding:0;background:{_cor(tipo, n)};border-radius:6px">'
        f'<a href="{html.escape(_com_nota(link, n))}" target="_blank" style="display:block;height:{ALTURA_NOTA}px;'
        f'mso-line-height-rule:exactly;line-height:{ALTURA_NOTA}px;background:{_cor(tipo, n)};color:#ffffff;{FONTE};'
        f'font-size:{FONTE_NOTA}px;font-weight:bold;text-decoration:none;border-radius:6px;text-align:center">{n}</a></td>'
        for n in notas
    )
    rotulo = f"{FONTE};font-size:12px;line-height:16px;color:#6b7280;padding:6px {ESPACO_NOTAS}px 0"
    rotulos = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"{centro} '
        f'style="width:100%{limite}"><tr>'
        f'<td width="50%" align="left" valign="top" style="{rotulo};text-align:left">{html.escape(rotulo_min)}</td>'
        f'<td width="50%" align="right" valign="top" style="{rotulo};text-align:right">{html.escape(rotulo_max)}</td>'
        f"</tr></table>"
    )
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="{ESPACO_NOTAS}" border="0"{centro} '
            f'style="width:100%{limite};table-layout:fixed;border-collapse:separate"><tr>{celulas}</tr></table>'
            f"{rotulos}")


def _botao(rotulo: str, link: str, cor: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr>'
        f'<td align="center" bgcolor="{cor}" style="border-radius:6px;background:{cor}">'
        f'<a href="{html.escape(link)}" target="_blank" style="display:inline-block;padding:12px 24px;{FONTE};'
        f'font-size:16px;font-weight:bold;color:{cor_do_texto(cor)};text-decoration:none;border-radius:6px">'
        f"{html.escape(rotulo)}</a></td></tr></table>"
    )


def bloco_da_nota(perguntas: list[dict], link: str, v: dict, cor: str = COR_PADRAO) -> str:
    """NPS → 0–10; CSAT/estrelas → 1–5; personalizado → um botão na cor de destaque."""
    tipo = tipo_principal(perguntas)
    if tipo == "personalizado":
        return _botao("Responder pesquisa", link, cor)
    p = pergunta_principal(perguntas)
    titulo = renderizar(p.get("titulo") or "", v) or ""
    if tipo == "nps":
        rmin, rmax = p.get("rotulo_min") or "Nada provável", p.get("rotulo_max") or "Muito provável"
    else:
        rmin, rmax = p.get("rotulo_min") or "Muito insatisfeito", p.get("rotulo_max") or "Muito satisfeito"
    pergunta = (f'<p style="margin:0 0 12px;{FONTE};font-size:16px;line-height:24px;font-weight:bold;'
                f'color:#111827;text-align:center">{html.escape(titulo)}</p>') if titulo else ""
    return pergunta + _botoes_nota(tipo, link, rmin, rmax)


# ---- cartão -----------------------------------------------------------------------------

def _faixa(cor: str) -> str:
    # 4 px na cor de destaque; os cantos de cima acompanham o arredondado do cartão
    return (f'<tr><td height="4" bgcolor="{cor}" style="height:4px;font-size:4px;line-height:4px;'
            f'mso-line-height-rule:exactly;background:{cor};border-radius:8px 8px 0 0">&nbsp;</td></tr>')


def _cabecalho(logo_url: str | None, empresa: str) -> str:
    if not logo_url:
        return ""
    # height="48" vale no Outlook (que ignora max-height); a largura acompanha a proporção da imagem
    return (
        f'<tr><td align="center" style="padding:{MARGEM}px {MARGEM}px 0">'
        f'<img src="{html.escape(logo_url)}" alt="{html.escape(empresa or "")}" height="48" '
        'style="display:block;height:48px;max-height:48px;width:auto;max-width:100%;border:0;outline:none;'
        f'text-decoration:none;{FONTE};font-size:16px;font-weight:bold;color:#111827"></td></tr>'
    )


ALTURA_MAXIMA_IMAGEM = 2 * LARGURA_IMAGEM


def altura_imagem_topo(largura: int, altura: int) -> int:
    """Altura em px da imagem de topo com 544 de largura (a mesma conta da prévia do site), até 1088."""
    return min(ALTURA_MAXIMA_IMAGEM, max(1, round(LARGURA_IMAGEM * altura / largura)))


def _imagem_topo(imagem: ImagemTopo | None) -> str:
    if imagem is None:
        return ""
    # height="…" (proporcional a 544 de largura) vale no Outlook, que ignora max-width e height:auto; com teto, para
    # uma imagem de proporção absurda (1 × 20000) não virar um atributo de milhões de pixels
    altura = (f' height="{altura_imagem_topo(imagem.largura, imagem.altura)}"'
              if imagem.largura and imagem.altura else "")
    return (
        f'<tr><td style="padding:24px {MARGEM}px 0">'
        f'<img src="{html.escape(imagem.url)}" alt="" width="{LARGURA_IMAGEM}"{altura} '
        'style="display:block;max-width:100%;height:auto;border:0;outline:none;text-decoration:none"></td></tr>'
    )


def _rodape(empresa: str, sair: str, rodape_da_conta: str | None) -> str:
    proprio = (f'<p style="margin:0 0 12px;{FONTE};font-size:12px;line-height:18px;color:#6b7280">'
               f"{_linhas(rodape_da_conta)}</p>") if rodape_da_conta else ""
    return (
        proprio
        + f'<p style="margin:0 0 6px;{FONTE};font-size:12px;line-height:18px;color:#6b7280">'
        f"Você recebeu esta pesquisa porque é cliente de {html.escape(empresa)}.</p>"
        f'<p style="margin:0;{FONTE};font-size:12px;line-height:18px">'
        f'<a href="{html.escape(sair)}" target="_blank" style="color:#6b7280;text-decoration:underline">'
        f"Não quero mais receber pesquisas</a></p>"
    )


def _layout(conteudo: str, empresa: str, sair: str, visual: Visual) -> str:
    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f3f4f6">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f3f4f6">'
        '<tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:600px;background:#ffffff;border-radius:8px">'
        f"{_faixa(visual.cor)}"
        f"{_cabecalho(visual.logo_url, empresa)}"
        f"{_imagem_topo(visual.imagem_topo)}"
        f'<tr><td style="padding:32px {MARGEM}px">{conteudo}{_assinatura(visual.assinatura)}</td></tr>'
        f'<tr><td style="padding:16px {MARGEM}px {MARGEM}px;border-top:1px solid #e5e7eb">'
        f"{_rodape(empresa, sair, visual.rodape)}</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def _cabecalhos(conta_id: int, email: str) -> dict[str, str]:
    return {"List-Unsubscribe": f"<{link_um_clique(conta_id, email)}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


# ---- e-mails ----------------------------------------------------------------------------

def email_pesquisa(*, conta_id: int, para: str, empresa: str, assunto: str, texto: str, perguntas: list[dict],
                   link: str, v: dict, remetente_nome: str | None, responder_para: str | None,
                   visual: Visual | None = None) -> Mensagem:
    """Convite, lembrete ou o e-mail de teste: texto da conta + bloco da nota + assinatura + rodapé com descadastro."""
    visual = visual or Visual()
    sair = link_descadastro(conta_id, para)
    partes = paragrafos(renderizar(texto, v))
    conteudo = "".join(_p(x) for x in partes) + bloco_da_nota(
        perguntas, link, variaveis_formulario(empresa, v["nome"]), visual.cor)
    texto_puro = "\n\n".join(partes + [f"Responda aqui: {link}"] + _extras_texto(visual) + [
        f"Você recebeu esta pesquisa porque é cliente de {empresa}.",
        f"Não quero mais receber pesquisas: {sair}",
    ])
    return Mensagem(para=para, assunto=renderizar(assunto, v), texto=texto_puro,
                    html=_layout(conteudo, empresa, sair, visual), remetente_nome=remetente_nome or empresa,
                    responder_para=responder_para, cabecalhos=_cabecalhos(conta_id, para))


def email_agradecimento(*, conta_id: int, para: str, empresa: str, texto: str, v: dict,
                        remetente_nome: str | None, responder_para: str | None,
                        visual: Visual | None = None) -> Mensagem:
    visual = visual or Visual()
    sair = link_descadastro(conta_id, para)
    partes = paragrafos(renderizar(texto, v))
    texto_puro = "\n\n".join(partes + _extras_texto(visual) + [
        f"Você recebeu esta pesquisa porque é cliente de {empresa}.",
        f"Não quero mais receber pesquisas: {sair}",
    ])
    assunto = f"{empresa} agradece a sua resposta" if empresa else "Obrigado pela sua resposta"
    return Mensagem(para=para, assunto=assunto, texto=texto_puro,
                    html=_layout("".join(_p(x) for x in partes), empresa, sair, visual),
                    remetente_nome=remetente_nome or empresa, responder_para=responder_para,
                    cabecalhos=_cabecalhos(conta_id, para))


def whatsapp(telefone: str, texto: str, v: dict) -> tuple[str, str]:
    """(endereço wa.me com a mensagem pronta, mensagem). Telefone só com dígitos, com DDI 55."""
    numero = telefone if len(telefone) > 11 else "55" + telefone
    mensagem = renderizar(texto, v)
    return f"https://wa.me/{numero}?text={quote(mensagem, safe='')}", mensagem


def link_formulario_publico(codigo: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/f/{codigo}?canal=link"
