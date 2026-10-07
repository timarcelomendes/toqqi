"""Páginas públicas de pesquisa (sem login).

A conta é descoberta em modo sistema só pela busca do hash do token (convite) ou do código público
(formulário); todo o resto acontece dentro de em_conta(conta).

Etapa 5f: cada envio de resposta (convite e link público) e de indicação grava o registro de acesso (`core.acessos`,
com o IP do cliente) na mesma transação; abrir as páginas não grava.

Etapa 5l: o formulário vai com a lógica, o HTML dos blocos de conteúdo (variáveis escapadas), `prefixo_imagens` e
`tem_finais` (dentro de `formulario`, e repetidos no topo da resposta); ao responder, a API descarta o que ficou fora do
caminho, escolhe o final (`final_id`, `html_final`, `botao_final`) e grava a versão publicada na resposta.

O cliente pode mudar a resposta (docs/api-editar-resposta.md), com `formularios.permite_editar`, até 7 dias depois de
responder (`registro.pode_editar`):
- convite: abrir a página já respondida traz `edicao` {ate, respondida_em, respostas}; responder de novo troca a
  resposta (mesma linha); fora do prazo (ou com a edição desligada), 409 `ja_respondido` como antes;
- link público: o envio devolve `edicao` {chave, ate}; com a chave, `editar_formulario` troca a resposta (a chave fica
  só na página aberta: reabrir o link começa outra resposta). Chave errada ou prazo vencido: 409
  `edicao_indisponivel`.
Nas duas, a tela final traz `edicao` {ate} (e a chave, no link público) enquanto der para mudar.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, select

from toqqi.core import acessos, relogio
from toqqi.core.planos import url_mencao
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.errors import AppError
from toqqi.core.security import hash_token
from toqqi.modelos import Conta, Contato, Convite, Formulario, Resposta
from toqqi.modulos.crescimento import depoimentos, indicacoes
from toqqi.modulos.envios import configuracao as config_envios
from toqqi.modulos.imagens.servico import logo_para_cliente
from toqqi.modulos.respostas.convites import CANAL_RESPOSTA, limpar_contexto
from toqqi.modulos.respostas.registro import (
    editar_resposta,
    formulario_publico,
    gravar_resposta,
    pode_editar,
    prazo_edicao,
    tela_final,
    validar_respostas,
    variaveis,
)

JANELA_DUPLICADA = timedelta(minutes=10)
_RE_CODIGO = re.compile(r"^[a-z0-9]{8}$")


MSG_JA_RESPONDIDO = "Você já respondeu esta pesquisa. Obrigado!"
MSG_EDICAO_INDISPONIVEL = "Não dá mais para mudar esta resposta. O prazo terminou ou o link mudou."


def link_invalido() -> AppError:
    return AppError(404, "link_invalido", "Este link de pesquisa não é válido ou não está mais disponível.")


def _resposta_do_convite(s, c: Convite) -> Resposta | None:
    return s.scalar(select(Resposta).where(Resposta.convite_id == c.id).order_by(Resposta.id.desc()).limit(1))


def _hash_chave(segredo: str) -> str:
    return hashlib.sha256(segredo.encode()).hexdigest()


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
    # etapa 5i: "Pesquisa feita com Toqqi" (null onde a conta tirou e o plano permite)
    aparece = config_envios.mencao(s, config_envios.obter(s, criar=False))["aparece"]
    dados["mencao_toqqi"] = {"texto": "Pesquisa feita com Toqqi", "url": url_mencao("pagina")} if aparece else None
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


def _pagina(dados: dict, **extra) -> dict:
    """{formulario, variaveis, ...}, com `prefixo_imagens` e `tem_finais` também no topo (como no `formulario`)."""
    return {**dados, **extra, "prefixo_imagens": dados["formulario"]["prefixo_imagens"],
            "tem_finais": dados["formulario"]["tem_finais"]}


def abrir_convite(token: str) -> dict:
    """{formulario, variaveis, ja_respondido, edicao}: `edicao` = {ate, respondida_em, respostas} quando o convite já
    foi respondido e o cliente ainda pode mudar a resposta; senão null."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id)
        f, _, v = _dados_convite(s, c)
        edicao = None
        if c.respondido_em is not None:
            r = _resposta_do_convite(s, c)
            if pode_editar(f, r, relogio.agora()):
                edicao = {"ate": prazo_edicao(r), "respondida_em": r.criada_em, "respostas": r.respostas}
        return _pagina({"formulario": _publico(s, conta_id, f, v), "variaveis": v},
                       ja_respondido=c.respondido_em is not None, edicao=edicao)


def responder_convite(token: str, respostas: dict, ip: str | None) -> dict:
    """{titulo_final, texto_final, final_id, html_final, botao_final, indicacao, depoimento}: o final escolhido pela
    lógica (`registro.tela_final`); `indicacao` = {titulo, texto, recompensa} do convite de indicação (etapa 5c)
    quando a nota dá direito e as indicações estão ligadas na conta liberada; senão null."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id, with_for_update=True)  # uma resposta por convite, mesmo em corrida
        if c.respondido_em is not None:
            # já respondido: com a edição ligada e no prazo, a resposta nova troca a de antes (a mesma linha)
            f = s.get(Formulario, c.formulario_id)
            r = _resposta_do_convite(s, c)
            if not _disponivel(f) or not pode_editar(f, r, relogio.agora()):
                raise AppError(409, "ja_respondido", MSG_JA_RESPONDIDO)
            _, _, v = _dados_convite(s, c)
            r = editar_resposta(s, f, r, respostas, v)
        else:
            f, contato, v = _dados_convite(s, c)
            r = gravar_resposta(s, f, respostas, CANAL_RESPOSTA[c.canal], v, contato=contato, empresa_id=c.empresa_id,
                                convite_id=c.id, contexto=c.contexto, referencia=c.referencia, ip_hash=ip_hash(ip))
            c.respondido_em = func.now()
        acessos.registrar(s, "resposta", conta_id=conta_id, item_id=r.id)
        return {**tela_final(f, v, r.respostas), "indicacao": indicacoes.convite_de_indicacao(s, r, v),
                "depoimento": depoimentos.tela_final(s, r, v.get("empresa") or ""),
                "edicao": {"ate": prazo_edicao(r)} if f.permite_editar else None}


def autorizar_depoimento(token: str) -> dict:
    """Melhoria 5: o cliente autoriza publicar o comentário (só pelo convite, depois de responder)."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id, with_for_update=True)
        r = indicacoes.resposta_do_convite(s, c.id)
        resultado = depoimentos.autorizar(s, r)
        return resultado


def indicar(token: str, dados) -> dict:
    """Indicação feita na tela final da pesquisa (só pelo convite: o link público não tem a quem atribuir). A repetida
    (mesmo telefone ou e-mail de uma indicação aberta) responde igual, sem criar outra. Formulário desativado ou
    arquivado depois da resposta: 409 `indicacao_indisponivel` (como a resposta arquivada)."""
    conta_id, convite_id = _achar_convite(token)
    with em_conta(conta_id) as s:
        c = s.get(Convite, convite_id, with_for_update=True)  # o limite de 3 por convite não corre
        if not _disponivel(s.get(Formulario, c.formulario_id)):
            raise indicacoes.indisponivel()
        i = indicacoes.criar_publica(s, c, dados)
        # a repetida (nada criado) também é um acesso: entra sem a indicação
        acessos.registrar(s, "indicacao", conta_id=conta_id, item_id=i.id if i is not None else None)
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
        return _pagina({"formulario": _publico(s, conta_id, f, v), "variaveis": v})


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
                # sem chave de edição: num tablet de balcão, a resposta gravada pode ser de outra pessoa
                acessos.registrar(s, "resposta", conta_id=conta_id)
                return {**tela_final(f, v, validadas[0]), "edicao": None}
        r = gravar_resposta(s, f, dados.respostas, dados.canal, v, contexto=limpar_contexto(dados.contexto),
                            referencia=dados.referencia, ip_hash=h, respostas_validadas=validadas)
        edicao = None
        if f.permite_editar:  # a chave de edição fica só na página aberta (o banco guarda o sha256 do segredo)
            segredo = secrets.token_urlsafe(24)
            r.edicao_hash = _hash_chave(segredo)
            s.flush()
            edicao = {"chave": f"{r.id}.{segredo}", "ate": prazo_edicao(r)}
        acessos.registrar(s, "resposta", conta_id=conta_id, item_id=r.id)
        return {**tela_final(f, v, r.respostas), "edicao": edicao}


def editar_formulario(codigo: str, dados, ip: str | None) -> dict:
    """Link público: troca a resposta enviada há pouco, com a chave devolvida no envio (até 7 dias, edição ligada)."""
    conta_id, form_id = _achar_formulario(codigo)
    rid, _, segredo = dados.chave.partition(".")
    if not rid.isdigit() or len(rid) > 18 or not segredo:
        raise AppError(409, "edicao_indisponivel", MSG_EDICAO_INDISPONIVEL)
    with em_conta(conta_id) as s:
        f = _form_publico(s, form_id)
        r = s.scalar(select(Resposta).where(Resposta.id == int(rid), Resposta.formulario_id == f.id)
                     .with_for_update())
        if (r is None or not r.edicao_hash or not hmac.compare_digest(r.edicao_hash, _hash_chave(segredo))
                or not pode_editar(f, r, relogio.agora())):
            raise AppError(409, "edicao_indisponivel", MSG_EDICAO_INDISPONIVEL)
        v = variaveis(_nome_conta(s), referencia=r.referencia)
        r = editar_resposta(s, f, r, dados.respostas, v)
        acessos.registrar(s, "resposta", conta_id=conta_id, item_id=r.id)
        return {**tela_final(f, v, r.respostas), "edicao": {"chave": dados.chave, "ate": prazo_edicao(r)}}
