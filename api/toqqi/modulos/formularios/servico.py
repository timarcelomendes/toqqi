"""Formulários: CRUD, padrões de NPS/CSAT, modelos, resultados e respostas.

Etapa 5l (docs/api-etapa-5l.md §1.5 e §4.2): rascunho e publicação. O editor grava num rascunho (`PUT …/rascunho`,
com `rev` para não sobrescrever outra aba: rev diferente → 409 `rascunho_desatualizado`) e o que está no ar só muda ao
publicar (`POST …/publicar`: valida estrito, versão +1, auditoria `formulario_publicado`). `PATCH` com perguntas, tema
ou finais continua publicando direto (sem mexer no rascunho). Nome, descrição, ativo, público, padrão e código mudam
na hora, como antes. Ao publicar e ao descartar, saem as imagens do formulário que ninguém mais cita.
"""
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
from toqqi.modelos import ConfigEnvios, Conta, Contato, Empresa, Formulario, Resposta, Usuario
from toqqi.modulos.formularios.logica import respondivel, sem_citacoes
from toqqi.modulos.formularios.modelos import MODELOS, TEMA_PADRAO, documento_do_modelo, tema_do_modelo
from toqqi.modulos.formularios.semear import codigo_publico_livre
from toqqi.modulos.formularios.validacao import (
    TIPOS_NOTA,
    analisar_documento,
    erro_documento,
    normalizar_documento,
    perguntas_respondiveis,
    tipo_principal,
)
from toqqi.modulos.imagens import servico as imagens
from toqqi.modulos.respostas.convites import CHAVES_CONTEXTO
from toqqi.modulos.respostas.registro import formatar_valor, renderizar, variaveis

ROTULO_USO = {"nps": "NPS", "csat": "CSAT"}
ROTULOS_CONTEXTO = {"pedido": "Pedido", "nota_fiscal": "Nota fiscal", "rota": "Rota", "motorista": "Motorista",
                    "filial": "Filial", "transportadora": "Transportadora"}
MAX_TEXTOS = 50
MSG_DESATUALIZADO = "Este formulário foi alterado em outra aba ou por outra pessoa. Recarregue para continuar."
MSG_SEM_RASCUNHO = "Não há alterações para publicar."


def erro_padrao(msg: str) -> AppError:
    return AppError(409, "formulario_padrao", msg)


def _msg_padrao(uso: str) -> str:
    return (f"Este é o formulário padrão de {ROTULO_USO[uso]}: a nota principal precisa continuar sendo "
            f"{ROTULO_USO[uso]}.")


def _qtd_respostas():
    return (select(Resposta.formulario_id, func.count().label("n")).where(Resposta.arquivada.is_(False))
            .group_by(Resposta.formulario_id).subquery())


def _nomes(s: Session, *ids: int | None) -> dict[int, str]:
    ids_validos = {i for i in ids if i}
    if not ids_validos:
        return {}
    return dict(s.execute(select(Usuario.id, Usuario.nome).where(Usuario.id.in_(ids_validos))).all())


def _json(s: Session | None, f: Formulario, respostas: int, completo: bool = True) -> dict:
    """O formulário (lista: resumido; `completo`: com as perguntas, os finais, o rascunho e quem publicou)."""
    d = {
        "id": f.id, "nome": f.nome, "descricao": f.descricao, "tipo_principal": tipo_principal(f.perguntas),
        "tema": f.tema, "ativo": f.ativo, "publico": f.publico, "codigo_publico": f.codigo_publico,
        "permite_editar": f.permite_editar,
        "padrao_nps": f.padrao_nps, "padrao_csat": f.padrao_csat, "respostas": respostas,
        "perguntas_total": len(perguntas_respondiveis(f.perguntas)), "atualizado_em": f.atualizado_em,
        "tem_rascunho": f.rascunho is not None, "versao": f.versao, "publicado_em": f.publicado_em,
    }
    if completo:
        nomes = _nomes(s, f.publicado_por, f.rascunho_por) if s is not None else {}
        rascunho = None
        if f.rascunho is not None:
            rascunho = {"perguntas": f.rascunho.get("perguntas", []), "tema": f.rascunho.get("tema", {}),
                        "finais": f.rascunho.get("finais", []), "salvo_em": f.rascunho_em,
                        "salvo_por_nome": nomes.get(f.rascunho_por)}
        d.update(perguntas=f.perguntas, finais=f.finais or [], publicado_por_nome=nomes.get(f.publicado_por),
                 rascunho=rascunho, rascunho_rev=f.rascunho_rev, prefixo_imagens=imagens.prefixo_publico())
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
        return [_json(s, f, n, completo=False) for f, n in linhas]


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
    """Os modelos (perguntas e finais já normalizados), com a cor da marca da conta no tema (a prévia mostra a cor que
    o formulário vai ter)."""
    with em_conta(ctx.conta_id) as s:
        cor = _cor_da_marca(s)
    saida = []
    for chave, m in MODELOS.items():
        perguntas, finais = documento_do_modelo(chave)
        doc, _ = normalizar_documento(perguntas, None, finais, estrito=True, base_tema=tema_do_modelo(chave))
        saida.append({"chave": chave, "nome": m["nome"], "descricao": m["descricao"], "perguntas": doc["perguntas"],
                      "finais": doc["finais"], "tema": _com_a_marca(doc["tema"], cor)})
    return saida


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
    """Cria já publicado (versão 1). Com `modelo` e sem perguntas, vêm as perguntas e os finais do modelo."""
    chave = dados.modelo
    if dados.perguntas is not None:
        perguntas, finais = dados.perguntas, dados.finais or []
    elif chave:
        perguntas, finais_do_modelo = documento_do_modelo(chave)
        finais = dados.finais if dados.finais is not None else finais_do_modelo
    else:
        perguntas, finais = [], dados.finais or []
    base_tema = tema_do_modelo(chave) if chave else None
    doc, _ = normalizar_documento(perguntas, dados.tema, finais, estrito=True, base_tema=base_tema)
    descricao = dados.descricao if dados.descricao is not None else (MODELOS[chave]["descricao"] if chave else "")
    with em_conta(ctx.conta_id) as s:
        tema = doc["tema"]
        if "cor" not in (dados.tema or {}):  # etapa 5h: sem cor pedida, nasce com a cor da marca (se houver)
            tema = _com_a_marca(tema, _cor_da_marca(s))
        f = Formulario(conta_id=ctx.conta_id, nome=dados.nome, descricao=descricao, perguntas=doc["perguntas"],
                       tema=tema, finais=doc["finais"], publicado_por=ctx.usuario_id)
        _inserir(s, f)
        s.refresh(f)
        return _json(s, f, 0)


def obter(ctx: Contexto, formulario_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id)
        return _json(s, f, _contar(s, f.id))


def _uso_padrao(f: Formulario) -> str | None:
    return "nps" if f.padrao_nps else "csat" if f.padrao_csat else None


def _conferir_padrao(f: Formulario, perguntas: list[dict]) -> None:
    """Formulário padrão não muda o tipo da nota principal (409 `formulario_padrao`)."""
    uso = _uso_padrao(f)
    if uso and tipo_principal(perguntas) != uso:
        raise erro_padrao(_msg_padrao(uso))


def _publicado(f: Formulario) -> dict:
    """O documento no ar ({perguntas, tema, finais}), com o tema completo (como sai da normalização)."""
    tema = {**TEMA_PADRAO, **{k: v for k, v in (f.tema or {}).items() if k in TEMA_PADRAO}}
    return {"perguntas": f.perguntas, "tema": tema, "finais": f.finais or []}


def _documento_de_trabalho(f: Formulario) -> dict:
    """O que o editor edita: o rascunho, se houver; senão o publicado."""
    return f.rascunho if f.rascunho is not None else _publicado(f)


def _publicar(s: Session, ctx: Contexto, f: Formulario, doc: dict) -> None:
    """Põe o documento no ar: versão +1, quem e quando, auditoria e limpeza das imagens que ninguém mais cita."""
    f.perguntas, f.tema, f.finais = doc["perguntas"], doc["tema"], doc["finais"]
    f.versao = (f.versao or 0) + 1
    f.publicado_em = func.now()
    f.publicado_por = ctx.usuario_id
    f.atualizado_em = func.now()
    s.flush()
    registrar(s, "formulario_publicado", "info",
              {"formulario": {"id": f.id, "nome": f.nome}, "versao": f.versao,
               "perguntas": len(perguntas_respondiveis(f.perguntas)), "finais": len(f.finais)},
              usuario_id=ctx.usuario_id)
    imagens.limpar_do_formulario(s, ctx.conta_id, f.id)


def _mexeu_no_rascunho(ctx: Contexto, f: Formulario) -> None:
    f.rascunho_rev = (f.rascunho_rev or 0) + 1
    f.rascunho_em = func.now()
    f.rascunho_por = ctx.usuario_id


def _conferir_rev(s: Session, f: Formulario, rev: int) -> None:
    """Outra aba (ou pessoa) gravou depois: 409 `rascunho_desatualizado` com quem e quando, para o editor avisar."""
    if rev != f.rascunho_rev:
        raise AppError(409, "rascunho_desatualizado", MSG_DESATUALIZADO,
                       extra={"rev": f.rascunho_rev, "salvo_em": f.rascunho_em,
                              "salvo_por_nome": _nomes(s, f.rascunho_por).get(f.rascunho_por)})


def alterar(ctx: Contexto, formulario_id: int, dados) -> dict:
    """Com perguntas, tema ou finais: valida estrito e publica direto. O rascunho fica como está, mas o `rascunho_rev`
    sobe (como em toda publicação): o editor aberto recebe 409 e recarrega, em vez de publicar por cima."""
    campos = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        uso = _uso_padrao(f)
        conteudo = {c for c in ("perguntas", "tema", "finais") if c in campos and getattr(dados, c) is not None}
        if conteudo:
            doc, _ = normalizar_documento(
                dados.perguntas if "perguntas" in conteudo else f.perguntas,
                dados.tema if "tema" in conteudo else None,
                dados.finais if "finais" in conteudo else (f.finais or []),
                estrito=True, base_tema=f.tema)
            _conferir_padrao(f, doc["perguntas"])
        if "ativo" in campos and dados.ativo is not None:
            if uso and not dados.ativo:
                raise erro_padrao(f"Este é o formulário padrão de {ROTULO_USO[uso]} e não pode ser desativado. "
                                  "Escolha outro formulário como padrão antes.")
            f.ativo = dados.ativo
        for campo in ("nome", "descricao", "publico", "permite_editar"):
            if campo in campos and getattr(dados, campo) is not None:
                setattr(f, campo, getattr(dados, campo))
        if conteudo:
            _mexeu_no_rascunho(ctx, f)  # o editor aberto em outra aba fica sabendo (409) e recarrega
            _publicar(s, ctx, f, doc)
        f.atualizado_em = func.now()
        s.flush()
        s.refresh(f)
        return _json(s, f, _contar(s, f.id))


def salvar_rascunho(ctx: Contexto, formulario_id: int, dados) -> dict:
    """Grava o rascunho (§4.2): `rev` igual ao atual (senão 409), normaliza sem bloquear (só o estrutural dá 422) e,
    se ficou igual ao publicado, não guarda rascunho. Devolve {rev, salvo_em, problemas, avisos, tem_rascunho,
    rascunho} com o documento normalizado (ids gerados e HTML limpo, para o editor aplicar)."""
    campos = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        _conferir_rev(s, f, dados.rev)
        base = _documento_de_trabalho(f)
        doc, c = analisar_documento(
            dados.perguntas if "perguntas" in campos and dados.perguntas is not None else base.get("perguntas", []),
            dados.tema if "tema" in campos and dados.tema is not None else None,
            dados.finais if "finais" in campos and dados.finais is not None else base.get("finais", []),
            estrito=False, base_tema=base.get("tema") or f.tema)
        if c.estruturais:
            raise erro_documento(c.estruturais)
        problemas = c.todos()
        uso = _uso_padrao(f)
        if uso and tipo_principal(doc["perguntas"]) != uso:
            problemas.setdefault("perguntas", _msg_padrao(uso))
        f.rascunho = None if doc == _publicado(f) else doc
        _mexeu_no_rascunho(ctx, f)
        s.flush()
        s.refresh(f, ["rascunho_em"])
        return {"rev": f.rascunho_rev, "salvo_em": f.rascunho_em, "problemas": problemas,
                "avisos": {k: v for k, v in c.avisos.items() if problemas.get(k) == v},
                "tem_rascunho": f.rascunho is not None, "rascunho": doc}


def publicar(ctx: Contexto, formulario_id: int, dados) -> dict:
    """Publica o rascunho (§4.2): rev igual (senão 409), com rascunho (senão 409 `sem_rascunho`), validação estrita
    (422 com `campos`) e a regra do padrão (409). Responde o formulário completo."""
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        _conferir_rev(s, f, dados.rev)
        if f.rascunho is None:
            raise AppError(409, "sem_rascunho", MSG_SEM_RASCUNHO)
        r = f.rascunho
        doc, _ = normalizar_documento(r.get("perguntas"), r.get("tema"), r.get("finais"), estrito=True,
                                      base_tema=f.tema)
        _conferir_padrao(f, doc["perguntas"])
        f.rascunho = None
        _mexeu_no_rascunho(ctx, f)
        _publicar(s, ctx, f, doc)
        s.flush()
        s.refresh(f)
        return _json(s, f, _contar(s, f.id))


def descartar_rascunho(ctx: Contexto, formulario_id: int) -> None:
    """Descarta o rascunho (sem auditoria) e limpa as imagens que só ele usava."""
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        f.rascunho = None
        _mexeu_no_rascunho(ctx, f)
        s.flush()
        imagens.limpar_do_formulario(s, ctx.conta_id, f.id)


def _trocar_urls(valor, trocas: dict[str, str]):
    """Troca as URLs de imagem (logo e HTML) em qualquer texto do documento."""
    if isinstance(valor, str):
        for antiga, nova in trocas.items():
            valor = valor.replace(antiga, nova)
        return valor
    if isinstance(valor, list):
        return [_trocar_urls(v, trocas) for v in valor]
    if isinstance(valor, dict):
        return {k: _trocar_urls(v, trocas) for k, v in valor.items()}
    return valor


def duplicar(ctx: Contexto, formulario_id: int) -> dict:
    """Copia o publicado e o rascunho (se houver). As imagens do original (logo e conteúdo, menos as do banco de
    imagens) ganham cópias no formulário novo, com as URLs trocadas: trocar o logo de um não mexe no outro."""
    with em_conta(ctx.conta_id) as s:
        o = _form_ou_404(s, formulario_id)
        f = Formulario(conta_id=ctx.conta_id, nome=f"Cópia de {o.nome}"[:120], descricao=o.descricao,
                       perguntas=copy.deepcopy(o.perguntas), tema=copy.deepcopy(o.tema),
                       finais=copy.deepcopy(o.finais or []), rascunho=copy.deepcopy(o.rascunho), ativo=True,
                       publico=o.publico, permite_editar=o.permite_editar, publicado_por=ctx.usuario_id,
                       rascunho_por=ctx.usuario_id if o.rascunho is not None else None,
                       rascunho_em=func.now() if o.rascunho is not None else None)
        _inserir(s, f)
        textos = [json.dumps(x) for x in (o.tema, o.perguntas, o.finais, o.rascunho) if x]
        trocas = imagens.copiar_para_formulario(s, textos, ctx.conta_id, f.id)
        if trocas:
            f.tema, f.perguntas = _trocar_urls(f.tema, trocas), _trocar_urls(f.perguntas, trocas)
            f.finais, f.rascunho = _trocar_urls(f.finais, trocas), _trocar_urls(f.rascunho, trocas)
            s.flush()
        s.refresh(f)
        return _json(s, f, 0)


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
        return _json(s, f, _contar(s, f.id))


def enviar_logo(ctx: Contexto, formulario_id: int, dados: bytes, tipo: str) -> dict:
    """Guarda um logo novo do formulário (chave nova) e devolve a URL pública. O editor põe a URL em `tema.logo_url`
    do rascunho; o logo publicado não é apagado (a limpeza é ao publicar e ao descartar)."""
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)  # um envio por vez (a contagem do limite não corre)
        imagem = imagens.gravar_do_formulario(s, "logo_formulario", dados, tipo, ctx.conta_id, f.id)
        return {"logo_url": imagens.url_publica(imagem.chave)}


def enviar_imagem(ctx: Contexto, formulario_id: int, dados: bytes, tipo: str, nome: str | None) -> dict:
    """Imagem de um bloco de conteúdo (PNG ou JPEG de até 1 MB, já conferida): {url, largura, altura}."""
    largura, altura = imagens.dimensoes(dados, tipo)
    with em_conta(ctx.conta_id) as s:
        f = _form_ou_404(s, formulario_id, travar=True)
        imagem = imagens.gravar_do_formulario(s, "conteudo_formulario", dados, tipo, ctx.conta_id, f.id, nome=nome,
                                              largura=largura, altura=altura)
        return {"url": imagens.url_publica(imagem.chave), "largura": largura, "altura": altura}


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
        return _json(s, f, _contar(s, f.id))


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
        if not respondivel(p["tipo"]):  # quebra de página e bloco de conteúdo
            continue
        item = {"id": p["id"], "tipo": p["tipo"], "titulo": sem_citacoes(p["titulo"]),
                "respostas": por_pergunta.get(p["id"], 0)}
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
        "data": r.data_resposta, "origem": r.origem, "editada_em": r.editada_em, "edicoes": r.edicoes,
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
    perguntas = perguntas_respondiveis(f.perguntas)
    v = variaveis(empresa)
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["Data", "Contato", "E-mail", "Empresa", "Canal", "Referência",
                *[ROTULOS_CONTEXTO[k] for k in CHAVES_CONTEXTO],
                *[sem_citacoes(renderizar(p["titulo"], v)) or p["id"] for p in perguntas]])
    for r, _, contato_nome, contato_email, empresa_nome in linhas:
        w.writerow([
            r.data_resposta.astimezone(FUSO).strftime("%d/%m/%Y %H:%M"),
            _celula(contato_nome), _celula(contato_email), _celula(empresa_nome), r.canal, _celula(r.referencia),
            *[_celula(r.contexto.get(k)) for k in CHAVES_CONTEXTO],
            *[_celula(formatar_valor(r.respostas[p["id"]])) if p["id"] in r.respostas else "" for p in perguntas],
        ])
    nome = re.sub(r"[^a-z0-9]+", "-", sem_acento(f.nome.lower())).strip("-") or "formulario"
    return buf.getvalue(), f"respostas-{nome}.csv"
