"""Conferência com o Asaas, conciliação em segundo plano e a tarefa `assinaturas` (agendador; primeira em `tudo`, para
a liberação valer antes dos envios):
1. recalcula as contas cuja situação muda só pela data;
2. com o Asaas configurado: descarta o que era de sandbox quando a chave passa a ser de produção; tenta de novo as
   remoções pendentes no Asaas; reprocessa os avisos do webhook; e, a partir das 6h, faz a conferência diária.

Conferência diária (uma vez por dia por conta com assinatura ativa ou cancelada há menos de 40 dias no ambiente atual,
e por conta com cliente no Asaas ainda não conferida — um assinar que falhou ou caiu no meio):
- concilia: assinatura viva no Asaas com a referência da conta e desconhecida aqui é adotada (conta sem assinatura
  ativa, que não é cortesia, com o valor de hoje e a descrição de um mesmo plano: `servico.plano_da_assinatura`) ou
  removida lá (auditoria); a cancelada aqui que segue viva lá é removida;
- assinatura ativa: lida no Asaas — removida, INACTIVE ou EXPIRED → cancelada aqui (auditoria); 404 → log de erro a
  cada dia e, no 3º dia seguido, cancelada aqui (auditoria, atenção); valor diferente do daqui → o do Asaas volta a ser
  o daqui, também nas faturas em aberto (auditoria, atenção); traz as cobranças (pega aviso perdido);
- canceladas há menos de 40 dias: traz as cobranças (pagamento de última hora, estorno);
- recalcula (também quando para no meio) e, com tudo conferido, marca o dia e verifica a sanidade (ativa, paga só até
  mais de 40 dias atrás e sem fatura em aberto → log de erro).
Para no primeiro Asaas fora do ar (ou chave recusada): as próximas também falhariam.
"""
import logging
import re
from datetime import date, time, timedelta

from sqlalchemy import and_, exists, func, or_, select, update

from toqqi.core import asaas, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.log_seguro import descrever_erro
from toqqi.core.planos import travar_contatos
from toqqi.core.texto import normalizar_documento, normalizar_telefone, telefone_canonico
from toqqi.modelos import AsaasRemocao, Assinatura, Cobranca, Conta
from toqqi.modulos.assinatura import servico
from toqqi.modulos.assinatura.regras import dia_de

log = logging.getLogger("toqqi.assinatura")

CONFERENCIA_A_PARTIR = time(6, 0)  # depois do processamento da madrugada do Asaas (vencidas do dia)
DIAS_CONFERIR_CANCELADA = 40
DIAS_NAO_ENCONTRADA = 3  # 404 no 3º dia seguido: cancelada aqui
DIAS_SANIDADE = 40
LOTE = 500
MAX_TENTATIVAS_REMOCAO = 20
RE_REFERENCIA = re.compile(r"toqqi-conta-([1-9][0-9]{0,17})")


def conta_da_referencia(ref) -> int | None:
    """"toqqi-conta-12" → 12; outra referência (de outro sistema) → None."""
    m = RE_REFERENCIA.fullmatch(ref) if isinstance(ref, str) else None
    return int(m.group(1)) if m else None


# ---- datas ---------------------------------------------------------------------------------

def recalcular_pelas_datas() -> int:
    """Contas cuja situação muda só pela data: teste que acabou, fatura pendente que passou do vencimento (o Asaas
    marca como vencida na madrugada seguinte) e período pago que acabou com o teste ainda valendo. Devolve quantos
    testes viraram `teste_expirado`."""
    agora = relogio.agora()
    hoje = dia_de(agora)
    pendente_vencida = exists().where(
        Cobranca.conta_id == Conta.id, Cobranca.situacao == "pendente", Cobranca.vencimento < hoje,
        Cobranca.assinatura_id.in_(select(Assinatura.id).where(Assinatura.situacao == "ativa")))
    with modo_sistema() as s:  # só ids; cada conta é recalculada em em_conta
        ids = s.scalars(select(Conta.id).where(or_(
            and_(Conta.situacao == "teste", or_(Conta.teste_ate.is_(None), Conta.teste_ate <= agora)),
            and_(Conta.situacao.in_(("teste", "ativa")), pendente_vencida),
            and_(Conta.situacao == "cancelada", Conta.pago_ate < hoje, Conta.teste_ate > agora),
        )).order_by(Conta.id)).all()
    expirados = 0
    for conta_id in ids:
        try:
            with em_conta(conta_id) as s:
                conta = servico.travar_conta(s, conta_id)
                antes, depois = servico.recalcular(s, conta)
            if antes == "teste" and depois == "teste_expirado":
                expirados += 1
        except Exception:  # noqa: BLE001 - uma conta não derruba as outras
            log.exception("Assinaturas: erro ao recalcular a conta %s.", conta_id)
    return expirados


# ---- conciliação ------------------------------------------------------------------------------

def _ou_nada(funcao, v) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        return funcao(v)
    except ValueError:
        return None


def _dados_do_cliente(conta: Conta, cliente_id) -> dict | None:
    """Dados de cobrança de uma assinatura adotada: os do cliente no Asaas (criado por nós com os dados que a conta
    informou); o que faltar sai dos dados da empresa. None se ainda faltar algo."""
    c: dict = {}
    if isinstance(cliente_id, str) and cliente_id:
        try:
            c = asaas.obter_cliente(cliente_id)
        except asaas.FalhaAsaas as f:
            if f.tipo in servico.FORA_DO_AR:
                raise
    razao = " ".join(str(c.get("name") or "").split())[:200] or conta.razao_social or conta.nome
    documento = _ou_nada(normalizar_documento, c.get("cpfCnpj")) or conta.documento
    email = c.get("email") if isinstance(c.get("email"), str) else None
    email = email.strip().lower() if email and "@" in email and 3 <= len(email.strip()) <= 254 else conta.email_contato
    telefone = _ou_nada(lambda v: telefone_canonico(normalizar_telefone(v)),
                        c.get("mobilePhone") or c.get("phone")) or conta.telefone
    if not (razao and documento and email and telefone):
        return None
    return {"razao_social": razao, "documento": documento, "email_cobranca": email, "telefone": telefone}


def _adotar(s, conta: Conta, sub: dict) -> Assinatura | None:
    """Grava aqui a assinatura viva no Asaas (com o plano do valor e da descrição dela) e troca o plano da conta."""
    valor = asaas.valor(sub.get("value"))
    plano = servico.plano_da_assinatura(sub)
    dados = _dados_do_cliente(conta, sub.get("customer")) if plano is not None else None
    if plano is None or dados is None:
        log.error("Assinaturas: a assinatura %s da conta %s no Asaas não tem o valor e a descrição de um plano ou dados "
                  "de cobrança válidos; não foi adotada.", sub["id"], conta.id)
        return None
    a = Assinatura(conta_id=conta.id, asaas_id=sub["id"], ambiente=asaas.ambiente(), plano=plano, valor=valor,
                   situacao="ativa", primeiro_vencimento=asaas.data(sub.get("nextDueDate")) or dia_de(relogio.agora()),
                   criada_em=servico._agora_utc(), criada_por=None, **dados)
    s.add(a)
    s.flush()
    travar_contatos(s, conta.id)  # o plano muda: a mesma trava do gatilho do limite
    conta.plano = plano
    servico.buscar_cobrancas(s, conta.id, a)
    servico.ajustar_primeiro_vencimento(s, a)
    registrar(s, "assinatura_adotada", "atencao", {"plano": plano, "valor": str(valor)}, conta_id=conta.id)
    return a


def conciliar(s, conta: Conta) -> Assinatura | None:
    """Nunca duas assinaturas vivas no Asaas para a conta (chame com a conta travada). As desconhecidas com a
    referência da conta: sem assinatura ativa (e sem ser cortesia), a mais nova com o valor e a descrição de um mesmo
    plano é adotada; as outras são removidas lá. As canceladas aqui que seguem vivas lá e as com a remoção pendente também são removidas.
    Devolve a adotada."""
    desconhecidas, remover = servico.assinaturas_no_asaas(s, conta)
    adotada = None
    if desconhecidas:
        log.error("Assinaturas: %s assinatura(s) viva(s) no Asaas com a referência da conta %s e desconhecida(s) aqui; "
                  "conciliando.", len(desconhecidas), conta.id)
        if conta.situacao == "cortesia":
            motivo = "cortesia"
        elif servico.assinatura_ativa(s, conta.id) is not None or servico.ativa_de_outro_ambiente(s, conta.id):
            motivo = "duplicada"
        else:
            motivo = "nao_adotada"
            for sub in desconhecidas:
                if servico.plano_da_assinatura(sub) is not None:
                    adotada = _adotar(s, conta, sub)
                    if adotada is not None:
                        motivo = "duplicada"
                        break
        for sub in desconhecidas:
            if adotada is None or sub["id"] != adotada.asaas_id:
                servico.remover_sobrando(s, conta.id, sub, motivo)
    for sub, motivo_remocao in remover:
        servico.remover_sobrando(s, conta.id, sub, motivo_remocao)
    return adotada


def _conhecida(s, asaas_id: str) -> bool:
    return s.scalar(select(Assinatura.id).where(Assinatura.asaas_id == asaas_id, servico.filtro_ambiente())) is not None


def conciliar_por_aviso(conta_id: int, asaas_id: str) -> int | None:
    """Aviso de cobrança de uma assinatura desconhecida com a referência da conta: espera o que estiver em andamento na
    conta (um assinar ainda gravando a assinatura) e, se ela continua desconhecida, concilia (log de erro). Devolve a
    conta se a assinatura passou a ser conhecida."""
    with em_conta(conta_id) as s:
        conta = servico.travar_conta(s, conta_id)
        if conta is None:
            log.error("Asaas: aviso de cobrança de uma assinatura com a referência da conta %s, que não existe aqui.",
                      conta_id)
            return None
        if _conhecida(s, asaas_id):
            return conta_id
        log.error("Asaas: aviso de cobrança de uma assinatura que não está gravada aqui (conta %s); conciliando.",
                  conta_id)
        conciliar(s, conta)
        servico.recalcular(s, conta)
        return conta_id if _conhecida(s, asaas_id) else None


# ---- conferência diária ------------------------------------------------------------------------

def _trazer_cobrancas(s, conta: Conta, a: Assinatura) -> None:
    try:
        pagamentos = asaas.cobrancas_da_assinatura(a.asaas_id)
    except asaas.FalhaAsaas as f:
        if f.tipo in servico.FORA_DO_AR:
            raise
        if f.tipo != "nao_encontrado":
            log.warning("Assinaturas: o Asaas recusou a lista de cobranças da assinatura da conta %s (%s).", conta.id,
                        f.detalhe)
        return
    servico.sincronizar_lista(s, conta.id, a, pagamentos)


def _nao_encontrada(s, conta: Conta, a: Assinatura, hoje: date) -> None:
    if a.nao_encontrada_desde is None or a.nao_encontrada_desde > hoje:
        a.nao_encontrada_desde = hoje
    dias = (hoje - a.nao_encontrada_desde).days + 1
    log.error("Assinaturas: a assinatura ativa da conta %s não existe no Asaas (404; %s dia(s) seguido(s)).", conta.id,
              dias)
    if dias >= DIAS_NAO_ENCONTRADA:
        servico.encerrar(s, a, None)
        registrar(s, "assinatura_cancelada", "atencao", {"plano": a.plano, "motivo": "nao_encontrada_no_asaas"},
                  conta_id=conta.id)


def _realinhar(s, conta: Conta, a: Assinatura, valor_asaas) -> None:
    """O valor no Asaas difere do daqui (troca de plano que não foi gravada aqui, ou mudança no painel): volta ao
    daqui, também nas faturas em aberto."""
    try:
        asaas.atualizar_assinatura(a.asaas_id, a.valor, servico.descricao(a.plano))
    except asaas.FalhaAsaas as f:
        if f.tipo in servico.FORA_DO_AR:
            raise
        log.error("Assinaturas: o valor da assinatura da conta %s no Asaas (%s) difere do daqui (%s) e não foi "
                  "possível corrigir (%s).", conta.id, valor_asaas, a.valor, f.detalhe)
        return
    log.warning("Assinaturas: o valor da assinatura da conta %s no Asaas (%s) foi corrigido para %s.", conta.id,
                valor_asaas, a.valor)
    registrar(s, "valor_realinhado", "atencao", {"plano": a.plano, "de": str(valor_asaas), "para": str(a.valor)},
              conta_id=conta.id)


def _conferir_ativa(s, conta: Conta, a: Assinatura, hoje: date) -> None:
    try:
        sub = asaas.obter_assinatura(a.asaas_id)
    except asaas.FalhaAsaas as f:
        if f.tipo != "nao_encontrado":
            raise
        _nao_encontrada(s, conta, a, hoje)
        return
    a.nao_encontrada_desde = None
    if not asaas.assinatura_viva(sub):  # removida, INACTIVE ou EXPIRED (ex.: cancelada no painel do Asaas)
        servico.encerrar(s, a, None)
        registrar(s, "assinatura_cancelada", "atencao", {"plano": a.plano, "motivo": "removida_no_asaas"},
                  conta_id=conta.id)
        return
    valor = asaas.valor(sub.get("value"))
    if valor is not None and valor != a.valor:
        _realinhar(s, conta, a, valor)
    _trazer_cobrancas(s, conta, a)


def _conferir(s, conta: Conta, hoje: date) -> None:
    conciliar(s, conta)
    ativa = servico.assinatura_ativa(s, conta.id)
    if ativa is not None:
        _conferir_ativa(s, conta, ativa, hoje)
    recente = relogio.agora() - timedelta(days=DIAS_CONFERIR_CANCELADA)
    for a in s.scalars(select(Assinatura).where(Assinatura.conta_id == conta.id, Assinatura.situacao == "cancelada",
                                                servico.filtro_ambiente(), Assinatura.cancelada_em > recente)
                       .order_by(Assinatura.id)).all():
        _trazer_cobrancas(s, conta, a)


def _sanidade(s, conta: Conta, hoje: date) -> None:
    """Ativa, paga só até mais de 40 dias atrás e sem fatura em aberto: algo se perdeu entre o Asaas e a API."""
    a = servico.assinatura_ativa(s, conta.id)
    if a is None:
        return
    coberto = conta.pago_ate or (a.primeiro_vencimento - timedelta(days=1))
    if coberto >= hoje - timedelta(days=DIAS_SANIDADE):
        return
    if not s.scalar(select(exists().where(Cobranca.assinatura_id == a.id, Cobranca.situacao.in_(servico.ABERTAS)))):
        log.error("Assinaturas: a conta %s tem assinatura ativa, pagamento só até %s e nenhuma fatura em aberto. "
                  "Confira no Asaas.", conta.id, coberto.isoformat())


def conferir_conta(conta_id: int, hoje: date | None = None) -> str:
    """Confere uma conta: "ok", "erro" ou "parar" (o Asaas está fora ou recusou a chave)."""
    hoje = hoje or dia_de(relogio.agora())
    try:
        with em_conta(conta_id) as s:
            conta = servico.travar_conta(s, conta_id)
            if conta is None:
                return "erro"
            resultado = "ok"
            try:
                _conferir(s, conta, hoje)
            except asaas.FalhaAsaas as f:
                if f.tipo not in servico.FORA_DO_AR:
                    raise
                resultado = "parar"
            servico.recalcular(s, conta)  # também quando parou no meio: a conta não fica pela metade
            if resultado == "ok":
                conta.asaas_conferida_em = hoje
                _sanidade(s, conta, hoje)
        return resultado
    except Exception as e:  # noqa: BLE001 - uma conta não derruba as outras
        detalhe = f"Asaas: {e.detalhe}" if isinstance(e, asaas.FalhaAsaas) else descrever_erro(e)
        log.error("Assinaturas: erro na conferência da conta %s (%s).", conta_id, detalhe)
        return "erro"


def conferir_contas() -> int:
    """Conferência diária (a partir das 6h). Devolve quantas contas foram conferidas."""
    agora = relogio.agora()
    if agora.astimezone(relogio.FUSO).time() < CONFERENCIA_A_PARTIR:
        return 0
    hoje = dia_de(agora)
    amb = asaas.ambiente()
    com_assinatura = exists().where(
        Assinatura.conta_id == Conta.id, Assinatura.ambiente == amb,
        or_(Assinatura.situacao == "ativa",
            Assinatura.cancelada_em > agora - timedelta(days=DIAS_CONFERIR_CANCELADA)))
    cliente_a_conferir = and_(Conta.asaas_conferida_em.is_(None), Conta.asaas_cliente_id.is_not(None),
                              Conta.asaas_ambiente == amb)
    with modo_sistema() as s:
        ids = s.scalars(select(Conta.id).where(
            or_(Conta.asaas_conferida_em.is_(None), Conta.asaas_conferida_em < hoje),
            or_(com_assinatura, cliente_a_conferir),
        ).order_by(Conta.id).limit(LOTE)).all()
    feitas = 0
    for conta_id in ids:
        resultado = conferir_conta(conta_id, hoje)
        if resultado == "parar":
            break
        if resultado == "ok":
            feitas += 1
    return feitas


# ---- ambiente e remoções pendentes ---------------------------------------------------------------

def tratar_outro_ambiente() -> int:
    """Chave de produção: descarta a cobrança de sandbox das contas que têm cliente ou assinatura ativa de sandbox
    (`servico.limpar_outro_ambiente`) e recalcula. Chave de sandbox com linhas de produção: só o log de erro (seria a
    chave errada; nada é apagado). Devolve quantas contas mudaram."""
    amb = asaas.ambiente()
    if amb is None:
        return 0
    outro = "sandbox" if amb == "producao" else "producao"
    with modo_sistema() as s:
        ids = s.scalars(select(Conta.id).where(or_(
            Conta.asaas_ambiente == outro,
            exists().where(Assinatura.conta_id == Conta.id, Assinatura.situacao == "ativa", Assinatura.ambiente == outro),
        )).order_by(Conta.id).limit(LOTE)).all()
    if not ids:
        return 0
    if amb == "sandbox":
        log.error("Assinaturas: a chave do Asaas é de sandbox, mas %s conta(s) têm cliente ou assinatura de produção. "
                  "Nada foi mudado; confira ASAAS_API_KEY.", len(ids))
        return 0
    feitas = 0
    for conta_id in ids:
        try:
            with em_conta(conta_id) as s:
                conta = servico.travar_conta(s, conta_id)
                mudou = conta is not None and servico.limpar_outro_ambiente(s, conta)
                if mudou:
                    servico.recalcular(s, conta)
        except Exception as e:  # noqa: BLE001 - uma conta não derruba as outras
            log.error("Assinaturas: erro ao descartar a cobrança de sandbox da conta %s (%s).", conta_id,
                      descrever_erro(e))
            continue
        if mudou:
            log.warning("Assinaturas: conta %s: cliente e assinatura de sandbox descartados (chave de produção).",
                        conta_id)
            feitas += 1
    return feitas


def remover_pendentes() -> int:
    """Tenta de novo as remoções no Asaas que falharam (`asaas_remocoes`, deste ambiente). 404 conta como removida.
    Para no primeiro Asaas fora do ar; desiste (log de erro) depois de 20 tentativas. Devolve quantas saíram."""
    with modo_sistema() as s:
        linhas = s.execute(select(AsaasRemocao.asaas_id, AsaasRemocao.conta_id, AsaasRemocao.motivo).where(
            AsaasRemocao.removida_em.is_(None), AsaasRemocao.ambiente == asaas.ambiente(),
            AsaasRemocao.tentativas < MAX_TENTATIVAS_REMOCAO,
        ).order_by(AsaasRemocao.criada_em).limit(LOTE)).all()
    feitas = 0
    for asaas_id, conta_id, motivo in linhas:
        try:
            asaas.remover_assinatura(asaas_id)
        except asaas.FalhaAsaas as f:
            if f.tipo != "nao_encontrado":
                with modo_sistema() as s:
                    tentativas = s.scalar(update(AsaasRemocao).where(AsaasRemocao.asaas_id == asaas_id).values(
                        tentativas=AsaasRemocao.tentativas + 1, erro=f.detalhe[:300]).returning(AsaasRemocao.tentativas))
                nivel = logging.ERROR if (tentativas or 0) >= MAX_TENTATIVAS_REMOCAO else logging.WARNING
                log.log(nivel, "Assinaturas: a remoção da assinatura %s no Asaas falhou de novo (tentativa %s de %s: "
                               "%s).", asaas_id, tentativas, MAX_TENTATIVAS_REMOCAO, f.detalhe)
                if f.tipo in servico.FORA_DO_AR:
                    break
                continue
        with modo_sistema() as s:
            s.execute(update(AsaasRemocao).where(AsaasRemocao.asaas_id == asaas_id)
                      .values(removida_em=func.now(), erro=None))
            if conta_id is not None:
                registrar(s, "assinatura_removida_no_asaas", "atencao", {"motivo": motivo}, conta_id=conta_id)
        feitas += 1
    return feitas


def executar() -> dict:
    """Tarefa `assinaturas`. Sem o Asaas configurado, só a parte das datas."""
    from toqqi.modulos.assinatura import webhook

    resumo = {"testes_expirados": recalcular_pelas_datas(), "contas_de_outro_ambiente": 0, "remocoes_no_asaas": 0,
              "eventos_reprocessados": 0, "contas_conferidas": 0}
    if asaas.disponivel():
        resumo["contas_de_outro_ambiente"] = tratar_outro_ambiente()
        resumo["remocoes_no_asaas"] = remover_pendentes()
        resumo["eventos_reprocessados"] = webhook.reprocessar()
        resumo["contas_conferidas"] = conferir_contas()
    return resumo
