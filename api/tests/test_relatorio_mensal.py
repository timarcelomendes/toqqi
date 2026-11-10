"""Relatório mensal em PDF: o download (mês válido, permissão, conteúdo com os números do painel e texto do cliente
com caracteres que a fonte não desenha) e o e-mail do dia 1 (só do dia 1 às 8h ao dia 3, uma vez por mês, PDF anexo,
pula o mês sem respostas, respeita a preferência e o provedor de e-mail)."""
import io
from datetime import date, datetime, time, timedelta

import pytest
from pypdf import PdfReader
from util import API, FUSO, conta_pronta, criar_contato, criar_empresa, emails_para, fixar_relogio, form_padrao, membro, sql

from toqqi import tarefas
from toqqi.core.config import config
from toqqi.core.email import caixa_memoria
from toqqi.modulos.formularios.validacao import grupo_da_nota
from toqqi.modulos.relatorios import mensal
from toqqi.modulos.respostas.temas import detectar

HOJE = datetime.now(FUSO).date()
MES = date(HOJE.year, HOJE.month, 1)  # o mês relatado
SEGUINTE = date(MES.year + MES.month // 12, MES.month % 12 + 1, 1)


def _texto(pdf: bytes) -> str:
    return " ".join(" ".join((p.extract_text() or "").split()) for p in PdfReader(io.BytesIO(pdf)).pages)


@pytest.fixture
def conta(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, datetime.combine(SEGUINTE, time(9), tzinfo=FUSO))  # dia 1 do mês seguinte, 9h
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    h = a["h"]
    a.update(nps=form_padrao(client, h)["id"], csat=form_padrao(client, h, "csat")["id"])
    a["empresa"] = criar_empresa(client, h, "Mercado Bom Preço")
    a["contato"] = criar_contato(client, h, nome="Paula Lima", empresa_id=a["empresa"]["id"])
    caixa_memoria.clear()
    return a


def resposta(dono, a, dia: date, nota: int, comentario: str = "", tipo: str = "nps") -> None:
    sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, respondida_em)
        values (:conta, :f, :c, :e, 'manual', 'manual', :n, :t, :g, :com, :com, :temas, :quando)
    """, conta=a["conta"]["id"], f=a[tipo], c=a["contato"]["id"], e=a["empresa"]["id"], n=nota, t=tipo,
        g=grupo_da_nota(tipo, nota), com=comentario, temas=detectar(comentario), quando=datetime.combine(dia, time(12), tzinfo=FUSO))


def _baixar(client, h, mes: str | None = None):
    return client.get(f"{API}/relatorios/mensal.pdf", headers=h, params={"mes": mes} if mes else None)


def test_baixar_o_pdf_do_mes(client, conta, dono):
    a = conta
    for dia, nota in ((1, 10), (2, 10), (3, 9), (4, 7), (5, 3)):  # 3 P, 1 N, 1 D → NPS 40
        resposta(dono, a, MES + timedelta(days=dia - 1), nota, "Entrega rápida 🚚 & atendimento <bom>" if nota == 10
                 else "Atrasou a entrega" if nota == 3 else "")
    resposta(dono, a, MES + timedelta(days=2), 5, "Muito bom", tipo="csat")
    resposta(dono, a, MES - timedelta(days=3), 0)  # mês anterior: NPS −100 → variação +140
    r = _baixar(client, a["h"], f"{MES:%Y-%m}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == f'attachment; filename="toqqi-relatorio-{MES:%Y-%m}.pdf"'
    assert r.content.startswith(b"%PDF")
    texto = _texto(r.content)
    assert f"Relatório de {mensal.nome_mes(MES)}" in texto and "Alfa Distribuidora" in texto
    assert "NPS do mês 40" in texto and "+140 sobre o mês anterior (-100)" in texto
    assert "3 promotores (60%)" in texto and "1 neutros (20%)" in texto and "1 detratores (20%)" in texto
    assert "CSAT: 100% de satisfeitos (1 de 1)" in texto
    assert "NPS nos últimos 12 meses" in texto and "O que mais citaram" in texto and "Prazo e entrega" in texto
    assert "Mercado Bom Preço (Paula Lima)" in texto
    assert "Entrega rápida & atendimento <bom>" in texto  # o emoji sai, &, < e > ficam
    # sem mês: o mês anterior ao de hoje (o relógio está no dia 1 do mês seguinte)
    r = _baixar(client, a["h"])
    assert r.headers["content-disposition"].endswith(f'toqqi-relatorio-{MES:%Y-%m}.pdf"')


@pytest.mark.parametrize("mes", ["2026-13", "26-10", "1999-12", "abc"])
def test_mes_invalido(client, conta, mes):
    r = _baixar(client, conta["h"], mes)
    assert r.status_code == 422 and "mes" in r.json()["erro"]["campos"]


def test_mes_futuro_e_permissao(client, conta):
    futuro = date(SEGUINTE.year + SEGUINTE.month // 12, SEGUINTE.month % 12 + 1, 1)
    assert _baixar(client, conta["h"], f"{futuro:%Y-%m}").status_code == 422
    assert _baixar(client, conta["h"], f"{SEGUINTE:%Y-%m}").status_code == 200  # o mês atual, até hoje
    assert "mês em andamento" in _texto(_baixar(client, conta["h"], f"{SEGUINTE:%Y-%m}").content)
    consulta = membro(client, conta["h"], "caio@alfa.com.br", perfil="consulta")
    assert _baixar(client, consulta["h"], f"{MES:%Y-%m}").status_code == 200  # consulta vê relatórios
    assert client.get(f"{API}/relatorios/mensal.pdf").status_code == 401


def test_mes_sem_respostas_tem_pdf_mas_nao_tem_email(client, conta):
    r = _baixar(client, conta["h"], f"{MES:%Y-%m}")
    assert r.status_code == 200 and "Nenhuma resposta de NPS no mês." in _texto(r.content)
    assert tarefas.executar("mensal")["mensal"] == {"contas": 0, "emails": 0}


def test_email_do_dia_1_com_o_pdf(client, conta, dono, monkeypatch):
    a = conta
    resposta(dono, a, MES + timedelta(days=1), 9, "Ótimo")
    gil = membro(client, a["h"], "gil@alfa.com.br", perfil="gestor")
    # Gil desliga o relatório em Minha conta
    r = client.patch(f"{API}/eu", headers=gil["h"], json={"recebe_relatorio_mensal": False})
    assert r.status_code == 200 and r.json()["recebe_relatorio_mensal"] is False
    assert tarefas.executar("mensal")["mensal"] == {"contas": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    assert not emails_para("gil@alfa.com.br")
    assert m.assunto == f"Relatório de {mensal.nome_mes(MES)}: NPS 100"
    anexo, = m.anexos
    assert anexo.nome == f"toqqi-relatorio-{MES:%Y-%m}.pdf" and anexo.tipo == "application/pdf"
    assert "NPS do mês 100" in _texto(anexo.conteudo)
    assert "Abrir os relatórios: http://app.teste/relatorios" in m.texto
    (mes, enviado, destinatarios), = sql(dono, "select mes, enviado_em, destinatarios from relatorios_mensais")
    assert mes == MES and enviado is not None and destinatarios == 1
    assert sql(dono, "select tipo from emails_enviados where destinatario = 'ana@alfa.com.br' "
                     "and tipo = 'relatorio_mensal'") == [("relatorio_mensal",)]
    # a segunda rodada no mesmo mês não manda de novo
    assert tarefas.executar("mensal")["mensal"] == {"contas": 0, "emails": 0}


@pytest.mark.parametrize("dia,hora,manda", [(1, 7, False), (1, 8, True), (3, 23, True), (4, 9, False), (15, 9, False)])
def test_so_do_dia_1_as_8h_ao_dia_3(client, conta, dono, monkeypatch, dia, hora, manda):
    resposta(dono, conta, MES + timedelta(days=1), 9)
    fixar_relogio(monkeypatch, datetime.combine(SEGUINTE.replace(day=dia), time(hora), tzinfo=FUSO))
    assert tarefas.executar("mensal")["mensal"] == ({"contas": 1, "emails": 1} if manda else {"contas": 0, "emails": 0})


def test_sem_provedor_real_nao_manda(client, conta, dono, monkeypatch):
    resposta(dono, conta, MES + timedelta(days=1), 9)
    monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
    monkeypatch.setattr(config(), "AMBIENTE", "producao")
    assert tarefas.executar("mensal")["mensal"] == {"contas": 0, "emails": 0}


def test_pdf_mostra_planos_de_acao_e_receita_em_risco(client, conta, dono):
    a = conta
    sql(dono, "update empresas set valor_mensal = 1500 where id = :e", e=a["empresa"]["id"])
    resposta(dono, a, MES + timedelta(days=1), 2, "Produto chegou quebrado")
    sql(dono, """insert into acoes (conta_id, empresa_id, contato_id, titulo, prioridade, prazo, situacao, origem, grupo,
                                    tipo_nota, nota)
                 values (:c, :e, :p, 'Ligar', 'alta', :prazo, 'a_fazer', 'automatica', 'detrator', 'nps', 2)""",
        c=a["conta"]["id"], e=a["empresa"]["id"], p=a["contato"]["id"], prazo=MES)
    texto = _texto(_baixar(client, a["h"], f"{MES:%Y-%m}").content)
    assert "R$ 1.500,00" in texto and "1 empresa com detrator" in texto
    assert "1 plano aberto, 1 vencido." in texto and "Sem responsável" in texto
