"""Exportação de todos os dados (etapa 5f) e "Exportar CSV" de Contatos e Empresas: arquivos e cabeçalhos exatos,
convenção do CSV, ids que batem, nenhum segredo, conta encerrada exporta, gestor 403, 409, 429, auditoria, só a própria
conta, desempenho (5.000 contatos e 50.000 respostas) e o CSV das listas igual à lista."""
import csv
import io
import time
import tracemalloc
import zipfile

import pytest
from sqlalchemy import text
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    definir_plano,
    encher_contatos,
    form_padrao,
    gerar_chave,
    membro,
    registrar_resposta,
    responder_convite,
    sql,
)

from toqqi.modulos.dados import exportacao

ARQUIVOS = ["LEIA-ME.txt", "empresas.csv", "responsaveis.csv", "cadastros.csv", "contatos.csv", "formularios.csv",
            "respostas.csv", "respostas-perguntas.csv", "planos-de-acao.csv", "convites.csv", "envios.csv",
            "descadastros.csv", "cobrancas.csv", "indicacoes.csv", "ofertas.csv", "equipe.csv",
            "aceites-dos-termos.csv", "auditoria.csv", "emails-enviados.csv", "configuracoes.csv"]
CONTEXTO = ["Pedido", "Nota fiscal", "Rota", "Motorista", "Filial", "Transportadora"]
CABECALHOS = {
    "empresas.csv": ["ID", "Nome", "CPF/CNPJ", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde",
                     "Código externo", "Ativa", "Criada em"],
    "responsaveis.csv": ["ID", "Nome", "Função", "E-mail", "Criado em"],
    "cadastros.csv": ["Tipo", "Nome", "Criado em"],
    "contatos.csv": ["ID", "Código", "Nome", "E-mail", "Telefone", "ID da empresa", "Empresa", "Cargo", "Perfil",
                     "Código externo", "Recebe pesquisas", "Ativo", "Última nota", "Último envio", "Próximo envio",
                     "Criado em"],
    "formularios.csv": ["ID", "Nome", "Descrição", "Tipo", "Ativo", "Público", "Padrão", "Arquivado", "Link público",
                        "Criado em", "Atualizado em", "Perguntas (JSON)", "Tema (JSON)"],
    "respostas.csv": ["ID", "Formulário", "ID do contato", "ID da empresa", "ID do convite", "Data", "Contato",
                      "E-mail", "Empresa", "Grupo de empresas", "Perfil", "Tipo", "Nota", "Categoria", "Temas",
                      "Comentário", "O que faltou", "O que combinamos", "Canal", "Origem", "Referência", *CONTEXTO,
                      "Arquivada", "Sentimento", "Resumo da IA", "Data de entrada"],
    "respostas-perguntas.csv": ["ID da resposta", "Formulário", "ID da pergunta", "Pergunta", "Resposta"],
    "planos-de-acao.csv": ["ID", "Título", "Descrição", "Prioridade", "Situação", "Prazo", "Origem", "Categoria",
                           "Tipo", "Nota", "ID da resposta", "ID da empresa", "Empresa", "ID do contato", "Contato",
                           "Responsável", "Resolução", "Passos da IA", "Criada por", "Criada em", "Iniciada em",
                           "Concluída em", "Concluída por"],
    "convites.csv": ["ID", "Data", "Formulário", "ID do contato", "Contato", "E-mail", "ID da empresa", "Canal",
                     "Assunto", "Referência", "Evento", *CONTEXTO, "Lembretes enviados", "Respondido em"],
    "envios.csv": ["ID", "Data", "ID do convite", "ID do contato", "Contato", "Para", "Canal", "Tipo", "Origem",
                   "Situação", "Erro", "Lembrete", "Enviado em", "Enviado por"],
    "descadastros.csv": ["E-mail", "Telefone", "Motivo", "Origem", "Data", "Registrado por"],
    "cobrancas.csv": ["Vencimento", "Valor", "Situação", "Forma", "Pago em"],
    "indicacoes.csv": ["ID", "Data", "Nome", "Empresa", "Telefone", "E-mail", "Observação", "Indicada por (empresa)",
                       "Indicada por (contato)", "Pode dizer quem indicou", "Origem", "Responsável", "Situação",
                       "Valor mensal", "Motivo", "Atualizada em"],
    "ofertas.csv": ["ID", "Data", "ID da empresa", "Empresa", "Contato", "Lista", "Canal", "Texto", "Feita por",
                    "Resultado", "Valor", "Resultado em"],
    "equipe.csv": ["ID", "Nome", "E-mail", "Cargo", "Telefone", "Perfil", "Situação", "E-mail confirmado",
                   "Último acesso", "Criado em", "Recebe resumo semanal", "Recebe alertas"],
    "aceites-dos-termos.csv": ["Nome", "E-mail", "Versão", "Aceito em", "Origem", "Retirado em"],
    "auditoria.csv": ["Data", "Evento", "Código", "Grupo", "Gravidade", "Usuário", "Detalhe (JSON)", "IP"],
    "emails-enviados.csv": ["Data", "Tipo", "Destinatário", "Assunto", "Situação", "Erro"],
    "configuracoes.csv": ["Seção", "Item", "Valor"],
}


def _baixar(client, h):
    return client.get(f"{API}/conta/exportacao.zip", headers=h)


def _abrir(conteudo: bytes) -> tuple[zipfile.ZipFile, dict[str, list[list[str]]]]:
    zf = zipfile.ZipFile(io.BytesIO(conteudo))
    planilhas = {}
    for nome in zf.namelist():
        if nome.endswith(".csv"):
            bruto = zf.read(nome).decode("utf-8")
            assert bruto.startswith("﻿"), nome
            assert bruto.split("\n", 1)[0].endswith("\r") and bruto.endswith("\r\n"), nome  # CRLF
            planilhas[nome] = list(csv.reader(io.StringIO(bruto[1:], newline=""), delimiter=";"))
    return zf, planilhas


def _linhas(planilha: list[list[str]]) -> list[dict]:
    return [dict(zip(planilha[0], linha)) for linha in planilha[1:]]


@pytest.fixture
def conta(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuição Ltda.")
    h = a["h"]
    resp = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br")
    e1 = criar_empresa(client, h, "Mercado Um", valor_mensal="1234.5", cliente_desde="2024-03-01",
                       responsavel_id=resp["id"])
    c1 = criar_contato(client, h, nome="=Carla Um", email="carla@um.com.br", telefone="11987654321",
                       empresa_id=e1["id"])
    c2 = criar_contato(client, h, nome="Davi Dois", email="davi@dois.com.br")
    responder_convite(client, h, c1["id"], 3, comentario="-Demorou demais")
    assert registrar_resposta(client, h, c2["id"], 10).status_code == 201
    return {"a": a, "h": h, "c": a["conta"]["id"], "e1": e1, "c1": c1, "c2": c2}


def test_arquivos_cabecalhos_e_convencao(client, dono, conta):
    r = _baixar(client, conta["h"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    hoje = sql(dono, "select (now() at time zone 'America/Sao_Paulo')::date")[0][0]
    assert r.headers["content-disposition"] == f'attachment; filename="toqqi-alfa-distribuicao-ltda-{hoje}.zip"'
    zf, planilhas = _abrir(r.content)
    assert zf.namelist() == ARQUIVOS
    assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in zf.infolist())
    for nome, cabecalho in CABECALHOS.items():
        assert planilhas[nome][0] == cabecalho, nome
    leia = zf.read("LEIA-ME.txt").decode("utf-8")
    assert "contatos.csv" in leia and "registros de acesso" in leia and "\r\n" in leia
    # convenção: datas de São Paulo, vírgula decimal, Sim/Não, proteção contra fórmula, rótulos das telas
    (empresa,) = _linhas(planilhas["empresas.csv"])
    assert (empresa["Valor mensal"], empresa["Cliente desde"], empresa["Ativa"], empresa["Responsável"]) == (
        "1234,50", "01/03/2024", "Sim", "Rita Gomes")
    contatos = {x["ID"]: x for x in _linhas(planilhas["contatos.csv"])}
    carla = contatos[str(conta["c1"]["id"])]
    assert carla["Nome"] == "'=Carla Um" and carla["Telefone"] == "(11) 98765-4321"
    assert carla["Recebe pesquisas"] == "Sim" and carla["Empresa"] == "Mercado Um"
    assert carla["Criado em"][2] == "/" and carla["Criado em"][-3] == ":"
    respostas = _linhas(planilhas["respostas.csv"])
    assert [x["ID do contato"] for x in respostas] == [str(conta["c1"]["id"]), str(conta["c2"]["id"])]
    assert respostas[0]["Comentário"].startswith("'-Demorou") and respostas[0]["Tipo"] == "NPS"
    assert respostas[0]["ID do convite"] and respostas[1]["ID do convite"] == ""
    perguntas = _linhas(planilhas["respostas-perguntas.csv"])
    assert {p["ID da resposta"] for p in perguntas} == {x["ID"] for x in respostas}
    assert any(p["Resposta"] == "'-Demorou demais" for p in perguntas)
    assert all("{empresa}" not in p["Pergunta"] for p in perguntas)
    acoes = _linhas(planilhas["planos-de-acao.csv"])
    assert acoes and acoes[0]["ID da resposta"] == respostas[0]["ID"] and acoes[0]["Origem"] == "Automática"
    formularios = _linhas(planilhas["formularios.csv"])
    assert {f["Tipo"] for f in formularios} == {"NPS", "CSAT"} and all("/f/" in f["Link público"] for f in formularios)
    (eu,) = _linhas(planilhas["equipe.csv"])
    assert (eu["E-mail"], eu["Perfil"], eu["E-mail confirmado"]) == ("ana@alfa.com.br", "Administrador", "Sim")
    (aceite,) = _linhas(planilhas["aceites-dos-termos.csv"])
    assert aceite["Origem"] == "Cadastro" and aceite["E-mail"] == "ana@alfa.com.br"
    auditoria = _linhas(planilhas["auditoria.csv"])
    assert {"Conta criada", "Entrou no sistema"} <= {x["Evento"] for x in auditoria}
    assert {x["Grupo"] for x in auditoria if x["Código"] == "login_ok"} == {"Acesso e segurança"}
    config = {(x["Seção"], x["Item"]): x["Valor"] for x in _linhas(planilhas["configuracoes.csv"])}
    assert config[("Dados da empresa", "Nome")] == "Alfa Distribuição Ltda."
    assert config[("Plano e situação", "Situação")] == "Em teste"
    assert config[("Permissões", "Gestor: Ver o painel")] == "Sim"
    assert config[("Chave de integração", "Começo da chave")] == "Nenhuma chave gerada"


def test_nenhum_segredo(client, dono, conta, meta):
    from util import conectar_whatsapp

    h, c = conta["h"], conta["c"]
    chave = gerar_chave(client, h)
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://erp.cliente.com.br/ganchos", "eventos": ["resposta.criada"]})
    assert w.status_code == 201, w.text
    assert conectar_whatsapp(client, h).status_code in (200, 201)
    sql(dono, "update responsaveis set teams_webhook = 'https://outlook.office.com/webhook/segredo-teams', "
              "foto_url = 'https://fotos.exemplo/rita.png' where conta_id = :c", c=c)
    # o IP e o navegador do aceite não vão (o IP da auditoria vai: em teste os dois seriam "testclient")
    sql(dono, "update aceites_termos set ip = '203.0.113.77', agente = 'Navegador Secreto 1.0' where conta_id = :c",
        c=c)
    form = form_padrao(client, h)
    from util import responder_link
    responder_link(client, form["codigo_publico"], {form["perguntas"][0]["id"]: 8})
    r = _baixar(client, h)
    assert r.status_code == 200, r.text
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    tudo = "\n".join(zf.read(n).decode("utf-8") for n in zf.namelist())
    segredos = [chave]
    for consulta in ("select senha_hash from usuarios", "select token_hash from tokens_uso_unico",
                     "select token_hash from convites", "select token_semente from convites",
                     "select hash from integracao_chaves", "select segredo_cifrado from webhooks",
                     "select token_cifrado from whatsapp_contas", "select teams_webhook from responsaveis",
                     "select foto_url from responsaveis", "select ip_hash from respostas",
                     "select ip from aceites_termos", "select agente from aceites_termos"):
        segredos += [v for (v,) in sql(dono, consulta + " where conta_id = :c", c=c) if v]
    assert len(segredos) >= 10
    for v in segredos:
        assert v not in tudo, v[:12]
    config = {(x["Seção"], x["Item"]): x["Valor"]
              for x in _linhas(_abrir(r.content)[1]["configuracoes.csv"])}
    assert config[("Chave de integração", "Começo da chave")].startswith("tq_live_")
    assert config[("WhatsApp", "Ativo")] == "Sim"
    assert ("Webhooks", "Webhook 1: endereço") in config


def test_so_a_propria_conta(client, conta):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    criar_contato(client, b["h"], nome="Bruno Beta", email="bruno@beta.com.br")
    _, planilhas = _abrir(_baixar(client, b["h"]).content)
    assert [x["Nome"] for x in _linhas(planilhas["contatos.csv"])] == ["Bruno Beta"]
    assert _linhas(planilhas["respostas.csv"]) == [] and _linhas(planilhas["empresas.csv"]) == []
    assert {x["E-mail"] for x in _linhas(planilhas["equipe.csv"])} == {"bia@beta.com.br"}


def test_encerrada_exporta_e_gestor_nao(client, dono, conta):
    g = membro(client, conta["h"], "gil@alfa.com.br", perfil="gestor")
    assert _baixar(client, g["h"]).status_code == 403
    sql(dono, "update contas set situacao = 'teste_expirado', teste_ate = now() - interval '200 days' "
              "where id = :c", c=conta["c"])
    assert _baixar(client, conta["h"]).status_code == 200


def test_auditoria_da_exportacao(client, dono, conta):
    r = _baixar(client, conta["h"])
    _, planilhas = _abrir(r.content)
    ((detalhe, usuario_id, gravidade),) = sql(
        dono, "select detalhe, usuario_id, gravidade from auditoria where conta_id = :c and evento = 'exportacao_conta'",
        c=conta["c"])
    assert gravidade == "info" and usuario_id == conta["a"]["usuario"]["id"]
    assert detalhe["arquivos"] == len(ARQUIVOS) and detalhe["bytes"] == len(r.content)
    assert detalhe["linhas"] == {nome: len(p) - 1 for nome, p in planilhas.items()}


def test_uma_por_vez_409(client, dono, conta):
    with dono.connect() as conexao:
        conexao.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                        {"k": f"exportacao:{conta['c']}"})
        r = _baixar(client, conta["h"])
        conexao.rollback()
    assert r.status_code == 409
    assert r.json()["erro"] == {"codigo": "exportacao_em_andamento", "campos": {},
                                "mensagem": "Já tem uma exportação sendo gerada nesta conta. Aguarde terminar."}
    assert sql(dono, "select count(*) from auditoria where evento = 'exportacao_conta'")[0][0] == 0


def test_limite_5_por_hora(client, conta):
    from toqqi.core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codigos = [_baixar(client, conta["h"]).status_code for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codigos == [200] * 5 + [429]


def test_arquivo_temporario_apagado(client, conta, monkeypatch):
    caminhos = []
    original = exportacao.gerar

    def gerar(ctx):
        caminho, nome, resumo = original(ctx)
        caminhos.append(caminho)
        return caminho, nome, resumo

    monkeypatch.setattr(exportacao, "gerar", gerar)
    assert _baixar(client, conta["h"]).status_code == 200
    import os
    assert caminhos and not os.path.exists(caminhos[0])


def test_desempenho_5000_contatos_50000_respostas(client, dono):
    a = conta_pronta(client, "ana@grande.com.br", empresa="Grande")
    c = a["conta"]["id"]
    definir_plano(dono, c, "empresa")
    encher_contatos(dono, c, 5000)
    form = form_padrao(client, a["h"])
    p1, p2 = form["perguntas"][0]["id"], form["perguntas"][1]["id"]
    sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, canal, nota, tipo_nota, grupo, comentario,
                               comentario_cliente, respostas, origem)
        select :c, :f, ids.a[1 + g % 5000], 'email', g % 11, 'nps',
               case when g % 11 <= 6 then 'detrator' when g % 11 <= 8 then 'neutro' else 'promotor' end,
               'Comentário ' || g, 'Comentário ' || g,
               jsonb_build_object(cast(:p1 as text), g % 11, cast(:p2 as text), 'Comentário ' || g), 'pesquisa'
          from generate_series(1, 50000) g,
               (select array_agg(id order by id) a from contatos where conta_id = :c) ids
    """, c=c, f=form["id"], p1=p1, p2=p2)
    tracemalloc.start()
    inicio = time.monotonic()
    try:
        r = _baixar(client, a["h"])
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    duracao = time.monotonic() - inicio
    assert r.status_code == 200, r.text
    assert duracao < 30, duracao
    assert pico < 64 * 1024 * 1024, pico
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    with zf.open("respostas.csv") as f:
        assert sum(1 for _ in f) == 50001
    with zf.open("respostas-perguntas.csv") as f:
        assert sum(1 for _ in f) == 100001
    with zf.open("contatos.csv") as f:
        assert sum(1 for _ in f) == 5001


# ---- "Exportar CSV" em Contatos e Empresas --------------------------------------------------------------

def _csv(client, h, lista: str, **filtros):
    r = client.get(f"{API}/{lista}.csv", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    texto = r.content.decode("utf-8")
    assert texto.startswith("﻿")
    return r, list(csv.reader(io.StringIO(texto[1:], newline=""), delimiter=";"))


def test_contatos_csv_igual_a_lista(client, dono, conta):
    h = conta["h"]
    criar_contato(client, h, nome="Zé Inativo", email="ze@x.com.br", ativo=False)
    for filtros in ({}, {"ativo": "true"}, {"busca": "carla"}, {"empresa_id": conta["e1"]["id"]}):
        lista = client.get(f"{API}/contatos", headers=h, params={**filtros, "por_pagina": 200}).json()["itens"]
        r, linhas = _csv(client, h, "contatos", **filtros)
        assert linhas[0] == ["Código", "Nome", "E-mail", "Telefone", "Empresa", "Cargo", "Perfil", "Código externo",
                             "Recebe pesquisas", "Ativo", "Situação", "Último envio", "Próximo envio", "Última nota",
                             "Criado em"]
        assert [x[0] for x in linhas[1:]] == [x["codigo"] for x in lista], filtros
    hoje = sql(dono, "select (now() at time zone 'America/Sao_Paulo')::date")[0][0]
    assert r.headers["content-disposition"] == f'attachment; filename="contatos-{hoje}.csv"'
    _, linhas = _csv(client, h, "contatos", busca="carla")
    carla = dict(zip(linhas[0], linhas[1]))
    assert carla["Nome"] == "'=Carla Um" and carla["Situação"] in ("Respondeu", "Na fila", "Aguardando resposta")
    aud = sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'exportacao_csv' order by id",
              c=conta["c"])
    assert aud[-1] == ({"lista": "contatos", "linhas": 1},)


def test_empresas_csv_igual_a_lista(client, dono, conta):
    h = conta["h"]
    criar_empresa(client, h, "Bazar Dois", ativa=False)
    for filtros in ({}, {"ativa": "true"}, {"busca": "bazar"}):
        lista = client.get(f"{API}/empresas", headers=h, params={**filtros, "por_pagina": 200}).json()["itens"]
        _, linhas = _csv(client, h, "empresas", **filtros)
        assert linhas[0] == ["Nome", "CPF/CNPJ", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde",
                             "Código externo", "Ativa", "Contatos", "Criada em", "Renovação", "Situação", "Saúde",
                             "Nota da saúde"]
        assert [x[0] for x in linhas[1:]] == [x["nome"] for x in lista], filtros
    _, linhas = _csv(client, h, "empresas", busca="mercado")
    linha = dict(zip(linhas[0], linhas[1]))
    assert linha["Contatos"] == "1" and linha["Situação"] == "Ativa" and linha["Saúde"] in ("Risco", "Atenção", "Saudável", "Sem dados") and linha["Nota da saúde"] != ""
    assert sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'exportacao_csv' "
                     "order by id desc limit 1", c=conta["c"]) == [({"lista": "empresas", "linhas": 1},)]


def test_csv_das_listas_exige_permissao(client, dono, conta):
    consulta = membro(client, conta["h"], "caio@alfa.com.br", perfil="consulta")  # sem painel.exportar
    assert client.get(f"{API}/contatos.csv", headers=consulta["h"]).status_code == 403
    assert client.get(f"{API}/empresas.csv", headers=consulta["h"]).status_code == 403
