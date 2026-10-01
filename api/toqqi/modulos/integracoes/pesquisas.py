"""Disparo por evento (POST /integracao/pesquisas e /integracao/csat): o ERP avisa "pedido entregue, pesquise
este cliente". Tudo roda numa transação da conta da chave. Com `id_evento`, o mesmo pedido em 24 h devolve a
mesma resposta (trava pelo id: dois pedidos iguais ao mesmo tempo não disparam duas vezes).

Respeita assinatura, descadastro (e-mail ou telefone), contato inativo e descanso; o provedor de e-mail e
`envios_ativos` só valem quando a pesquisa vai por e-mail. Não respeita janela de horário nem intervalo.
"""
from datetime import timedelta

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import em_conta, travar
from toqqi.core.errors import AppError
from toqqi.core.texto import telefone_canonico
from toqqi.modelos import ConfigEnvios, Contato, Convite, Empresa, EventoIdempotencia, Formulario
from toqqi.modulos.contatos.servico import codigo_livre, formulario_para_envio
from toqqi.modulos.envios.configuracao import exigir, obter
from toqqi.modulos.envios.descadastro import esta_descadastrado, telefone_sql
from toqqi.modulos.envios.processamento import Pares, criar_convite
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.modulos.respostas.convites import link_do_convite, novo_convite, token_do_convite
from toqqi.modulos.whatsapp import franquia

VALIDADE_ID_EVENTO = timedelta(hours=24)
NOME_TIPO = {"nps": "NPS", "csat": "CSAT"}
SEM_CANAL = {
    "email": "O contato não tem e-mail.",
    "whatsapp": "O WhatsApp automático não está disponível para este contato (sem telefone, WhatsApp "
                "desligado ou franquia do mês esgotada).",
}


def _resultado(situacao: str, mensagem: str, contato: Contato | None = None, convite: Convite | None = None,
               link: str | None = None, canal: str | None = None) -> dict:
    return {"situacao": situacao, "convite_id": convite.id if convite else None, "link": link, "canal": canal,
            "contato_id": contato.id if contato else None, "mensagem": mensagem}


def _formulario(s: Session, dados, tipo_padrao: str | None) -> Formulario:
    if dados.formulario_id is not None:
        return formulario_para_envio(s, dados.formulario_id)
    tipo = dados.tipo or tipo_padrao or ("csat" if dados.referencia else "nps")
    f = s.scalar(select(Formulario).where(getattr(Formulario, f"padrao_{tipo}").is_(True)))
    if f is None or not f.ativo or f.arquivado:
        msg = f"A conta não tem um formulário padrão de {NOME_TIPO[tipo]} ativo. Informe o formulario_id."
        raise AppError(422, "dados_invalidos", msg, {"tipo": msg})
    return f


def _empresa(s: Session, e) -> int | None:
    """Procura por código externo, documento ou nome; cria se vier o nome."""
    if e is None:
        return None
    for coluna, valor in ((Empresa.codigo_externo, e.codigo_externo), (Empresa.documento, e.documento),
                          (Empresa.nome, e.nome)):
        if valor:
            achada = s.scalar(select(Empresa.id).where(coluna == valor).order_by(Empresa.id).limit(1))
            if achada is not None:
                return achada
    if not e.nome:
        return None
    nova = Empresa(nome=e.nome, documento=e.documento, codigo_externo=e.codigo_externo)
    s.add(nova)
    s.flush()
    return nova.id


def _contato(s: Session, dados) -> Contato:
    """Procura por código externo, depois e-mail, depois telefone; senão cria (o banco aplica o limite do plano:
    402). Um contato achado só ganha os dados que não tinha."""
    buscas = [(Contato.codigo_externo, dados.codigo_externo), (Contato.email, dados.email),
              (telefone_sql(Contato.telefone), telefone_canonico(dados.telefone or ""))]
    contato = None
    for coluna, valor in buscas:
        if valor:
            contato = s.scalar(select(Contato).where(coluna == valor)
                               .order_by(Contato.ativo.desc(), Contato.id).limit(1))
            if contato is not None:
                break
    empresa_id = _empresa(s, dados.empresa)
    if contato is None:
        contato = Contato(codigo=codigo_livre(s), nome=(dados.nome or dados.email or dados.telefone)[:120],
                          email=dados.email, telefone=dados.telefone, codigo_externo=dados.codigo_externo,
                          empresa_id=empresa_id)
        s.add(contato)
        s.flush()
        return contato
    if not contato.email and dados.email and not s.scalar(select(exists().where(Contato.email == dados.email))):
        contato.email = dados.email
    contato.telefone = contato.telefone or dados.telefone
    contato.codigo_externo = contato.codigo_externo or dados.codigo_externo
    contato.empresa_id = contato.empresa_id or empresa_id
    s.flush()
    return contato


def _em_descanso(cfg: ConfigEnvios, contato: Contato) -> str | None:
    if cfg.descanso_dias == 0 or contato.ultimo_envio is None:
        return None
    dias = (relogio.hoje() - contato.ultimo_envio.astimezone(relogio.FUSO).date()).days
    if dias >= cfg.descanso_dias:
        return None
    quando = "hoje" if dias == 0 else "há 1 dia" if dias == 1 else f"há {dias} dias"
    return f"O contato recebeu uma pesquisa {quando} (descanso de {cfg.descanso_dias} dias)."


def _canais(canal: str, cfg: ConfigEnvios) -> tuple[str, ...]:
    if canal != "auto":
        return (canal,)
    return ("email", "whatsapp") if cfg.canal == "email" else ("whatsapp", "email")


def _disparar(s: Session, dados, tipo_padrao: str | None, assunto: str | None) -> tuple[dict, Pares]:
    cfg = obter(s)
    exigir(s, cfg, ("assinatura",))
    f = _formulario(s, dados, tipo_padrao)
    contato = _contato(s, dados)
    if not contato.ativo:
        return _resultado("ignorado_inativo", "O contato está inativo.", contato), []
    if not contato.recebe_pesquisas or esta_descadastrado(s, contato.email, contato.telefone):
        return _resultado("ignorado_descadastrado", "O contato saiu da lista e não recebe pesquisas.", contato), []
    descanso = None if dados.ignorar_descanso else _em_descanso(cfg, contato)
    if descanso:
        return _resultado("ignorado_descanso", descanso, contato), []
    campos = {"evento": dados.evento, "referencia": dados.referencia, "assunto": assunto,
              "contexto": dados.contexto.model_dump() if dados.contexto else {}}
    if dados.enviar and dados.canal != "link":
        canais = _canais(dados.canal, cfg)
        wa = franquia.disponivel(s) if "whatsapp" in canais else None
        e = criar_convite(s, cfg, contato, "automatico", canais, wa, formulario_id=f.id, **campos)
        if e is not None:
            if e.canal == "email":
                exigir(s, cfg, ("provedor", "envios_ativos"))
            convite = s.get(Convite, e.convite_id)
            meio = "WhatsApp" if e.canal == "whatsapp" else "e-mail"
            return _resultado("enviado", f"Pesquisa enviada por {meio}.", contato, convite,
                              link_do_convite(token_do_convite(convite.token_semente)), e.canal), [(e.conta_id, e.id)]
        if dados.canal != "auto":
            return _resultado("sem_canal", SEM_CANAL[dados.canal], contato), []
    convite, token = novo_convite(s, f.id, contato_id=contato.id, canal="link_manual", empresa_id=contato.empresa_id,
                                  **campos)
    return _resultado("link_gerado", "Link da pesquisa gerado.", contato, convite, link_do_convite(token), "link"), []


def disparar(ci: ContextoIntegracao, dados, tipo_padrao: str | None = None,
             assunto: str | None = None) -> tuple[dict, bool, Pares]:
    """(resposta, se é nova, envios a processar depois do commit)."""
    if not dados.email and not dados.telefone:
        msg = "Informe o e-mail ou o telefone."
        raise AppError(422, "dados_invalidos", msg, {"email": msg, "telefone": msg})
    with em_conta(ci.conta_id) as s:
        if dados.id_evento:
            travar(s, f"evento:{ci.conta_id}:{dados.id_evento}")
            s.execute(delete(EventoIdempotencia).where(EventoIdempotencia.expira <= relogio.agora()))
            salvo = s.get(EventoIdempotencia, (ci.conta_id, dados.id_evento))
            if salvo is not None:
                return salvo.resposta, False, []
        resposta, envios = _disparar(s, dados, tipo_padrao, assunto)
        if dados.id_evento:
            s.add(EventoIdempotencia(id_evento=dados.id_evento, resposta=jsonable_encoder(resposta),
                                     expira=relogio.agora() + VALIDADE_ID_EVENTO))
    return resposta, True, envios
