"""Modelo de mensagem (template) do WhatsApp automático: conferência ao conectar e montagem do envio.

Modelo esperado (o cliente cria no WhatsApp Manager, categoria Utilidade): corpo com {{1}} = primeiro nome,
{{2}} = nome da conta, {{3}} = referência ("seu pedido 1234" / "nosso atendimento"); botão de URL dinâmica
`{FRONTEND_URL}/r/{{1}}`, cujo sufixo é o token do convite.
"""
import re

from toqqi.core.config import config

VARIAVEIS = ("{{1}}", "{{2}}", "{{3}}")
REFERENCIA_PADRAO = "nosso atendimento"


class ModeloInvalido(ValueError):
    pass


def url_do_botao() -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/r/{{{{1}}}}"


def conferir(modelos: list[dict], nome: str, idioma: str) -> int:
    """Confere o modelo devolvido pela Meta e devolve a posição do botão de URL. Levanta ModeloInvalido."""
    modelo = next((m for m in modelos if m.get("name") == nome and m.get("language") == idioma), None)
    if modelo is None:
        raise ModeloInvalido(f"Não encontramos o modelo “{nome}” no idioma {idioma} nesta conta do WhatsApp.")
    if modelo.get("status") != "APPROVED":
        raise ModeloInvalido("O modelo ainda não foi aprovado pela Meta. Espere a aprovação e tente de novo.")
    if modelo.get("category") != "UTILITY":
        raise ModeloInvalido("O modelo precisa ser da categoria Utilidade.")
    componentes = [c for c in modelo.get("components") or [] if isinstance(c, dict)]
    corpo = next((c.get("text") or "" for c in componentes if c.get("type") == "BODY"), "")
    if sorted(set(re.findall(r"\{\{\d+\}\}", corpo))) != list(VARIAVEIS):
        raise ModeloInvalido("O texto do modelo precisa ter as variáveis {{1}}, {{2}} e {{3}} (e só elas).")
    botoes = next((c.get("buttons") or [] for c in componentes if c.get("type") == "BUTTONS"), [])
    for i, b in enumerate(botoes):
        if isinstance(b, dict) and b.get("type") == "URL" and b.get("url") == url_do_botao():
            return i
    raise ModeloInvalido(f"O modelo precisa de um botão de link com o endereço {url_do_botao()}.")


def referencia_texto(referencia: str | None) -> str:
    return f"seu pedido {referencia}" if referencia else REFERENCIA_PADRAO


def corpo_modelo(*, nome_modelo: str, idioma: str, botao: int, telefone: str, primeiro_nome: str, empresa: str,
                 referencia: str, token: str) -> dict:
    def texto(v: str) -> dict:
        return {"type": "text", "text": v}

    return {
        "messaging_product": "whatsapp", "recipient_type": "individual", "to": telefone, "type": "template",
        "template": {
            "name": nome_modelo, "language": {"code": idioma},
            "components": [
                {"type": "body", "parameters": [texto(primeiro_nome or "cliente"), texto(empresa), texto(referencia)]},
                {"type": "button", "sub_type": "url", "index": str(botao), "parameters": [texto(token)]},
            ],
        },
    }


def corpo_texto(telefone: str, mensagem: str) -> dict:
    """Mensagem de sessão (só dentro das 24 h depois de a pessoa escrever)."""
    return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": telefone, "type": "text",
            "text": {"body": mensagem}}
