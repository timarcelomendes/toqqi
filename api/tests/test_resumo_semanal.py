"""Etapa 4b: resumo semanal — conteúdo de uma semana montada à mão, só na segunda depois das 8h (e até terça), uma
vez por semana, pula a conta parada e sem provedor de e-mail."""
import json
from datetime import datetime, time, timedelta

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    emails_para,
    fixar_relogio,
    form_padrao,
    membro,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.email import caixa_memoria
from toqqi.modulos.formularios.validacao import grupo_da_nota
from toqqi.modulos.relatorios.emails import semana_a_resumir
from toqqi.modulos.respostas.temas import detectar


@pytest.fixture
def conta(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, segunda(9))  # segunda-feira, 9h: resume a semana anterior
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    h = a["h"]
    a.update(nps=form_padrao(client, h)["id"], csat=form_padrao(client, h, "csat")["id"])
    a["rita"] = criar_responsavel(client, h, "Rita Gomes")
    a["empresa"] = criar_empresa(client, h, "Mercado Bom Preço")
    a["contato"] = criar_contato(client, h, nome="Paula Lima", empresa_id=a["empresa"]["id"])
    a["sem_empresa"] = criar_contato(client, h, nome="Rui Sem Empresa")
    a["semana"] = relogio.hoje() - timedelta(days=7)
    caixa_memoria.clear()
    return a


def resposta(dono, a, dia, nota: int, comentario: str = "", tipo: str = "nps", resumo_ia: str | None = None,
             ia_temas: list | None = None) -> int:
    quando = datetime.combine(dia, time(12), tzinfo=FUSO)
    (rid,), = sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, respondida_em, ia_situacao, ia_temas, ia_resumo)
        values (:conta, :f, :c, :e, 'manual', 'manual', :n, :t, :g, :com, :com, :temas, :quando, :sit,
                cast(:ia as jsonb), :resumo) returning id
    """, conta=a["conta"]["id"], f=a[tipo], c=a["contato"]["id"], e=a["empresa"]["id"], n=nota, t=tipo,
        g=grupo_da_nota(tipo, nota), com=comentario, temas=detectar(comentario), quando=quando,
        sit="analisada" if ia_temas is not None else None, ia=json.dumps(ia_temas) if ia_temas is not None else None,
        resumo=resumo_ia)
    return rid


def acao(dono, a, nota: int, prazo, grupo: str = "detrator", situacao: str = "a_fazer", empresa: bool = True,
         responsavel: bool = False) -> int:
    (aid,), = sql(dono, """
        insert into acoes (conta_id, empresa_id, contato_id, responsavel_id, titulo, prioridade, prazo, situacao,
                           origem, grupo, tipo_nota, nota)
        values (:conta, :e, :c, :r, 'Ação', 'alta', :prazo, :s, 'automatica', :g, 'nps', :n) returning id
    """, conta=a["conta"]["id"], e=a["empresa"]["id"] if empresa else None,
        c=a["contato"]["id"] if empresa else a["sem_empresa"]["id"], r=a["rita"]["id"] if responsavel else None,
        prazo=prazo, s=situacao, g=grupo, n=nota)
    return aid


def test_conteudo_de_uma_semana(client, conta, dono):
    a = conta
    w, hoje = a["semana"], relogio.hoje()
    # semana resumida (segunda a domingo): NPS 10, 9, 8, 3, 0, 2 → 2 P, 1 N, 3 D → −16,7 → −17; CSAT 1
    resposta(dono, a, w, 10, "Entrega rápida")
    resposta(dono, a, w + timedelta(days=1), 9)
    resposta(dono, a, w + timedelta(days=2), 8, "Vendedor demorou a responder")
    resposta(dono, a, w + timedelta(days=3), 3, "Frete caro e atrasou")
    resposta(dono, a, w + timedelta(days=4), 0, "Produto quebrado", resumo_ia="Reclama de produto quebrado",
             ia_temas=[{"tema": "produto_avarias", "sentimento": "negativo"}])
    resposta(dono, a, w + timedelta(days=5), 1, "Atrasou demais", tipo="csat")
    resposta(dono, a, w + timedelta(days=6), 2, "Atrasou outra vez")
    # semana anterior: 10, 10, 6 → 33; quatro semanas antes: 1 reclamação de prazo (média 0,25 → 0,3)
    for d, nota in ((7, 10), (6, 10), (5, 6)):
        resposta(dono, a, w - timedelta(days=d), nota)
    resposta(dono, a, w - timedelta(days=10), 4, "Atrasou")
    resposta(dono, a, w - timedelta(days=100), 10)  # fora dos 90 dias
    # ações abertas de detratores (vencidas primeiro, depois o prazo); neutra e concluída não entram
    ids = [acao(dono, a, 3, hoje - timedelta(days=3), responsavel=True), acao(dono, a, 0, hoje, empresa=False),
           acao(dono, a, 1, hoje + timedelta(days=1), grupo="insatisfeito"), acao(dono, a, 2, hoje - timedelta(days=1)),
           acao(dono, a, 4, None), acao(dono, a, 6, hoje + timedelta(days=5)),
           acao(dono, a, 7, hoje - timedelta(days=9), grupo="neutro"),
           acao(dono, a, 1, hoje - timedelta(days=9), situacao="concluida")]
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    periodo = f"{w.strftime('%d/%m')} a {(w + timedelta(days=6)).strftime('%d/%m')}"
    assert m.assunto == f"Resumo da semana ({periodo}): NPS -17"
    plano = "http://app.teste/planos-de-acao/"
    assert m.texto.split("\n\n") == [
        "NPS DA SEMANA",
        "NPS -17 (Crítico) · 6 respostas: 2 promotores, 1 neutro e 3 detratores.",
        "Variação: -50 em relação à semana anterior (NPS 33).",
        "Últimos 90 dias: NPS -10.",
        "DETRATORES SEM TRATAMENTO",
        "6 ações abertas de detratores, 2 vencidas.",
        f"Mercado Bom Preço · nota 3 · Rita Gomes · vencida há 3 dias: {plano}{ids[0]}",
        f"Mercado Bom Preço · nota 2 · sem responsável · vencida há 1 dia: {plano}{ids[3]}",
        f"Rui Sem Empresa · nota 0 · sem responsável · vence hoje: {plano}{ids[1]}",
        f"Mercado Bom Preço · nota 1 · sem responsável · vence amanhã: {plano}{ids[2]}",
        f"Mercado Bom Preço · nota 6 · sem responsável · vence em 5 dias: {plano}{ids[5]}",
        "TEMAS EM ALTA",
        "Prazo e entrega: 3 reclamações (média de 0,3 por semana nas 4 semanas anteriores) · pico",
        "Produto e avarias: 1 reclamação (média de 0,0 por semana nas 4 semanas anteriores)",
        "Preço e condições: 1 reclamação (média de 0,0 por semana nas 4 semanas anteriores)",
        "O QUE DISSERAM",
        "Mercado Bom Preço · nota 2: Atrasou outra vez",
        "Mercado Bom Preço · nota 1: Atrasou demais",
        "Mercado Bom Preço · nota 0: Reclama de produto quebrado",
        "Abrir o painel: http://app.teste/inicio",
        "Equipe Toqqi",
        "Você recebe este e-mail porque acompanha o painel da Alfa Distribuidora. Para parar, desligue em Minha "
        "conta. http://app.teste/minha-conta",
    ]
    assert f'href="{plano}{ids[0]}"' in m.html and 'href="http://app.teste/inicio"' in m.html
    assert '<a href="http://app.teste/minha-conta" style="color:#666">Minha conta</a>' in m.html
    (semana, enviado, destinatarios), = sql(dono, "select semana, enviado_em, destinatarios from resumos_semanais")
    assert semana == w and enviado is not None and destinatarios == 1
    # etapa 5e: entra no registro de e-mails enviados da conta
    assert sql(dono, "select conta_id, tipo, destinatario, assunto, situacao from emails_enviados "
                     "where tipo = 'resumo_semanal'") == [(a["conta"]["id"], "resumo_semanal", "ana@alfa.com.br",
                                                            m.assunto, "enviado")]


def test_semana_sem_nps_e_sem_detratores(client, conta, dono):
    a = conta
    resposta(dono, a, a["semana"] + timedelta(days=2), 5, "Tudo certo", tipo="csat")
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    assert m.assunto.startswith("Resumo da semana (") and "NPS" not in m.assunto
    partes = m.texto.split("\n\n")
    assert partes[1:3] == ["Nenhuma resposta de NPS na semana.", "Últimos 90 dias: sem respostas de NPS."]
    assert "Nenhum detrator esperando tratamento." in partes and "Nenhuma reclamação na semana." in partes
    assert "O QUE DISSERAM" in partes  # o comentário do CSAT


@pytest.mark.parametrize("momento,semana", [
    (datetime(2026, 10, 5, 7, 59), None),                 # segunda antes das 8h
    (datetime(2026, 10, 5, 8, 0), "2026-09-28"),          # segunda a partir das 8h
    (datetime(2026, 10, 6, 23, 59), "2026-09-28"),        # terça até 23:59
    (datetime(2026, 10, 7, 0, 0), None),                  # quarta: a semana foi pulada
    (datetime(2026, 10, 4, 12, 0), None),                 # domingo
])
def test_so_na_segunda_depois_das_8h_e_ate_terca(momento, semana):
    resultado = semana_a_resumir(momento.replace(tzinfo=FUSO))
    assert (resultado.isoformat() if resultado else None) == semana


def test_uma_vez_por_semana_e_fora_do_horario(client, conta, dono, monkeypatch):
    a = conta
    resposta(dono, a, a["semana"], 3, "Atrasou")
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    assert tarefas.executar("resumo")["resumo"] == {"contas": 0, "emails": 0}  # já saiu nesta semana
    fixar_relogio(monkeypatch, segunda(9) + timedelta(days=1, hours=14))  # terça 23h: ainda é a mesma semana
    assert tarefas.executar("resumo")["resumo"] == {"contas": 0, "emails": 0}
    assert len(emails_para("ana@alfa.com.br")) == 1
    assert sql(dono, "select count(*) from resumos_semanais")[0][0] == 1
    fixar_relogio(monkeypatch, segunda(9) + timedelta(days=3))  # quinta: fora do horário
    resposta(dono, a, relogio.hoje() - timedelta(days=1), 2, "Atrasou")
    assert tarefas.executar("resumo")["resumo"] == {"contas": 0, "emails": 0}
    fixar_relogio(monkeypatch, segunda(9) + timedelta(days=7))  # segunda seguinte: a semana nova
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    assert sql(dono, "select count(*) from resumos_semanais")[0][0] == 2


@pytest.mark.parametrize("ajuste", ["parada", "sem_provedor", "assinatura", "preferencia"])
def test_quem_nao_recebe(client, conta, dono, monkeypatch, ajuste):
    a = conta
    if ajuste != "parada":
        resposta(dono, a, a["semana"], 3, "Atrasou")
    if ajuste == "sem_provedor":
        monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
        monkeypatch.setattr(config(), "AMBIENTE", "producao")
    elif ajuste == "assinatura":
        sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=a["conta"]["id"])
    elif ajuste == "preferencia":
        client.patch(f"{API}/eu", headers=a["h"], json={"recebe_resumo_semanal": False})
        m = membro(client, a["h"], "gil@alfa.com.br", "gestor")
        assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
        assert [x.para for x in caixa_memoria] == ["gil@alfa.com.br"] and m
        return
    assert tarefas.executar("resumo")["resumo"] == {"contas": 0, "emails": 0}
    assert caixa_memoria == []
    if ajuste == "parada":  # sem respostas na semana e sem ações abertas: nem registra
        assert sql(dono, "select count(*) from resumos_semanais")[0][0] == 0


def test_conta_so_com_acoes_abertas_recebe(client, conta, dono):
    a = conta
    acao(dono, a, 2, relogio.hoje() - timedelta(days=2))
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    assert "1 ação aberta de detratores, 1 vencida." in m.texto.split("\n\n")


def test_sem_variacao_e_acoes_de_empresa_inativa_ficam_de_fora(client, conta, dono):
    """Como no painel ("só empresas ativas"): ações de empresa inativa não entram; NPS igual = "Sem variação"."""
    a = conta
    w, hoje = a["semana"], relogio.hoje()
    resposta(dono, a, w + timedelta(days=1), 10)
    resposta(dono, a, w - timedelta(days=3), 10)
    inativa = criar_empresa(client, a["h"], "Mercearia Antiga")
    sql(dono, "update empresas set ativa = false where id = :e", e=inativa["id"])
    ativa = acao(dono, a, 3, hoje - timedelta(days=2))
    fora = acao(dono, a, 1, hoje - timedelta(days=5))
    sql(dono, "update acoes set empresa_id = :e where id = :a", e=inativa["id"], a=fora)
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    partes = m.texto.split("\n\n")
    assert "Sem variação em relação à semana anterior (NPS 100)." in partes
    assert "1 ação aberta de detratores, 1 vencida." in partes
    assert any(f"/planos-de-acao/{ativa}" in x for x in partes) and not any(f"/planos-de-acao/{fora}" in x for x in partes)
