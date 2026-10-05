"""Etapa 5h §2 (docs/api-etapa-5h.md): IA nos importados. Ao concluir a importação de respostas, com a IA ativa na
conta, as importadas agora dos últimos 90 dias com comentário de 3+ letras vão para a fila (a regra e o saldo de
"analisar os últimos 90 dias", que ganhou um núcleo sem erros), a resposta traz `ia_marcadas` e a fila desta conta é
analisada logo depois do commit (até 100 análises ou 120 s, no máximo 4 ao mesmo tempo); o resto fica para a tarefa."""
import threading
import time
from datetime import timedelta

import pytest
from util import API, conta_pronta, criar_contato, registrar_resposta, sem_passos, sql, tarefa_ia

from toqqi.core import ia, relogio
from toqqi.core.config import config
from toqqi.modulos.ia import servico
from toqqi.modulos.ia.servico import mes_atual

pytestmark = pytest.mark.usefixtures("relogio_estavel")
EMAIL = "paula@cliente.com.br"


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sem_passos(dono, a["conta"]["id"])  # aqui só a análise por resposta gasta o teto
    criar_contato(client, a["h"], nome="Paula", email=EMAIL)
    return a


def _dia(dias: int) -> str:
    return (relogio.hoje() - timedelta(days=dias)).strftime("%d/%m/%Y")


def _importar(client, h, linhas: list[tuple], **corpo) -> dict:
    """Importa respostas: linhas (dias atrás, nota, comentário) do contato Paula."""
    csv = "email;data;nota;comentario\r\n" + "\r\n".join(f"{EMAIL};{_dia(d)};{n};{c}" for d, n, c in linhas)
    d = client.post(f"{API}/importacao/analisar", headers=h, data={"tipo": "respostas"},
                    files={"arquivo": ("historico.csv", csv.encode())})
    assert d.status_code == 200, d.text
    d = d.json()
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h,
                    json={"mapeamento": d["mapeamento_sugerido"], **corpo})
    assert r.status_code == 200, r.text
    return r.json()


def _situacoes(dono, conta_id: int) -> dict:
    return {c: s for c, s in sql(dono, "select comentario_cliente, ia_situacao from respostas where conta_id = :c",
                                 c=conta_id)}


def _uso(dono, conta_id: int) -> int:
    linhas = sql(dono, "select analises from ia_uso_mensal where conta_id = :c", c=conta_id)
    return linhas[0][0] if linhas else 0


def test_marca_e_analisa_so_as_importadas_dos_ultimos_90_dias_com_comentario(client, admin, dono):
    h, conta = admin["h"], admin["conta"]["id"]
    # uma resposta de antes, sem análise, que não é desta importação: fica como está
    antiga = registrar_resposta(client, h, criar_contato(client, h, email="rui@c.com.br")["id"], 4,
                                comentario="Retorno demorado").json()["id"]
    sql(dono, "update respostas set ia_situacao = null where id = :r", r=antiga)
    ia.memoria.limpar()
    r = _importar(client, h, [(1, 3, "Frete caro"), (2, 9, "Vendedor ótimo"), (89, 7, "Atrasou um pouco"),
                              (90, 2, "Fora da janela"), (3, 6, "ok"), (4, 8, "")])
    assert (r["novos"], r["ia_marcadas"]) == (6, 3)
    # analisadas logo depois do commit (provedor de testes), das mais recentes para as mais antigas
    assert _situacoes(dono, conta) == {"Frete caro": "analisada", "Vendedor ótimo": "analisada",
                                       "Atrasou um pouco": "analisada", "Fora da janela": None, "ok": None, "": None,
                                       "Retorno demorado": None}
    assert sorted(e.comentario for e in ia.memoria.chamadas) == ["Atrasou um pouco", "Frete caro", "Vendedor ótimo"]
    assert _uso(dono, conta) == 1 + 3  # a resposta à mão e as 3: o teto de segurança, não a cota do plano
    assert client.get(f"{API}/conta/ia", headers=h).json()["cota"]["usadas"] == 0
    x = sql(dono, "select ia_sentimento, temas from respostas where comentario_cliente = 'Frete caro'")[0]
    assert x == ("negativo", ["prazo_entrega", "preco_condicoes"])
    # nada sobra para a tarefa
    assert tarefa_ia() == {"analisadas": 0, "falharam": 0, "limite": 0}


def test_atualizadas_tambem_entram_e_as_ja_analisadas_nao(client, admin, dono):
    h, conta = admin["h"], admin["conta"]["id"]
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    assert _importar(client, h, [(5, 2, "Produto quebrado"), (6, 9, "Muito bom")])["ia_marcadas"] == 0
    assert set(_situacoes(dono, conta).values()) == {None}
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": True}).status_code == 200
    # a mesma planilha de novo, atualizando: as duas são "importadas agora"
    r = _importar(client, h, [(5, 2, "Produto quebrado"), (6, 9, "Muito bom")], atualizar_existentes=True)
    assert (r["novos"], r["atualizados"], r["ia_marcadas"]) == (0, 2, 2)
    assert set(_situacoes(dono, conta).values()) == {"analisada"}
    # de novo: já analisadas, nada a marcar
    r = _importar(client, h, [(5, 2, "Produto quebrado")], atualizar_existentes=True)
    assert r["ia_marcadas"] == 0 and _uso(dono, conta) == 2


def test_respeita_o_saldo_do_teto(client, admin, dono):
    h, conta = admin["h"], admin["conta"]["id"]
    limite = client.get(f"{API}/conta/ia", headers=h).json()["limite"]
    sql(dono, "insert into ia_uso_mensal (conta_id, mes, analises) values (:c, :m, :n)", c=conta, m=mes_atual(),
        n=limite - 2)
    r = _importar(client, h, [(1, 3, "Um comentário"), (2, 4, "Dois comentários"), (3, 5, "Três comentários"),
                              (4, 6, "Quatro comentários")])
    assert r["ia_marcadas"] == 2
    assert _situacoes(dono, conta) == {"Um comentário": "analisada", "Dois comentários": "analisada",
                                       "Três comentários": None, "Quatro comentários": None}
    assert _uso(dono, conta) == limite
    # sem saldo: nada marcado
    assert _importar(client, h, [(7, 1, "Sem saldo nenhum")])["ia_marcadas"] == 0
    assert client.post(f"{API}/conta/ia/analisar-recentes", headers=h).json() == {"marcadas": 0,
                                                                                 "restantes_no_mes": 0}


@pytest.mark.parametrize("caso", ["ia_desligada_na_conta", "sem_ia_na_plataforma", "conta_pausada"])
def test_sem_ia_ativa_nao_marca(client, admin, dono, monkeypatch, caso):
    h, conta = admin["h"], admin["conta"]["id"]
    if caso == "ia_desligada_na_conta":
        assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    elif caso == "sem_ia_na_plataforma":
        monkeypatch.setattr(config(), "IA_PROVEDOR", "desligado")
    else:  # o teste acabou sem assinatura: a conta não está liberada
        sql(dono, "update contas set teste_ate = now() - interval '1 day' where id = :c", c=conta)
    ia.memoria.limpar()
    r = _importar(client, h, [(1, 2, "Entrega atrasou"), (2, 3, "Frete caro")])
    assert (r["novos"], r["ia_marcadas"]) == (2, 0)
    assert set(_situacoes(dono, conta).values()) == {None}
    assert ia.memoria.chamadas == [] and _uso(dono, conta) == 0


def test_contatos_e_respostas_de_outra_conta(client, admin, dono):
    """A importação de contatos não tem `ia_marcadas`; a fila analisada é só a da conta que importou."""
    h = admin["h"]
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    cb = criar_contato(client, b["h"], email="cb@b.com.br")
    ia.memoria.programar("configuracao")  # a resposta de B fica pendente
    rb = registrar_resposta(client, b["h"], cb["id"], 2, comentario="Pendente da conta B").json()["id"]
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rb) == [("pendente",)]
    assert _importar(client, h, [(1, 3, "Da conta A")])["ia_marcadas"] == 1
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rb) == [("pendente",)]
    assert _situacoes(dono, admin["conta"]["id"])["Da conta A"] == "analisada"
    d = client.post(f"{API}/importacao/analisar", headers=h, files={
        "arquivo": ("c.csv", "nome;email\r\nRui;rui@x.com.br\r\n".encode())}).json()
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json={"mapeamento": d["mapeamento_sugerido"]})
    assert r.status_code == 200 and "ia_marcadas" not in r.json()


def test_processar_conta_limites(client, admin, dono, monkeypatch):
    """Até 100 análises (das mais recentes), no máximo 4 ao mesmo tempo, e para no tempo; o resto fica pendente."""
    conta = admin["conta"]["id"]
    contato = sql(dono, "select id from contatos where conta_id = :c", c=conta)[0][0]
    formulario = sql(dono, "select id from formularios where conta_id = :c and padrao_nps", c=conta)[0][0]
    sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, canal, origem, nota, tipo_nota, grupo, comentario,
                               comentario_cliente, respondida_em, ia_situacao)
        select :c, :f, :ct, 'importacao', 'importacao', 5, 'nps', 'detrator', 'Comentário ' || g, 'Comentário ' || g,
               now() - g * interval '1 hour', 'pendente'
          from generate_series(1, 105) g
    """, c=conta, f=formulario, ct=contato)
    ao_mesmo_tempo = {"agora": 0, "maximo": 0}
    trava = threading.Lock()
    original = ia.memoria.analisar

    def lenta(entrada):
        with trava:
            ao_mesmo_tempo["agora"] += 1
            ao_mesmo_tempo["maximo"] = max(ao_mesmo_tempo["maximo"], ao_mesmo_tempo["agora"])
        time.sleep(0.005)
        try:
            return original(entrada)
        finally:
            with trava:
                ao_mesmo_tempo["agora"] -= 1

    monkeypatch.setattr(ia.memoria, "analisar", lenta)
    assert servico.processar_conta(conta) == {"analisadas": 100, "falharam": 0, "limite": 0}
    assert ao_mesmo_tempo["maximo"] <= 4
    pendentes = sql(dono, "select comentario_cliente from respostas where conta_id = :c and ia_situacao = 'pendente'",
                    c=conta)
    assert sorted(x[0] for x in pendentes) == [f"Comentário {g}" for g in (101, 102, 103, 104, 105)]  # as mais antigas
    # sem tempo: nada começa
    monkeypatch.setattr(servico, "TEMPO_FILA_CONTA", 0)
    assert servico.processar_conta(conta) == {"analisadas": 0, "falharam": 0, "limite": 0}
    monkeypatch.setattr(servico, "TEMPO_FILA_CONTA", 120)
    # falha de configuração para a rodada (e não conta tentativa); a tarefa retoma depois
    monkeypatch.setattr(ia.memoria, "analisar", original)
    ia.memoria.programar("configuracao")
    assert servico.processar_conta(conta)["analisadas"] <= 4
    assert tarefa_ia()["analisadas"] >= 1
    assert sql(dono, "select count(*) from respostas where conta_id = :c and ia_situacao = 'pendente'",
               c=conta)[0][0] == 0


def test_processar_conta_nao_levanta(client, admin, monkeypatch):
    def quebra(*_a, **_k):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(servico, "em_conta", quebra)
    assert servico.processar_conta(admin["conta"]["id"]) == {"analisadas": 0, "falharam": 0, "limite": 0}


def test_nucleo_igual_ao_analisar_recentes(client, admin, dono):
    """`analisar-recentes` continua igual (agora pelo núcleo): os mesmos erros e o mesmo saldo."""
    h, conta = admin["h"], admin["conta"]["id"]
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    r = client.post(f"{API}/conta/ia/analisar-recentes", headers=h)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ia_indisponivel"
    _importar(client, h, [(1, 3, "Frete caro"), (95, 2, "Muito antigo")])
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": True}).status_code == 200
    limite = client.get(f"{API}/conta/ia", headers=h).json()["limite"]
    r = client.post(f"{API}/conta/ia/analisar-recentes", headers=h)
    assert r.json() == {"marcadas": 1, "restantes_no_mes": limite - 1}
    assert _situacoes(dono, conta) == {"Frete caro": "pendente", "Muito antigo": None}
