"""Feedback de quem usa o Toqqi (docs/api-feedback.md §3): enviar, acompanhar e conversar com a equipe Toqqi.

Rotas do usuário logado (qualquer perfil, inclusive com a conta em teste encerrado ou pagamento atrasado): cada um vê só
os próprios feedbacks (`usuario_id`), dentro da conta (RLS). As rotas da equipe ficam em `plataforma.py`.

Marcas de leitura: `ultima_do_usuario_em` (relato e mensagens dele) × `visto_pela_equipe_em` (a equipe abriu o
detalhe ou respondeu) dão o "precisa de atenção" da Plataforma; `ultima_da_equipe_em` (resposta ou mudança de
situação) × `visto_pelo_usuario_em` (o usuário abriu o detalhe ou escreveu) dão a "novidade" do usuário. Abrir o
detalhe (GET) marca como visto: a tela só pede quando a pessoa abre a conversa.

E-mails (`emails.py`, depois do commit): feedback novo → aos superadmins; mensagem nova do usuário → aos superadmins
só se a equipe já tinha visto tudo até ali (senão o aviso anterior ainda está pendente e um segundo seria ruído).
"""
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from toqqi.core.db import apos_commit, em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.modelos import Feedback, FeedbackImagem, FeedbackMensagem, Usuario
from toqqi.modulos.feedback import emails, regras
from toqqi.modulos.imagens.servico import dimensoes, nome_do_arquivo, tipo_da_imagem

MSG_NAO_ENCONTRADO = "Não encontramos esse feedback."
MSG_LIMITE_MENSAGENS = "Esta conversa chegou ao limite de mensagens. Envie um feedback novo."
MSG_LIMITE_IMAGENS = f"Esta conversa chegou ao limite de {regras.MAX_IMAGENS_FEEDBACK} imagens."
MAX_LISTA = 200


@dataclass(frozen=True)
class ImagemLida:
    dados: bytes
    tipo: str
    nome: str | None
    largura: int | None
    altura: int | None


# ---- imagens enviadas ----------------------------------------------------------------------------------------------

def ler_imagens(arquivos: list[UploadFile] | None) -> list[ImagemLida]:
    """As imagens de uma mensagem: até 3, PNG ou JPG (pelos primeiros bytes) de até 1 MB cada. Fora disso, 422 no campo
    `imagens` (nada é gravado)."""
    arquivos = [a for a in (arquivos or []) if a is not None and (a.filename or a.size)]
    if len(arquivos) > regras.MAX_IMAGENS_MENSAGEM:
        raise AppError(422, "dados_invalidos", regras.MSG_QUANTAS, {"imagens": regras.MSG_QUANTAS})
    lidas = []
    for arquivo in arquivos:
        dados = arquivo.file.read(regras.LIMITE_IMAGEM + 1)
        tipo = tipo_da_imagem(dados)
        if tipo is None or len(dados) > regras.LIMITE_IMAGEM:
            raise AppError(422, "dados_invalidos", regras.MSG_IMAGENS, {"imagens": regras.MSG_IMAGENS})
        largura, altura = dimensoes(dados, tipo)
        lidas.append(ImagemLida(dados, tipo, nome_do_arquivo(arquivo.filename), largura, altura))
    return lidas


def conferir_limites(s: Session, f: Feedback, novas_imagens: int) -> None:
    """409 com a conversa no limite de mensagens (200) ou de imagens (12)."""
    mensagens = s.scalar(select(func.count()).select_from(FeedbackMensagem).where(FeedbackMensagem.feedback_id == f.id))
    if mensagens >= regras.MAX_MENSAGENS:
        raise AppError(409, "limite_mensagens", MSG_LIMITE_MENSAGENS)
    if novas_imagens:
        imagens = s.scalar(select(func.count()).select_from(FeedbackImagem).where(FeedbackImagem.feedback_id == f.id))
        if imagens + novas_imagens > regras.MAX_IMAGENS_FEEDBACK:
            raise AppError(409, "limite_imagens", MSG_LIMITE_IMAGENS, {"imagens": MSG_LIMITE_IMAGENS})


def gravar_imagens(s: Session, f: Feedback, m: FeedbackMensagem, imagens: list[ImagemLida]) -> None:
    for i in imagens:
        s.add(FeedbackImagem(conta_id=f.conta_id, feedback_id=f.id, mensagem_id=m.id, tipo=i.tipo, dados=i.dados,
                             tamanho=len(i.dados), largura=i.largura, altura=i.altura, nome=i.nome))
    s.flush()


# ---- JSON -----------------------------------------------------------------------------------------------------------

def novidade_expr():
    """A equipe respondeu ou mudou a situação depois da última vez que o usuário abriu a conversa."""
    return and_(Feedback.ultima_da_equipe_em.is_not(None),
                or_(Feedback.visto_pelo_usuario_em.is_(None),
                    Feedback.ultima_da_equipe_em > Feedback.visto_pelo_usuario_em))


def atencao_expr():
    """Feedback novo ou mensagem do usuário que a equipe ainda não viu."""
    return or_(Feedback.visto_pela_equipe_em.is_(None), Feedback.ultima_do_usuario_em > Feedback.visto_pela_equipe_em)


def primeiro_texto():
    """O texto do relato (a primeira mensagem), para a lista."""
    return (select(FeedbackMensagem.texto).where(FeedbackMensagem.feedback_id == Feedback.id)
            .order_by(FeedbackMensagem.id).limit(1).scalar_subquery())


def contagem_mensagens():
    """Mensagens com texto (as mudanças de situação sem texto não contam)."""
    return (select(func.count()).select_from(FeedbackMensagem)
            .where(FeedbackMensagem.feedback_id == Feedback.id, FeedbackMensagem.texto != "").scalar_subquery())


def contagem_imagens():
    return select(func.count()).select_from(FeedbackImagem).where(FeedbackImagem.feedback_id == Feedback.id).scalar_subquery()


def resumo_json(f: Feedback, texto: str | None, mensagens: int, imagens: int) -> dict:
    return {"id": f.id, "tipo": f.tipo, "situacao": f.situacao, "impacto": f.impacto,
            "autoriza_depoimento": f.autoriza_depoimento, "trecho": regras.trecho(texto or ""),
            "mensagens": mensagens, "imagens": imagens, "pagina_titulo": f.pagina_titulo,
            "criado_em": f.criado_em, "atualizado_em": f.atualizado_em}


def mensagens_json(s: Session, f: Feedback) -> list[dict]:
    """A conversa em ordem, cada mensagem com as imagens (só os dados para mostrar, sem os bytes). O nome do autor: o do
    usuário hoje (nulo se ele saiu da conta) ou o da equipe guardado na mensagem."""
    imagens: dict[int, list[dict]] = {}
    for i in s.execute(select(FeedbackImagem.id, FeedbackImagem.mensagem_id, FeedbackImagem.tipo,
                              FeedbackImagem.tamanho, FeedbackImagem.largura, FeedbackImagem.altura,
                              FeedbackImagem.nome)
                       .where(FeedbackImagem.feedback_id == f.id).order_by(FeedbackImagem.id)):
        imagens.setdefault(i.mensagem_id, []).append({"id": i.id, "tipo": i.tipo, "tamanho": i.tamanho,
                                                      "largura": i.largura, "altura": i.altura, "nome": i.nome})
    linhas = s.execute(select(FeedbackMensagem, Usuario.nome)
                       .outerjoin(Usuario, and_(Usuario.id == FeedbackMensagem.usuario_id,
                                                Usuario.conta_id == FeedbackMensagem.conta_id))
                       .where(FeedbackMensagem.feedback_id == f.id).order_by(FeedbackMensagem.id))
    return [{"id": m.id, "autor": m.autor, "autor_nome": m.autor_nome if m.autor == "equipe" else nome,
             "texto": m.texto, "situacao": m.situacao, "criado_em": m.criado_em, "imagens": imagens.get(m.id, [])}
            for m, nome in linhas]


def detalhe_json(s: Session, f: Feedback) -> dict:
    """O que o usuário vê do feedback (sem a nota interna nem o diagnóstico)."""
    s.refresh(f)
    return {"id": f.id, "tipo": f.tipo, "situacao": f.situacao, "impacto": f.impacto,
            "autoriza_depoimento": f.autoriza_depoimento, "pagina": f.pagina, "pagina_titulo": f.pagina_titulo,
            "criado_em": f.criado_em, "atualizado_em": f.atualizado_em, "mensagens": mensagens_json(s, f)}


# ---- consultas ------------------------------------------------------------------------------------------------------

def _do_usuario(s: Session, ctx: Contexto, feedback_id: int, travar: bool = False) -> Feedback:
    consulta = select(Feedback).where(Feedback.id == feedback_id, Feedback.usuario_id == ctx.usuario_id)
    f = s.scalar(consulta.with_for_update() if travar else consulta)
    if f is None:
        raise nao_encontrado(MSG_NAO_ENCONTRADO)
    return f


def listar(ctx: Contexto) -> dict:
    """Os feedbacks do usuário (até 200), a atividade mais recente primeiro, e quantos têm novidade."""
    with em_conta(ctx.conta_id) as s:
        linhas = s.execute(
            select(Feedback, primeiro_texto(), contagem_mensagens(), contagem_imagens(), novidade_expr())
            .where(Feedback.usuario_id == ctx.usuario_id)
            .order_by(Feedback.atualizado_em.desc(), Feedback.id.desc()).limit(MAX_LISTA)).all()
        itens = [{**resumo_json(f, texto, n, i), "novidade": bool(nov)} for f, texto, n, i, nov in linhas]
        return {"itens": itens, "novidades": _contar_novidades(s, ctx)}


def _contar_novidades(s: Session, ctx: Contexto) -> int:
    return s.scalar(select(func.count()).select_from(Feedback)
                    .where(Feedback.usuario_id == ctx.usuario_id, novidade_expr())) or 0


def novidades(ctx: Contexto) -> dict:
    """Quantos feedbacks do usuário têm resposta ou mudança de situação que ele ainda não viu (o número do menu)."""
    with em_conta(ctx.conta_id) as s:
        return {"novidades": _contar_novidades(s, ctx)}


def detalhe(ctx: Contexto, feedback_id: int) -> dict:
    """O feedback com a conversa; marca como visto pelo usuário."""
    with em_conta(ctx.conta_id) as s:
        f = _do_usuario(s, ctx, feedback_id)
        s.execute(update(Feedback).where(Feedback.id == f.id).values(visto_pelo_usuario_em=func.now())
                  .execution_options(synchronize_session=False))
        return detalhe_json(s, f)


def imagem(ctx: Contexto, feedback_id: int, imagem_id: int) -> tuple[bytes, str]:
    """(bytes, tipo) de uma imagem de um feedback do próprio usuário; 404 se não for dele."""
    with em_conta(ctx.conta_id) as s:
        linha = s.execute(select(FeedbackImagem.dados, FeedbackImagem.tipo)
                          .join(Feedback, and_(Feedback.id == FeedbackImagem.feedback_id,
                                               Feedback.conta_id == FeedbackImagem.conta_id))
                          .where(FeedbackImagem.id == imagem_id, FeedbackImagem.feedback_id == feedback_id,
                                 Feedback.usuario_id == ctx.usuario_id)).one_or_none()
    if linha is None:
        raise nao_encontrado("Não encontramos essa imagem.")
    return linha.dados, linha.tipo


# ---- escrita --------------------------------------------------------------------------------------------------------

def criar(ctx: Contexto, dados: dict, arquivos: list[UploadFile] | None, navegador: str | None) -> dict:
    """Feedback novo com a primeira mensagem e as imagens. `dados`: tipo, texto, impacto (só erro), autoriza_depoimento
    (só elogio), pagina e pagina_titulo (onde a pessoa estava) e, com `detalhes`, tela, versao_site e diagnostico (o
    navegador vem do cabeçalho User-Agent, também só com `detalhes`)."""
    tipo = regras.validar_tipo(dados.get("tipo"))
    texto = regras.validar_texto(dados.get("texto"))
    impacto = regras.validar_impacto(tipo, dados.get("impacto"))
    imagens = ler_imagens(arquivos)
    detalhes = bool(dados.get("detalhes", True))
    with em_conta(ctx.conta_id) as s:
        f = Feedback(conta_id=ctx.conta_id, usuario_id=ctx.usuario_id, tipo=tipo, impacto=impacto,
                     autoriza_depoimento=tipo == "elogio" and bool(dados.get("autoriza_depoimento")),
                     pagina=regras.limpar_pagina(dados.get("pagina")),
                     pagina_titulo=regras.limpar_titulo(dados.get("pagina_titulo")),
                     navegador=regras.limpar_navegador(navegador) if detalhes else None,
                     tela=regras.limpar_tela(dados.get("tela")) if detalhes else None,
                     versao_site=regras.limpar_versao(dados.get("versao_site")) if detalhes else None,
                     diagnostico=regras.limpar_diagnostico(dados.get("diagnostico")) if detalhes else None)
        s.add(f)
        s.flush()
        m = FeedbackMensagem(conta_id=ctx.conta_id, feedback_id=f.id, autor="usuario", usuario_id=ctx.usuario_id,
                             texto=texto)
        s.add(m)
        s.flush()
        gravar_imagens(s, f, m, imagens)
        aviso = emails.AvisoEquipe(
            feedback_id=f.id, tipo=tipo, impacto=impacto, texto=texto, imagens=len(imagens),
            autor_nome=ctx.usuario.get("nome") or ctx.email, autor_email=ctx.email,
            conta_nome=ctx.conta.get("nome") or "", conta_plano=ctx.conta.get("plano"),
            conta_situacao=ctx.conta.get("situacao"), pagina=f.pagina, pagina_titulo=f.pagina_titulo,
            autoriza_depoimento=f.autoriza_depoimento)
        apos_commit(s, lambda: emails.avisar_equipe(aviso, novo=True))
        return detalhe_json(s, f)


def responder(ctx: Contexto, feedback_id: int, texto: object, arquivos: list[UploadFile] | None) -> dict:
    """Mensagem nova do usuário na conversa (texto e/ou até 3 imagens); devolve o feedback com a conversa."""
    texto = regras.validar_texto(texto, obrigatorio=False)
    imagens = ler_imagens(arquivos)
    if not texto and not imagens:
        raise AppError(422, "dados_invalidos", regras.MSG_TEXTO, {"texto": regras.MSG_TEXTO})
    with em_conta(ctx.conta_id) as s:
        f = _do_usuario(s, ctx, feedback_id, travar=True)
        conferir_limites(s, f, len(imagens))
        # a equipe já tinha visto tudo até aqui: avisa; senão o aviso anterior ainda está pendente
        equipe_em_dia = f.visto_pela_equipe_em is not None and f.visto_pela_equipe_em >= f.ultima_do_usuario_em
        m = FeedbackMensagem(conta_id=f.conta_id, feedback_id=f.id, autor="usuario", usuario_id=ctx.usuario_id,
                             texto=texto)
        s.add(m)
        s.flush()
        gravar_imagens(s, f, m, imagens)
        s.execute(update(Feedback).where(Feedback.id == f.id)
                  .values(ultima_do_usuario_em=func.now(), atualizado_em=func.now(), visto_pelo_usuario_em=func.now())
                  .execution_options(synchronize_session=False))
        if equipe_em_dia:
            aviso = emails.AvisoEquipe(
                feedback_id=f.id, tipo=f.tipo, impacto=f.impacto, texto=texto, imagens=len(imagens),
                autor_nome=ctx.usuario.get("nome") or ctx.email, autor_email=ctx.email,
                conta_nome=ctx.conta.get("nome") or "", conta_plano=ctx.conta.get("plano"),
                conta_situacao=ctx.conta.get("situacao"), pagina=f.pagina, pagina_titulo=f.pagina_titulo,
                autoriza_depoimento=f.autoriza_depoimento)
            apos_commit(s, lambda: emails.avisar_equipe(aviso, novo=False))
        return detalhe_json(s, f)


def alterar(ctx: Contexto, feedback_id: int, autoriza_depoimento: bool) -> dict:
    """O usuário dá ou retira a autorização de usar o elogio como depoimento no site do Toqqi (só elogio; 409 nos
    outros tipos)."""
    with em_conta(ctx.conta_id) as s:
        f = _do_usuario(s, ctx, feedback_id, travar=True)
        if f.tipo != "elogio":
            raise AppError(409, "nao_e_elogio", "Só um elogio pode virar depoimento.")
        f.autoriza_depoimento = bool(autoriza_depoimento)
        s.flush()
        return detalhe_json(s, f)


# ---- limpeza ---------------------------------------------------------------------------------------------------------

DIAS_IMAGENS = 180
LOTE_IMAGENS = 2000


def limpar_imagens_antigas() -> int:
    """Tarefa `limpeza`: apaga as imagens dos feedbacks concluídos ou encerrados sem atividade há mais de 180 dias (até
    2.000 por rodada; a conversa fica). Devolve quantas saíram."""
    with modo_sistema() as s:
        return s.execute(text("""
            DELETE FROM feedback_imagens WHERE id IN (
                SELECT i.id FROM feedback_imagens i JOIN feedbacks f ON f.id = i.feedback_id
                 WHERE f.situacao IN ('concluido', 'encerrado')
                   AND f.atualizado_em < now() - make_interval(days => :dias)
                 LIMIT :lote)
        """), {"dias": DIAS_IMAGENS, "lote": LOTE_IMAGENS}).rowcount
