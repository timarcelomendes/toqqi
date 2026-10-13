"""Plano Grátis (docs/api-plano-gratis.md): as passagens (fim do teste, fim do período pago, 30 dias de atraso), os
limites (contatos, e-mails do mês e do dia, usuários, formulários, IA), as integrações desligadas, a proteção contra
abuso (nota de risco que pausa até a equipe liberar, formulário pedindo dado sensível, remetente fixo, descanso
mínimo, denúncia), a Plataforma (lista, Visão geral, Parâmetros, "+N dias", denúncias) e o site (planos públicos)."""
import json
from datetime import date, datetime, timedelta

import pytest
from util import (
    API,
    DADOS_COBRANCA,
    assinar,
    conta_pronta,
    criar_contato,
    criar_form,
    disparar,
    emails_para,
    encher_contatos,
    entrar,
    evento,
    fixar_relogio,
    form_padrao,
    gerar_chave,
    grupo_parametros,
    ligar_envios,
    link_pesquisa,
    membro,
    responder_convite,
    salvar_parametros,
    segunda,
    sql,
    superadmin,
    token_do_convite,
)

from toqqi import tarefas
from toqqi.core import parametros
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.email import caixa_memoria
from toqqi.modelos import Conta
from toqqi.modulos.assinatura import gratis
from toqqi.modulos.ia import cota
from toqqi.modulos.ia import regras as ia_regras
from toqqi.modulos.plataforma import risco

SEGUNDA = segunda(11)  # dia útil, na janela de envio
HOJE = SEGUNDA.date()


def _param(dono, **valores) -> None:
    """Grava parâmetros do grupo `gratis` e limpa o cache."""
    for chave, valor in valores.items():
        sql(dono, "insert into parametros (chave, valor) values (:c, cast(:v as jsonb)) "
                  "on conflict (chave) do update set valor = excluded.valor", c=f"gratis.{chave}", v=json.dumps(valor))
    parametros.invalidar()


def _ao_gratis(dono, monkeypatch, conta_id: int, quando: datetime = SEGUNDA) -> dict:
    """O teste acabou há uma hora e a tarefa `assinaturas` roda: a conta passa para o Grátis (a da equipe, criada antes,
    fica em teste)."""
    sql(dono, "update contas set teste_ate = :t where id = :c", t=quando - timedelta(hours=1), c=conta_id)
    sql(dono, "update contas set teste_ate = :t where id <> :c and situacao = 'teste'", t=quando + timedelta(days=30),
        c=conta_id)
    fixar_relogio(monkeypatch, quando)
    r = tarefas.executar("assinaturas")["assinaturas"]
    assert r["contas_ao_gratis"] == 1, r
    return r


def _situacao(dono, conta_id: int) -> tuple:
    return sql(dono, "select situacao, gratis_motivo, gratis_desde is not null from contas where id = :c",
               c=conta_id)[0]


def _pre(client, h) -> dict:
    return {i["chave"]: i for i in client.get(f"{API}/envios/pre-condicoes", headers=h).json()["itens"]}


@pytest.fixture
def ana(client, monkeypatch):
    fixar_relogio(monkeypatch, SEGUNDA - timedelta(days=20))
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


# ---- passagens --------------------------------------------------------------------------------------

def test_fim_do_teste_passa_para_o_gratis(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    ligar_envios(client, h, descanso_dias=10)
    gil = membro(client, h, "gil@alfa.com.br", perfil="admin")  # entrou no teste
    caixa_memoria.clear()
    _ao_gratis(dono, monkeypatch, c)
    assert _situacao(dono, c) == ("gratis", "teste", True)
    ((detalhe, gravidade),) = sql(dono, "select detalhe, gravidade from auditoria where conta_id = :c "
                                        "and evento = 'plano_gratis'", c=c)
    assert gravidade == "atencao"
    assert detalhe == {"de": "teste", "motivo": "teste", "contatos_ativos": 0, "sessoes_encerradas": 1}
    # o e-mail aos administradores ativos (os dois)
    (m,) = emails_para("ana@alfa.com.br")
    assert m.assunto == gratis.ASSUNTO_PASSOU and len(emails_para("gil@alfa.com.br")) == 1
    assert "O teste da conta Alfa no Toqqi terminou e a conta passou para o plano Grátis." in m.texto
    assert "até 200 pesquisas por e-mail por mês para até 100 contatos ativos, com 1 usuário" in m.texto
    assert "R$ 149,00 por mês" in m.texto and "Ver planos" in m.html and "/assinatura" in m.texto
    # o descanso sobe para 30 dias; a sessão de quem não entra mais é encerrada e ele não entra de novo
    assert sql(dono, "select descanso_dias from config_envios where conta_id = :c", c=c) == [(30,)]
    assert client.get(f"{API}/eu", headers=gil["h"]).status_code == 401
    r = entrar(client, "gil@alfa.com.br")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "plano_gratis"
    assert "plano Grátis, que tem 1 usuário" in r.json()["erro"]["mensagem"]
    # a Ana (o administrador mais antigo) segue; o aviso e o resumo do Grátis vêm em /eu
    eu = client.get(f"{API}/eu", headers=h).json()["conta"]
    assert eu["situacao"] == "gratis" and eu["cobranca"]["liberada"] is True
    assert eu["cobranca"]["aviso"] == {"tipo": "gratis", "data": HOJE.isoformat(), "dias": 0, "motivo": "teste"}
    g = eu["gratis"]
    assert g["contatos"] == {"ativos": 0, "limite": 100} and g["motivo"] == "teste"
    assert (g["envios"]["mes"], g["envios"]["limite_mes"], g["envios"]["limite_dia"]) == (0, 200, 100)
    assert g["envios"]["volta_mes"] == gratis.proximo_mes(HOJE).isoformat()
    assert (g["ia"], g["usuarios"], g["formularios"], g["pausada_por_risco"]) == (
        {"usadas": 0, "limite": 10}, 1, 2, False)
    a = client.get(f"{API}/assinatura", headers=h).json()
    assert a["gratis"]["contatos"]["limite"] == 100 and a["limites_gratis"]["envios_mes"] == 200
    # a tarefa de novo não faz nada (a conta já está no Grátis)
    assert tarefas.executar("assinaturas")["assinaturas"]["contas_ao_gratis"] == 0


def test_fim_do_periodo_pago_cancelado_passa_para_o_gratis(client, dono, ana, monkeypatch):
    c = ana["conta"]["id"]
    sql(dono, "update contas set situacao = 'cancelada', pago_ate = :p, teste_ate = :t where id = :c", c=c,
        p=HOJE - timedelta(days=1), t=SEGUNDA - timedelta(days=60))
    caixa_memoria.clear()
    fixar_relogio(monkeypatch, SEGUNDA)
    assert tarefas.executar("assinaturas")["assinaturas"]["contas_ao_gratis"] == 1
    assert _situacao(dono, c) == ("gratis", "cancelamento", True)
    (m,) = emails_para("ana@alfa.com.br")
    assert "O período pago da assinatura da conta Alfa no Toqqi terminou" in m.texto


def test_30_dias_de_atraso_cancelam_a_assinatura_e_a_conta_passa_para_o_gratis(client, dono, monkeypatch,
                                                                                asaas_falso):
    dia = lambda d, hora=10: datetime.combine(date.fromisoformat(d), datetime.min.time().replace(hour=hora),  # noqa
                                              tzinfo=gratis.relogio.FUSO)
    fixar_relogio(monkeypatch, dia("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    c = a["conta"]["id"]
    sql(dono, "update contas set teste_ate = :t where id = :c", t=dia("2026-10-15", 14), c=c)
    assert assinar(client, a["h"]).status_code == 201  # assinou no teste: a fatura vence em 15/10
    fixar_relogio(monkeypatch, dia("2026-10-16", 8))
    tarefas.executar("assinaturas")
    assert _situacao(dono, c)[0] == "atrasada"
    # 29 dias de atraso: nada; 30: cancelada e no Grátis
    fixar_relogio(monkeypatch, dia("2026-11-13", 8))
    assert tarefas.executar("assinaturas")["assinaturas"]["canceladas_por_atraso"] == 0
    caixa_memoria.clear()
    fixar_relogio(monkeypatch, dia("2026-11-14", 8))
    assert tarefas.executar("assinaturas")["assinaturas"]["canceladas_por_atraso"] == 1
    assert _situacao(dono, c) == ("gratis", "atraso", True)
    assert sql(dono, "select situacao from assinaturas where conta_id = :c", c=c) == [("cancelada",)]
    ((detalhe,),) = sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'assinatura_cancelada'",
                        c=c)
    assert detalhe == {"plano": "profissional", "motivo": "atraso", "vencida_em": "2026-10-15"}
    assert any(p.method == "DELETE" and "/subscriptions/" in p.url.path for p in asaas_falso.pedidos)
    (m,) = emails_para("ana@alfa.com.br")
    assert "foi cancelada porque a fatura ficou 30 dias vencida" in m.texto


def test_mais_dias_de_teste_e_cortesia_tiram_do_gratis(client, dono, ana, monkeypatch):
    c = ana["conta"]["id"]
    _ao_gratis(dono, monkeypatch, c)
    root = superadmin(client)
    r = client.post(f"{API}/plataforma/contas/{c}/estender-teste", headers=root["h"], json={"dias": 7})
    assert r.status_code == 200 and r.json()["situacao"] == "teste" and r.json()["gratis_desde"] is None
    ((detalhe,),) = sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'plano_gratis_saiu'",
                        c=c)
    assert detalhe["para"] == "teste"
    assert sql(dono, "select gratis_motivo from contas where id = :c", c=c) == [(None,)]


# ---- limites ----------------------------------------------------------------------------------------

def test_limite_de_contatos(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    _param(dono, contatos=2)
    ligar_envios(client, h)
    ids = [criar_contato(client, h, email=f"c{i}@x.com.br")["id"] for i in range(3)]  # 3 no teste
    _ao_gratis(dono, monkeypatch, c)
    # mais contatos ativos que o limite: os envios param até ficarem dentro dele
    item = _pre(client, h)["contatos_do_plano"]
    assert not item["ok"] and item["acao"] == {"rotulo": "Contatos", "rota": "/contatos"}
    assert item["mensagem"] == ("Sua conta tem 3 contatos ativos e o plano Grátis envia para até 2. Desative os "
                                "que não quer pesquisar, ou assine um plano.")
    r = disparar(client, h, ids[:1])
    assert r.status_code == 409 and r.json()["erro"]["mensagem"] == item["mensagem"]
    sql(dono, "update contatos set ativo = false where id = :i", i=ids[2])
    assert _pre(client, h)["contatos_do_plano"]["ok"] is True
    # contato novo além do limite não entra como ativo (a trava do banco)
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Quarto", "email": "q@x.com.br"})
    assert r.status_code == 402 and r.json()["erro"]["codigo"] == "limite_do_plano"
    assert "até 2 contatos ativos" in r.json()["erro"]["mensagem"]


def test_envios_por_email_do_mes_e_do_dia(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    _param(dono, envios_mes=3, envios_dia=2)
    ligar_envios(client, h)
    ids = [criar_contato(client, h, nome=f"Pessoa {i}", email=f"p{i}@x.com.br")["id"] for i in range(4)]
    _ao_gratis(dono, monkeypatch, c)
    caixa_memoria.clear()
    r = disparar(client, h, ids[:3]).json()
    assert r["agendados"] == 2
    assert r["ignorados"] == [{"contato_id": ids[2], "nome": "Pessoa 2",
                               "motivo": "Os envios por e-mail de hoje acabaram (2 de 2). Voltam amanhã."}]
    item = _pre(client, h)["envios_do_mes"]
    assert not item["ok"] and item["mensagem"].startswith("Os envios por e-mail de hoje acabaram")
    # amanhã: o terceiro sai e o mês acaba (e-mail aos administradores, uma vez)
    fixar_relogio(monkeypatch, SEGUNDA + timedelta(days=1))
    assert disparar(client, h, [ids[2]]).json()["agendados"] == 1
    volta = gratis.proximo_mes(HOJE + timedelta(days=1))
    msg = f"Os envios por e-mail deste mês acabaram (3 de 3). Voltam em {volta:%d/%m}, ou assine um plano para " \
          "continuar agora."
    r = disparar(client, h, [ids[3]])
    assert r.status_code == 409 and r.json()["erro"]["mensagem"] == msg
    (aviso,) = [m for m in emails_para("ana@alfa.com.br") if m.assunto == gratis.ASSUNTO_FIM_DO_MES]
    assert "usou as 3 pesquisas por e-mail do plano Grátis" in aviso.texto
    assert sql(dono, "select count(*) from auditoria where conta_id = :c and evento = 'envio_limite_mes'",
               c=c) == [(1,)]
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["gratis"]["envios"]["mes"] == 3
    # o agradecimento não conta nem para: quem responde recebe
    (convite,) = [m for m in emails_para("p0@x.com.br")]
    f = form_padrao(client, h)
    r = client.post(f"{API}/publico/convites/{token_do_convite(convite)}/responder",
                    json={"respostas": {f["perguntas"][0]["id"]: 10}})
    assert r.status_code == 201
    assert len(emails_para("p0@x.com.br")) == 2  # convite + agradecimento
    # o robô não roda com o mês acabado
    ligar_envios(client, h, envio_automatico=True)
    assert tarefas.executar("robo")["robo"]["agendados"] == 0


def test_envio_que_nao_sai_devolve_o_envio_do_mes(client, dono, ana, monkeypatch):
    c = ana["conta"]["id"]
    _ao_gratis(dono, monkeypatch, c)
    with em_conta(c) as s:
        conta = s.get(Conta, c)
        assert gratis.reservar_email(s, conta) and gratis.reservar_email(s, conta)
        assert gratis.uso_envios(s, c) == (2, 2)
        gratis.devolver_email(s, c, SEGUNDA)
        assert gratis.uso_envios(s, c) == (1, 1)
        gratis.devolver_email(s, c, SEGUNDA - timedelta(days=40))  # de outro mês: nada
        assert gratis.uso_envios(s, c) == (1, 1)


def test_um_usuario(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    _ao_gratis(dono, monkeypatch, c)
    r = client.post(f"{API}/equipe", headers=h, json={"nome": "Gil", "email": "gil@alfa.com.br", "perfil": "consulta",
                                                     "senha": "Senha@123"})
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"
    assert r.json()["erro"]["plano_minimo"] == "essencial"
    assert "O plano Grátis tem 1 usuário" in r.json()["erro"]["mensagem"]
    # pedido de acesso pendente não é aprovado
    ((uid,),) = sql(dono, "insert into usuarios (conta_id, nome, email, senha_hash, perfil, situacao, "
                          "email_confirmado) values (:c, 'Rui', 'rui@alfa.com.br', 'x', 'consulta', 'pendente', true) "
                          "returning id", c=c)
    r = client.patch(f"{API}/equipe/{uid}", headers=h, json={"situacao": "ativo"})
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"
    # com dois usuários liberados (parâmetro), aprova
    _param(dono, usuarios=2)
    assert client.patch(f"{API}/equipe/{uid}", headers=h, json={"situacao": "ativo"}).status_code == 200


def test_dois_formularios(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    extra = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Sugestão"}], nome="Extra")  # 3 no teste
    ligar_envios(client, h)
    _ao_gratis(dono, monkeypatch, c)
    # com mais de 2 recebendo respostas, os envios novos usam só os padrão (NPS e CSAT)
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"formulario_id": extra["id"]})
    assert r.status_code == 200
    item = _pre(client, h)["formulario"]
    assert not item["ok"] and item["mensagem"] == gratis.MSG_FORMULARIO_FORA.format(n=2)
    contato = criar_contato(client, h, email="x@x.com.br")
    r = client.post(f"{API}/contatos/{contato['id']}/link-pesquisa", headers=h, json={"formulario_id": extra["id"]})
    assert r.status_code == 422 and r.json()["erro"]["campos"]["formulario_id"] == item["mensagem"]
    assert link_pesquisa(client, h, contato["id"], formulario_id=form_padrao(client, h)["id"])
    # o terceiro segue recebendo pelos links já enviados (continua ativo); criar, duplicar ou ativar outro: não
    r = client.post(f"{API}/formularios", headers=h, json={"nome": "Mais um", "perguntas": []})
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"
    assert client.post(f"{API}/formularios/{extra['id']}/duplicar", headers=h).status_code == 403
    assert client.patch(f"{API}/formularios/{extra['id']}", headers=h, json={"ativo": False}).status_code == 200
    assert client.patch(f"{API}/formularios/{extra['id']}", headers=h, json={"ativo": True}).status_code == 403


def test_ia_do_gratis():
    c = Conta(situacao="gratis", plano="empresa")
    assert (cota.chave_do_limite(c), cota.limite(c)) == ("ia.cota.gratis", 10)
    assert (ia_regras.chave_do_teto(c), ia_regras.teto_mensal(c)) == ("ia.teto.gratis", 100)


# ---- recursos desligados ----------------------------------------------------------------------------

def test_integracoes_desligadas_e_guardadas(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    chave = gerar_chave(client, h)
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://exemplo.com.br/toqqi", "eventos": ["resposta.criada"]})
    assert w.status_code == 201
    ligar_envios(client, h)
    _ao_gratis(dono, monkeypatch, c)
    r = evento(client, chave, "pesquisas", email="cliente@x.com.br")
    assert r.status_code == 403 and r.json()["erro"] == {
        "codigo": "recurso_do_plano", "plano_minimo": "essencial",
        "mensagem": "A API do Toqqi não faz parte do plano Grátis. Disponível a partir do plano Essencial.",
        "campos": {}}
    assert client.post(f"{API}/integracoes/chave", headers=h).status_code == 403
    assert client.post(f"{API}/integracoes/webhooks", headers=h, json={
        "url": "https://exemplo.com.br/outro", "eventos": ["resposta.criada"]}).status_code == 403
    assert client.post(f"{API}/integracoes/webhooks/{w.json()['id']}/testar", headers=h).status_code == 403
    r = client.put(f"{API}/integracoes/conectores/rdstation-crm", headers=h,
                   json={"token": "x" * 32, "pesquisar_ao_ganhar": True})
    assert r.status_code == 403 and "RD Station" in r.json()["erro"]["mensagem"]
    # o webhook fica guardado, mas nenhuma resposta entra na fila dele
    contato = criar_contato(client, h, email="r@x.com.br")
    responder_convite(client, h, contato["id"], 9)
    assert sql(dono, "select count(*) from webhook_entregas where conta_id = :c", c=c) == [(0,)]
    assert client.get(f"{API}/integracoes/chave", headers=h).json()["existe"] is True


# ---- abuso ------------------------------------------------------------------------------------------

def test_remetente_fixo_e_descanso_minimo(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    ligar_envios(client, h, remetente_nome="Banco X", responder_para="golpe@x.com.br", descanso_dias=0)
    a = criar_contato(client, h, email="a@x.com.br")
    b = criar_contato(client, h, email="b@x.com.br")
    assert disparar(client, h, [b["id"]]).json()["agendados"] == 1  # recebeu no teste
    _ao_gratis(dono, monkeypatch, c)
    caixa_memoria.clear()
    assert disparar(client, h, [a["id"]]).json()["agendados"] == 1
    (m,) = emails_para("a@x.com.br")
    assert (m.remetente_nome, m.responder_para) == ("Alfa", "ana@alfa.com.br")
    # o descanso é de pelo menos 30 dias, e ignorar o descanso não vale
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"descanso_dias": 10})
    assert r.status_code == 422 and r.json()["erro"]["campos"]["descanso_dias"] == gratis.MSG_DESCANSO
    r = disparar(client, h, [b["id"]], ignorar_descanso=True).json()
    assert r["agendados"] == 0 and "descanso de 30 dias" in r["ignorados"][0]["motivo"]
    # o e-mail de teste também sai com o nome da conta
    caixa_memoria.clear()
    assert client.post(f"{API}/envios/configuracao/teste", headers=h).status_code == 200
    (m,) = emails_para("ana@alfa.com.br")
    assert (m.remetente_nome, m.responder_para) == ("Alfa", "ana@alfa.com.br")


def test_formulario_pedindo_senha_nao_e_enviado(client, dono, ana, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    golpe = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Para validar, digite a senha do seu banco"}],
                       nome="Validação")
    ligar_envios(client, h, formulario_id=golpe["id"])
    contato = criar_contato(client, h, email="v@x.com.br")
    sql(dono, "update formularios set ativo = false where conta_id = :c and padrao_csat", c=c)  # 2 ativos
    _ao_gratis(dono, monkeypatch, c)
    item = _pre(client, h)["formulario"]
    assert not item["ok"] and "Para validar, digite a senha do seu banco" in item["mensagem"]
    assert item["acao"] == {"rotulo": "Editar o formulário", "rota": f"/formularios/{golpe['id']}"}
    assert disparar(client, h, [contato["id"]]).status_code == 409
    r = client.post(f"{API}/contatos/{contato['id']}/link-pesquisa", headers=h, json={"formulario_id": golpe["id"]})
    assert r.status_code == 422


@pytest.fixture
def root(client):
    return superadmin(client)


def test_risco_alto_pausa_ate_a_equipe_liberar(client, dono, ana, root, monkeypatch):
    h, c = ana["h"], ana["conta"]["id"]
    ligar_envios(client, h)
    contato = criar_contato(client, h, email="r@x.com.br")
    # um formulário pedindo senha (60 pontos), criado no teste e desativado (os envios usam o padrão)
    criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Digite a senha do seu banco"}], nome="Golpe")
    sql(dono, "update formularios set ativo = false where conta_id = :c and nome = 'Golpe'", c=c)
    _ao_gratis(dono, monkeypatch, c)
    # a tarefa grava a nota e a conta Grátis pausa (aviso à equipe)
    caixa_memoria.clear()
    r = tarefas.executar("riscos")["riscos"]
    assert r["pausadas"] == 1
    assert sql(dono, "select risco_pontos from contas where id = :c", c=c)[0][0] >= 60
    assert sql(dono, "select count(*) from auditoria where conta_id = :c and evento = 'risco_pausou'", c=c) == [(1,)]
    (m,) = emails_para("root@toqqi.com")
    assert "Alfa: nota" in m.texto and "formulário pedindo dado sensível" in m.texto
    item = _pre(client, h)["revisao"]
    assert not item["ok"] and item["mensagem"] == gratis.MSG_RISCO
    assert disparar(client, h, [contato["id"]]).status_code == 409
    lista = {x["id"]: x for x in client.get(f"{API}/plataforma/contas", headers=root["h"]).json()}
    assert lista[c]["envios_pausados"] is True
    # a equipe libera: volta a enviar; uma nota acima da liberada pausa de novo
    r = client.post(f"{API}/plataforma/contas/{c}/liberar-envios", headers=root["h"])
    assert r.status_code == 200 and r.json()["envios_pausados"] is False and r.json()["risco_liberado_em"]
    assert _pre(client, h)["revisao"]["ok"] is True
    assert client.post(f"{API}/plataforma/contas/{c}/liberar-envios", headers=root["h"]).status_code == 409
    sql(dono, "update contas set risco_pontos = risco_liberado_pontos + 10 where id = :c", c=c)
    assert _pre(client, h)["revisao"]["ok"] is False
    # nos planos pagos, a nota segue só como alerta
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=c)
    assert "revisao" not in _pre(client, h)


def test_denunciar_a_pesquisa(client, dono, ana, root, monkeypatch):
    from fastapi.testclient import TestClient

    h, c = ana["h"], ana["conta"]["id"]
    contato = criar_contato(client, h, email="d@x.com.br")
    token = link_pesquisa(client, h, contato["id"])
    assert client.get(f"{API}/publico/convites/{token}").json()["formulario"]["denuncia"] is False  # no teste
    _ao_gratis(dono, monkeypatch, c)
    assert client.get(f"{API}/publico/convites/{token}").json()["formulario"]["denuncia"] is True
    caixa_memoria.clear()
    with TestClient(client.app, client=("198.51.100.7", 50000)) as fulano:
        for _ in range(2):  # a mesma pessoa duas vezes: uma denúncia
            r = fulano.post(f"{API}/publico/convites/{token}/denuncia",
                            json={"motivo": "dados_pessoais", "detalhe": "Pediu a senha do banco"})
            assert r.status_code == 201 and "Recebemos a sua denúncia" in r.json()["mensagem"]
    with modo_sistema() as s:
        assert s.execute(sql_text("select conta_id, origem, motivo, detalhe, situacao from denuncias")).all() == [
            (c, "convite", "dados_pessoais", "Pediu a senha do banco", "aberta")]
    with em_conta(c) as s:  # a conta denunciada nunca vê
        assert s.execute(sql_text("select count(*) from denuncias")).scalar() == 0
    (m,) = emails_para("root@toqqi.com")
    assert m.assunto == "Denúncia de pesquisa no plano Grátis" and "Pede senha, cartão ou dados bancários" in m.texto
    # pesa na nota de risco: 1 pessoa 30, 2 pessoas 60
    with modo_sistema() as s:
        (sinal,) = [x for x in risco.calcular(s)[c]["sinais"] if x["tipo"] == "denuncias"]
    assert (sinal["pontos"], sinal["pessoas"]) == (30, 1)
    with TestClient(client.app, client=("203.0.113.9", 50000)) as outro:
        f = client.get(f"{API}/formularios", headers=h).json()
        codigo = next(x for x in f if x["padrao_nps"])["codigo_publico"]
        sql(dono, "update formularios set publico = true where conta_id = :c and padrao_nps", c=c)
        assert outro.post(f"{API}/publico/formularios/{codigo}/denuncia", json={"motivo": "spam"}).status_code == 201
    with modo_sistema() as s:
        (sinal,) = [x for x in risco.calcular(s)[c]["sinais"] if x["tipo"] == "denuncias"]
    assert (sinal["pontos"], sinal["pessoas"], sinal["denuncias"]) == (60, 2, 2)
    # Plataforma › Feedback › Denúncias: lista e descarta (sai da nota)
    r = client.get(f"{API}/plataforma/denuncias", headers=root["h"]).json()
    assert r["abertas"] == 2 and {x["origem"] for x in r["itens"]} == {"convite", "link_publico"}
    assert client.get(f"{API}/plataforma/denuncias", headers=h).status_code == 403
    for x in r["itens"]:
        d = client.patch(f"{API}/plataforma/denuncias/{x['id']}", headers=root["h"],
                         json={"situacao": "descartada", "nota_interna": "Pesquisa normal"})
        assert d.status_code == 200 and d.json()["situacao"] == "descartada" and d.json()["resolvida_em"]
    with modo_sistema() as s:
        assert not [x for x in risco.calcular(s)[c]["sinais"] if x["tipo"] == "denuncias"]
    assert client.get(f"{API}/plataforma/denuncias", headers=root["h"]).json()["abertas"] == 0


def sql_text(q: str):
    from sqlalchemy import text

    return text(q)


# ---- Plataforma e site -------------------------------------------------------------------------------

def test_visao_geral_e_parametros(client, dono, ana, root, monkeypatch):
    c = ana["conta"]["id"]
    encher_contatos(dono, c, 5)
    _ao_gratis(dono, monkeypatch, c)
    v = client.get(f"{API}/plataforma/visao", headers=root["h"]).json()
    assert v["gratis"] == {"contas": 1, "entraram_30d": 1, "assinaram_30d": 0, "pausadas": 0}
    assert v["totais"]["por_situacao"]["gratis"] == 1 and "teste_expirado" not in v["totais"]["por_situacao"]
    g = grupo_parametros(client, root["h"], "gratis")
    assert g["rotulo"] == "Plano Grátis"
    assert g["valores"] == {"gratis.contatos": 100, "gratis.envios_mes": 200, "gratis.envios_dia": 100,
                            "gratis.usuarios": 1, "gratis.dias_sem_uso": 180, "gratis.dias_aviso": 30,
                            "gratis.dias_atraso": 30}
    r = salvar_parametros(client, root["h"], "gratis", {"gratis.envios_dia": 300})
    assert r.status_code == 422 and "gratis.envios_dia" in r.json()["erro"]["campos"]
    # diminuir pede confirmação e mostra as contas Grátis acima do novo limite
    g = grupo_parametros(client, root["h"], "gratis")
    r = client.post(f"{API}/plataforma/parametros/gratis/previa", headers=root["h"],
                    json={"valores": {**g["valores"], "gratis.contatos": 3}}).json()
    assert r["precisa_confirmar"] is True
    (impacto,) = r["impactos"]
    assert impacto["chave"] == "gratis.contatos" and impacto["contas"] == 1 and impacto["exemplos"][0]["uso"] == 5
    assert salvar_parametros(client, root["h"], "gratis", {"gratis.contatos": 3}).status_code == 200
    parametros.invalidar()
    assert client.get(f"{API}/eu", headers=ana["h"]).json()["conta"]["gratis"]["contatos"]["limite"] == 3
    # IA e WhatsApp do Grátis ficam nos grupos deles
    assert grupo_parametros(client, root["h"], "ia")["valores"]["ia.cota.gratis"] == 10
    assert grupo_parametros(client, root["h"], "whatsapp")["valores"]["whatsapp.franquia.gratis"] is None


def test_planos_publicos_trazem_o_gratis(client, root):
    """O site mostra o cartão e a coluna do Grátis com estes números (os formulários são fixos no código)."""
    r = client.get(f"{API}/publico/planos").json()
    assert r["gratis"] == {"contatos": 100, "envios_mes": 200, "envios_dia": 100, "usuarios": 1, "formularios": 2,
                           "ia_cota": 10, "ia_teto": 100, "whatsapp": None}
    # acompanham Plataforma › Parâmetros
    assert salvar_parametros(client, root["h"], "gratis", {"gratis.envios_dia": 80}).status_code == 200
    assert client.get(f"{API}/publico/planos").json()["gratis"]["envios_dia"] == 80


def test_assinar_saindo_do_gratis_usa_o_limite_do_plano_assinado(client, dono, ana, monkeypatch, asaas_falso):
    """Com 150 contatos ativos (vindos do teste), o Grátis envia para até 100, mas o Essencial (300) cabe: assinar
    não é recusado. Até a primeira fatura ser paga, a conta segue no Grátis."""
    h, c = ana["h"], ana["conta"]["id"]
    encher_contatos(dono, c, 150)
    _ao_gratis(dono, monkeypatch, c)
    r = assinar(client, h, "essencial")
    assert r.status_code == 201, r.text
    assert _situacao(dono, c)[0] == "gratis"
    eu = client.get(f"{API}/eu", headers=h).json()["conta"]
    assert eu["cobranca"]["assinada"] is True and eu["cobranca"]["aviso"]["tipo"] == "gratis_aguardando"
    assert DADOS_COBRANCA  # (os dados de cobrança do util)
