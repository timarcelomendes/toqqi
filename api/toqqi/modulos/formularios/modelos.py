"""Modelos prontos de formulário e tema padrão.

Módulo só de dados (sem banco): também é usado pela migração 0002 para semear as contas existentes.
Textos aceitam as variáveis {empresa} {nome} {assunto} {referencia}.
"""
import copy
import secrets
import string

_ALFABETO_ID = string.ascii_lowercase + string.digits

TEMA_PADRAO = {
    "cor": "#1f6feb",
    "logo_url": None,
    "modo": "uma_por_vez",
    "titulo_abertura": None,
    "texto_abertura": None,
    "texto_botao": "Enviar",
    "titulo_final": "Obrigado!",
    "texto_final": "Sua resposta foi registrada. Ela ajuda a {empresa} a melhorar a cada dia.",
}


def gerar_id_pergunta() -> str:
    return "p_" + "".join(secrets.choice(_ALFABETO_ID) for _ in range(6))


def _p(tipo: str, titulo: str, obrigatoria: bool = False, **extra) -> dict:
    return {"tipo": tipo, "titulo": titulo, "obrigatoria": obrigatoria, **extra}


MODELOS: dict[str, dict] = {
    "nps_simples": {
        "nome": "NPS simples",
        "descricao": "A pergunta clássica de recomendação, de 0 a 10, com espaço para o cliente explicar a nota.",
        "perguntas": [
            _p("nps", "Em uma escala de 0 a 10, quanto você recomendaria a {empresa} a um colega ou parceiro "
                      "de negócios?", True, rotulo_min="Nada provável", rotulo_max="Muito provável"),
            _p("comentario", "O que mais pesou na sua nota?"),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Leva menos de um minuto e ajuda muito a {empresa}."},
    },
    "pos_entrega": {
        "nome": "Satisfação pós-entrega",
        "descricao": "Para enviar logo depois da entrega: avalia a entrega do pedido e pergunta o que deu errado "
                     "quando o cliente não ficou satisfeito.",
        "perguntas": [
            _p("csat", "Como foi a entrega do seu pedido {referencia}?", True,
               rotulo_min="Muito ruim", rotulo_max="Excelente"),
            _p("escolha_multipla", "O que aconteceu na entrega?",
               opcoes=["Atrasou", "Produto avariado", "Produto errado ou faltando", "Atendimento do motorista",
                       "Nota fiscal ou boleto com erro", "Outro motivo"],
               condicao={"tipo": "grupo", "grupos": ["insatisfeito", "neutro"]}),
            _p("comentario", "O que podemos melhorar?",
               condicao={"tipo": "grupo", "grupos": ["insatisfeito", "neutro"]}),
            _p("comentario", "Quer deixar um elogio para a equipe de entrega?",
               condicao={"tipo": "grupo", "grupos": ["satisfeito"]}),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Seu pedido chegou? Conte para a {empresa} como foi a entrega."},
    },
    "pos_atendimento": {
        "nome": "Pós-atendimento",
        "descricao": "Satisfação com um atendimento (troca, reclamação, cotação) e o esforço que o cliente teve.",
        "perguntas": [
            _p("csat", "Como você avalia {assunto}?", True, rotulo_min="Muito ruim", rotulo_max="Excelente"),
            _p("escala", "A {empresa} facilitou a resolução da sua solicitação.", True, min=1, max=7,
               rotulo_min="Discordo totalmente", rotulo_max="Concordo totalmente"),
            _p("comentario", "O que poderia ter sido mais simples?",
               condicao={"tipo": "nota", "operador": "<=", "valor": 3}),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Queremos saber como foi o seu último contato com a {empresa}."},
    },
    "nps_distribuidora": {
        "nome": "NPS distribuidora",
        "descricao": "NPS com os motivos que mais pesam para quem compra de uma distribuidora: prazo, preço, "
                     "mix de produtos e atendimento.",
        "perguntas": [
            _p("nps", "Em uma escala de 0 a 10, quanto você recomendaria a {empresa} como fornecedora?", True,
               rotulo_min="Nada provável", rotulo_max="Muito provável"),
            _p("escolha_multipla", "O que mais influenciou a sua nota?",
               opcoes=["Prazo de entrega", "Preço e condições de pagamento", "Disponibilidade de produtos",
                       "Atendimento do vendedor", "Qualidade dos produtos", "Trocas e pós-venda"]),
            _p("comentario", "O que a {empresa} precisa fazer para merecer nota 10?",
               condicao={"tipo": "nota", "operador": "<=", "valor": 8}),
            _p("comentario", "Que bom! O que você mais valoriza em comprar com a gente?",
               condicao={"tipo": "grupo", "grupos": ["promotor"]}),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Sua opinião ajuda a {empresa} a atender melhor o seu negócio."},
    },
    "pesquisa_rapida": {
        "nome": "Pesquisa rápida",
        "descricao": "NPS com nome e e-mail opcionais. Boa para QR Code no balcão, no caminhão ou na nota fiscal.",
        "perguntas": [
            _p("nps", "De 0 a 10, quanto você recomendaria a {empresa}?", True,
               rotulo_min="Nada provável", rotulo_max="Muito provável"),
            _p("comentario", "Quer contar o motivo da sua nota?"),
            _p("texto_curto", "Seu nome", formato="texto"),
            _p("texto_curto", "Seu e-mail", formato="email",
               descricao="Opcional. Só usamos para responder você, se for preciso."),
        ],
        "tema": {},
    },
    "em_branco": {
        "nome": "Em branco",
        "descricao": "Comece do zero e monte as suas perguntas.",
        "perguntas": [],
        "tema": {},
    },
}

# Formulários que toda conta nova recebe: (nome, modelo, padrão).
FORMULARIOS_INICIAIS = [
    ("Pesquisa NPS", "nps_simples", "nps"),
    ("Satisfação pós-entrega", "pos_entrega", "csat"),
]

PERFIS_INICIAIS = ["Decisor", "Influenciador"]


def perguntas_do_modelo(chave: str) -> list[dict]:
    """Cópia das perguntas do modelo, já com ids novos."""
    perguntas = copy.deepcopy(MODELOS[chave]["perguntas"])
    for p in perguntas:
        p["id"] = gerar_id_pergunta()
    return perguntas


def tema_do_modelo(chave: str) -> dict:
    return {**TEMA_PADRAO, **copy.deepcopy(MODELOS[chave]["tema"])}
