"""Correções pequenas da etapa 5f: os avisos da importação ("Será criada 1 empresa: X.", "A, B e C.", "e mais 15.",
"(linhas 7, 9 e 12)", "e mais 4") e o `teste_ate` do cadastro, da Plataforma e do "+14 dias" pelo relógio das regras."""
from datetime import datetime, timedelta, timezone

import pytest
from util import API, FUSO, conta_pronta, fixar_relogio, sql

from toqqi.core.config import config
from toqqi.modulos.importacao.respostas import _linhas_texto
from toqqi.modulos.importacao.servico import aviso_criados


@pytest.mark.parametrize("campo,nomes,esperado", [
    ("empresa", ["Atacado Norte"], "Será criada 1 empresa: Atacado Norte."),
    ("empresa", ["A", "B"], "Serão criadas 2 empresas: A e B."),
    ("empresa", ["A", "B", "C", "D", "E"], "Serão criadas 5 empresas: A, B, C, D e E."),
    ("empresa", [f"E{i}" for i in range(20)], "Serão criadas 20 empresas: E0, E1, E2, E3, E4 e mais 15."),
    ("empresa", ["Alfa Ltda."], "Será criada 1 empresa: Alfa Ltda."),  # um ponto só
    ("grupo", ["Sul"], "Será criado 1 grupo: Sul."),
    ("segmento", ["Varejo", "Atacado", "Indústria"], "Serão criados 3 segmentos: Varejo, Atacado e Indústria."),
    ("cargo", ["Gerente"], "Será criado 1 cargo: Gerente."),
    ("perfil", ["Decisor", "Usuário"], "Serão criados 2 perfis: Decisor e Usuário."),
    ("responsavel", [f"R{i}" for i in range(7)], "Serão criados 7 responsáveis: R0, R1, R2, R3, R4 e mais 2."),
])
def test_aviso_dos_cadastros_criados(campo, nomes, esperado):
    assert aviso_criados(campo, nomes) == esperado


@pytest.mark.parametrize("numeros,esperado", [
    ([7], "linha 7"),
    ([7, 9], "linhas 7 e 9"),
    ([7, 9, 12], "linhas 7, 9 e 12"),
    (list(range(2, 12)), "linhas 2, 3, 4, 5, 6, 7, 8, 9, 10 e 11"),
    (list(range(2, 16)), "linhas 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 e mais 4"),
])
def test_linhas_da_importacao_de_respostas(numeros, esperado):
    assert _linhas_texto(numeros) == esperado


def test_importacao_de_contatos_avisa_as_empresas(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    linhas = [["Nome", "E-mail", "Empresa"], ["Paula", "paula@n.com.br", "Atacado Norte"],
              ["Marcos", "marcos@n.com.br", "Mercearia Sul"]]
    conteudo = "\r\n".join(";".join(x) for x in linhas).encode("utf-8-sig")
    d = client.post(f"{API}/importacao/analisar", headers=a["h"], files={"arquivo": ("c.csv", conteudo)}).json()
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "atualizar_existentes": False}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=a["h"], json=corpo).json()
    assert "Serão criadas 2 empresas: Atacado Norte e Mercearia Sul." in c["avisos"]


MOMENTO = datetime(2026, 3, 10, 9, 30, tzinfo=FUSO)


def _teste_ate(dono, conta_id: int) -> datetime:
    return sql(dono, "select teste_ate from contas where id = :c", c=conta_id)[0][0]


def test_teste_ate_pelo_relogio_das_regras(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, MOMENTO)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert _teste_ate(dono, a["conta"]["id"]) == MOMENTO + timedelta(days=14)
    # Plataforma: criar conta em teste e "+14 dias" (a partir de agora, pelo relógio das regras, já que o teste acabou)
    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "root@toqqi.com")
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    r = client.post(f"{API}/plataforma/contas", headers=root["h"],
                    json={"empresa": "Beta", "admin_nome": "Bia", "admin_email": "bia@beta.com.br",
                          "admin_senha": "Senha@123", "situacao": "teste"})
    assert r.status_code == 201, r.text
    beta = r.json()["id"]
    assert _teste_ate(dono, beta) == MOMENTO + timedelta(days=14)
    depois = MOMENTO + timedelta(days=30)
    fixar_relogio(monkeypatch, depois)
    r = client.post(f"{API}/plataforma/contas/{beta}/estender-teste", headers=root["h"], json={"dias": 14})
    assert r.status_code == 200, r.text
    assert _teste_ate(dono, beta) == depois + timedelta(days=14)
    assert _teste_ate(dono, beta).tzinfo is not None and depois.astimezone(timezone.utc).year == 2026
