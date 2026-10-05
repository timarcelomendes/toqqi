"""Zona de risco (Configurações › Dados da conta; `zona_risco.usar`, só administrador): apagar de uma vez as respostas,
os contatos ou recomeçar do zero. Etapa 5f.

Opções (cumulativas):
- `respostas`: as respostas com `tipo_nota` diferente de 'csat' (NPS e personalizadas, inclusive arquivadas, manuais e
  importadas). Ações, envios e indicações perdem o vínculo (SET NULL); convites continuam; `contatos.ultima_nota` é
  recalculada em lote (a regra de `respostas.registro.atualizar_ultima_nota`).
- `contatos`: o de cima + todos os `envios`, os `convites` com contato, `importacoes`, `eventos_idempotencia`, os
  `emails_enviados` de convite, lembrete, agradecimento, alerta de risco e indicação e, por último, os `contatos`.
  Antes, as CSAT ficam com `contato_id` nulo (sem cópia de nome, e-mail ou telefone); ações, ofertas e indicações
  perdem o contato (SET NULL).
- `tudo` (Recomeçar do zero): o de cima + `acoes`, `indicacoes`, `ofertas` e `empresas`. CSAT e convites sem contato
  ficam sem empresa (SET NULL).
- Em todas, também `ia_pareceres`, `alertas_pico` e `webhook_entregas`.

Sempre fica: usuários, configurações (inclusive webhooks, WhatsApp e chave), formulários, imagens, responsáveis,
cadastros, descadastros, auditoria, as CSAT (nota, comentário, temas, análise, contexto, referência, datas), os
convites sem contato (links de CSAT da integração: seguem respondíveis), o uso de IA e de WhatsApp e a assinatura.

Uma transação (tudo ou nada), em nome da conta e com `conta_id` explícito em cada comando além do RLS:
`pg_try_advisory_xact_lock('zona_risco:{conta}')` (ocupada → 409 `zona_em_andamento`), a linha de `config_envios`
travada (a mesma do robô e dos lembretes: nada é agendado no meio) e `statement_timeout` de 120 s (estourou → tudo
desfeito, 503 `zona_indisponivel`). Comandos por conjunto (os índices da migração 0015 cobrem os SET NULL/CASCADE):
5.000 contatos e 50.000 respostas saem em segundos. A ordem dentro da transação evita trabalho à toa (em `tudo`, ações,
indicações e ofertas saem antes; envios antes das respostas); o resultado é o da tabela acima.

`apagados` = o `rowcount` de cada comando, com as mesmas chaves das contagens do GET (as do GET são o que o POST
apagaria). Auditoria `zona_risco` (atenção) `{opcao, apagados, mantidos}` na mesma transação; nada vai para webhooks
nem e-mail. Os ids não voltam (as sequências são de todas as contas).
"""
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.modelos import (
    Acao,
    AlertaPico,
    ConfigEnvios,
    Contato,
    Convite,
    Descadastro,
    EmailEnviado,
    Empresa,
    Envio,
    EventoIdempotencia,
    Formulario,
    IaParecer,
    Importacao,
    Indicacao,
    Oferta,
    Resposta,
    Usuario,
    WebhookEntrega,
)

OPCOES = ("respostas", "contatos", "tudo")
CONFIRMACAO = "APAGAR"
TEMPO_MAXIMO = "120s"
TIPOS_EMAIL_CONTATO = ("convite", "lembrete", "agradecimento", "retorno", "alerta_risco", "indicacao")

MSG_CONFIRMACAO = "Digite APAGAR para confirmar."
MSG_EM_ANDAMENTO = "Já tem uma exclusão da zona de risco em andamento nesta conta. Aguarde terminar."
MSG_INDISPONIVEL = "Não deu para apagar agora e nada foi apagado. Tente de novo em alguns minutos."


def _nao_csat(conta_id: int):
    return Resposta.conta_id == conta_id, Resposta.tipo_nota.is_distinct_from("csat")


def _contar(s: Session, modelo, *conds) -> int:
    return s.scalar(select(func.count()).select_from(modelo).where(*conds))


def contagens(s: Session, conta_id: int) -> dict:
    """O que cada opção apagaria agora (as mesmas chaves de `apagados`) e o que sempre fica."""
    respostas = _contar(s, Resposta, *_nao_csat(conta_id))
    acoes_sem_vinculo = _contar(s, Acao, Acao.conta_id == conta_id, Acao.resposta_id.in_(
        select(Resposta.id).where(*_nao_csat(conta_id))))
    contatos = {
        "contatos": _contar(s, Contato, Contato.conta_id == conta_id),
        "respostas": respostas,
        "convites": _contar(s, Convite, Convite.conta_id == conta_id, Convite.contato_id.is_not(None)),
        "envios": _contar(s, Envio, Envio.conta_id == conta_id),
        "csat_sem_contato": _contar(s, Resposta, Resposta.conta_id == conta_id, Resposta.tipo_nota == "csat",
                                    Resposta.contato_id.is_not(None)),
    }
    tudo = {
        **contatos,
        "empresas": _contar(s, Empresa, Empresa.conta_id == conta_id),
        "acoes": _contar(s, Acao, Acao.conta_id == conta_id),
        "indicacoes": _contar(s, Indicacao, Indicacao.conta_id == conta_id),
        "ofertas": _contar(s, Oferta, Oferta.conta_id == conta_id),
    }
    return {"opcoes": {"respostas": {"respostas": respostas, "acoes_sem_vinculo": acoes_sem_vinculo},
                       "contatos": contatos, "tudo": tudo},
            "mantidos": mantidos(s, conta_id)}


def mantidos(s: Session, conta_id: int) -> dict:
    return {
        "csat": _contar(s, Resposta, Resposta.conta_id == conta_id, Resposta.tipo_nota == "csat"),
        "descadastros": _contar(s, Descadastro, Descadastro.conta_id == conta_id),
        "usuarios": _contar(s, Usuario, Usuario.conta_id == conta_id),
        "formularios": _contar(s, Formulario, Formulario.conta_id == conta_id),
    }


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return contagens(s, ctx.conta_id)


# ---- apagar --------------------------------------------------------------------------------------

def _rowcount(s: Session, comando) -> int:
    return s.execute(comando.execution_options(synchronize_session=False)).rowcount


def _recalcular_ultima_nota(s: Session, conta_id: int) -> None:
    """`ultima_nota` = a nota da resposta mais recente (pela data da resposta) não arquivada e com nota; sem nenhuma,
    vazia. Em lote, só onde muda (sem as respostas apagadas, só pode diminuir o que havia)."""
    s.execute(text("""
        UPDATE contatos c SET ultima_nota = n.nota
          FROM (SELECT ct.id,
                       (SELECT r.nota FROM respostas r
                         WHERE r.conta_id = :c AND r.contato_id = ct.id AND NOT r.arquivada AND r.nota IS NOT NULL
                         ORDER BY r.data_resposta DESC, r.id DESC LIMIT 1) AS nota
                  FROM contatos ct
                 WHERE ct.conta_id = :c AND ct.ultima_nota IS NOT NULL) n
         WHERE c.conta_id = :c AND c.id = n.id AND c.ultima_nota IS DISTINCT FROM n.nota
    """), {"c": conta_id})


def _apagar_respostas(s: Session, c: int, apagados: dict) -> None:
    apagados["acoes_sem_vinculo"] = _rowcount(s, update(Acao).where(
        Acao.conta_id == c, Acao.resposta_id.in_(select(Resposta.id).where(*_nao_csat(c)))).values(resposta_id=None))
    apagados["respostas"] = _rowcount(s, delete(Resposta).where(*_nao_csat(c)))  # envios e indicações: SET NULL


def _apagar_contatos(s: Session, c: int, apagados: dict) -> None:
    apagados["csat_sem_contato"] = _rowcount(s, update(Resposta).where(
        Resposta.conta_id == c, Resposta.contato_id.is_not(None)).values(contato_id=None))  # só sobraram as CSAT
    apagados["convites"] = _rowcount(s, delete(Convite).where(Convite.conta_id == c, Convite.contato_id.is_not(None)))
    s.execute(delete(Importacao).where(Importacao.conta_id == c))
    s.execute(delete(EventoIdempotencia).where(EventoIdempotencia.conta_id == c))
    s.execute(delete(EmailEnviado).where(EmailEnviado.conta_id == c, EmailEnviado.tipo.in_(TIPOS_EMAIL_CONTATO)))
    # ações, ofertas e indicações perdem o contato (SET NULL)
    apagados["contatos"] = _rowcount(s, delete(Contato).where(Contato.conta_id == c))


def _apagar_comercial(s: Session, c: int, apagados: dict) -> None:
    """Recomeçar do zero, antes do resto: ações, indicações e ofertas (nada aponta para elas)."""
    apagados["acoes"] = _rowcount(s, delete(Acao).where(Acao.conta_id == c))
    apagados["indicacoes"] = _rowcount(s, delete(Indicacao).where(Indicacao.conta_id == c))
    apagados["ofertas"] = _rowcount(s, delete(Oferta).where(Oferta.conta_id == c))


def _apagar_empresas(s: Session, c: int, apagados: dict) -> None:
    apagados["empresas"] = _rowcount(s, delete(Empresa).where(Empresa.conta_id == c))  # CSAT e convites: SET NULL


def _apagar_derivados(s: Session, c: int) -> None:
    for modelo in (IaParecer, AlertaPico, WebhookEntrega):
        s.execute(delete(modelo).where(modelo.conta_id == c))


def _apagar(s: Session, c: int, opcao: str) -> dict:
    apagados: dict[str, int] = {}
    if opcao == "tudo":
        _apagar_comercial(s, c, apagados)
    if opcao in ("contatos", "tudo"):
        apagados["envios"] = _rowcount(s, delete(Envio).where(Envio.conta_id == c))
    _apagar_respostas(s, c, apagados)
    if opcao in ("contatos", "tudo"):
        _apagar_contatos(s, c, apagados)
    if opcao == "tudo":
        _apagar_empresas(s, c, apagados)
    _apagar_derivados(s, c)
    if opcao == "respostas":
        _recalcular_ultima_nota(s, c)
    chaves = {"respostas": ("respostas", "acoes_sem_vinculo"),
              "contatos": ("contatos", "respostas", "convites", "envios", "csat_sem_contato"),
              "tudo": ("contatos", "respostas", "convites", "envios", "csat_sem_contato", "empresas", "acoes",
                       "indicacoes", "ofertas")}[opcao]
    return {k: apagados[k] for k in chaves}


def confirmacao_ok(confirmacao: str | None) -> bool:
    return (confirmacao or "").strip().upper() == CONFIRMACAO


def _tempo_esgotado(e: OperationalError) -> bool:
    return getattr(e.orig, "sqlstate", None) == "57014"  # query_canceled (statement_timeout)


def apagar(ctx: Contexto, opcao: str, confirmacao: str | None) -> dict:
    """POST /conta/zona-de-risco → {opcao, apagados, mantidos}."""
    assert opcao in OPCOES
    if not confirmacao_ok(confirmacao):
        raise AppError(422, "dados_invalidos", MSG_CONFIRMACAO, {"confirmacao": MSG_CONFIRMACAO})
    c = ctx.conta_id
    try:
        with em_conta(c) as s:
            livre = s.scalar(text("select pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
                             {"k": f"zona_risco:{c}"})
            if not livre:
                raise AppError(409, "zona_em_andamento", MSG_EM_ANDAMENTO)
            # a linha do robô e dos lembretes: nada é agendado enquanto os dados saem
            s.execute(select(ConfigEnvios.conta_id).where(ConfigEnvios.conta_id == c).with_for_update())
            s.execute(text(f"SET LOCAL statement_timeout = '{TEMPO_MAXIMO}'"))
            apagados = _apagar(s, c, opcao)
            ficam = mantidos(s, c)
            registrar(s, "zona_risco", "atencao", {"opcao": opcao, "apagados": apagados, "mantidos": ficam},
                      usuario_id=ctx.usuario_id)
    except OperationalError as e:
        if _tempo_esgotado(e):
            raise AppError(503, "zona_indisponivel", MSG_INDISPONIVEL) from None
        raise
    return {"opcao": opcao, "apagados": apagados, "mantidos": ficam}
