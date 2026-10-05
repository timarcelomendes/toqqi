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

import jwt
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, erro_do_banco
from toqqi.core.segredos import cifrar, decifrar
from toqqi.core.texto import telefone_canonico
from toqqi.modelos import Conector, Conta, Contato, Empresa
from toqqi.modulos.conectores import bling
from toqqi.modulos.conectores.servico import _hash, _texto
from toqqi.modulos.empresas.desfecho import marcar
from toqqi.modulos.integracoes import pesquisas
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.integracoes.esquemas import EmpresaEventoIn, PesquisaIn

PROVEDOR = "bling"
MAX_CONTATOS = 5000
MAX_DETALHES = 600
VALIDADE_STATE = timedelta(minutes=15)


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
    if not bling.disponivel():
        raise AppError(503, "conector_indisponivel", "O conector do Bling ainda não está disponível.")
    state = jwt.encode({"c": ctx.conta_id, "u": ctx.usuario_id, "p": PROVEDOR, "n": secrets.token_hex(8),
                        "exp": datetime.now(timezone.utc) + VALIDADE_STATE}, config().JWT_SECRET, algorithm="HS256")
    return {"url": bling.url_autorizar(state)}


def _volta(resultado: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/integracoes?aba=crm&conector=bling&resultado={resultado}"


def retorno(codigo: str | None, state: str | None) -> str:
    """Endereço do site para onde o navegador volta (com `resultado=ok|erro|negado`)."""
    try:
        dados = jwt.decode(state or "", config().JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return _volta("erro")
    if dados.get("p") != PROVEDOR:
        return _volta("erro")
    if not codigo:
        return _volta("negado")
    try:
        tokens = bling.trocar_codigo(codigo)
        empresa_bling = bling.empresa(tokens)
    except bling.ErroBling:
        return _volta("erro")
    with em_conta(int(dados["c"])) as s:
        c = _obter(s) or Conector(conta_id=int(dados["c"]), provedor=PROVEDOR)
        c.token_cifrado = cifrar(json.dumps(tokens))
        c.segredo_hash = c.segredo_hash or _hash(secrets.token_urlsafe(32))
        c.opcoes = {"pesquisar_ao_faturar": (c.opcoes or {}).get("pesquisar_ao_faturar", True),
                    "empresa_bling": empresa_bling}
        c.erro, c.atualizado_em = None, relogio.agora()
        s.add(c)
        s.flush()
        registrar(s, "conector_ligado", "info", {"provedor": PROVEDOR}, usuario_id=dados.get("u"))
    return _volta("ok")


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


def alterar(ctx: Contexto, pesquisar: bool) -> dict:
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
