"""Etapa 5j, conector do Bling (ERP). Diferente do RD e do Omie, o Bling usa OAuth do aplicativo do Toqqi:
1. "Conectar com o Bling" leva o administrador à tela de autorização do Bling; a volta (`/publico/conectores/bling/
   retorno`) troca o código pelos tokens, guarda cifrados com o id da empresa no Bling e devolve ao site;
2. "Sincronizar agora" roda em segundo plano (o Bling aceita 3 pedidos por segundo e o e-mail só vem no detalhe de cada
   contato): cada cliente ativo vira empresa + contato (`bling:<id>`), até MAX_DETALHES novos por vez; quem já existe é
   pulado sem consultar o detalhe, então cada rodada continua de onde a outra parou;
3. com "Pesquisar quando uma nota for emitida", o aviso do aplicativo (`invoice.created`, assinado com o client secret)
   acha a conta pelo `companyId` e manda a pesquisa NPS ao contato da nota, uma vez por evento."""
import json
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import jwt
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, erro_do_banco
from toqqi.core.segredos import cifrar, decifrar
from toqqi.core.texto import telefone_canonico
from toqqi.modelos import BlingInstalacao, Conector, Conta, Contato, Empresa
from toqqi.modulos.conectores import bling
from toqqi.modulos.conectores.servico import _hash, _texto
from toqqi.modulos.empresas.desfecho import marcar
from toqqi.modulos.integracoes import pesquisas
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.integracoes.esquemas import EmpresaEventoIn, PesquisaIn
from toqqi.modulos.assinatura import gratis

PROVEDOR = "bling"
RECURSO = "O conector do Bling"
MAX_CONTATOS = 5000
MAX_DETALHES = 600
VALIDADE_STATE = timedelta(minutes=15)
VALIDADE_INSTALACAO = timedelta(hours=24)


def _obter(s) -> Conector | None:
    return s.scalar(select(Conector).where(Conector.provedor == PROVEDOR))


def _tokens(c: Conector) -> dict | None:
    texto = decifrar(c.token_cifrado)
    try:
        return json.loads(texto) if texto else None
    except ValueError:
        return None


def _json(c: Conector | None) -> dict:
    base = {"disponivel": bling.disponivel(), "eventos": list(bling.EVENTOS_PESQUISA)}
    if c is None:
        return {**base, "conectado": False}
    o = c.opcoes or {}
    return {**base, "conectado": True, "pesquisar_ao_faturar": bool(o.get("pesquisar_ao_faturar")),
            "sincronizando": bool(o.get("sincronizando")), "sincronizado_em": c.sincronizado_em, "resumo": c.resumo,
            "erro": c.erro, "conectado_em": c.criado_em}


def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _json(_obter(s))


# ---- conectar (OAuth) ------------------------------------------------------------------------

def autorizar(ctx: Contexto) -> dict:
    gratis.exigir_recurso_ctx(ctx, RECURSO)
    if not bling.disponivel():
        raise AppError(503, "conector_indisponivel", "O conector do Bling ainda não está disponível.")
    state = jwt.encode({"c": ctx.conta_id, "u": ctx.usuario_id, "p": PROVEDOR, "n": secrets.token_hex(8),
                        "exp": datetime.now(timezone.utc) + VALIDADE_STATE}, config().JWT_SECRET, algorithm="HS256")
    return {"url": bling.url_autorizar(state)}


def _volta(resultado: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/integracoes?aba=crm&conector=bling&resultado={resultado}"


def _volta_loja(**params: str) -> str:
    return str(httpx.URL(f"{config().FRONTEND_URL.rstrip('/')}/conectar/bling", params=params))


def _tirar_de_outras_contas(empresa_bling: str | None, conta_id: int) -> int:
    """A mesma empresa do Bling ligada a outra conta do Toqqi passa para esta: quem acabou de autorizar no Bling provou
    que controla a empresa, e os avisos de nota acham a conta pelo `companyId` (duas contas com a mesma empresa ficariam
    ambíguas). A conexão antiga é apagada, com registro na auditoria daquela conta. Devolve quantas foram tiradas."""
    if not empresa_bling:
        return 0
    with modo_sistema() as s:
        antigas = s.scalars(select(Conector).where(Conector.provedor == PROVEDOR, Conector.conta_id != conta_id,
                                                   Conector.opcoes["empresa_bling"].astext == empresa_bling)).all()
        contas = [c.conta_id for c in antigas]
        for c in antigas:
            s.delete(c)
    for outra in contas:
        with em_conta(outra) as s:
            registrar(s, "conector_desligado", "atencao",
                      {"provedor": PROVEDOR, "motivo": "A empresa do Bling foi conectada a outra conta do Toqqi."})
    return len(contas)


def _gravar_conector(conta_id: int, usuario_id: int | None, tokens: dict, empresa_bling: str | None,
                     origem: str) -> None:
    with em_conta(conta_id) as s:
        c = _obter(s) or Conector(conta_id=conta_id, provedor=PROVEDOR)
        c.token_cifrado = cifrar(json.dumps(tokens))
        c.segredo_hash = c.segredo_hash or _hash(secrets.token_urlsafe(32))
        c.opcoes = {"pesquisar_ao_faturar": (c.opcoes or {}).get("pesquisar_ao_faturar", True),
                    "empresa_bling": empresa_bling}
        c.erro, c.atualizado_em = None, relogio.agora()
        s.add(c)
        s.flush()
        registrar(s, "conector_ligado", "info", {"provedor": PROVEDOR, "origem": origem}, usuario_id=usuario_id)


def retorno(codigo: str | None, state: str | None) -> str:
    """Endereço do site para onde o navegador volta. Começou no Toqqi (com `state`): Integrações com
    `resultado=ok|movido|erro|negado|plano` (movido: a empresa do Bling estava em outra conta e passou para esta). Começou na loja do Bling (sem `state` do Toqqi): /conectar/bling com
    o código da instalação (`instalacao=`) ou `resultado=erro|negado`."""
    try:
        dados = jwt.decode(state or "", config().JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return _instalacao_da_loja(codigo)
    if dados.get("p") != PROVEDOR:
        return _instalacao_da_loja(codigo)
    if not codigo:
        return _volta("negado")
    with em_conta(int(dados["c"])) as s:
        if s.scalar(select(Conta.situacao)) == gratis.GRATIS:
            return _volta("plano")  # a conta passou para o Grátis no meio da autorização
    try:
        tokens = bling.trocar_codigo(codigo)
        empresa_bling = bling.empresa(tokens)
    except bling.ErroBling:
        return _volta("erro")
    movidas = _tirar_de_outras_contas(empresa_bling, int(dados["c"]))
    _gravar_conector(int(dados["c"]), dados.get("u"), tokens, empresa_bling, "toqqi")
    return _volta("movido" if movidas else "ok")


def _instalacao_da_loja(codigo: str | None) -> str:
    if not codigo or not bling.disponivel():
        return _volta_loja(resultado="negado" if bling.disponivel() else "erro")
    try:
        tokens = bling.trocar_codigo(codigo)
        empresa_bling = bling.empresa(tokens)
    except bling.ErroBling:
        return _volta_loja(resultado="erro")
    instalacao = secrets.token_urlsafe(32)
    with modo_sistema() as s:
        s.add(BlingInstalacao(codigo_hash=_hash(instalacao), tokens_cifrado=cifrar(json.dumps(tokens)),
                              empresa_bling=empresa_bling, expira_em=relogio.agora() + VALIDADE_INSTALACAO))
    return _volta_loja(instalacao=instalacao)


def ligar_instalacao(ctx: Contexto, instalacao: str) -> dict:
    """Liga à conta de quem entrou a instalação feita pela loja do Bling (administrador; fora do Plano Grátis)."""
    gratis.exigir_recurso_ctx(ctx, RECURSO)
    with modo_sistema() as s:
        pendente = s.scalar(select(BlingInstalacao).where(BlingInstalacao.codigo_hash == _hash(instalacao.strip()),
                                                          BlingInstalacao.expira_em > relogio.agora()))
        if pendente is None:
            raise AppError(404, "instalacao_vencida", "Esta instalação venceu ou já foi usada. Instale o Toqqi de novo "
                           "pela Central de Extensões do Bling ou conecte por Integrações.")
        tokens, empresa_bling = _tokens_texto(pendente.tokens_cifrado), pendente.empresa_bling
    if tokens is None:
        raise AppError(404, "instalacao_vencida", "Esta instalação não pode mais ser lida. Instale o Toqqi de novo.")
    movidas = _tirar_de_outras_contas(empresa_bling, ctx.conta_id)
    _gravar_conector(ctx.conta_id, ctx.usuario_id, tokens, empresa_bling, "loja")
    with modo_sistema() as s:
        s.execute(delete(BlingInstalacao).where(BlingInstalacao.codigo_hash == _hash(instalacao.strip())))
    return ver(ctx) | {"movido": bool(movidas)}


def _tokens_texto(cifrado: str) -> dict | None:
    try:
        texto = decifrar(cifrado)
        return json.loads(texto) if texto else None
    except ValueError:
        return None


def limpar_instalacoes() -> int:
    """Tarefa `limpeza`: apaga as instalações pela loja que venceram sem ser ligadas a uma conta."""
    with modo_sistema() as s:
        return s.execute(delete(BlingInstalacao).where(BlingInstalacao.expira_em <= relogio.agora())).rowcount or 0


def _tokens_validos(conta_id: int) -> dict:
    """Os tokens da conta, renovados (e salvos) se o access token venceu."""
    with em_conta(conta_id) as s:
        c = _obter(s)
        tokens = _tokens(c) if c else None
    if not tokens:
        raise bling.ErroBling("O Bling não está conectado.")
    if bling.vencido(tokens):
        novos = bling.renovar(tokens["refresh"])
        tokens = {**novos, "refresh": novos.get("refresh") or tokens["refresh"]}
        with em_conta(conta_id) as s:
            c = _obter(s)
            if c:
                c.token_cifrado = cifrar(json.dumps(tokens))
    return tokens


def homologacao(ctx: Contexto) -> dict:
    """Plataforma (superadmin): roda o teste de homologação do Bling com o Bling conectado na conta de quem pediu."""
    if not bling.disponivel():
        raise AppError(503, "conector_indisponivel", "Configure BLING_CLIENT_ID e BLING_CLIENT_SECRET no Render antes.")
    try:
        tokens = _tokens_validos(ctx.conta_id)
    except bling.ErroBling:
        raise AppError(409, "bling_desconectado", "Conecte o Bling nesta conta (Integrações › Bling) e rode o teste "
                       "de novo: o teste usa a conexão da sua conta.")

    def renovar(atuais: dict) -> dict:
        novos = bling.renovar(atuais["refresh"])
        novos = {**novos, "refresh": novos.get("refresh") or atuais["refresh"]}
        with em_conta(ctx.conta_id) as s:
            c = _obter(s)
            if c:
                c.token_cifrado = cifrar(json.dumps(novos))
        return novos

    try:
        r = bling.homologacao(tokens, renovar)
    except bling.ErroBling as e:  # a renovação do token falhou
        r = {"ok": False, "passos": [], "erro": str(e), "total_ms": None}
    with em_conta(ctx.conta_id) as s:
        registrar(s, "bling_homologacao", "info", {"ok": r["ok"], "total_ms": r["total_ms"]}, usuario_id=ctx.usuario_id)
    return r


def alterar(ctx: Contexto, pesquisar: bool) -> dict:
    gratis.exigir_recurso_ctx(ctx, RECURSO)
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O Bling não está conectado.")
        c.opcoes = {**(c.opcoes or {}), "pesquisar_ao_faturar": pesquisar}
        return _json(c)


def desconectar(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is not None:
            s.delete(c)
            registrar(s, "conector_desligado", "info", {"provedor": PROVEDOR}, usuario_id=ctx.usuario_id)


# ---- sincronizar (em segundo plano) -----------------------------------------------------------

def iniciar_sincronizacao(ctx: Contexto) -> dict:
    gratis.exigir_recurso_ctx(ctx, RECURSO)
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O Bling não está conectado.")
        if (c.opcoes or {}).get("sincronizando"):
            raise AppError(409, "em_andamento", "A sincronização com o Bling já está em andamento.")
        c.opcoes = {**(c.opcoes or {}), "sincronizando": True}
        return _json(c)


def _fim(conta_id: int, resumo: dict | None, erro: str | None, usuario_id: int | None) -> None:
    with em_conta(conta_id) as s:
        c = _obter(s)
        if c is None:
            return
        c.opcoes = {**(c.opcoes or {}), "sincronizando": False}
        c.erro = erro
        if resumo is not None:
            c.sincronizado_em, c.resumo = relogio.agora(), resumo
            registrar(s, "conector_sincronizado", "info", {"provedor": PROVEDOR, **resumo}, usuario_id=usuario_id)


def sincronizar(conta_id: int, usuario_id: int | None) -> None:
    """Roda depois da resposta (BackgroundTasks). Nunca levanta: o resultado fica no conector."""
    r = {"empresas_novas": 0, "empresas_existentes": 0, "contatos_novos": 0, "contatos_existentes": 0,
         "sem_email_ou_telefone": 0, "inativos": 0, "limite_do_plano": False, "cortado": False}
    try:
        tokens = _tokens_validos(conta_id)
        lista = [x for x in bling.contatos(tokens, MAX_CONTATOS)]
        r["cortado"] = len(lista) >= MAX_CONTATOS
        detalhes = 0
        for item in lista:
            bid = str(item.get("id") or "")
            if not bid:
                continue
            if not bling.ativo(item):
                r["inativos"] += 1
                continue
            externo = f"bling:{bid}"
            with em_conta(conta_id) as s:
                if s.scalar(select(Contato.id).where(Contato.codigo_externo == externo).limit(1)):
                    r["contatos_existentes"] += 1
                    continue
            if detalhes >= MAX_DETALHES:
                r["cortado"] = True
                break
            detalhes += 1
            det = {**item, **bling.contato(tokens, bid)}
            if not _gravar(conta_id, usuario_id, det, externo, r):
                break
        _fim(conta_id, r, None, usuario_id)
    except bling.ErroBling as e:
        _fim(conta_id, None, str(e)[:300], usuario_id)
    except Exception:  # noqa: BLE001 - o conector não pode ficar "sincronizando" para sempre
        _fim(conta_id, None, "A sincronização com o Bling falhou. Tente de novo.", usuario_id)
        raise


def _gravar(conta_id: int, usuario_id: int | None, det: dict, externo: str, r: dict) -> bool:
    """Empresa + contato de um cliente do Bling. False = parou no limite do plano."""
    nome = _texto(det.get("fantasia") or det.get("nome"), 200)
    if not nome:
        return True
    doc = bling.documento(det)
    email = bling.email(det)
    fone = telefone_canonico(bling.telefone(det) or "") or None
    with em_conta(conta_id) as s:
        marcar(s, "api", usuario_id)
        existe = s.scalar(select(Empresa.id).where((Empresa.codigo_externo == externo) | (Empresa.nome == nome)).limit(1))
        if existe:
            r["empresas_existentes"] += 1
        else:
            try:
                with s.begin_nested():
                    s.add(Empresa(nome=nome, documento=doc, codigo_externo=externo))
                    s.flush()
                r["empresas_novas"] += 1
            except DBAPIError:
                pass
        if not email and not fone:
            r["sem_email_ou_telefone"] += 1
            return True
        dados = SimpleNamespace(codigo_externo=externo, email=email, telefone=fone, nome=nome[:120],
                                empresa=SimpleNamespace(codigo_externo=externo, documento=doc, nome=nome))
        try:
            with s.begin_nested():
                pesquisas._contato(s, dados)
            r["contatos_novos"] += 1
        except DBAPIError as e:
            erro = erro_do_banco(e)
            if erro is not None and erro.status == 402:
                r["limite_do_plano"] = True
                return False
    return True


# ---- aviso do aplicativo (nota emitida) --------------------------------------------------------

def receber_aviso(corpo: bytes, assinatura: str | None) -> list:
    if not bling.assinatura_valida(corpo, assinatura):
        return []
    try:
        aviso = json.loads(corpo)
    except ValueError:
        return []
    if not isinstance(aviso, dict) or aviso.get("event") not in bling.EVENTOS_PESQUISA:
        return []
    empresa_bling, dados = str(aviso.get("companyId") or ""), aviso.get("data") or {}
    with modo_sistema() as s:
        achado = s.execute(select(Conector.conta_id, Conector.opcoes, Conta.nome).join(Conta, Conta.id == Conector.conta_id)
                           .where(Conector.provedor == PROVEDOR,
                                  Conector.opcoes["empresa_bling"].astext == empresa_bling)).first()
    if achado is None or not empresa_bling:
        return []
    conta_id, opcoes, conta_nome = achado
    if not (opcoes or {}).get("pesquisar_ao_faturar"):
        return []
    contato_id = bling.contato_do_aviso(dados if isinstance(dados, dict) else {})
    if not contato_id:
        return []
    try:
        det = bling.contato(_tokens_validos(conta_id), contato_id)
    except bling.ErroBling:
        return []
    email, fone = bling.email(det), telefone_canonico(bling.telefone(det) or "") or None
    if not email and not fone:
        return []
    nome = _texto(det.get("fantasia") or det.get("nome"), 120)
    numero = dados.get("numero") or dados.get("id")
    try:
        pesquisa = PesquisaIn(email=email, telefone=fone, nome=nome, tipo="nps", evento="nota_emitida",
                              empresa=EmpresaEventoIn(nome=nome, codigo_externo=f"bling:{contato_id}") if nome else None,
                              referencia=_texto(f"Nota {numero}" if numero else None, 120),
                              id_evento=_texto(f"bling:{aviso.get('eventId') or numero}", 100))
        return pesquisas.disparar(ContextoIntegracao(conta_id=conta_id, conta_nome=conta_nome), pesquisa)[2]
    except (AppError, ValueError) as e:
        with em_conta(conta_id) as s:
            c = _obter(s)
            if c:
                c.erro = f"Nota emitida sem pesquisa: {getattr(e, 'mensagem', None) or e}"[:300]
        return []
