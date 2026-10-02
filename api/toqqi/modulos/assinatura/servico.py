"""Assinatura e cobrança pelo Asaas: situação da conta (`recalcular`), cobranças locais, conciliação ao assinar e as
rotas da assinatura. A conferência diária, a conciliação em segundo plano e a tarefa `assinaturas` ficam em
`conferencia.py`.

A fonte da verdade do pagamento é o Asaas: as cobranças locais só mudam pelo que a API do Asaas diz (consulta feita
com a conta travada, para duas atualizações da mesma conta não gravarem uma leitura velha por cima de uma nova).

Ambiente: clientes e assinaturas guardam o ambiente do Asaas em que existem (`sandbox` | `producao`, pelo prefixo da
chave). Para a chave atual, uma linha do outro ambiente não existe: não aparece em GET /assinatura, não recebe aviso
nem conferência e os pagamentos dela não contam no `pago_ate`. Com a chave de produção, o que era de sandbox é
descartado (`limpar_outro_ambiente`, pela tarefa ou no próximo assinar).

Nunca duas assinaturas vivas no Asaas para a mesma conta: antes de criar uma (e depois de um tempo esgotado ao criar),
as assinaturas com a referência da conta ("toqqi-conta-{id}") são listadas; a desconhecida com o valor pedido é adotada
(um pedido anterior chegou a criá-la) e as outras são removidas. Remoção que falha fica em `asaas_remocoes` para a
tarefa tentar de novo.

Travas (sempre nesta ordem): `assinatura:{conta}` (uma operação por vez por conta: rotas, avisos, conferência), a
linha da conta (FOR NO KEY UPDATE: não segura as inclusões que só apontam para a conta, como contatos e respostas) e,
ao mudar o plano, a trava das inclusões de contatos (a mesma do gatilho do limite) até o fim da transação. Limitação
conhecida: as chamadas ao Asaas (até 20 s cada) acontecem com essas travas pegas.
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, exists, func, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import asaas, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema, travar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.planos import (
    NOMES,
    PRECOS,
    contatos_ativos,
    limite_contatos,
    numero,
    planos_json,
    travar_contatos,
)
from toqqi.core.texto import normalizar_telefone
from toqqi.modelos import AsaasRemocao, Assinatura, Cobranca, Conta, Usuario
from toqqi.modulos.assinatura import regras
from toqqi.modulos.assinatura.regras import assinou_no_teste, dia_de, fim_do_periodo_pago, fim_do_teste

log = logging.getLogger("toqqi.assinatura")

CAMPOS_DADOS = ("razao_social", "documento", "email_cobranca", "telefone")
ABERTAS = ("pendente", "vencida")
HISTORICO = 12
PLANO_DO_TESTE = "profissional"  # o plano de quem está no teste (e de quem saiu da assinatura sem nunca pagar)
FORA_DO_AR = ("indisponivel", "configuracao")  # falhas em que as próximas chamadas também falhariam

MSG_INDISPONIVEL = "A cobrança está temporariamente indisponível. Tente de novo em alguns minutos."
MSG_NAO_CONFIGURADA = "A cobrança online ainda não está disponível. Fale com a equipe Toqqi."
MSG_RECUSADO = "O Asaas recusou os dados. Confira e tente de novo."
CAMPOS_ASAAS = {
    "invalid_cpfCnpj": ("documento", "O Asaas recusou este CPF/CNPJ. Confira os números."),
    "invalid_email": ("email_cobranca", "O Asaas recusou este e-mail. Confira o endereço."),
    "invalid_mobilePhone": ("telefone", "O Asaas recusou este telefone. Informe um número com DDD."),
    "invalid_phone": ("telefone", "O Asaas recusou este telefone. Informe um número com DDD."),
}


# ---- erros -----------------------------------------------------------------------------

def erro_asaas(f: asaas.FalhaAsaas) -> AppError:
    """Recusado → 422 `cobranca_recusada` (CPF/CNPJ, e-mail e telefone no campo; o resto na mensagem, com a descrição
    do Asaas); configuração, indisponível ou não encontrado → 503 `cobranca_indisponivel`."""
    if f.tipo != "recusado":
        return indisponivel()
    campos: dict[str, str] = {}
    gerais: list[str] = []
    for codigo, descricao in f.erros:
        if codigo in CAMPOS_ASAAS:
            campo, msg = CAMPOS_ASAAS[codigo]
            campos.setdefault(campo, msg)
        elif descricao and descricao not in gerais:
            gerais.append(descricao)
    mensagem = " ".join(gerais) or ("Confira os campos destacados." if campos else MSG_RECUSADO)
    return AppError(422, "cobranca_recusada", mensagem, campos)


def indisponivel() -> AppError:
    return AppError(503, "cobranca_indisponivel", MSG_INDISPONIVEL)


def nao_configurada() -> AppError:
    return AppError(503, "cobranca_indisponivel", MSG_NAO_CONFIGURADA)


def sem_assinatura() -> AppError:
    return AppError(409, "sem_assinatura", "Sua conta não tem assinatura ativa.")


# ---- consultas e formato ---------------------------------------------------------------

def _agora_utc() -> datetime:
    return relogio.agora().astimezone(timezone.utc)


def filtro_ambiente():
    """Assinaturas do ambiente da chave atual (sem chave configurada: todas)."""
    amb = asaas.ambiente()
    return Assinatura.ambiente == amb if amb is not None else true()


def ids_do_ambiente():
    return select(Assinatura.id).where(filtro_ambiente())


def assinatura_ativa(s: Session, conta_id: int) -> Assinatura | None:
    """A assinatura ativa da conta no ambiente da chave atual (a de outro ambiente não existe para ela)."""
    return s.scalar(select(Assinatura).where(Assinatura.conta_id == conta_id, Assinatura.situacao == "ativa",
                                             filtro_ambiente()))


def ativa_de_outro_ambiente(s: Session, conta_id: int) -> Assinatura | None:
    amb = asaas.ambiente()
    if amb is None:
        return None
    return s.scalar(select(Assinatura).where(Assinatura.conta_id == conta_id, Assinatura.situacao == "ativa",
                                             Assinatura.ambiente != amb))


def trava(conta_id: int) -> str:
    return f"assinatura:{conta_id}"


def travar_conta(s: Session, conta_id: int) -> Conta | None:
    """`assinatura:{conta}` e a linha da conta (FOR NO KEY UPDATE) até o fim da transação."""
    travar(s, trava(conta_id))
    return s.get(Conta, conta_id, with_for_update={"key_share": True})


def descricao(plano: str) -> str:
    return f"Toqqi – plano {NOMES[plano]}"


def referencia(conta_id: int) -> str:
    return f"toqqi-conta-{conta_id}"


def plano_do_valor(valor: Decimal | None) -> str | None:
    return next((p for p, v in PRECOS.items() if v == valor), None)


def situacao_exibida(c: Cobranca, hoje: date) -> str:
    """Pendente com o vencimento já passado sai como vencida (o Asaas marca na madrugada seguinte)."""
    return "vencida" if c.situacao == "pendente" and c.vencimento < hoje else c.situacao


def _dados_json(a: Assinatura) -> dict:
    return {c: getattr(a, c) for c in CAMPOS_DADOS}


def _assinatura_json(a: Assinatura) -> dict:
    return {"plano": a.plano, "valor": a.valor, "situacao": a.situacao, "criada_em": a.criada_em,
            "cancelada_em": a.cancelada_em, "primeiro_vencimento": a.primeiro_vencimento, "dados": _dados_json(a)}


def _cobranca_json(c: Cobranca, hoje: date) -> dict:
    return {"valor": c.valor, "vencimento": c.vencimento, "situacao": situacao_exibida(c, hoje), "forma": c.forma,
            "pago_em": c.pago_em, "link": c.link}


def _fatura_json(c: Cobranca, hoje: date) -> dict:
    return {"valor": c.valor, "vencimento": c.vencimento, "situacao": situacao_exibida(c, hoje), "link": c.link}


def _telefone_ou_nada(v: str | None) -> str | None:
    try:
        return normalizar_telefone(v) if v else None
    except ValueError:
        return None


def dados_sugeridos(s: Session, conta: Conta, usuario_id: int, email: str) -> dict:
    """Dos dados da empresa (razão social, ou o nome; CPF/CNPJ; telefone) e do admin (e-mail; telefone do cadastro
    quando a empresa não tem)."""
    telefone = conta.telefone or _telefone_ou_nada(s.scalar(select(Usuario.telefone).where(Usuario.id == usuario_id)))
    return {"razao_social": conta.razao_social or conta.nome, "documento": conta.documento, "email_cobranca": email,
            "telefone": telefone}


def estado(s: Session, conta: Conta, usuario_id: int, email: str) -> dict:
    """Formato de GET /assinatura (e das rotas que mudam a assinatura). Só o ambiente da chave atual."""
    agora = relogio.agora()
    hoje = dia_de(agora)
    ativa = assinatura_ativa(s, conta.id)
    aberta = None
    if ativa is not None:
        aberta = s.scalar(select(Cobranca).where(Cobranca.conta_id == conta.id, Cobranca.assinatura_id == ativa.id,
                                                 Cobranca.situacao.in_(ABERTAS))
                          .order_by(Cobranca.vencimento, Cobranca.id).limit(1))
    recentes = s.scalars(select(Cobranca).where(Cobranca.conta_id == conta.id,
                                                Cobranca.assinatura_id.in_(ids_do_ambiente()))
                         .order_by(Cobranca.vencimento.desc(), Cobranca.id.desc()).limit(HISTORICO)).all()
    return {
        "conta": {"situacao": conta.situacao, "plano": conta.plano, "teste_ate": conta.teste_ate,
                  "pago_ate": conta.pago_ate, "atrasada_desde": conta.atrasada_desde,
                  "liberada": regras.liberada(conta, agora), "pausa_em": regras.pausa_em(conta, agora)},
        "contatos_ativos": contatos_ativos(s),
        "disponivel": asaas.disponivel(),
        "planos": planos_json(),
        "dados_sugeridos": dados_sugeridos(s, conta, usuario_id, email),
        "assinatura": _assinatura_json(ativa) if ativa is not None else None,
        "fatura_aberta": _fatura_json(aberta, hoje) if aberta is not None else None,
        "cobrancas": [_cobranca_json(c, hoje) for c in recentes],
    }


# ---- situação da conta -------------------------------------------------------------------

def _situacao(s: Session, conta: Conta, ativa: Assinatura | None, agora: datetime) -> str:
    """Seção 3 do contrato, com duas proteções: só tem a carência de 7 dias (`atrasada`) e só fica `ativa` sem
    pagamento nesta assinatura quem estava coberto quando ela começou (pelo teste ou por um período pago que ela
    continua). Quem assina sem teste válido e não paga não ganha envios por estar em atraso.
    Sem assinatura ativa: período pago valendo → `cancelada`; senão teste valendo → `teste`; senão já pagou →
    `cancelada`; senão `teste_expirado`."""
    hoje = dia_de(agora)
    if ativa is None:
        if conta.pago_ate is not None and conta.pago_ate >= hoje:
            return "cancelada"
        if conta.teste_ate is not None and agora < conta.teste_ate:
            return "teste"
        return "cancelada" if conta.pago_ate is not None else "teste_expirado"
    paga_nesta = s.scalar(select(exists().where(Cobranca.assinatura_id == ativa.id, Cobranca.situacao == "paga")))
    continua_paga = conta.pago_ate is not None and ativa.primeiro_vencimento <= conta.pago_ate + timedelta(days=1)
    if conta.atrasada_desde is not None and (paga_nesta or continua_paga or assinou_no_teste(conta)):
        return "atrasada"
    if paga_nesta or continua_paga:
        return "ativa"
    fim = fim_do_teste(conta)
    if fim is not None and agora < fim:
        return "teste"
    return "cancelada" if conta.pago_ate is not None else "teste_expirado"


def recalcular(s: Session, conta: Conta) -> tuple[str, str]:
    """Decide a situação da conta depois de qualquer mudança (assinar, cancelar, aviso, tarefa, plataforma) e refaz
    `pago_ate` (nunca diminui: maior vencimento pago + 1 mês − 1 dia, só de assinaturas do ambiente atual),
    `atrasada_desde` (vencimento mais antigo em atraso da assinatura ativa: vencida, ou pendente com o vencimento já
    passado) e `primeiro_vencimento` (o da assinatura ativa). Quem fica sem assinatura sem nunca ter pago volta ao
    plano do teste. `cortesia` não muda por cobrança. Chame com a conta travada. Devolve (antes, depois)."""
    anterior = conta.situacao
    agora = relogio.agora()
    hoje = dia_de(agora)
    ativa = assinatura_ativa(s, conta.id)
    pagas = s.scalars(select(Cobranca.vencimento).where(Cobranca.conta_id == conta.id, Cobranca.situacao == "paga",
                                                        Cobranca.assinatura_id.in_(ids_do_ambiente()))).all()
    if pagas:
        fim = max(fim_do_periodo_pago(v) for v in pagas)
        conta.pago_ate = max(conta.pago_ate, fim) if conta.pago_ate else fim
    conta.primeiro_vencimento = ativa.primeiro_vencimento if ativa is not None else None
    atrasadas = []
    if ativa is not None:
        atrasadas = s.scalars(select(Cobranca.vencimento).where(
            Cobranca.conta_id == conta.id, Cobranca.assinatura_id == ativa.id,
            or_(Cobranca.situacao == "vencida", and_(Cobranca.situacao == "pendente", Cobranca.vencimento < hoje)),
        )).all()
    conta.atrasada_desde = min(atrasadas) if atrasadas else None
    if conta.situacao != "cortesia":
        conta.situacao = _situacao(s, conta, ativa, agora)
        if (ativa is None and conta.pago_ate is None and conta.plano != PLANO_DO_TESTE
                and ativa_de_outro_ambiente(s, conta.id) is None):
            conta.plano = PLANO_DO_TESTE  # cancelou (ou perdeu a assinatura) sem nunca pagar: o plano do teste
    s.flush()
    return anterior, conta.situacao


def limpar_outro_ambiente(s: Session, conta: Conta) -> bool:
    """Chave de produção: a assinatura e o cliente de sandbox não existem para ela. Cancela aqui a assinatura ativa de
    sandbox (sem chamar o Asaas), esquece o cliente de sandbox, zera `pago_ate` e `atrasada_desde` (pagamento de
    sandbox não vale em produção; `recalcular` refaz com os de produção) e audita. Com a chave de sandbox, as linhas de
    produção não são tocadas (seria a chave errada; a tarefa registra o erro). Devolve se mudou algo (quem chamou
    recalcula)."""
    if asaas.ambiente() != "producao":
        return False
    ativa = s.scalar(select(Assinatura).where(Assinatura.conta_id == conta.id, Assinatura.situacao == "ativa",
                                              Assinatura.ambiente == "sandbox"))
    cliente = conta.asaas_ambiente == "sandbox"
    if ativa is None and not cliente:
        return False
    detalhe = {"de": "sandbox", "para": "producao", "assinatura_cancelada": ativa is not None,
               "pago_ate_anterior": conta.pago_ate.isoformat() if conta.pago_ate else None}
    if ativa is not None:
        encerrar(s, ativa, None)
    if cliente:
        conta.asaas_cliente_id = conta.asaas_ambiente = None
    conta.pago_ate = conta.atrasada_desde = None
    registrar(s, "ambiente_asaas_trocado", "atencao", detalhe, conta_id=conta.id)
    s.flush()
    return True


# ---- cobranças locais --------------------------------------------------------------------

def _meio_dia_utc(d: date) -> datetime:
    """Data do pagamento (o Asaas só informa o dia) às 12:00 de São Paulo, em UTC."""
    return datetime.combine(d, time(12), tzinfo=relogio.FUSO).astimezone(timezone.utc)


def _auditar_mudanca(s: Session, c: Cobranca) -> None:
    detalhe = {"valor": str(c.valor), "vencimento": c.vencimento.isoformat()}
    if c.situacao == "paga":
        registrar(s, "pagamento_confirmado", "info", {**detalhe, "forma": c.forma}, conta_id=c.conta_id)
    elif c.situacao == "vencida":
        registrar(s, "pagamento_vencido", "atencao", detalhe, conta_id=c.conta_id)
    elif c.situacao == "estornada":
        registrar(s, "pagamento_estornado", "atencao", detalhe, conta_id=c.conta_id)


def sincronizar_cobranca(s: Session, conta_id: int, pagamento_id: str, pagamento: dict | None,
                         assinatura: Assinatura | None = None) -> bool:
    """Grava ou atualiza a cobrança local com o que o Asaas diz (`pagamento` None = o Asaas não acha mais: removida).
    Uma cobrança nova só entra se for de uma assinatura da conta. Audita confirmação, vencimento e estorno quando a
    situação muda. Devolve se a situação mudou."""
    c = s.scalar(select(Cobranca).where(Cobranca.conta_id == conta_id, Cobranca.asaas_id == pagamento_id))
    if pagamento is None:
        if c is None or c.situacao == "removida":
            return False
        c.situacao = "removida"
        c.atualizada_em = _agora_utc()
        s.flush()
        return True
    nova = asaas.situacao(pagamento)
    vencimento = asaas.vencimento(pagamento)
    valor = asaas.valor(pagamento.get("value"))
    anterior = c.situacao if c is not None else None
    if c is None:
        sub = pagamento.get("subscription")
        if assinatura is None and isinstance(sub, str):
            assinatura = s.scalar(select(Assinatura).where(Assinatura.conta_id == conta_id, Assinatura.asaas_id == sub))
        if assinatura is None or vencimento is None or valor is None:
            return False
        c = Cobranca(conta_id=conta_id, assinatura_id=assinatura.id, asaas_id=pagamento_id, valor=valor,
                     vencimento=vencimento, situacao=nova or "pendente", criada_em=_agora_utc())
        s.add(c)
    elif nova is None:
        log.warning("Asaas: situação desconhecida na cobrança %s; mantida como %s.", pagamento_id, c.situacao)
    if nova is not None:
        c.situacao = nova
    if vencimento is not None:
        c.vencimento = vencimento
    if valor is not None:
        c.valor = valor
    liquido = asaas.valor(pagamento.get("netValue"))
    if liquido is not None:
        c.valor_liquido = liquido
    status = pagamento.get("status")
    if isinstance(status, str):
        c.situacao_asaas = status[:60]
    c.forma = asaas.forma(pagamento)
    pago = asaas.data_do_pagamento(pagamento)
    c.pago_em = _meio_dia_utc(pago) if pago is not None else None
    c.link = asaas.link(pagamento) or c.link
    c.atualizada_em = _agora_utc()
    s.flush()
    if c.situacao != anterior:
        _auditar_mudanca(s, c)
        return True
    return False


def sincronizar_lista(s: Session, conta_id: int, assinatura: Assinatura, pagamentos: list[dict]) -> None:
    for p in pagamentos:
        pid = p.get("id")
        if isinstance(pid, str) and 1 <= len(pid) <= 100:
            sincronizar_cobranca(s, conta_id, pid, p, assinatura)


def buscar_cobrancas(s: Session, conta_id: int, a: Assinatura) -> None:
    """Depois de assinar, adotar ou trocar de plano: traz as faturas da assinatura (sem elas, o aviso do Asaas e a
    conferência diária completam)."""
    try:
        pagamentos = asaas.cobrancas_da_assinatura(a.asaas_id)
    except asaas.FalhaAsaas as f:
        log.warning("Asaas: não foi possível buscar as cobranças da assinatura da conta %s (%s).", conta_id, f.detalhe)
        return
    sincronizar_lista(s, conta_id, a, pagamentos)


def ajustar_primeiro_vencimento(s: Session, a: Assinatura) -> None:
    """Assinatura adotada: o primeiro vencimento é o da fatura mais antiga dela no Asaas."""
    primeiro = s.scalar(select(func.min(Cobranca.vencimento)).where(Cobranca.assinatura_id == a.id))
    if primeiro is not None:
        a.primeiro_vencimento = primeiro
        s.flush()


def encerrar(s: Session, a: Assinatura, por: int | None) -> None:
    """Marca a assinatura cancelada e as faturas em aberto dela como removidas (o Asaas apaga junto)."""
    a.situacao = "cancelada"
    a.cancelada_em = _agora_utc()
    a.cancelada_por = por
    a.nao_encontrada_desde = None
    s.execute(update(Cobranca).where(Cobranca.assinatura_id == a.id, Cobranca.situacao.in_(ABERTAS))
              .values(situacao="removida", atualizada_em=_agora_utc()))
    s.flush()


def remover_no_asaas(asaas_id: str) -> None:
    """Remove a assinatura no Asaas; já removida lá (404) conta como removida. Qualquer outra falha → 503 (quem
    chamou desfaz a transação: nada muda)."""
    if not asaas.disponivel():
        raise nao_configurada()
    try:
        asaas.remover_assinatura(asaas_id)
    except asaas.FalhaAsaas as f:
        if f.tipo != "nao_encontrado":
            raise indisponivel() from None


def remover_vivas_no_asaas(conta: Conta) -> None:
    """Exclusão da conta: nenhuma assinatura com a referência dela segue viva no Asaas (uma que um pedido que esgotou
    o tempo criou, por exemplo). Só para conta com cliente no ambiente atual; falhou → 503 (nada muda)."""
    if not conta.asaas_cliente_id or conta.asaas_ambiente != asaas.ambiente():
        return
    try:
        for a in asaas.listar_assinaturas(referencia(conta.id)):
            if asaas.assinatura_viva(a):
                remover_no_asaas(a["id"])
    except asaas.FalhaAsaas:
        raise indisponivel() from None


# ---- remoções e conciliação -------------------------------------------------------------------

def registrar_remocao(s: Session, asaas_id: str, motivo: str, erro: str, conta_id: int | None) -> None:
    """Assinatura que precisa sair do Asaas e não saiu agora: a tarefa `assinaturas` tenta de novo."""
    valores = {"asaas_id": asaas_id, "ambiente": asaas.ambiente() or "sandbox", "motivo": motivo[:60],
               "erro": erro[:300], "conta_id": conta_id}
    s.execute(insert(AsaasRemocao).values(**valores).on_conflict_do_nothing(index_elements=[AsaasRemocao.asaas_id]))


def registrar_remocao_avulsa(conta_id: int | None, asaas_id: str, motivo: str, erro: str) -> None:
    """`registrar_remocao` numa transação própria (a de quem chamou já foi desfeita)."""
    try:
        with (em_conta(conta_id) if conta_id is not None else modo_sistema()) as s:
            registrar_remocao(s, asaas_id, motivo, erro, conta_id)
    except Exception:  # noqa: BLE001 - a conferência diária ainda acha a assinatura pela referência da conta
        log.exception("Assinatura: não foi possível registrar a remoção pendente da assinatura %s no Asaas.", asaas_id)


def remover_sobrando(s: Session, conta_id: int, sub: dict, motivo: str) -> bool:
    """Remove no Asaas uma assinatura com a referência da conta que não pode ficar viva (duplicada, cancelada aqui ou
    com a remoção pendente) e audita. Falhou: fica em `asaas_remocoes` (a tarefa tenta de novo) e o Asaas fora do ar
    (ou a chave recusada) interrompe quem chamou. Devolve se saiu."""
    valor = asaas.valor(sub.get("value"))
    try:
        asaas.remover_assinatura(sub["id"])
    except asaas.FalhaAsaas as f:
        if f.tipo != "nao_encontrado":
            registrar_remocao(s, sub["id"], motivo, f.detalhe, conta_id)
            log.error("Assinaturas: não foi possível remover no Asaas a assinatura %s da conta %s (%s); a tarefa "
                      "tenta de novo.", sub["id"], conta_id, f.detalhe)
            if f.tipo in FORA_DO_AR:
                raise
            return False
    s.execute(update(AsaasRemocao).where(AsaasRemocao.asaas_id == sub["id"], AsaasRemocao.removida_em.is_(None))
              .values(removida_em=func.now(), erro=None))
    registrar(s, "assinatura_removida_no_asaas", "atencao",
              {"motivo": motivo, "valor": str(valor) if valor is not None else None}, conta_id=conta_id)
    return True


def assinaturas_no_asaas(s: Session, conta: Conta) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Assinaturas vivas no Asaas com a referência da conta, fora as ativas daqui: (desconhecidas, da mais nova para a
    mais antiga; [(assinatura, motivo)] a remover: as canceladas aqui e as com a remoção pendente, que nunca são
    adotadas)."""
    vivas = [a for a in asaas.listar_assinaturas(referencia(conta.id)) if asaas.assinatura_viva(a)]
    if not vivas:
        return [], []
    ids = [a["id"] for a in vivas]
    locais = dict(s.execute(select(Assinatura.asaas_id, Assinatura.situacao).where(
        Assinatura.conta_id == conta.id, filtro_ambiente(), Assinatura.asaas_id.in_(ids))).all())
    pendentes = dict(s.execute(select(AsaasRemocao.asaas_id, AsaasRemocao.motivo).where(
        AsaasRemocao.asaas_id.in_(ids), AsaasRemocao.removida_em.is_(None))).all())
    remover = [(a, pendentes[a["id"]]) for a in vivas if a["id"] in pendentes]
    remover += [(a, "cancelada_aqui") for a in vivas if locais.get(a["id"]) == "cancelada" and a["id"] not in pendentes]
    desconhecidas = sorted((a for a in vivas if a["id"] not in locais and a["id"] not in pendentes),
                           key=lambda a: (str(a.get("dateCreated") or ""), a["id"]), reverse=True)
    return desconhecidas, remover


def conciliar_para_assinar(s: Session, conta: Conta, valor: Decimal) -> dict | None:
    """Antes de criar a assinatura (e depois de um tempo esgotado ao criar): a desconhecida mais nova com o valor
    pedido é devolvida para ser adotada (um pedido anterior chegou a criá-la); as outras desconhecidas, as canceladas
    aqui que seguem vivas lá e as com a remoção pendente são removidas."""
    desconhecidas, remover = assinaturas_no_asaas(s, conta)
    adotar = next((a for a in desconhecidas if asaas.valor(a.get("value")) == valor), None)
    for a in desconhecidas:
        if a is not adotar:
            remover_sobrando(s, conta.id, a, "duplicada")
    for a, motivo in remover:
        remover_sobrando(s, conta.id, a, motivo)
    return adotar


# ---- rotas -------------------------------------------------------------------------------

def _cliente(dados, conta_id: int) -> asaas.Cliente:
    return asaas.Cliente(nome=dados.razao_social, documento=dados.documento, email=dados.email_cobranca,
                         telefone=dados.telefone, referencia=referencia(conta_id))


def _conferir_limite(s: Session, conta: Conta, plano: str, acao: str, travar_inclusoes: bool = True) -> None:
    """422 `limite_do_plano` se a conta tem mais contatos ativos que o plano permite. Pega antes (sempre) a trava das
    inclusões de contatos, a mesma do gatilho do limite: ela fica até o fim da transação que grava o plano, e a
    inclusão que esperou lê o plano novo. `travar_inclusoes=False` só para a conferência prévia (sem mudar o plano)."""
    if travar_inclusoes:
        travar_contatos(s, conta.id)
    limite = limite_contatos(plano, conta.situacao)
    if limite is None:
        return
    ativos = contatos_ativos(s)
    if ativos > limite:
        raise AppError(422, "limite_do_plano",
                       f"Você tem {numero(ativos)} contatos ativos; o plano {NOMES[plano]} permite até "
                       f"{numero(limite)}. Desative contatos antes de {acao}.", {"limite": str(limite)})


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return estado(s, s.get(Conta, ctx.conta_id), ctx.usuario_id, ctx.email)


def _pode_assinar(s: Session, conta: Conta) -> None:
    if conta.situacao == "cortesia":
        raise AppError(409, "cortesia", "Sua conta é cortesia: não precisa assinar.")
    if assinatura_ativa(s, conta.id) is not None:
        raise AppError(409, "ja_assinada", "Sua conta já tem uma assinatura ativa.")
    outra = ativa_de_outro_ambiente(s, conta.id)
    if outra is not None and outra.ambiente != "sandbox":
        log.error("Assinatura: a conta %s tem assinatura ativa de produção e a chave do Asaas é de sandbox. Confira "
                  "ASAAS_API_KEY.", conta.id)
        raise indisponivel()


def _cliente_pela_referencia(cliente: asaas.Cliente) -> str | None:
    """Cliente já criado para a conta (num pedido que esgotou o tempo, ou cujo id se perdeu), atualizado."""
    for c in asaas.buscar_clientes(cliente.referencia):
        try:
            asaas.atualizar_cliente(c["id"], cliente)
        except asaas.FalhaAsaas as f:
            if f.tipo != "nao_encontrado":
                raise
            continue
        return c["id"]
    return None


def _cliente_no_asaas(conta: Conta, cliente: asaas.Cliente, amb: str) -> str:
    """O cliente guardado (deste ambiente), atualizado; senão um com a referência da conta; senão um novo. Se a
    criação esgotar o tempo, procura de novo (ela pode ter passado)."""
    cliente_id = conta.asaas_cliente_id if conta.asaas_ambiente == amb else None
    if cliente_id:
        try:
            asaas.atualizar_cliente(cliente_id, cliente)
            return cliente_id
        except asaas.FalhaAsaas as f:
            if f.tipo != "nao_encontrado":
                raise
    existente = _cliente_pela_referencia(cliente)
    if existente is not None:
        return existente
    try:
        return asaas.criar_cliente(cliente)
    except asaas.FalhaAsaas as f:
        if f.tipo != "indisponivel":
            raise
        falha = f
    try:
        existente = _cliente_pela_referencia(cliente)
    except asaas.FalhaAsaas:
        existente = None
    if existente is None:
        raise falha
    log.warning("Asaas: a criação do cliente da conta %s esgotou o tempo, mas ele foi criado lá; reaproveitado.",
                conta.id)
    return existente


def _garantir_cliente(ctx: Contexto, dados) -> None:
    """1ª fase de assinar: o cliente no Asaas fica gravado na conta (com o ambiente) mesmo se a assinatura falhar."""
    falha: asaas.FalhaAsaas | None = None
    with em_conta(ctx.conta_id) as s:
        conta = travar_conta(s, ctx.conta_id)
        _pode_assinar(s, conta)
        _conferir_limite(s, conta, dados.plano, "assinar", travar_inclusoes=False)  # a que vale é a da 2ª fase
        conta.asaas_conferida_em = None  # se o processo cair no meio, a próxima conferência concilia esta conta
        amb = asaas.ambiente()
        try:
            cliente_id = _cliente_no_asaas(conta, _cliente(dados, conta.id), amb)
        except asaas.FalhaAsaas as f:
            falha = f
        else:
            conta.asaas_cliente_id, conta.asaas_ambiente = cliente_id, amb
    if falha is not None:
        raise erro_asaas(falha)


def _desfazer_no_asaas(conta_id: int, asaas_id: str) -> None:
    """A gravação falhou depois de criar (ou adotar) a assinatura no Asaas: sem ela gravada aqui, o Asaas cobraria sem
    a conta saber. Remove lá; se não der, fica em `asaas_remocoes` para a tarefa tentar de novo."""
    try:
        asaas.remover_assinatura(asaas_id)
    except asaas.FalhaAsaas as f:
        if f.tipo != "nao_encontrado":
            log.error("Assinatura: a gravação falhou depois de criar a assinatura %s no Asaas e a remoção lá também "
                      "falhou (%s); a tarefa `assinaturas` tenta de novo.", asaas_id, f.detalhe)
            registrar_remocao_avulsa(conta_id, asaas_id, "gravacao_falhou", f.detalhe)
            return
    log.warning("Assinatura: a gravação falhou depois de criar a assinatura %s no Asaas; ela foi removida lá.",
                asaas_id)


def _criar_assinatura(ctx: Contexto, dados) -> dict:
    """2ª fase de assinar (ver `assinar`)."""
    amb = asaas.ambiente()
    valor = PRECOS[dados.plano]
    nova: str | None = None  # criada (ou adotada) no Asaas e ainda não gravada aqui
    falha: asaas.FalhaAsaas | None = None
    resultado: dict = {}
    try:
        with em_conta(ctx.conta_id) as s:
            conta = travar_conta(s, ctx.conta_id)
            _pode_assinar(s, conta)
            if not conta.asaas_cliente_id or conta.asaas_ambiente != amb:
                raise indisponivel()  # a chave mudou entre as duas fases
            if limpar_outro_ambiente(s, conta):
                recalcular(s, conta)
            vencimento = regras.primeiro_vencimento(conta)
            adotada = None
            try:
                adotada = conciliar_para_assinar(s, conta, valor)
                _conferir_limite(s, conta, dados.plano, "assinar")  # trava as inclusões de contatos até gravar
                if adotada is None:
                    try:
                        nova = asaas.criar_assinatura(conta.asaas_cliente_id, valor, vencimento,
                                                      descricao(dados.plano), referencia(conta.id))
                    except asaas.FalhaAsaas as f:
                        if f.tipo != "indisponivel":
                            raise
                        adotada = _depois_do_tempo_esgotado(s, conta, valor, f)
                if adotada is not None:
                    nova = adotada["id"]
                    vencimento = asaas.data(adotada.get("nextDueDate")) or vencimento
            except asaas.FalhaAsaas as f:
                falha = f
            else:
                a = Assinatura(conta_id=conta.id, asaas_id=nova, ambiente=amb, plano=dados.plano, valor=valor,
                               situacao="ativa", razao_social=dados.razao_social, documento=dados.documento,
                               email_cobranca=dados.email_cobranca, telefone=dados.telefone,
                               primeiro_vencimento=vencimento, criada_em=_agora_utc(), criada_por=ctx.usuario_id)
                s.add(a)
                s.flush()
                conta.plano = dados.plano
                buscar_cobrancas(s, conta.id, a)
                if adotada is not None:
                    ajustar_primeiro_vencimento(s, a)
                    log.warning("Assinatura: a conta %s adotou a assinatura %s, criada no Asaas por um pedido "
                                "anterior.", conta.id, nova)
                recalcular(s, conta)
                registrar(s, "assinatura_criada", "info", {"plano": dados.plano, "valor": str(valor)},
                          usuario_id=ctx.usuario_id)
                resultado = estado(s, conta, ctx.usuario_id, ctx.email)
    except Exception:
        if nova is not None and falha is None:
            _desfazer_no_asaas(ctx.conta_id, nova)
        raise
    if falha is not None:
        raise erro_asaas(falha)
    return resultado


def _depois_do_tempo_esgotado(s: Session, conta: Conta, valor: Decimal, falha: asaas.FalhaAsaas) -> dict:
    """A criação esgotou o tempo (ou o Asaas caiu): ela pode ter passado. Lista de novo e adota a que chegou a ser
    criada; sem ela (ou sem conseguir listar), a falha segue (503)."""
    try:
        adotada = conciliar_para_assinar(s, conta, valor)
    except asaas.FalhaAsaas:
        adotada = None
    if adotada is None:
        raise falha
    return adotada


def assinar(ctx: Contexto, dados) -> dict:
    """Em duas transações (o cliente fica gravado mesmo se a assinatura falhar):
    1. o cliente no Asaas: o guardado (deste ambiente), senão um com a referência da conta, senão um novo;
    2. a assinatura: concilia (adota a que um pedido anterior criou, remove as que sobram), cria com o primeiro
       vencimento da regra (tempo esgotado: lista de novo e adota se ela chegou a ser criada), busca a primeira fatura,
       troca o plano da conta e recalcula. Se a gravação falhar depois de criar no Asaas, ela é removida lá (e, se não
       der, fica para a tarefa)."""
    if not asaas.disponivel():
        raise nao_configurada()
    _garantir_cliente(ctx, dados)
    return _criar_assinatura(ctx, dados)


def _valor_no_asaas_e(asaas_id: str, valor: Decimal) -> bool:
    try:
        return asaas.valor(asaas.obter_assinatura(asaas_id).get("value")) == valor
    except asaas.FalhaAsaas:
        return False


def trocar_plano(ctx: Contexto, plano: str) -> dict:
    """Muda o valor no Asaas (também das faturas em aberto) e o plano da conta (e o limite de contatos) na hora. Tempo
    esgotado no Asaas: confere a assinatura lá; com o valor novo já gravado, conclui aqui (senão 503)."""
    mudou_no_asaas: tuple[str, str, Decimal] | None = None
    try:
        with em_conta(ctx.conta_id) as s:
            conta = travar_conta(s, ctx.conta_id)
            a = assinatura_ativa(s, conta.id)
            if a is None:
                raise sem_assinatura()
            if a.plano != plano:
                _conferir_limite(s, conta, plano, "trocar")
                if not asaas.disponivel():
                    raise nao_configurada()
                valor = PRECOS[plano]
                try:
                    asaas.atualizar_assinatura(a.asaas_id, valor, descricao(plano))
                except asaas.FalhaAsaas as f:
                    if f.tipo != "indisponivel" or not _valor_no_asaas_e(a.asaas_id, valor):
                        raise erro_asaas(f) from None
                    log.warning("Asaas: a troca de plano da conta %s esgotou o tempo, mas o valor novo já está lá.",
                                conta.id)
                mudou_no_asaas = (a.asaas_id, a.plano, a.valor)
                de = a.plano
                a.plano, a.valor = plano, valor
                conta.plano = plano
                s.execute(update(Cobranca).where(Cobranca.assinatura_id == a.id, Cobranca.situacao == "pendente")
                          .values(valor=valor, atualizada_em=_agora_utc()))
                buscar_cobrancas(s, conta.id, a)
                recalcular(s, conta)
                registrar(s, "plano_alterado", "info", {"de": de, "para": plano}, usuario_id=ctx.usuario_id)
            resultado = estado(s, conta, ctx.usuario_id, ctx.email)
    except Exception:
        if mudou_no_asaas is not None:  # a gravação falhou: volta o valor no Asaas
            asaas_id, plano_antes, valor_antes = mudou_no_asaas
            try:
                asaas.atualizar_assinatura(asaas_id, valor_antes, descricao(plano_antes))
            except asaas.FalhaAsaas as f:
                log.error("Assinatura: o plano mudou no Asaas (%s) e não foi gravado aqui; não foi possível voltar "
                          "(%s). A conferência diária volta o valor do Asaas para o daqui.", asaas_id, f.detalhe)
        raise
    return resultado


def _igual(campo: str, atual: str, novo: str) -> bool:
    return atual.lower() == novo.lower() if campo == "email_cobranca" else atual == novo  # e-mail é citext


def alterar_dados(ctx: Contexto, dados) -> dict:
    """Atualiza o cliente no Asaas e os dados da assinatura. Sem mudança, não chama o Asaas nem audita."""
    with em_conta(ctx.conta_id) as s:
        conta = travar_conta(s, ctx.conta_id)
        a = assinatura_ativa(s, conta.id)
        if a is None:
            raise sem_assinatura()
        novos = {c: getattr(dados, c) for c in CAMPOS_DADOS}
        mudaram = [c for c in CAMPOS_DADOS if not _igual(c, getattr(a, c), novos[c])]
        if mudaram:
            if not asaas.disponivel():
                raise nao_configurada()
            if not conta.asaas_cliente_id or conta.asaas_ambiente != asaas.ambiente():
                raise indisponivel()
            try:
                asaas.atualizar_cliente(conta.asaas_cliente_id, _cliente(dados, conta.id))
            except asaas.FalhaAsaas as f:
                raise erro_asaas(f) from None
            for c in mudaram:
                setattr(a, c, novos[c])
            registrar(s, "dados_cobranca_alterados", "info", {"campos": mudaram}, usuario_id=ctx.usuario_id)
            s.flush()
        return estado(s, conta, ctx.usuario_id, ctx.email)


def cancelar(ctx: Contexto) -> dict:
    """Remove a assinatura no Asaas (que apaga as faturas em aberto), marca cancelada e recalcula: o uso segue até o
    fim do período pago ou do teste (o que for mais tarde); quem cancela sem nunca ter pago volta ao plano do
    teste."""
    with em_conta(ctx.conta_id) as s:
        conta = travar_conta(s, ctx.conta_id)
        a = assinatura_ativa(s, conta.id)
        if a is None:
            raise sem_assinatura()
        remover_no_asaas(a.asaas_id)
        encerrar(s, a, ctx.usuario_id)
        recalcular(s, conta)
        registrar(s, "assinatura_cancelada", "atencao", {"plano": a.plano}, usuario_id=ctx.usuario_id)
        return estado(s, conta, ctx.usuario_id, ctx.email)
