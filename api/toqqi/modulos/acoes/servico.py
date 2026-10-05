"""Planos de ação: quadro A fazer → Em andamento → Concluído, lista, criação, edição (mover e concluir),
exclusão e configuração dos prazos das ações automáticas. Etapa 5d: a ação manual criada a partir de uma resposta pode
ficar com os passos da IA pendentes (`acoes.passos`); editar ou mover a ação não mexe nos passos."""
from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.filtros import entre_datas
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Acao, Contato, Empresa, Responsavel, Resposta, Usuario
from toqqi.modulos.acoes import passos
from toqqi.modulos.acoes.configuracao import config_json, obter
from toqqi.modulos.acoes.regras import ABERTAS, ordem_urgencia, peso_prioridade, prazo_selo, vencida
from toqqi.modulos.empresas.servico import conferir_referencias, ref

MAX_POR_COLUNA = 300
CONCLUIDAS_NO_QUADRO = 15
REFERENCIAS = {
    "empresa_id": (Empresa, "Empresa não encontrada."),
    "contato_id": (Contato, "Contato não encontrado."),
    "resposta_id": (Resposta, "Resposta não encontrada."),
    "responsavel_id": (Responsavel, "Responsável não encontrado."),
}
MSG_CONCLUIR = "Para concluir a ação, escolha o responsável e conte o que foi feito."


# ---- consulta e formato -----------------------------------------------------

def _juntar(consulta):
    return (consulta.outerjoin(Empresa, Empresa.id == Acao.empresa_id)
            .outerjoin(Contato, Contato.id == Acao.contato_id))


def _consulta():
    criador, concluiu = aliased(Usuario, name="criador"), aliased(Usuario, name="concluiu")
    consulta = select(
        Acao, Empresa.nome.label("empresa_nome"), Contato.nome.label("contato_nome"),
        Responsavel.nome.label("responsavel_nome"), Responsavel.email.label("responsavel_email"),
        Responsavel.foto_url.label("responsavel_foto"),
        Resposta.nota.label("r_nota"), Resposta.tipo_nota.label("r_tipo_nota"), Resposta.grupo.label("r_grupo"),
        Resposta.comentario.label("r_comentario"), Resposta.data_resposta.label("r_data"),
        criador.nome.label("criador_nome"), concluiu.nome.label("concluiu_nome"),
    ).select_from(Acao)
    return (_juntar(consulta)
            .outerjoin(Responsavel, Responsavel.id == Acao.responsavel_id)
            .outerjoin(Resposta, Resposta.id == Acao.resposta_id)
            .outerjoin(criador, criador.id == Acao.criado_por)
            .outerjoin(concluiu, concluiu.id == Acao.concluida_por))


def acao_json(x, hoje) -> dict:
    a: Acao = x.Acao
    return {
        "id": a.id, "titulo": a.titulo, "descricao": a.descricao, "resolucao": a.resolucao, "situacao": a.situacao,
        "prioridade": a.prioridade, "prazo": a.prazo, "prazo_selo": prazo_selo(a.situacao, a.prazo, hoje),
        "empresa": ref(a.empresa_id, x.empresa_nome), "contato": ref(a.contato_id, x.contato_nome),
        "responsavel": ({"id": a.responsavel_id, "nome": x.responsavel_nome, "email": x.responsavel_email,
                         "foto_url": x.responsavel_foto} if a.responsavel_id else None),
        "resposta": ({"id": a.resposta_id, "nota": x.r_nota, "tipo_nota": x.r_tipo_nota, "grupo": x.r_grupo,
                      "comentario": x.r_comentario, "data": x.r_data} if a.resposta_id else None),
        "origem": a.origem, "grupo": a.grupo, "tipo_nota": a.tipo_nota, "nota": a.nota,
        "criada_em": a.criada_em, "atualizada_em": a.atualizada_em, "iniciada_em": a.iniciada_em,
        "concluida_em": a.concluida_em, "criado_por": ref(a.criado_por, x.criador_nome),
        "concluida_por": ref(a.concluida_por, x.concluiu_nome),
        # etapa 5d: passos sugeridos pela IA (lista só com 'pronta'; situação nula = a ação não passa pela IA)
        "ia_passos": a.ia_passos, "ia_passos_situacao": a.ia_passos_situacao,
        # melhoria 4: retorno ao cliente
        "retorno_em": a.retorno_em, "retorno_texto": a.retorno_texto,
    }


def _uma(s: Session, acao_id: int) -> dict:
    # populate_existing: relê do banco o que acabou de mudar (datas no mesmo formato das listas)
    x = s.execute(_consulta().where(Acao.id == acao_id).execution_options(populate_existing=True)).one_or_none()
    if x is None:
        raise nao_encontrado("Ação não encontrada.")
    return acao_json(x, relogio.hoje())


def _acao(s: Session, acao_id: int, travar: bool = False) -> Acao:
    a = s.get(Acao, acao_id, with_for_update=travar)
    if a is None:
        raise nao_encontrado("Ação não encontrada.")
    return a


def condicoes(f, hoje) -> list:
    """Filtros comuns do quadro e da lista (pedem a junção de empresa e contato)."""
    conds = []
    if f.busca and f.busca.strip():
        termo = f"%{f.busca.strip()}%"
        conds.append(or_(Acao.titulo.ilike(termo), cast(Empresa.nome, String).ilike(termo),
                         Contato.nome.ilike(termo)))
    if f.categoria:
        conds.append(Acao.grupo == f.categoria)
    if f.tipo_nota:
        conds.append(Acao.tipo_nota == f.tipo_nota)
    if f.responsavel_id is not None:
        conds.append(Acao.responsavel_id.is_(None) if f.responsavel_id == 0
                     else Acao.responsavel_id == f.responsavel_id)
    if f.empresa_id is not None:
        conds.append(Acao.empresa_id == f.empresa_id)
    if f.grupo_id is not None:
        conds.append(Empresa.grupo_id == f.grupo_id)
    conds += entre_datas(Acao.criada_em, f.de, f.ate)
    if f.so_vencidas:
        conds.append(vencida(hoje))
    return conds


# ---- quadro e lista ---------------------------------------------------------

def quadro(ctx: Contexto, f) -> dict:
    hoje = relogio.hoje()
    conds = [Acao.conta_id == ctx.conta_id, *condicoes(f, hoje)]
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        colunas = {}
        for situacao in ABERTAS:
            linhas = s.execute(_consulta().where(*conds, Acao.situacao == situacao)
                               .order_by(*ordem_urgencia(hoje)).limit(MAX_POR_COLUNA)).all()
            colunas[situacao] = [acao_json(x, hoje) for x in linhas]
        linhas = s.execute(_consulta().where(*conds, Acao.situacao == "concluida")
                           .order_by(Acao.concluida_em.desc().nulls_last(), Acao.id.desc())
                           .limit(CONCLUIDAS_NO_QUADRO)).all()
        colunas["concluida"] = [acao_json(x, hoje) for x in linhas]
        totais = s.execute(_juntar(select(
            func.count().filter(Acao.situacao == "a_fazer").label("a_fazer"),
            func.count().filter(Acao.situacao == "em_andamento").label("em_andamento"),
            func.count().filter(Acao.situacao == "concluida").label("concluida"),
            func.count().filter(vencida(hoje)).label("vencidas"),
        ).select_from(Acao)).where(*conds)).one()
    return {"colunas": colunas, "totais": totais._asdict()}


def _ordem_lista(f, hoje) -> list:
    if f.situacao == "concluida":
        return [Acao.concluida_em.desc().nulls_last(), Acao.id.desc()]
    if f.situacao in ABERTAS:
        return ordem_urgencia(hoje)
    concluida = Acao.situacao == "concluida"
    # abertas primeiro (por urgência), depois as concluídas (mais recentes primeiro)
    return [case((concluida, 1), else_=0), case((and_(~concluida, Acao.prazo < hoje), 0), else_=1),
            case((concluida, None), else_=Acao.prazo).asc().nulls_last(), Acao.concluida_em.desc().nulls_last(),
            peso_prioridade(), Acao.criada_em.asc(), Acao.id.asc()]


def listar(ctx: Contexto, f, pg: Pagina) -> dict:
    hoje = relogio.hoje()
    conds = [Acao.conta_id == ctx.conta_id, *condicoes(f, hoje)]
    if f.situacao:
        conds.append(Acao.situacao == f.situacao)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        total = s.scalar(_juntar(select(func.count()).select_from(Acao)).where(*conds))
        linhas = s.execute(_consulta().where(*conds).order_by(*_ordem_lista(f, hoje))
                           .limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([acao_json(x, hoje) for x in linhas], total)


def obter_acao(ctx: Contexto, acao_id: int) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _uma(s, acao_id)


# ---- criar, alterar, excluir ------------------------------------------------

def criar(ctx: Contexto, dados) -> dict:
    """Ação manual. Sem empresa: a da resposta (ou a do contato); com empresa e sem responsável: o da empresa."""
    valores = dados.model_dump()
    with em_conta(ctx.conta_id) as s:
        conferir_referencias(s, valores, REFERENCIAS)
        resposta = s.get(Resposta, dados.resposta_id) if dados.resposta_id else None
        contato_id = dados.contato_id or (resposta.contato_id if resposta else None)
        contato = s.get(Contato, contato_id) if contato_id else None
        empresa_id = (dados.empresa_id or (resposta.empresa_id if resposta else None)
                      or (contato.empresa_id if contato else None))
        responsavel_id = dados.responsavel_id
        if responsavel_id is None and empresa_id is not None:
            responsavel_id = s.get(Empresa, empresa_id).responsavel_id
        agora = relogio.agora()
        a = Acao(titulo=dados.titulo, descricao=dados.descricao or "", empresa_id=empresa_id, contato_id=contato_id,
                 resposta_id=dados.resposta_id, responsavel_id=responsavel_id, prioridade=dados.prioridade,
                 prazo=dados.prazo, situacao="a_fazer", origem="manual",
                 grupo=resposta.grupo if resposta else None, tipo_nota=resposta.tipo_nota if resposta else None,
                 nota=resposta.nota if resposta else None, criado_por=ctx.usuario_id, criada_em=agora,
                 atualizada_em=agora)
        s.add(a)
        s.flush()
        passos.marcar(s, ctx.conta_id, a, resposta)  # quem chama usa coletar_passos() e agenda depois do commit
        return _uma(s, a.id)


def _conferir_conclusao(a: Acao) -> None:
    campos = {}
    if a.responsavel_id is None:
        campos["responsavel_id"] = "Escolha o responsável antes de concluir."
    if not (a.resolucao or "").strip():
        campos["resolucao"] = "Conte o que foi feito para concluir."
    if campos:
        raise AppError(422, "dados_invalidos", MSG_CONCLUIR, campos)


def alterar(ctx: Contexto, acao_id: int, dados) -> dict:
    valores = {c: getattr(dados, c) for c in dados.model_fields_set}
    for campo in ("titulo", "prioridade", "situacao"):  # obrigatórios: null não muda
        if campo in valores and valores[campo] is None:
            del valores[campo]
    if "descricao" in valores:
        valores["descricao"] = valores["descricao"] or ""
    with em_conta(ctx.conta_id) as s:
        a = _acao(s, acao_id, travar=True)
        conferir_referencias(s, valores, {c: REFERENCIAS[c] for c in ("empresa_id", "responsavel_id")})
        antes = a.situacao
        for campo, valor in valores.items():
            setattr(a, campo, valor)
        # concluir exige responsável e o que foi feito (também ao mexer nesses campos de uma já concluída)
        if a.situacao == "concluida" and (antes != "concluida" or {"responsavel_id", "resolucao"} & valores.keys()):
            _conferir_conclusao(a)
        agora = relogio.agora()
        if a.situacao != antes:
            if a.situacao == "concluida":
                a.concluida_em, a.concluida_por = agora, ctx.usuario_id
            else:
                a.concluida_em, a.concluida_por = None, None
            if a.situacao == "em_andamento" and a.iniciada_em is None:
                a.iniciada_em = agora
        a.atualizada_em = agora
        s.flush()
        return _uma(s, a.id)


def excluir(ctx: Contexto, acao_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        a = _acao(s, acao_id)
        registrar(s, "acao_excluida", "atencao", {"acao_id": a.id, "titulo": a.titulo}, usuario_id=ctx.usuario_id)
        s.delete(a)


# ---- configuração -----------------------------------------------------------

def ver_config(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return config_json(obter(s))


def salvar_config(ctx: Contexto, dados) -> dict:
    novos = {c: getattr(dados, c) for c in dados.model_fields_set if getattr(dados, c) is not None}
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s, travar=True)
        antes = config_json(cfg)
        for campo, valor in novos.items():
            setattr(cfg, campo, valor)
        cfg.atualizado_em = relogio.agora()
        s.flush()
        depois = config_json(cfg)
        mudou = sorted(c for c in depois if depois[c] != antes[c])
        if mudou:
            registrar(s, "config_acoes", "info", {"campos": mudou}, usuario_id=ctx.usuario_id)
        return depois


# ---- melhoria 4: retorno ao cliente ("você falou, nós fizemos") ------------------------------------

def enviar_retorno(ctx: Contexto, acao_id: int, texto: str) -> tuple[dict, list]:
    """Manda ao contato da ação concluída o texto escrito por quem tratou (uma vez por ação). Devolve a ação e os
    envios a processar depois do commit."""
    from toqqi.modulos.envios.descadastro import esta_descadastrado
    from toqqi.modulos.envios.processamento import novo_envio

    texto = (texto or "").strip()
    if len(texto) < 10:
        raise AppError(422, "dados_invalidos", "Confira os campos destacados.",
                       {"texto": "Escreva o que foi feito (pelo menos uma frase)."})
    with em_conta(ctx.conta_id) as s:
        a = _acao(s, acao_id, travar=True)
        if a.situacao != "concluida":
            raise AppError(409, "nao_concluida", "Conclua o plano de ação antes de avisar o cliente.")
        if a.retorno_em:
            raise AppError(409, "ja_enviado", "O cliente já foi avisado sobre este plano de ação.")
        contato = s.get(Contato, a.contato_id) if a.contato_id else None
        if contato is None or not contato.email:
            raise AppError(409, "sem_email", "O contato deste plano de ação não tem e-mail.")
        if not contato.recebe_pesquisas or esta_descadastrado(s, contato.email, contato.telefone):
            raise AppError(409, "descadastrado", "O contato saiu da lista e não recebe e-mails da sua empresa.")
        a.retorno_texto, a.retorno_em = texto, relogio.agora()
        e = novo_envio(s, contato, "retorno", "manual", acao_id=a.id, usuario_id=ctx.usuario_id)
        registrar(s, "envio_retorno", "info", {"acao": a.id, "contato": contato.id}, usuario_id=ctx.usuario_id)
        s.flush()
        return _uma(s, a.id), [(e.conta_id, e.id)]
