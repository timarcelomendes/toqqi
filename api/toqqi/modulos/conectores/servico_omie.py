"""Etapa 5j, conector do Omie (ERP): o administrador cola o App Key e o App Secret de um aplicativo do Omie e o Toqqi
1. traz os clientes do Omie ("Sincronizar agora"): cada cliente ativo vira uma empresa (nome fantasia ou razão social,
   CNPJ/CPF, código `omie:<código>`) com um contato (o contato do cadastro, e-mail e telefone); cria o que falta,
   nunca apaga nem sobrescreve, e para no limite de contatos do plano;
2. com "Pesquisar quando um pedido for faturado", recebe o aviso do Omie (o cliente cadastra o endereço mostrado pelo
   Toqqi no portal do desenvolvedor do Omie, nos eventos de pedido faturado ou nota autorizada) e manda a pesquisa NPS
   aos contatos ativos daquele cliente, pelas regras do disparo por evento da integração.
As chaves e o segredo do endereço ficam cifrados; a busca do aviso é pelo hash do segredo."""
import json
import secrets
from types import SimpleNamespace

from sqlalchemy import false, select
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
from toqqi.modulos.conectores import omie
from toqqi.modulos.conectores.servico import _existe, _hash, _texto
from toqqi.modulos.empresas.desfecho import marcar
from toqqi.modulos.integracoes import pesquisas
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.integracoes.esquemas import EmpresaEventoIn, PesquisaIn

PROVEDOR = "omie"
MAX_CLIENTES = 5000
MAX_CONTATOS_AVISO = 5


def _url_aviso(segredo: str) -> str:
    return f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/conectores/omie/{segredo}"


def _chaves(c: Conector) -> dict | None:
    texto = decifrar(c.token_cifrado)
    try:
        return json.loads(texto) if texto else None
    except ValueError:
        return None


def _obter(s) -> Conector | None:
    return s.scalar(select(Conector).where(Conector.provedor == PROVEDOR))


def _json(c: Conector | None) -> dict:
    if c is None:
        return {"conectado": False}
    chaves = _chaves(c) or {}
    return {"conectado": True, "pesquisar_ao_faturar": bool((c.opcoes or {}).get("pesquisar_ao_faturar")),
            "url_aviso": _url_aviso(chaves["segredo"]) if chaves.get("segredo") else None,
            "eventos": list(omie.TOPICOS_PESQUISA), "sincronizado_em": c.sincronizado_em, "resumo": c.resumo,
            "erro": c.erro, "conectado_em": c.criado_em}


def _erro(e: omie.ErroOmie) -> AppError:
    return AppError(502, "conector_falhou", str(e))


def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _json(_obter(s))


def conectar(ctx: Contexto, app_key: str, app_secret: str, pesquisar: bool) -> dict:
    chaves = {"app_key": app_key.strip(), "app_secret": app_secret.strip()}
    try:
        omie.conferir(chaves)
    except omie.ErroOmie as e:
        raise _erro(e)
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        antigas = _chaves(c) if c else None
        segredo = (antigas or {}).get("segredo") or secrets.token_urlsafe(32)  # o endereço já cadastrado continua
        c = c or Conector(conta_id=ctx.conta_id, provedor=PROVEDOR)
        c.token_cifrado, c.segredo_hash = cifrar(json.dumps({**chaves, "segredo": segredo})), _hash(segredo)
        c.opcoes, c.erro, c.atualizado_em = {"pesquisar_ao_faturar": pesquisar}, None, relogio.agora()
        s.add(c)
        s.flush()
        registrar(s, "conector_ligado", "info", {"provedor": PROVEDOR, "pesquisar_ao_faturar": pesquisar},
                  usuario_id=ctx.usuario_id)
        return _json(c)


def alterar(ctx: Contexto, pesquisar: bool) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O Omie não está conectado.")
        c.opcoes = {**(c.opcoes or {}), "pesquisar_ao_faturar": pesquisar}
        c.atualizado_em = relogio.agora()
        return _json(c)


def desconectar(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is not None:
            s.delete(c)
            registrar(s, "conector_desligado", "info", {"provedor": PROVEDOR}, usuario_id=ctx.usuario_id)


def sincronizar(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O Omie não está conectado.")
        chaves = _chaves(c)
    if not chaves:
        raise AppError(409, "token_invalido", "Conecte o Omie de novo (as chaves salvas não podem ser lidas).")
    try:
        lista = list(omie.clientes(chaves, MAX_CLIENTES))
    except omie.ErroOmie as e:
        with em_conta(ctx.conta_id) as s:
            c = _obter(s)
            if c:
                c.erro = str(e)[:300]
        raise _erro(e)
    r = {"empresas_novas": 0, "empresas_existentes": 0, "contatos_novos": 0, "contatos_existentes": 0,
         "sem_email_ou_telefone": 0, "inativos": 0, "limite_do_plano": False, "cortado": len(lista) >= MAX_CLIENTES}
    with em_conta(ctx.conta_id) as s:
        marcar(s, "api", ctx.usuario_id)
        for cli in lista:
            if not omie.ativo(cli):
                r["inativos"] += 1
                continue
            codigo, nome = str(cli.get("codigo_cliente_omie") or ""), _texto(omie.nome_empresa(cli), 200)
            if not codigo or not nome:
                continue
            externo, doc = f"omie:{codigo}", omie.documento(cli)
            existe = s.scalar(select(Empresa.id).where((Empresa.codigo_externo == externo) | (Empresa.nome == nome)
                                                       | ((Empresa.documento == doc) if doc else false())).limit(1))
            if existe:
                r["empresas_existentes"] += 1
            else:
                try:
                    with s.begin_nested():
                        s.add(Empresa(nome=nome, documento=doc, codigo_externo=externo))
                        s.flush()
                    r["empresas_novas"] += 1
                except DBAPIError:
                    continue
            email = omie.primeiro_email(cli.get("email"))
            fone = telefone_canonico(omie.telefone(cli) or "") or None
            if not email and not fone:
                r["sem_email_ou_telefone"] += 1
                continue
            dados = SimpleNamespace(codigo_externo=externo, email=email, telefone=fone,
                                    nome=_texto(cli.get("contato"), 120) or nome[:120],
                                    empresa=SimpleNamespace(codigo_externo=externo, documento=doc, nome=nome))
            if _existe(s, dados):
                r["contatos_existentes"] += 1
                continue
            try:
                with s.begin_nested():
                    pesquisas._contato(s, dados)
            except DBAPIError as e:
                erro = erro_do_banco(e)
                if erro is not None and erro.status == 402:
                    r["limite_do_plano"] = True
                    break
                continue
            r["contatos_novos"] += 1
        c = _obter(s)
        c.sincronizado_em, c.resumo, c.erro = relogio.agora(), r, None
        registrar(s, "conector_sincronizado", "info", {"provedor": PROVEDOR, **r}, usuario_id=ctx.usuario_id)
    return r


def receber_aviso(segredo: str, corpo: dict) -> list:
    """Pedido faturado / nota autorizada → pesquisa aos contatos ativos do cliente. Nunca levanta."""
    if not segredo or len(segredo) > 100 or not isinstance(corpo, dict):
        return []
    with modo_sistema() as s:
        achado = s.execute(select(Conector, Conta.nome).join(Conta, Conta.id == Conector.conta_id)
                           .where(Conector.segredo_hash == _hash(segredo))).one_or_none()
        if achado is None:
            return []
        c, conta_nome = achado
        conta_id, opcoes, chaves = c.conta_id, dict(c.opcoes or {}), _chaves(c)
    if not opcoes.get("pesquisar_ao_faturar") or not chaves:
        return []
    if corpo.get("appKey") and str(corpo["appKey"]) != str(chaves.get("app_key")):
        return []  # aviso de outro aplicativo do Omie
    topico = str(corpo.get("topic") or "")
    evento = corpo.get("event") if isinstance(corpo.get("event"), dict) else {}
    if topico not in omie.TOPICOS_PESQUISA:
        return []
    codigo = omie.cliente_do_aviso(evento)
    if not codigo:
        return []
    externo = f"omie:{codigo}"
    with em_conta(conta_id) as s:
        empresa_id = s.scalar(select(Empresa.id).where(Empresa.codigo_externo == externo).limit(1))
        alvos = [(x.email, x.telefone, x.nome) for x in s.scalars(
            select(Contato).where(Contato.ativo.is_(True),
                                  (Contato.empresa_id == empresa_id) if empresa_id else (Contato.codigo_externo == externo))
            .order_by(Contato.id).limit(MAX_CONTATOS_AVISO))]
    empresa = None
    if not alvos:  # cliente ainda não sincronizado: busca no Omie
        try:
            cli = omie.cliente(chaves, codigo)
        except (omie.ErroOmie, ValueError):
            cli = {}
        email = omie.primeiro_email(cli.get("email"))
        fone = telefone_canonico(omie.telefone(cli) or "") or None
        if email or fone:
            alvos = [(email, fone, _texto(cli.get("contato"), 120) or _texto(omie.nome_empresa(cli), 120))]
            empresa = EmpresaEventoIn(nome=_texto(omie.nome_empresa(cli), 120), codigo_externo=externo)
    ref = evento.get("idPedido") or evento.get("nIdPedido") or evento.get("numero_pedido") or corpo.get("messageId")
    envios, erros = [], []
    ci = ContextoIntegracao(conta_id=conta_id, conta_nome=conta_nome)
    for i, (email, fone, nome) in enumerate(alvos):
        try:
            dados = PesquisaIn(email=email, telefone=fone, nome=nome, empresa=empresa, tipo="nps",
                               evento="pedido_faturado", referencia=_texto(f"Pedido {ref}" if ref else None, 120),
                               id_evento=f"omie:{topico}:{ref}:{i}" if ref else None)
            envios += pesquisas.disparar(ci, dados)[2]
        except (AppError, ValueError) as e:
            erros.append(getattr(e, "mensagem", None) or str(e))
    if erros:
        with em_conta(conta_id) as s:
            c = _obter(s)
            if c:
                c.erro = f"Pedido faturado sem pesquisa: {erros[0]}"[:300]
    return envios
