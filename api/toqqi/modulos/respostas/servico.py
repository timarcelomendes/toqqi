"""Respostas (tela Respostas): lista com filtros e métricas, detalhe, registro à mão, análise, arquivar/restaurar,
exclusão definitiva e CSV. A data de toda regra de período é `data_resposta` (informada, senão a de entrada)."""
import csv
import io
from datetime import date, datetime, time

from sqlalchemy import String, case, cast, delete, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.filtros import FUSO, entre_datas
from toqqi.core.paginacao import Pagina
from toqqi.modelos import (
    Acao,
    Conta,
    Contato,
    Convite,
    Empresa,
    Formulario,
    Grupo,
    PerfilContato,
    Resposta,
    Usuario,
)
from toqqi.modulos.acoes.regras import prazo_selo
from toqqi.modulos.empresas.servico import ref
from toqqi.modulos.formularios.servico import ROTULOS_CONTEXTO, _celula
from toqqi.modulos.formularios.logica import respondivel, sem_citacoes
from toqqi.modulos.formularios.validacao import grupo_da_nota, pergunta_principal
from toqqi.modulos.ia.regras import ORIGENS as ORIGENS_IA
from toqqi.modulos.ia.regras import ia_ativa, texto_qualifica
from toqqi.modulos.ia.servico import limpar_analise, marcar_pendente, temas_automaticos
from toqqi.modulos.respostas import temas as temas_mod
from toqqi.modulos.respostas.convites import CHAVES_CONTEXTO
from toqqi.modulos.respostas.indicadores import ROTULOS_GRUPO, ROTULOS_TIPO, bloco_nps, media, percentual
from toqqi.modulos.respostas.registro import (
    atualizar_ultima_nota,
    formatar_valor,
    gravar_resposta,
    renderizar,
    variaveis,
)

DATA_MINIMA = date(2000, 1, 1)
HORA_INFORMADA = time(12, 0)  # resposta com data informada (à mão, importação) fica às 12:00 de São Paulo
PERGUNTA_REMOVIDA = "Pergunta que não existe mais no formulário"
ROTULOS_CANAL = {"email": "E-mail", "whatsapp": "WhatsApp", "link": "Link", "qr": "QR Code", "widget": "Widget",
                 "api": "API", "importacao": "Importação", "manual": "Manual", "telefone": "Telefone",
                 "reuniao": "Reunião"}
ROTULOS_ORIGEM = {"pesquisa": "Pesquisa", "manual": "Registrada à mão", "importacao": "Importação"}
CABECALHO_CSV = ["Data", "Contato", "E-mail", "Empresa", "Grupo de empresas", "Perfil", "Tipo", "Nota", "Categoria",
                 "Temas", "Comentário", "O que faltou", "O que combinamos", "Canal", "Origem", "Referência",
                 *[ROTULOS_CONTEXTO[k] for k in CHAVES_CONTEXTO], "Arquivada", "Sentimento", "Resumo da IA"]
ROTULOS_SENTIMENTO = {"positivo": "Positivo", "neutro": "Neutro", "negativo": "Negativo", "misto": "Misto"}
CONTEXTOS_FILTRO = ("motorista", "rota", "filial", "transportadora")


def data_informada(d: date) -> datetime:
    return datetime.combine(d, HORA_INFORMADA, tzinfo=FUSO)


# ---- consulta e formato -----------------------------------------------------

def _juntar_cadastros(consulta):
    """Contato (e perfil) e empresa (e grupo de empresas) da resposta."""
    return (consulta
            .outerjoin(Contato, Contato.id == Resposta.contato_id)
            .outerjoin(PerfilContato, PerfilContato.id == Contato.perfil_id)
            .outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
            .outerjoin(Grupo, Grupo.id == Empresa.grupo_id))


def _consulta():
    analista, registrou = aliased(Usuario, name="analista"), aliased(Usuario, name="registrou")
    # a ação automática da resposta; senão a mais recente ligada a ela
    acao = (select(Acao.id, Acao.situacao, Acao.prazo)
            .where(Acao.conta_id == Resposta.conta_id, Acao.resposta_id == Resposta.id)
            .order_by(case((Acao.origem == "automatica", 0), else_=1), Acao.criada_em.desc(), Acao.id.desc())
            .limit(1).correlate(Resposta).lateral("acao"))
    consulta = select(
        Resposta, Formulario.nome.label("formulario_nome"),
        Contato.nome.label("contato_nome"), Contato.email.label("contato_email"), Contato.perfil_id,
        PerfilContato.nome.label("perfil_nome"), Empresa.nome.label("empresa_nome"), Empresa.grupo_id,
        Grupo.nome.label("grupo_nome"), analista.nome.label("analista_nome"), registrou.nome.label("registrou_nome"),
        acao.c.id.label("acao_id"), acao.c.situacao.label("acao_situacao"), acao.c.prazo.label("acao_prazo"),
    ).select_from(Resposta).join(Formulario, Formulario.id == Resposta.formulario_id)
    return (_juntar_cadastros(consulta)
            .outerjoin(analista, analista.id == Resposta.analisada_por)
            .outerjoin(registrou, registrou.id == Resposta.registrada_por)
            .outerjoin(acao, true()))


def resposta_json(x, hoje: date) -> dict:
    r: Resposta = x.Resposta
    return {
        "id": r.id, "formulario": {"id": r.formulario_id, "nome": x.formulario_nome},
        "contato": ({"id": r.contato_id, "nome": x.contato_nome, "email": x.contato_email,
                     "perfil": ref(x.perfil_id, x.perfil_nome)} if r.contato_id else None),
        "empresa": ({"id": r.empresa_id, "nome": x.empresa_nome, "grupo": ref(x.grupo_id, x.grupo_nome)}
                    if r.empresa_id else None),
        "canal": r.canal, "nota": r.nota, "tipo_nota": r.tipo_nota, "grupo": r.grupo, "comentario": r.comentario,
        "respostas": r.respostas, "contexto": r.contexto, "referencia": r.referencia, "criada_em": r.criada_em,
        "data": r.data_resposta, "respondida_em": r.respondida_em, "origem": r.origem, "temas": list(r.temas or []),
        "temas_manuais": r.temas_manuais, "o_que_faltou": r.o_que_faltou, "o_que_combinamos": r.o_que_combinamos,
        "analisada_em": r.analisada_em, "analisada_por": ref(r.analisada_por, x.analista_nome),
        "registrada_por": ref(r.registrada_por, x.registrou_nome), "arquivada": r.arquivada,
        "arquivada_em": r.arquivada_em, "editada_em": r.editada_em, "edicoes": r.edicoes,
        "acao": ({"id": x.acao_id, "situacao": x.acao_situacao, "prazo": x.acao_prazo,
                  "prazo_selo": prazo_selo(x.acao_situacao, x.acao_prazo, hoje)} if x.acao_id else None),
        "ia": ia_json(r),
    }


def ia_json(r: Resposta) -> dict | None:
    """Análise da IA (null quando a resposta não passa pela IA)."""
    if r.ia_situacao is None:
        return None
    return {"situacao": r.ia_situacao, "sentimento": r.ia_sentimento, "resumo": r.ia_resumo,
            "temas": r.ia_temas, "em": r.ia_em}


def valor_contexto(chave: str):
    """Valor do contexto do pedido para agrupar e filtrar: sem diferenciar maiúsculas nem espaços nas pontas."""
    return func.lower(func.btrim(Resposta.contexto[chave].astext))


def _linha(s: Session, resposta_id: int):
    # populate_existing: relê do banco o que acabou de mudar (datas no mesmo formato das listas)
    x = s.execute(_consulta().where(Resposta.id == resposta_id)
                  .execution_options(populate_existing=True)).one_or_none()
    if x is None:
        raise nao_encontrado("Resposta não encontrada.")
    return x


def _uma(s: Session, resposta_id: int) -> dict:
    return resposta_json(_linha(s, resposta_id), relogio.hoje())


def _resposta(s: Session, resposta_id: int, travar: bool = False) -> Resposta:
    r = s.get(Resposta, resposta_id, with_for_update=travar)
    if r is None:
        raise nao_encontrado("Resposta não encontrada.")
    return r


# ---- filtros e métricas -----------------------------------------------------

def condicoes(f) -> list:
    """Condições da lista (e do CSV) a partir de FiltrosRespostas. Pedem a junção de contato e empresa."""
    conds = []
    if f.busca and f.busca.strip():
        termo = f"%{f.busca.strip()}%"
        conds.append(or_(Contato.nome.ilike(termo), cast(Contato.email, String).ilike(termo),
                         cast(Empresa.nome, String).ilike(termo), Resposta.comentario.ilike(termo),
                         Resposta.referencia.ilike(termo)))
    for campo, coluna in (("categoria", Resposta.grupo), ("tipo_nota", Resposta.tipo_nota),
                          ("grupo_id", Empresa.grupo_id), ("empresa_id", Resposta.empresa_id),
                          ("contato_id", Resposta.contato_id), ("perfil_id", Contato.perfil_id),
                          ("canal", Resposta.canal), ("origem", Resposta.origem),
                          ("formulario_id", Resposta.formulario_id)):
        valor = getattr(f, campo)
        if valor is not None:
            conds.append(coluna == valor)
    if f.tema:
        conds.append(Resposta.temas.any(f.tema))
    if f.reclamacao:  # com tema: reclamação daquele tema; sem tema: qualquer reclamação
        conds.append(Resposta.temas_reclamacao.any(f.tema) if f.tema
                     else func.cardinality(Resposta.temas_reclamacao) > 0)
    if f.sentimento == "sem_analise":  # respostas com texto do cliente ainda sem análise da IA
        conds += [Resposta.comentario_cliente != "", Resposta.ia_situacao.is_distinct_from("analisada")]
    elif f.sentimento:
        conds += [Resposta.ia_situacao == "analisada", Resposta.ia_sentimento == f.sentimento]
    for chave in CONTEXTOS_FILTRO:
        valor = getattr(f, chave)
        if valor and valor.strip():
            conds.append(valor_contexto(chave) == valor.strip().lower())
    if f.so_ativos:  # como no painel: respostas sem empresa sempre contam
        conds.append(or_(Resposta.empresa_id.is_(None), Empresa.ativa.is_(True)))
    coluna_data = Resposta.criada_em if f.data_por == "entrada" else Resposta.data_resposta
    conds += entre_datas(coluna_data, f.de, f.ate)
    arquivadas = f.arquivadas or "false"
    if arquivadas != "todas":
        conds.append(Resposta.arquivada.is_(arquivadas == "true"))
    return conds


def contagens(s: Session, conds: list):
    """Total, grupos do NPS e CSAT sobre as respostas das condições (todas as páginas)."""
    nps = Resposta.tipo_nota == "nps"
    csat = Resposta.tipo_nota == "csat"
    consulta = select(
        func.count().label("total"),
        func.count().filter(nps, Resposta.grupo == "promotor").label("promotores"),
        func.count().filter(nps, Resposta.grupo == "neutro").label("neutros"),
        func.count().filter(nps, Resposta.grupo == "detrator").label("detratores"),
        func.count().filter(csat).label("csat_total"),
        func.count().filter(csat, Resposta.grupo == "satisfeito").label("satisfeitos"),
        func.coalesce(func.sum(Resposta.nota).filter(csat), 0).label("csat_soma"),
    ).select_from(Resposta)
    return s.execute(_juntar_cadastros(consulta).where(*conds)).one()


def bloco_csat(satisfeitos: int, total: int, soma) -> dict:
    return {"percentual": percentual(satisfeitos, total), "media": media(soma, total), "total": total}


def metricas_json(c) -> dict:
    return {
        "nps": bloco_nps(c.promotores, c.neutros, c.detratores) if c.promotores + c.neutros + c.detratores else None,
        "csat": bloco_csat(c.satisfeitos, c.csat_total, c.csat_soma) if c.csat_total else None,
        "total": c.total,
    }


# ---- leitura ----------------------------------------------------------------

def listar(ctx: Contexto, f, pg: Pagina) -> dict:
    conds = [Resposta.conta_id == ctx.conta_id, *condicoes(f)]  # conta explícita: deixa o banco usar os índices
    ordem = (Resposta.data_resposta.desc(), Resposta.id.desc())
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        c = contagens(s, conds)
        # primeiro os ids da página; os detalhes (e a ação de cada uma) só para eles
        pagina_ids = (_juntar_cadastros(select(Resposta.id).select_from(Resposta)).where(*conds).order_by(*ordem)
                      .limit(pg.por_pagina).offset(pg.offset))
        linhas = s.execute(_consulta().where(Resposta.id.in_(pagina_ids)).order_by(*ordem)).all()
        hoje = relogio.hoje()
        return {**pg.resultado([resposta_json(x, hoje) for x in linhas], c.total), "metricas": metricas_json(c)}


def _perguntas(perguntas: list[dict], respostas: dict, v: dict) -> list[dict]:
    """Todas as perguntas do formulário (sem blocos de conteúdo nem quebras de página) com a resposta em texto pronto
    (None se não respondida; citações `{{ID}}` no título saem como "…"); respostas de perguntas que saíram do
    formulário vêm no fim."""
    saida, ids = [], set()
    for p in perguntas:
        if not respondivel(p.get("tipo")):
            continue
        ids.add(p["id"])
        valor = respostas.get(p["id"])
        saida.append({"id": p["id"], "titulo": sem_citacoes(renderizar(p.get("titulo"), v)), "tipo": p["tipo"],
                      "resposta": None if valor is None else formatar_valor(valor)})
    for pid, valor in respostas.items():
        if pid not in ids:
            saida.append({"id": pid, "titulo": PERGUNTA_REMOVIDA, "tipo": None, "resposta": formatar_valor(valor)})
    return saida


def _detalhe(s: Session, resposta_id: int) -> dict:
    x = _linha(s, resposta_id)
    hoje = relogio.hoje()
    dados = resposta_json(x, hoje)
    r: Resposta = x.Resposta
    f = s.get(Formulario, r.formulario_id)
    convite = s.get(Convite, r.convite_id) if r.convite_id else None
    v = variaveis(s.scalar(select(Conta.nome)) or "", x.contato_nome, convite.assunto if convite else None,
                  r.referencia)
    acoes = s.execute(select(Acao.id, Acao.titulo, Acao.situacao, Acao.prazo)
                      .where(Acao.resposta_id == r.id).order_by(Acao.criada_em, Acao.id)).all()
    dados.update(
        perguntas=_perguntas(f.perguntas if f else [], r.respostas or {}, v),
        convite=({"evento": convite.evento, "referencia": convite.referencia, "assunto": convite.assunto}
                 if convite else None),
        acoes=[{"id": a.id, "titulo": a.titulo, "situacao": a.situacao, "prazo": a.prazo,
                "prazo_selo": prazo_selo(a.situacao, a.prazo, hoje)} for a in acoes],
    )
    return dados


def obter(ctx: Contexto, resposta_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _detalhe(s, resposta_id)


# ---- registro à mão ---------------------------------------------------------

def registrar_manual(ctx: Contexto, dados) -> dict:
    """Resposta registrada por alguém da conta (telefone, reunião...): formulário padrão de NPS, origem manual.
    Passa pelo ponto único (grupo, temas, ação automática, alerta, webhook), sem agradecimento."""
    if dados.data is not None:
        if dados.data > relogio.hoje():
            raise AppError(422, "dados_invalidos", "Confira os campos destacados.",
                           {"data": "A data não pode ser no futuro."})
        if dados.data < DATA_MINIMA:
            raise AppError(422, "dados_invalidos", "Confira os campos destacados.",
                           {"data": "Use uma data a partir de 01/01/2000."})
    with em_conta(ctx.conta_id) as s:
        contato = s.get(Contato, dados.contato_id)
        if contato is None:
            raise AppError(422, "dados_invalidos", "Confira os campos destacados.",
                           {"contato_id": "Contato não encontrado."})
        f = s.scalar(select(Formulario).where(Formulario.padrao_nps.is_(True)))
        principal = pergunta_principal(f.perguntas) if f else None
        if principal is None or principal["tipo"] != "nps":
            raise AppError(409, "sem_formulario_nps",
                           "Escolha um formulário padrão de NPS em Formulários antes de registrar respostas.")
        # data de hoje (a tela sempre manda): vale a hora real de entrada, não 12:00 (que poderia ficar no futuro)
        informada = dados.data if dados.data is not None and dados.data != relogio.hoje() else None
        r = gravar_resposta(
            s, f, None, dados.canal, variaveis(""), contato=contato,
            respostas_validadas=({principal["id"]: dados.nota}, dados.nota, "nps", grupo_da_nota("nps", dados.nota)),
            origem="manual", comentario=dados.comentario or "",
            respondida_em=data_informada(informada) if informada else None, registrada_por=ctx.usuario_id)
        return _uma(s, r.id)


# ---- análise ----------------------------------------------------------------

def _erro(campo: str, msg: str) -> AppError:
    return AppError(422, "dados_invalidos", "Confira os campos destacados.", {campo: msg})


def _comentario_editado(s: Session, conta_id: int, r: Resposta) -> None:
    """Comentário novo: a análise anterior da IA não vale mais. Se a resposta passa pela IA (ou já tinha passado,
    pelo "analisar os últimos 90 dias"), volta para pendente; senão fica sem análise."""
    conta = s.get(Conta, conta_id)
    if ((r.origem in ORIGENS_IA or r.ia_situacao is not None) and texto_qualifica(r.comentario_cliente)
            and ia_ativa(conta)):
        marcar_pendente(s, r)
    elif r.ia_situacao is not None:
        limpar_analise(r, None)


def analisar(ctx: Contexto, resposta_id: int, dados) -> dict:
    campos = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        r = _resposta(s, resposta_id, travar=True)
        f = s.get(Formulario, r.formulario_id)
        perguntas = f.perguntas if f else []
        nota_antes, comentario_antes = r.nota, r.comentario
        if "nota" in campos and dados.nota is not None:
            if r.tipo_nota is None or r.nota is None:
                raise _erro("nota", "Esta resposta não tem nota.")
            minimo, maximo = (0, 10) if r.tipo_nota == "nps" else (1, 5)
            if not minimo <= dados.nota <= maximo:
                raise _erro("nota", f"A nota precisa ser de {minimo} a {maximo}.")
            if dados.nota != r.nota:
                r.nota = dados.nota
                r.grupo = grupo_da_nota(r.tipo_nota, dados.nota)
                principal = pergunta_principal(perguntas)
                if principal is not None and principal["id"] in (r.respostas or {}):
                    r.respostas = {**r.respostas, principal["id"]: dados.nota}  # resultados por pergunta seguem a nota
        if "comentario" in campos and (dados.comentario or "") != r.comentario:
            # editado na análise: o texto como ficou passa a ser o comentário do cliente (painel, palavras, temas)
            r.comentario = dados.comentario or ""
            r.comentario_cliente = r.comentario
            _comentario_editado(s, ctx.conta_id, r)
        for campo in ("o_que_faltou", "o_que_combinamos"):
            if campo in campos:
                setattr(r, campo, getattr(dados, campo))
        if "temas" in campos and dados.temas is not None:
            r.temas = temas_mod.ordenar(dados.temas)
            r.temas_manuais = True
        elif not r.temas_manuais and {"comentario", "o_que_faltou"} & campos:
            r.temas = temas_automaticos(r, perguntas)
        r.analisada_em = relogio.agora()
        r.analisada_por = ctx.usuario_id
        s.flush()
        comentario_alterado = r.comentario != comentario_antes
        if r.nota != nota_antes:
            atualizar_ultima_nota(s, r.contato_id)
        if r.nota != nota_antes or comentario_alterado:
            registrar(s, "resposta_editada", "info",
                      {"resposta_id": r.id, "antes": {"nota": nota_antes}, "depois": {"nota": r.nota},
                       "comentario_alterado": comentario_alterado}, usuario_id=ctx.usuario_id)
        return _detalhe(s, r.id)


def arquivar(ctx: Contexto, resposta_id: int, arquivada: bool) -> dict:
    """Arquivada sai de todos os indicadores (e da última nota do contato); restaurar devolve."""
    with em_conta(ctx.conta_id) as s:
        r = _resposta(s, resposta_id, travar=True)
        if r.arquivada != arquivada:
            r.arquivada = arquivada
            r.arquivada_em = relogio.agora() if arquivada else None
            s.flush()
            atualizar_ultima_nota(s, r.contato_id)
        return _uma(s, r.id)


def excluir(ctx: Contexto, resposta_id: int) -> None:
    """Exclusão definitiva (perfil admin): apaga as ações ligadas e a resposta; recalcula a última nota."""
    with em_conta(ctx.conta_id) as s:
        r = _resposta(s, resposta_id, travar=True)
        contato = s.get(Contato, r.contato_id) if r.contato_id else None
        apagadas = s.execute(delete(Acao).where(Acao.resposta_id == r.id)).rowcount
        registrar(s, "resposta_excluida", "atencao",
                  {"resposta_id": r.id, "contato": {"id": contato.id, "nome": contato.nome} if contato else None,
                   "nota": r.nota, "acoes_apagadas": apagadas}, usuario_id=ctx.usuario_id)
        s.delete(r)
        s.flush()
        if contato is not None:
            atualizar_ultima_nota(s, contato.id)


# ---- CSV ----------------------------------------------------------------------

def consulta_csv(*extras):
    """As colunas de `CABECALHO_CSV` (e as `extras`) das respostas, com os cadastros juntados; sem filtro nem ordem."""
    return _juntar_cadastros(select(
        Resposta.data_resposta, Contato.nome.label("contato"), Contato.email, Empresa.nome.label("empresa"),
        Grupo.nome.label("grupo_empresas"), PerfilContato.nome.label("perfil"), Resposta.tipo_nota, Resposta.nota,
        Resposta.grupo, Resposta.temas, Resposta.comentario, Resposta.o_que_faltou, Resposta.o_que_combinamos,
        Resposta.canal, Resposta.origem, Resposta.referencia, Resposta.contexto, Resposta.arquivada,
        Resposta.ia_situacao, Resposta.ia_sentimento, Resposta.ia_resumo, *extras,
    ).select_from(Resposta))


def linha_csv(x) -> list:
    """Uma linha de `CABECALHO_CSV` (células protegidas contra fórmula) de uma linha de `consulta_csv`."""
    contexto = x.contexto or {}
    return [
        x.data_resposta.astimezone(FUSO).strftime("%d/%m/%Y %H:%M"),
        _celula(x.contato), _celula(x.email), _celula(x.empresa), _celula(x.grupo_empresas), _celula(x.perfil),
        ROTULOS_TIPO.get(x.tipo_nota, ""), "" if x.nota is None else x.nota, ROTULOS_GRUPO.get(x.grupo, ""),
        ", ".join(temas_mod.ROTULOS[t] for t in temas_mod.ordenar(x.temas)),
        _celula(x.comentario), _celula(x.o_que_faltou), _celula(x.o_que_combinamos),
        ROTULOS_CANAL.get(x.canal, x.canal), ROTULOS_ORIGEM.get(x.origem, x.origem), _celula(x.referencia),
        *[_celula(contexto.get(k)) for k in CHAVES_CONTEXTO],
        "Sim" if x.arquivada else "Não",
        ROTULOS_SENTIMENTO.get(x.ia_sentimento, "") if x.ia_situacao == "analisada" else "",
        _celula(x.ia_resumo) if x.ia_situacao == "analisada" else "",
    ]


def gerar_csv(s: Session, conds: list) -> str:
    """CSV `;` (UTF-8 com BOM) das respostas das condições, mais novas primeiro; células protegidas contra fórmula."""
    consulta = consulta_csv().where(*conds).order_by(Resposta.data_resposta.desc(), Resposta.id.desc())
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(CABECALHO_CSV)
    for x in s.execute(consulta.execution_options(yield_per=2000)):
        w.writerow(linha_csv(x))
    return buf.getvalue()


def nome_csv(prefixo: str = "respostas") -> str:
    return f"{prefixo}-{relogio.hoje().isoformat()}.csv"


def exportar_csv(ctx: Contexto, f) -> str:
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        return gerar_csv(s, [Resposta.conta_id == ctx.conta_id, *condicoes(f)])

