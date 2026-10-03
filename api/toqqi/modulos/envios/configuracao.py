"""Configurações de envio da conta e pré-condições de qualquer envio.

Visual dos e-mails de pesquisa (etapa 5e): `email_cor` (#RRGGBB em maiúsculas; nula = a cor do formulário do
envio), `email_mostrar_logo`, `email_imagem_topo_id` (uma imagem do banco de imagens da conta), `email_assinatura` e
`email_rodape` (texto puro). No JSON, a imagem de topo sai como `email_imagem_topo: {id, url, largura, altura} | null`.
`visual` resolve tudo isso para um envio (cor de destaque, logo, imagem), lido na hora de montar cada e-mail.
"""
from datetime import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.errors import AppError
from toqqi.modelos import ConfigEnvios, Conta, Formulario, Imagem
from toqqi.modulos.assinatura.regras import liberada, mensagem_pausa
from toqqi.modulos.envios import mensagens
from toqqi.modulos.imagens.servico import logo_para_cliente, url_publica

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
    # etapa 5e: visual dos e-mails de pesquisa
    "email_cor": None,
    "email_mostrar_logo": True,
    "email_imagem_topo_id": None,
    "email_assinatura": None,
    "email_rodape": None,
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


def imagem_topo(s: Session, cfg: ConfigEnvios) -> Imagem | None:
    """A imagem de topo dos e-mails (do banco de imagens da conta), se houver."""
    if cfg.email_imagem_topo_id is None:
        return None
    return s.scalar(select(Imagem).where(Imagem.id == cfg.email_imagem_topo_id, Imagem.conta_id == cfg.conta_id,
                                         Imagem.uso == "banco"))


def config_json(cfg: ConfigEnvios, topo: Imagem | None = None) -> dict:
    """A configuração para a tela; `topo` = `imagem_topo(s, cfg)`."""
    dados = {c: getattr(cfg, c) for c in CAMPOS if c != "email_imagem_topo_id"}
    dados["janela_inicio"] = _hora(cfg.janela_inicio)
    dados["janela_fim"] = _hora(cfg.janela_fim)
    dados["dias_lembretes"] = list(cfg.dias_lembretes)
    dados["email_imagem_topo"] = None if topo is None else {
        "id": topo.id, "url": url_publica(topo.chave), "largura": topo.largura, "altura": topo.altura}
    return dados


def visual(s: Session, cfg: ConfigEnvios, conta_id: int, tema: dict | None) -> mensagens.Visual:
    """O visual de um e-mail de pesquisa da conta; `tema` = o do formulário do envio (cor e logo)."""
    tema = tema or {}
    topo = imagem_topo(s, cfg)
    return mensagens.Visual(
        cor=mensagens.cor_de_destaque(cfg.email_cor, tema.get("cor")),
        logo_url=logo_para_cliente(s, conta_id, tema.get("logo_url")) if cfg.email_mostrar_logo else None,
        imagem_topo=mensagens.ImagemTopo(url_publica(topo.chave), topo.largura, topo.altura) if topo else None,
        assinatura=cfg.email_assinatura, rodape=cfg.email_rodape)


def prazo_aguardando(cfg: ConfigEnvios) -> int:
    """Dias depois do convite em que ele ainda é esperado: maior prazo de lembrete + 7."""
    return max(cfg.dias_lembretes[: cfg.lembretes], default=0) + 7


def na_janela(cfg: ConfigEnvios, momento) -> bool:
    if cfg.so_dias_uteis and momento.weekday() >= 5:
        return False
    return cfg.janela_inicio <= momento.time() < cfg.janela_fim


# ---- pré-condições ----------------------------------------------------------
# A da assinatura é a regra de "liberada" (assinatura.regras.liberada), a mesma do robô, dos lembretes, do CSAT,
# da IA e dos e-mails do painel.

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
        _item("assinatura", liberada(conta), mensagem_pausa(conta), ("Assinatura", ROTA_ASSINATURA)),
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
