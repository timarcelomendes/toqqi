"""Auditoria (etapa 5f): todo evento em exatamente um grupo, `GET /auditoria/grupos`, o filtro `grupo` (outra chave →
422), `grupo` em cada item e os eventos novos: envio automático e lembretes (pela tarefa e pelo "executar agora"),
chave gerada de novo e webhooks criados, alterados e excluídos."""
import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    fixar_relogio,
    gerar_chave,
    ligar_envios,
    membro,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.core.auditoria import GRUPO_DO_EVENTO, GRUPOS, ROTULOS, grupo_de


def test_todo_evento_em_um_grupo_so():
    assert set(GRUPO_DO_EVENTO) == set(ROTULOS)
    assert set(GRUPO_DO_EVENTO.values()) == set(GRUPOS)
    assert list(GRUPOS) == ["acesso", "equipe", "configuracoes", "envios", "dados", "exclusoes", "integracoes",
                            "assinatura"]
    esperado = {
        "login_ok": "acesso", "login_falhou": "acesso", "cadastro_conta": "acesso", "senha_alterada": "acesso",
        "sessao_encerrada": "acesso", "seguranca_alterada": "acesso", "termos_revogados": "acesso",
        "usuario_criado": "equipe", "usuario_bloqueado": "equipe", "permissoes_alteradas": "equipe",
        "usuario_excluido": "exclusoes", "config_envios": "configuracoes", "logo_removido": "configuracoes",
        "formulario_padrao": "configuracoes", "formulario_arquivado": "configuracoes",
        "imagem_enviada": "configuracoes", "ia_analisar_recentes": "configuracoes", "envio_manual": "envios",
        "envio_automatico": "envios", "lembretes_automaticos": "envios", "descadastro_desfeito": "envios",
        "importacao": "dados", "importacao_respostas": "dados", "resposta_editada": "dados",
        "indicacao_atualizada": "dados", "exportacao_conta": "dados", "exportacao_csv": "dados",
        "empresa_excluida": "exclusoes", "imagem_excluida": "exclusoes", "webhook_excluido": "exclusoes",
        "zona_risco": "exclusoes", "chave_regerada": "integracoes", "webhook_desativado": "integracoes",
        "webhook_criado": "integracoes", "whatsapp_conectado": "integracoes", "conta_excluida": "assinatura",
        "conta_excluida_automatica": "assinatura", "exclusao_automatica": "assinatura",
        "exclusao_avisada": "assinatura", "pagamento_vencido": "assinatura", "teste_estendido": "assinatura",
    }
    assert {e: grupo_de(e) for e in esperado} == esperado


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


def _auditoria(client, h, **filtros) -> dict:
    r = client.get(f"{API}/auditoria", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def test_grupos_e_filtro(client, admin):
    h = admin["h"]
    r = client.get(f"{API}/auditoria/grupos", headers=h)
    assert r.status_code == 200
    assert r.json()[0] == {"chave": "acesso", "rotulo": "Acesso e segurança"}
    assert [g["chave"] for g in r.json()] == list(GRUPOS)
    gerar_chave(client, h)
    tudo = _auditoria(client, h)["itens"]
    assert {(i["evento"], i["grupo"]) for i in tudo} >= {("login_ok", "acesso"), ("chave_gerada", "integracoes")}
    so_acesso = _auditoria(client, h, grupo="acesso")
    assert so_acesso["total"] >= 2 and {i["grupo"] for i in so_acesso["itens"]} == {"acesso"}
    assert [i["evento"] for i in _auditoria(client, h, grupo="integracoes")["itens"]] == ["chave_gerada"]
    assert _auditoria(client, h, grupo="")["total"] == len(tudo)
    r = client.get(f"{API}/auditoria", headers=h, params={"grupo": "outro"})
    assert r.status_code == 422 and "grupo" in r.json()["erro"]["campos"]
    g = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/auditoria/grupos", headers=g["h"]).status_code == 403


def _eventos(dono, conta_id: int, evento: str) -> list[tuple]:
    return sql(dono, "select gravidade, detalhe, usuario_id from auditoria where conta_id = :c and evento = :e "
                     "order by id", c=conta_id, e=evento)


def test_envio_automatico_e_lembretes(client, admin, dono, monkeypatch):
    h, c = admin["h"], admin["conta"]["id"]
    ligar_envios(client, h, envio_automatico=True)
    criar_contato(client, h, email="x@c.com.br")
    fixar_relogio(monkeypatch, segunda(10))
    tarefas.executar("robo")
    assert _eventos(dono, c, "envio_automatico") == [
        ("info", {"agendados": 1, "ignorados": 0, "executado_agora": False}, None)]
    tarefas.executar("robo")  # nada agendado pela tarefa: nada registrado
    assert len(_eventos(dono, c, "envio_automatico")) == 1
    # "executar agora" registra mesmo sem agendar, com quem pediu
    assert client.post(f"{API}/envios/robo/executar", headers=h).json() == {"agendados": 0, "ignorados": 0}
    assert _eventos(dono, c, "envio_automatico")[-1] == (
        "info", {"agendados": 0, "ignorados": 0, "executado_agora": True}, admin["usuario"]["id"])
    # lembretes: o primeiro sai 3 dias depois (padrão)
    fixar_relogio(monkeypatch, segunda(11, mais_dias=3))
    tarefas.executar("lembretes")
    assert _eventos(dono, c, "lembretes_automaticos") == [
        ("info", {"enviados": 1, "ignorados": 0, "executado_agora": False}, None)]
    assert client.post(f"{API}/envios/lembretes/executar", headers=h).json() == {"enviados": 0, "ignorados": 0}
    assert _eventos(dono, c, "lembretes_automaticos")[-1] == (
        "info", {"enviados": 0, "ignorados": 0, "executado_agora": True}, admin["usuario"]["id"])


def test_chave_gerada_de_novo(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    primeira = client.post(f"{API}/integracoes/chave", headers=h).json()["prefixo"]
    segunda_chave = client.post(f"{API}/integracoes/chave", headers=h).json()["prefixo"]
    assert [d for _, d, _ in _eventos(dono, c, "chave_gerada")] == [{"prefixo": primeira}]
    assert _eventos(dono, c, "chave_regerada") == [
        ("atencao", {"prefixo": segunda_chave, "prefixo_anterior": primeira}, admin["usuario"]["id"])]


def test_webhooks_criado_alterado_excluido(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://erp.cliente.com.br/ganchos", "eventos": ["resposta.criada"]}).json()
    assert _eventos(dono, c, "webhook_criado") == [
        ("info", {"webhook_id": w["id"], "url": "https://erp.cliente.com.br/ganchos", "campos": ["url", "eventos"]},
         admin["usuario"]["id"])]
    client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h,
                 json={"ativo": False, "eventos": ["resposta.criada"]})  # eventos iguais: não conta
    client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h, json={"ativo": False})  # nada mudou
    client.post(f"{API}/integracoes/webhooks/{w['id']}/novo-segredo", headers=h)
    assert [d for _, d, _ in _eventos(dono, c, "webhook_alterado")] == [
        {"webhook_id": w["id"], "campos": ["ativo"]}, {"webhook_id": w["id"], "campos": ["segredo"]}]
    assert client.delete(f"{API}/integracoes/webhooks/{w['id']}", headers=h).status_code == 204
    assert _eventos(dono, c, "webhook_excluido") == [
        ("atencao", {"webhook_id": w["id"], "url": "https://erp.cliente.com.br/ganchos"}, admin["usuario"]["id"])]
    assert {i["grupo"] for i in _auditoria(client, h, grupo="exclusoes")["itens"]} == {"exclusoes"}
