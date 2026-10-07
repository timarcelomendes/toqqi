"""Plataforma › Feedback (docs/api-feedback.md §4): a equipe Toqqi (superadmins) lê, responde e organiza os feedbacks
de todas as contas, em modo sistema (como Plataforma › Erros).

- Lista (até 300) com filtros de tipo, situação (abertos = recebido, em análise ou planejado; concluídos; encerrados;
  todos) e busca (conta, nome ou e-mail de quem mandou, ou o texto de qualquer mensagem), a atividade mais recente
  primeiro, com `atencao` (feedback novo ou mensagem do usuário que a equipe ainda não viu) e as contagens.
- Detalhe: o feedback com a conversa, a conta, quem mandou, o contexto (tela, navegador, versão, diagnóstico) e a nota
  interna; abrir marca como visto pela equipe.
- Responder: texto e/ou situação nova numa mensagem só; texto → e-mail à pessoa (ativa, confirmada e sem ter retirado o
  aceite dos termos).
- Alterar: situação (entra na conversa como mudança, sem e-mail) e/ou nota interna (só a equipe vê).
"""
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from toqqi.core.db import apos_commit, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.modelos import AceiteTermos, Conta, Feedback, FeedbackImagem, FeedbackMensagem, Usuario
from toqqi.modulos.feedback import emails, regras
from toqqi.modulos.feedback.servico import (
    MSG_NAO_ENCONTRADO,
    atencao_expr,
    conferir_limites,
    contagem_imagens,
    contagem_mensagens,
    mensagens_json,
    primeiro_texto,
    resumo_json,
)

FILTROS_SITUACAO = ("abertos", "concluidos", "encerrados", "todos")
MAX_LISTA = 300
MAX_BUSCA = 100
MSG_RESPOSTA = "Escreva a resposta ou escolha uma situação diferente da atual."


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _com_autor():
    return and_(Usuario.id == Feedback.usuario_id, Usuario.conta_id == Feedback.conta_id)


def contagem() -> dict:
    """{atencao, abertos}: o número da aba e do menu da Plataforma."""
    with modo_sistema() as s:
        atencao = s.scalar(select(func.count()).select_from(Feedback).where(atencao_expr())) or 0
        abertos = s.scalar(select(func.count()).select_from(Feedback)
                           .where(Feedback.situacao.in_(regras.ABERTAS))) or 0
    return {"atencao": atencao, "abertos": abertos}


def listar(tipo: str | None, situacao: str, busca: str | None) -> dict:
    consulta = (select(Feedback, Conta.nome, Usuario.nome, Usuario.email, primeiro_texto(), contagem_mensagens(),
                       contagem_imagens(), atencao_expr())
                .join(Conta, Conta.id == Feedback.conta_id).outerjoin(Usuario, _com_autor()))
    if tipo:
        consulta = consulta.where(Feedback.tipo == tipo)
    if situacao == "abertos":
        consulta = consulta.where(Feedback.situacao.in_(regras.ABERTAS))
    elif situacao == "concluidos":
        consulta = consulta.where(Feedback.situacao == "concluido")
    elif situacao == "encerrados":
        consulta = consulta.where(Feedback.situacao == "encerrado")
    termo = " ".join((busca or "").split())[:MAX_BUSCA]
    if termo:
        padrao = f"%{_escapar_like(termo)}%"
        texto = exists().where(FeedbackMensagem.feedback_id == Feedback.id, FeedbackMensagem.texto.ilike(padrao))
        consulta = consulta.where(or_(Conta.nome.ilike(padrao), Usuario.nome.ilike(padrao), Usuario.email.ilike(padrao),
                                      texto))
    with modo_sistema() as s:
        linhas = s.execute(consulta.order_by(Feedback.atualizado_em.desc(), Feedback.id.desc()).limit(MAX_LISTA)).all()
        itens = [{**resumo_json(f, texto, n, i), "conta_id": f.conta_id, "conta_nome": conta, "autor_nome": nome,
                  "autor_email": email_autor, "atencao": bool(atencao)}
                 for f, conta, nome, email_autor, texto, n, i, atencao in linhas]
    return {"itens": itens, "contagem": contagem()}


def _travado(s: Session, feedback_id: int) -> Feedback:
    f = s.scalar(select(Feedback).where(Feedback.id == feedback_id).with_for_update())
    if f is None:
        raise nao_encontrado(MSG_NAO_ENCONTRADO)
    return f


def _autor(s: Session, f: Feedback) -> Usuario | None:
    if f.usuario_id is None:
        return None
    return s.scalar(select(Usuario).where(Usuario.id == f.usuario_id, Usuario.conta_id == f.conta_id))


def _detalhe(s: Session, f: Feedback) -> dict:
    s.refresh(f)
    conta = s.get(Conta, f.conta_id)
    autor = _autor(s, f)
    return {
        "id": f.id, "tipo": f.tipo, "situacao": f.situacao, "impacto": f.impacto,
        "autoriza_depoimento": f.autoriza_depoimento, "criado_em": f.criado_em, "atualizado_em": f.atualizado_em,
        "conta": {"id": conta.id, "nome": conta.nome, "plano": conta.plano, "situacao": conta.situacao},
        "autor": None if autor is None else {"id": autor.id, "nome": autor.nome, "email": autor.email,
                                             "perfil": autor.perfil, "cargo": autor.cargo, "situacao": autor.situacao},
        "contexto": {"pagina": f.pagina, "pagina_titulo": f.pagina_titulo, "navegador": f.navegador, "tela": f.tela,
                     "versao_site": f.versao_site, "diagnostico": f.diagnostico},
        "nota_interna": f.nota_interna, "mensagens": mensagens_json(s, f),
    }


def detalhe(feedback_id: int) -> dict:
    """O feedback para a equipe; marca como visto pela equipe."""
    with modo_sistema() as s:
        f = s.get(Feedback, feedback_id)
        if f is None:
            raise nao_encontrado(MSG_NAO_ENCONTRADO)
        f.visto_pela_equipe_em = func.now()
        s.flush()
        return _detalhe(s, f)


def _pode_receber(s: Session, u: Usuario | None) -> bool:
    """Ativo, e-mail confirmado e sem ter retirado o aceite dos termos (sem aceitar de novo)."""
    if u is None or u.situacao != "ativo" or not u.email_confirmado:
        return False
    em_vigor = s.scalar(select(exists().where(AceiteTermos.usuario_id == u.id, AceiteTermos.revogado_em.is_(None))))
    retirou = s.scalar(select(exists().where(AceiteTermos.usuario_id == u.id, AceiteTermos.revogado_em.is_not(None))))
    return bool(em_vigor or not retirou)


def responder(ctx: Contexto, feedback_id: int, texto: object, situacao: object) -> dict:
    """Mensagem da equipe (texto e/ou situação nova). Com texto, a pessoa recebe e-mail com a resposta."""
    texto = regras.validar_texto(texto, obrigatorio=False)
    nova = regras.validar_situacao(situacao) if situacao not in (None, "") else None
    with modo_sistema() as s:
        f = _travado(s, feedback_id)
        if nova == f.situacao:
            nova = None
        if not texto and nova is None:
            raise AppError(422, "dados_invalidos", MSG_RESPOSTA, {"texto": MSG_RESPOSTA})
        conferir_limites(s, f, 0)
        equipe = (ctx.usuario.get("nome") or ctx.email)[:120]
        s.add(FeedbackMensagem(conta_id=f.conta_id, feedback_id=f.id, autor="equipe", autor_nome=equipe, texto=texto,
                               situacao=nova))
        if nova:
            f.situacao = nova
        f.ultima_da_equipe_em = func.now()
        f.atualizado_em = func.now()
        f.visto_pela_equipe_em = func.now()
        s.flush()
        autor = _autor(s, f)
        if texto and _pode_receber(s, autor):
            s.refresh(f)
            resposta = emails.RespostaUsuario(
                feedback_id=f.id, conta_id=f.conta_id, tipo=f.tipo, criado_em=f.criado_em, para=autor.email,
                nome=autor.nome, equipe_nome=equipe, texto=texto, situacao=nova)
            apos_commit(s, lambda: emails.avisar_usuario(resposta))
        return _detalhe(s, f)


def alterar(ctx: Contexto, feedback_id: int, situacao: object = None, nota_interna: object = None) -> dict:
    """Situação (vira uma linha na conversa, sem e-mail) e/ou nota interna."""
    nova = regras.validar_situacao(situacao) if situacao is not None else None
    nota = regras.validar_nota(nota_interna) if nota_interna is not None else None
    with modo_sistema() as s:
        f = _travado(s, feedback_id)
        if nova is not None and nova != f.situacao:
            conferir_limites(s, f, 0)
            s.add(FeedbackMensagem(conta_id=f.conta_id, feedback_id=f.id, autor="equipe",
                                   autor_nome=(ctx.usuario.get("nome") or ctx.email)[:120], texto="", situacao=nova))
            f.situacao = nova
            f.ultima_da_equipe_em = func.now()
            f.atualizado_em = func.now()
            f.visto_pela_equipe_em = func.now()
        if nota is not None:
            f.nota_interna = nota
        s.flush()
        return _detalhe(s, f)


def imagem(feedback_id: int, imagem_id: int) -> tuple[bytes, str]:
    with modo_sistema() as s:
        linha = s.execute(select(FeedbackImagem.dados, FeedbackImagem.tipo)
                          .where(FeedbackImagem.id == imagem_id, FeedbackImagem.feedback_id == feedback_id)).one_or_none()
    if linha is None:
        raise nao_encontrado("Não encontramos essa imagem.")
    return linha.dados, linha.tipo
