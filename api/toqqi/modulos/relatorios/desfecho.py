"""Etapa 5i, Relatórios › Desfecho (docs/api-etapa-5i.md §2.6): quem saiu, por quê, o que dizia antes de sair e quanto
da receita ficou (GRR e NRR).

O estado de uma empresa num dia sai do histórico gravado pelo banco (`empresa_historico`): vale a última linha com
`data` antes daquele dia, na ordem (data, id). `entrada`, `valor` e `reativada` = cliente, com `valor_depois`;
`perdida` = perdida; sem linha = ainda não existia. Filtros: os de empresa da 4b, sobre os dados atuais da empresa
(sem "só ativas": as perdidas são inativas)."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.modelos import Acao, EmpresaHistorico, Resposta
from toqqi.modulos.empresas.desfecho import MOTIVOS
from toqqi.modulos.painel.servico import _validar_periodo
from toqqi.modulos.relatorios.regras import carregar_empresas
from toqqi.modulos.respostas.indicadores import percentual

JANELA_ANTES = 90  # dias até a perda (inclusive) em que se olha a nota
AMOSTRA_PEQUENA = 5
MAX_ITENS = 500
GRUPOS_ANTES = ("detrator", "neutro", "promotor", "sem_resposta")
ZERO = Decimal("0.00")


def _estado(linhas: list, ate: date, inclusive: bool) -> tuple[str, Decimal | None] | None:
    """(cliente|perdida, valor) da empresa no fim de `ate` (inclusive) ou logo antes dele; None = não existia."""
    atual = None
    for x in linhas:
        if x.data < ate or (inclusive and x.data == ate):
            atual = x
        else:
            break
    if atual is None:
        return None
    if atual.tipo == "perdida":
        return "perdida", atual.valor_antes
    return "cliente", atual.valor_depois


def _grupo_antes(notas: list[tuple[date, int]], fim: date) -> tuple[str, dict | None]:
    """Pela pior nota NPS nos JANELA_ANTES dias até `fim`: detrator > neutro > promotor > sem resposta."""
    inicio = fim - timedelta(days=JANELA_ANTES - 1)
    dentro = [(d, n) for d, n in notas if inicio <= d <= fim]
    if not dentro:
        return "sem_resposta", None
    pior = min(n for _, n in dentro)
    d, n = max(dentro)
    grupo = "detrator" if pior <= 6 else "neutro" if pior <= 8 else "promotor"
    return grupo, {"nota": n, "data": d}


def _bloco(contagem: dict, total: int) -> dict:
    return {"total": total, **{g: contagem.get(g, 0) for g in GRUPOS_ANTES},
            "percentuais": {g: percentual(contagem.get(g, 0), total, 1) for g in GRUPOS_ANTES}}


def _pct(parte: Decimal, total: Decimal) -> float | None:
    return float(round(parte * 100 / total, 1)) if total else None


def relatorio(ctx: Contexto, f) -> dict:
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    fim = min(f.ate or hoje, hoje)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        filtro = _filtro(f)
        empresas = {e.id: e for e in carregar_empresas(s, ctx.conta_id, filtro, hoje)}
        ids = list(empresas)
        historico = defaultdict(list)
        for x in s.execute(select(EmpresaHistorico.empresa_id, EmpresaHistorico.tipo, EmpresaHistorico.data,
                                  EmpresaHistorico.valor_antes, EmpresaHistorico.valor_depois,
                                  EmpresaHistorico.motivo, EmpresaHistorico.motivo_detalhe)
                           .where(EmpresaHistorico.empresa_id.in_(ids))
                           .order_by(EmpresaHistorico.empresa_id, EmpresaHistorico.data, EmpresaHistorico.id)):
            historico[x.empresa_id].append(x)
        primeira = min((h[0].data for h in historico.values()), default=None)
        inicio = f.de or primeira or fim
        migracao = s.scalar(select(func.min(func.timezone(relogio.FUSO_NOME, EmpresaHistorico.criado_em)))
                            .where(EmpresaHistorico.origem == "migracao"))
        janela_notas = min(inicio, fim) - timedelta(days=JANELA_ANTES)
        notas = defaultdict(list)
        for e_id, quando, nota in s.execute(
                select(Resposta.empresa_id, Resposta.data_resposta, Resposta.nota)
                .where(Resposta.empresa_id.in_(ids), Resposta.tipo_nota == "nps", Resposta.nota.is_not(None),
                       Resposta.arquivada.is_(False), Resposta.data_resposta >= janela_notas)):
            notas[e_id].append((quando.astimezone(relogio.FUSO).date(), nota))
        acoes = defaultdict(list)
        for e_id, quando in s.execute(select(Acao.empresa_id, Acao.criada_em)
                                      .where(Acao.empresa_id.in_(ids), Acao.criada_em >= janela_notas)):
            acoes[e_id].append(quando.astimezone(relogio.FUSO).date())

    # ---- perdidas no período (e ainda perdidas no fim) -----------------------------------
    perdidas = []
    for e_id, linhas in historico.items():
        estado_fim = _estado(linhas, fim, inclusive=True)
        if not estado_fim or estado_fim[0] != "perdida":
            continue
        perda = next(x for x in reversed(linhas) if x.tipo == "perdida" and x.data <= fim)
        if perda.data < inicio:
            continue
        e = empresas[e_id]
        grupo, ultima = _grupo_antes(notas[e_id], perda.data)
        perdidas.append({
            "empresa": {"id": e.id, "nome": e.nome}, "perdida_em": perda.data, "motivo": perda.motivo,
            "motivo_rotulo": MOTIVOS.get(perda.motivo), "motivo_detalhe": perda.motivo_detalhe,
            "valor_mensal": perda.valor_antes, "responsavel": e.responsavel, "antes": grupo, "ultima_nota": ultima,
            "plano_antes": any(perda.data - timedelta(days=JANELA_ANTES - 1) <= d <= perda.data for d in acoes[e_id]),
        })
    perdidas.sort(key=lambda p: (p["perdida_em"], p["empresa"]["id"]), reverse=True)

    motivos = []
    for chave, rotulo in MOTIVOS.items():
        doms = [p for p in perdidas if p["motivo"] == chave]
        motivos.append({"motivo": chave, "rotulo": rotulo, "empresas": len(doms),
                        "receita_mensal": sum((p["valor_mensal"] or ZERO for p in doms), ZERO)})

    # ---- o que diziam antes de sair × a carteira ativa ------------------------------------
    cont_perdidas = defaultdict(int)
    for p in perdidas:
        cont_perdidas[p["antes"]] += 1
    carteira = [e for e in empresas.values() if e.ativa]  # perdida é sempre inativa
    cont_carteira = defaultdict(int)
    ativos = 0
    for e in carteira:
        estado = _estado(historico.get(e.id, []), fim, inclusive=True)
        if estado and estado[0] == "perdida":
            continue
        ativos += 1
        cont_carteira[_grupo_antes(notas[e.id], fim)[0]] += 1

    # ---- retenção da receita (GRR e NRR) --------------------------------------------------
    retencao = None
    if historico:
        receita = perdida = reducao = aumento = ZERO
        n_inicio = sem_valor = 0
        novas_n, novas_receita = 0, ZERO
        for linhas in historico.values():
            antes = _estado(linhas, inicio, inclusive=False)
            depois = _estado(linhas, fim, inclusive=True)
            if antes and antes[0] == "cliente":
                if not antes[1]:
                    sem_valor += 1
                    continue
                n_inicio += 1
                receita += antes[1]
                if depois and depois[0] == "perdida":
                    perdida += antes[1]
                else:
                    delta = (depois[1] - antes[1]) if depois and depois[1] is not None else ZERO
                    reducao += max(ZERO, -delta)
                    aumento += max(ZERO, delta)
            elif depois and depois[0] == "cliente" and depois[1] and any(
                    x.tipo in ("entrada", "reativada") and inicio <= x.data <= fim for x in linhas):
                novas_n += 1
                novas_receita += depois[1]
        retencao = {
            "inicio": {"data": inicio, "empresas": n_inicio, "receita": receita, "sem_valor": sem_valor},
            "perdida": perdida, "reducao": reducao, "aumento": aumento,
            "fim": receita - perdida - reducao + aumento,
            "novas": {"empresas": novas_n, "receita": novas_receita},
            "grr": _pct(receita - perdida - reducao, receita),
            "nrr": _pct(receita - perdida - reducao + aumento, receita),
            "historico_parcial": bool(migracao and inicio < migracao.date()),
        }

    return {
        "periodo": {"de": inicio, "ate": fim},
        "perdidas": {"empresas": len(perdidas),
                     "receita_mensal": sum((p["valor_mensal"] or ZERO for p in perdidas), ZERO),
                     "sem_valor": sum(1 for p in perdidas if not p["valor_mensal"]),
                     "itens": perdidas[:MAX_ITENS]},
        "motivos": motivos,
        "antes_de_sair": {"perdidas": _bloco(cont_perdidas, len(perdidas)), "carteira": _bloco(cont_carteira, ativos),
                          "amostra_pequena": len(perdidas) < AMOSTRA_PEQUENA},
        "retencao": retencao,
    }


def _filtro(f):
    from toqqi.modulos.relatorios.servico import _filtro_empresas

    filtro = _filtro_empresas(f)
    filtro.so_ativos = False
    return filtro
