"""Importação de contatos por planilha."""
import io
from datetime import datetime

import pytest
from util import API, conta_pronta, criar_contato, definir_plano, encher_contatos, membro, sql


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _csv(linhas: list[list[str]], sep: str = ";", cod: str = "utf-8-sig") -> bytes:
    return "\r\n".join(sep.join(x) for x in linhas).encode(cod)


def analisar(client, h, conteudo: bytes, nome: str = "contatos.csv"):
    r = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": (nome, conteudo)})
    return r


def _ok(client, h, conteudo, nome="contatos.csv") -> dict:
    r = analisar(client, h, conteudo, nome)
    assert r.status_code == 200, r.text
    return r.json()


BASICO = [
    ["Nome", "E-mail", "WhatsApp", "Razão Social", "CNPJ", "Cargo", "Vendedor", "Valor mensal", "Cliente desde"],
    ["Paula Lima", "paula@norte.com.br", "(11) 98888-7777", "Atacado Norte", "11.222.333/0001-81", "Compradora",
     "Rita", "1.250,50", "01/03/2024"],
    ["Marcos Reis", "marcos@norte.com.br", "", "atacado norte", "", "Gerente", "Rita", "", ""],
    ["Júlia Sá", "", "11 3333-4444", "Mercearia Sul", "", "", "", "300", "2023-05-10"],
]


def test_modelo_csv(client, admin):
    r = client.get(f"{API}/importacao/modelo?tipo=contatos", headers=admin["h"])
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    assert r.content.decode("utf-8-sig").strip() == (
        "nome;email;telefone;empresa;documento_empresa;cargo;perfil;grupo;segmento;responsavel;"
        "valor_mensal;cliente_desde;renovacao_em;perdida_em;motivo_perda;codigo_externo;ativo")


def test_analisar_sugere_mapeamento_por_nomes_equivalentes(client, admin):
    d = _ok(client, admin["h"], _csv(BASICO))
    assert d["total_linhas"] == 3
    assert d["colunas"] == BASICO[0]
    assert d["mapeamento_sugerido"] == {
        "Nome": "nome", "E-mail": "email", "WhatsApp": "telefone", "Razão Social": "empresa",
        "CNPJ": "documento_empresa", "Cargo": "cargo", "Vendedor": "responsavel", "Valor mensal": "valor_mensal",
        "Cliente desde": "cliente_desde"}
    assert d["amostra"][0] == {"linha": 2, "valores": dict(zip(BASICO[0], BASICO[1]))}
    assert {"chave": "nome", "rotulo": "Nome do contato", "obrigatorio": True} in d["campos"]


def test_conferir_e_importar_tudo(client, admin):
    h = admin["h"]
    d = _ok(client, h, _csv(BASICO))
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "atualizar_existentes": False}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert (c["prontas"], c["com_problema"], c["novos"], c["atualizados"]) == (3, 0, 3, 0)
    assert any("empresas" in a for a in c["avisos"])
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200, r.text
    assert r.json() == {"novos": 3, "atualizados": 0, "ignorados": 0, "problemas": []}

    contatos = {x["nome"]: x for x in client.get(f"{API}/contatos", headers=h).json()["itens"]}
    assert contatos["Paula Lima"]["telefone"] == "5511988887777"
    assert contatos["Paula Lima"]["cargo"]["nome"] == "Compradora"
    assert contatos["Júlia Sá"]["telefone"] == "551133334444" and contatos["Júlia Sá"]["email"] is None
    # "Atacado Norte" e "atacado norte" viram a mesma empresa
    empresas = {e["nome"]: e for e in client.get(f"{API}/empresas", headers=h).json()["itens"]}
    assert set(empresas) == {"Atacado Norte", "Mercearia Sul"}
    norte = empresas["Atacado Norte"]
    assert norte["contatos"] == 2 and norte["documento"] == "11222333000181"
    assert norte["valor_mensal"] == 1250.5 and norte["cliente_desde"] == "2024-03-01"
    assert norte["responsavel"]["nome"] == "Rita"
    assert empresas["Mercearia Sul"]["cliente_desde"] == "2023-05-10"
    assert [r["nome"] for r in client.get(f"{API}/responsaveis", headers=h).json()] == ["Rita"]
    assert len(client.get(f"{API}/cadastros/cargos", headers=h).json()) == 2
    # auditoria com as contagens; a análise não pode ser usada de novo
    ev = next(i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == "importacao")
    assert ev["detalhe"]["novos"] == 3 and ev["detalhe"]["criados"]["empresas"] == 2
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo).status_code == 404


def test_problemas_por_linha_e_tudo_ou_nada(client, admin):
    h = admin["h"]
    linhas = [
        ["nome", "email", "telefone", "documento_empresa", "empresa", "valor_mensal", "cliente_desde", "ativo"],
        ["Ok", "ok@x.com.br", "", "", "Empresa Ok", "", "", ""],
        ["Email ruim", "sem-arroba", "", "", "", "", "", ""],
        ["Tel ruim", "", "123", "", "", "", "", ""],
        ["Sem canal", "", "", "", "", "", "", ""],
        ["Valor ruim", "v@x.com.br", "", "", "", "abc", "", ""],
        ["Data ruim", "d@x.com.br", "", "", "", "", "31/02/2024", ""],
        ["Doc ruim", "doc@x.com.br", "", "11.222.333/0001-00", "E", "", "", ""],
        ["Repetido", "OK@x.com.br", "", "", "", "", "", ""],
        ["", "semnome@x.com.br", "", "", "", "", "", ""],
        ["Ativo ruim", "a@x.com.br", "", "", "", "", "", "talvez"],
    ]
    d = _ok(client, h, _csv(linhas))
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email"}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert c["prontas"] == 1 and c["com_problema"] == 9
    motivos = {p["linha"]: p["motivo"] for p in c["problemas"]}
    assert "E-mail inválido" in motivos[3]
    assert "Telefone inválido" in motivos[4]
    assert "Sem e-mail e sem telefone" in motivos[5]
    assert "Valor mensal inválido" in motivos[6]
    assert "Data inválida" in motivos[7]
    assert "CNPJ/CPF inválido" in motivos[8]
    assert "linha 2" in motivos[9]
    assert "Nome em branco" in motivos[10]
    assert "ativo" in motivos[11]
    # com problema e sem ignorar: nada é gravado
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "importacao_com_problema"
    assert client.get(f"{API}/contatos", headers=h).json()["total"] == 0
    assert client.get(f"{API}/empresas", headers=h).json()["total"] == 0
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json={**corpo, "ignorar_com_problema": True})
    assert r.json()["novos"] == 1 and r.json()["ignorados"] == 9 and len(r.json()["problemas"]) == 9
    assert client.get(f"{API}/contatos", headers=h).json()["total"] == 1


def test_chave_codigo_externo_atualiza_existentes(client, admin):
    h = admin["h"]
    antigo = criar_contato(client, h, nome="Nome Antigo", email="antigo@x.com.br", codigo_externo="ERP-1")
    linhas = [["Código", "Nome", "Email", "Status"],
              ["ERP-1", "Nome Novo", "novo@x.com.br", "inativo"],
              ["ERP-2", "Outra Pessoa", "outra@x.com.br", "sim"]]
    d = _ok(client, h, _csv(linhas))
    assert d["mapeamento_sugerido"] == {"Código": "codigo_externo", "Nome": "nome", "Email": "email", "Status": "ativo"}
    base = {"mapeamento": d["mapeamento_sugerido"], "chave": "codigo_externo"}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=base).json()
    assert (c["novos"], c["atualizados"]) == (1, 0) and any("mantid" in a for a in c["avisos"])
    corpo = {**base, "atualizar_existentes": True}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert (c["novos"], c["atualizados"]) == (1, 1)
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo).json()
    assert r == {"novos": 1, "atualizados": 1, "ignorados": 0, "problemas": []}
    atual = client.get(f"{API}/contatos/{antigo['id']}", headers=h).json()
    assert (atual["nome"], atual["email"], atual["ativo"]) == ("Nome Novo", "novo@x.com.br", False)
    assert atual["codigo"] == antigo["codigo"]


def test_email_de_outro_contato_e_problema(client, admin):
    h = admin["h"]
    criar_contato(client, h, email="dono@x.com.br", telefone="11911112222")
    linhas = [["nome", "telefone", "email"], ["Outro", "11933334444", "dono@x.com.br"]]
    d = _ok(client, h, _csv(linhas))
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": d["mapeamento_sugerido"], "chave": "telefone"}).json()
    assert c["com_problema"] == 1 and "outro contato" in c["problemas"][0]["motivo"]


def test_xlsx(client, admin):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Nome completo", "Celular", "Cliente", "Grupo", "Segmento", "Perfil", "Desde"])
    ws.append(["Rui Costa", 11977776666, "Transportes Rui", "Rede Leste", "Transporte", "decisor",
               datetime(2022, 7, 1)])
    buf = io.BytesIO()
    wb.save(buf)
    h = admin["h"]
    d = _ok(client, h, buf.getvalue(), "planilha.xlsx")
    assert d["mapeamento_sugerido"]["Celular"] == "telefone"
    assert d["amostra"][0]["valores"]["Celular"] == "11977776666"
    assert d["amostra"][0]["valores"]["Desde"] == "2022-07-01"
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "telefone"}
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200 and r.json()["novos"] == 1, r.text
    c = client.get(f"{API}/contatos", headers=h).json()["itens"][0]
    assert c["telefone"] == "5511977776666" and c["perfil"]["nome"] == "Decisor"  # perfil já existente
    e = client.get(f"{API}/empresas", headers=h).json()["itens"][0]
    assert e["grupo"]["nome"] == "Rede Leste" and e["segmento"]["nome"] == "Transporte"
    assert len(client.get(f"{API}/cadastros/perfis", headers=h).json()) == 2


def test_xls(client, admin):
    xlwt = pytest.importorskip("xlwt")
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Contatos")
    for c, v in enumerate(["nome", "email", "valor_mensal"]):
        ws.write(0, c, v)
    for c, v in enumerate(["Ana Paula", "ana.paula@x.com.br", 99.9]):
        ws.write(1, c, v)
    buf = io.BytesIO()
    wb.save(buf)
    d = _ok(client, admin["h"], buf.getvalue(), "antigo.xls")
    assert d["amostra"][0]["valores"] == {"nome": "Ana Paula", "email": "ana.paula@x.com.br", "valor_mensal": "99.9"}


def test_csv_latin1_com_virgula(client, admin):
    linhas = [["Nome", "E-mail", "Função"], ["José Conceição", "jose@x.com.br", "Diretor"]]
    d = _ok(client, admin["h"], _csv(linhas, sep=",", cod="latin-1"))
    assert d["colunas"] == ["Nome", "E-mail", "Função"]
    assert d["amostra"][0]["valores"]["Nome"] == "José Conceição"
    assert d["mapeamento_sugerido"]["Função"] == "cargo"
    d = _ok(client, admin["h"], _csv(linhas, sep="\t"))
    assert len(d["colunas"]) == 3


def test_arquivo_invalido(client, admin):
    h = admin["h"]
    assert analisar(client, h, b"x", "contatos.pdf").status_code == 422
    assert analisar(client, h, b"nome;email\r\n", "vazio.csv").status_code == 422
    assert analisar(client, h, b"nao e xlsx", "x.xlsx").status_code == 422
    grande = b"nome;email\r\n" + b"a;b\r\n" * 20001
    r = analisar(client, h, grande)
    assert r.status_code == 422 and "20.000" in r.json()["erro"]["mensagem"]


def test_mapeamento_invalido(client, admin):
    h = admin["h"]
    d = _ok(client, h, _csv(BASICO))
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": {"E-mail": "email"}, "chave": "email"})
    assert r.status_code == 422 and "mapeamento" in r.json()["erro"]["campos"]
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": {"Nome": "nome", "E-mail": "email"}, "chave": "codigo_externo"})
    assert r.status_code == 422 and "chave" in r.json()["erro"]["campos"]
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": {"Nome": "nome", "E-mail": "email", "Cargo": "email"}, "chave": "email"})
    assert r.status_code == 422


def test_limite_do_plano_na_importacao(client, admin, dono):
    h = admin["h"]
    conta_id = admin["conta"]["id"]
    definir_plano(dono, conta_id, "essencial")
    encher_contatos(dono, conta_id, 298)
    d = _ok(client, h, _csv(BASICO))  # 3 novos → 301
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email"}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert any("300" in a for a in c["avisos"])
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 402 and r.json()["erro"]["codigo"] == "limite_do_plano"
    # nada gravado (nem empresas/cadastros)
    assert client.get(f"{API}/empresas", headers=h).json()["total"] == 0
    assert client.get(f"{API}/responsaveis", headers=h).json() == []
    definir_plano(dono, conta_id, "profissional")
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo).status_code == 200


def test_grupo_padrao_e_analise_expirada(client, admin, dono):
    h = admin["h"]
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Importados"}).json()
    d = _ok(client, h, _csv(BASICO))
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "grupo_id": g["id"]}
    client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert all(e["grupo"]["id"] == g["id"] for e in client.get(f"{API}/empresas", headers=h).json()["itens"])
    d = _ok(client, h, _csv(BASICO))
    sql(dono, "update importacoes set expira_em = now() - interval '1 minute'")
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo)
    assert r.status_code == 404
    _ok(client, h, _csv(BASICO))  # nova análise limpa as vencidas
    assert sql(dono, "select count(*) from importacoes")[0][0] == 1


def test_permissoes_importacao(client, admin):
    consulta = membro(client, admin["h"], "caio@alfa.com.br", "consulta")
    gestor = membro(client, admin["h"], "gil@alfa.com.br", "gestor")
    assert analisar(client, consulta["h"], _csv(BASICO)).status_code == 403
    assert client.get(f"{API}/importacao/modelo", headers=consulta["h"]).status_code == 403
    d = _ok(client, gestor["h"], _csv(BASICO))
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=gestor["h"],
                    json={"mapeamento": d["mapeamento_sugerido"], "chave": "email"})
    assert r.status_code == 200


def test_ativo_vazio_nao_reativa_existente(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, email="x@x.com.br", ativo=False)
    linhas = [["nome", "email", "ativo"], ["Novo Nome", "x@x.com.br", ""], ["Outro", "o@x.com.br", ""]]
    d = _ok(client, h, _csv(linhas))
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "atualizar_existentes": True}
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo).status_code == 200
    atual = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    assert atual["nome"] == "Novo Nome" and atual["ativo"] is False
    assert client.get(f"{API}/contatos?ativo=true", headers=h).json()["itens"][0]["nome"] == "Outro"
