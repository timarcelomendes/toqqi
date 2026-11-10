"""Conectores do Pipedrive e do HubSpot (pedido do Marcelo em 10/11/2026), no modelo do RD Station CRM (`servico.py`):
o administrador cola o token do CRM e o Toqqi

1. traz as empresas e os contatos do CRM ("Sincronizar agora": cria o que falta, pelo código externo `pd:<id>` ou
   `hs:<id>`, depois e-mail e telefone; nunca apaga nem sobrescreve o que já existe, e para no limite de contatos do
   plano);
2. com "Pesquisar quando um negócio for ganho", manda a pesquisa NPS aos contatos do negócio ganho (até 5), pelas
   mesmas regras do disparo por evento da integração (descadastro, descanso, assinatura, canal automático), com
   `id_evento` por negócio e contato:
   - Pipedrive: o aviso chega na hora (webhook de negócio alterado, versão 2.0, cadastrado pelo Toqqi no Pipedrive com
     o token; o endereço leva um segredo próprio, só o hash fica no banco). Só a passagem para "ganho" conta.
     A nota volta como anotação no negócio (tarefa `conectores`, como no RD);
   - HubSpot: a chave de serviço não recebe webhooks, então a tarefa `conectores` consulta, a cada rodada,
     os negócios ganhos alterados desde a última consulta (`opcoes.desde`, com 10 minutos de folga) e guarda os
     últimos 500 negócios já pesquisados (`opcoes.vistos`), para o mesmo negócio nunca mandar duas vezes.

O token fica cifrado. No Plano Grátis, os conectores ficam fechados (como os outros)."""
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, erro_do_banco
from toqqi.core.segredos import cifrar, decifrar
from toqqi.core.texto import telefone_canonico
from toqqi.modelos import Conector, Conta, Contato, Convite, Empresa
from toqqi.modulos.assinatura import gratis
from toqqi.modulos.conectores import hubspot, pipedrive
from toqqi.modulos.empresas.desfecho import marcar
from toqqi.modulos.envios.descadastro import telefone_sql
from toqqi.modulos.envios.processamento import processar_lista
from toqqi.modulos.integracoes import pesquisas
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.integracoes.esquemas import EmpresaEventoIn, PesquisaIn

log = logging.getLogger("toqqi.conectores")

MAX_EMPRESAS = 2000
MAX_CONTATOS = 5000
MAX_CONTATOS_NEGOCIO = 5
FOLGA_CONSULTA = timedelta(minutes=10)
MAX_VISTOS = 500


@dataclass(frozen=True)
class Provedor:
    chave: str  # em `conectores.provedor` e no endereço (/integracoes/conectores/{chave})
    nome: str
    prefixo: str  # do código externo das empresas e contatos e de `convites.origem_externa`
    cliente: ModuleType
    erro: type[Exception]
    webhook: bool  # True: o aviso chega pelo webhook; False: a tarefa consulta

    @property
    def recurso(self) -> str:
        return f"O conector do {self.nome}"


PIPEDRIVE = Provedor("pipedrive", "Pipedrive", "pd", pipedrive, pipedrive.ErroPipedrive, webhook=True)
HUBSPOT = Provedor("hubspot", "HubSpot", "hs", hubspot, hubspot.ErroHubspot, webhook=False)
PROVEDORES = {p.chave: p for p in (PIPEDRIVE, HUBSPOT)}


def _hash(segredo: str) -> str:
    return hashlib.sha256(segredo.encode()).hexdigest()


def _url_aviso(p: Provedor, segredo: str) -> str:
    return f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/conectores/{p.chave}/{segredo}"


def _json(p: Provedor, c: Conector | None) -> dict:
    if c is None:
        return {"conectado": False}
    opcoes = c.opcoes or {}
    dados = {"conectado": True, "pesquisar_ao_ganhar": bool(opcoes.get("pesquisar_ao_ganhar")),
             "sincronizado_em": c.sincronizado_em, "resumo": c.resumo, "erro": c.erro, "conectado_em": c.criado_em}
    if p.webhook:
        dados["aviso_cadastrado"] = bool(c.webhook_externo)
    else:
        dados["consultado_em"] = opcoes.get("consultado_em")
    return dados


def _obter(s, p: Provedor) -> Conector | None:
    return s.scalar(select(Conector).where(Conector.provedor == p.chave))


def _erro(p: Provedor, e: Exception) -> AppError:
    return AppError(502, "conector_falhou", str(e))


def _nao_conectado(p: Provedor) -> AppError:
    return AppError(404, "nao_encontrado", f"O {p.nome} não está conectado.")


def _token_ilegivel(p: Provedor) -> AppError:
    return AppError(409, "token_invalido", f"Conecte o {p.nome} de novo (o token salvo não pode ser lido).")


def ver(ctx: Contexto, p: Provedor) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _json(p, _obter(s, p))


def conectar(ctx: Contexto, p: Provedor, token: str, pesquisar_ao_ganhar: bool) -> dict:
    gratis.exigir_recurso_ctx(ctx, p.recurso)
    token = token.strip()
    try:
        p.cliente.conferir_token(token)
    except p.erro as e:
        raise _erro(p, e)
    with em_conta(ctx.conta_id) as s:
        antigo = _obter(s, p)
        antigo_token = decifrar(antigo.token_cifrado) if antigo else None
        antigo_webhook = antigo.webhook_externo if antigo else None
        antigas_opcoes = dict(antigo.opcoes or {}) if antigo else {}
    if antigo_webhook and antigo_token:
        try:
            p.cliente.remover_webhook(antigo_token, antigo_webhook)
        except p.erro:
            pass  # o aviso antigo aponta para um segredo que deixa de existir: o Toqqi ignora
    segredo = secrets.token_urlsafe(32)
    webhook, erro = None, None
    if pesquisar_ao_ganhar and p.webhook:
        try:
            webhook = p.cliente.criar_webhook(token, _url_aviso(p, segredo))
        except p.erro as e:
            erro = f"Não conseguimos cadastrar o aviso de negócio ganho no {p.nome}: {e}"[:300]
    opcoes = {"pesquisar_ao_ganhar": pesquisar_ao_ganhar}
    if not p.webhook:  # a consulta começa agora (negócios ganhos antes de ligar não recebem pesquisa)
        ligou_antes = antigas_opcoes.get("pesquisar_ao_ganhar") and pesquisar_ao_ganhar
        opcoes["desde"] = antigas_opcoes.get("desde") if ligou_antes else relogio.agora().isoformat()
        opcoes["vistos"] = antigas_opcoes.get("vistos") or []
        if antigas_opcoes.get("consultado_em"):
            opcoes["consultado_em"] = antigas_opcoes["consultado_em"]
    with em_conta(ctx.conta_id) as s:
        c = _obter(s, p) or Conector(conta_id=ctx.conta_id, provedor=p.chave)
        c.token_cifrado, c.segredo_hash, c.webhook_externo = cifrar(token), _hash(segredo), webhook
        c.opcoes, c.erro, c.atualizado_em = opcoes, erro, relogio.agora()
        s.add(c)
        s.flush()
        registrar(s, "conector_ligado", "info", {"provedor": p.chave, "pesquisar_ao_ganhar": pesquisar_ao_ganhar},
                  usuario_id=ctx.usuario_id)
        return _json(p, c)


def alterar(ctx: Contexto, p: Provedor, pesquisar_ao_ganhar: bool) -> dict:
    """Liga ou desliga a pesquisa no negócio ganho (no Pipedrive, cadastra ou remove o aviso)."""
    gratis.exigir_recurso_ctx(ctx, p.recurso)
    with em_conta(ctx.conta_id) as s:
        c = _obter(s, p)
        if c is None:
            raise _nao_conectado(p)
        token, ligado = decifrar(c.token_cifrado), bool((c.opcoes or {}).get("pesquisar_ao_ganhar"))
    if not token:
        raise _token_ilegivel(p)
    if ligado == pesquisar_ao_ganhar and (not p.webhook or pesquisar_ao_ganhar == bool(ver(ctx, p).get("aviso_cadastrado"))):
        return ver(ctx, p)
    return conectar(ctx, p, token, pesquisar_ao_ganhar)


def desconectar(ctx: Contexto, p: Provedor) -> None:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s, p)
        if c is None:
            return
        token, webhook = decifrar(c.token_cifrado), c.webhook_externo
        s.delete(c)
        registrar(s, "conector_desligado", "info", {"provedor": p.chave}, usuario_id=ctx.usuario_id)
    if token and webhook:
        try:
            p.cliente.remover_webhook(token, webhook)
        except p.erro:
            pass


# ---- sincronizar (empresas e contatos) --------------------------------------------------------

def _texto(v, limite: int) -> str | None:
    v = (str(v).strip() if v is not None else "")
    return v[:limite] or None


def _existe(s, dados) -> bool:
    for coluna, valor in ((Contato.codigo_externo, dados.codigo_externo), (Contato.email, dados.email),
                          (telefone_sql(Contato.telefone), dados.telefone)):
        if valor and s.scalar(select(Contato.id).where(coluna == valor).limit(1)):
            return True
    return False


def sincronizar(ctx: Contexto, p: Provedor) -> dict:
    gratis.exigir_recurso_ctx(ctx, p.recurso)
    with em_conta(ctx.conta_id) as s:
        c = _obter(s, p)
        if c is None:
            raise _nao_conectado(p)
        token = decifrar(c.token_cifrado)
    if not token:
        raise _token_ilegivel(p)
    try:  # tudo do CRM antes de abrir a transação
        orgs = list(p.cliente.empresas(token, MAX_EMPRESAS))
        pessoas = list(p.cliente.contatos(token, MAX_CONTATOS))
    except p.erro as e:
        with em_conta(ctx.conta_id) as s:
            c = _obter(s, p)
            if c:
                c.erro = str(e)[:300]
        raise _erro(p, e)

    r = {"empresas_novas": 0, "empresas_existentes": 0, "contatos_novos": 0, "contatos_existentes": 0,
         "sem_email_ou_telefone": 0, "limite_do_plano": False,
         "cortado": len(orgs) >= MAX_EMPRESAS or len(pessoas) >= MAX_CONTATOS}
    with em_conta(ctx.conta_id) as s:
        marcar(s, "api", ctx.usuario_id)
        nomes_org = {}
        for o in orgs:
            oid, nome = o.get("id"), _texto(o.get("nome"), 200)
            if not oid or not nome:
                continue
            nomes_org[oid] = nome
            codigo = f"{p.prefixo}:{oid}"
            existe = s.scalar(select(Empresa.id).where((Empresa.codigo_externo == codigo) | (Empresa.nome == nome))
                              .limit(1))
            if existe:
                r["empresas_existentes"] += 1
            else:
                s.add(Empresa(nome=nome, codigo_externo=codigo))
                s.flush()
                r["empresas_novas"] += 1
        for pessoa in pessoas:
            email = _texto(pessoa.get("email"), 254)
            telefone = telefone_canonico(pessoa.get("telefone") or "") or None
            if not email and not telefone:
                r["sem_email_ou_telefone"] += 1
                continue
            pid, org = pessoa.get("id"), pessoa.get("empresa_id")
            nome_org = nomes_org.get(org) or _texto(pessoa.get("empresa_nome"), 200) if org else None
            dados = SimpleNamespace(
                codigo_externo=f"{p.prefixo}:{pid}" if pid else None, email=email.lower() if email else None,
                telefone=telefone, nome=_texto(pessoa.get("nome"), 120),
                empresa=SimpleNamespace(codigo_externo=f"{p.prefixo}:{org}", documento=None, nome=nome_org)
                if org else None)
            if _existe(s, dados):
                r["contatos_existentes"] += 1
                continue  # nunca sobrescreve quem já está no Toqqi
            try:
                with s.begin_nested():
                    pesquisas._contato(s, dados)
            except DBAPIError as e:
                erro = erro_do_banco(e)
                if erro is not None and erro.status == 402:
                    r["limite_do_plano"] = True
                    break
                continue  # empresa perdida (409) ou dado recusado: pula o contato
            r["contatos_novos"] += 1
        c = _obter(s, p)
        c.sincronizado_em, c.resumo, c.erro = relogio.agora(), r, None
        registrar(s, "conector_sincronizado", "info", {"provedor": p.chave, **r}, usuario_id=ctx.usuario_id)
    return r


# ---- negócio ganho → pesquisa -------------------------------------------------------------------

def _disparar(p: Provedor, conta_id: int, conta_nome: str, deal_id: str, nome_negocio, pessoas: list[dict],
              empresa: dict | None) -> tuple[list, list[str]]:
    """Manda a pesquisa NPS aos contatos do negócio. Devolve (envios a processar, erros)."""
    envios, erros = [], []
    ci = ContextoIntegracao(conta_id=conta_id, conta_nome=conta_nome)
    org_id = (empresa or {}).get("id")
    org_nome = _texto((empresa or {}).get("nome"), 120)
    for i, pessoa in enumerate(pessoas[:MAX_CONTATOS_NEGOCIO]):
        email = _texto(pessoa.get("email"), 254)
        telefone = telefone_canonico(pessoa.get("telefone") or "") or None
        if not email and not telefone:
            continue
        try:
            dados = PesquisaIn(
                email=email, telefone=telefone, nome=_texto(pessoa.get("nome"), 120),
                codigo_externo=f"{p.prefixo}:{pessoa['id']}" if pessoa.get("id") else None,
                empresa=EmpresaEventoIn(nome=org_nome, codigo_externo=f"{p.prefixo}:{org_id}" if org_id else None)
                if (org_nome or org_id) else None,
                evento="negocio_ganho", referencia=_texto(nome_negocio, 120), tipo="nps",
                id_evento=f"{p.prefixo}:{deal_id}:{i}")
            resultado, _, novos = pesquisas.disparar(ci, dados)
            envios += novos
            if p.webhook and resultado.get("convite_id"):  # para devolver a nota ao negócio (tarefa `conectores`)
                with em_conta(conta_id) as s:
                    s.execute(update(Convite).where(Convite.id == resultado["convite_id"], Convite.origem_externa.is_(None))
                              .values(origem_externa=f"{p.prefixo}:{deal_id}"[:100]))
        except (AppError, ValueError) as e:
            erros.append(getattr(e, "mensagem", None) or str(e))
    return envios, erros


def _anotar_erro(conta_id: int, p: Provedor, erros: list[str]) -> None:
    if erros:
        with em_conta(conta_id) as s:
            c = _obter(s, p)
            if c:
                c.erro = f"Negócio ganho sem pesquisa: {erros[0]}"[:300]


def receber_aviso_pipedrive(segredo: str, corpo: dict) -> list:
    """Aviso de negócio alterado do Pipedrive. Devolve os envios a processar depois do commit. Nunca levanta: o
    Pipedrive só precisa do 200 (e apaga o webhook depois de 3 dias de falhas)."""
    p = PIPEDRIVE
    if not segredo or len(segredo) > 100:
        return []
    with modo_sistema() as s:
        achado = s.execute(select(Conector.conta_id, Conector.token_cifrado, Conector.opcoes, Conta.nome)
                           .join(Conta, Conta.id == Conector.conta_id)
                           .where(Conector.provedor == p.chave, Conector.segredo_hash == _hash(segredo))).one_or_none()
    if achado is None:
        return []
    conta_id, token_cifrado, opcoes, conta_nome = achado
    if not (opcoes or {}).get("pesquisar_ao_ganhar"):
        return []
    lido = pipedrive.negocio_do_aviso(corpo)
    if lido is None or not pipedrive.acabou_de_ganhar(*lido):
        return []
    deal, _ = lido
    deal_id = pipedrive.ident(deal.get("id")) or pipedrive.ident((corpo.get("meta") or {}).get("entity_id"))
    token = decifrar(token_cifrado)
    if not deal_id or not token:
        return []
    try:
        pessoas = pipedrive.pessoas_do_negocio(token, deal_id)
        if not pessoas and pipedrive.ident(deal.get("person_id")):
            uma = pipedrive.uma_pessoa(token, pipedrive.ident(deal.get("person_id")))
            pessoas = [uma] if uma else []
        org_id = pipedrive.ident(deal.get("org_id"))
        empresa = pipedrive.organizacao(token, org_id) if org_id else None
    except pipedrive.ErroPipedrive as e:
        _anotar_erro(conta_id, p, [str(e)])
        return []
    envios, erros = _disparar(p, conta_id, conta_nome, deal_id, deal.get("title"), pessoas, empresa)
    _anotar_erro(conta_id, p, erros)
    return envios


def consultar_hubspot() -> int:
    """Tarefa `conectores`: em cada conta com o HubSpot e a pesquisa ligada (fora do Grátis), os negócios ganhos desde a
    última consulta recebem a pesquisa (os envios saem aqui mesmo). Devolve quantos negócios novos foram tratados."""
    p = HUBSPOT
    with modo_sistema() as s:
        contas = s.execute(select(Conector.conta_id, Conta.nome).join(Conta, Conta.id == Conector.conta_id)
                           .where(Conector.provedor == p.chave, Conta.situacao != gratis.GRATIS,
                                  Conector.opcoes["pesquisar_ao_ganhar"].astext == "true")
                           .order_by(Conector.conta_id)).all()
    tratados = 0
    for conta_id, conta_nome in contas:
        try:
            tratados += _consultar_conta(p, conta_id, conta_nome)
        except Exception:  # noqa: BLE001 - uma conta não derruba as outras
            log.exception("Falha ao consultar o HubSpot da conta %s", conta_id)
    return tratados


def _consultar_conta(p: Provedor, conta_id: int, conta_nome: str) -> int:
    agora = relogio.agora()
    with em_conta(conta_id) as s:
        c = _obter(s, p)
        if c is None:
            return 0
        token, opcoes = decifrar(c.token_cifrado), dict(c.opcoes or {})
    if not token:
        return 0
    try:
        desde = datetime.fromisoformat(opcoes.get("desde")) if opcoes.get("desde") else agora
    except ValueError:
        desde = agora
    vistos: list[str] = list(opcoes.get("vistos") or [])
    tratados, envios, erros = 0, [], []
    try:
        negocios = hubspot.negocios_ganhos(token, desde - FOLGA_CONSULTA)
        for d in negocios:
            if d["id"] in vistos:
                continue
            pessoas, empresa = hubspot.contatos_do_negocio(token, d["id"], MAX_CONTATOS_NEGOCIO)
            novos, falhas = _disparar(p, conta_id, conta_nome, d["id"], d.get("nome"), pessoas, empresa)
            envios += novos
            erros += falhas
            vistos.append(d["id"])
            tratados += 1
        erro_consulta = None
    except hubspot.ErroHubspot as e:
        erro_consulta = f"Não conseguimos consultar os negócios ganhos no HubSpot: {e}"[:300]
    with em_conta(conta_id) as s:
        c = _obter(s, p)
        if c is not None:
            novas = dict(c.opcoes or {})
            novas["vistos"] = vistos[-MAX_VISTOS:]
            if erro_consulta is None:  # com erro, a próxima rodada tenta o mesmo período de novo
                novas["desde"], novas["consultado_em"] = agora.isoformat(), agora.isoformat()
            c.opcoes = novas
            if erro_consulta or erros:
                c.erro = erro_consulta or f"Negócio ganho sem pesquisa: {erros[0]}"[:300]
    if envios:
        processar_lista(envios)
    return tratados
