"""Avisos do Plano Grátis à equipe Toqqi (docs/api-plano-gratis.md), por e-mail a cada superadmin confirmado
(`SUPERADMIN_EMAILS`), como os do feedback: não entram no registro de e-mails da conta e nunca levantam.

- `contas_pausadas`: contas Grátis que a nota de risco acabou de pausar (tarefa `riscos`), para liberar ou excluir em
  Plataforma › Contas › Suspeitas;
- `denuncia`: alguém denunciou uma pesquisa de conta Grátis ("Denunciar esta pesquisa"), para conferir em
  Plataforma › Feedback › Denúncias.
"""
import logging

from toqqi.core import email
from toqqi.core.config import config
from toqqi.core.db import modo_sistema

log = logging.getLogger("toqqi.plataforma")

SINAIS = {
    "formulario_sensivel": "formulário pedindo dado sensível", "denuncias": "denúncias",
    "email_temporario": "e-mail temporário", "descadastros": "muita gente saindo da lista",
    "invalidos": "endereços que não existem", "documento_repetido": "CPF ou CNPJ de outra conta",
    "estorno": "pagamento estornado", "telefone_repetido": "telefone de outra conta",
    "sem_respostas": "quase ninguém respondendo", "email_nao_confirmado": "e-mail não confirmado",
    "nome_de_teste": "nome de teste", "nome_repetido": "nome de outra conta", "email_pessoal": "e-mail pessoal",
    "dominio_repetido": "domínio de outra conta", "volume_inicio": "muito envio no começo",
}
MOTIVOS = {"dados_pessoais": "Pede senha, cartão ou dados bancários", "golpe": "Finge ser outra empresa",
           "spam": "Não pedi para receber", "ofensa": "Conteúdo ofensivo", "outro": "Outro motivo"}
RODAPE = "Você recebe este aviso por fazer parte da equipe Toqqi (SUPERADMIN_EMAILS)."


def _url(caminho: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}{caminho}"


def _equipe() -> list[str]:
    from toqqi.modulos.plataforma.erros import superadmins_confirmados  # evita import circular na carga

    with modo_sistema() as s:
        return superadmins_confirmados(s)


def _enviar(assunto: str, paragrafos: list[str], botao: tuple[str, str], caminho: str) -> int:
    para = _equipe()
    if not para:
        log.warning("Plano Grátis: nenhum superadmin com o e-mail confirmado para avisar (%s).", assunto)
        return 0
    rodape = (RODAPE, "Plataforma", _url(caminho))
    for destino in para:
        email.enviar(destino, assunto, paragrafos, botao, rodape)
    return len(para)


def contas_pausadas(contas: list[dict]) -> int:
    """[{id, nome, pontos, sinais}] das contas Grátis pausadas nesta rodada. Devolve quantos e-mails saíram."""
    try:
        n = len(contas)
        assunto = ("Conta Grátis pausada pela nota de risco" if n == 1
                   else f"{n} contas Grátis pausadas pela nota de risco")
        linhas = [f"{c['nome']}: nota {c['pontos']} ({', '.join(SINAIS.get(x, x) for x in c['sinais'])})."
                  for c in contas]
        paragrafos = ["Os envios destas contas do plano Grátis foram pausados pela nota de risco:", *linhas,
                      "Confira em Plataforma › Contas › Suspeitas e libere os envios ou exclua a conta."]
        return _enviar(assunto, paragrafos, ("Abrir as suspeitas", _url("/plataforma/contas?suspeitas=1")),
                       "/plataforma/contas")
    except Exception:  # noqa: BLE001 - o aviso nunca derruba a tarefa
        log.exception("Plano Grátis: falha ao avisar a equipe das contas pausadas.")
        return 0


def denuncia(conta_nome: str, formulario_nome: str | None, motivo: str, detalhe: str | None) -> int:
    """Uma denúncia nova. Devolve quantos e-mails saíram."""
    try:
        paragrafos = [f"Alguém denunciou uma pesquisa da conta {conta_nome} (plano Grátis)"
                      + (f", no formulário “{formulario_nome}”." if formulario_nome else "."),
                      f"Motivo: {MOTIVOS.get(motivo, motivo)}."]
        if detalhe:
            paragrafos.append(f"Detalhe: {detalhe}")
        paragrafos.append("Confira em Plataforma › Feedback › Denúncias. Se a conta passar de 60 pontos de risco, os "
                          "envios dela param até a equipe liberar.")
        return _enviar("Denúncia de pesquisa no plano Grátis", paragrafos,
                       ("Abrir as denúncias", _url("/plataforma/feedback?denuncias=1")), "/plataforma/feedback")
    except Exception:  # noqa: BLE001 - o aviso nunca derruba a denúncia
        log.exception("Plano Grátis: falha ao avisar a equipe da denúncia.")
        return 0
