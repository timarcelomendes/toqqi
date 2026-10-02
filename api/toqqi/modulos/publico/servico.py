"""Páginas públicas de pesquisa (sem login).

A conta é descoberta em modo sistema só pela busca do hash do token (convite) ou do código público
(formulário); todo o resto acontece dentro de em_conta(conta).
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, select

from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.errors import AppError
from toqqi.core.security import hash_token
from toqqi.modelos import Conta, Contato, Convite, Formulario, Resposta
from toqqi.modulos.crescimento import indicacoes
from toqqi.modulos.imagens.servico import logo_para_cliente
from toqqi.modulos.respostas.convites import CANAL_RESPOSTA, limpar_contexto
from toqqi.modulos.respostas.registro import (
    formulario_publico,
    gravar_resposta,
    texto_final,
    validar_respostas,
    variaveis,
)

JANELA_DUPLICADA = timedelta(minutes=10)
_RE_CODIGO = re.compile(r"^[a-z0-9]{8}$")


def link_invalido() -> AppError:
    return AppError(404, "link_invalido", "Este link de pesquisa não é válido ou não está mais disponível.")


def ip_hash(ip: str | None) -> str | None:
    """sha256(ip + sal do dia): identifica repetição no mesmo dia sem guardar o IP."""
    if not ip:
        return None
    dia = datetime.now(timezone.utc).date().isoformat()
    return hashlib.sha256(f"{config().JWT_SECRET}|{dia}|{ip}".encode()).hexdigest()


def _nome_conta(s) -> str:
    return s.scalar(select(Conta.nome)) or ""


def _disponivel(f: Formulario | None) -> bool:
    return f is not None and f.ativo and not f.arquivado


def _publico(s, conta_id: int, f: Formulario, v: dict) -> dict:
    """Formulário para a página pública; sem logo próprio, o tema leva o logo da conta (se houver)."""
    dados = formulario_publico(f, v)
    dados["tema"]["logo_url"] = logo_para_cliente(s, conta_id, (f.tema or {}).get("logo_url"))
    return dados


# ---- convites ---------------------------------------------------------------

def _achar_convite(token: str) -> tuple[int, int]:
    if not token or len(token) > 200:
        raise link_invalido()
    with modo_sistema() as s:  # só descobre a conta pelo hash
        achado = s.execute(select(Convite.conta_id, Convite.id)
                           .where(Convite.token_hash == hash_token(token))).one_or_none()
    if achado is None:
        raise link_invalido()
    return achado[0], achado[1]


def _dados_convite(s, c: Convite) -> tuple[Formulario, Contato | None, dict]:
    f = s.get(Formulario, c.formulario_id)
    if not _disponivel(f):
        raise link_invalido()
    contato = s.get(Contato, c.contato_id) if c.contato_id else None
    v = variaveis(_nome_conta(s), contato.nome if contato else None, c.assunto, c.referencia)
    return f, contato, v


def abrir_convite(token: str) -> dict:
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id)
        f, _, v = _dados_convite(s, c)
        return {"formulario": _publico(s, conta_id, f, v), "variaveis": v, "ja_respondido": c.respondido_em is not None}


def responder_convite(token: str, respostas: dict, ip: str | None) -> dict:
    """{titulo_final, texto_final, indicacao}: `indicacao` = {titulo, texto, recompensa} do convite de indicação
    (etapa 5c) quando a nota dá direito e as indicações estão ligadas na conta liberada; senão null."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id, with_for_update=True)  # uma resposta por convite, mesmo em corrida
        if c.respondido_em is not None:
            raise AppError(409, "ja_respondido", "Você já respondeu esta pesquisa. Obrigado!")
        f, contato, v = _dados_convite(s, c)
        r = gravar_resposta(s, f, respostas, CANAL_RESPOSTA[c.canal], v, contato=contato, empresa_id=c.empresa_id,
                            convite_id=c.id, contexto=c.contexto, referencia=c.referencia, ip_hash=ip_hash(ip))
        c.respondido_em = func.now()
        return {**texto_final(f, v), "indicacao": indicacoes.convite_de_indicacao(s, r, v)}


def indicar(token: str, dados) -> dict:
    """Indicação feita na tela final da pesquisa (só pelo convite: o link público não tem a quem atribuir). A repetida
    (mesmo telefone ou e-mail de uma indicação aberta) responde igual, sem criar outra. Formulário desativado ou
    arquivado depois da resposta: 409 `indicacao_indisponivel` (como a resposta arquivada)."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id, with_for_update=True)  # o limite de 3 por convite não corre
        if not _disponivel(s.get(Formulario, c.formulario_id)):
            raise indicacoes.indisponivel()
        indicacoes.criar_publica(s, c, dados)
    return {"mensagem": indicacoes.MSG_OBRIGADO}


# ---- link público do formulário --------------------------------------------

def _achar_formulario(codigo: str) -> tuple[int, int]:
    codigo = (codigo or "").lower()
    if not _RE_CODIGO.match(codigo):
        raise link_invalido()
    with modo_sistema() as s:  # só descobre a conta pelo código
        achado = s.execute(select(Formulario.conta_id, Formulario.id)
                           .where(Formulario.codigo_publico == codigo)).one_or_none()
    if achado is None:
        raise link_invalido()
    return achado[0], achado[1]


def _form_publico(s, form_id: int) -> Formulario:
    f = s.get(Formulario, form_id)
    if not _disponivel(f) or not f.publico:
        raise link_invalido()
    return f


def abrir_formulario(codigo: str, referencia: str | None = None) -> dict:
    conta_id, form_id = _achar_formulario(codigo)
    with em_conta(conta_id) as s:
        f = _form_publico(s, form_id)
        v = variaveis(_nome_conta(s), referencia=(referencia or "")[:120] or None)
        return {"formulario": _publico(s, conta_id, f, v), "variaveis": v}


def responder_formulario(codigo: str, dados, ip: str | None) -> dict:
    conta_id, form_id = _achar_formulario(codigo)
    h = ip_hash(ip)
    with em_conta(conta_id) as s:
        f = _form_publico(s, form_id)
        v = variaveis(_nome_conta(s), referencia=dados.referencia)
        validadas = validar_respostas(f.perguntas, dados.respostas)
        if h is not None:
            repetida = s.scalar(select(exists().where(
                Resposta.formulario_id == f.id,
                Resposta.ip_hash == h,
                Resposta.respostas == validadas[0],
                Resposta.criada_em > func.now() - JANELA_DUPLICADA,
            )))
            if repetida:  # mesma resposta, mesmo IP, há pouco: responde igual e não grava de novo
                return texto_final(f, v)
        gravar_resposta(s, f, dados.respostas, dados.canal, v, contexto=limpar_contexto(dados.contexto),
                        referencia=dados.referencia, ip_hash=h, respostas_validadas=validadas)
        return texto_final(f, v)
