"""Etapa 5i (desfecho, segunda parte): linha do tempo da empresa, CSV da aba Desfecho, renovação pela importação (e
contato de empresa perdida entra inativo), `POST /integracao/empresas` (cria, atualiza, perde e volta), webhooks
`empresa.*` e o ToqqiAI sobre perdas e saúde."""
import pytest
from util import API, conta_pronta, contexto_de, criar_contato, criar_empresa, evento, gerar_chave, sql

from toqqi.core import rede
from toqqi.modulos.assistente import ferramentas


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _antigo(dono, empresa_id: int) -> None:
    sql(dono, "update empresa_historico set data = '2025-01-01' where empresa_id = :e", e=empresa_id)


def test_linha_do_tempo_e_csv(client, dono, admin):
    h = admin["h"]
    e = criar_empresa(client, h, nome="Mercado Azul", valor_mensal="1000.00")
    criar_contato(client, h, empresa_id=e["id"])
    _antigo(dono, e["id"])
    assert client.patch(f"{API}/empresas/{e['id']}", headers=h, json={"valor_mensal": "1200.00"}).status_code == 200
    r = client.post(f"{API}/empresas/{e['id']}/perda", headers=h,
                    json={"motivo_perda": "concorrente", "motivo_detalhe": "Foi para a X"})
    assert r.status_code == 200, r.text

    r = client.get(f"{API}/empresas/{e['id']}/historico", headers=h)
    assert r.status_code == 200, r.text
    itens = r.json()["itens"]
    assert itens[0]["tipo"] == "perdida" and itens[0]["motivo_rotulo"] == "Foi para um concorrente"
    assert itens[0]["contatos"] == 1 and itens[0]["origem"] == "tela" and itens[0]["usuario"]["nome"]
    assert {i["tipo"] for i in itens} >= {"entrada", "perdida"}
    assert client.get(f"{API}/empresas/999999/historico", headers=h).status_code == 404

    r = client.get(f"{API}/relatorios/desfecho.csv", headers=h)
    assert r.status_code == 200, r.text
    linhas = r.content.decode("utf-8-sig").splitlines()
    assert linhas[0].startswith("Empresa;Perdida em;Motivo")
    assert "Mercado Azul" in linhas[1] and "Foi para um concorrente" in linhas[1]


def test_importacao_com_renovacao_e_empresa_perdida(client, dono, admin):
    h = admin["h"]
    perdida = criar_empresa(client, h, nome="Padaria Sol")
    _antigo(dono, perdida["id"])
    client.post(f"{API}/empresas/{perdida['id']}/perda", headers=h, json={"motivo_perda": "preco"})
    linhas = [["Nome", "E-mail", "Empresa", "Renovação do contrato"],
              ["Ana", "ana@norte.com.br", "Atacado Norte", "01/03/2027"],
              ["Beto", "beto@sol.com.br", "Padaria Sol", ""]]
    conteudo = "\r\n".join(";".join(x) for x in linhas).encode("utf-8-sig")
    d = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("c.csv", conteudo)}).json()
    assert d["mapeamento_sugerido"]["Renovação do contrato"] == "renovacao_em"
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email"}
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200, r.text
    assert sql(dono, "select renovacao_em::text from empresas where nome = 'Atacado Norte'")[0][0] == "2027-03-01"
    assert sql(dono, "select ativo from contatos where email = 'beto@sol.com.br'")[0][0] is False


def test_integracao_empresas_e_webhooks(client, dono, admin, monkeypatch):
    h = admin["h"]
    monkeypatch.setattr(rede, "resolver", lambda host: ["52.96.1.10"])
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://erp.cliente.com.br/toqqi", "eventos": ["empresa.perdida", "empresa.reativada"]})
    assert w.status_code == 201, w.text
    chave = gerar_chave(client, h)

    assert evento(client, chave, "empresas").status_code == 422
    r = evento(client, chave, "empresas", codigo_externo="ERP-9", nome="Loja Lua", valor_mensal="800.00",
               renovacao_em="2027-01-10")
    assert r.status_code == 201, r.text
    e = r.json()
    assert (e["nome"], e["valor_mensal"], e["renovacao_em"]) == ("Loja Lua", 800.0, "2027-01-10")
    criar_contato(client, h, empresa_id=e["id"])
    _antigo(dono, e["id"])

    r = evento(client, chave, "empresas", codigo_externo="ERP-9", situacao="perdida")
    assert r.status_code == 422  # sem motivo
    r = evento(client, chave, "empresas", codigo_externo="ERP-9", situacao="perdida", motivo_perda="preco")
    assert r.status_code == 200, r.text
    assert (r.json()["situacao"], r.json()["ativa"]) == ("perdida", False)
    assert sql(dono, "select count(*) from contatos where ativo")[0][0] == 0
    r = evento(client, chave, "empresas", codigo_externo="ERP-9", situacao="ativa", valor_mensal="900.00")
    assert r.status_code == 200 and r.json()["situacao"] == "ativa" and r.json()["valor_mensal"] == 900.0
    assert sql(dono, "select count(*) from contatos where ativo")[0][0] == 1

    origens = [o for (o,) in sql(dono, "select origem from empresa_historico where empresa_id = :e and tipo in "
                                       "('perdida', 'reativada') order by id", e=e["id"])]
    assert origens == ["api", "api"]
    eventos = [ev for (ev,) in sql(dono, "select evento from webhook_entregas order by criado_em")]
    assert eventos == ["empresa.perdida", "empresa.reativada"]
    corpo = sql(dono, "select corpo from webhook_entregas where evento = 'empresa.perdida'")[0][0]
    assert corpo["dados"]["empresa"]["codigo_externo"] == "ERP-9" and corpo["dados"]["motivo"] == "preco"


def test_toqqiai_perdas_e_saude(client, dono, admin):
    h = admin["h"]
    e = criar_empresa(client, h, nome="Mercado Azul", valor_mensal="1000.00")
    criar_empresa(client, h, nome="Padaria Sol", valor_mensal="500.00")
    _antigo(dono, e["id"])
    client.post(f"{API}/empresas/{e['id']}/perda", headers=h, json={"motivo_perda": "preco"})
    ctx = contexto_de(admin)

    r = ferramentas.executar(ctx, "desfecho", {})
    assert "erro" not in r, r
    assert "Mercado Azul" in str(r)

    r = ferramentas.executar(ctx, "saude_empresas", {})
    assert "erro" not in r, r
    assert "Padaria Sol" in str(r) or r.get("faixas")


def test_perda_pela_planilha(client, dono, admin):
    h = admin["h"]
    linhas = [["Nome", "E-mail", "Empresa", "Data do cancelamento", "Motivo do cancelamento"],
              ["Ana", "ana@lua.com.br", "Loja Lua", "01/09/2026", "Achou caro"],
              ["Bia", "bia@lua.com.br", "Loja Lua", "", ""],
              ["Caio", "caio@sol.com.br", "Sol Ltda", "02/09/2026", "Mudou de ramo"],
              ["Duda", "duda@x.com.br", "", "02/09/2026", ""]]
    conteudo = "\r\n".join(";".join(x) for x in linhas).encode("utf-8-sig")
    d = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("c.csv", conteudo)}).json()
    assert d["mapeamento_sugerido"]["Data do cancelamento"] == "perdida_em"
    assert d["mapeamento_sugerido"]["Motivo do cancelamento"] == "motivo_perda"
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "ignorar_com_problema": True}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert any("2 empresas serão marcadas como perdidas" in a for a in c["avisos"])
    assert any("sem empresa" in p["motivo"] for p in c["problemas"])
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200, r.text
    assert r.json()["empresas_perdidas"] == 2
    emp = {n: (str(p), m, det) for n, p, m, det in sql(
        dono, "select nome, perdida_em, motivo_perda, motivo_detalhe from empresas order by nome")}
    assert emp["Loja Lua"] == ("2026-09-01", "preco", "Achou caro")
    assert emp["Sol Ltda"] == ("2026-09-02", "outro", "Mudou de ramo")
    assert sql(dono, "select count(*) from contatos where ativo")[0][0] == 0
    origens = {o for (o,) in sql(dono, "select origem from empresa_historico where tipo = 'perdida'")}
    assert origens == {"importacao"}


def test_corrigir_a_perda(client, dono, admin):
    h = admin["h"]
    e = criar_empresa(client, h, nome="Mercado Azul")
    _antigo(dono, e["id"])
    client.post(f"{API}/empresas/{e['id']}/perda", headers=h, json={"motivo_perda": "preco"})
    r = client.patch(f"{API}/empresas/{e['id']}/perda", headers=h,
                     json={"perdida_em": "2026-08-01", "motivo_perda": "concorrente", "motivo_detalhe": "Foi para a X"})
    assert r.status_code == 200, r.text
    assert (r.json()["perdida_em"], r.json()["motivo_perda"]) == ("2026-08-01", "concorrente")
    (data, motivo, n), = sql(dono, "select max(data)::text, max(motivo), count(*) from empresa_historico "
                                   "where empresa_id = :e and tipo = 'perdida'", e=e["id"])
    assert (data, motivo, n) == ("2026-08-01", "concorrente", 1)  # a mesma linha, corrigida
    assert client.patch(f"{API}/empresas/{e['id']}/perda", headers=h, json={"perdida_em": "2024-01-01"}).status_code == 422
    assert client.patch(f"{API}/empresas/{e['id']}/perda", headers=h, json={"motivo_perda": "outro",
                                                                          "motivo_detalhe": ""}).status_code == 422
    outra = criar_empresa(client, h, nome="Ativa")
    assert client.patch(f"{API}/empresas/{outra['id']}/perda", headers=h, json={"motivo_perda": "preco"}).status_code == 409
    assert sql(dono, "select count(*) from auditoria where evento = 'empresa_perda_corrigida'")[0][0] == 1
