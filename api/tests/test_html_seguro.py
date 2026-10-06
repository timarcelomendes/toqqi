"""Etapa 5l (docs/api-etapa-5l.md §3): HTML dos blocos de conteúdo e dos finais — lista permitida (nh3), cada tipo de
ataque removido, `target`/`rel` forçados nos links, imagens só da plataforma, `style` só com `text-align`, tamanho,
`renderizar_html` (variáveis escapadas, espaços e citações intactos) e `renderizar` sem estragar as citações."""
import pytest

from toqqi.core import html_seguro
from toqqi.core.html_seguro import limpar_html, renderizar_html, sem_conteudo
from toqqi.modulos.imagens.servico import prefixo_publico
from toqqi.modulos.respostas.registro import renderizar, variaveis

REL = 'target="_blank" rel="noopener noreferrer nofollow ugc"'
CHAVE = "a" * 43


def _img() -> str:
    return prefixo_publico() + CHAVE


def test_lista_permitida_fica_como_esta():
    html = ("<h2>Título</h2><h3>Sub</h3><h4>Menor</h4><p><strong>forte</strong> <b>b</b> <em>em</em> <i>i</i> "
            "<u>u</u> <s>s</s> <small>p</small> <sub>2</sub> <sup>3</sup> <code>x</code></p><pre>  a\n   b</pre>"
            "<ul><li>um</li></ul><ol><li>dois</li></ol><blockquote>citação</blockquote><hr><p>a<br>b</p>"
            "<div><span>s</span></div><figure><figcaption>legenda</figcaption></figure>"
            "<table><caption>c</caption><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>")
    assert limpar_html(html) == html


@pytest.mark.parametrize("ataque,esperado", [
    ("<script>alert(1)</script><p>ok</p>", "<p>ok</p>"),
    ("<p onclick=\"alert(1)\" onmouseover='x()'>ok</p>", "<p>ok</p>"),
    ('<a href="javascript:alert(1)">x</a>', f"<a {REL}>x</a>"),
    ('<a href="JaVaScRiPt:alert(1)">x</a>', f"<a {REL}>x</a>"),
    ('<a href="java&#x09;script:alert(1)">x</a>', f"<a {REL}>x</a>"),
    ('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>', f"<a {REL}>x</a>"),
    ('<a href="/configuracoes">relativo</a>', f"<a {REL}>relativo</a>"),
    ('<img src="data:image/png;base64,iVBORw0KGgo=">', ""),
    ('<p style="color: red; position: fixed; background: url(javascript:x)">ok</p>', "<p>ok</p>"),
    ('<p style="text-align: center; color: red">ok</p>', '<p style="text-align: center">ok</p>'),
    ('<p style="text-align: expression(alert(1))">ok</p>', "<p>ok</p>"),
    ('<span style="text-align: center">ok</span>', "<span>ok</span>"),  # style só em p, h2–h4, div, td, th
    ('<iframe src="https://evil.com">alt</iframe><p>ok</p>', "<p>ok</p>"),
    ("<svg onload=alert(1)><script>alert(1)</script><text>t</text></svg><p>ok</p>", "<p>ok</p>"),
    ("<math><mi>x</mi></math><p>ok</p>", "<p>ok</p>"),
    ('<img src="https://evil.com/pixel.png"><p>ok</p>', "<p>ok</p>"),
    ('<p class="x" id="y" name="z" data-x="1">ok</p>', "<p>ok</p>"),
    ("<style>p{color:red}</style><p>ok</p>", "<p>ok</p>"),
    ('<object data="x.swf">alt</object><embed src="x"><p>ok</p>', "<p>ok</p>"),
    ('<form action="https://evil.com"><input name="senha"><button>Enviar</button></form>', "Enviar"),
    ('<video src="x.mp4">v</video><audio src="x.mp3">a</audio><p>ok</p>', "<p>ok</p>"),
    ('<meta http-equiv="refresh" content="0;url=https://evil.com"><link rel="stylesheet" href="x">'
     '<base href="https://evil.com"><p>ok</p>', "<p>ok</p>"),
    ("<!-- comentário --><p>ok</p>", "<p>ok</p>"),
    ("<template><p>x</p></template><noscript><p>y</p></noscript><p>ok</p>", "<p>ok</p>"),
    ("<p>\x01ok\x07</p>", "<p>ok</p>"),
    ("<details><summary>a</summary>b</details>", "ab"),
])
def test_ataques_removidos(ataque, esperado):
    assert limpar_html(ataque) == esperado


def test_links_com_target_e_rel_forcados():
    assert limpar_html('<a href="https://site.com" target="_self" rel="opener" title="t">x</a>') == (
        f'<a href="https://site.com" title="t" {REL}>x</a>')
    assert limpar_html('<a href="mailto:a@b.com">m</a><a href="tel:+551140001234">t</a>') == (
        f'<a href="mailto:a@b.com" {REL}>m</a><a href="tel:+551140001234" {REL}>t</a>')


def test_imagens_so_da_plataforma():
    assert limpar_html(f'<img src="{_img()}" alt="logo" width="320" height="0090">') == (
        f'<img src="{_img()}" alt="logo" width="320" height="90">')
    # largura fora de 1–2000 cai (a imagem fica)
    assert limpar_html(f'<img src="{_img()}" width="5000" height="-1">') == f'<img src="{_img()}">'
    # chave curta, com consulta, outro caminho ou outro site: a imagem sai inteira
    for src in (prefixo_publico() + "curta", _img() + "?x=1", _img().replace("/imagens/", "/outra/"),
                "https://cdn.com/" + CHAVE, "//cdn.com/x.png"):
        assert limpar_html(f'<p>a</p><img src="{src}" alt="x"><p>b</p>') == "<p>a</p><p>b</p>", src
    # o `>` dentro do alt não confunde a retirada
    assert limpar_html(f'<img alt="a > b" src="{_img()}">') == f'<img alt="a &gt; b" src="{_img()}">'
    # prefixo informado (o do site, por exemplo)
    assert limpar_html('<img src="https://x.com/i/' + CHAVE + '">', "https://x.com/i/") == (
        '<img src="https://x.com/i/' + CHAVE + '">')


def test_tabelas_colspan_rowspan_e_alinhamento():
    html = ('<table><tbody><tr><td colspan="2" rowspan="21" style="text-align:LEFT">a</td>'
            '<th style="TEXT-ALIGN: right; text-align: justify">b</th></tr></tbody></table>')
    assert limpar_html(html) == ('<table><tbody><tr><td colspan="2" style="text-align: left">a</td>'
                                 '<th style="text-align: justify">b</th></tr></tbody></table>')


def test_limpar_de_novo_nao_muda_e_vazio():
    sujo = ('<p style="text-align:center" onclick="x">Oi <a href="https://a.com">a</a> {{p_abc123}} {empresa} &amp; '
            "&lt;</p><script>x</script>")
    limpo = limpar_html(sujo)
    assert limpar_html(limpo) == limpo
    assert "{{p_abc123}}" in limpo and "{empresa}" in limpo
    assert limpar_html("") == "" and limpar_html(None) == ""
    assert sem_conteudo("<p></p>") and sem_conteudo("<p>&nbsp; </p><p><br></p>") and sem_conteudo("")
    assert not sem_conteudo("<p>x</p>") and not sem_conteudo("<hr>") and not sem_conteudo(f'<img src="{_img()}">')


def test_tamanhos():
    assert html_seguro.MAX_ENTRADA == 50_000 and html_seguro.MAX_HTML == 20_000
    assert html_seguro.MSG_GRANDE == "Este conteúdo está grande demais (máx. 20.000 caracteres)."


# ---- variáveis e citações -----------------------------------------------------------------

def test_renderizar_html_escapa_e_nao_junta_espacos():
    v = {"empresa": "Alfa & <Cia>", "nome": "Ana", "assunto": "o pedido", "referencia": '"x" onclick="y"'}
    assert renderizar_html("<p>A {empresa}  e   {{p_abc123}}</p>", v) == (
        "<p>A Alfa &amp; &lt;Cia&gt;  e   {{p_abc123}}</p>")
    assert renderizar_html('<a href="https://loja.com/{referencia}" title="{referencia}">{assunto}</a>', v) == (
        '<a href="https://loja.com/&quot;x&quot; onclick=&quot;y&quot;" '
        'title="&quot;x&quot; onclick=&quot;y&quot;">o pedido</a>')
    # citação com o nome de uma variável continua citação
    assert renderizar_html("<p>{{empresa}} {{nome}}</p>", v) == "<p>{{empresa}} {{nome}}</p>"


def test_renderizar_html_com_variavel_vazia():
    v = variaveis("Alfa")
    assert renderizar_html("<p>Olá, {nome}!</p>", v) == "<p>Olá!</p>"
    assert renderizar_html("<p>{nome}, tudo bem?</p>", v) == "<p>Tudo bem?</p>"
    assert renderizar_html("<p>Pedido {referencia}.</p>", v) == "<p>Pedido.</p>"
    assert renderizar_html("<p>{nome}, {{p1}}</p>", v) == "<p>{{p1}}</p>"
    assert renderizar_html("", v) == "" and renderizar_html("<p>sem chaves</p>", v) == "<p>sem chaves</p>"


@pytest.mark.parametrize("texto,esperado", [
    ("Você deu {{p_abc123}}. Por quê?", "Você deu {{p_abc123}}. Por quê?"),
    ("Olá, {nome}! {{nome}}", "Olá! {{nome}}"),
    ("{{empresa}} e {empresa}", "{{empresa}} e Alfa"),
    ("Pedido {referencia}:   {{p1}}", "Pedido: {{p1}}"),
    ("{nome}, {{p1}} foi a nota", "{{p1}} foi a nota"),
])
def test_renderizar_nao_estraga_citacoes(texto, esperado):
    assert renderizar(texto, variaveis("Alfa")) == esperado


def test_valor_da_variavel_nao_vira_citacao():
    """O valor de uma variável (a referência vem do link público) não consegue montar uma citação."""
    v = {**variaveis("Alfa"), "referencia": "#0# {{p1}}"}
    assert renderizar("Pedido {referencia} e {{p2}}", v) == "Pedido #0# {{p1}} e {{p2}}"
    assert renderizar_html("<p>{referencia} {{p2}}</p>", v) == "<p>#0# {{p1}} {{p2}}</p>"
