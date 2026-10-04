"""Plataforma › Parâmetros (etapa 5g): a equipe Toqqi (superadmin) edita preços e limites dos planos, IA, WhatsApp
automático e teste, por grupo, com prévia do impacto e histórico. Valores, padrões, validação e cache em
`core.parametros`. Modo sistema de propósito (os parâmetros não são de conta alguma); tela, prévia e PUT leem o banco
direto, sem cache.

Rotas (`requer_superadmin`):
- GET /plataforma/parametros → {grupos: [{grupo, rotulo, versao, alterado_em, alterado_por, valores, padroes,
  origens}]}, na ordem de `GRUPOS`. `versao` = id da última linha do histórico do grupo (0 sem nenhuma), de onde vêm
  `alterado_em`/`alterado_por` (null sem nenhuma). Dinheiro em texto ("149.00").
- POST /plataforma/parametros/{grupo}/previa {valores} → {mudancas: [{chave, de, para}], precisa_confirmar, impactos:
  [{chave, contas, exemplos: [{id, nome, uso}]}]} (validação e 422 do PUT; não testa o modelo). Impacto de cada valor
  que diminui: contatos → contas do plano (não cortesia) com mais ativos que o novo limite (`uso` = ativos); cota, teto
  e franquia → contas a que o valor se aplica (`cota.chave_do_limite`, `regras.chave_do_teto`,
  `franquia.plano_da_franquia`) que já usaram o novo valor ou mais no mês (`uso` = usado); análises de um nível que
  aumentam → contas com o nível (equilibrado: também o desconhecido; `uso` 0). `exemplos`: até 5, de maior uso.
  `precisa_confirmar`: preço mudou; limite de contatos, cota, teto ou franquia diminuiu; análises aumentaram; ou a
  exclusão automática foi a `ligada`.
- PUT /plataforma/parametros/{grupo} {versao, valores, confirmar} → o grupo (como no GET) e, em `ia`, `testados`:
  (1) valida (422; grupo desconhecido → 404); (2) nada mudou → 200 sem gravar; (3) `precisa_confirmar` sem
  `confirmar: true` → 409 `confirmacao_necessaria`; (4) em `ia`, testa cada nível com modelo ou esforço mudado
  (`ia_texto.testar`, fora da transação; recusa → 422 no campo `ia.modelo.{nivel}`, sem resposta → 503
  `teste_ia_indisponivel`; sem IA na plataforma, não testa); (5) transação com a trava `parametros`: `versao` ≠ a
  atual → 409 `parametros_alterados`; apaga as linhas do grupo fora do formato (gravadas à mão; também sem outra
  mudança, sem histórico); grava (igual ao padrão → apaga a linha; senão upsert da chave e do valor), o histórico só
  com o que mudou e o evento global `parametros_alterados` (atenção) {grupo, por, mudancas}; depois do commit,
  `invalidar()`. Quem alterou e quando ficam só no histórico (a tabela `parametros` tem só chave e valor).
- GET /plataforma/parametros/historico?grupo=&pagina=&por_pagina= → página de {id, criado_em, grupo, por, mudancas},
  mais novos primeiro (`por_pagina` 20, até 100).
Público (sem login, 60/min por IP, `Cache-Control: public, max-age=60`):
- GET /publico/planos → {planos: [{chave, nome, preco, contatos, whatsapp, ia_cota, ia_teto}], teste: {dias, plano,
  whatsapp, ia_teto}, ia_analises: {rapido, equilibrado, detalhado}} (do cache; sem modelos nem o modo da exclusão).
"""
import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import ia, ia_texto, parametros
from toqqi.core.auditoria import registrar
from toqqi.core.db import apos_commit, modo_sistema, travar
from toqqi.core.deps import Contexto, requer_superadmin
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.planos import PLANOS
from toqqi.core.rate_limit import LIMITE_PLANOS_PUBLICOS, limiter
from toqqi.modelos import Conta, Contato, IaUsoMensal, Parametro, ParametroHistorico, WhatsappUso
from toqqi.modulos.ia import cota, regras
from toqqi.modulos.whatsapp import franquia

log = logging.getLogger("toqqi.parametros")

router = APIRouter(prefix="/plataforma/parametros", tags=["plataforma"])
router_publico = APIRouter(prefix="/publico", tags=["publico"])

TRAVA = "parametros"
MAX_EXEMPLOS = 5
POR_PAGINA = 20
POR_PAGINA_MAX = 100
MSG_CONFIRMAR = "Confirme a mudança antes de salvar."
MSG_ALTERADOS = ("Outra pessoa mudou estes parâmetros enquanto você editava. Recarregue para ver os valores "
                 "atuais.")
MSG_TESTE_INDISPONIVEL = ("Não deu para testar o modelo agora: a OpenAI não respondeu. Nada foi salvo; tente de novo "
                          "em alguns minutos.")


class PreviaIn(BaseModel):
    valores: dict[str, Any]


class SalvarIn(BaseModel):
    versao: Annotated[int, Field(ge=0)]
    valores: dict[str, Any]
    confirmar: bool = False


# ---- leitura -------------------------------------------------------------------------------------------------

def _grupo_valido(nome: str) -> str:
    if nome not in parametros.GRUPOS:
        raise nao_encontrado("Grupo de parâmetros não encontrado.")
    return nome


def _ultima(s: Session, nome: str) -> ParametroHistorico | None:
    return s.scalar(select(ParametroHistorico).where(ParametroHistorico.grupo == nome)
                    .order_by(ParametroHistorico.id.desc()).limit(1))


def _grupo_json(s: Session, nome: str, validas: dict) -> dict:
    ultima = _ultima(s, nome)
    chaves = parametros.chaves_do_grupo(nome)
    return {
        "grupo": nome, "rotulo": parametros.GRUPOS[nome], "versao": ultima.id if ultima else 0,
        "alterado_em": ultima.criado_em if ultima else None, "alterado_por": ultima.por if ultima else None,
        "valores": {c: parametros.para_json(c, parametros.efetivo(c, validas)) for c in chaves},
        "padroes": {c: parametros.para_json(c, parametros.padrao(c)) for c in chaves},
        "origens": {c: parametros.origem(c, validas) for c in chaves},
    }


def listar() -> dict:
    with modo_sistema() as s:
        validas = parametros.linhas_validas(parametros.ler_banco(s))
        return {"grupos": [_grupo_json(s, g, validas) for g in parametros.GRUPOS]}


# ---- mudanças, confirmação e impacto --------------------------------------------------------------------------

def _mudancas(nome: str, novos: dict, validas: dict) -> list[tuple[str, Any, Any]]:
    """[(chave, de, para)] (valores efetivos, no tipo do Python) só do que muda, na ordem das chaves."""
    saida = []
    for c in parametros.chaves_do_grupo(nome):
        de = parametros.efetivo(c, validas)
        if de != novos[c]:
            saida.append((c, de, novos[c]))
    return saida


def _mudancas_json(mudancas: list[tuple[str, Any, Any]]) -> list[dict]:
    return [{"chave": c, "de": parametros.para_json(c, de), "para": parametros.para_json(c, para)}
            for c, de, para in mudancas]


def _diminuiu(chave: str, de, para) -> bool:
    if chave.endswith(".contatos"):
        return parametros._maior(de, para)
    return para < de


def _familia(chave: str) -> str | None:
    if chave.startswith("planos.") and chave.endswith(".preco"):
        return "preco"
    if chave.startswith("planos.") and chave.endswith(".contatos"):
        return "contatos"
    for prefixo in ("ia.cota.", "ia.teto.", "whatsapp.franquia.", "ia.analises."):
        if chave.startswith(prefixo):
            return prefixo.rstrip(".")
    if chave == "teste.exclusao_automatica":
        return "exclusao"
    return None


def _pede_confirmacao(m: tuple[str, Any, Any]) -> bool:
    chave, de, para = m
    familia = _familia(chave)
    if familia == "preco":
        return True
    if familia in ("contatos", "ia.cota", "ia.teto", "whatsapp.franquia"):
        return _diminuiu(chave, de, para)
    if familia == "ia.analises":
        return para > de
    if familia == "exclusao":
        return para == "ligada"
    return False


def _exemplos(linhas: list[tuple[int, str, int]]) -> dict:
    linhas = sorted(linhas, key=lambda x: (-x[2], x[0]))
    return {"contas": len(linhas), "exemplos": [{"id": i, "nome": n, "uso": u} for i, n, u in linhas[:MAX_EXEMPLOS]]}


def _impacto_contatos(s: Session, plano: str, limite: int | None) -> dict:
    if limite is None:
        return _exemplos([])
    ativos = (select(Contato.conta_id, func.count().label("n")).where(Contato.ativo.is_(True))
              .group_by(Contato.conta_id).subquery())
    linhas = s.execute(select(Conta.id, Conta.nome, ativos.c.n).join(ativos, ativos.c.conta_id == Conta.id)
                       .where(Conta.plano == plano, Conta.situacao != "cortesia", ativos.c.n > limite)).all()
    return _exemplos([tuple(x) for x in linhas])


def _impacto_ia(s: Session, chave: str, novo: int, coluna, qual) -> dict:
    """Contas a que `chave` se aplica (`qual(conta) == chave`) que já usaram `novo` ou mais no mês (`coluna` de
    ia_uso_mensal: cota_usada ou analises)."""
    uso = func.coalesce(coluna, 0)
    linhas = s.execute(select(Conta, uso).outerjoin(
        IaUsoMensal, (IaUsoMensal.conta_id == Conta.id) & (IaUsoMensal.mes == cota.mes_atual()))
        .where(uso >= novo)).all()
    return _exemplos([(c.id, c.nome, int(u)) for c, u in linhas if qual(c) == chave])


def _impacto_franquia(s: Session, chave: str, novo: int) -> dict:
    uso = func.coalesce(WhatsappUso.usadas, 0)
    linhas = s.execute(select(Conta, uso).outerjoin(
        WhatsappUso, (WhatsappUso.conta_id == Conta.id) & (WhatsappUso.mes == franquia.mes_atual()))
        .where(uso >= novo)).all()
    return _exemplos([(c.id, c.nome, int(u)) for c, u in linhas
                      if f"whatsapp.franquia.{franquia.plano_da_franquia(c)}" == chave])


def _impacto_analises(s: Session, nivel: str) -> dict:
    if nivel == ia_texto.NIVEL_PADRAO:
        filtro = Conta.ia_modelo.is_(None) | Conta.ia_modelo.notin_([n for n in ia_texto.NIVEIS if n != nivel])
    else:
        filtro = Conta.ia_modelo == nivel
    return _exemplos([(i, n, 0) for i, n in s.execute(select(Conta.id, Conta.nome).where(filtro)).all()])


def _impacto(s: Session, m: tuple[str, Any, Any]) -> dict | None:
    """O impacto de uma mudança que pede confirmação por diminuir um limite (ou aumentar as análises de um nível)."""
    chave, _, para = m
    familia = _familia(chave)
    if familia in (None, "preco", "exclusao") or not _pede_confirmacao(m):
        return None
    ultimo = chave.rsplit(".", 1)[1]
    if familia == "contatos":
        dados = _impacto_contatos(s, chave.split(".")[1], para)
    elif familia == "ia.cota":
        dados = _impacto_ia(s, chave, para, IaUsoMensal.cota_usada, cota.chave_do_limite)
    elif familia == "ia.teto":
        dados = _impacto_ia(s, chave, para, IaUsoMensal.analises, regras.chave_do_teto)
    elif familia == "whatsapp.franquia":
        dados = _impacto_franquia(s, chave, para)
    else:  # ia.analises
        dados = _impacto_analises(s, ultimo)
    return {"chave": chave, **dados}


def _analisar(nome: str, valores) -> tuple[dict, list[tuple[str, Any, Any]], bool, bool]:
    """(valores normalizados, mudanças, precisa_confirmar, há linhas do grupo fora do formato), lidos do banco agora."""
    novos = parametros.validar(nome, valores)
    with modo_sistema() as s:
        linhas = parametros.ler_banco(s)
        validas = parametros.linhas_validas(linhas)
        invalidas = parametros.invalidas_do_grupo(nome, linhas)
    mudancas = _mudancas(nome, novos, validas)
    return novos, mudancas, any(_pede_confirmacao(m) for m in mudancas), bool(invalidas)


def previa(nome: str, valores) -> dict:
    nome = _grupo_valido(nome)
    novos = parametros.validar(nome, valores)
    with modo_sistema() as s:
        validas = parametros.linhas_validas(parametros.ler_banco(s))
        mudancas = _mudancas(nome, novos, validas)
        impactos = [i for i in (_impacto(s, m) for m in mudancas) if i is not None]
    return {"mudancas": _mudancas_json(mudancas), "precisa_confirmar": any(_pede_confirmacao(m) for m in mudancas),
            "impactos": impactos}


# ---- teste do modelo ------------------------------------------------------------------------------------------

def _rotulo_esforco(esforco: str) -> str:
    return f"com o esforço “{esforco}”" if esforco else "sem raciocínio"


def _testar_niveis(novos: dict, mudancas: list[tuple[str, Any, Any]]) -> list[str]:
    """Testa cada nível com modelo ou esforço mudado, parando no primeiro erro. Sem IA na plataforma, não testa."""
    mudadas = {m[0] for m in mudancas}
    niveis = [n for n in ia_texto.NIVEIS if {f"ia.modelo.{n}", f"ia.esforco.{n}"} & mudadas]
    if not niveis or not ia.disponivel():
        return []
    for n in niveis:
        modelo, esforco = novos[f"ia.modelo.{n}"], novos[f"ia.esforco.{n}"]
        try:
            ia_texto.testar(modelo, esforco)
        except ia.FalhaIA as falha:
            log.warning("Parâmetros: o teste do nível %s (modelo %s) falhou (%s: %s); nada foi salvo.", n, modelo,
                        falha.tipo, falha.detalhe)
            if falha.tipo == "transitoria":
                raise AppError(503, "teste_ia_indisponivel", MSG_TESTE_INDISPONIVEL) from None
            http = f" ({falha.detalhe.split(' (')[0]})" if falha.detalhe.startswith("HTTP ") else ""
            msg = (f"A OpenAI recusou o modelo “{modelo}” {_rotulo_esforco(esforco)}{http}. Confira o nome e o "
                   "esforço.")
            raise AppError(422, "dados_invalidos", parametros.MSG_INVALIDOS, {f"ia.modelo.{n}": msg}) from None
    return niveis


# ---- salvar ---------------------------------------------------------------------------------------------------

def _gravar(s: Session, nome: str, novos: dict, mudancas: list[tuple[str, Any, Any]], por: str) -> list[dict]:
    """Grava as mudanças (igual ao padrão → apaga a linha; senão upsert só da chave e do valor), o histórico (quem e
    quando ficam só nele) e o evento global."""
    for chave, _, _ in mudancas:
        if novos[chave] == parametros.padrao(chave):
            s.execute(delete(Parametro).where(Parametro.chave == chave))
        else:
            valor = parametros.para_json(chave, novos[chave])
            s.execute(insert(Parametro).values(chave=chave, valor=valor)
                      .on_conflict_do_update(index_elements=[Parametro.chave], set_={"valor": valor}))
    em_json = _mudancas_json(mudancas)
    s.add(ParametroHistorico(grupo=nome, por=por, mudancas=em_json))
    registrar(s, "parametros_alterados", "atencao", {"grupo": nome, "por": por, "mudancas": em_json})
    s.flush()
    return em_json


def _apagar_invalidas(s: Session, nome: str, linhas: dict[str, Parametro]) -> list[str]:
    """Apaga as linhas do grupo fora do formato (ou de chaves que o código não conhece), gravadas à mão: a tela mostrava
    o padrão no lugar delas e é o que passa a valer (ou o valor salvo junto). Sem histórico: o valor efetivo da tela
    não muda por isso."""
    invalidas = parametros.invalidas_do_grupo(nome, linhas)
    if invalidas:
        s.execute(delete(Parametro).where(Parametro.chave.in_(invalidas)))
        log.warning("Parâmetros: o PUT do grupo %s apagou linhas fora do formato (%s).", nome, ", ".join(invalidas))
    return invalidas


def salvar(ctx: Contexto, nome: str, dados: SalvarIn) -> dict:
    nome = _grupo_valido(nome)
    novos, mudancas, confirmar, invalidas = _analisar(nome, dados.valores)
    extra = {"testados": []} if nome == "ia" else {}
    if mudancas and confirmar and not dados.confirmar:
        raise AppError(409, "confirmacao_necessaria", MSG_CONFIRMAR)
    if mudancas and nome == "ia":
        extra["testados"] = _testar_niveis(novos, mudancas)
    with modo_sistema() as s:
        if mudancas or invalidas:
            travar(s, TRAVA)
            ultima = _ultima(s, nome)
            if (ultima.id if ultima else 0) != dados.versao:
                raise AppError(409, "parametros_alterados", MSG_ALTERADOS)
            linhas = parametros.ler_banco(s)
            apagadas = _apagar_invalidas(s, nome, linhas)
            mudancas = _mudancas(nome, novos, parametros.linhas_validas(linhas))
            if mudancas:
                por = ctx.email[:254]
                _gravar(s, nome, novos, mudancas, por)
                log.info("Parâmetros: grupo %s alterado por um superadmin (%s).", nome,
                         ", ".join(m[0] for m in mudancas))
            if mudancas or apagadas:
                apos_commit(s, parametros.invalidar)
        resultado = _grupo_json(s, nome, parametros.linhas_validas(parametros.ler_banco(s)))
    return {**resultado, **extra}


# ---- histórico ------------------------------------------------------------------------------------------------

def historico(nome: str | None, pagina: int, por_pagina: int) -> dict:
    filtro = [ParametroHistorico.grupo == nome] if nome else []
    with modo_sistema() as s:
        total = s.scalar(select(func.count()).select_from(ParametroHistorico).where(*filtro))
        linhas = s.scalars(select(ParametroHistorico).where(*filtro).order_by(ParametroHistorico.id.desc())
                           .offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    itens = [{"id": h.id, "criado_em": h.criado_em, "grupo": h.grupo, "por": h.por, "mudancas": h.mudancas}
             for h in linhas]
    return {"itens": itens, "total": total, "pagina": pagina, "por_pagina": por_pagina}


# ---- público --------------------------------------------------------------------------------------------------

def planos_publicos() -> dict:
    v = parametros.valor
    return {
        "planos": [{"chave": c, "nome": n, "preco": v(f"planos.{c}.preco"), "contatos": v(f"planos.{c}.contatos"),
                    "whatsapp": v(f"whatsapp.franquia.{c}"), "ia_cota": v(f"ia.cota.{c}"), "ia_teto": v(f"ia.teto.{c}")}
                   for c, n in PLANOS],
        "teste": {"dias": v("teste.dias"), "plano": v("teste.plano"), "whatsapp": v("whatsapp.franquia.teste"),
                  "ia_teto": v("ia.teto.teste")},
        "ia_analises": {n: v(f"ia.analises.{n}") for n in ia_texto.NIVEIS},
    }


# ---- rotas ----------------------------------------------------------------------------------------------------

@router.get("")
def obter(ctx: Contexto = Depends(requer_superadmin)):
    return listar()


@router.get("/historico")
def ver_historico(
    grupo: Annotated[Literal[("", *parametros.GRUPOS)] | None, Query()] = None,  # type: ignore[valid-type]
    pagina: Annotated[int, Query(ge=1, le=100000)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAX)] = POR_PAGINA,
    ctx: Contexto = Depends(requer_superadmin),
):
    return historico(grupo or None, pagina, por_pagina)


@router.post("/{grupo}/previa")
def ver_previa(grupo: str, dados: PreviaIn, ctx: Contexto = Depends(requer_superadmin)):
    return previa(grupo, dados.valores)


@router.put("/{grupo}")
def alterar(grupo: str, dados: SalvarIn, ctx: Contexto = Depends(requer_superadmin)):
    return salvar(ctx, grupo, dados)


@router_publico.get("/planos")
@limiter.limit(LIMITE_PLANOS_PUBLICOS)
def planos(request: Request):
    """Preços e limites de hoje para o site da raiz (sem login)."""
    return JSONResponse(jsonable_encoder(planos_publicos()), headers={"Cache-Control": "public, max-age=60"})
