"""Etapa 5g: Plataforma › Parâmetros — padrões de hoje com a tabela vazia, variável como padrão (origem ambiente) e o
banco vencendo, igual ao padrão apaga a linha, cache de 30 s (relógio falso) e falha de leitura; rotas: GET (forma,
ordem, versão, origens), prévia (impactos, exemplos, `precisa_confirmar`), PUT (validação, ordem dos planos, chave a
mais ou a menos, nada mudou não grava, 409 de confirmação e de versão, histórico, evento global, teste do modelo),
histórico (ordem, filtro, páginas), só superadmin e `GET /publico/planos`."""
import logging
import threading
from datetime import datetime
import time
from decimal import Decimal

import pytest
from conftest import APP_URL
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from util import (
    API,
    conta_pronta,
    definir_plano,
    encher_contatos,
    gravar_parametro,
    grupo_parametros,
    salvar_parametros,
    sql,
    superadmin,
    usar_cota,
)

from toqqi.core import db, ia, parametros, relogio
from toqqi.core.config import Config, config
from toqqi.core.ia_texto import memoria
from toqqi.core.rate_limit import limiter

PADROES = {
    "planos": {"planos.essencial.preco": "149.00", "planos.essencial.contatos": 300,
               "planos.profissional.preco": "349.00", "planos.profissional.contatos": 1500,
               "planos.empresa.preco": "799.00", "planos.empresa.contatos": 5000,
               "planos.desconto.pix": 3, "planos.desconto.anual": 10,
               "planos.personalizado.base": "99.00", "planos.personalizado.ate_1500": "18.00",
               "planos.personalizado.ate_10000": "11.00", "planos.personalizado.acima": "6.00",
               "planos.personalizado.ia_500": "30.00", "planos.personalizado.ia_2000": "120.00",
               "planos.personalizado.ia_5000": "250.00"},
    "ia": {"ia.cota.essencial": 100, "ia.cota.profissional": 500, "ia.cota.empresa": 2000, "ia.cota.cortesia": 200,
           "ia.cota.teste": 50,
           "ia.modelo.rapido": "gpt-6-luna", "ia.esforco.rapido": "none", "ia.analises.rapido": 1,
           "ia.modelo.equilibrado": "gpt-6-luna", "ia.esforco.equilibrado": "low", "ia.analises.equilibrado": 1,
           "ia.modelo.detalhado": "gpt-6-sol", "ia.esforco.detalhado": "low", "ia.analises.detalhado": 3,
           "ia.teto.essencial": 1000, "ia.teto.profissional": 5000, "ia.teto.empresa": 15000,
           "ia.teto.cortesia": 2000, "ia.teto.teste": 500},
    "whatsapp": {"whatsapp.franquia.essencial": None, "whatsapp.franquia.profissional": None,
                 "whatsapp.franquia.empresa": None, "whatsapp.franquia.personalizado": None,
                 "whatsapp.franquia.cortesia": None, "whatsapp.franquia.teste": None},
    "teste": {"teste.dias": 14, "teste.plano": "profissional", "teste.exclusao_automatica": "simular"},
}

@pytest.fixture
def root(client):
    return superadmin(client)


@pytest.fixture
def config_limpa(monkeypatch):
    """Uma configuração lida só do ambiente dos testes (sem os `monkeypatch.setattr(config(), ...)` de outros testes,
    que marcam as variáveis como definidas em `model_fields_set`)."""
    fresca = Config()
    monkeypatch.setattr(parametros, "config", lambda: fresca)
    return fresca


# ---- padrões e leitura -------------------------------------------------------------------------------------

def test_tabela_vazia_tudo_como_hoje(client, root, config_limpa):
    r = client.get(f"{API}/plataforma/parametros", headers=root["h"])
    assert r.status_code == 200
    grupos = r.json()["grupos"]
    assert [(g["grupo"], g["rotulo"]) for g in grupos] == [
        ("planos", "Planos"), ("ia", "IA"), ("whatsapp", "WhatsApp automático"), ("teste", "Teste e cortesia")]
    for g in grupos:
        assert set(g) == {"grupo", "rotulo", "versao", "alterado_em", "alterado_por", "valores", "padroes", "origens"}
        assert (g["versao"], g["alterado_em"], g["alterado_por"]) == (0, None, None)
        assert g["valores"] == g["padroes"] == PADROES[g["grupo"]]
        assert list(g["valores"]) == list(PADROES[g["grupo"]])  # a ordem das chaves
        assert set(g["origens"].values()) == {"codigo"}
    assert set(parametros.CAMPOS) == {c for g in PADROES.values() for c in g}


def test_variavel_vira_o_padrao_e_o_banco_vence(client, root, dono, monkeypatch):
    fresca = Config()
    monkeypatch.setattr(parametros, "config", lambda: fresca)
    monkeypatch.setattr(fresca, "IA_COTA_CORTESIA", 42)
    monkeypatch.setattr(fresca, "IA_MODELO_DETALHADO", "gpt-5.1")
    monkeypatch.setattr(fresca, "EXCLUSAO_AUTOMATICA", "ligada")
    ia_ = grupo_parametros(client, root["h"], "ia")
    assert (ia_["padroes"]["ia.cota.cortesia"], ia_["valores"]["ia.modelo.detalhado"]) == (42, "gpt-5.1")
    assert ia_["origens"]["ia.cota.cortesia"] == ia_["origens"]["ia.modelo.detalhado"] == "ambiente"
    assert ia_["origens"]["ia.modelo.rapido"] == "codigo"
    assert grupo_parametros(client, root["h"], "teste")["valores"]["teste.exclusao_automatica"] == "ligada"
    assert parametros.valor("ia.cota.cortesia") == 42 and parametros.origem("ia.cota.cortesia") == "ambiente"

    r = salvar_parametros(client, root["h"], "ia", {"ia.cota.cortesia": 7})
    assert r.status_code == 200, r.text
    assert (r.json()["valores"]["ia.cota.cortesia"], r.json()["padroes"]["ia.cota.cortesia"],
            r.json()["origens"]["ia.cota.cortesia"]) == (7, 42, "banco")
    assert parametros.valor("ia.cota.cortesia") == 7
    assert sql(dono, "select chave, valor from parametros") == [("ia.cota.cortesia", 7)]
    # igual ao padrão: a linha sai e a chave volta a seguir a variável
    r = salvar_parametros(client, root["h"], "ia", {"ia.cota.cortesia": 42})
    assert r.status_code == 200 and r.json()["origens"]["ia.cota.cortesia"] == "ambiente"
    assert sql(dono, "select count(*) from parametros") == [(0,)]
    assert [m for (m,) in sql(dono, "select mudancas from parametros_historico order by id")] == [
        [{"chave": "ia.cota.cortesia", "de": 42, "para": 7}], [{"chave": "ia.cota.cortesia", "de": 7, "para": 42}]]


def test_cache_de_30_segundos(client, root, dono, monkeypatch):
    agora = [1000.0]
    monkeypatch.setattr(parametros, "monotonico", lambda: agora[0])
    assert parametros.valor("teste.dias") == 14
    gravar_parametro(dono, "teste.dias", 7, limpar_cache=False)  # outro processo
    agora[0] += 29
    assert parametros.valor("teste.dias") == 14
    agora[0] += 1.5
    assert parametros.valor("teste.dias") == 7
    # quem salva vê na hora (sem o relógio andar)
    r = salvar_parametros(client, root["h"], "teste", {"teste.dias": 9})
    assert r.status_code == 200 and parametros.valor("teste.dias") == 9
    assert client.get(f"{API}/publico/planos").json()["teste"]["dias"] == 9


def _relogio(monkeypatch, inicio: float = 1000.0) -> list[float]:
    """Relógio monotônico falso do cache (agora[0] anda quando o teste quer)."""
    agora = [inicio]
    monkeypatch.setattr(parametros, "monotonico", lambda: agora[0])
    return agora


def _sem_leitura(dono):
    """O papel da aplicação perde o SELECT em `parametros` (como o banco fora do ar para o cache), até o fim do bloco."""
    class Bloco:
        def __enter__(self):
            sql(dono, "revoke select on parametros from toqqi_app")

        def __exit__(self, *_):
            sql(dono, "grant select on parametros to toqqi_app")
    return Bloco()


def test_falha_ao_ler_usa_a_ultima_espera_5_s_e_sem_nenhuma_sobe(dono, monkeypatch, caplog):
    agora = _relogio(monkeypatch)
    gravar_parametro(dono, "teste.dias", 7)
    assert parametros.valor("teste.dias") == 7
    with _sem_leitura(dono):
        agora[0] += 31  # vencido
        with caplog.at_level(logging.WARNING, logger="toqqi.parametros"):
            assert [parametros.valor("teste.dias") for _ in range(3)] == [7, 7, 7]
            agora[0] += 4.9
            assert parametros.valor("teste.dias") == 7
            assert caplog.text.count("última leitura") == 1  # uma tentativa só: espera 5 s para tentar de novo
            agora[0] += 0.2
            assert parametros.valor("teste.dias") == 7
            assert caplog.text.count("última leitura") == 2
        # sem nenhuma leitura boa, sobe (cair no padrão em silêncio cobraria o preço errado), também na espera
        parametros.limpar()
        for _ in range(2):
            with pytest.raises(Exception):  # noqa: B017 - a falha do banco (ou a da espera depois dela)
                parametros.valor("planos.essencial.preco")
    agora[0] += 5.1
    assert parametros.valor("teste.dias") == 7  # o banco voltou


def test_cache_vencido_nao_espera_pelo_pool_de_quem_chamou(dono, monkeypatch):
    """Quem lê os parâmetros pode estar dentro de `em_conta`, segurando uma conexão do pool principal: com todas elas
    presas, a leitura do cache vencido vai por um pool próprio e ninguém espera por conexão."""
    agora = _relogio(monkeypatch)
    gravar_parametro(dono, "teste.dias", 7)
    assert parametros.valor("teste.dias") == 7
    pequeno = create_engine(APP_URL, pool_size=2, max_overflow=0, pool_timeout=2)
    monkeypatch.setattr(db, "_fabrica", lambda: sessionmaker(pequeno, expire_on_commit=False))
    sql(dono, "update parametros set valor = '8' where chave = 'teste.dias'")  # outro processo
    agora[0] += 31
    barreira = threading.Barrier(2)
    lidos, tempos = [], []

    def rota(conta_id: int):
        with db.em_conta(conta_id):  # a conexão do pool principal fica presa até o fim
            barreira.wait(5)
            t0 = time.monotonic()
            lidos.append(parametros.valor("teste.dias"))
            tempos.append(time.monotonic() - t0)

    threads = [threading.Thread(target=rota, args=(i,)) for i in (1, 2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
    finally:
        pequeno.dispose()
    assert len(tempos) == 2 and max(tempos) < 1, tempos
    assert set(lidos) <= {7, 8} and parametros.valor("teste.dias") == 8


def test_uma_leitura_por_vez_e_as_outras_seguem_com_os_ultimos_valores(dono, monkeypatch):
    _relogio(monkeypatch)
    gravar_parametro(dono, "teste.dias", 7)
    assert parametros.valor("teste.dias") == 7
    original = parametros._ler_do_banco
    entrou, solta, chamadas = threading.Event(), threading.Event(), []

    def lenta():
        chamadas.append(1)
        entrou.set()
        assert solta.wait(10)
        return original()

    monkeypatch.setattr(parametros, "_ler_do_banco", lenta)
    gravar_parametro(dono, "teste.dias", 8)  # limpa o cache: a próxima leitura vai ao banco
    leitora = threading.Thread(target=parametros.valor, args=("teste.dias",))
    leitora.start()
    try:
        assert entrou.wait(5)
        t0 = time.monotonic()
        assert [parametros.valor("teste.dias") for _ in range(20)] == [7] * 20  # sem esperar a que está lendo
        assert time.monotonic() - t0 < 1 and len(chamadas) == 1
    finally:
        solta.set()
        leitora.join(10)
    assert parametros.valor("teste.dias") == 8 and len(chamadas) == 1


def test_invalidar_durante_a_leitura_faz_ler_de_novo(dono, monkeypatch):
    """Quem salva limpa o cache enquanto outra thread lia (com o valor de antes): a leitura dela não vale 30 s."""
    _relogio(monkeypatch)
    gravar_parametro(dono, "teste.dias", 7)
    original = parametros._ler_do_banco
    leu, solta = threading.Event(), threading.Event()

    def devagar():
        linhas = original()  # já leu o 7
        leu.set()
        assert solta.wait(10)
        return linhas

    monkeypatch.setattr(parametros, "_ler_do_banco", devagar)
    leitora = threading.Thread(target=parametros.valor, args=("teste.dias",))
    leitora.start()
    try:
        assert leu.wait(5)
        gravar_parametro(dono, "teste.dias", 9)  # salvou e limpou o cache no meio da leitura
    finally:
        solta.set()
        leitora.join(10)
    monkeypatch.setattr(parametros, "_ler_do_banco", original)
    assert parametros.valor("teste.dias") == 9


def test_cache_aquecido_ao_subir_a_api(app, dono):
    """A API lê os parâmetros ao subir: a primeira rota não espera o banco por eles (com o banco fora logo depois,
    valem os lidos ao subir)."""
    gravar_parametro(dono, "teste.dias", 8)
    parametros.limpar()
    with TestClient(app):
        pass
    with _sem_leitura(dono):
        assert parametros.valor("teste.dias") == 8


# ---- linhas fora do formato (só gravadas à mão) -------------------------------------------------------------

def test_linha_fora_do_formato_vale_o_padrao(dono, caplog):
    gravar_parametro(dono, "teste.dias", "sete")
    with caplog.at_level(logging.ERROR, logger="toqqi.parametros"):
        assert parametros.valor("teste.dias") == 14
    assert "teste.dias" in caplog.text


def test_preco_fora_do_formato_e_erro_e_nunca_o_padrao(dono, monkeypatch, caplog):
    """No preço, a linha fora do formato não vale o padrão (cobraria o preço errado): fica o último valor bom lido ou,
    sem nenhum, o erro. As outras chaves seguem a leitura nova."""
    gravar_parametro(dono, "planos.essencial.preco", "159.00")
    assert parametros.valor("planos.essencial.preco") == Decimal("159.00")
    gravar_parametro(dono, "planos.essencial.preco", "159,00")
    gravar_parametro(dono, "teste.dias", 8)
    with caplog.at_level(logging.ERROR, logger="toqqi.parametros"):
        assert parametros.valor("planos.essencial.preco") == Decimal("159.00")
    assert "planos.essencial.preco" in caplog.text
    assert parametros.valor("teste.dias") == 8
    parametros.limpar()  # o processo recomeçou: nenhum valor bom lido
    with pytest.raises(Exception, match="planos.essencial.preco"):
        parametros.valor("planos.essencial.preco")
    assert parametros.valor("planos.profissional.preco") == Decimal("349.00") and parametros.valor("teste.dias") == 8


@pytest.mark.parametrize("bruto,esperado", [
    (2, 2), (None, None), ("2", 300), (True, 300), (2.5, 300), (2.0, 300), (0, 300), (-1, 300), (1_000_001, 300),
    ([2], 300), ({"n": 2}, 300)])
def test_limite_de_contatos_fora_do_formato_vale_o_padrao_no_banco_e_no_python(dono, bruto, esperado):
    """A função `limite_contatos` (gatilho e API) e o Python aceitam as mesmas linhas: número inteiro de 1 a 1.000.000
    ou null; o resto vale o padrão nos dois."""
    gravar_parametro(dono, "planos.essencial.contatos", bruto)
    assert sql(dono, "select limite_contatos('essencial', 'ativa')") == [(esperado,)]
    assert parametros.valor("planos.essencial.contatos") == esperado


def test_put_apaga_as_linhas_fora_do_formato_do_grupo(client, root, dono):
    gravar_parametro(dono, "teste.dias", "sete")
    gravar_parametro(dono, "teste.outra", 1)  # chave que o código não conhece
    gravar_parametro(dono, "ia.cota.essencial", "cem")  # de outro grupo: fica
    r = salvar_parametros(client, root["h"], "teste", {"teste.plano": "essencial"})
    assert r.status_code == 200 and r.json()["valores"]["teste.dias"] == 14
    assert sql(dono, "select chave from parametros order by chave") == [("ia.cota.essencial",), ("teste.plano",)]
    assert [m for (m,) in sql(dono, "select mudancas from parametros_historico")] == [
        [{"chave": "teste.plano", "de": "profissional", "para": "essencial"}]]
    # sem mudança nenhuma, também apaga (sem histórico)
    gravar_parametro(dono, "teste.dias", "sete")
    r = salvar_parametros(client, root["h"], "teste", {})
    assert r.status_code == 200 and r.json()["versao"] == 1
    assert sql(dono, "select chave from parametros order by chave") == [("ia.cota.essencial",), ("teste.plano",)]
    assert sql(dono, "select count(*) from parametros_historico") == [(1,)]


# ---- PUT: validação ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("grupo,mudancas,campo,mensagem", [
    ("planos", {"planos.essencial.preco": "4.99"}, "planos.essencial.preco",
     "Use um valor entre R$ 5,00 e R$ 99.999,99."),
    ("planos", {"planos.empresa.preco": "100000.00"}, "planos.empresa.preco",
     "Use um valor entre R$ 5,00 e R$ 99.999,99."),
    ("planos", {"planos.essencial.preco": "149.999"}, "planos.essencial.preco", "Use no máximo 2 casas decimais."),
    ("planos", {"planos.essencial.preco": "149,90"}, "planos.essencial.preco", "Use um valor em reais com ponto"),
    ("planos", {"planos.essencial.preco": True}, "planos.essencial.preco", "Use um valor em reais com ponto"),
    ("planos", {"planos.profissional.preco": "149.00"}, "planos.profissional.preco",
     "O preço do Profissional precisa ser maior que o do Essencial."),
    ("planos", {"planos.empresa.preco": 300}, "planos.empresa.preco",
     "O preço do Empresa precisa ser maior que o do Profissional."),
    ("planos", {"planos.essencial.contatos": 0}, "planos.essencial.contatos", "Use um número inteiro de 1 a 1.000.000"),
    ("planos", {"planos.essencial.contatos": "300"}, "planos.essencial.contatos", "Use um número inteiro de 1"),
    ("planos", {"planos.essencial.contatos": 2000}, "planos.profissional.contatos",
     "O limite do Profissional não pode ser menor que o do Essencial."),
    ("planos", {"planos.essencial.contatos": None}, "planos.profissional.contatos",
     "O limite do Profissional não pode ser menor que o do Essencial."),
    ("planos", {"planos.empresa.contatos": 1000}, "planos.empresa.contatos",
     "O limite do Empresa não pode ser menor que o do Profissional."),
    ("ia", {"ia.cota.essencial": -1}, "ia.cota.essencial", "Use um número inteiro de 0 a 100.000."),
    ("ia", {"ia.cota.essencial": "100"}, "ia.cota.essencial", "Use um número inteiro de 0 a 100.000."),
    ("ia", {"ia.cota.cortesia": True}, "ia.cota.cortesia", "Use um número inteiro de 0 a 100.000."),
    ("ia", {"ia.cota.empresa": 2000.0}, "ia.cota.empresa", "Use um número inteiro de 0 a 100.000."),
    ("ia", {"ia.analises.rapido": 0}, "ia.analises.rapido", "Use um número inteiro de 1 a 10."),
    ("ia", {"ia.analises.detalhado": 11}, "ia.analises.detalhado", "Use um número inteiro de 1 a 10."),
    ("ia", {"ia.analises.rapido": 2}, "ia.analises.equilibrado",
     "O Equilibrado não pode gastar menos análises que o Rápido."),
    ("ia", {"ia.analises.equilibrado": 4}, "ia.analises.detalhado",
     "O Mais detalhado não pode gastar menos análises que o Equilibrado."),
    ("ia", {"ia.teto.teste": 1_000_001}, "ia.teto.teste", "Use um número inteiro de 0 a 1.000.000."),
    ("ia", {"ia.modelo.rapido": "gpt 5"}, "ia.modelo.rapido", "Informe o nome do modelo"),
    ("ia", {"ia.modelo.rapido": ""}, "ia.modelo.rapido", "Informe o nome do modelo"),
    ("ia", {"ia.esforco.rapido": "turbo"}, "ia.esforco.rapido", "Escolha um esforço da lista"),
    ("whatsapp", {"whatsapp.franquia.teste": 100_001}, "whatsapp.franquia.teste",
     "Use um número inteiro de 0 a 100.000, ou marque “Sem limite”."),
    ("whatsapp", {"whatsapp.franquia.teste": "20"}, "whatsapp.franquia.teste", "Use um número inteiro de 0"),
    ("planos", {"planos.desconto.pix": 31}, "planos.desconto.pix", "Use um número inteiro de 0 a 30."),
    ("planos", {"planos.desconto.anual": 51}, "planos.desconto.anual", "Use um número inteiro de 0 a 50."),
    ("planos", {"planos.personalizado.base": "4.99"}, "planos.personalizado.base", "Use um valor entre R$ 5,00"),
    ("planos", {"planos.personalizado.ate_10000": "19.00"}, "planos.personalizado.ate_10000",
     "O preço a cada 100 contatos não pode subir na faixa seguinte."),
    ("planos", {"planos.personalizado.ia_2000": "30.00"}, "planos.personalizado.ia_2000",
     "O pacote maior do ToqqiAI precisa custar mais que o menor."),
    ("teste", {"teste.dias": 91}, "teste.dias", "Use um número inteiro de 1 a 90."),
    ("teste", {"teste.dias": 0}, "teste.dias", "Use um número inteiro de 1 a 90."),
    ("teste", {"teste.plano": "ouro"}, "teste.plano", "Escolha um dos planos"),
    ("teste", {"teste.exclusao_automatica": "desligada"}, "teste.exclusao_automatica", "Escolha “ligada” ou"),
])
def test_validacao(client, root, dono, grupo, mudancas, campo, mensagem):
    for rota in ("previa", "put"):
        if rota == "put":
            r = salvar_parametros(client, root["h"], grupo, mudancas)
        else:
            valores = {**grupo_parametros(client, root["h"], grupo)["valores"], **mudancas}
            r = client.post(f"{API}/plataforma/parametros/{grupo}/previa", headers=root["h"], json={"valores": valores})
        assert r.status_code == 422, r.text
        erro = r.json()["erro"]
        assert erro["codigo"] == "dados_invalidos" and erro["campos"][campo].startswith(mensagem), erro
    assert sql(dono, "select count(*) from parametros_historico") == [(0,)]


def test_chaves_que_faltam_ou_sobram_e_grupo_desconhecido(client, root):
    g = grupo_parametros(client, root["h"], "teste")
    url = f"{API}/plataforma/parametros/teste"
    sem_uma = {k: v for k, v in g["valores"].items() if k != "teste.dias"}
    for valores in (sem_uma, {**g["valores"], "teste.outra": 1}, {**g["valores"], "planos.essencial.preco": "1.00"}):
        r = client.put(url, headers=root["h"], json={"versao": 0, "valores": valores})
        assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"valores"}, r.text
    assert "teste.dias" in client.put(url, headers=root["h"], json={"versao": 0, "valores": sem_uma}).json()[
        "erro"]["campos"]["valores"]
    r = client.put(f"{API}/plataforma/parametros/outro", headers=root["h"], json={"versao": 0, "valores": {}})
    assert r.status_code == 404
    r = client.post(f"{API}/plataforma/parametros/outro/previa", headers=root["h"], json={"valores": {}})
    assert r.status_code == 404


def test_preco_normalizado_e_espacos_do_modelo(client, root, dono):
    r = salvar_parametros(client, root["h"], "planos", {"planos.essencial.preco": 159.9})
    assert r.status_code == 200 and r.json()["valores"]["planos.essencial.preco"] == "159.90"
    assert sql(dono, "select valor from parametros where chave = 'planos.essencial.preco'") == [("159.90",)]
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.rapido": "  gpt-6-luna  "})
    assert r.status_code == 200 and r.json()["versao"] == 0  # igual ao padrão depois de tirar os espaços: nada muda


# ---- PUT: gravação, confirmação, versão, histórico e evento ------------------------------------------------------

def test_put_grava_historico_e_evento_global(client, root, dono):
    r = salvar_parametros(client, root["h"], "planos", {"planos.essencial.preco": "159.90"}, confirmar=False)
    assert r.status_code == 409 and r.json()["erro"] == {
        "codigo": "confirmacao_necessaria", "mensagem": "Confirme a mudança antes de salvar.", "campos": {}}
    assert sql(dono, "select count(*) from parametros") == [(0,)]
    r = salvar_parametros(client, root["h"], "planos", {"planos.essencial.preco": "159.90"})
    assert r.status_code == 200, r.text
    g = r.json()
    assert (g["grupo"], g["versao"], g["alterado_por"]) == ("planos", 1, "root@toqqi.com") and g["alterado_em"]
    assert (g["valores"]["planos.essencial.preco"], g["origens"]["planos.essencial.preco"]) == ("159.90", "banco")
    assert "testados" not in g
    mudancas = [{"chave": "planos.essencial.preco", "de": "149.00", "para": "159.90"}]
    assert sql(dono, "select id, grupo, por, mudancas from parametros_historico") == [
        (1, "planos", "root@toqqi.com", mudancas)]
    assert sql(dono, "select gravidade, detalhe from auditoria where evento = 'parametros_alterados' "
                     "and conta_id is null") == [("atencao", {"grupo": "planos", "por": "root@toqqi.com",
                                                              "mudancas": mudancas})]
    assert grupo_parametros(client, root["h"], "planos") == {k: v for k, v in g.items()}
    # nada mudou: 200 sem gravar
    r = salvar_parametros(client, root["h"], "planos", {})
    assert r.status_code == 200 and r.json()["versao"] == 1
    assert sql(dono, "select count(*) from parametros_historico") == [(1,)]
    # versão velha: 409, nada gravado
    r = salvar_parametros(client, root["h"], "planos", {"planos.essencial.preco": "169.90"}, versao=0)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "parametros_alterados"
    assert r.json()["erro"]["mensagem"].startswith("Outra pessoa mudou estes parâmetros enquanto você editava.")
    assert sql(dono, "select valor from parametros") == [("159.90",)]
    # a versão é por grupo
    assert salvar_parametros(client, root["h"], "teste", {"teste.dias": 7}).json()["versao"] == 2
    assert grupo_parametros(client, root["h"], "planos")["versao"] == 1


@pytest.mark.parametrize("grupo,mudancas,confirmar", [
    ("planos", {"planos.empresa.preco": "899.00"}, True),
    ("planos", {"planos.essencial.contatos": 250}, True),
    ("planos", {"planos.essencial.contatos": 400}, False),
    ("planos", {"planos.empresa.contatos": 4000}, True),
    ("planos", {"planos.empresa.contatos": None}, False),  # número → sem limite: aumentou
    ("planos", {"planos.desconto.pix": 5}, True),
    ("planos", {"planos.personalizado.base": "109.00"}, True),
    ("ia", {"ia.cota.essencial": 90}, True),
    ("ia", {"ia.cota.essencial": 110}, False),
    ("ia", {"ia.teto.teste": 400}, True),
    ("ia", {"ia.analises.detalhado": 4}, True),
    ("ia", {"ia.analises.detalhado": 1}, False),
    ("ia", {"ia.esforco.rapido": "low"}, False),
    ("whatsapp", {"whatsapp.franquia.cortesia": 100}, True),  # sem limite → número: diminuiu
    ("teste", {"teste.exclusao_automatica": "ligada"}, True),
    ("teste", {"teste.dias": 7, "teste.plano": "essencial"}, False),
])
def test_o_que_pede_confirmacao(client, root, grupo, mudancas, confirmar):
    valores = {**grupo_parametros(client, root["h"], grupo)["valores"], **mudancas}
    r = client.post(f"{API}/plataforma/parametros/{grupo}/previa", headers=root["h"], json={"valores": valores})
    assert r.status_code == 200 and r.json()["precisa_confirmar"] is confirmar
    r = salvar_parametros(client, root["h"], grupo, mudancas, confirmar=False)
    assert r.status_code == (409 if confirmar else 200), r.text


# ---- prévia -----------------------------------------------------------------------------------------------

def _conta(client, dono, email: str, nome: str, plano: str, situacao: str = "ativa") -> int:
    c = conta_pronta(client, email, empresa=nome)["conta"]["id"]
    definir_plano(dono, c, plano, situacao)
    return c


def _previa(client, h, grupo: str, mudancas: dict) -> dict:
    valores = {**grupo_parametros(client, h, grupo)["valores"], **mudancas}
    r = client.post(f"{API}/plataforma/parametros/{grupo}/previa", headers=h, json={"valores": valores})
    assert r.status_code == 200, r.text
    return r.json()


def test_previa_dos_contatos_e_do_preco(client, root, dono):
    alfa = _conta(client, dono, "ana@alfa.com.br", "Alfa", "essencial")
    beta = _conta(client, dono, "bia@beta.com.br", "Beta", "essencial", "teste")
    gama = _conta(client, dono, "gil@gama.com.br", "Gama", "essencial", "cortesia")
    delta = _conta(client, dono, "dan@delta.com.br", "Delta", "profissional")
    for conta, n in ((alfa, 3), (beta, 5), (gama, 9), (delta, 9)):
        encher_contatos(dono, conta, n)
    p = _previa(client, root["h"], "planos", {"planos.essencial.contatos": 2, "planos.essencial.preco": "159.00",
                                              "planos.empresa.contatos": 4000})
    assert p["mudancas"] == [{"chave": "planos.essencial.preco", "de": "149.00", "para": "159.00"},
                             {"chave": "planos.essencial.contatos", "de": 300, "para": 2},
                             {"chave": "planos.empresa.contatos", "de": 5000, "para": 4000}]
    assert p["precisa_confirmar"] is True
    assert p["impactos"] == [
        {"chave": "planos.essencial.contatos", "contas": 2,
         "exemplos": [{"id": beta, "nome": "Beta", "uso": 5}, {"id": alfa, "nome": "Alfa", "uso": 3}]},
        {"chave": "planos.empresa.contatos", "contas": 0, "exemplos": []}]
    assert sql(dono, "select count(*) from parametros") == [(0,)]  # a prévia não grava
    p = _previa(client, root["h"], "planos", {"planos.essencial.contatos": 500})
    assert (p["precisa_confirmar"], p["impactos"]) == (False, [])


def test_previa_da_cota_do_teto_da_franquia_e_das_analises(client, root, dono):
    alfa = _conta(client, dono, "ana@alfa.com.br", "Alfa", "profissional")
    beta = _conta(client, dono, "bia@beta.com.br", "Beta", "profissional", "teste")
    gama = _conta(client, dono, "gil@gama.com.br", "Gama", "profissional", "cortesia")
    mes = relogio.hoje().replace(day=1)
    usar_cota(dono, alfa, 300)
    usar_cota(dono, beta, 450)
    usar_cota(dono, gama, 400)
    sql(dono, "update ia_uso_mensal set analises = cota_usada where mes = :m", m=mes)
    sql(dono, "update contas set ia_modelo = 'detalhado' where id = :c", c=alfa)
    p = _previa(client, root["h"], "ia", {"ia.cota.profissional": 300, "ia.teto.teste": 400,
                                          "ia.analises.detalhado": 4, "ia.analises.equilibrado": 2,
                                          "ia.cota.cortesia": 600, "ia.cota.teste": 40})
    assert p["precisa_confirmar"] is True
    por_chave = {i["chave"]: i for i in p["impactos"]}
    assert set(por_chave) == {"ia.cota.profissional", "ia.cota.teste", "ia.teto.teste", "ia.analises.detalhado",
                              "ia.analises.equilibrado"}  # subir a cota da cortesia não tem impacto
    # a cota da cortesia não é a do plano; o teste tem a sua (5k)
    assert por_chave["ia.cota.profissional"]["exemplos"] == [{"id": alfa, "nome": "Alfa", "uso": 300}]
    assert por_chave["ia.cota.teste"]["exemplos"] == [{"id": beta, "nome": "Beta", "uso": 450}]
    assert por_chave["ia.teto.teste"] == {"chave": "ia.teto.teste", "contas": 1,
                                          "exemplos": [{"id": beta, "nome": "Beta", "uso": 450}]}
    assert por_chave["ia.analises.detalhado"]["exemplos"] == [{"id": alfa, "nome": "Alfa", "uso": 0}]
    assert por_chave["ia.analises.equilibrado"]["contas"] == 3  # Beta, Gama e Toqqi
    # franquia: o teste e a cortesia têm a sua
    sql(dono, "insert into whatsapp_uso (conta_id, mes, usadas) values (:a, :m, 80), (:b, :m, 15), (:g, :m, 150)",
        a=alfa, b=beta, g=gama, m=relogio.agora().strftime("%Y-%m"))
    p = _previa(client, root["h"], "whatsapp", {"whatsapp.franquia.profissional": 70, "whatsapp.franquia.teste": 10,
                                                "whatsapp.franquia.cortesia": 100})
    assert [(i["chave"], i["contas"], [e["nome"] for e in i["exemplos"]]) for i in p["impactos"]] == [
        ("whatsapp.franquia.profissional", 1, ["Alfa"]), ("whatsapp.franquia.cortesia", 1, ["Gama"]),
        ("whatsapp.franquia.teste", 1, ["Beta"])]


def test_previa_mostra_ate_5_exemplos_de_maior_uso(client, root, dono):
    contas = [_conta(client, dono, f"p{i}@c{i}.com.br", f"Conta {i}", "essencial") for i in range(7)]
    for i, c in enumerate(contas):
        usar_cota(dono, c, 50 + i)
    p = _previa(client, root["h"], "ia", {"ia.cota.essencial": 50})
    impacto, = p["impactos"]
    assert impacto["contas"] == 7 and [e["uso"] for e in impacto["exemplos"]] == [56, 55, 54, 53, 52]


def test_previa_da_exclusao(client, root):
    p = _previa(client, root["h"], "teste", {"teste.exclusao_automatica": "ligada"})
    assert (p["precisa_confirmar"], p["impactos"]) == (True, [])
    assert p["mudancas"] == [{"chave": "teste.exclusao_automatica", "de": "simular", "para": "ligada"}]


# ---- teste do modelo ------------------------------------------------------------------------------------------

def test_modelo_novo_testado_antes_de_salvar(client, root, dono):
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.detalhado": "gpt-6-astra", "ia.cota.essencial": 120})
    assert r.status_code == 200, r.text
    assert r.json()["testados"] == ["detalhado"] and r.json()["valores"]["ia.modelo.detalhado"] == "gpt-6-astra"
    assert memoria.corpos == [{"model": "gpt-6-astra", "reasoning": {"effort": "low"}, "input": "Responda apenas: ok",
                               "max_output_tokens": 16, "store": False}]
    assert memoria.tempos == [20]
    # só os níveis mudados; sem esforço, sem `reasoning`; a resposta incompleta também vale
    memoria.limpar()
    memoria.programar({"output": [], "status": "incomplete"})
    r = salvar_parametros(client, root["h"], "ia", {"ia.esforco.rapido": ""})
    assert r.status_code == 200 and r.json()["testados"] == ["rapido"]
    assert memoria.corpos == [{"model": "gpt-6-luna", "input": "Responda apenas: ok", "max_output_tokens": 16,
                               "store": False}]
    # nada de modelo mudou: não testa
    memoria.limpar()
    r = salvar_parametros(client, root["h"], "ia", {"ia.cota.essencial": 130})
    assert r.status_code == 200 and r.json()["testados"] == [] and memoria.corpos == []
    assert sql(dono, "select count(*) from ia_uso_mensal") == [(0,)]  # os tokens não entram em conta alguma


def test_modelo_recusado_ou_sem_resposta_nada_salvo(client, root, dono):
    memoria.programar(ia.FalhaIA("configuracao", "HTTP 400 (model_not_found)"))
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.rapido": "gpt-x", "ia.cota.essencial": 120})
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"ia.modelo.rapido": "A OpenAI recusou o modelo “gpt-x” com o esforço "
                                                              "“none” (HTTP 400). Confira o nome e o esforço."}
    memoria.programar("definitiva")
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.detalhado": "gpt-y", "ia.esforco.detalhado": ""})
    assert r.status_code == 422 and r.json()["erro"]["campos"]["ia.modelo.detalhado"].startswith(
        "A OpenAI recusou o modelo “gpt-y” sem raciocínio.")
    memoria.programar("transitoria")
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.rapido": "gpt-z"})
    assert r.status_code == 503 and r.json()["erro"] == {
        "codigo": "teste_ia_indisponivel", "campos": {},
        "mensagem": "Não deu para testar o modelo agora: a OpenAI não respondeu. Nada foi salvo; tente de novo em "
                    "alguns minutos."}
    # para no primeiro erro
    memoria.limpar()
    memoria.programar("configuracao")
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.rapido": "gpt-a", "ia.modelo.detalhado": "gpt-b"})
    assert r.status_code == 422 and len(memoria.corpos) == 1
    assert sql(dono, "select count(*) from parametros") == [(0,)]
    assert sql(dono, "select count(*) from parametros_historico") == [(0,)]


def test_sem_ia_na_plataforma_salva_sem_testar(client, root, monkeypatch):
    monkeypatch.setattr(config(), "IA_PROVEDOR", "desligado")
    r = salvar_parametros(client, root["h"], "ia", {"ia.modelo.rapido": "gpt-6-nano"})
    assert r.status_code == 200 and r.json()["testados"] == [] and memoria.corpos == []
    assert parametros.valor("ia.modelo.rapido") == "gpt-6-nano"


def test_alterado_em_e_por_vem_da_ultima_linha_do_historico_de_cada_grupo(client, root, dono, monkeypatch):
    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "root@toqqi.com,bia@toqqi.com")
    bia = conta_pronta(client, "bia@toqqi.com", empresa="Toqqi 2")
    assert salvar_parametros(client, root["h"], "teste", {"teste.dias": 7}).status_code == 200
    assert salvar_parametros(client, bia["h"], "whatsapp", {"whatsapp.franquia.teste": 30}).status_code == 200
    assert salvar_parametros(client, bia["h"], "teste", {"teste.dias": 8}).status_code == 200
    gravar_parametro(dono, "planos.essencial.preco", "159.00")  # linha sem histórico (gravada à mão)
    historico = {g: (i, em, por) for i, g, em, por in sql(
        dono, "select distinct on (grupo) id, grupo, criado_em, por from parametros_historico order by grupo, id desc")}
    grupos = {g["grupo"]: g for g in client.get(f"{API}/plataforma/parametros", headers=root["h"]).json()["grupos"]}
    for nome in ("teste", "whatsapp"):
        i, em, por = historico[nome]
        g = grupos[nome]
        assert (g["versao"], g["alterado_por"]) == (i, por)
        assert datetime.fromisoformat(g["alterado_em"].replace("Z", "+00:00")) == em
    assert grupos["teste"]["alterado_por"] == grupos["whatsapp"]["alterado_por"] == "bia@toqqi.com"
    assert (grupos["planos"]["versao"], grupos["planos"]["alterado_em"], grupos["planos"]["alterado_por"]) == (
        0, None, None)
    assert grupos["planos"]["valores"]["planos.essencial.preco"] == "159.00"


# ---- histórico --------------------------------------------------------------------------------------------

def test_historico_ordem_filtro_e_paginas(client, root):
    salvar_parametros(client, root["h"], "teste", {"teste.dias": 7})
    salvar_parametros(client, root["h"], "whatsapp", {"whatsapp.franquia.teste": 30})
    salvar_parametros(client, root["h"], "teste", {"teste.dias": 10})
    url = f"{API}/plataforma/parametros/historico"
    r = client.get(url, headers=root["h"])
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["total"], corpo["pagina"], corpo["por_pagina"]) == (3, 1, 20)
    assert [(i["id"], i["grupo"]) for i in corpo["itens"]] == [(3, "teste"), (2, "whatsapp"), (1, "teste")]
    assert set(corpo["itens"][0]) == {"id", "criado_em", "grupo", "por", "mudancas"}
    assert corpo["itens"][0]["mudancas"] == [{"chave": "teste.dias", "de": 7, "para": 10}]
    assert corpo["itens"][0]["por"] == "root@toqqi.com"
    r = client.get(url, headers=root["h"], params={"grupo": "teste", "por_pagina": 1, "pagina": 2})
    assert (r.json()["total"], [i["id"] for i in r.json()["itens"]]) == (2, [1])
    assert client.get(url, headers=root["h"], params={"grupo": ""}).json()["total"] == 3
    r = client.get(url, headers=root["h"], params={"grupo": "outro"})
    assert r.status_code == 422 and "grupo" in r.json()["erro"]["campos"]
    assert client.get(url, headers=root["h"], params={"por_pagina": 101}).status_code == 422


# ---- quem pode ----------------------------------------------------------------------------------------------

def test_so_superadmin_com_email_confirmado(client, root, dono):
    ana = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    rotas = [("get", "/plataforma/parametros", None), ("get", "/plataforma/parametros/historico", None),
             ("post", "/plataforma/parametros/teste/previa", {"valores": {}}),
             ("put", "/plataforma/parametros/teste", {"versao": 0, "valores": {}})]
    for metodo, rota, corpo in rotas:
        kwargs = {"json": corpo} if corpo is not None else {}
        r = getattr(client, metodo)(f"{API}{rota}", headers=ana["h"], **kwargs)
        assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao"
        assert getattr(client, metodo)(f"{API}{rota}", **kwargs).status_code == 401
    sql(dono, "update usuarios set email_confirmado = false where email = 'root@toqqi.com'")
    assert client.get(f"{API}/plataforma/parametros", headers=root["h"]).status_code == 403


# ---- GET /publico/planos ----------------------------------------------------------------------------------

def test_planos_publicos(client, root):
    r = client.get(f"{API}/publico/planos")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=60"
    assert r.json() == {
        "planos": [
            {"chave": "essencial", "nome": "Essencial", "preco": 149.0, "contatos": 300, "whatsapp": None,
             "ia_cota": 100, "ia_teto": 1000},
            {"chave": "profissional", "nome": "Profissional", "preco": 349.0, "contatos": 1500, "whatsapp": None,
             "ia_cota": 500, "ia_teto": 5000},
            {"chave": "empresa", "nome": "Empresa", "preco": 799.0, "contatos": 5000, "whatsapp": None,
             "ia_cota": 2000, "ia_teto": 15000}],
        "teste": {"dias": 14, "plano": "profissional", "whatsapp": None, "ia_teto": 500, "ia_cota": 50},
        "ia_analises": {"rapido": 1, "equilibrado": 1, "detalhado": 3},
        "descontos": {"pix": 3, "anual": 10},
        "personalizado": {"base": 99.0, "faixas": [{"ate": 1500, "preco": 18.0}, {"ate": 10000, "preco": 11.0},
                                                   {"ate": None, "preco": 6.0}],
                          "ia": [{"cota": 100, "preco": 0.0}, {"cota": 500, "preco": 30.0},
                                 {"cota": 2000, "preco": 120.0}, {"cota": 5000, "preco": 250.0}],
                          "contatos_min": 100, "contatos_max": 100000, "passo": 100, "whatsapp": None}}
    assert salvar_parametros(client, root["h"], "planos", {"planos.essencial.preco": "159.90",
                                                           "planos.empresa.contatos": 9000}).status_code == 200
    assert salvar_parametros(client, root["h"], "teste", {"teste.dias": 7, "teste.plano": "essencial"}
                             ).status_code == 200
    corpo = client.get(f"{API}/publico/planos").json()
    assert (corpo["planos"][0]["preco"], corpo["planos"][2]["contatos"]) == (159.9, 9000)
    assert corpo["teste"] == {"dias": 7, "plano": "essencial", "whatsapp": None, "ia_teto": 500, "ia_cota": 50}


def test_planos_publicos_60_por_minuto(client):
    limiter.enabled = True
    try:
        codigos = [client.get(f"{API}/publico/planos").status_code for _ in range(61)]
    finally:
        limiter.enabled = False
    assert codigos == [200] * 60 + [429]
