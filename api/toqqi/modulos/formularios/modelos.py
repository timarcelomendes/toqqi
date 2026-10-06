"""Modelos prontos de formulário e tema padrão.

Módulo só de dados (sem banco): também é usado pela migração 0002 para semear as contas existentes.
Textos aceitam as variáveis {empresa} {nome} {assunto} {referencia}.

Etapa 5l: a lógica dos modelos já vem no formato novo (`logica.mostrar_se`, docs/api-etapa-5l.md §1.3) e alguns
modelos trazem finais. Nos modelos, cada pergunta tem um id local (ex.: "nota") que a lógica e os finais usam;
`documento_do_modelo` troca esses ids por ids novos (`p_` + 6) e leva junto as referências (fontes das condições,
destinos de `pular` e citações `{{id}}`). Os ids das regras e dos finais são gerados na normalização.
"""
import copy
import re
import secrets
import string

_ALFABETO_ID = string.ascii_lowercase + string.digits
_RE_CITACAO = re.compile(r"\{\{([A-Za-z0-9_-]{1,32})\}\}")

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


def gerar_id(prefixo: str = "p_") -> str:
    """`p_` (item), `r_` (regra de pular) ou `f_` (final) + 6 caracteres [a-z0-9]."""
    return prefixo + "".join(secrets.choice(_ALFABETO_ID) for _ in range(6))


def gerar_id_pergunta() -> str:
    return gerar_id("p_")


def _p(tipo: str, titulo: str, obrigatoria: bool = False, **extra) -> dict:
    return {"tipo": tipo, "titulo": titulo, "obrigatoria": obrigatoria, **extra}


def _se(fonte: str, op: str, valor) -> dict:
    """`logica` com um `mostrar_se` de uma condição só."""
    return {"mostrar_se": {"juncao": "todas", "condicoes": [{"fonte": fonte, "op": op, "valor": valor}]}}


def _grupos(fonte: str, *grupos: str) -> dict:
    return _se(fonte, "grupo_e", list(grupos))


def _final(nome: str, titulo: str, html: str, fonte: str, *grupos: str) -> dict:
    return {"nome": nome, "titulo": titulo, "html": html, "botao": None,
            "mostrar_se": _grupos(fonte, *grupos)["mostrar_se"]}


MODELOS: dict[str, dict] = {
    "nps_simples": {
        "nome": "NPS simples",
        "descricao": "A pergunta clássica de recomendação, de 0 a 10, com espaço para o cliente explicar a nota.",
        "perguntas": [
            _p("nps", "Em uma escala de 0 a 10, quanto você recomendaria a {empresa} a um colega ou parceiro "
                      "de negócios?", True, id="nota", rotulo_min="Nada provável", rotulo_max="Muito provável"),
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
            _p("csat", "Como foi a entrega do seu pedido {referencia}?", True, id="nota",
               rotulo_min="Muito ruim", rotulo_max="Excelente"),
            _p("escolha_multipla", "O que aconteceu na entrega?",
               opcoes=["Atrasou", "Produto avariado", "Produto errado ou faltando", "Atendimento do motorista",
                       "Nota fiscal ou boleto com erro", "Outro motivo"],
               logica=_grupos("nota", "insatisfeito", "neutro")),
            _p("comentario", "O que podemos melhorar?", logica=_grupos("nota", "insatisfeito", "neutro")),
            _p("comentario", "Quer deixar um elogio para a equipe de entrega?", logica=_grupos("nota", "satisfeito")),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Seu pedido chegou? Conte para a {empresa} como foi a entrega."},
    },
    "pos_atendimento": {
        "nome": "Pós-atendimento",
        "descricao": "Satisfação com um atendimento (troca, reclamação, cotação) e o esforço que o cliente teve.",
        "perguntas": [
            _p("csat", "Como você avalia {assunto}?", True, id="nota", rotulo_min="Muito ruim",
               rotulo_max="Excelente"),
            _p("escala", "A {empresa} facilitou a resolução da sua solicitação.", True, min=1, max=7,
               rotulo_min="Discordo totalmente", rotulo_max="Concordo totalmente"),
            _p("comentario", "O que poderia ter sido mais simples?", logica=_se("nota", "menor_igual", 3)),
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
               id="nota", rotulo_min="Nada provável", rotulo_max="Muito provável"),
            _p("escolha_multipla", "O que mais influenciou a sua nota?",
               opcoes=["Prazo de entrega", "Preço e condições de pagamento", "Disponibilidade de produtos",
                       "Atendimento do vendedor", "Qualidade dos produtos", "Trocas e pós-venda"]),
            _p("comentario", "O que a {empresa} precisa fazer para merecer nota 10?",
               logica=_se("nota", "menor_igual", 8)),
            _p("comentario", "Que bom! O que você mais valoriza em comprar com a gente?",
               logica=_grupos("nota", "promotor")),
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
    "nps_segmentos": {
        "nome": "NPS com acompanhamento e finais por segmento",
        "descricao": "NPS com uma pergunta de acompanhamento para cada segmento e um agradecimento diferente para "
                     "promotores e para detratores.",
        "perguntas": [
            _p("nps", "Em uma escala de 0 a 10, quanto você recomendaria a {empresa} a um colega ou parceiro "
                      "de negócios?", True, id="nota", rotulo_min="Nada provável", rotulo_max="Muito provável"),
            _p("comentario", "O que podemos melhorar?", logica=_grupos("nota", "detrator", "neutro")),
            _p("comentario", "O que você mais valoriza na {empresa}?", logica=_grupos("nota", "promotor")),
            _p("sim_nao", "Podemos entrar em contato para entender melhor?", logica=_grupos("nota", "detrator")),
        ],
        "finais": [
            _final("Promotores", "Obrigado por recomendar a {empresa}!",
                   "<p>Que bom saber que você recomenda a gente. A sua opinião ajuda a {empresa} a continuar "
                   "acertando.</p>", "nota", "promotor"),
            _final("Detratores", "Obrigado pela sinceridade",
                   "<p>Vamos usar o que você contou para melhorar.</p>", "nota", "detrator"),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Leva menos de um minuto e ajuda muito a {empresa}."},
    },
    "ces_atendimento": {
        "nome": "Esforço do cliente (CES)",
        "descricao": "Mede de 1 a 7 o esforço que o cliente teve para resolver a solicitação, pergunta o que poderia "
                     "ser mais simples quando a nota é baixa e fecha com a satisfação com o atendimento.",
        "perguntas": [
            _p("escala", "A {empresa} facilitou a resolução da sua solicitação?", True, id="esforco", min=1, max=7,
               rotulo_min="Discordo totalmente", rotulo_max="Concordo totalmente"),
            _p("comentario", "O que poderia ter sido mais simples?", logica=_se("esforco", "menor_igual", 3)),
            _p("csat", "Como você avalia {assunto}?", True, rotulo_min="Muito ruim", rotulo_max="Excelente"),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Conte para a {empresa} como foi resolver a sua solicitação."},
    },
    "csat_motivo": {
        "nome": "CSAT com motivo",
        "descricao": "Satisfação de 1 a 5 com o motivo da nota: opções diferentes para quem ficou insatisfeito e "
                     "para quem ficou satisfeito, e um espaço para comentar.",
        "perguntas": [
            _p("csat", "Como você avalia {assunto}?", True, id="nota", rotulo_min="Muito ruim",
               rotulo_max="Excelente"),
            _p("escolha_multipla", "O que mais pesou?",
               opcoes=["Demora", "Atendimento", "Produto ou serviço", "Preço", "Falta de informação",
                       "Outro motivo"],
               logica=_grupos("nota", "insatisfeito", "neutro")),
            _p("escolha_multipla", "O que mais pesou?",
               opcoes=["Rapidez", "Atendimento", "Produto ou serviço", "Preço justo", "Facilidade", "Outro motivo"],
               logica=_grupos("nota", "satisfeito")),
            _p("comentario", "Quer contar mais?"),
        ],
        "tema": {"titulo_abertura": "Olá, {nome}!",
                 "texto_abertura": "Leva menos de um minuto e ajuda muito a {empresa}."},
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


def _trocar_fontes(grupo: dict | None, mapa: dict[str, str]) -> None:
    for cond in (grupo or {}).get("condicoes", []):
        cond["fonte"] = mapa.get(cond.get("fonte"), cond.get("fonte"))


def _trocar_citacoes(texto, mapa: dict[str, str]):
    if not isinstance(texto, str) or "{{" not in texto:
        return texto
    return _RE_CITACAO.sub(lambda m: "{{" + mapa.get(m.group(1), m.group(1)) + "}}", texto)


def documento_do_modelo(chave: str) -> tuple[list[dict], list[dict]]:
    """Cópia das perguntas e dos finais do modelo, com ids novos nas perguntas (a lógica, os finais e as citações
    acompanham os ids novos)."""
    perguntas = copy.deepcopy(MODELOS[chave]["perguntas"])
    finais = copy.deepcopy(MODELOS[chave].get("finais", []))
    mapa: dict[str, str] = {}
    for p in perguntas:
        novo = gerar_id_pergunta()
        while novo in mapa.values():
            novo = gerar_id_pergunta()
        if p.get("id"):
            mapa[p["id"]] = novo
        p["id"] = novo
    for p in perguntas:
        logica = p.get("logica") or {}
        _trocar_fontes(logica.get("mostrar_se"), mapa)
        for regra in logica.get("pular", []):
            _trocar_fontes(regra.get("se"), mapa)
            regra["para"] = mapa.get(regra.get("para"), regra.get("para"))
        for campo in ("titulo", "descricao", "html"):
            if campo in p:
                p[campo] = _trocar_citacoes(p[campo], mapa)
    for f in finais:
        _trocar_fontes(f.get("mostrar_se"), mapa)
        for campo in ("titulo", "html"):
            f[campo] = _trocar_citacoes(f.get(campo), mapa)
    return perguntas, finais


def perguntas_do_modelo(chave: str) -> list[dict]:
    """Cópia das perguntas do modelo, já com ids novos."""
    return documento_do_modelo(chave)[0]


def tema_do_modelo(chave: str) -> dict:
    return {**TEMA_PADRAO, **copy.deepcopy(MODELOS[chave]["tema"])}
