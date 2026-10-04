"""Etapa 5b: Ajuda — validação do conteúdo (exemplo e arquivo real), GET /ajuda e a busca usada pelo assistente."""
import copy
import json
import logging

import pytest
from util import AJUDA_EXEMPLO, API, conta_pronta, membro

from toqqi.modulos.ajuda import servico as ajuda


@pytest.fixture
def exemplo(monkeypatch) -> dict:
    """A Ajuda de exemplo no lugar do conteudo.json (que é de outro agente e pode ainda não existir)."""
    monkeypatch.setattr(ajuda, "CAMINHO", AJUDA_EXEMPLO)
    ajuda.limpar_cache()
    return json.loads(AJUDA_EXEMPLO.read_text(encoding="utf-8"))


# ---- validação -------------------------------------------------------------------------------

def test_exemplo_e_valido(exemplo):
    assert ajuda.validar(exemplo) == []


def _secao(dados: dict, topico: int = 0, secao: int = 0) -> dict:
    return dados["topicos"][topico]["secoes"][secao]


@pytest.mark.parametrize("estragar,trecho", [
    (lambda d: d["topicos"][1].update(id="contatos"), "id repetido"),
    (lambda d: d["topicos"][0].update(id="Contatos_X"), "kebab-case"),
    (lambda d: _secao(d, 0, 1).update(id="importar-planilha"), "id repetido no tópico"),
    (lambda d: _secao(d).update(id="importar planilha"), "kebab-case"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "video", "texto": "x"}), "tipo de bloco"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "passos", "itens": []}), "sem itens"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "dica", "texto": "x", "itens": ["y"]}), "leva só"),
    (lambda d: _secao(d).update(atalho="painel_secreto"), "atalho desconhecido"),
    (lambda d: _secao(d).update(titulo="  "), "texto vazio"),
    (lambda d: d["topicos"][0].update(resumo=""), "texto vazio"),
    (lambda d: _secao(d)["palavras"].append(""), "texto vazio"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "paragrafo", "texto": "Veja <b>isto</b>"}), "'<'"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "paragrafo", "texto": "Acesse HTTPS://toqqi.com"}), "'http'"),
    (lambda d: _secao(d)["blocos"].append({"tipo": "lista", "itens": ["Veja www.toqqi.com"]}), "'www.'"),
    (lambda d: _secao(d).update(titulo="**Importar**"), "'**'"),
    (lambda d: _secao(d).update(somente_admin="não"), "somente_admin"),
    (lambda d: _secao(d).pop("palavras"), "faltam os campos palavras"),
    (lambda d: d["topicos"][0].update(icone="x"), "campos desconhecidos icone"),
    (lambda d: d["topicos"][0].update(secoes=[]), "sem seções"),
    (lambda d: _secao(d).update(blocos=[]), "sem blocos"),
    (lambda d: d.update(versao="1"), "versao"),
    (lambda d: d.update(topicos=[]), "lista vazia"),
])
def test_validacao_aponta_os_problemas(exemplo, estragar, trecho):
    dados = copy.deepcopy(exemplo)
    estragar(dados)
    erros = ajuda.validar(dados)
    assert any(trecho in e for e in erros), erros


def test_conteudo_real_valido():
    """O conteudo.json de verdade (escrito à parte): formato, regras de texto e os tópicos na ordem combinada."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    dados = json.loads(ajuda.CAMINHO.read_text(encoding="utf-8"))
    assert ajuda.validar(dados) == []
    assert [t["id"] for t in dados["topicos"]] == list(ajuda.TOPICOS)
    assert ajuda.carregar() == dados


def test_dica_de_configuracoes_diz_onde_fica_o_salvar():
    """Conferido nas telas (web/src/modulos/configuracoes): a barra fixa com “Salvar alterações” e o aviso “Sair sem
    salvar?” existem em Empresa, Envios, Planos de ação e Crescimento (5c); Segurança tem os botões no fim do formulário e
    não avisa; IA não tem “Salvar alterações” (o interruptor vale na hora). A dica não pode dizer “em todas as telas”."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    dados = json.loads(ajuda.CAMINHO.read_text(encoding="utf-8"))
    topico, = [t for t in dados["topicos"] if t["id"] == "configuracoes"]
    secao, = [s for s in topico["secoes"] if s["id"] == "o-que-tem-em-configuracoes"]
    dica, = [b["texto"] for b in secao["blocos"] if b["tipo"] == "dica"]
    assert "todas as telas" not in dica.lower()
    barra, seguranca, ia = dica.split(". Em ")
    assert barra.startswith("Em Empresa, Envios, Planos de ação e Crescimento, “Salvar alterações” fica numa barra fixa")
    assert "“Sair sem salvar?”" in barra
    assert seguranca.startswith("Segurança, “Salvar alterações” fica no fim da página, sem barra fixa")
    assert "não avisa" in seguranca
    assert ia.startswith("IA não há “Salvar alterações”")



def test_assistente_se_chama_toqqiai_na_ajuda():
    """Pedido de 02/10: para o usuário, o assistente é o ToqqiAI. O id do tópico continua `assistente` (endereço
    /ajuda/assistente); "assistente" só fica nas palavras de busca e na apresentação ("o assistente de IA do Toqqi")."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    dados = json.loads(ajuda.CAMINHO.read_text(encoding="utf-8"))
    topico, = [t for t in dados["topicos"] if t["id"] == "assistente"]
    assert topico["titulo"] == "ToqqiAI"
    primeira = topico["secoes"][0]
    assert primeira["titulo"] == "O que é o ToqqiAI e como abrir"
    assert primeira["blocos"][0]["texto"].startswith("O ToqqiAI, o assistente de IA do Toqqi, é um chat")
    textos = []
    for t in dados["topicos"]:
        textos += [t["titulo"], t["resumo"]]
        for secao in t["secoes"]:
            textos.append(secao["titulo"])
            for b in secao["blocos"]:
                textos += [b["texto"]] if "texto" in b else b["itens"]
    com_assistente = [x for x in textos if "assistente" in x.lower()]
    assert com_assistente == [primeira["blocos"][0]["texto"]]
    assert "Toqqi AI" not in " ".join(textos)
    assert ajuda.buscar("toqqiai")[0]["titulo"] == "O que é o ToqqiAI e como abrir"
    for termo in ("assistente", "como abrir o assistente", "chat"):  # quem ainda procura pelo nome antigo também acha
        assert ajuda.buscar(termo)[0]["titulo"] == "O que é o ToqqiAI e como abrir"

# ---- GET /ajuda ------------------------------------------------------------------------------------

def test_get_ajuda_para_todos_os_perfis(client, exemplo):
    admin = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    for h in (admin["h"], membro(client, admin["h"], "gestor@alfa.com.br", "gestor")["h"],
              membro(client, admin["h"], "consulta@alfa.com.br", "consulta")["h"]):
        r = client.get(f"{API}/ajuda", headers=h)
        assert r.status_code == 200 and r.json() == exemplo
        assert r.headers["cache-control"] == "private, max-age=300"
    assert client.get(f"{API}/ajuda").status_code == 401


def test_arquivo_lido_uma_vez(client, exemplo, tmp_path, monkeypatch):
    copia = tmp_path / "conteudo.json"
    copia.write_text(json.dumps(exemplo), encoding="utf-8")
    monkeypatch.setattr(ajuda, "CAMINHO", copia)
    assert ajuda.carregar() == exemplo
    copia.write_text(json.dumps({"versao": 2, "topicos": []}), encoding="utf-8")
    assert ajuda.carregar() == exemplo  # cache em memória
    ajuda.limpar_cache()
    assert ajuda.carregar() == {"versao": 2, "topicos": []}


def test_arquivo_ausente_ou_quebrado_fica_vazio_sem_cache(tmp_path, caplog):
    faltando = tmp_path / "conteudo.json"
    with caplog.at_level(logging.ERROR, logger="toqqi.ajuda"):
        assert ajuda.carregar(faltando) == {"versao": 1, "topicos": []}
    assert "conteudo.json" in caplog.text
    faltando.write_text("{quebrado", encoding="utf-8")
    assert ajuda.carregar(faltando) == {"versao": 1, "topicos": []}
    faltando.write_text(json.dumps({"versao": 1, "topicos": [{"id": "x"}]}), encoding="utf-8")
    assert ajuda.carregar(faltando)["topicos"] == [{"id": "x"}]  # lido quando ficou bom
    assert ajuda.buscar("qualquer coisa", caminho=faltando) == []  # conteúdo fora do formato não derruba a busca


# ---- busca --------------------------------------------------------------------------------------------

def test_busca_pontua_titulo_palavras_e_texto(exemplo):
    achadas = ajuda.buscar("Como importo meus contatos?")
    assert [x["titulo"] for x in achadas] == ["Importar uma planilha", "Adicionar um contato"]
    primeira = achadas[0]
    assert (primeira["topico"], primeira["atalho"]) == ("Contatos", "importar_contatos")
    assert primeira["texto"] == (
        "Traga muitos contatos de uma vez a partir de uma planilha do Excel ou de um arquivo CSV.\n"
        "1. Abra Contatos e clique em Importar planilha.\n2. Escolha o arquivo e confira as colunas.\n"
        "3. Clique em Importar.\nDica: Contatos com o mesmo e-mail são atualizados, não duplicados.")
    # sem acento e sem diferenciar maiúsculas; seção só do administrador avisa no texto; lista com "- "
    envios, = ajuda.buscar("ENVIOS AUTOMÁTICOS")
    assert envios["titulo"] == "Ligar os envios automáticos" and envios["atalho"] == "config_envios"
    assert envios["texto"].startswith("Só administrador.\nO robô manda") and envios["texto"].endswith("- WhatsApp")
    assert ajuda.buscar("robo")[0]["titulo"] == "Ligar os envios automáticos"
    # palavras (peso 3) contam mais que o texto (peso 1); atalho null fica null
    cota, = ajuda.buscar("limite")
    assert (cota["titulo"], cota["atalho"]) == ("Cota de análises", None)


def test_busca_sem_resultado_palavras_curtas_e_limite(exemplo):
    assert ajuda.buscar("") == [] and ajuda.buscar("de a o é") == [] and ajuda.buscar("como para que") == []
    assert ajuda.buscar("xilofone") == []
    assert len(ajuda.buscar("contatos planilha envios cota", limite=3)) == 3
    assert len(ajuda.buscar("contatos planilha envios cota", limite=1)) == 1
    assert ajuda.buscar("contatos", limite=0) == []


def test_busca_corta_o_texto_em_1500(exemplo, tmp_path):
    longo = copy.deepcopy(exemplo)
    _secao(longo)["blocos"] = [{"tipo": "paragrafo", "texto": "palavra " * 400}]
    caminho = tmp_path / "longo.json"
    caminho.write_text(json.dumps(longo), encoding="utf-8")
    texto = ajuda.buscar("importar planilha", caminho=caminho)[0]["texto"]
    assert len(texto) <= 1500 and texto.endswith("palavra…")
