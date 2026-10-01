"""Configurações de envio da conta e pré-condições de qualquer envio."""
from datetime import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.errors import AppError
from toqqi.modelos import ConfigEnvios, Conta, Formulario

DIAS_LEMBRETES_PADRAO = [3, 7, 15]
PADROES = {
    "envios_ativos": False,
    "envio_automatico": False,
    "intervalo_dias": 90,
    "descanso_dias": 30,
    "lembretes": 3,
    "dias_lembretes": DIAS_LEMBRETES_PADRAO,
    "janela_inicio": time(8, 0),
    "janela_fim": time(18, 0),
    "so_dias_uteis": True,
    "responder_para": None,
    "remetente_nome": None,
    "assunto_convite": "{empresa} quer saber a sua opinião",
    "texto_convite": "Olá, {nome}!\n\nSua opinião ajuda a {empresa} a melhorar. Leva menos de um minuto.",
    "assunto_lembrete": "Lembrete: {empresa} quer saber a sua opinião",
    "texto_lembrete": "Olá, {nome}! Ainda dá tempo de responder a nossa pesquisa.\n\n"
                      "Sua opinião ajuda a {empresa} a melhorar. Leva menos de um minuto.",
    "texto_whatsapp": "Olá, {nome}! Aqui é da {empresa}. Pode responder uma pesquisa rápida? Leva 1 minuto: {link}",
    "agradecimento_ativo": True,
    "canal": "email",
    "agradecimento": {
        "promotor": "Olá, {nome}! Muito obrigado pela sua nota {nota}. Ficamos felizes em saber que você "
                    "confia na {empresa}.",
        "neutro": "Olá, {nome}! Obrigado pela sua resposta. Vamos usar a sua opinião para a {empresa} "
                  "melhorar ainda mais.",
        "detrator": "Olá, {nome}! Obrigado por ser sincero com a gente. Sentimos muito que a sua experiência "
                    "não tenha sido boa; a {empresa} vai usar a sua opinião para melhorar.",
    },
}
CAMPOS = list(PADROES) + ["formulario_id"]
ROTA_CONFIG = "/configuracoes/envios"
ROTA_ASSINATURA = "/assinatura"


def obter(s: Session, criar: bool = True, travar: bool = False) -> ConfigEnvios:
    """Configuração da conta da transação. Sem registro: cria com os padrões (ou, com criar=False,
    devolve um objeto com os padrões que não é gravado)."""
    consulta = select(ConfigEnvios)
    if travar:
        consulta = consulta.with_for_update()
    cfg = s.scalar(consulta)
    if cfg is not None:
        return cfg
    formulario_id = s.scalar(select(Formulario.id).where(Formulario.padrao_nps.is_(True)))
    valores = {**PADROES, "formulario_id": formulario_id}
    if not criar:
        return ConfigEnvios(**valores)
    s.execute(insert(ConfigEnvios).values(**valores).on_conflict_do_nothing())
    return s.scalar(consulta)


def _hora(t: time) -> str:
    return t.strftime("%H:%M")


def config_json(cfg: ConfigEnvios) -> dict:
    dados = {c: getattr(cfg, c) for c in CAMPOS}
    dados["janela_inicio"] = _hora(cfg.janela_inicio)
    dados["janela_fim"] = _hora(cfg.janela_fim)
    dados["dias_lembretes"] = list(cfg.dias_lembretes)
    return dados


def prazo_aguardando(cfg: ConfigEnvios) -> int:
    """Dias depois do convite em que ele ainda é esperado: maior prazo de lembrete + 7."""
    return max(cfg.dias_lembretes[: cfg.lembretes], default=0) + 7


def na_janela(cfg: ConfigEnvios, momento) -> bool:
    if cfg.so_dias_uteis and momento.weekday() >= 5:
        return False
    return cfg.janela_inicio <= momento.time() < cfg.janela_fim


# ---- pré-condições ----------------------------------------------------------

def assinatura_ok(conta: Conta) -> bool:
    if conta.situacao in ("cortesia", "ativa"):
        return True
    return conta.situacao == "teste" and conta.teste_ate is not None and conta.teste_ate > relogio.agora()


def provedor_ok() -> bool:
    cfg = config()
    return {
        "zeptomail": bool(cfg.ZEPTOMAIL_TOKEN),
        "resend": bool(cfg.RESEND_API_KEY),
        "memory": True,
        "console": cfg.AMBIENTE != "producao",
    }[cfg.EMAIL_PROVIDER]


def formulario_ok(s: Session, cfg: ConfigEnvios) -> bool:
    if cfg.formulario_id is None:
        return False
    f = s.get(Formulario, cfg.formulario_id)
    return f is not None and f.ativo and not f.arquivado


def _item(chave: str, ok: bool, mensagem: str, acao: tuple[str, str] | None = None) -> dict:
    return {"chave": chave, "ok": ok, "mensagem": None if ok else mensagem,
            "acao": {"rotulo": acao[0], "rota": acao[1]} if acao and not ok else None}


def pre_condicoes(s: Session, cfg: ConfigEnvios) -> dict:
    conta = s.scalar(select(Conta))
    itens = [
        _item("assinatura", assinatura_ok(conta),
              "O período de teste acabou. Assine um plano para voltar a enviar.", ("Assinatura", ROTA_ASSINATURA)),
        _item("provedor", provedor_ok(), "O envio de e-mails ainda não foi configurado na plataforma."),
        _item("formulario", formulario_ok(s, cfg), "Escolha o formulário usado nos convites.",
              ("Configurações de envio", ROTA_CONFIG)),
        _item("envios_ativos", cfg.envios_ativos, "Os envios estão desligados. Ligue em Configurações de envio.",
              ("Configurações de envio", ROTA_CONFIG)),
    ]
    return {"pronto": all(i["ok"] for i in itens), "itens": itens}


def erro_pre_condicao(mensagem: str) -> AppError:
    return AppError(409, "pre_condicao", mensagem)


def exigir(s: Session, cfg: ConfigEnvios, chaves: tuple[str, ...] | None = None) -> None:
    """409 `pre_condicao` com a mensagem do primeiro item que falta (entre `chaves`, se dadas)."""
    for item in pre_condicoes(s, cfg)["itens"]:
        if not item["ok"] and (chaves is None or item["chave"] in chaves):
            raise erro_pre_condicao(item["mensagem"])


def pronto(s: Session, cfg: ConfigEnvios) -> bool:
    return pre_condicoes(s, cfg)["pronto"]
