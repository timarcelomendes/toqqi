"""Etapa 5b: Ajuda — validação do conteúdo (exemplo e arquivo real), GET /ajuda e a busca usada pelo assistente.
Jornadas (docs/ajuda-jornadas.md): validação, texto, busca junto com as seções e a resposta do ToqqiAI."""
import copy
import json
import logging

import pytest
from util import AJUDA_EXEMPLO, API, conta_pronta, membro, perguntar

from toqqi.core import ia_conversa
from toqqi.modulos.ajuda import servico as ajuda

# três jornadas que apontam para as seções da Ajuda de exemplo: duas do ciclo (uma só do administrador) e uma
# "para ir além", sem atalho
JORNADAS_EXEMPLO = [
    {"id": "trazer-os-contatos", "grupo": "ciclo", "titulo": "Trazer os contatos",
     "objetivo": "Colocar a lista de clientes no Toqqi de uma vez.", "somente_admin": False,
     "onde": ["Contatos", "Importar planilha"], "atalho": "importar_contatos",
     "como": ["Em Contatos, clique em “Importar planilha”.", "Escolha o arquivo do Excel e clique em “Importar”."],
     "resultado": "Os contatos aparecem na lista, prontos para receber a pesquisa.",
     "veja": ["contatos#importar-planilha", "contatos#adicionar-contato"], "palavras": ["subir lista", "excel"]},
    {"id": "ligar-o-robo", "grupo": "ciclo", "titulo": "Ligar o robô",
     "objetivo": "Fazer a pesquisa sair sozinha, sem ninguém enviar.", "somente_admin": True,
     "onde": ["Configurações", "Envios"], "atalho": "config_envios",
     "como": ["Ligue “Envio automático”.", "Escolha o horário e clique em “Salvar alterações”."],
     "resultado": "A pesquisa sai sozinha todo dia, no horário escolhido.",
     "veja": ["envios#ligar-envios"], "palavras": ["robô", "automático"]},
    {"id": "conferir-a-cota", "grupo": "alem", "titulo": "Conferir a cota",
     "objetivo": "Saber quantas perguntas ao ToqqiAI ainda cabem no mês.", "somente_admin": False,
     "onde": ["Qualquer tela", "Botão ToqqiAI"], "atalho": None,
     "como": ["Clique no botão “ToqqiAI”.", "Veja no alto do chat quantas análises restam."],
     "resultado": "Você sabe quantas análises ainda pode usar até o dia 1º.",
     "veja": ["assistente#cota"], "palavras": ["limite"]},
]


@pytest.fixture
def exemplo(monkeypatch) -> dict:
    """A Ajuda de exemplo no lugar do conteudo.json (que é de outro agente e pode ainda não existir)."""
    monkeypatch.setattr(ajuda, "CAMINHO", AJUDA_EXEMPLO)
    ajuda.limpar_cache()
    return json.loads(AJUDA_EXEMPLO.read_text(encoding="utf-8"))


@pytest.fixture
def com_jornadas(exemplo, tmp_path, monkeypatch) -> dict:
    """A Ajuda de exemplo com as jornadas de JORNADAS_EXEMPLO, no lugar do conteudo.json."""
    dados = {"versao": exemplo["versao"], "jornadas": copy.deepcopy(JORNADAS_EXEMPLO), "topicos": exemplo["topicos"]}
    caminho = tmp_path / "com_jornadas.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ajuda, "CAMINHO", caminho)
    ajuda.limpar_cache()
    return dados


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


def _jornada(dados: dict, i: int = 0) -> dict:
    return dados["jornadas"][i]


def test_exemplo_com_jornadas_e_valido(com_jornadas):
    assert ajuda.validar(com_jornadas) == []


def test_jornada_no_limite_de_tudo_e_valida_e_o_texto_para_em_1500(com_jornadas):
    cheia = {**JORNADAS_EXEMPLO[1], "titulo": "t" * 60, "objetivo": ("objetivo " * 20)[:160], "onde": ["o" * 40] * 4,
             "como": [("passo " * 40)[:220]] * 6, "resultado": ("resultado " * 40)[:320],
             "veja": ["contatos#importar-planilha", "envios#ligar-envios", "assistente#cota"]}
    assert ajuda.validar({**com_jornadas, "jornadas": [cheia]}) == []
    texto = ajuda.texto_da_jornada(cheia)
    assert texto.startswith("Só administrador.\nobjetivo objetivo") and len(texto) <= 1500 and texto.endswith("…")


@pytest.mark.parametrize("estragar,trecho", [
    (lambda d: d.update(jornadas=[]), "jornadas: lista vazia"),
    (lambda d: d.update(jornadas=None), "jornadas: lista vazia"),
    (lambda d: d["jornadas"].append("x"), "jornadas[3]: não é um objeto"),
    (lambda d: d.update(capa="x"), "raiz: campos desconhecidos capa"),
    (lambda d: _jornada(d).pop("veja"), "jornada trazer-os-contatos: faltam os campos veja"),
    (lambda d: _jornada(d).update(icone="x"), "jornada trazer-os-contatos: campos desconhecidos icone"),
    (lambda d: _jornada(d).update(id="Trazer_Contatos"), "jornada Trazer_Contatos: id fora do kebab-case"),
    (lambda d: _jornada(d, 1).update(id="trazer-os-contatos"), "jornada trazer-os-contatos: id repetido"),
    (lambda d: _jornada(d).update(grupo="extra"), "jornada trazer-os-contatos, grupo: precisa ser ciclo ou alem"),
    (lambda d: d["jornadas"].insert(0, d["jornadas"].pop()),  # a do grupo alem antes das do ciclo
     "jornada trazer-os-contatos, grupo: as jornadas do ciclo vêm antes das de alem"),
    (lambda d: _jornada(d).update(titulo=" "), "jornada trazer-os-contatos, titulo: texto vazio"),
    (lambda d: _jornada(d).update(titulo="t" * 61), "jornada trazer-os-contatos, titulo: passa de 60 caracteres"),
    (lambda d: _jornada(d).update(objetivo="o" * 161), "objetivo: passa de 160 caracteres"),
    (lambda d: _jornada(d).update(resultado="r" * 321), "resultado: passa de 320 caracteres"),
    (lambda d: _jornada(d).update(objetivo="Veja em HTTPS://toqqi.com"), "objetivo: contém 'http'"),
    (lambda d: _jornada(d).update(resultado="A lista <b>aparece</b>."), "resultado: contém '<'"),
    (lambda d: _jornada(d)["como"].append("Clique em **Salvar**."), "como: contém '**'"),
    (lambda d: _jornada(d)["onde"].append("www.toqqi.com"), "onde: contém 'www.'"),
    (lambda d: _jornada(d)["palavras"].append("<script>"), "palavras: contém '<'"),
    (lambda d: _jornada(d).update(onde=[]), "onde: precisa ter de 1 a 4 pedaços"),
    (lambda d: _jornada(d).update(onde=["A", "B", "C", "D", "E"]), "onde: precisa ter de 1 a 4 pedaços"),
    (lambda d: _jornada(d).update(onde="Contatos"), "onde: precisa ter de 1 a 4 pedaços"),
    (lambda d: _jornada(d).update(onde=["Contatos › Importar planilha"]), "onde: sem “›” nos pedaços"),
    (lambda d: _jornada(d).update(onde=["o" * 41]), "onde: passa de 40 caracteres"),
    (lambda d: _jornada(d).update(onde=["Contatos", ""]), "onde: texto vazio"),
    (lambda d: _jornada(d).update(como=["Um passo só."]), "como: precisa ter de 2 a 6 passos"),
    (lambda d: _jornada(d).update(como=["Mais um passo."] * 7), "como: precisa ter de 2 a 6 passos"),
    (lambda d: _jornada(d)["como"].append("p" * 221), "como: passa de 220 caracteres"),
    (lambda d: _jornada(d)["como"].append(""), "como: texto vazio"),
    (lambda d: _jornada(d).update(atalho="painel_secreto"), "atalho: desconhecido (painel_secreto)"),
    (lambda d: _jornada(d).update(somente_admin="não"), "somente_admin: precisa ser true ou false"),
    (lambda d: _jornada(d).update(veja=[]), "veja: precisa ter de 1 a 3 referências"),
    (lambda d: _jornada(d).update(veja=["contatos#importar-planilha", "contatos#adicionar-contato",
                                        "envios#ligar-envios", "assistente#cota"]), "veja: precisa ter de 1 a 3"),
    (lambda d: _jornada(d).update(veja=["contatos#nao-existe"]), "veja: seção inexistente (contatos#nao-existe)"),
    (lambda d: _jornada(d).update(veja=["envios#importar-planilha"]), "veja: seção inexistente"),  # de outro tópico
    (lambda d: _jornada(d).update(veja=["importar-planilha"]), "veja: seção inexistente"),  # sem o tópico
    (lambda d: _jornada(d).update(veja=["contatos#importar-planilha"] * 2),
     "veja: referência repetida (contatos#importar-planilha)"),
    (lambda d: _jornada(d).update(palavras="excel"), "palavras: precisa ser uma lista"),
    (lambda d: _jornada(d)["palavras"].append(" "), "palavras: texto vazio"),
    (lambda d: d["topicos"][0].update(id="jornadas"), "tópico jornadas: id reservado"),
])
def test_validacao_das_jornadas_aponta_os_problemas(com_jornadas, estragar, trecho):
    dados = copy.deepcopy(com_jornadas)
    estragar(dados)
    erros = ajuda.validar(dados)
    assert any(trecho in e for e in erros), erros


def test_conteudo_real_valido():
    """O conteudo.json de verdade (escrito à parte): formato, regras de texto e os tópicos e as jornadas na ordem
    combinada."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    dados = json.loads(ajuda.CAMINHO.read_text(encoding="utf-8"))
    assert ajuda.validar(dados) == []
    assert [t["id"] for t in dados["topicos"]] == list(ajuda.TOPICOS)
    assert [j["id"] for j in dados["jornadas"]] == list(ajuda.JORNADAS)
    assert ajuda.carregar() == dados


def test_jornadas_reais_como_no_contrato():
    """docs/ajuda-jornadas.md §1: grupo, atalho, primeira referência do `veja` (o tópico "dono" da jornada) e as que
    são só do administrador."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    dados = json.loads(ajuda.CAMINHO.read_text(encoding="utf-8"))
    assert [(j["id"], j["grupo"], j["atalho"], j["veja"][0], j["somente_admin"]) for j in dados["jornadas"]] == [
        ("cadastrar-seus-clientes", "ciclo", "importar_contatos", "contatos#importar-planilha-de-contatos", False),
        ("preparar-a-pesquisa", "ciclo", "formularios", "formularios#criar-um-formulario", False),
        ("ligar-os-envios", "ciclo", "config_envios", "configuracoes#configuracoes-de-envio-ligar-canal-e-horario",
         True),
        ("enviar-a-pesquisa", "ciclo", "envios", "envios#enviar-por-email-agora", False),
        ("ler-as-respostas", "ciclo", "respostas", "respostas#ver-e-filtrar-as-respostas", False),
        ("tratar-um-cliente-insatisfeito", "ciclo", "planos_de_acao", "planos-de-acao#tratar-e-concluir-uma-acao",
         False),
        ("acompanhar-os-numeros", "ciclo", "inicio", "painel#o-que-mostra-o-inicio", False),
        ("descobrir-onde-agir", "ciclo", "relatorios", "relatorios#empresas-nps-cobertura-e-receita", False),
        ("crescer-com-quem-esta-feliz", "ciclo", "crescimento", "crescimento#indicacoes-dos-promotores", False),
        ("perguntar-ao-toqqiai", "alem", None, "assistente#o-que-e-o-assistente", False),
        ("trazer-a-equipe", "alem", "equipe", "equipe#adicionar-e-gerenciar-pessoas", True),
        ("ligar-o-seu-sistema", "alem", "integracoes", "integracoes#ligar-seu-sistema-zapier-make-n8n", True),
        ("assinar-um-plano", "alem", "assinatura", "assinatura#assinar-um-plano", True),
    ]
    sistema, = [j for j in dados["jornadas"] if j["id"] == "ligar-o-seu-sistema"]
    assert sistema["titulo"] == "Ligar o seu sistema e o WhatsApp automático"


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
    /ajuda/assistente); "assistente" só fica nas palavras de busca (das seções e das jornadas) e na apresentação ("o
    assistente de IA do Toqqi")."""
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
    for j in dados["jornadas"]:  # o que a tela mostra da jornada (as palavras e o veja não aparecem)
        textos += [j["titulo"], j["objetivo"], *j["onde"], *j["como"], j["resultado"]]
    com_assistente = [x for x in textos if "assistente" in x.lower()]
    assert com_assistente == [primeira["blocos"][0]["texto"]]
    assert "Toqqi AI" not in " ".join(textos)
    # quem procura pelo nome novo ou pelo antigo acha o ToqqiAI: a jornada "Perguntar ao ToqqiAI" (que vem antes no
    # empate) ou a seção que o apresenta
    toqqiai = {("Jornadas", "Perguntar ao ToqqiAI"), ("ToqqiAI", "O que é o ToqqiAI e como abrir")}
    for termo in ("toqqiai", "assistente", "como abrir o assistente", "chat"):
        achada = ajuda.buscar(termo)[0]
        assert (achada["topico"], achada["titulo"]) in toqqiai, (termo, achada["titulo"])


@pytest.mark.parametrize("pergunta,jornada", [
    ("Como cadastro meus clientes?", "Cadastrar seus clientes"),  # empata com três seções: a jornada vem antes
    ("Como preparo a pesquisa?", "Preparar a pesquisa"),  # empata com "Enviar a pesquisa por e-mail agora"
    ("Como trato quem deu nota baixa?", "Tratar um cliente insatisfeito"),
    ("Como vender mais para clientes satisfeitos?", "Crescer com quem está feliz"),
    ("Como dar acesso para a minha equipe?", "Trazer a equipe"),
    ("Como uso o chat?", "Perguntar ao ToqqiAI"),
])
def test_busca_real_traz_a_jornada_primeiro(pergunta, jornada):
    """Dúvidas de uso no conteúdo real: a jornada certa vem em primeiro (conferido na busca de verdade)."""
    if not ajuda.CAMINHO.exists():
        pytest.skip("api/toqqi/modulos/ajuda/conteudo.json ainda não existe")
    achada = ajuda.buscar(pergunta)[0]
    assert (achada["topico"], achada["titulo"]) == ("Jornadas", jornada)

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


# ---- busca com jornadas -------------------------------------------------------------------------------

def _achadas(termo: str, **extra) -> list[tuple[str, str]]:
    return [(x["topico"], x["titulo"]) for x in ajuda.buscar(termo, **extra)]


def test_busca_com_jornadas_empate_jornada_primeiro(com_jornadas):
    # empate (palavras 3 + texto 1; só palavras 3): a jornada vem antes da seção
    assert _achadas("excel") == [("Jornadas", "Trazer os contatos"), ("Contatos", "Importar uma planilha")]
    assert _achadas("limite") == [("Jornadas", "Conferir a cota"), ("ToqqiAI", "Cota de análises")]
    # mais pontos vencem a ordem: o termo no título e nas palavras da seção vale mais que no texto da jornada
    assert _achadas("importar planilha") == [("Contatos", "Importar uma planilha"), ("Jornadas", "Trazer os contatos")]
    assert _achadas("ENVIOS AUTOMÁTICOS") == [("Envios", "Ligar os envios automáticos"), ("Jornadas", "Ligar o robô")]


def test_busca_traz_a_jornada_com_onde_como_resultado_e_atalho(com_jornadas):
    cota = com_jornadas["jornadas"][2]
    assert ajuda.buscar("subir lista") == [{"topico": "Jornadas", "titulo": "Trazer os contatos", "texto": (
        "Colocar a lista de clientes no Toqqi de uma vez.\n"
        "Onde: Contatos › Importar planilha\n"
        "Como:\n"
        "1. Em Contatos, clique em “Importar planilha”.\n"
        "2. Escolha o arquivo do Excel e clique em “Importar”.\n"
        "Resultado: Os contatos aparecem na lista, prontos para receber a pesquisa."), "atalho": "importar_contatos"}]
    # só do administrador: avisa no começo, como nas seções
    assert ajuda.buscar("robô")[0] == {"topico": "Jornadas", "titulo": "Ligar o robô", "texto": (
        "Só administrador.\n"
        "Fazer a pesquisa sair sozinha, sem ninguém enviar.\n"
        "Onde: Configurações › Envios\n"
        "Como:\n"
        "1. Ligue “Envio automático”.\n"
        "2. Escolha o horário e clique em “Salvar alterações”.\n"
        "Resultado: A pesquisa sai sozinha todo dia, no horário escolhido."), "atalho": "config_envios"}
    assert ajuda.buscar("limite")[0]["texto"] == ajuda.texto_da_jornada(cota)
    assert ajuda.buscar("limite")[0]["atalho"] is None  # atalho null fica null
    # partes vazias ou fora do formato ficam de fora do texto
    assert ajuda.texto_da_jornada({"onde": ["", " Contatos ", 3], "como": ["Passo."], "resultado": " "}) == (
        "Onde: Contatos\nComo:\n1. Passo.")


def test_busca_com_jornadas_limite_vale_para_as_duas(com_jornadas):
    termo = "excel limite robô"
    assert _achadas(termo, limite=10) == [
        ("Jornadas", "Ligar o robô"), ("Jornadas", "Trazer os contatos"), ("Contatos", "Importar uma planilha"),
        ("Envios", "Ligar os envios automáticos"), ("Jornadas", "Conferir a cota"), ("ToqqiAI", "Cota de análises")]
    assert _achadas(termo) == _achadas(termo, limite=10)[:3]  # padrão: 3
    assert _achadas(termo, limite=1) == [("Jornadas", "Ligar o robô")]
    assert ajuda.buscar(termo, limite=0) == []


def test_jornadas_nao_mudam_as_secoes_na_busca(com_jornadas):
    """Com jornadas, as seções saem na mesma ordem e com o mesmo texto; sem jornadas, a busca é a de hoje (os testes
    acima, com a Ajuda de exemplo, ficaram como estavam)."""
    for termo in ("Como importo meus contatos?", "ENVIOS AUTOMÁTICOS", "robo", "limite", "excel",
                  "contatos planilha envios cota"):
        secoes = [x for x in ajuda.buscar(termo, limite=20) if x["topico"] != "Jornadas"]
        assert secoes == ajuda.buscar(termo, limite=20, caminho=AJUDA_EXEMPLO), termo


@pytest.mark.parametrize("jornadas", [None, "jornadas", 5, {"titulo": "Robô"}, [None, 3, "x", {}, {"titulo": 5}]])
def test_jornadas_fora_do_formato_nao_derrubam_a_busca(exemplo, tmp_path, jornadas):
    caminho = tmp_path / "estranho.json"
    caminho.write_text(json.dumps({**exemplo, "jornadas": jornadas}), encoding="utf-8")
    for termo in ("robô", "Como importo meus contatos?", "limite"):
        assert ajuda.buscar(termo, caminho=caminho) == ajuda.buscar(termo, caminho=AJUDA_EXEMPLO), termo


def test_jornada_malformada_com_titulo_entra_na_busca_sem_derrubar(exemplo, tmp_path):
    torta = {"titulo": "Robô torto", "objetivo": 3, "onde": "Configurações", "como": ["  ", 7, "Ligue o envio."],
             "resultado": None, "palavras": "robo", "atalho": "painel_secreto", "somente_admin": "sim"}
    caminho = tmp_path / "torta.json"
    caminho.write_text(json.dumps({**exemplo, "jornadas": [torta]}), encoding="utf-8")
    secao, = ajuda.buscar("robô", caminho=AJUDA_EXEMPLO)  # palavras 3 + texto 1
    assert ajuda.buscar("robô", caminho=caminho) == [  # a jornada só tem o título (3)
        secao, {"topico": "Jornadas", "titulo": "Robô torto", "texto": "Como:\n1. Ligue o envio.", "atalho": None}]


# ---- ToqqiAI ----------------------------------------------------------------------------------------------

def test_toqqiai_responde_a_duvida_de_uso_com_a_jornada(client, com_jornadas, relogio_estavel):
    """De ponta a ponta com o provedor `memoria` (padrão por palavras: dúvida de uso → buscar_ajuda, e a resposta é o
    primeiro resultado): a jornada chega com Onde, Como e Resultado e o atalho da tela, e as instruções pedem as três
    partes. GET /ajuda serve as jornadas como estão."""
    mem = ia_conversa.memoria
    admin = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = admin["h"]
    assert client.get(f"{API}/ajuda", headers=h).json()["jornadas"] == JORNADAS_EXEMPLO
    r = perguntar(client, h, "Como trazer os contatos para o Toqqi?")
    assert r.status_code == 200, r.text
    resposta = r.json()["resposta"]
    assert resposta == "Trazer os contatos (Jornadas):\n" + ajuda.texto_da_jornada(JORNADAS_EXEMPLO[0])
    linhas = resposta.splitlines()
    assert linhas[2:5] == ["Onde: Contatos › Importar planilha", "Como:",
                           "1. Em Contatos, clique em “Importar planilha”."]
    assert linhas[-1].startswith("Resultado: Os contatos aparecem na lista")
    assert [a["chave"] for a in r.json()["atalhos"]] == ["importar_contatos", "ajuda"]
    saida, = [json.loads(i["output"]) for i in mem.corpos[1]["input"] if i.get("type") == "function_call_output"]
    assert saida["secoes"][0]["topico"] == "Jornadas" and saida["secoes"][0]["atalho"] == "importar_contatos"
    instrucoes = mem.corpos[0]["instructions"]
    assert 'Quando vier uma jornada (topico "Jornadas") sobre a dúvida, responda em três partes' in instrucoes
    assert '"Como:" (os passos curtos, cada um numa linha com "- ")' in instrucoes
    assert '"Onde:"' in instrucoes and '"Resultado:"' in instrucoes
    # quem não abre a tela de importação recebe a jornada, mas só o atalho da Ajuda
    consulta = membro(client, h, "consulta@alfa.com.br", "consulta")
    r = perguntar(client, consulta["h"], "Como trazer os contatos para o Toqqi?").json()
    assert "\nOnde: Contatos › Importar planilha\n" in r["resposta"]
    assert [a["chave"] for a in r["atalhos"]] == ["ajuda"]
