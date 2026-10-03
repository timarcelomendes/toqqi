"""Assistente (etapa 5b): perguntas sobre os resultados e sobre o uso do Toqqi, com IA e ferramentas.

Funciona com a IA disponível na plataforma (`ia.disponivel()`) e a conta liberada (`assinatura.regras.liberada`);
não depende do interruptor "Analisar comentários com IA". Todos os perfis usam; cada consulta respeita as
permissões de quem pergunta. Cada pergunta gasta da cota mensal do plano (`ia.cota`) as análises do nível de modelo
da conta (`ia_texto.analises_do_nivel`: 1, ou 2 no Mais detalhado); a que falha devolve as mesmas.

Ordem de `perguntar`: validação (esquema) → limite por minuto (8 por usuário: 429) → vagas, tentadas sem esperar
(2 perguntas em andamento por usuário: 429; 6 no processo: 503, porque cada pergunta segura uma thread da API por até
60 s) → IA disponível → conta liberada → reservar o custo do nível (transação curta, com commit antes da conversa;
sem saldo: 409 `cota_esgotada` ou, se restam menos análises que o custo, `cota_insuficiente`) → conversa
(`core.ia_conversa`, fora de transação; cada consulta abre a sua) → devolver as análises se falhou. As vagas voltam
sempre (finally); as perguntas recusadas por elas não gastam a cota.

Os tokens de todas as chamadas vão para `cota_tokens_*`, inclusive os de uma pergunta que falhou ou deu erro
inesperado (`erro.andamento`). Com a resposta pronta, a contabilidade não a derruba: se somar os tokens falhar, só
fica no log; se ler a cota falhar, vai a calculada a partir da reserva.

Nada da conversa é guardado (o histórico vem do navegador) e nada vai para a auditoria. O log leva só o status, o
tipo de falha, o número de consultas e os tokens: nunca a pergunta, a resposta ou os dados.

Etapa 5d: a conversa usa o nível de modelo da conta (`contas.ia_modelo`) e as instruções ganham a linha do estilo
(`contas.ia_estilo`), lidos na mesma transação da reserva. O nível é lido uma vez só por pergunta: a reserva gasta o
custo dele e a conversa usa o mesmo nível (trocar o nível no meio não cobra 1 e roda o Mais detalhado). O GET e a
resposta trazem `custo` (as análises de uma pergunta no nível da conta) ao lado da `cota`.
"""
import logging
import re
import unicodedata

from toqqi.core import ia, ia_conversa, ia_texto, relogio
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.log_seguro import descrever_erro
from toqqi.modelos import Conta
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.assistente import atalhos as atalhos_mod
from toqqi.modulos.assistente import ferramentas
from toqqi.modulos.assistente.esquemas import MensagemIn
from toqqi.modulos.assistente.instrucoes import instrucoes
from toqqi.modulos.assistente.limite import MAX_SIMULTANEAS, em_andamento, limite
from toqqi.modulos.ia import cota

log = logging.getLogger("toqqi.assistente")

MSG_PAUSADA = "O ToqqiAI volta quando a assinatura estiver em dia."
MSG_COTA = cota.MSG_ESGOTADA  # 409 cota_esgotada (o 409 cota_insuficiente vem de cota.mensagem_insuficiente)
MSG_LIMITE = "Muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo."
MSG_INDISPONIVEL = "O ToqqiAI está indisponível no momento. Tente de novo em instantes."
RECUSA = "Só consigo ajudar com a satisfação dos seus clientes e com o uso do Toqqi."
MAX_RESPOSTA = 2000
MAX_SUGESTAO = 80
MAX_SUGESTOES = 3

SUGESTOES_NUMEROS = ("Qual é o NPS dos últimos 30 dias?", "Quais clientes têm o NPS mais baixo nos últimos 90 dias?")
SUGESTAO_COMENTARIOS = "O que os detratores disseram este mês?"
SUGESTAO_AJUDA = "Como importo meus contatos?"

# formato da resposta (§5.4), JSON Schema estrito: os limites de quantidade valem depois da IA (abaixo)
ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["resposta", "sugestoes", "atalhos"],
    "properties": {
        "resposta": {"type": "string", "description": "a resposta, em texto simples"},
        "sugestoes": {"type": "array", "items": {"type": "string"},
                      "description": "3 próximas perguntas curtas, até 80 caracteres cada"},
        "atalhos": {"type": "array", "items": {"type": "string", "enum": list(atalhos_mod.CHAVES)},
                    "description": "até 2 chaves das telas citadas"},
    },
}

_ENDERECO = re.compile(r"(?i)\S*(?:https?://|www\.)\S*")
_TRECHO = re.compile(r"\S+")


# ---- texto depois da IA ------------------------------------------------------------------------

def _tem_endereco(trecho: str) -> bool:
    return _ENDERECO.search(unicodedata.normalize("NFKC", trecho)) is not None


def sem_enderecos(texto: str) -> str:
    """Sem caracteres de formato (Unicode Cf: largura zero, controles de direção…), sem `**` e sem os trechos inteiros
    (sequências sem espaço) que, normalizados com NFKC, têm `http://`, `https://` ou `www.`: saem "Acesse_https://…",
    "h<largura zero>ttps://…", "ＨＴＴＰＳ：／／…" e "1www.…"; "erro HTTP 500" fica. O `**` sai antes para não formar um
    endereço depois ("ww**w." → "www."). O NFKC serve só para achar o endereço: o resto do texto fica como veio (o
    NFKC trocaria "1º" por "1o" e "…" por "...")."""
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Cf").replace("**", "")
    return _TRECHO.sub(lambda achado: "" if _tem_endereco(achado.group()) else achado.group(), texto)


def limpar_resposta(texto: str) -> str:
    """Sem controles (menos quebra de linha), sem `**` e sem endereços (`sem_enderecos`); até 2.000 caracteres."""
    linhas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    texto = "\n".join(ia.sem_controle(linha) for linha in linhas)  # controles viram espaço (sai no ajuste abaixo)
    texto = sem_enderecos(texto)
    linhas = [" ".join(linha.split()) for linha in texto.split("\n")]
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    return ia.cortar(texto, MAX_RESPOSTA)


def limpar_sugestoes(sugestoes: list[str]) -> list[str]:
    """Sem vazias nem repetidas, numa linha, sem `**` e sem endereços (`sem_enderecos`), até 80 caracteres cada, no
    máximo 3."""
    itens: list[str] = []
    for s in sugestoes:
        s = " ".join(sem_enderecos(ia.sem_controle(s)).split())
        s = ia.cortar(s, MAX_SUGESTAO) if s else s
        if s and s not in itens:
            itens.append(s)
        if len(itens) == MAX_SUGESTOES:
            break
    return itens


# ---- rotas ---------------------------------------------------------------------------------------

def sugestoes_iniciais(permissoes) -> list[str]:
    itens: list[str] = []
    if "painel.ver" in permissoes or "relatorios.ver" in permissoes:
        itens += SUGESTOES_NUMEROS
    if "respostas.ver" in permissoes:
        itens.append(SUGESTAO_COMENTARIOS)
    itens.append(SUGESTAO_AJUDA)
    return itens[:MAX_SUGESTOES]


def estado(ctx: Contexto) -> dict:
    """GET /assistente: {disponivel, motivo, cota, custo, sugestoes}. `custo`: as análises que uma pergunta gasta no
    nível da conta (null sem IA na plataforma, como a cota); restam menos que ele → "cota_insuficiente"."""
    if not ia.disponivel():
        return {"disponivel": False, "motivo": "ia_indisponivel", "cota": None, "custo": None, "sugestoes": []}
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id)
        uso = cota.estado(s, conta)
        custo = ia_texto.analises_do_nivel(conta.ia_modelo)
        livre = liberada(conta)
    base = {"cota": uso, "custo": custo}
    if not livre:
        return {"disponivel": False, "motivo": "conta_pausada", **base, "sugestoes": []}
    sem_saldo = cota.motivo_sem_saldo(uso, custo)
    if sem_saldo:
        return {"disponivel": False, "motivo": sem_saldo, **base, "sugestoes": []}
    return {"disponivel": True, "motivo": None, **base, "sugestoes": sugestoes_iniciais(ctx.permissoes)}


def _indisponivel() -> AppError:
    return AppError(503, "ia_indisponivel", MSG_INDISPONIVEL)


def perguntar(ctx: Contexto, pergunta: str, historico: list[MensagemIn] | None) -> dict:
    """POST /assistente/perguntar: {resposta, sugestoes, atalhos, cota}."""
    if not limite.permitir(ctx.usuario_id):
        raise AppError(429, "limite_perguntas", MSG_LIMITE)
    recusada = em_andamento.entrar(ctx.usuario_id)  # sem esperar vaga
    if recusada == "usuario":
        raise AppError(429, "limite_perguntas", MSG_LIMITE)
    if recusada == "processo":
        log.warning("Assistente: as %d vagas do processo estão ocupadas; pergunta da conta %s recusada.",
                    MAX_SIMULTANEAS, ctx.conta_id)
        raise _indisponivel()
    try:
        return _responder(ctx, pergunta, historico)
    finally:
        em_andamento.sair(ctx.usuario_id)


def _responder(ctx: Contexto, pergunta: str, historico: list[MensagemIn] | None) -> dict:
    """`perguntar` depois dos limites e com a vaga ocupada."""
    if not ia.disponivel():
        raise _indisponivel()
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id)
        if not liberada(conta):
            raise AppError(409, "conta_pausada", MSG_PAUSADA)
        # o nível é lido uma vez só: a reserva gasta o custo dele e a conversa usa o mesmo nível
        nome_conta, nivel, estilo = conta.nome, conta.ia_modelo, conta.ia_estilo
        reserva = cota.reservar(s, conta, ia_texto.analises_do_nivel(nivel))
        if reserva is None:
            raise cota.erro_sem_saldo(s, conta, nivel)
    mensagens = [{"role": "user" if m.papel == "usuario" else "assistant", "content": m.texto}
                 for m in historico or []]
    resultado = None
    try:
        resultado = ia_conversa.conversar(
            instrucoes(nome_conta, relogio.hoje(), estilo), mensagens, pergunta, ferramentas.DEFINICOES, ESQUEMA,
            lambda nome, argumentos: ferramentas.executar(ctx, nome, argumentos), nivel)
        resposta = RECUSA if resultado.recusa else limpar_resposta(resultado.resposta)
        if not resposta:
            raise ia_conversa.Falha("transitoria", "resposta vazia", resultado)
        if resultado.recusa:
            sugestoes, atalhos = sugestoes_iniciais(ctx.permissoes), []
        else:
            sugestoes = limpar_sugestoes(resultado.sugestoes)
            atalhos = atalhos_mod.filtrar(resultado.atalhos, ctx.perfil, ctx.permissoes)
    except ia_conversa.Falha as falha:
        with em_conta(ctx.conta_id) as s:
            cota.devolver(reserva, s)
            cota.somar_tokens(reserva, falha.tokens_entrada, falha.tokens_saida, s)
        nivel_log = logging.ERROR if falha.tipo == "configuracao" else logging.WARNING
        log.log(nivel_log, "Assistente: falha %s (%s) na conta %s; análises devolvidas: %d (consultas=%d, "
                "chamadas=%d, tokens=%d/%d).%s", falha.tipo, falha.detalhe, ctx.conta_id, reserva.quantidade,
                falha.consultas, falha.chamadas, falha.tokens_entrada, falha.tokens_saida,
                " Confira OPENAI_API_KEY e IA_ASSISTENTE_MODELO." if falha.tipo == "configuracao" else "")
        raise _indisponivel() from None
    except Exception as erro:
        # os tokens das chamadas já feitas: os da conversa inteira, ou o andamento que `conversar` anexou ao erro
        andamento = resultado if resultado is not None else getattr(erro, "andamento", None)
        entrada, saida = (andamento.tokens_entrada, andamento.tokens_saida) if andamento is not None else (0, 0)
        with em_conta(ctx.conta_id) as s:
            cota.devolver(reserva, s)
            cota.somar_tokens(reserva, entrada, saida, s)
        log.error("Assistente: erro inesperado na conta %s; análises devolvidas: %d (tokens=%d/%d).", ctx.conta_id,
                  reserva.quantidade, entrada, saida)
        raise
    # a resposta está pronta: daqui em diante, nada a derruba
    _somar_tokens(ctx, reserva, resultado)
    uso = _cota_depois(ctx, reserva)
    log.info("Assistente: %s na conta %s (nível %s, análises=%d, consultas=%d, chamadas=%d, tokens=%d/%d).",
             "recusa" if resultado.recusa else "resposta", ctx.conta_id, ia_texto.nivel_valido(nivel),
             reserva.quantidade, resultado.consultas, resultado.chamadas, resultado.tokens_entrada,
             resultado.tokens_saida)
    # `custo`: o desta pergunta (o nível lido no começo), que é o da próxima enquanto ninguém trocar o nível
    return {"resposta": resposta, "sugestoes": sugestoes, "atalhos": atalhos, "cota": uso,
            "custo": reserva.quantidade}


def _somar_tokens(ctx: Contexto, reserva: cota.Reserva, resultado: ia_conversa.Resultado) -> None:
    """Soma os tokens da pergunta em `cota_tokens_*`; se o banco falhar, só registra (sem dados) e segue."""
    try:
        cota.somar_tokens(reserva, resultado.tokens_entrada, resultado.tokens_saida)
    except Exception as erro:  # noqa: BLE001 - a resposta já existe: não a perde por causa da contabilidade
        log.error("Assistente: não foi possível somar os tokens (%d/%d) na conta %s (%s).",
                  resultado.tokens_entrada, resultado.tokens_saida, ctx.conta_id, descrever_erro(erro))


def _cota_depois(ctx: Contexto, reserva: cota.Reserva) -> dict:
    """A cota depois da pergunta; se o banco falhar, a calculada a partir da reserva."""
    try:
        with em_conta(ctx.conta_id) as s:
            return cota.estado(s, s.get(Conta, ctx.conta_id))
    except Exception as erro:  # noqa: BLE001 - a resposta já existe: não a perde por causa da contabilidade
        log.error("Assistente: não foi possível ler a cota da conta %s (%s); vai a da reserva.", ctx.conta_id,
                  descrever_erro(erro))
        return cota.estado_da_reserva(reserva)
