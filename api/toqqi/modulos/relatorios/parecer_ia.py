"""Parecer dos relatórios pela IA (etapa 5d, §2.4 e §2.5): o que vai para a IA, as instruções, o formato e a limpeza.
O fluxo (cota, travas, gravação) é o de `ia.pareceres`.

Dados, com os filtros comuns dos relatórios (`relatorios.servico`, as mesmas regras e sem JIT): os totais de
respostas do recorte (NPS e CSAT, para citar o total e avisar a amostra pequena); o resumo da aba Empresas (empresas,
com respostas, cobertura, receita total e em risco com o percentual, faixas); a matriz NPS × valor (quadrantes e até 5
empresas "Proteger já": nome, NPS, valor mensal, responsável); os temas citados (menções, reclamações, nota média e
variação) e os picos; os até 5 responsáveis com mais receita em risco (nome, empresas, NPS, receita em risco, ações
abertas e vencidas); a operação (taxa de resposta, ações concluídas no prazo, contatos sem resposta: só o total e os
atrasados) e "esta semana" (os últimos 7 dias até hoje, com os mesmos filtros de empresa: detratores novos e as ações
vencidas agora). Nenhum comentário, nenhum nome de contato. Datas em dd/mm/aaaa e valores em reais com duas casas.

Formato: {"resumo", "recomendacoes"} — resumo de 2 a 3 frases (até 600 caracteres) e de 1 a 3 recomendações para a
semana (até 200 caracteres cada, sem vazias nem repetidas) depois da limpeza; resumo vazio ou nenhuma recomendação =
falha transitória (a análise volta para a cota).
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toqqi.core.deps import Contexto
from toqqi.core.ia_texto import PADROES_MEMORIA
from toqqi.modelos import Acao, Empresa, Resposta
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.ia.pareceres import Recorte, Tipo, falha_de_formato, linha
from toqqi.modulos.painel import servico as painel
from toqqi.modulos.painel.resumo_ia import (
    AMOSTRA_NPS,
    REGRAS,
    cabecalho,
    data_br,
    filtros_json,
    periodo_texto,
    picos_json,
    reais,
)
from toqqi.modulos.relatorios import picos as picos_mod
from toqqi.modulos.relatorios import servico as rel
from toqqi.modulos.relatorios.regras import QUADRANTES
from toqqi.modulos.respostas import indicadores as ind
from toqqi.modulos.respostas import temas as temas_mod

NOME_FORMATO = "parecer_relatorios"
MAX_RESUMO = 600
MAX_RECOMENDACAO = 200
MAX_RECOMENDACOES = 3
MAX_PROTEGER = 5
MAX_RESPONSAVEIS = 5
DIAS_SEMANA = 7

ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["resumo", "recomendacoes"],
    "properties": {
        "resumo": {"type": "string", "description": "2 a 3 frases, até 600 caracteres"},
        "recomendacoes": {"type": "array", "items": {"type": "string"},
                          "description": "1 a 3 recomendações para esta semana, até 200 caracteres cada"},
    },
}


def instrucoes(conta: str, hoje: date) -> str:
    return f"""{cabecalho(conta, hoje)}

{REGRAS}

Tarefa
Escreva o parecer dos relatórios para o recorte filtrado:
- "resumo": de 2 a 3 frases (até 600 caracteres) com o principal do período: como está a satisfação, onde está o \
risco e o que chama a atenção;
- "recomendacoes": de 1 a 3 recomendações para esta semana (até 200 caracteres cada), concretas, na ordem de \
prioridade, cada uma ligada a um número dos dados."""


@dataclass
class _Filtros:
    """Os filtros comuns no formato que as funções de `relatorios.servico` leem."""
    de: date | None
    ate: date | None
    grupo_id: int | None
    so_ativos: bool


def _temas(s: Session, conds: list, conds_anterior: list | None) -> list[dict]:
    contagem = rel._contagem_temas(s, conds)
    anterior = rel._contagem_temas(s, conds_anterior) if conds_anterior is not None else None
    itens = []
    for t in temas_mod.CHAVES:
        mencoes, reclamacoes, _elogios, n_nps, soma = contagem.get(t, [0] * 9)[:5]
        variacao = None if anterior is None else mencoes - anterior.get(t, [0])[0]
        if mencoes or variacao:
            itens.append({"tema": temas_mod.ROTULOS[t], "mencoes": mencoes, "reclamacoes": reclamacoes,
                          "nota_media": ind.media(soma, n_nps, 1), "variacao": variacao})
    return sorted(itens, key=lambda x: -x["mencoes"])


def _responsaveis(carteiras: list[dict]) -> list[dict]:
    ordem = sorted(carteiras, key=lambda x: (-x["receita_em_risco"], -x["acoes_vencidas"], -x["acoes_abertas"]))
    return [{"nome": (x["responsavel"] or {}).get("nome") or "Sem responsável", "empresas": x["empresas"],
             "nps": x["nps"]["valor"], "receita_em_risco": reais(x["receita_em_risco"]),
             "acoes_abertas": x["acoes_abertas"], "acoes_vencidas": x["acoes_vencidas"]}
            for x in ordem[:MAX_RESPONSAVEIS]]


def _esta_semana(s: Session, ctx: Contexto, r: Recorte, hoje: date) -> dict:
    inicio = hoje - timedelta(days=DIAS_SEMANA - 1)
    f = painel.Filtro(ctx.conta_id, inicio, hoje, r.grupo_id, r.so_ativos)
    detratores = s.scalar(painel._com_empresa(select(func.count()).select_from(Resposta))
                          .where(*f.respostas(), painel.NPS, Resposta.grupo == "detrator"))
    vencidas = s.scalar(select(func.count()).select_from(Acao).outerjoin(Empresa, Empresa.id == Acao.empresa_id)
                        .where(Acao.conta_id == ctx.conta_id, aberta(), Acao.prazo < hoje,
                               *f.empresa(Acao.empresa_id)))
    return {"periodo": periodo_texto(inicio, hoje), "detratores_novos": detratores, "acoes_vencidas": vencidas}


def dados(s: Session, ctx: Contexto, r: Recorte, hoje: date) -> dict | None:
    """Os dados do parecer; None sem nenhuma resposta NPS nem CSAT no recorte."""
    filtro = painel.Filtro(ctx.conta_id, r.de, r.ate, r.grupo_id, r.so_ativos)
    nps, csat, _tom = painel._nps_csat(s, filtro.respostas())  # o terceiro (contagens do "Tom", painel v2) não entra aqui
    if not nps["total"] and not csat["total"]:
        return None
    f = _Filtros(r.de, r.ate, r.grupo_id, r.so_ativos)
    itens, resumo, matriz = rel._dados_empresas(s, ctx, f)
    anterior = None
    if r.de and r.ate:  # mesmo tamanho, imediatamente antes (como a aba Temas)
        dias = (r.ate - r.de).days + 1
        anterior = filtro.respostas(r.de - timedelta(days=dias), r.de - timedelta(days=1))
    proteger = sorted((x for x in itens if x["quadrante"] == "proteger"), key=lambda x: -x["valor_mensal"])
    receita, cobertura = resumo["receita"], resumo["cobertura"]
    operacao = rel.numeros_operacao(s, ctx, f, hoje)
    return {
        "hoje": data_br(hoje),
        "periodo": periodo_texto(r.de, r.ate),
        "filtros": filtros_json(s, r),
        "respostas": {"nps": nps["total"], "csat": csat["total"], "amostra_pequena": nps["total"] < AMOSTRA_NPS},
        "nps": {k: nps[k] for k in ("valor", "promotores", "neutros", "detratores")},
        "csat": {k: csat[k] for k in ("percentual", "media")},
        "empresas": {
            "total": resumo["empresas"], "com_respostas": resumo["com_respostas"],
            "cobertura": {"contatos_ativos": cobertura["contatos_ativos"], "responderam": cobertura["responderam"],
                          "percentual": cobertura["percentual"]},
            "receita": {"total": reais(receita["total"]), "em_risco": reais(receita["em_risco"]),
                        "percentual_em_risco": receita["percentual"], "empresas_em_risco": receita["empresas_em_risco"],
                        "empresas_em_risco_sem_valor": receita["sem_valor"]},
            "por_faixa_de_nps": resumo["por_faixa"],
        },
        "matriz_nps_valor": {
            "mediana_do_valor_mensal": reais(matriz["mediana_valor"]) if matriz["mediana_valor"] is not None else None,
            "quadrantes": {QUADRANTES[k]: n for k, n in matriz["quadrantes"].items()},
            "proteger_ja": [{"nome": x["empresa"]["nome"], "nps": x["nps"]["valor"],
                             "valor_mensal": reais(x["valor_mensal"]),
                             "responsavel": (x["responsavel"] or {}).get("nome")} for x in proteger[:MAX_PROTEGER]],
        },
        "temas": _temas(s, filtro.respostas(), anterior),
        "picos_de_reclamacao": picos_json(picos_mod.calcular(s, ctx.conta_id, hoje)),
        "responsaveis": _responsaveis(rel._carteiras(s, ctx, f)),
        "operacao": {
            "taxa_de_resposta": {"percentual": operacao["taxa_resposta"]["percentual"],
                                 "amostra_pequena": operacao["taxa_resposta"]["amostra_pequena"]},
            "acoes_concluidas": {"concluidas": operacao["acoes"]["concluidas"],
                                 "no_prazo_percentual": operacao["acoes"]["no_prazo_percentual"]},
            "contatos_sem_resposta": {"total": operacao["sem_resposta"]["total"],
                                      "atrasados": operacao["sem_resposta"]["atrasados"]},
        },
        "esta_semana": _esta_semana(s, ctx, r, hoje),
    }


# ---- depois da IA ----------------------------------------------------------------------------------

def normalizar(conteudo: dict) -> dict:
    resumo = linha(conteudo.get("resumo"), MAX_RESUMO)
    if not resumo:
        raise falha_de_formato("parecer sem resumo")
    recomendacoes: list[str] = []
    lista = conteudo.get("recomendacoes")
    for item in lista if isinstance(lista, list) else []:
        texto = linha(item, MAX_RECOMENDACAO)
        if texto and texto not in recomendacoes:
            recomendacoes.append(texto)
        if len(recomendacoes) == MAX_RECOMENDACOES:
            break
    if not recomendacoes:
        raise falha_de_formato("parecer sem recomendações")
    return {"resumo": resumo, "recomendacoes": recomendacoes}


def exemplo_memoria(d: dict) -> dict:
    """Provedor de memória (testes e teste integrado): texto previsível a partir dos números recebidos."""
    empresas, semana = d["empresas"], d["esta_semana"]
    nps = (f"o NPS foi {d['nps']['valor']} com {d['respostas']['nps']} respostas" if d["nps"]["valor"] is not None
           else f"não houve respostas de NPS (CSAT: {d['respostas']['csat']} respostas)")
    resumo = (f"No período ({d['periodo']}), {nps}, e {empresas['com_respostas']} de {empresas['total']} empresas "
              f"responderam. A receita em risco é {empresas['receita']['em_risco']}.")
    recomendacoes = [f"Fale esta semana com as {len(d['matriz_nps_valor']['proteger_ja'])} empresas do quadrante "
                     "Proteger já.",
                     f"Trate os {semana['detratores_novos']} detratores novos e as {semana['acoes_vencidas']} ações "
                     "vencidas."]
    return {"resumo": resumo, "recomendacoes": recomendacoes}


PADROES_MEMORIA[NOME_FORMATO] = exemplo_memoria

TIPO = Tipo(nome="relatorios", nome_formato=NOME_FORMATO, esquema=ESQUEMA, dados=dados, instrucoes=instrucoes,
            normalizar=normalizar, msg_andamento="Já tem um parecer sendo gerado. Aguarde alguns segundos.",
            msg_falha="Não foi possível gerar o parecer agora. Tente de novo em instantes.")
