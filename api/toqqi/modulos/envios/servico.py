"""Envios: configuração, fila, disparo manual, histórico, WhatsApp e execução manual das tarefas."""
from datetime import datetime, time, timedelta

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import aliased

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.email import FalhaEnvio, enviar_mensagem
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Conta, Contato, Empresa, Envio, Formulario, Usuario
from toqqi.modulos.contatos.servico import formulario_para_envio
from toqqi.modulos.envios import automacao, mensagens
from toqqi.modulos.envios.configuracao import (
    CAMPOS,
    DIAS_LEMBRETES_PADRAO,
    config_json,
    erro_pre_condicao,
    exigir,
    formulario_ok,
    obter,
    pre_condicoes,
)
from toqqi.modulos.envios.descadastro import esta_descadastrado
from toqqi.modulos.envios.esquemas import FiltrosFila
from toqqi.modulos.envios.fila import consulta_fila, contato_envio_json, descadastrado, filtrar, ordem
from toqqi.modulos.envios.processamento import criar_convite_email, marcar_convite_enviado, novo_envio
from toqqi.modulos.respostas.convites import link_do_convite, novo_convite

Pares = list[tuple[int, int]]
MAX_IGNORADOS = 500
ANULAVEIS = {"responder_para", "remetente_nome"}


# ---- configuração -----------------------------------------------------------

def ver_pre_condicoes(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return pre_condicoes(s, obter(s, criar=False))


def ver_config(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return config_json(obter(s))


def _validar(s, v: dict) -> None:
    campos: dict[str, str] = {}
    if v["janela_fim"] <= v["janela_inicio"]:
        campos["janela_fim"] = "O fim da janela precisa ser depois do início."
    dias = v["dias_lembretes"]
    if len(dias) != v["lembretes"]:
        campos["dias_lembretes"] = "Informe um prazo para cada lembrete."
    elif any(b <= a for a, b in zip(dias, dias[1:])):
        campos["dias_lembretes"] = "Os prazos precisam ser crescentes, como 3, 7 e 15."
    if "{link}" not in v["texto_whatsapp"]:
        campos["texto_whatsapp"] = "Inclua {link} no texto: é ali que entra o link da pesquisa."
    f = s.get(Formulario, v["formulario_id"]) if v["formulario_id"] else None
    if f is None or not f.ativo or f.arquivado:
        campos["formulario_id"] = "Escolha um formulário ativo da conta."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira os campos destacados.", campos)


def salvar_config(ctx: Contexto, dados) -> dict:
    novos = {c: getattr(dados, c) for c in dados.model_fields_set
             if getattr(dados, c) is not None or c in ANULAVEIS}
    if "agradecimento" in novos:
        novos["agradecimento"] = dados.agradecimento.model_dump()
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s, travar=True)
        v = {c: getattr(cfg, c) for c in CAMPOS} | novos
        if "lembretes" in novos and "dias_lembretes" not in novos and len(v["dias_lembretes"]) != v["lembretes"]:
            atuais = list(cfg.dias_lembretes)
            v["dias_lembretes"] = (atuais if len(atuais) >= v["lembretes"] else DIAS_LEMBRETES_PADRAO)[: v["lembretes"]]
        _validar(s, v)
        antes = config_json(cfg)
        for c, valor in v.items():
            setattr(cfg, c, valor)
        cfg.atualizado_em = relogio.agora()
        s.flush()
        depois = config_json(cfg)
        mudou = sorted(c for c in depois if depois[c] != antes[c])
        if mudou:
            registrar(s, "config_envios", "info", {"campos": mudou}, usuario_id=ctx.usuario_id)
        return depois


def enviar_teste(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s)
        exigir(s, cfg, ("provedor", "formulario"))
        f = s.get(Formulario, cfg.formulario_id)
        empresa = s.scalar(select(Conta.nome))
        m = mensagens.email_pesquisa(
            conta_id=ctx.conta_id, para=ctx.email, empresa=empresa, assunto=cfg.assunto_convite,
            texto=cfg.texto_convite, perguntas=f.perguntas, link=mensagens.link_formulario_publico(f.codigo_publico),
            v=mensagens.variaveis(empresa, ctx.usuario.get("nome")), remetente_nome=cfg.remetente_nome,
            responder_para=cfg.responder_para)
    try:
        enviar_mensagem(m)
    except FalhaEnvio as falha:
        raise AppError(409, "falha_envio", falha.mensagem)
    return {"mensagem": f"Enviamos um exemplo para {ctx.email}."}


# ---- fila -------------------------------------------------------------------

def resumo(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s, criar=False)
        hoje = relogio.hoje()
        q = consulta_fila(cfg, hoje)

        def ativos(*cond):
            return func.count().filter(q.c.ativo.is_(True), *cond)

        linha = s.execute(select(
            ativos(q.c.situacao == "na_fila").label("na_fila"),
            ativos(q.c.situacao == "aguardando").label("aguardando"),
            ativos(q.c.situacao == "respondeu").label("responderam"),
            ativos(q.c.situacao == "nao_saiu").label("com_erro"),
            func.count().filter(q.c.saiu.is_(True)).label("saiu_da_lista"),
            ativos(q.c.proximo_lembrete == hoje).label("lembretes_hoje"),
        ).select_from(q)).one()
        enviados = s.scalar(select(func.count()).select_from(Envio).where(
            Envio.situacao.in_(("enviado", "aberto_no_whatsapp")),
            func.coalesce(Envio.enviado_em, Envio.criado_em) >= relogio.agora() - timedelta(days=30)))
    return {**linha._asdict(), "enviados_30d": enviados}


def listar_contatos(ctx: Contexto, filtros: FiltrosFila, pg: Pagina) -> dict:
    with em_conta(ctx.conta_id) as s:
        hoje = relogio.hoje()
        q = consulta_fila(obter(s, criar=False), hoje)
        conds = filtrar(q, filtros, hoje)
        total = s.scalar(select(func.count()).select_from(q).where(*conds))
        linhas = s.execute(select(q).where(*conds).order_by(*ordem(q)).limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([contato_envio_json(x) for x in linhas], total)


def _motivo(linha, cfg, hoje, ignorar_descanso: bool) -> str | None:
    if not linha.ativo:
        return "Contato inativo"
    if linha.saiu:
        return "Saiu da lista"
    if not linha.email:
        return "Sem e-mail"
    if linha.situacao == "enviando":
        return "Já está sendo enviado"
    if linha.descanso_ate and not ignorar_descanso:
        dias = (hoje - linha.ultimo_envio.astimezone(relogio.FUSO).date()).days
        quando = "hoje" if dias == 0 else "há 1 dia" if dias == 1 else f"há {dias} dias"
        return f"Recebeu uma pesquisa {quando} (descanso de {cfg.descanso_dias} dias)"
    return None


def disparar(ctx: Contexto, dados) -> tuple[dict, Pares]:
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s)
        exigir(s, cfg)
        hoje = relogio.hoje()
        q = consulta_fila(cfg, hoje)
        if dados.contato_ids:
            ids = list(dict.fromkeys(dados.contato_ids))
            achados = {x.id: x for x in s.execute(select(q).where(q.c.id.in_(ids)))}
            linhas = [achados[i] for i in ids if i in achados]
        else:
            f = dados.filtros or FiltrosFila()
            if f.situacao is None:
                f = f.model_copy(update={"situacao": "na_fila"})
            linhas = s.execute(select(q).where(*filtrar(q, f, hoje)).order_by(*ordem(q))).all()
        envios: Pares = []
        ignorados = []
        for linha in linhas:
            motivo = _motivo(linha, cfg, hoje, dados.ignorar_descanso)
            if motivo:
                ignorados.append({"contato_id": linha.id, "nome": linha.nome, "motivo": motivo})
                continue
            e = criar_convite_email(s, cfg, s.get(Contato, linha.id), "manual", ctx.usuario_id)
            envios.append((ctx.conta_id, e.id))
        if envios:
            registrar(s, "envio_manual", "info", {"quantidade": len(envios), "ignorados": len(ignorados)},
                      usuario_id=ctx.usuario_id)
    return {"agendados": len(envios), "ignorados": ignorados[:MAX_IGNORADOS]}, envios


def _pode_receber(s, c: Contato) -> bool:
    return c.ativo and c.recebe_pesquisas and bool(c.email) and not esta_descadastrado(s, c.email)


def tentar_de_novo(ctx: Contexto, envio_id: int) -> tuple[dict, Pares]:
    with em_conta(ctx.conta_id) as s:
        e = s.get(Envio, envio_id)
        if e is None:
            raise nao_encontrado("Envio não encontrado.")
        exigir(s, obter(s))
        mais_novo = s.scalar(select(exists().where(Envio.contato_id == e.contato_id, Envio.tipo == e.tipo,
                                                   Envio.id > e.id)))
        if e.situacao != "erro" or e.canal != "email" or e.contato_id is None or mais_novo:
            raise AppError(409, "nao_pode_tentar", "Só dá para tentar de novo o erro mais recente do contato.")
        contato = s.get(Contato, e.contato_id)
        if not _pode_receber(s, contato):
            raise AppError(409, "nao_pode_receber",
                           "Este contato não pode receber pesquisas agora (inativo, sem e-mail ou fora da lista).")
        novo = novo_envio(s, contato, e.tipo, "manual", convite_id=e.convite_id, resposta_id=e.resposta_id,
                          lembrete=e.lembrete, usuario_id=ctx.usuario_id)
        return {"mensagem": "Estamos tentando enviar de novo."}, [(ctx.conta_id, novo.id)]


# ---- histórico --------------------------------------------------------------

def _envio_json(e: Envio, contato_nome, usuario_nome, pode: bool) -> dict:
    return {
        "id": e.id, "criado_em": e.criado_em,
        "contato": {"id": e.contato_id, "nome": contato_nome} if e.contato_id else None,
        "para": e.para, "canal": e.canal, "tipo": e.tipo, "origem": e.origem, "situacao": e.situacao,
        "erro": e.erro, "usuario": {"id": e.usuario_id, "nome": usuario_nome} if e.usuario_id else None,
        "pode_tentar_de_novo": bool(pode),
    }


def historico(ctx: Contexto, f, pg: Pagina) -> dict:
    novo = aliased(Envio)
    mais_novo = exists().where(novo.contato_id == Envio.contato_id, novo.tipo == Envio.tipo, novo.id > Envio.id)
    pode = and_(Envio.situacao == "erro", Envio.canal == "email", Contato.id.is_not(None),
                Contato.ativo.is_(True), Contato.recebe_pesquisas.is_(True), Contato.email.is_not(None),
                not_(descadastrado(Contato.email)), not_(mais_novo))
    base = (select(Envio, Contato.nome, Usuario.nome, pode)
            .outerjoin(Contato, Contato.id == Envio.contato_id)
            .outerjoin(Usuario, Usuario.id == Envio.usuario_id))
    conds = []
    if f.de:
        conds.append(Envio.criado_em >= datetime.combine(f.de, time.min, tzinfo=relogio.FUSO))
    if f.ate:
        conds.append(Envio.criado_em < datetime.combine(f.ate + timedelta(days=1), time.min, tzinfo=relogio.FUSO))
    for campo in ("tipo", "canal", "situacao", "contato_id"):
        if getattr(f, campo):
            conds.append(getattr(Envio, campo) == getattr(f, campo))
    if f.busca:
        termo = f"%{f.busca.strip()}%"
        conds.append(or_(Envio.para.ilike(termo), Contato.nome.ilike(termo)))
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(select(func.count()).select_from(base.where(*conds).subquery()))
        linhas = s.execute(base.where(*conds).order_by(Envio.criado_em.desc(), Envio.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([_envio_json(*x) for x in linhas], total)


# ---- WhatsApp ---------------------------------------------------------------

def whatsapp(ctx: Contexto, contato_id: int, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = s.get(Contato, contato_id)
        if c is None:
            raise nao_encontrado("Contato não encontrado.")
        cfg = obter(s)
        exigir(s, cfg, ("assinatura",))
        if not c.telefone:
            msg = "Este contato não tem telefone."
            raise AppError(422, "dados_invalidos", msg, {"telefone": msg})
        if not c.ativo:
            raise AppError(409, "contato_inativo", "Este contato está inativo.")
        if not c.recebe_pesquisas or esta_descadastrado(s, c.email):
            raise AppError(409, "saiu_da_lista", "Este contato saiu da lista e não recebe mais pesquisas.")
        if dados.formulario_id is None and formulario_ok(s, cfg):
            f = s.get(Formulario, cfg.formulario_id)
        else:
            f = formulario_para_envio(s, dados.formulario_id)
        agora = relogio.agora()
        convite, token = novo_convite(s, f.id, contato_id=c.id, canal="whatsapp", empresa_id=c.empresa_id,
                                      criado_em=agora)
        link = link_do_convite(token)
        empresa = s.scalar(select(Conta.nome))
        empresa_cliente = s.scalar(select(Empresa.nome).where(Empresa.id == c.empresa_id))
        url, mensagem = mensagens.whatsapp(c.telefone, cfg.texto_whatsapp,
                                           mensagens.variaveis(empresa, c.nome, empresa_cliente, link))
        s.add(Envio(contato_id=c.id, convite_id=convite.id, canal="whatsapp", tipo="convite", origem="manual",
                    situacao="aberto_no_whatsapp", para=c.telefone, usuario_id=ctx.usuario_id,
                    criado_em=agora, enviado_em=agora))
        marcar_convite_enviado(cfg, c)
    return {"url": url, "mensagem": mensagem, "link": link}


# ---- lembretes e robô (execução manual) -------------------------------------

def _exigir_admin(ctx: Contexto) -> None:
    if ctx.perfil != "admin":
        raise AppError(403, "sem_permissao", "Só o administrador da conta pode fazer isso.")


def previa_lembretes(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return automacao.previa_lembretes(s)


def executar_lembretes(ctx: Contexto) -> tuple[dict, Pares]:
    _exigir_admin(ctx)
    with em_conta(ctx.conta_id) as s:
        exigir(s, obter(s))
    r = automacao.lembretes_conta(ctx.conta_id, forcar=True) or {"enviados": 0, "ignorados": 0, "envios": []}
    return {"enviados": r["enviados"], "ignorados": r["ignorados"]}, r["envios"]


def executar_robo(ctx: Contexto) -> tuple[dict, Pares]:
    _exigir_admin(ctx)
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s)
        exigir(s, cfg)
        if not cfg.envio_automatico:
            raise erro_pre_condicao("O envio automático está desligado. Ligue em Configurações de envio.")
    r = automacao.robo_conta(ctx.conta_id, forcar=True) or {"agendados": 0, "ignorados": 0, "envios": []}
    return {"agendados": r["agendados"], "ignorados": r["ignorados"]}, r["envios"]
