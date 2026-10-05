"""Etapa 5j, conector do RD Station CRM: o administrador cola o token de instância do RD e o Toqqi
1. traz as empresas e os contatos do RD ("Sincronizar agora": cria o que falta, pelo código externo `rd:<id>`, depois
   e-mail e telefone; nunca apaga nem sobrescreve o que já existe, e para no limite de contatos do plano);
2. com "Pesquisar quando um negócio for ganho", recebe o aviso do RD (webhook `crm_deal_updated`) e manda a pesquisa
   NPS aos contatos da negociação ganha, pelas mesmas regras do disparo por evento da integração (descadastro,
   descanso, assinatura, canal automático), com `id_evento` por negociação e contato (o aviso repetido não manda duas
   vezes).
O token fica cifrado; o endereço do aviso leva um segredo próprio (só o hash fica no banco)."""
import hashlib
import secrets
from datetime import timedelta
from types import SimpleNamespace

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
from toqqi.modelos import Conector, Conta, Contato, Convite, Empresa, Resposta
from toqqi.modulos.conectores import rdstation
from toqqi.modulos.empresas.desfecho import marcar
from toqqi.modulos.envios.descadastro import telefone_sql
from toqqi.modulos.integracoes import pesquisas
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.integracoes.esquemas import EmpresaEventoIn, PesquisaIn

PROVEDOR = "rdstation_crm"
MAX_EMPRESAS = 2000
MAX_CONTATOS = 5000
MAX_CONTATOS_NEGOCIO = 5


def _hash(segredo: str) -> str:
    return hashlib.sha256(segredo.encode()).hexdigest()


def _url_aviso(segredo: str) -> str:
    return f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/conectores/rdstation-crm/{segredo}"


def _json(c: Conector | None) -> dict:
    if c is None:
        return {"conectado": False}
    return {"conectado": True, "pesquisar_ao_ganhar": bool((c.opcoes or {}).get("pesquisar_ao_ganhar")),
            "aviso_cadastrado": bool(c.webhook_externo), "sincronizado_em": c.sincronizado_em, "resumo": c.resumo,
            "erro": c.erro, "conectado_em": c.criado_em}


def _obter(s) -> Conector | None:
    return s.scalar(select(Conector).where(Conector.provedor == PROVEDOR))


def _erro_rd(e: rdstation.ErroRd) -> AppError:
    return AppError(502, "conector_falhou", str(e))


def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return {"rdstation_crm": _json(_obter(s))}


def conectar(ctx: Contexto, token: str, pesquisar_ao_ganhar: bool) -> dict:
    token = token.strip()
    try:
        rdstation.conferir_token(token)
    except rdstation.ErroRd as e:
        raise _erro_rd(e)
    with em_conta(ctx.conta_id) as s:
        antigo = _obter(s)
        antigo_token = decifrar(antigo.token_cifrado) if antigo else None
        antigo_webhook = antigo.webhook_externo if antigo else None
    if antigo_webhook and antigo_token:
        try:
            rdstation.remover_webhook(antigo_token, antigo_webhook)
        except rdstation.ErroRd:
            pass  # o aviso antigo aponta para um segredo que deixa de existir: o Toqqi ignora
    segredo = secrets.token_urlsafe(32)
    webhook, erro = None, None
    if pesquisar_ao_ganhar:
        try:
            webhook = rdstation.criar_webhook(token, _url_aviso(segredo))
        except rdstation.ErroRd as e:
            erro = f"Não conseguimos cadastrar o aviso de negócio ganho no RD: {e}"[:300]
    with em_conta(ctx.conta_id) as s:
        c = _obter(s) or Conector(conta_id=ctx.conta_id, provedor=PROVEDOR)
        c.token_cifrado, c.segredo_hash, c.webhook_externo = cifrar(token), _hash(segredo), webhook
        c.opcoes, c.erro, c.atualizado_em = {"pesquisar_ao_ganhar": pesquisar_ao_ganhar}, erro, relogio.agora()
        s.add(c)
        s.flush()
        registrar(s, "conector_ligado", "info", {"provedor": PROVEDOR, "pesquisar_ao_ganhar": pesquisar_ao_ganhar},
                  usuario_id=ctx.usuario_id)
        return _json(c)


def alterar(ctx: Contexto, pesquisar_ao_ganhar: bool) -> dict:
    """Liga ou desliga a pesquisa no negócio ganho (cadastra ou remove o aviso no RD)."""
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O RD Station CRM não está conectado.")
        token, webhook = decifrar(c.token_cifrado), c.webhook_externo
    if not token:
        raise AppError(409, "token_invalido", "Conecte o RD Station CRM de novo (o token salvo não pode ser lido).")
    return conectar(ctx, token, pesquisar_ao_ganhar) if (pesquisar_ao_ganhar and not webhook) or \
        (not pesquisar_ao_ganhar and webhook) else ver(ctx)["rdstation_crm"]


def desconectar(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            return
        token, webhook = decifrar(c.token_cifrado), c.webhook_externo
        s.delete(c)
        registrar(s, "conector_desligado", "info", {"provedor": PROVEDOR}, usuario_id=ctx.usuario_id)
    if token and webhook:
        try:
            rdstation.remover_webhook(token, webhook)
        except rdstation.ErroRd:
            pass


# ---- sincronizar (empresas e contatos) --------------------------------------------------------

def _texto(v, limite: int) -> str | None:
    v = (str(v).strip() if v is not None else "")
    return v[:limite] or None


def sincronizar(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = _obter(s)
        if c is None:
            raise AppError(404, "nao_encontrado", "O RD Station CRM não está conectado.")
        token = decifrar(c.token_cifrado)
    if not token:
        raise AppError(409, "token_invalido", "Conecte o RD Station CRM de novo (o token salvo não pode ser lido).")
    try:  # tudo do RD antes de abrir a transação
        orgs = list(rdstation.empresas(token, MAX_EMPRESAS))
        pessoas = list(rdstation.contatos(token, MAX_CONTATOS))
    except rdstation.ErroRd as e:
        with em_conta(ctx.conta_id) as s:
            c = _obter(s)
            if c:
                c.erro = str(e)[:300]
        raise _erro_rd(e)

    r = {"empresas_novas": 0, "empresas_existentes": 0, "contatos_novos": 0, "contatos_existentes": 0,
         "sem_email_ou_telefone": 0, "limite_do_plano": False,
         "cortado": len(orgs) >= MAX_EMPRESAS or len(pessoas) >= MAX_CONTATOS}
    with em_conta(ctx.conta_id) as s:
        marcar(s, "api", ctx.usuario_id)
        nomes_org = {}
        for o in orgs:
            oid, nome = rdstation.ident(o), _texto(o.get("name"), 200)
            if not oid or not nome:
                continue
            nomes_org[oid] = nome
            codigo = f"rd:{oid}"
            existe = s.scalar(select(Empresa.id).where((Empresa.codigo_externo == codigo) | (Empresa.nome == nome))
                              .limit(1))
            if existe:
                r["empresas_existentes"] += 1
            else:
                s.add(Empresa(nome=nome, codigo_externo=codigo))
                s.flush()
                r["empresas_novas"] += 1
        for p in pessoas:
            email = _texto(rdstation.primeiro(p.get("emails"), "email"), 254)
            telefone = rdstation.primeiro(p.get("phones"), "phone")
            telefone = telefone_canonico(telefone or "") or None
            if not email and not telefone:
                r["sem_email_ou_telefone"] += 1
                continue
            pid, org = rdstation.ident(p), str(p.get("organization_id") or "") or None
            dados = SimpleNamespace(
                codigo_externo=f"rd:{pid}" if pid else None, email=email.lower() if email else None,
                telefone=telefone, nome=_texto(p.get("name"), 120),
                empresa=SimpleNamespace(codigo_externo=f"rd:{org}", documento=None, nome=nomes_org.get(org))
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
        c = _obter(s)
        c.sincronizado_em, c.resumo, c.erro = relogio.agora(), r, None
        registrar(s, "conector_sincronizado", "info", {"provedor": PROVEDOR, **r}, usuario_id=ctx.usuario_id)
    return r


def _existe(s, dados) -> bool:
    for coluna, valor in ((Contato.codigo_externo, dados.codigo_externo), (Contato.email, dados.email),
                          (telefone_sql(Contato.telefone), dados.telefone)):
        if valor and s.scalar(select(Contato.id).where(coluna == valor).limit(1)):
            return True
    return False


# ---- aviso do RD (negócio ganho) ---------------------------------------------------------------

def receber_aviso(segredo: str, corpo: dict) -> list:
    """Devolve os envios a processar depois do commit. Nunca levanta: o RD só precisa do 200."""
    if not segredo or len(segredo) > 100:
        return []
    with modo_sistema() as s:
        achado = s.execute(select(Conector.conta_id, Conector.token_cifrado, Conector.opcoes, Conta.nome)
                           .join(Conta, Conta.id == Conector.conta_id)
                           .where(Conector.segredo_hash == _hash(segredo))).one_or_none()
    if achado is None:
        return []
    conta_id, token_cifrado, opcoes, conta_nome = achado
    if not (opcoes or {}).get("pesquisar_ao_ganhar"):
        return []
    doc = corpo.get("document") if isinstance(corpo, dict) else None
    if not isinstance(doc, dict) or not rdstation.ganha(doc):
        return []
    deal_id = rdstation.ident(doc)
    pessoas = doc.get("contacts")
    if not pessoas and deal_id:
        token = decifrar(token_cifrado)
        try:
            completo = rdstation.negociacao(token, deal_id) if token else {}
        except rdstation.ErroRd:
            completo = {}
        pessoas, doc = completo.get("contacts") or [], {**completo, **doc}
    org = doc.get("organization") or {}
    org_id, org_nome = rdstation.ident(org) if isinstance(org, dict) else None, \
        _texto(org.get("name"), 120) if isinstance(org, dict) else None
    envios, erros = [], []
    ci = ContextoIntegracao(conta_id=conta_id, conta_nome=conta_nome)
    for i, p in enumerate((pessoas or [])[:MAX_CONTATOS_NEGOCIO]):
        email = _texto(rdstation.primeiro(p.get("emails"), "email"), 254)
        telefone = telefone_canonico(rdstation.primeiro(p.get("phones"), "phone") or "") or None
        if not email and not telefone:
            continue
        try:
            dados = PesquisaIn(
                email=email, telefone=telefone, nome=_texto(p.get("name"), 120),
                empresa=EmpresaEventoIn(nome=org_nome, codigo_externo=f"rd:{org_id}" if org_id else None)
                if (org_nome or org_id) else None,
                evento="negocio_ganho", referencia=_texto(doc.get("name"), 120), tipo="nps",
                id_evento=f"rd:{deal_id}:{i}" if deal_id else None)
            resultado, _, novos = pesquisas.disparar(ci, dados)
            envios += novos
            if deal_id and resultado.get("convite_id"):  # para devolver a nota à negociação (tarefa `conectores`)
                with em_conta(conta_id) as s:
                    s.execute(update(Convite).where(Convite.id == resultado["convite_id"], Convite.origem_externa.is_(None))
                              .values(origem_externa=f"rd:{deal_id}"[:100]))
        except (AppError, ValueError) as e:
            erros.append(getattr(e, "mensagem", None) or str(e))
    if erros:
        with em_conta(conta_id) as s:
            c = _obter(s)
            if c:
                c.erro = f"Negócio ganho sem pesquisa: {erros[0]}"[:300]
    return envios


# ---- devolver a nota ao CRM (tarefa `conectores`) ------------------------------------------------------

DIAS_DEVOLVER = 7
MAX_DEVOLVER = 100
GRUPOS = {"promotor": "promotor", "neutro": "neutro", "detrator": "detrator"}


def texto_nota(nota: int | None, tipo: str | None, grupo: str | None, nome: str | None, comentario: str | None) -> str:
    """"Pesquisa Toqqi (NPS): Ana Azul deu nota 9 (promotor). Comentário: …" (até 1.000 caracteres)."""
    quem = nome or "O cliente"
    partes = [f"Pesquisa Toqqi ({(tipo or 'nps').upper()}): {quem} deu nota {nota}"
              + (f" ({GRUPOS[grupo]})." if grupo in GRUPOS else ".")]
    if comentario and comentario.strip():
        partes.append(f"Comentário: {comentario.strip()}")
    return " ".join(partes)[:1000]


def devolver_notas() -> dict:
    """Anota no RD Station CRM, na negociação que mandou a pesquisa, as respostas dos últimos 7 dias ainda não
    anotadas (até 100 por vez; a que falhar tenta de novo na próxima rodada, dentro dos 7 dias)."""
    desde = relogio.agora() - timedelta(days=DIAS_DEVOLVER)
    with modo_sistema() as s:
        linhas = s.execute(
            select(Convite.id, Convite.conta_id, Convite.origem_externa, Conector.token_cifrado, Resposta.nota,
                   Resposta.tipo_nota, Resposta.grupo, Resposta.comentario_cliente, Contato.nome)
            .join(Conector, (Conector.conta_id == Convite.conta_id) & (Conector.provedor == "rdstation_crm"))
            .join(Resposta, Resposta.convite_id == Convite.id)
            .outerjoin(Contato, Contato.id == Resposta.contato_id)
            .where(Convite.origem_externa.like("rd:%"), Convite.devolvida_em.is_(None),
                   Convite.respondido_em >= desde, Resposta.nota.is_not(None))
            .order_by(Convite.respondido_em, Convite.id).limit(MAX_DEVOLVER)).all()
    anotadas = falharam = 0
    vistos: set[int] = set()
    for convite_id, conta_id, origem, token_cifrado, nota, tipo, grupo, comentario, nome in linhas:
        if convite_id in vistos:
            continue
        vistos.add(convite_id)
        try:
            rdstation.anotar(decifrar(token_cifrado), origem.split(":", 1)[1], texto_nota(nota, tipo, grupo, nome, comentario))
        except rdstation.ErroRd:
            falharam += 1
            continue
        with modo_sistema() as s:
            s.execute(update(Convite).where(Convite.id == convite_id).values(devolvida_em=relogio.agora()))
        anotadas += 1
    return {"anotadas": anotadas, "falharam": falharam}
