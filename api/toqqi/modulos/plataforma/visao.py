"""Plataforma › Visão geral (etapa 5h, docs/api-etapa-5h.md §5): GET /plataforma/visao, a visão do negócio para a
equipe Toqqi (superadmin), em modo sistema. Um número fixo de consultas agregadas por conta (GROUP BY), sem N+1: o
número de consultas não cresce com o de contas. Nada de nome, e-mail ou telefone de contatos: só contagens.

Forma (decisões desta etapa onde o contrato não diz):
- `gerado_em`.
- `totais`: {contas, por_situacao: {teste, teste_expirado, ativa, atrasada, pausada, cancelada, cortesia}, pagantes,
  receita_mensal, ambiente, novas_7d, novas_30d}. Cada conta conta numa situação só: `pausada` é a atrasada depois dos
  7 dias de carência (envios parados: o aviso `pausada` de `assinatura.regras`); `atrasada`, a que ainda está na
  carência. `pagantes` = contas com assinatura ativa no ambiente atual do Asaas (`assinaturas.filtro_ambiente()`: sem
  chave configurada, todas); `receita_mensal` = soma do `valor` delas (Decimal; sai como número, como o `valor` em
  GET /plataforma/contas); `ambiente` = sandbox | producao | null (sem chave).
- `conversao`: {de, ate, contas, assinaram, taxa}: das contas que tiveram teste (`teste_ate` preenchido; a cortesia
  criada pela Plataforma nunca teve) criadas entre 60 e 15 dias atrás (`de` e `ate`: os dias, em São Paulo), quantas
  criaram assinatura no ambiente atual (mesmo cancelada depois); `taxa` = assinaram ÷ contas (de 0 a 1, 4 casas), ou
  null sem contas no período.
- `testes_acabando`: contas em `teste` sem assinatura ativa (quem já assinou no teste não precisa de lembrete) com
  `teste_ate` nos próximos 7 dias, do fim mais próximo ao mais distante: {id, nome, email (do administrador mais
  antigo), teste_ate, dias (até o último dia do teste, como no aviso do topo; 0 = hoje), ultimo_acesso, ativacao}.
- `teste` (melhoria 9): das contas com teste criadas entre 90 e 14 dias atrás, quantas chegaram à primeira resposta de
  pesquisa (não contam as importadas nem as registradas à mão), quantas em até 7 e 14 dias, a mediana em dias e a
  conversão de quem chegou × quem não chegou.
- `contas`: todas, das mais novas às mais antigas: {id, nome, situacao (como em `por_situacao`), plano, criada_em,
  teste_ate, ultimo_acesso (a última entrada de algum usuário), usuarios, admin_email (o administrador mais antigo, para
  a busca), contatos_ativos, convites_30d, respostas_30d (gravadas nos últimos 30 dias, também as importadas: é o uso
  da conta), respostas_total, ativacao {contatos, envios_ligados, primeiro_envio, primeira_resposta} (os 4 passos de
  `painel.servico._primeiros_passos`), ia_analises_mes (o teto de segurança usado no mês) e assinatura ({plano, valor}
  da ativa no ambiente atual, ou null)}.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from toqqi.core import asaas, relogio
from toqqi.core.db import modo_sistema, sem_jit
from toqqi.modelos import Assinatura, ConfigEnvios, Conta, Contato, Convite, Envio, IaUsoMensal, Resposta, Usuario
from toqqi.modulos.assinatura import regras
from toqqi.modulos.assinatura import servico as assinaturas
from toqqi.modulos.painel.servico import SAIU_CONVITE

SITUACOES = ("teste", "teste_expirado", "ativa", "atrasada", "pausada", "cancelada", "cortesia")
DIAS_ACABANDO = 7
CONVERSAO_DE = 60  # dias atrás
CONVERSAO_ATE = 15


DIAS_ORIGEM = 90
TESTE_DE, TESTE_ATE = 90, 14  # melhoria 9: contas com teste criadas entre 90 e 14 dias atrás (tiveram 14 dias)


def situacao_exibida(c: Conta, agora: datetime) -> str:
    """A situação da conta, com `pausada` para a atrasada que passou da carência (envios parados)."""
    if c.situacao == "atrasada" and not regras.liberada(c, agora):
        return "pausada"
    return c.situacao


def _por_conta(s, consulta) -> dict:
    return {linha[0]: tuple(linha[1:]) for linha in s.execute(consulta)}


def visao() -> dict:
    agora = relogio.agora()
    hoje = regras.dia_de(agora)
    trinta = agora - timedelta(days=30)
    with modo_sistema() as s:
        sem_jit(s)
        contas = list(s.scalars(select(Conta).order_by(Conta.criada_em.desc(), Conta.id.desc())))
        usuarios = _por_conta(s, select(Usuario.conta_id, func.count(), func.max(Usuario.ultimo_acesso))
                              .group_by(Usuario.conta_id))
        admins = dict(s.execute(select(Usuario.conta_id, Usuario.email).where(Usuario.perfil == "admin")
                                .distinct(Usuario.conta_id).order_by(Usuario.conta_id, Usuario.id)).all())
        contatos = _por_conta(s, select(Contato.conta_id, func.count(), func.count().filter(Contato.ativo.is_(True)))
                              .group_by(Contato.conta_id))
        envios_ligados = set(s.scalars(select(ConfigEnvios.conta_id).where(ConfigEnvios.envios_ativos.is_(True))))
        primeiro_envio = set(s.scalars(select(Envio.conta_id).where(Envio.tipo == "convite",
                                                                    Envio.situacao.in_(SAIU_CONVITE)).distinct()))
        convites = dict(s.execute(select(Convite.conta_id, func.count()).where(Convite.criado_em >= trinta)
                                  .group_by(Convite.conta_id)).all())
        respostas = _por_conta(s, select(Resposta.conta_id, func.count(),
                                         func.count().filter(Resposta.criada_em >= trinta))
                               .group_by(Resposta.conta_id))
        ia = dict(s.execute(select(IaUsoMensal.conta_id, IaUsoMensal.analises)
                            .where(IaUsoMensal.mes == hoje.replace(day=1))).all())
        ativas = {a.conta_id: a for a in s.scalars(select(Assinatura).where(Assinatura.situacao == "ativa",
                                                                            assinaturas.filtro_ambiente()))}
        assinaram = set(s.scalars(select(Assinatura.conta_id).where(assinaturas.filtro_ambiente()).distinct()))
        # melhoria 9: a primeira resposta de cliente de verdade (pela pesquisa; não as importadas nem as registradas)
        primeira = dict(s.execute(select(Resposta.conta_id, func.min(Resposta.criada_em))
                                  .where(Resposta.origem == "pesquisa").group_by(Resposta.conta_id)).all())

    def ativacao(cid: int) -> dict:
        return {"contatos": contatos.get(cid, (0, 0))[0] > 0, "envios_ligados": cid in envios_ligados,
                "primeiro_envio": cid in primeiro_envio, "primeira_resposta": respostas.get(cid, (0, 0))[0] > 0}

    def rotulo_origem(c: Conta) -> str | None:
        o = c.origem or {}
        partes = [o[k] for k in ("utm_source", "utm_medium", "utm_campaign") if o.get(k)]
        return " · ".join(partes) or None

    def ultimo_acesso(cid: int):
        return usuarios.get(cid, (0, None))[1]

    por_situacao = dict.fromkeys(SITUACOES, 0)
    lista = []
    for c in contas:
        situacao = situacao_exibida(c, agora)
        por_situacao[situacao] = por_situacao.get(situacao, 0) + 1
        a = ativas.get(c.id)
        lista.append({
            "id": c.id, "nome": c.nome, "situacao": situacao, "plano": c.plano, "criada_em": c.criada_em,
            "teste_ate": c.teste_ate, "ultimo_acesso": ultimo_acesso(c.id), "usuarios": usuarios.get(c.id, (0,))[0],
            "admin_email": admins.get(c.id), "contatos_ativos": contatos.get(c.id, (0, 0))[1],
            "convites_30d": convites.get(c.id, 0), "respostas_30d": respostas.get(c.id, (0, 0))[1],
            "respostas_total": respostas.get(c.id, (0, 0))[0], "ativacao": ativacao(c.id),
            "ia_analises_mes": ia.get(c.id, 0), "origem": rotulo_origem(c),
            "assinatura": {"plano": a.plano, "valor": a.valor} if a is not None else None,
        })

    limite = agora + timedelta(days=DIAS_ACABANDO)
    acabando = sorted((c for c in contas if c.situacao == "teste" and c.id not in ativas
                       and c.teste_ate is not None and agora < c.teste_ate <= limite),
                      key=lambda c: (c.teste_ate, c.id))
    testes_acabando = [{
        "id": c.id, "nome": c.nome, "email": admins.get(c.id), "teste_ate": c.teste_ate,
        "dias": (regras.ultimo_dia_do_teste(c) - hoje).days, "ultimo_acesso": ultimo_acesso(c.id),
        "ativacao": ativacao(c.id),
    } for c in acabando]

    de, ate = agora - timedelta(days=CONVERSAO_DE), agora - timedelta(days=CONVERSAO_ATE)
    janela = [c for c in contas if c.teste_ate is not None and de <= c.criada_em < ate]
    convertidas = sum(1 for c in janela if c.id in assinaram)

    # melhoria 9: quanto tempo o teste leva até a primeira resposta (para decidir entre 7 dias, 14 ou "até responder")
    t_de, t_ate = agora - timedelta(days=TESTE_DE), agora - timedelta(days=TESTE_ATE)
    testes = [c for c in contas if c.teste_ate is not None and t_de <= c.criada_em < t_ate]
    dias = sorted((primeira[c.id] - c.criada_em).total_seconds() / 86400 for c in testes if c.id in primeira)
    com = [c for c in testes if c.id in primeira]
    sem = [c for c in testes if c.id not in primeira]

    def taxa(n: int, total: int) -> float | None:
        return round(n / total, 4) if total else None

    teste = {
        "de": regras.dia_de(t_de), "ate": regras.dia_de(t_ate), "contas": len(testes),
        "chegaram": len(dias), "ate_7_dias": sum(1 for d in dias if d <= 7), "ate_14_dias": sum(1 for d in dias if d <= 14),
        "mediana_dias": round(dias[len(dias) // 2] if len(dias) % 2 else (dias[len(dias) // 2 - 1] + dias[len(dias) // 2]) / 2, 1)
        if dias else None,
        "conversao_com_resposta": taxa(sum(1 for c in com if c.id in assinaram), len(com)),
        "conversao_sem_resposta": taxa(sum(1 for c in sem if c.id in assinaram), len(sem)),
    }

    # etapa 5i: cadastros por origem (utm gravado no cadastro) nos últimos DIAS_ORIGEM dias e quantos pagam hoje
    desde = agora - timedelta(days=DIAS_ORIGEM)
    grupos: dict[str | None, list[int]] = {}
    for c in contas:
        if c.criada_em >= desde:
            g = grupos.setdefault(rotulo_origem(c), [0, 0])
            g[0] += 1
            g[1] += c.id in ativas
    sem = grupos.pop(None, [0, 0])
    origens = {
        "dias": DIAS_ORIGEM,
        "itens": [{"rotulo": r, "cadastros": n, "pagantes": p}
                  for r, (n, p) in sorted(grupos.items(), key=lambda x: (-x[1][0], x[0]))],
        "sem_origem": {"cadastros": sem[0], "pagantes": sem[1]},
    }

    return {
        "gerado_em": agora,
        "origens": origens,
        "totais": {
            "contas": len(contas), "por_situacao": por_situacao, "pagantes": len(ativas),
            "receita_mensal": sum((a.valor for a in ativas.values()), Decimal("0.00")),
            "ambiente": asaas.ambiente(),
            "novas_7d": sum(1 for c in contas if c.criada_em >= agora - timedelta(days=7)),
            "novas_30d": sum(1 for c in contas if c.criada_em >= trinta),
        },
        "conversao": {"de": regras.dia_de(de), "ate": regras.dia_de(ate), "contas": len(janela),
                      "assinaram": convertidas, "taxa": round(convertidas / len(janela), 4) if janela else None},
        "testes_acabando": testes_acabando,
        "teste": teste,
        "contas": lista,
    }
