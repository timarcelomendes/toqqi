"""WhatsApp automático (API oficial da Meta, Cloud API): conexão da conta por formulário, liga/desliga,
excedente, desconexão, mensagem de teste e situação (com a franquia do mês).

Ao conectar, os dados são conferidos na Graph API (número e modelo). O token fica cifrado (core.segredos) e
nunca volta nas respostas. O número (phone_number_id) só pode estar em uma conta da plataforma.

Situação e registro do número (docs/api-whatsapp-registro.md): `numero` lê na Meta se o número já está registrado na
Cloud API; `registrar_numero` faz o registro com o token salvo e um PIN que a pessoa digita (nunca guardado). Até
`MAX_TENTATIVAS_REGISTRO` pedidos em 72 horas por conta (a Meta bloqueia o número por 72 horas depois de 10).
"""
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.segredos import cifrar, decifrar
from toqqi.modelos import Auditoria, ConfigEnvios, Conta, WhatsappConta
from toqqi.modulos.whatsapp import franquia, graph, modelo

CAMINHO_WEBHOOK = "/api/v1/publico/whatsapp/webhook"
MAX_TENTATIVAS_REGISTRO = 8
JANELA_REGISTRO = timedelta(hours=72)
EVENTOS_REGISTRO = ("whatsapp_numero_registrado", "whatsapp_registro_recusado")
MSG_REGISTRADO = ("Pronto! O número foi registrado na Meta. Em alguns minutos ele aparece como Conectado no "
                  "WhatsApp Manager.")
MSG_TENTATIVAS = ("Já foram {n} tentativas de registro nos últimos 3 dias. A Meta bloqueia o número por 72 horas "
                  "depois de 10: confira o PIN no WhatsApp Manager e tente de novo mais tarde.")


def _json(s, ctx: Contexto) -> dict:
    wc = franquia.conectada(s)
    admin = ctx.perfil == "admin"
    cfg = config()
    return {
        "conectado": wc is not None,
        "numero_exibicao": wc.numero_exibicao if wc else None,
        "nome_verificado": wc.nome_verificado if wc else None,
        "phone_number_id": wc.phone_number_id if wc else None,
        "waba_id": wc.waba_id if wc else None,
        "modelo": {"nome": wc.modelo_nome, "idioma": wc.modelo_idioma} if wc else None,
        "ativo": bool(wc and wc.ativo),
        "franquia": franquia.franquia_json(s),
        "ultimo_erro": wc.ultimo_erro if wc else None,
        # para colar no painel da Meta (só o administrador vê)
        "webhook_url": f"{cfg.API_PUBLIC_URL.rstrip('/')}{CAMINHO_WEBHOOK}" if admin else None,
        "webhook_verificacao": (cfg.WHATSAPP_VERIFY_TOKEN or None) if admin else None,
    }


def _invalido(campo: str, mensagem: str) -> AppError:
    return AppError(422, "dados_invalidos", mensagem, {campo: mensagem})


def nao_conectado() -> AppError:
    return AppError(409, "whatsapp_nao_conectado", "Conecte o WhatsApp em Integrações primeiro.")


def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _json(s, ctx)


def conectar(ctx: Contexto, dados) -> dict:
    em_uso = AppError(409, "numero_em_uso", "Este número de WhatsApp já está conectado a outra conta da Toqqi.")
    with modo_sistema() as s:  # o número só pode estar em uma conta: confere entre todas
        dono = s.scalar(select(WhatsappConta.conta_id).where(WhatsappConta.phone_number_id == dados.phone_number_id))
    if dono is not None and dono != ctx.conta_id:
        raise em_uso
    try:
        numero = graph.dados_do_numero(dados.token, dados.phone_number_id)
    except graph.FalhaGraph as f:
        if graph.traduzir(f.status, f.codigo)[0] == graph.MSG_TOKEN:
            raise _invalido("token", "A Meta recusou o token. Use o token permanente do usuário do sistema.")
        raise _invalido("phone_number_id", "Não encontramos este número com esse token. Confira o identificador "
                                           "do número (Phone number ID).")
    try:
        modelos = graph.modelos(dados.token, dados.waba_id, dados.modelo_nome)
    except graph.FalhaGraph:
        raise _invalido("waba_id", "Não conseguimos ler os modelos desta conta do WhatsApp. Confira o identificador "
                                   "da conta (WABA ID) e se o token tem acesso a ela.")
    try:
        botao = modelo.conferir(modelos, dados.modelo_nome, dados.modelo_idioma)
    except modelo.ModeloInvalido as e:
        raise _invalido("modelo_nome", str(e))
    valores = {"phone_number_id": dados.phone_number_id, "waba_id": dados.waba_id, "token_cifrado": cifrar(dados.token),
               "modelo_nome": dados.modelo_nome, "modelo_idioma": dados.modelo_idioma, "modelo_botao": botao,
               "ativo": True, "ultimo_erro": None, "numero_exibicao": numero.get("display_phone_number"),
               "nome_verificado": numero.get("verified_name"), "conectado_em": relogio.agora()}
    try:
        with em_conta(ctx.conta_id) as s:
            s.execute(insert(WhatsappConta).values(**valores)
                      .on_conflict_do_update(index_elements=["conta_id"], set_=valores))
            registrar(s, "whatsapp_conectado", "atencao", {"numero": valores["numero_exibicao"]},
                      usuario_id=ctx.usuario_id)
            return _json(s, ctx)
    except IntegrityError:  # outra conta conectou o mesmo número ao mesmo tempo
        raise em_uso


def alterar(ctx: Contexto, dados) -> dict:
    novos = {c: getattr(dados, c) for c in dados.model_fields_set if getattr(dados, c) is not None}
    with em_conta(ctx.conta_id) as s:
        wc = s.scalar(select(WhatsappConta).with_for_update())
        if wc is None:
            raise nao_conectado()
        for campo, valor in novos.items():
            setattr(wc, campo, valor)
        s.flush()
        return _json(s, ctx)


def desconectar(ctx: Contexto) -> None:
    """Apaga a conexão e o token; os envios voltam a ser só por e-mail."""
    with em_conta(ctx.conta_id) as s:
        apagada = s.execute(delete(WhatsappConta).returning(WhatsappConta.numero_exibicao)).one_or_none()
        s.execute(update(ConfigEnvios).values(canal="email"))
        if apagada is not None:
            registrar(s, "whatsapp_desconectado", "atencao", {"numero": apagada[0]}, usuario_id=ctx.usuario_id)


def testar(ctx: Contexto, telefone: str) -> dict:
    """Manda o modelo para o número (link de exemplo); não usa a franquia."""
    with em_conta(ctx.conta_id) as s:
        wc = franquia.conectada(s)
        if wc is None:
            raise nao_conectado()
        token = decifrar(wc.token_cifrado)
        empresa = s.scalar(select(Conta.nome))
        corpo = modelo.corpo_modelo(nome_modelo=wc.modelo_nome, idioma=wc.modelo_idioma, botao=wc.modelo_botao,
                                    telefone=telefone, primeiro_nome=(ctx.usuario.get("nome") or "").split(" ")[0],
                                    empresa=empresa, referencia=modelo.REFERENCIA_PADRAO, token="teste")
        pnid = wc.phone_number_id
    if token is None:
        raise AppError(409, "falha_envio", graph.MSG_TOKEN)
    try:
        graph.enviar_mensagem(token, pnid, corpo)
    except graph.FalhaGraph as f:
        mensagem, da_conta = graph.traduzir(f.status, f.codigo)
        if da_conta:
            with em_conta(ctx.conta_id) as s:
                s.execute(update(WhatsappConta).values(ultimo_erro=mensagem))
        raise AppError(409, "falha_envio", mensagem)
    return {"mensagem": f"Enviamos a mensagem de teste para o número terminado em {telefone[-4:]}."}


# ---- situação e registro do número na Meta ------------------------------------------------------------------------

def _conexao(s) -> tuple[str | None, str, str | None]:
    wc = franquia.conectada(s)
    if wc is None:
        raise nao_conectado()
    return decifrar(wc.token_cifrado), wc.phone_number_id, wc.numero_exibicao


def _situacao_json(dados: dict) -> dict:
    codigo = str(dados.get("code_verification_status") or "").upper()
    return {"situacao": graph.situacao(dados), "status": str(dados.get("status") or "").upper() or None,
            "codigo_confirmado": codigo == "VERIFIED" if codigo else None}


def numero(ctx: Contexto) -> dict:
    """Situação do número na Meta, lida na hora: {situacao, status, codigo_confirmado}."""
    with em_conta(ctx.conta_id) as s:
        token, pnid, _ = _conexao(s)
    if token is None:
        raise AppError(409, "falha_meta", graph.MSG_TOKEN)
    try:
        dados = graph.situacao_do_numero(token, pnid)
    except graph.FalhaGraph as f:
        raise AppError(409, "falha_meta", graph.traduzir(f.status, f.codigo)[0])
    return _situacao_json(dados)


def registrar_numero(ctx: Contexto, pin: str) -> dict:
    """Registra o número na Cloud API com o token salvo. Cada pedido (aceito ou recusado) fica na auditoria, que
    também conta o limite. Aceito: limpa o erro "sem número registrado" do último envio."""
    with em_conta(ctx.conta_id) as s:
        token, pnid, exibicao = _conexao(s)
        feitas = s.scalar(select(func.count()).select_from(Auditoria).where(
            Auditoria.evento.in_(EVENTOS_REGISTRO), Auditoria.criado_em > func.now() - JANELA_REGISTRO))
    if feitas >= MAX_TENTATIVAS_REGISTRO:
        raise AppError(409, "muitas_tentativas_registro", MSG_TENTATIVAS.format(n=feitas))
    if token is None:
        raise AppError(409, "falha_meta", graph.MSG_TOKEN)
    try:
        graph.registrar_numero(token, pnid, pin)
    except graph.FalhaGraph as f:
        with em_conta(ctx.conta_id) as s:
            registrar(s, "whatsapp_registro_recusado", "atencao", {"numero": exibicao, "codigo": f.codigo},
                      usuario_id=ctx.usuario_id)
        raise AppError(409, "registro_recusado", graph.traduzir_registro(f.status, f.codigo))
    with em_conta(ctx.conta_id) as s:
        s.execute(update(WhatsappConta).where(WhatsappConta.ultimo_erro == graph.MSG_CONTA).values(ultimo_erro=None))
        registrar(s, "whatsapp_numero_registrado", "sucesso", {"numero": exibicao}, usuario_id=ctx.usuario_id)
    return {"mensagem": MSG_REGISTRADO,
            "numero": {"situacao": "registrado", "status": None, "codigo_confirmado": True}}
