"""Relatório mensal em PDF (pedido do Marcelo em 10/11/2026): o resumo de um mês para o dono da empresa, com os
mesmos números do painel (`painel.servico.painel` com o mês como período, só empresas ativas, todos os grupos).

- `GET /relatorios/mensal.pdf?mes=AAAA-MM` (permissão `relatorios.ver`): baixa o PDF de qualquer mês até o atual
  (sem `mes`: o mês anterior). O mês atual sai "até hoje".
- Tarefa `mensal`: no dia 1, a partir das 8h de Brasília (se não rodar no dia 1, até o dia 3; depois o mês é pulado),
  manda o PDF do mês anterior por e-mail a quem acompanha o painel e deixou "Relatório mensal" ligado em Minha conta
  (`emails.destinatarios`). Uma vez por conta e mês (`relatorios_mensais`, gravado antes de enviar; o UNIQUE impede
  duplicar). Pula a conta sem nenhuma resposta (NPS ou CSAT) no mês. Só conta liberada e provedor de e-mail real.

O PDF usa as fontes padrão do PDF (Helvetica): o texto dos clientes passa por `_seguro`, que tira o que a fonte não
desenha (emojis etc.). Os planos de ação e a receita em risco são a situação no dia em que o PDF foi gerado (como
no painel)."""
import io
import logging
import re
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from toqqi.core import email, relogio
from toqqi.core.db import em_conta
from toqqi.core.errors import AppError
from toqqi.modelos import Conta, RelatorioMensal
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.envios.configuracao import provedor_ok
from toqqi.modulos.painel import servico as painel_servico
from toqqi.modulos.painel.resumo_ia import reais
from toqqi.modulos.relatorios.emails import _contas_em_dia, _url, destinatarios, rodape
from toqqi.modulos.relatorios.regras import ROTULOS_FAIXA_NPS

log = logging.getLogger("toqqi.relatorios")

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")
MESES_CURTOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
ENVIO_A_PARTIR = time(8, 0)
DIAS_PARA_ENVIAR = 3  # dia 1 a 3
MAX_COMENTARIOS = 6
MAX_TEXTO = 280
MAX_EMPRESAS_ATENCAO = 8

# cores (as do site: texto slate, coral da marca só nos destaques, verde/âmbar/vermelho do NPS)
TINTA = colors.HexColor("#0F172A")
SUAVE = colors.HexColor("#475569")
FRACO = colors.HexColor("#64748B")
BORDA = colors.HexColor("#E2E8F0")
FUNDO = colors.HexColor("#F8FAFC")
CORAL = colors.HexColor("#D63A18")
VERDE = colors.HexColor("#059669")
AMBAR = colors.HexColor("#D97706")
VERMELHO = colors.HexColor("#DC2626")


# ---- o mês ------------------------------------------------------------------------------------

def _mes_seguinte(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def mes_anterior(hoje: date) -> date:
    primeiro = date(hoje.year, hoje.month, 1)
    anterior = primeiro - timedelta(days=1)
    return date(anterior.year, anterior.month, 1)


def ler_mes(texto: str | None) -> date:
    """"AAAA-MM" → o dia 1 do mês (sem texto: o mês anterior). 422 para formato inválido, mês futuro ou antes de 2000."""
    hoje = relogio.hoje()
    if not texto:
        return mes_anterior(hoje)
    m = re.fullmatch(r"(\d{4})-(\d{2})", texto.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise AppError(422, "dados_invalidos", "Confira o mês.", {"mes": "Use o formato AAAA-MM, ex.: 2026-10."})
    inicio = date(int(m.group(1)), int(m.group(2)), 1)
    if inicio.year < 2000 or inicio > date(hoje.year, hoje.month, 1):
        raise AppError(422, "dados_invalidos", "Confira o mês.", {"mes": "Escolha um mês entre 2000 e o mês atual."})
    return inicio


def nome_mes(inicio: date) -> str:
    return f"{MESES[inicio.month - 1]} de {inicio.year}"


def nome_arquivo(inicio: date) -> str:
    return f"toqqi-relatorio-{inicio:%Y-%m}.pdf"


def dados_do_mes(conta_id: int, inicio: date) -> tuple[dict, date]:
    """Os números do painel no mês (o mês atual vai até hoje). Devolve (painel, último dia)."""
    fim = min(_mes_seguinte(inicio) - timedelta(days=1), relogio.hoje())
    ctx = SimpleNamespace(conta_id=conta_id)
    return painel_servico.painel(ctx, inicio, fim, None, True), fim


# ---- texto ------------------------------------------------------------------------------------

def _seguro(texto, limite: int | None = None) -> str:
    """Texto pronto para um Paragraph com Helvetica: sem o que a fonte não desenha (cp1252), espaços juntados,
    cortado em `limite` com reticências e com &, < e > escapados."""
    t = str(texto or "").encode("cp1252", "ignore").decode("cp1252")
    t = " ".join(t.split())
    if limite and len(t) > limite:
        t = t[: limite - 1].rstrip() + "…"
    return escape(t)


def _n(v) -> str:
    return f"{int(v):,}".replace(",", ".")


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",").removesuffix(",0") + "%"


def _sinal(v: int) -> str:
    return f"+{v}" if v > 0 else str(v)


def _cor_nps(v) -> colors.Color:
    if v is None:
        return FRACO
    if v >= 50:
        return VERDE
    if v >= 0:
        return AMBAR
    return VERMELHO


def _quem(item: dict) -> str:
    empresa = (item.get("empresa") or {}).get("nome")
    contato = (item.get("contato") or {}).get("nome")
    if empresa and contato:
        return f"{empresa} ({contato})"
    return empresa or contato or "Cliente sem cadastro"


# ---- PDF --------------------------------------------------------------------------------------

def _estilos() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=TINTA, alignment=TA_LEFT)
    return {
        "base": base,
        "suave": ParagraphStyle("suave", parent=base, textColor=SUAVE),
        "fraco": ParagraphStyle("fraco", parent=base, fontSize=8.5, leading=12, textColor=FRACO),
        "titulo": ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=26),
        "marca": ParagraphStyle("marca", parent=base, fontName="Helvetica-Bold", fontSize=11, textColor=CORAL),
        "secao": ParagraphStyle("secao", parent=base, fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                                spaceBefore=14, spaceAfter=6),
        "rotulo": ParagraphStyle("rotulo", parent=base, fontSize=8.5, leading=11, textColor=SUAVE),
        "numero": ParagraphStyle("numero", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22),
        "celula": ParagraphStyle("celula", parent=base, fontSize=9, leading=12),
        "celula_b": ParagraphStyle("celula_b", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=12),
    }


def _tabela(linhas: list[list], larguras: list[float], cabecalho: bool = True) -> Table:
    t = Table(linhas, colWidths=larguras, repeatRows=1 if cabecalho else 0, hAlign="LEFT")
    estilo = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 0),
              ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDA)]
    if cabecalho:
        estilo.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, SUAVE))
    t.setStyle(TableStyle(estilo))
    return t


def _cartoes(itens: list[tuple[str, str, str, colors.Color]], largura: float, e: dict) -> Table:
    """A linha de indicadores: (rótulo, número, detalhe, cor do número)."""
    celulas = []
    cabe = largura / len(itens) - 20
    for rotulo, numero, detalhe, cor in itens:
        tamanho = e["numero"].fontSize  # diminui até o número caber numa linha (ex.: receita em milhões)
        while tamanho > 10 and stringWidth(numero.replace("&nbsp;", " "), "Helvetica-Bold", tamanho) > cabe:
            tamanho -= 1
        estilo_n = ParagraphStyle("n", parent=e["numero"], textColor=cor, fontSize=tamanho, leading=22)
        celulas.append([Paragraph(_seguro(rotulo), e["rotulo"]), Paragraph(numero, estilo_n),
                        Paragraph(detalhe, e["fraco"])])
    t = Table([celulas], colWidths=[largura / len(itens)] * len(itens), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDA), ("INNERGRID", (0, 0), (-1, -1), 0.6, BORDA),
        ("BACKGROUND", (0, 0), (-1, -1), FUNDO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9)]))
    return t


def _barra_grupos(nps: dict, largura: float) -> Drawing:
    """Barra única promotores / neutros / detratores, com 2 pt de espaço entre as partes."""
    d = Drawing(largura, 12)
    total = nps["total"] or 0
    if not total:
        d.add(Rect(0, 2, largura, 8, fillColor=BORDA, strokeColor=None))
        return d
    x = 0.0
    partes = [(nps["promotores"], VERDE), (nps["neutros"], AMBAR), (nps["detratores"], VERMELHO)]
    visiveis = [(n, c) for n, c in partes if n]
    livre = largura - 2 * (len(visiveis) - 1)
    for i, (n, cor) in enumerate(visiveis):
        w = livre * n / total
        d.add(Rect(x, 2, w, 8, fillColor=cor, strokeColor=None))
        x += w + (2 if i < len(visiveis) - 1 else 0)
    return d


def _grafico_12m(itens: list[dict], largura: float) -> Drawing:
    """NPS dos 12 meses: barras a partir do zero (para cima ou para baixo), o número em cima e o mês embaixo."""
    altura, topo, base_rotulo = 120, 14, 14
    d = Drawing(largura, altura)
    zona = altura - topo - base_rotulo
    valores = [it["nps"] for it in itens if it["nps"] is not None]
    teto = max([abs(v) for v in valores] + [25])  # a maior barra ocupa a altura (mínimo: 25 pontos)
    negativos = any(v < 0 for v in valores)
    zero = base_rotulo + (zona / 2 if negativos else 10)
    escala = ((zona / 2 if negativos else zona - 10) - 6) / teto
    d.add(Line(0, zero, largura, zero, strokeColor=BORDA, strokeWidth=0.8))
    passo = largura / max(len(itens), 1)
    barra = min(18, passo * 0.55)
    for i, it in enumerate(itens):
        cx = passo * i + passo / 2
        ano, mes = (int(x) for x in it["mes"].split("-"))
        rotulo = MESES_CURTOS[mes - 1] + (f"/{str(ano)[2:]}" if mes == 1 or i == 0 else "")
        d.add(String(cx, 2, rotulo, fontName="Helvetica", fontSize=7, fillColor=FRACO, textAnchor="middle"))
        v = it["nps"]
        if v is None:
            d.add(String(cx, zero + 3, "—", fontName="Helvetica", fontSize=7, fillColor=FRACO, textAnchor="middle"))
            continue
        h = max(abs(v) * escala, 1.5)
        y = zero if v >= 0 else zero - h
        cor = CORAL if it.get("no_periodo") else colors.HexColor("#CBD5E1")
        d.add(Rect(cx - barra / 2, y, barra, h, fillColor=cor, strokeColor=None, rx=2, ry=2))
        ty = zero + h + 2 if v >= 0 else zero - h - 8
        d.add(String(cx, ty, str(v), fontName="Helvetica-Bold" if it.get("no_periodo") else "Helvetica", fontSize=7,
                     fillColor=TINTA if it.get("no_periodo") else SUAVE, textAnchor="middle"))
    return d


def gerar_pdf(conta_nome: str, inicio: date, fim: date, p: dict) -> bytes:
    e = _estilos()
    buf = io.BytesIO()
    titulo_mes = nome_mes(inicio)
    gerado = relogio.agora()

    def rodape_pagina(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(FRACO)
        canvas.drawString(18 * mm, 10 * mm, f"Toqqi · {conta_nome[:60]} · relatório de {titulo_mes}"
                          .encode("cp1252", "ignore").decode("cp1252"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=f"Relatório de {titulo_mes}", author="Toqqi",
                            subject=conta_nome)
    largura = A4[0] - 36 * mm
    nps, csat, taxa, atencao = p["nps"], p["csat"], p["taxa_resposta"], p["atencao"]
    hist: list = []

    # cabeçalho
    hist.append(Paragraph("toqqi", e["marca"]))
    hist.append(Spacer(1, 4))
    hist.append(Paragraph(f"Relatório de {_seguro(titulo_mes)}", e["titulo"]))
    ate_hoje = fim < _mes_seguinte(inicio) - timedelta(days=1)
    periodo = f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" + (" (mês em andamento)" if ate_hoje else "")
    hist.append(Paragraph(f"{_seguro(conta_nome)} · {periodo}", e["suave"]))
    hist.append(Spacer(1, 12))

    # indicadores
    variacao = p.get("variacao")
    if nps["valor"] is None:
        detalhe_nps = "Nenhuma resposta de NPS no mês."
    else:
        detalhe_nps = ROTULOS_FAIXA_NPS[nps["faixa"]]
        if variacao:
            detalhe_nps += f" · {_sinal(variacao['valor'])} sobre o mês anterior ({variacao['anterior']})"
    total_respostas = nps["total"] + csat["total"]
    detalhe_resp = f"{_n(nps['total'])} de NPS" + (f" e {_n(csat['total'])} de CSAT" if csat["total"] else "")
    detalhe_taxa = (f"{_n(taxa['responderam'])} de {_n(taxa['convidados'])} convidados" if taxa["convidados"]
                    else "Nenhum convite saiu no mês.")
    risco = atencao["receita_em_risco"]
    detalhe_risco = (f"{_n(risco['empresas'])} empresa{'s' if risco['empresas'] != 1 else ''} com detrator"
                     if risco["empresas"] else "Nenhuma empresa com detrator.")
    hist.append(_cartoes([
        ("NPS do mês", "—" if nps["valor"] is None else str(nps["valor"]), detalhe_nps, _cor_nps(nps["valor"])),
        ("Respostas", _n(total_respostas), detalhe_resp, TINTA),
        ("Taxa de resposta", _pct(taxa["percentual"]), detalhe_taxa, TINTA),
        ("Receita em risco", reais(risco["valor"]).replace(" ", "&nbsp;"), detalhe_risco, VERMELHO if risco["valor"] else TINTA),
    ], largura, e))

    # como avaliaram
    if nps["total"]:
        hist.append(Paragraph("Como os clientes avaliaram", e["secao"]))
        hist.append(_barra_grupos(nps, largura))
        hist.append(Spacer(1, 3))
        pct = nps["pct"]
        hist.append(Paragraph(
            f'<font color="#059669"><b>{_n(nps["promotores"])} promotores</b></font> ({_pct(pct["promotores"])}) · '
            f'<font color="#B45309"><b>{_n(nps["neutros"])} neutros</b></font> ({_pct(pct["neutros"])}) · '
            f'<font color="#DC2626"><b>{_n(nps["detratores"])} detratores</b></font> ({_pct(pct["detratores"])})',
            e["base"]))
        mov = p["movimentacao"]
        frases = []
        if mov["resgatados"]:
            n = mov["resgatados"]
            frases.append("1 cliente passou de detrator a promotor" if n == 1
                          else f"{_n(n)} clientes passaram de detrator a promotor")
        if mov["deixaram_de_ser_promotores"]:
            n = mov["deixaram_de_ser_promotores"]
            frases.append(f"{_n(n)} cliente deixou de ser promotor" if n == 1
                          else f"{_n(n)} clientes deixaram de ser promotores")
        if frases:
            hist.append(Spacer(1, 3))
            hist.append(Paragraph(_seguro("; ".join(frases) + "."), e["suave"]))
    if csat["total"]:
        hist.append(Spacer(1, 4))
        hist.append(Paragraph(
            f"<b>CSAT:</b> {_pct(csat['percentual'])} de satisfeitos ({_n(csat['satisfeitos'])} de "
            f"{_n(csat['total'])}), média {str(csat['media']).replace('.', ',') if csat['media'] is not None else '—'}"
            " de 5.", e["base"]))

    # 12 meses
    hist.append(KeepTogether([Paragraph("NPS nos últimos 12 meses", e["secao"]), _grafico_12m(p["evolucao_12m"], largura)]))

    # temas
    temas = p["temas"]
    if temas:
        linhas = [[Paragraph("<b>Tema</b>", e["celula"]), Paragraph("<b>Menções</b>", e["celula"]),
                   Paragraph("<b>Reclamações</b>", e["celula"]), Paragraph("<b>Nota média</b>", e["celula"]),
                   Paragraph("<b>Mês anterior</b>", e["celula"])]]
        for t in temas:
            var = t.get("variacao")
            linhas.append([Paragraph(_seguro(t["rotulo"]), e["celula"]), Paragraph(_n(t["mencoes"]), e["celula"]),
                           Paragraph(_n(t["reclamacoes"]), e["celula"]),
                           Paragraph(str(t["nota_media"]).replace(".", ",") if t["nota_media"] is not None else "—",
                                     e["celula"]),
                           Paragraph("—" if var is None else (f"{_sinal(var)} menções" if var else "igual"),
                                     e["celula"])])
        hist.append(KeepTogether([Paragraph("O que mais citaram", e["secao"]),
                                  _tabela(linhas, [largura * x for x in (0.34, 0.15, 0.17, 0.15, 0.19)])]))

    # empresas
    empresas = p["empresas"]
    if empresas["menor"] or empresas["maior"]:
        def _lista(itens):
            linhas = [[Paragraph("<b>Empresa</b>", e["celula"]), Paragraph("<b>NPS</b>", e["celula"]),
                       Paragraph("<b>Respostas</b>", e["celula"])]]
            for x in itens:
                linhas.append([Paragraph(_seguro(x["empresa"]["nome"], 60), e["celula"]),
                               Paragraph(f'<font color="{_cor_nps(x["nps"]).hexval().replace("0x", "#")}">'
                                         f'<b>{x["nps"]}</b></font>', e["celula"]),
                               Paragraph(_n(x["respostas"]), e["celula"])])
            return _tabela(linhas, [largura * 0.30, largura * 0.08, largura * 0.11])
        lado = Table([[Paragraph("<b>Menor NPS</b>", e["suave"]), Paragraph("<b>Maior NPS</b>", e["suave"])],
                      [_lista(empresas["menor"]) if empresas["menor"] else Paragraph("—", e["fraco"]),
                       _lista(empresas["maior"]) if empresas["maior"] else Paragraph("—", e["fraco"])]],
                     colWidths=[largura / 2, largura / 2], hAlign="LEFT")
        lado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        hist.append(KeepTogether([Paragraph("Empresas com 3 ou mais respostas", e["secao"]), lado]))

    # planos de ação
    bloco: list = [Paragraph(f"Planos de ação (situação em {gerado:%d/%m/%Y})", e["secao"])]
    if atencao["tudo_em_dia"]:
        texto = "Nenhum plano de ação aberto."
    else:
        texto = (f"<b>{_n(atencao['acoes_abertas'])}</b> plano{'s' if atencao['acoes_abertas'] != 1 else ''} aberto"
                 f"{'s' if atencao['acoes_abertas'] != 1 else ''}"
                 + (f", <font color='#DC2626'><b>{_n(atencao['acoes_vencidas'])} vencido"
                    f"{'s' if atencao['acoes_vencidas'] != 1 else ''}</b></font>" if atencao["acoes_vencidas"] else "")
                 + ".")
    sem_plano = atencao.get("detratores_sem_plano") or 0
    if sem_plano:
        texto += (f" {_n(sem_plano)} cliente{'s' if sem_plano != 1 else ''} com detrator no mês ainda sem plano de ação.")
    bloco.append(Paragraph(texto, e["base"]))
    if atencao["empresas"]:
        linhas = [[Paragraph("<b>Empresa</b>", e["celula"]), Paragraph("<b>Abertos</b>", e["celula"]),
                   Paragraph("<b>Vencidos</b>", e["celula"]), Paragraph("<b>Responsável</b>", e["celula"])]]
        for x in atencao["empresas"][:MAX_EMPRESAS_ATENCAO]:
            linhas.append([Paragraph(_seguro(x["empresa"]["nome"], 60), e["celula"]),
                           Paragraph(_n(x["acoes_abertas"]), e["celula"]),
                           Paragraph(_n(x["acoes_vencidas"]) if x["acoes_vencidas"] else "—", e["celula"]),
                           Paragraph(_seguro((x.get("responsavel") or {}).get("nome") or "Sem responsável", 40),
                                     e["celula"])])
        bloco += [Spacer(1, 4), _tabela(linhas, [largura * x for x in (0.46, 0.14, 0.14, 0.26)])]
    hist.append(KeepTogether(bloco))

    # comentários
    # detratores e insatisfeitos primeiro (o que pede ação), depois os mais recentes (a ordem do painel)
    comentarios = sorted(p["comentarios"], key=lambda c: c.get("grupo") not in ("detrator", "insatisfeito"))[:MAX_COMENTARIOS]
    if comentarios:
        hist.append(Paragraph("O que disseram", e["secao"]))
        for c in comentarios:
            nota = f"nota {c['nota']}" if c.get("nota") is not None else ""
            cabeca = f"<b>{_seguro(_quem(c), 80)}</b>" + (f" · {nota}" if nota else "") + \
                     (f" · {c['data']:%d/%m}" if isinstance(c.get("data"), (date, datetime)) else "")
            hist.append(KeepTogether([Paragraph(cabeca, e["celula"]),
                                      Paragraph(f"“{_seguro(c['comentario'], MAX_TEXTO)}”", e["suave"]),
                                      Spacer(1, 6)]))

    hist.append(Spacer(1, 10))
    hist.append(Paragraph(f"Gerado pelo Toqqi em {gerado:%d/%m/%Y às %H:%M}. Os números são os do painel com o mês como "
                          "período, só empresas ativas.", e["fraco"]))
    doc.build(hist, onFirstPage=rodape_pagina, onLaterPages=rodape_pagina)
    return buf.getvalue()


def pdf_da_conta(conta_id: int, inicio: date) -> bytes:
    with em_conta(conta_id) as s:
        conta_nome = s.get(Conta, conta_id).nome
    p, fim = dados_do_mes(conta_id, inicio)
    return gerar_pdf(conta_nome, inicio, fim, p)


# ---- e-mail do dia 1 ------------------------------------------------------------------------------

def mes_a_enviar(agora: datetime) -> date | None:
    """O mês anterior, se é dia 1 depois das 8h ou dia 2 ou 3; senão None."""
    dia = agora.date()
    if (dia.day == 1 and agora.time() >= ENVIO_A_PARTIR) or 1 < dia.day <= DIAS_PARA_ENVIAR:
        return mes_anterior(dia)
    return None


def enviar_conta(conta_id: int, inicio: date) -> dict | None:
    """Gera, registra (uma vez por mês) e manda o PDF da conta. None se não era o caso."""
    with em_conta(conta_id) as s:
        conta = s.get(Conta, conta_id)
        if conta is None or not liberada(conta):
            return None
        conta_nome = conta.nome
    p, fim = dados_do_mes(conta_id, inicio)
    if not (p["nps"]["total"] or p["csat"]["total"]):
        return None  # mês sem respostas: nada a relatar
    with em_conta(conta_id) as s:
        relatorio_id = s.scalar(insert(RelatorioMensal).values(conta_id=conta_id, mes=inicio)
                                .on_conflict_do_nothing(index_elements=[RelatorioMensal.conta_id, RelatorioMensal.mes])
                                .returning(RelatorioMensal.id))
        if relatorio_id is None:
            return None  # já saiu neste mês
        para = destinatarios(s, "recebe_relatorio_mensal")
    conteudo = gerar_pdf(conta_nome, inicio, fim, p)
    titulo = nome_mes(inicio)
    nps = p["nps"]["valor"]
    assunto = f"Relatório de {titulo}" + (f": NPS {nps}" if nps is not None else "")
    paragrafos = [f"Segue em anexo o relatório de {titulo} da {conta_nome}: NPS, respostas, temas, empresas, planos "
                  "de ação e o que os clientes disseram.",
                  "Dá para baixar o de qualquer mês em Relatórios, no Toqqi."]
    anexo = email.Anexo(nome_arquivo(inicio), "application/pdf", conteudo)
    texto_rodape = rodape(conta_nome)
    for destino in para:  # depois do commit: o relatório já está registrado
        email.enviar(destino, assunto, paragrafos, ("Abrir os relatórios", _url("/relatorios")), texto_rodape,
                     conta_id=conta_id, tipo="relatorio_mensal", anexos=[anexo])
    with em_conta(conta_id) as s:
        s.execute(update(RelatorioMensal).where(RelatorioMensal.id == relatorio_id)
                  .values(enviado_em=relogio.agora(), destinatarios=len(para)))
    return {"emails": len(para)}


def executar() -> dict:
    """Tarefa `mensal`. Devolve {contas, emails}."""
    total = {"contas": 0, "emails": 0}
    inicio = mes_a_enviar(relogio.agora())
    if inicio is None or not provedor_ok():
        return total
    for conta_id in _contas_em_dia():
        try:
            r = enviar_conta(conta_id, inicio)
        except Exception:  # noqa: BLE001 - uma conta não derruba as outras
            log.exception("Falha no relatório mensal da conta %s", conta_id)
            continue
        if r is not None:
            total["contas"] += 1
            total["emails"] += r["emails"]
    return total
