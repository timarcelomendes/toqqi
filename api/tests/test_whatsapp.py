"""Etapa 3b: WhatsApp automático (Cloud API da Meta) — conexão, envio por modelo, franquia, canal, avisos da
Meta (situação e "SAIR"), lembretes e isolamento entre contas. A Graph API é sempre um dublê (MetaFalsa)."""
import json
from datetime import datetime, timedelta

import pytest
from util import (
    gravar_parametro,
    API,
    FUSO,
    PNID,
    TOKEN_META,
    VERIFY_TOKEN,
    aviso_mensagem,
    aviso_meta,
    aviso_status,
    conectar_whatsapp,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    evento,
    fila,
    fixar_relogio,
    gerar_chave,
    historico,
    ligar_envios,
    membro,
    modelo_meta,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.core.config import config
from toqqi.core.segredos import decifrar
from toqqi.modulos.whatsapp import graph


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


def ligar(client, h, canal="whatsapp", **extra):
    r = conectar_whatsapp(client, h)
    assert r.status_code == 200, r.text
    ligar_envios(client, h, canal=canal, **extra)


def ver(client, h) -> dict:
    r = client.get(f"{API}/integracoes/whatsapp", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def envios_db(dono):
    return sql(dono, "select canal, situacao, erro, wamid, cobranca, para from envios order by id")


def botao(corpo: dict) -> str:
    return corpo["template"]["components"][1]["parameters"][0]["text"]


def mes() -> str:
    return datetime.now(FUSO).strftime("%Y-%m")


# ---- conexão ----------------------------------------------------------------

def test_conectar_confere_na_meta_e_guarda_o_token_cifrado(client, admin, meta, dono):
    h = admin["h"]
    d = ver(client, h)
    assert d["conectado"] is False and d["modelo"] is None and d["ativo"] is False
    assert d["franquia"] == {"plano": "cortesia", "limite": None, "usadas_mes": 0, "excedente_ativo": False,
                             "excedentes_mes": 0, "valor_excedente": 1.5}
    assert d["webhook_url"] == f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/whatsapp/webhook"
    assert d["webhook_verificacao"] == VERIFY_TOKEN

    r = conectar_whatsapp(client, h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["conectado"], d["ativo"], d["ultimo_erro"]) == (True, True, None)
    assert (d["numero_exibicao"], d["nome_verificado"]) == ("+55 11 4000-1234", "Alfa Distribuidora")
    assert (d["phone_number_id"], d["waba_id"]) == (PNID, "9876543210")
    assert d["modelo"] == {"nome": "pesquisa_toqqi", "idioma": "pt_BR"}
    assert TOKEN_META not in r.text and TOKEN_META not in client.get(f"{API}/integracoes/whatsapp", headers=h).text
    (cifrado, posicao), = sql(dono, "select token_cifrado, modelo_botao from whatsapp_contas")
    assert TOKEN_META not in cifrado and decifrar(cifrado) == TOKEN_META and posicao == 1
    numero, modelos = meta.pedidos
    assert numero.url.path == f"/v23.0/{PNID}" and numero.url.params["fields"] == "display_phone_number,verified_name"
    assert modelos.url.path == "/v23.0/9876543210/message_templates" and modelos.url.params["name"] == "pesquisa_toqqi"
    assert numero.headers["authorization"] == f"Bearer {TOKEN_META}"
    eventos = client.get(f"{API}/auditoria", headers=h).json()["itens"]
    assert any(e["evento"] == "whatsapp_conectado" for e in eventos)
    assert all(TOKEN_META not in str(e) for e in eventos)

    # quem só vê envios lê a situação, sem os dados para o painel da Meta
    consulta = membro(client, h, "caio@alfa.com.br")
    d = ver(client, consulta["h"])
    assert d["conectado"] is True and d["webhook_url"] is None and d["webhook_verificacao"] is None
    assert conectar_whatsapp(client, consulta["h"]).status_code == 403
    gestor = membro(client, h, "gil@alfa.com.br", perfil="gestor")
    assert client.patch(f"{API}/integracoes/whatsapp", headers=gestor["h"], json={"ativo": False}).status_code == 403


@pytest.mark.parametrize("ajuste,campo,trecho", [
    ({"erro_numero": (401, {"code": 190, "message": "Invalid OAuth access token"})}, "token", "token"),
    ({"erro_numero": (400, {"code": 100, "message": "Unsupported get request"})}, "phone_number_id", "número"),
    ({"modelos": [modelo_meta(status="PENDING")]}, "modelo_nome", "aprovado"),
    ({"modelos": [modelo_meta(category="MARKETING")]}, "modelo_nome", "Utilidade"),
    ({"modelos": [modelo_meta(language="en_US")]}, "modelo_nome", "Não encontramos"),
    ({"modelos": [modelo_meta(components=[{"type": "BODY", "text": "Oi {{1}}, {{2}} {{3}}"}])]}, "modelo_nome",
     "botão"),
    ({"modelos": [modelo_meta(components=[{"type": "BODY", "text": "Oi {{1}}"}])]}, "modelo_nome", "variáveis"),
])
def test_conectar_recusa(client, admin, meta, ajuste, campo, trecho):
    for k, v in ajuste.items():
        setattr(meta, k, v)
    r = conectar_whatsapp(client, admin["h"])
    assert r.status_code == 422, r.text
    assert trecho in r.json()["erro"]["campos"][campo]
    assert ver(client, admin["h"])["conectado"] is False


def test_conectar_validacao_e_numero_de_outra_conta(client, admin, meta):
    r = conectar_whatsapp(client, admin["h"], pnid="abc", modelo_nome="Pesquisa Toqqi", token="curto")
    assert r.status_code == 422
    assert set(r.json()["erro"]["campos"]) == {"phone_number_id", "modelo_nome", "token"}
    assert conectar_whatsapp(client, admin["h"]).status_code == 200
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    r = conectar_whatsapp(client, b["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "numero_em_uso"
    assert conectar_whatsapp(client, b["h"], pnid="5555555555").status_code == 200
    # reconectar a própria conta (ex.: token novo) pode
    assert conectar_whatsapp(client, admin["h"]).status_code == 200


def test_desconectar_e_canal_da_configuracao(client, admin, meta, dono):
    h = admin["h"]
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"canal": "whatsapp"})
    assert r.status_code == 422 and "canal" in r.json()["erro"]["campos"]
    ligar(client, h, canal="whatsapp_e_email")
    assert client.get(f"{API}/envios/configuracao", headers=h).json()["canal"] == "whatsapp_e_email"
    assert client.patch(f"{API}/integracoes/whatsapp", headers=h,
                        json={"ativo": False, "excedente_ativo": True}).json()["franquia"]["excedente_ativo"] is True
    assert client.delete(f"{API}/integracoes/whatsapp", headers=h).status_code == 204
    assert ver(client, h)["conectado"] is False
    assert sql(dono, "select count(*) from whatsapp_contas")[0][0] == 0
    assert client.get(f"{API}/envios/configuracao", headers=h).json()["canal"] == "email"
    r = client.patch(f"{API}/integracoes/whatsapp", headers=h, json={"ativo": True})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "whatsapp_nao_conectado"
    assert any(e["evento"] == "whatsapp_desconectado"
               for e in client.get(f"{API}/auditoria", headers=h).json()["itens"])


def test_mensagem_de_teste(client, admin, meta):
    h = admin["h"]
    r = client.post(f"{API}/integracoes/whatsapp/teste", headers=h, json={"telefone": "11987654321"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "whatsapp_nao_conectado"
    ligar(client, h)
    r = client.post(f"{API}/integracoes/whatsapp/teste", headers=h, json={"telefone": "(11) 98765-4321"})
    assert r.status_code == 200 and r.json()["mensagem"].endswith("terminado em 4321.")
    corpo = meta.mensagens[-1]
    assert corpo["to"] == "5511987654321" and botao(corpo) == "teste"
    assert ver(client, h)["franquia"]["usadas_mes"] == 0      # teste não gasta franquia
    assert client.post(f"{API}/integracoes/whatsapp/teste", headers=h, json={}).status_code == 422
    meta.erro_envio = (401, {"code": 190, "message": "Error validating access token"})
    r = client.post(f"{API}/integracoes/whatsapp/teste", headers=h, json={"telefone": "11987654321"})
    assert r.status_code == 409 and r.json()["erro"]["mensagem"] == graph.MSG_TOKEN
    assert ver(client, h)["ultimo_erro"] == graph.MSG_TOKEN


# ---- envio ------------------------------------------------------------------

def test_envio_automatico_pelo_modelo(client, admin, meta, dono):
    h = admin["h"]
    ligar(client, h)
    c = criar_contato(client, h, nome="João Lima", email=None, telefone="11987654321")
    r = disparar(client, h, [c["id"]])
    assert r.status_code == 202 and r.json() == {"agendados": 1, "ignorados": []}
    corpo, = meta.mensagens
    assert meta.pedidos[-1].url.path == f"/v23.0/{PNID}/messages"
    assert (corpo["messaging_product"], corpo["to"], corpo["type"]) == ("whatsapp", "5511987654321", "template")
    t = corpo["template"]
    assert t["name"] == "pesquisa_toqqi" and t["language"] == {"code": "pt_BR"}
    corpo_modelo, botao_url = t["components"]
    assert [p["text"] for p in corpo_modelo["parameters"]] == ["João", "Alfa Distribuidora", "nosso atendimento"]
    assert (botao_url["type"], botao_url["sub_type"], botao_url["index"]) == ("button", "url", "1")
    # o sufixo do botão é o token do convite: abre a pesquisa
    assert client.get(f"{API}/publico/convites/{botao(corpo)}").status_code == 200
    assert envios_db(dono) == [("whatsapp", "enviado", None, "wamid.1", "franquia", "5511987654321")]
    e, = historico(client, h)
    assert (e["canal"], e["situacao"], e["para"]) == ("whatsapp", "enviado", "5511987654321")
    assert ver(client, h)["franquia"]["usadas_mes"] == 1
    assert fila(client, h)[c["id"]]["situacao"] == "aguardando"


def test_evento_auto_e_canal_da_configuracao(client, admin, meta, dono):
    h = admin["h"]
    ligar(client, h, canal="whatsapp")
    chave = gerar_chave(client, h)
    r = evento(client, chave, email="joao@cliente.com.br", telefone="11987654321", nome="João", referencia="1234")
    assert r.status_code == 201 and (r.json()["situacao"], r.json()["canal"]) == ("enviado", "whatsapp")
    assert r.json()["mensagem"] == "Pesquisa enviada por WhatsApp."
    assert meta.mensagens[-1]["template"]["components"][0]["parameters"][2]["text"] == "seu pedido 1234"
    assert r.json()["link"].endswith("/r/" + botao(meta.mensagens[-1]))
    assert not emails_para("joao@cliente.com.br")
    # canal escolhido à força
    r = evento(client, chave, email="maria@cliente.com.br", telefone="11911112222", canal="email")
    assert r.json()["canal"] == "email" and emails_para("maria@cliente.com.br")
    # configuração "email": o e-mail vem antes; sem e-mail, ainda vai por WhatsApp
    ligar_envios(client, h, canal="email")
    r = evento(client, chave, email="rui@cliente.com.br", telefone="11922223333")
    assert r.json()["canal"] == "email"
    r = evento(client, chave, telefone="11933334444")
    assert r.json()["canal"] == "whatsapp"
    # WhatsApp desligado: só e-mail, ou só o link
    client.patch(f"{API}/integracoes/whatsapp", headers=h, json={"ativo": False})
    r = evento(client, chave, telefone="11944445555")
    assert r.json()["situacao"] == "link_gerado"


def test_avisos_da_meta_atualizam_a_situacao(client, admin, meta, dono):
    h = admin["h"]
    ligar(client, h)
    a = criar_contato(client, h, email=None, telefone="11987654321")
    b = criar_contato(client, h, email=None, telefone="11911112222")
    disparar(client, h, [a["id"], b["id"]])
    assert ver(client, h)["franquia"]["usadas_mes"] == 2

    def situacao(wamid):
        return sql(dono, "select situacao, erro from envios where wamid = :w", w=wamid)[0]

    for status, esperado in [("sent", "enviado"), ("delivered", "entregue"), ("read", "lido"), ("delivered", "lido")]:
        assert aviso_meta(client, aviso_status("wamid.1", status)).status_code == 200
        assert situacao("wamid.1").situacao == esperado
    aviso_meta(client, aviso_status("wamid.2", "failed", codigo=131026))
    assert tuple(situacao("wamid.2")) == ("erro", "O número não tem WhatsApp ou não pode receber a mensagem.")
    assert ver(client, h)["franquia"]["usadas_mes"] == 1          # a que não saiu volta para a franquia
    assert fila(client, h)[b["id"]]["situacao"] == "nao_saiu"
    assert {e["situacao"] for e in historico(client, h)} == {"lido", "erro"}
    assert len(historico(client, h, situacao="lido")) == 1

    # assinatura errada ou ausente
    r = aviso_meta(client, aviso_status("wamid.2", "read"), segredo="outro")
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "assinatura_invalida"
    assert client.post(f"{API}/publico/whatsapp/webhook", json=aviso_status("wamid.2", "read")).status_code == 401
    # número de ninguém: ignorado
    assert aviso_meta(client, aviso_status("wamid.1", "failed", pnid="999999")).status_code == 200
    assert situacao("wamid.1").situacao == "lido"


def test_verificacao_do_webhook(client, meta):
    url = f"{API}/publico/whatsapp/webhook"
    r = client.get(url, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "123"})
    assert r.status_code == 200 and r.text == "123"
    r = client.get(url, params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "123"})
    assert r.status_code == 403


def test_franquia_avisos_queda_para_email_e_excedente(client, admin, meta, dono):
    h = admin["h"]
    conta = admin["conta"]["id"]
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() + interval '10 days' where id = :c", c=conta)
    gravar_parametro(dono, "whatsapp.franquia.teste", 20)  # 5k: sem franquia por padrão; a equipe pode definir
    ligar(client, h)
    chave = gerar_chave(client, h)
    assert ver(client, h)["franquia"]["limite"] == 20 and ver(client, h)["franquia"]["plano"] == "teste"
    sql(dono, "insert into whatsapp_uso (conta_id, mes, usadas) values (:c, :m, 15)", c=conta, m=mes())

    r = evento(client, chave, telefone="11900000001", email="c1@cliente.com.br")
    assert r.json()["canal"] == "whatsapp"
    aviso = emails_para("ana@alfa.com.br")[-1]
    assert aviso.assunto == "Você já usou 80% da franquia de WhatsApp do mês" and "16 das 20" in aviso.texto
    sql(dono, "update whatsapp_uso set usadas = 19")
    assert evento(client, chave, telefone="11900000002").json()["canal"] == "whatsapp"
    aviso = emails_para("ana@alfa.com.br")[-1]
    assert aviso.assunto == "A franquia de WhatsApp do mês acabou" and "por e-mail" in aviso.texto
    # etapa 5e: os dois avisos entram no registro de e-mails enviados da conta
    assert sql(dono, "select assunto from emails_enviados where tipo = 'aviso' order by id") == [
        ("Você já usou 80% da franquia de WhatsApp do mês",), ("A franquia de WhatsApp do mês acabou",)]
    n_avisos = len(emails_para("ana@alfa.com.br"))

    # acabou: e-mail se houver, senão só o link
    r = evento(client, chave, telefone="11900000003", email="c3@cliente.com.br")
    assert r.json()["canal"] == "email" and emails_para("c3@cliente.com.br")
    assert evento(client, chave, telefone="11900000004").json()["situacao"] == "link_gerado"
    assert evento(client, chave, telefone="11900000005", canal="whatsapp").json()["situacao"] == "sem_canal"
    # robô / envio manual: só telefone fica de fora
    c6 = criar_contato(client, h, email=None, telefone="11900000006")
    r = disparar(client, h, [c6["id"]])
    assert r.json()["ignorados"][0]["motivo"] == "Sem e-mail e a franquia de WhatsApp do mês acabou"

    # excedente ligado: volta para o WhatsApp, contado à parte
    client.patch(f"{API}/integracoes/whatsapp", headers=h, json={"excedente_ativo": True})
    assert evento(client, chave, telefone="11900000007").json()["canal"] == "whatsapp"
    f = ver(client, h)["franquia"]
    assert (f["usadas_mes"], f["excedentes_mes"], f["excedente_ativo"]) == (20, 1, True)
    assert sql(dono, "select cobranca from envios order by id desc limit 1")[0][0] == "excedente"
    assert len(emails_para("ana@alfa.com.br")) == n_avisos       # cada aviso sai uma vez por mês


def test_whatsapp_com_email_de_reserva(client, admin, meta, dono):
    h = admin["h"]
    ligar(client, h, canal="whatsapp_e_email")
    meta.erro_envio = (400, {"code": 131026, "message": "Message undeliverable"})
    a = criar_contato(client, h, email="joao@cliente.com.br", telefone="11987654321")
    disparar(client, h, [a["id"]])
    assert [(c, s) for c, s, *_ in envios_db(dono)] == [("whatsapp", "erro"), ("email", "enviado")]
    assert envios_db(dono)[0].erro == "O número não tem WhatsApp ou não pode receber a mensagem."
    assert emails_para("joao@cliente.com.br")
    assert sql(dono, "select canal from convites")[0][0] == "email"
    assert ver(client, h)["franquia"]["usadas_mes"] == 0
    linha = fila(client, h)[a["id"]]
    assert linha["situacao"] == "aguardando"

    # só WhatsApp: não há reserva; conta como falha
    ligar_envios(client, h, canal="whatsapp")
    b = criar_contato(client, h, email="maria@cliente.com.br", telefone="11911112222")
    disparar(client, h, [b["id"]])
    assert not emails_para("maria@cliente.com.br")
    assert fila(client, h)[b["id"]]["situacao"] == "nao_saiu"
    assert sql(dono, "select falhas from contatos where id = :c", c=b["id"])[0][0] == 1
    # problema da conexão aparece na tela de Integrações
    meta.erro_envio = (401, {"code": 190, "message": "Error validating access token"})
    c = criar_contato(client, h, email=None, telefone="11922223333")
    disparar(client, h, [c["id"]])
    assert ver(client, h)["ultimo_erro"] == graph.MSG_TOKEN
    meta.erro_envio = None
    d = criar_contato(client, h, email=None, telefone="11933334444")
    disparar(client, h, [d["id"]])
    assert ver(client, h)["ultimo_erro"] is None


def test_sair_pelo_whatsapp_descadastra_o_telefone(client, admin, meta, dono, destino):
    h = admin["h"]
    ligar(client, h)
    client.post(f"{API}/integracoes/webhooks", headers=h,
                json={"url": "https://erp.cliente.com.br/x", "eventos": ["contato.descadastrado"]})
    c = criar_contato(client, h, nome="João", email="joao@cliente.com.br", telefone="11987654321")
    # o WhatsApp informa o celular sem o nono dígito
    assert aviso_meta(client, aviso_mensagem("551187654321", "Oi, tudo bem?")).status_code == 200
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0
    assert aviso_meta(client, aviso_mensagem("551187654321", "  Sáir! ")).status_code == 200
    assert sql(dono, "select email, telefone, origem from descadastros") == [(None, "5511987654321", "whatsapp")]
    resposta = meta.mensagens[-1]
    assert resposta == {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "551187654321",
                        "type": "text", "text": {"body": "Pronto! Você não vai mais receber pesquisas da "
                                                         "Alfa Distribuidora. Se mudar de ideia, responda VOLTAR."}}
    corpo = json.loads(destino.recebidos[0]["corpo"])
    assert corpo["dados"] == {"email_mascarado": "jo***@cliente.com.br", "contato_id": c["id"], "origem": "whatsapp"}

    # vale como o descadastro por e-mail, em todos os canais
    assert fila(client, h)[c["id"]]["situacao"] == "saiu_da_lista"
    r = client.post(f"{API}/contatos/{c['id']}/whatsapp", headers=h, json={})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "saiu_da_lista"
    assert disparar(client, h, [c["id"]]).json()["ignorados"][0]["motivo"] == "Saiu da lista"
    chave = gerar_chave(client, h)
    assert evento(client, chave, email="joao@cliente.com.br").json()["situacao"] == "ignorado_descadastrado"
    item, = client.get(f"{API}/envios/descadastros", headers=h).json()["itens"]
    assert (item["email"], item["telefone"], item["origem"], item["contato"]["id"]) == \
        (None, "5511987654321", "whatsapp", c["id"])

    # repetir não duplica, mas confirma de novo
    for palavra in ("PARAR", "stop", "Cancelar."):
        aviso_meta(client, aviso_mensagem("5511987654321", palavra))
    assert sql(dono, "select count(*) from descadastros")[0][0] == 1
    assert len(meta.mensagens) == 4
    assert len(destino.recebidos) == 1


def test_lembretes_no_maximo_um_por_whatsapp(client, admin, meta, monkeypatch):
    h = admin["h"]
    ligar(client, h)
    com_email = criar_contato(client, h, email="joao@cliente.com.br", telefone="11987654321")
    so_tel = criar_contato(client, h, email=None, telefone="11911112222")
    fixar_relogio(monkeypatch, segunda(9))
    disparar(client, h, [com_email["id"], so_tel["id"]])
    assert len(meta.mensagens) == 2

    fixar_relogio(monkeypatch, segunda(11, mais_dias=3))
    assert tarefas.executar("lembretes")["lembretes"] == {"contas": 1, "enviados": 2, "ignorados": 0}
    assert len(meta.mensagens) == 4 and not emails_para("joao@cliente.com.br")
    assert {e["canal"] for e in historico(client, h, tipo="lembrete")} == {"whatsapp"}

    fixar_relogio(monkeypatch, segunda(11, mais_dias=7))
    assert tarefas.executar("lembretes")["lembretes"] == {"contas": 1, "enviados": 1, "ignorados": 1}
    assert len(meta.mensagens) == 4
    m, = emails_para("joao@cliente.com.br")
    assert "Lembrete" in m.assunto
    # o lembrete por e-mail leva o mesmo link do convite por WhatsApp
    assert botao(meta.mensagens[0]) in m.texto


def test_isolamento_pelo_numero(client, admin, meta, dono):
    h = admin["h"]
    ligar(client, h)
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert conectar_whatsapp(client, b["h"], pnid="5555555555").status_code == 200
    c = criar_contato(client, h, email=None, telefone="11987654321")
    criar_contato(client, b["h"], email=None, telefone="11987654321")
    disparar(client, h, [c["id"]])
    # aviso que chega pelo número de B não mexe no envio de A
    aviso_meta(client, aviso_status("wamid.1", "read", pnid="5555555555"))
    assert sql(dono, "select situacao from envios")[0][0] == "enviado"
    aviso_meta(client, aviso_mensagem("5511987654321", "SAIR", pnid="5555555555"))
    assert sql(dono, "select conta_id from descadastros") == [(b["conta"]["id"],)]
    assert fila(client, h)[c["id"]]["situacao"] == "aguardando"


def test_franquia_conta_por_mes(client, admin, meta, dono, monkeypatch):
    h = admin["h"]
    ligar(client, h)
    c = criar_contato(client, h, email=None, telefone="11987654321")
    fixar_relogio(monkeypatch, datetime(2026, 9, 30, 23, 0, tzinfo=FUSO))
    disparar(client, h, [c["id"]], ignorar_descanso=True)
    fixar_relogio(monkeypatch, datetime(2026, 9, 30, 23, 0, tzinfo=FUSO) + timedelta(hours=2))
    disparar(client, h, [c["id"]], ignorar_descanso=True)
    assert sql(dono, "select mes, usadas from whatsapp_uso order by mes") == [("2026-09", 1), ("2026-10", 1)]
    assert ver(client, h)["franquia"]["usadas_mes"] == 1


def test_sem_franquia_por_padrao_conta_e_nao_avisa(client, admin, meta, dono):
    """Etapa 5k: o padrão é sem franquia (a Meta cobra a conta do cliente): tudo sai pelo WhatsApp, sem aviso."""
    h = admin["h"]
    conta = admin["conta"]["id"]
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() + interval '10 days' where id = :c", c=conta)
    ligar(client, h)
    chave = gerar_chave(client, h)
    sql(dono, "insert into whatsapp_uso (conta_id, mes, usadas) values (:c, :m, 5000)", c=conta, m=mes())
    assert ver(client, h)["franquia"]["limite"] is None
    r = evento(client, chave, telefone="11900000001", email="c1@cliente.com.br")
    assert r.json()["canal"] == "whatsapp"
    assert sql(dono, "select usadas, excedentes from whatsapp_uso where conta_id = :c", c=conta) == [(5001, 0)]
    assert not [m for m in emails_para("ana@alfa.com.br") if "franquia" in m.assunto]
