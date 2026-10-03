"""Ação automática e alerta ao responsável, no ponto único "resposta registrada".

Respostas de pesquisa e registradas à mão (não as importadas) ganham uma ação automática (no máximo uma por
resposta; o banco garante com índice único parcial):

- NPS detrator (0–6): alta, hoje + prazo_detrator, "[Detrator NPS {nota}] Ação requerida: {alvo}";
- NPS neutro (7–8): media, hoje + prazo_neutro, "[Neutro NPS {nota}] Ação requerida: {alvo}";
- NPS promotor (9–10), só com acao_promotor: baixa, hoje + prazo_promotor,
  "[Promotor NPS {nota}] Ação requerida: {alvo}";
- CSAT insatisfeito (1–2): alta, hoje + prazo_detrator, "[CSAT {nota}] Cliente insatisfeito: {assunto}".

`alvo` = empresa, senão contato, senão "cliente sem cadastro"; `assunto` = contexto.assunto, senão o assunto do
convite, senão `alvo`. Responsável = responsável da empresa. Hoje = data em São Paulo (`relogio`). Etapa 5d: a ação
nova pode ficar com os passos da IA pendentes (`acoes.passos.marcar`; quem grava usa também `coletar_passos()`).

Descrição: o comentário do cliente (só o que ele escreveu), as opções que marcou, o contato (só o nome: a ação já
leva ao cadastro) e o contexto do pedido.

Alerta: ação alta com responsável que tem e-mail → e-mail "Alerta de risco" pelo provedor da plataforma (e-mail do
sistema: não entra no histórico de envios, mas entra no registro de e-mails enviados da conta, tipo `alerta_risco`),
só se o provedor conta como configurado pela mesma regra dos envios de pesquisa (o `console` não conta em produção:
comentário e dados do cliente não vão parar no log). Quem grava a resposta envolve o trabalho em `coletar_alertas()` e
agenda `enviar_alertas` depois do commit (BackgroundTasks); sem coletor, o alerta não sai.
"""
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from toqqi.core import email, relogio
from toqqi.core.config import config
from toqqi.modelos import Acao, Contato, Convite, Empresa, Formulario, Responsavel, Resposta
from toqqi.modulos.acoes import passos
from toqqi.modulos.acoes.configuracao import obter
from toqqi.modulos.envios.configuracao import provedor_ok
from toqqi.modulos.formularios.servico import ROTULOS_CONTEXTO
from toqqi.modulos.respostas.convites import CHAVES_CONTEXTO
from toqqi.modulos.respostas.eventos import GANCHOS
from toqqi.modulos.respostas.indicadores import ROTULOS_GRUPO, ROTULOS_TIPO
from toqqi.modulos.respostas.registro import SEPARADOR_COMENTARIOS, escolhas_do_cliente

log = logging.getLogger("toqqi.acoes")

SEM_CADASTRO = "cliente sem cadastro"
MAX_TITULO = 200
MAX_DESCRICAO = 4000
MAX_COMENTARIO_ALERTA = 1000


# ---- alertas (depois do commit) ---------------------------------------------

@dataclass
class Alerta:
    para: str
    assunto: str
    paragrafos: list[str]
    botao: tuple[str, str]
    conta_id: int


_coletados: ContextVar[list | None] = ContextVar("alertas_apos_commit", default=None)


@contextmanager
def coletar_alertas() -> Iterator[list[Alerta]]:
    """Junta os alertas decididos pelos ganchos durante o bloco, para enviar depois do commit."""
    lista: list[Alerta] = []
    marca = _coletados.set(lista)
    try:
        yield lista
    finally:
        _coletados.reset(marca)


def enviar_alertas(alertas: Iterable[Alerta]) -> None:
    """Envia os alertas um a um (e-mail do sistema: falha vai para o log e não derruba nada). Sem provedor de
    e-mail configurado (mesma regra das pesquisas), não envia: o `console` imprimiria os dados do cliente no log."""
    alertas = list(alertas)
    if not alertas:
        return
    if not provedor_ok():
        log.info("%d alerta(s) de risco não enviado(s): o envio de e-mails não está configurado.", len(alertas))
        return
    for a in alertas:
        email.enviar(a.para, a.assunto, a.paragrafos, a.botao, conta_id=a.conta_id, tipo="alerta_risco")


# ---- regra ------------------------------------------------------------------

def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def regra(cfg, tipo_nota: str | None, grupo: str | None) -> tuple[str, int] | None:
    """(prioridade, dias de prazo) da ação automática, ou None se a resposta não gera ação."""
    if tipo_nota == "nps":
        if grupo == "detrator":
            return "alta", cfg.prazo_detrator
        if grupo == "neutro":
            return "media", cfg.prazo_neutro
        if grupo == "promotor" and cfg.acao_promotor:
            return "baixa", cfg.prazo_promotor
    elif tipo_nota == "csat" and grupo == "insatisfeito":
        return "alta", cfg.prazo_detrator
    return None


def _descricao(r: Resposta, escolhas: list[str], contato: Contato | None) -> str:
    linhas = [f"Comentário do cliente: {r.comentario_cliente or '(sem comentário)'}"]
    if escolhas:
        linhas.append(f"O cliente marcou: {SEPARADOR_COMENTARIOS.join(escolhas)}")
    if contato is not None:
        linhas.append(f"Contato: {contato.nome}")
    for chave in CHAVES_CONTEXTO:
        valor = (r.contexto or {}).get(chave)
        if valor:
            linhas.append(f"{ROTULOS_CONTEXTO[chave]}: {valor}")
    return _cortar("\n".join(linhas), MAX_DESCRICAO)


def _alerta(acao: Acao, r: Resposta, alvo: str, contato: Contato | None, para: str) -> Alerta:
    link = f"{config().FRONTEND_URL.rstrip('/')}/planos-de-acao/{acao.id}"
    comentario = r.comentario_cliente
    return Alerta(
        para=para,
        assunto=f"Alerta de risco: {alvo} deu nota {r.nota}",
        paragrafos=[
            f"{alvo} deu nota {r.nota} e precisa de atenção.",
            f"Nota: {r.nota} · Categoria: {ROTULOS_GRUPO[r.grupo]} ({ROTULOS_TIPO[r.tipo_nota]})",
            f"Comentário: {_cortar(comentario, MAX_COMENTARIO_ALERTA)}" if comentario
            else "Comentário: o cliente não deixou comentário.",
            f"Contato: {contato.nome if contato else SEM_CADASTRO}",
            f"Prazo para tratar: {acao.prazo.strftime('%d/%m/%Y')}.",
        ],
        botao=("Tratar no Toqqi", link),
        conta_id=r.conta_id,
    )


def criar_acao_automatica(s: Session, r: Resposta) -> Acao | None:
    """Cria a ação automática da resposta (se a nota pede) e coleta o alerta. Roda na transação da resposta."""
    if r.origem not in ("pesquisa", "manual") or r.nota is None:
        return None
    prioridade_prazo = regra(obter(s, criar=False), r.tipo_nota, r.grupo)
    if prioridade_prazo is None:
        return None
    prioridade, dias = prioridade_prazo
    empresa = s.get(Empresa, r.empresa_id) if r.empresa_id else None
    contato = s.get(Contato, r.contato_id) if r.contato_id else None
    alvo = (empresa.nome if empresa else None) or (contato.nome if contato else None) or SEM_CADASTRO
    if r.tipo_nota == "csat":
        convite = s.get(Convite, r.convite_id) if r.convite_id else None
        assunto = (r.contexto or {}).get("assunto") or (convite.assunto if convite else None) or alvo
        titulo = f"[CSAT {r.nota}] Cliente insatisfeito: {assunto}"
    else:
        titulo = f"[{ROTULOS_GRUPO[r.grupo]} NPS {r.nota}] Ação requerida: {alvo}"
    formulario = s.get(Formulario, r.formulario_id) if r.origem == "pesquisa" else None
    escolhas = escolhas_do_cliente(formulario.perguntas, r.respostas) if formulario else []
    agora = relogio.agora()
    acao = Acao(resposta_id=r.id, empresa_id=r.empresa_id, contato_id=r.contato_id,
                responsavel_id=empresa.responsavel_id if empresa else None, titulo=_cortar(titulo, MAX_TITULO),
                descricao=_descricao(r, escolhas, contato), prioridade=prioridade,
                prazo=relogio.hoje() + timedelta(days=dias), situacao="a_fazer", origem="automatica", grupo=r.grupo,
                tipo_nota=r.tipo_nota, nota=r.nota, criada_em=agora, atualizada_em=agora)
    s.add(acao)
    s.flush()
    passos.marcar(s, r.conta_id, acao, r)  # etapa 5d: passos sugeridos pela IA, depois do commit
    if prioridade == "alta" and acao.responsavel_id is not None:
        responsavel = s.get(Responsavel, acao.responsavel_id)
        lista = _coletados.get()
        if responsavel is not None and responsavel.email and lista is not None:
            lista.append(_alerta(acao, r, alvo, contato, responsavel.email))
    return acao


def _ao_registrar_resposta(s: Session, r: Resposta) -> None:
    criar_acao_automatica(s, r)


GANCHOS.append(_ao_registrar_resposta)
