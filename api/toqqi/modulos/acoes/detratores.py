"""Planos para os detratores sem plano (etapa 5h, §2): `POST /acoes/detratores`.

Com os filtros do painel (período, grupo, só ativas): para cada empresa (ou contato sem empresa) com resposta NPS de
detrator no filtro e sem ação aberta (a fazer ou em andamento), uma ação a partir da resposta de detrator mais recente,
com o título, a prioridade, o prazo, o responsável e a descrição da ação automática (`automatica.montar_acao`),
origem `manual` e `criado_por` = quem pediu; os passos da IA como em qualquer ação de uma resposta (`passos.marcar`;
quem chama usa `coletar_passos()` e agenda depois do commit). Sem o "Alerta de risco" por e-mail (são respostas que já
estavam lá, não uma resposta nova). Até 100 por chamada, das mais urgentes (`painel.alvos_sem_plano`: menor nota,
depois a mais recente); devolve {criadas, restantes}. Uma transação só, uma chamada por vez na conta (duas ao mesmo
tempo criariam a mesma ação duas vezes). Auditoria `acoes_detratores_criadas` com o número, quando cria alguma.
"""
from datetime import date

from sqlalchemy import select

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, sem_jit, travar
from toqqi.core.deps import Contexto
from toqqi.modelos import Resposta
from toqqi.modulos.acoes import passos
from toqqi.modulos.acoes.automatica import montar_acao
from toqqi.modulos.acoes.configuracao import obter
from toqqi.modulos.painel.servico import Filtro, _validar_periodo, alvos_sem_plano

MAX_POR_CHAMADA = 100


def criar(ctx: Contexto, de: date | None, ate: date | None, grupo_id: int | None, so_ativos: bool) -> dict:
    _validar_periodo(de, ate)
    f = Filtro(ctx.conta_id, de, ate, grupo_id, so_ativos)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        travar(s, f"acoes_detratores:{ctx.conta_id}")
        ids = s.scalars(alvos_sem_plano(f)).all()
        escolhidas = ids[:MAX_POR_CHAMADA]
        respostas = {r.id: r for r in s.scalars(select(Resposta).where(Resposta.id.in_(escolhidas)))}
        cfg = obter(s, criar=False)
        criadas = 0
        for resposta_id in escolhidas:  # na ordem de urgência
            r = respostas[resposta_id]
            montada = montar_acao(s, r, cfg, origem="manual", criado_por=ctx.usuario_id)
            if montada is None:  # detrator de NPS sempre pede ação; só por garantia
                continue
            s.add(montada.acao)
            s.flush()
            passos.marcar(s, ctx.conta_id, montada.acao, r)
            criadas += 1
        if criadas:
            registrar(s, "acoes_detratores_criadas", "info", {"criadas": criadas}, usuario_id=ctx.usuario_id)
        return {"criadas": criadas, "restantes": len(ids) - len(escolhidas)}
