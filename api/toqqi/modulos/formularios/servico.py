"""Formulários: CRUD, padrões de NPS/CSAT, modelos, resultados e respostas."""
import copy
import csv
import io
import json
import re
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.filtros import FUSO, limites, periodo
from toqqi.core.paginacao import Pagina
from toqqi.core.texto import sem_acento
from toqqi.modelos import ConfigEnvios, Conta, Contato, Empresa, Formulario, Resposta
from toqqi.modulos.formularios.modelos import MODELOS, TEMA_PADRAO, perguntas_do_modelo, tema_do_modelo
from toqqi.modulos.formularios.semear import codigo_publico_livre
from toqqi.modulos.formularios.validacao import (
    TIPOS_NOTA,
    normalizar_perguntas,
    normalizar_tema,
    tipo_principal,
)
from toqqi.modulos.imagens import servico as imagens
from toqqi.modulos.respostas.convites import CHAVES_CONTEXTO
from toqqi.modulos.respostas.registro import formatar_valor, renderizar, variaveis

ROTULO_USO = {"nps": "NPS", "csat": "CSAT"}
ROTULOS_CONTEXTO = {"pedido": "Pedido", "nota_fiscal": "Nota fiscal", "rota": "Rota", "motorista": "Motorista",
                    "filial": "Filial", "transportadora": "Transportadora"}
MAX_TEXTOS = 50


def erro_padrao(msg: str) -> AppError:
    return AppError(409, "formulario_padrao", msg)


def _qtd_respostas():
    return (select(Resposta.formulario_id, func.count().label("n")).where(Resposta.arquivada.is_(False))
            .group_by(Resposta.formulario_id).subquery())


def _json(f: Formulario, respostas: int, completo: bool = True) -> dict:
    d = {
        "id": f.id, "nome": f.nome, "descricao": f.descricao, "tipo_principal": tipo_principal(f.perguntas),
        "tema": f.tema, "ativo": f.ativo, "publico": f.publico, "codigo_publico": f.codigo_publico,
        "padrao_nps": f.padrao_nps, "padrao_csat": f.padrao_csat, "respostas": respostas,
        "perguntas_total": sum(1 for p in f.perguntas if p["tipo"] != "quebra_pagina"),
        "atualizado_em": f.atualizado_em,
    }
    if completo:
        d["perguntas"] = f.perguntas
    return d


def _contar(s: Session, formulario_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Resposta)
                    .where(Resposta.formulario_id == formulario_id, Resposta.arquivada.is_(False)))


def _form_ou_404(s: Session, formulario_id: int, travar: bool = False) -> Formulario:
    f = s.get(Formulario, formulario_id, with_for_update=travar)
    if f is None or f.arquivado:
        raise nao_encontrado("Formulário não encontrado.")
    return f


def listar(ctx: Contexto) -> list[dict]:
    qtd = _qtd_respostas()
    with em_conta(ctx.conta_id) as s:
        linhas = s.execute(
            select(Formulario, func.coalesce(qtd.c.n, 0))
            .outerjoin(qtd, qtd.c.formulario_id == Formulario.id)
            .where(Formulario.arquivado.is_(False))
            .order_by(Formulario.padrao_nps.desc(), Formulario.padrao_csat.desc(), func.lower(Formulario.nome),
                      Formulario.id)
        ).all()
    return [_json(f, n, completo=False) for f, n in linhas]


def _cor_da_marca(s: Session) -> str | None:
    """Etapa 5h: a cor da marca da conta (`config_envios.email_cor`), em minúsculas como no tema, ou None."""
    cor = s.scalar(select(ConfigEnvios.email_cor))
    return cor.lower() if cor else None


def _com_a_marca(tema: dict, cor: str | None) -> dict:
    """Formulário novo nasce com a cor da marca: troca a cor dos modelos (`TEMA_PADRAO`) pela da conta, se houver."""
    if cor and str(tema.get("cor") or "").lower() == TEMA_PADRAO["cor"].lower():
        return {**tema, "cor": cor}
    return tema


def modelos(ctx: Contexto) -> list[dict]:
    """Os modelos, com a cor da marca da conta no tema (a prévia mostra a cor que o formulário vai ter)."""
    with em_conta(ctx.conta_id) as s:
        cor = _cor_da_marca(s)
    return [
        {"chave": chave, "nome": m["nome"], "descricao": m["descricao"],
         "perguntas": normalizar_perguntas(perguntas_do_modelo(chave)), "tema": _com_a_marca(tema_do_modelo(chave), cor)}
        for chave, m in MODELOS.items()
    ]


def _inserir(s: Session, f: Formulario) -> None:
    for tentativa in range(5):
        f.codigo_publico = codigo_publico_livre(s)
        try:
            with s.begin_nested():
                s.add(f)
                s.flush()
            return
        except IntegrityError:
            if tentativa == 4:
                raise


def criar(ctx: Contexto, dados) -> dict:
    chave = dados.modelo
    if dados.perguntas is not None:
        perguntas = normalizar_perguntas(dados.perguntas)
    elif chave:
        perguntas = normalizar_perguntas(perguntas_do_modelo(chave))
    else:
        perguntas = []
    base_tema = tema_do_modelo(chave) if chave else None
    tema = normalizar_tema(dados.tema, base_tema)
    descricao = dados.descricao if dados.descricao is not None else (MODELOS[chave]["descricao"] if chave else "")
    with em_conta(ctx.conta_id) as s:
        if "cor" not in (dados.tema or {}):  # etapa 5h: sem cor pedida, nasce com a cor da marca (se houver)
            tema = _com_a_marca(tema, _cor_da_marca(s))
        f = Formulario(conta_id=ctx.conta_id, nome=dados.nome, descricao=descricao, perguntas=perguntas, tema=tema)
        _inserir(s, f)
        return _json(f, 0)


def obter(ctx: Contexto, formulario_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id)
        return _json(f, _contar(s, f.id))


def _uso_padrao(f: Formulario) -> str | None:
    return "nps" if f.padrao_nps else "csat" if f.padrao_csat else None


def alterar(ctx: Contexto, formulario_id: int, dados) -> dict:
    campos = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        uso = _uso_padrao(f)
        if "perguntas" in campos and dados.perguntas is not None:
            perguntas = normalizar_perguntas(dados.perguntas)
            if uso and tipo_principal(perguntas) != uso:
                raise erro_padrao(f"Este é o formulário padrão de {ROTULO_USO[uso]}: a nota principal "
                                  f"precisa continuar sendo {ROTULO_USO[uso]}.")
            f.perguntas = perguntas
        if "tema" in campos and dados.tema is not None:
            f.tema = normalizar_tema(dados.tema, f.tema)
        if "ativo" in campos and dados.ativo is not None:
            if uso and not dados.ativo:
                raise erro_padrao(f"Este é o formulário padrão de {ROTULO_USO[uso]} e não pode ser desativado. "
                                  "Escolha outro formulário como padrão antes.")
            f.ativo = dados.ativo
        for campo in ("nome", "descricao", "publico"):
            if campo in campos and getattr(dados, campo) is not None:
                setattr(f, campo, getattr(dados, campo))
        f.atualizado_em = func.now()
        s.flush()
        s.refresh(f)
        return _json(f, _contar(s, f.id))


def duplicar(ctx: Contexto, formulario_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        o = _form_ou_404(s, formulario_id)
        f = Formulario(conta_id=ctx.conta_id, nome=f"Cópia de {o.nome}"[:120], descricao=o.descricao,
                       perguntas=copy.deepcopy(o.perguntas), tema=copy.deepcopy(o.tema), ativo=True, publico=o.publico)
        _inserir(s, f)
        # logo enviado à plataforma: a cópia ganha a própria imagem (trocar o logo de um não mexe no outro)
        logo = imagens.copiar_para_formulario(s, (o.tema or {}).get("logo_url"), ctx.conta_id, f.id)
        if logo:
            f.tema = {**f.tema, "logo_url": logo}
            s.flush()
        return _json(f, 0)


def excluir(ctx: Contexto, formulario_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        uso = _uso_padrao(f)
        if uso:
            raise erro_padrao(f"Este é o formulário padrão de {ROTULO_USO[uso]} e não pode ser excluído. "
                              "Escolha outro formulário como padrão antes.")
        tem_respostas = s.scalar(select(func.count()).select_from(Resposta).where(Resposta.formulario_id == f.id))
        detalhe = {"formulario": {"id": f.id, "nome": f.nome}, "respostas": tem_respostas}
        if tem_respostas:
            f.arquivado = True
            f.ativo = False
            registrar(s, "formulario_arquivado", "atencao", detalhe, usuario_id=ctx.usuario_id)
        else:
            registrar(s, "formulario_excluido", "atencao", detalhe, usuario_id=ctx.usuario_id)
            s.delete(f)


def definir_padrao(ctx: Contexto, formulario_id: int, uso: str) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        if tipo_principal(f.perguntas) != uso:
            raise erro_padrao(f"Para ser o padrão de {ROTULO_USO[uso]}, a nota principal do formulário "
                              f"precisa ser {ROTULO_USO[uso]}.")
        if not f.ativo:
            raise erro_padrao("Ative o formulário antes de torná-lo padrão.")
        coluna = Formulario.padrao_nps if uso == "nps" else Formulario.padrao_csat
        anterior = s.scalar(select(Formulario).where(coluna.is_(True), Formulario.id != f.id).with_for_update())
        if anterior is not None:
            setattr(anterior, coluna.key, False)
            s.flush()
        setattr(f, coluna.key, True)
        s.flush()
        registrar(s, "formulario_padrao", "info",
                  {"uso": uso, "formulario": {"id": f.id, "nome": f.nome},
                   "anterior": {"id": anterior.id, "nome": anterior.nome} if anterior else None},
                  usuario_id=ctx.usuario_id)
        return _json(f, _contar(s, f.id))


def enviar_logo(ctx: Contexto, formulario_id: int, dados: bytes, tipo: str) -> dict:
    """Troca o logo guardado do formulário (chave nova) e devolve a URL pública. O editor põe a URL em
    `tema.logo_url`, que só muda quando o formulário é salvo."""
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)  # uma troca por vez
        return {"logo_url": imagens.gravar(s, "logo_formulario", dados, tipo, ctx.conta_id, f.id)}


def novo_codigo(ctx: Contexto, formulario_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        for tentativa in range(5):
            try:
                with s.begin_nested():
                    f.codigo_publico = codigo_publico_livre(s)
                    s.flush()
                break
            except IntegrityError:
                if tentativa == 4:
                    raise
        return _json(f, _contar(s, f.id))


# ---- resultados -------------------------------------------------------------

def _pct(parte: int, total: int) -> float:
    return float((Decimal(parte) * 100 / Decimal(total)).quantize(Decimal("0.1"), ROUND_HALF_UP)) if total else 0.0


def _filtro_sql(de: str | None, ate: str | None) -> tuple[str, dict]:
    """O mesmo período de `periodo` (pela data da resposta), em SQL puro, para as agregações por pergunta."""
    inicio, fim = limites(de, ate)
    sql, params = "", {}
    if inicio:
        sql += " AND r.data_resposta >= :inicio"
        params["inicio"] = inicio
    if fim:
        sql += " AND r.data_resposta < :fim"
        params["fim"] = fim
    return sql, params


def resultados(ctx: Contexto, formulario_id: int, de: str | None, ate: str | None) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id)
        filtros = [Resposta.formulario_id == f.id, Resposta.arquivada.is_(False),
                   *periodo(Resposta.data_resposta, de, ate)]
        total = s.scalar(select(func.count()).select_from(Resposta).where(*filtros))
        saida: dict = {"total": total}
        tp = tipo_principal(f.perguntas)
        if tp == "nps":
            p, n, d = s.execute(select(
                func.count().filter(Resposta.grupo == "promotor"),
                func.count().filter(Resposta.grupo == "neutro"),
                func.count().filter(Resposta.grupo == "detrator"),
            ).where(*filtros, Resposta.tipo_nota == "nps")).one()
            qtd = p + n + d
            valor = int((Decimal(p - d) * 100 / qtd).quantize(Decimal("1"), ROUND_HALF_UP)) if qtd else None
            saida["nps"] = {"valor": valor, "promotores": p, "neutros": n, "detratores": d}
        elif tp == "csat":
            sat, qtd, media = s.execute(select(
                func.count().filter(Resposta.grupo == "satisfeito"), func.count(Resposta.nota), func.avg(Resposta.nota),
            ).where(*filtros, Resposta.tipo_nota == "csat")).one()
            saida["csat"] = {"percentual": _pct(sat, qtd) if qtd else None,
                             "media": float(Decimal(media).quantize(Decimal("0.01"), ROUND_HALF_UP)) if qtd else None}

        cond, params = _filtro_sql(de, ate)
        params["fid"] = f.id
        origem = "FROM respostas r CROSS JOIN LATERAL jsonb_each(r.respostas) kv"
        onde = f"WHERE r.formulario_id = :fid AND NOT r.arquivada{cond}"
        por_pergunta = dict(s.execute(text(f"SELECT kv.key, count(*) {origem} {onde} GROUP BY kv.key"),
                                      params).all())
        ids_contagem = [p["id"] for p in f.perguntas
                        if p["tipo"] in (*TIPOS_NOTA, "escolha_unica", "escolha_multipla", "sim_nao")]
        valores: dict[str, dict] = {}
        # Cada valor (ou cada opção marcada, na escolha múltipla) contado por pergunta.
        for chave, valor, qtd in s.execute(text(f"""
            SELECT kv.key, e.value::text, count(*) {origem}
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(kv.value) = 'array' THEN kv.value ELSE jsonb_build_array(kv.value) END
            ) e
            {onde} AND kv.key = ANY(:ids)
            GROUP BY 1, 2
        """), {**params, "ids": ids_contagem}):
            valores.setdefault(chave, {})[json.loads(valor)] = qtd
        textos: dict[str, list] = {}
        ids_texto = [p["id"] for p in f.perguntas if p["tipo"] in ("texto_curto", "comentario", "data")]
        if ids_texto:
            for chave, texto_, data in s.execute(text(f"""
                SELECT key, texto, data FROM (
                    SELECT kv.key, kv.value #>> '{{}}' AS texto, r.data_resposta AS data,
                           row_number() OVER (PARTITION BY kv.key ORDER BY r.data_resposta DESC, r.id DESC) AS n
                    {origem} {onde} AND kv.key = ANY(:ids)
                ) x WHERE n <= {MAX_TEXTOS} ORDER BY key, data DESC
            """), {**params, "ids": ids_texto}):
                textos.setdefault(chave, []).append({"texto": texto_, "data": data})

    perguntas = []
    for p in f.perguntas:
        if p["tipo"] == "quebra_pagina":
            continue
        item = {"id": p["id"], "tipo": p["tipo"], "titulo": p["titulo"], "respostas": por_pergunta.get(p["id"], 0)}
        v = valores.get(p["id"], {})
        if p["tipo"] in TIPOS_NOTA:
            mn, mx = (0, 10) if p["tipo"] == "nps" else (1, 5) if p["tipo"] in ("csat", "estrelas") \
                else (p["min"], p["max"])
            item["distribuicao"] = {str(n): v.get(n, 0) for n in range(mn, mx + 1)}
            qtd = sum(item["distribuicao"].values())
            soma = sum(int(k) * q for k, q in item["distribuicao"].items())
            item["media"] = float((Decimal(soma) / qtd).quantize(Decimal("0.01"), ROUND_HALF_UP)) if qtd else None
        elif p["tipo"] in ("escolha_unica", "escolha_multipla"):
            item["opcoes"] = {o: v.get(o, 0) for o in p.get("opcoes", [])}
        elif p["tipo"] == "sim_nao":
            item["opcoes"] = {"Sim": v.get(True, 0), "Não": v.get(False, 0)}
        else:
            item["textos"] = textos.get(p["id"], [])
        perguntas.append(item)
    saida["perguntas"] = perguntas
    return saida


# ---- respostas --------------------------------------------------------------

def _consulta_respostas(filtros):
    return (
        select(Resposta, Formulario.nome, Contato.nome, Contato.email, Empresa.nome)
        .join(Formulario, Formulario.id == Resposta.formulario_id)
        .outerjoin(Contato, Contato.id == Resposta.contato_id)
        .outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
        .where(*filtros)
        .order_by(Resposta.data_resposta.desc(), Resposta.id.desc())
    )


def resposta_json(linha) -> dict:
    r, form_nome, contato_nome, contato_email, empresa_nome = linha
    return {
        "id": r.id, "formulario": {"id": r.formulario_id, "nome": form_nome},
        "contato": {"id": r.contato_id, "nome": contato_nome, "email": contato_email} if r.contato_id else None,
        "empresa": {"id": r.empresa_id, "nome": empresa_nome} if r.empresa_id else None,
        "canal": r.canal, "nota": r.nota, "tipo_nota": r.tipo_nota, "grupo": r.grupo, "comentario": r.comentario,
        "respostas": r.respostas, "contexto": r.contexto, "referencia": r.referencia, "criada_em": r.criada_em,
        "data": r.data_resposta, "origem": r.origem,
    }


def listar_respostas(ctx: Contexto, formulario_id: int, de: str | None, ate: str | None, pg: Pagina) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id)
        filtros = [Resposta.formulario_id == f.id, Resposta.arquivada.is_(False),
                   *periodo(Resposta.data_resposta, de, ate)]
        total = s.scalar(select(func.count()).select_from(Resposta).where(*filtros))
        linhas = s.execute(_consulta_respostas(filtros).limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([resposta_json(x) for x in linhas], total)


def _celula(v) -> str:
    t = "" if v is None else str(v)
    if t[:1] in ("=", "+", "-", "@", "\t", "\r"):  # evita fórmula ao abrir no Excel
        t = "'" + t
    return t


def respostas_csv(ctx: Contexto, formulario_id: int, de: str | None, ate: str | None) -> tuple[str, str]:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id)
        empresa = s.scalar(select(Conta.nome).where(Conta.id == ctx.conta_id))
        filtros = [Resposta.formulario_id == f.id, Resposta.arquivada.is_(False),
                   *periodo(Resposta.data_resposta, de, ate)]
        linhas = s.execute(_consulta_respostas(filtros)).all()
    perguntas = [p for p in f.perguntas if p["tipo"] != "quebra_pagina"]
    v = variaveis(empresa)
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["Data", "Contato", "E-mail", "Empresa", "Canal", "Referência",
                *[ROTULOS_CONTEXTO[k] for k in CHAVES_CONTEXTO],
                *[renderizar(p["titulo"], v) or p["id"] for p in perguntas]])
    for r, _, contato_nome, contato_email, empresa_nome in linhas:
        w.writerow([
            r.data_resposta.astimezone(FUSO).strftime("%d/%m/%Y %H:%M"),
            _celula(contato_nome), _celula(contato_email), _celula(empresa_nome), r.canal, _celula(r.referencia),
            *[_celula(r.contexto.get(k)) for k in CHAVES_CONTEXTO],
            *[_celula(formatar_valor(r.respostas[p["id"]])) if p["id"] in r.respostas else "" for p in perguntas],
        ])
    nome = re.sub(r"[^a-z0-9]+", "-", sem_acento(f.nome.lower())).strip("-") or "formulario"
    return buf.getvalue(), f"respostas-{nome}.csv"
