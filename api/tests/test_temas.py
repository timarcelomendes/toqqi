"""Etapa 4a: temas do comentário por palavras-chave (funções puras) e GET /respostas/temas."""
import pytest
from util import API, conta_pronta, membro

from toqqi.modulos.respostas.registro import comentario_do_cliente, escolhas_do_cliente, temas_da_resposta
from toqqi.modulos.respostas.temas import CHAVES, detectar, normalizar, ordenar


@pytest.mark.parametrize("texto,esperado", [
    ("Meu pedido chegou atrasado", ["prazo_entrega"]),  # "pedido" sozinho não é sistema_pedidos
    ("A entrega demorou demais", ["prazo_entrega"]),
    ("Frete caro e a transportadora sumiu", ["prazo_entrega", "preco_condicoes"]),
    ("O produto veio QUEBRADO e a embalagem amassada", ["produto_avarias"]),
    ("Veio produto errado, faltando itens; pedi a troca", ["produto_avarias"]),
    ("Atendimento ótimo, vendedor muito atencioso", ["atendimento"]),
    ("Ótimo pós-venda", ["atendimento"]),
    ("Preço alto e o boleto veio com juros", ["preco_condicoes"]),
    ("Faltou informação: ninguém deu retorno", ["comunicacao"]),
    ("Mandem o boleto por e-mail", ["preco_condicoes", "comunicacao"]),
    ("Mandem por E-MAIL ou WhatsApp", ["comunicacao"]),
    ("Não consigo fazer pedido pelo site", ["sistema_pedidos"]),
    ("Pedido errado de novo", ["sistema_pedidos"]),
    ("Erro no pedido e na nota fiscal", ["sistema_pedidos"]),
    ("A NF-e não chegou", ["prazo_entrega", "sistema_pedidos"]),
    ("Esqueci a senha do portal", ["sistema_pedidos"]),
    ("Tudo certo, recomendo", []),
    ("", []),
    (None, []),
    ("Foi uma reentrega", []),  # início de palavra: "reentrega" não é "entreg"
    ("O motorista foi grosseiro e a caixa veio danificada; o preço é bom",
     ["prazo_entrega", "produto_avarias", "atendimento", "preco_condicoes"]),
])
def test_detectar(texto, esperado):
    assert detectar(texto) == esperado


def test_normalizar():
    assert normalizar("Pós-Venda:  ÓTIMO!\nNão") == "pos venda otimo nao"
    assert normalizar("Ação/Preço") == "acao preco"


def test_ordem_da_tabela_e_sem_repetir():
    assert ordenar(["sistema_pedidos", "prazo_entrega", "x", "prazo_entrega"]) == ["prazo_entrega", "sistema_pedidos"]
    assert CHAVES == ("prazo_entrega", "produto_avarias", "atendimento", "preco_condicoes", "comunicacao",
                      "sistema_pedidos")


def test_texto_analisado_e_comentario_mais_o_que_faltou():
    assert temas_da_resposta("Tudo certo", "faltou desconto") == ["preco_condicoes"]
    assert temas_da_resposta("", "o site caiu") == ["sistema_pedidos"]


def test_comentario_do_cliente_vem_das_respostas():
    """Só as perguntas de comentário (lidas das respostas, não do resumo "Pergunta: resposta | ..."); nome, e-mail,
    sim/não e nota não são comentário. As opções marcadas entram nos temas."""
    perguntas = [
        {"id": "n", "tipo": "nps", "titulo": "Nota"},
        {"id": "m", "tipo": "escolha_multipla", "titulo": "O que aconteceu na entrega?",
         "opcoes": ["Atrasou", "Produto avariado"]},
        {"id": "c", "tipo": "comentario", "titulo": "Fale da equipe"},
        {"id": "t", "tipo": "texto_curto", "titulo": "Seu nome", "formato": "texto"},
        {"id": "e", "tipo": "texto_curto", "titulo": "Seu e-mail", "formato": "email"},
        {"id": "s", "tipo": "sim_nao", "titulo": "Voltaria?"},
        {"id": "c2", "tipo": "comentario", "titulo": "Algo mais?"},
    ]
    respostas = {"n": 3, "m": ["Atrasou", "Produto avariado"], "c": "Muito | ruim", "t": "Sac Silva",
                 "e": "contato@cliente.com.br", "s": True, "c2": "  obrigado  "}
    # o " | " escrito pelo cliente não atrapalha (o texto não sai do resumo)
    assert comentario_do_cliente(perguntas, respostas) == "Muito | ruim · obrigado"
    assert escolhas_do_cliente(perguntas, respostas) == ["Atrasou, Produto avariado"]
    cliente = comentario_do_cliente(perguntas, respostas)
    # "contato@..." (comunicação) e "Sac Silva" (atendimento) não contam; as opções marcadas, sim
    assert temas_da_resposta(cliente, None, perguntas, respostas) == ["prazo_entrega", "produto_avarias"]
    assert temas_da_resposta("Muito | ruim · obrigado") == []  # sem as opções, nada
    assert comentario_do_cliente(perguntas, {"n": 9, "e": "contato@x.com.br", "t": "Joao"}) == ""
    assert comentario_do_cliente(None, respostas) == "" and escolhas_do_cliente(perguntas, None) == []


def test_rota_lista_temas(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    consulta = membro(client, a["h"], "caio@alfa.com.br", "consulta")
    r = client.get(f"{API}/respostas/temas", headers=consulta["h"])
    assert r.status_code == 200
    assert r.json() == [
        {"chave": "prazo_entrega", "rotulo": "Prazo e entrega"},
        {"chave": "produto_avarias", "rotulo": "Produto e avarias"},
        {"chave": "atendimento", "rotulo": "Atendimento"},
        {"chave": "preco_condicoes", "rotulo": "Preço e condições"},
        {"chave": "comunicacao", "rotulo": "Comunicação"},
        {"chave": "sistema_pedidos", "rotulo": "Sistema e pedidos"},
    ]
    assert client.get(f"{API}/respostas/temas").status_code == 401
