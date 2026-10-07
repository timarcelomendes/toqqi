"""Tarefas periódicas: `python -m toqqi.tarefas
[assinaturas|robo|lembretes|pendentes|webhooks|ia|picos|resumo|erros|limpeza|tudo]` (padrão: tudo).

Também disponíveis em POST /api/v1/interno/tarefas (cabeçalho X-Tarefas-Token). Em produção, o Cron Job
`toqqi-tarefas` do Render roda este comando a cada 15 minutos; cada tarefa decide por conta se é hora de agir.
`tudo` roda na ordem: assinaturas, pendentes, robô, lembretes, webhooks, ia, picos, resumo, erros, limpeza
(assinaturas primeiro, para a liberação dos envios já valer; a IA antes dos picos, para eles já usarem as análises
novas; a limpeza por último, depois de tudo o que manda e-mails).

A tarefa `ia` analisa as respostas pendentes e, depois, no mesmo tempo da rodada, sugere os passos das ações
pendentes (etapa 5d): {analisadas, falharam, limite, passos: {prontas, falharam, limite}}.

A tarefa `limpeza` (etapa 5e) apaga o que passou do prazo de guarda: os e-mails enviados com mais de 90 dias, em
lotes ({emails_apagados}). Etapa 5f: também os registros de acesso com mais de 184 dias ({acessos_apagados},
`core.acessos`) e, a partir das 9h, uma vez por dia, a exclusão automática das contas encerradas ({encerradas}: o
resumo da rodada, ou null quando ela pulou; `assinatura.exclusao`, com o parâmetro `teste.exclusao_automatica`
(etapa 5g, Plataforma › Parâmetros; padrão: `EXCLUSAO_AUTOMATICA`) = ligada para agir; simular só conta). Etapa 5h:
também os erros com a última ocorrência há mais de 30 dias ({erros_apagados}, `core.erros`). Feedback: as imagens dos
feedbacks concluídos ou encerrados sem atividade há mais de 180 dias ({feedback_imagens_apagadas}).

Etapa 5h (aviso de erros):
- Cada tarefa roda no seu try/except: a exceção de uma vai para o log e para Plataforma › Erros (origem `tarefa`,
  local = o nome da tarefa, `core.erros`) e as outras seguem; no resumo, a que falhou fica {erro: "TipoDoErro"}. Pela
  linha de comando, a saída é 1 quando alguma falhou (o resumo sai mesmo assim).
- A tarefa `erros` manda aos superadmins o e-mail diário dos erros abertos nas últimas 24 h, a partir das 8h, uma vez por
  dia (`plataforma.erros.aviso_diario`): {erros, emails}, ou null quando pulou.

Pela linha de comando, o log da aplicação sai como na API (`core.logs.configurar`: INFO, "INFO:     toqqi - ...").
"""
import json
import logging
import sys
import time as relogio_real
from collections.abc import Callable

from toqqi.core import acessos, erros, logs
from toqqi.modulos.acoes import passos
from toqqi.modulos.assinatura import conferencia as assinaturas
from toqqi.modulos.assinatura import exclusao
from toqqi.modulos.auditoria import emails as emails_enviados
from toqqi.modulos.envios import automacao
from toqqi.modulos.feedback import servico as feedback
from toqqi.modulos.ia import servico as ia
from toqqi.modulos.conectores import servico as conectores
from toqqi.modulos.integracoes import webhooks
from toqqi.modulos.plataforma import erros as aviso_erros
from toqqi.modulos.relatorios import emails

TAREFAS = ("assinaturas", "robo", "lembretes", "pendentes", "webhooks", "conectores", "ia", "picos", "resumo", "erros", "limpeza",
           "tudo")

log = logging.getLogger("toqqi.tarefas")


def _ia() -> dict:
    inicio = relogio_real.monotonic()
    return {**ia.executar(), "passos": passos.executar(inicio)}


def limpeza() -> dict:
    """Tarefa `limpeza`: apaga o que passou do prazo de guarda (e-mails enviados com mais de 90 dias, registros de
    acesso com mais de 184, erros sem ocorrência há mais de 30, imagens dos feedbacks concluídos ou encerrados há mais
    de 180) e roda a exclusão automática das contas encerradas (uma vez por dia, a partir das 9h)."""
    return {"emails_apagados": emails_enviados.limpar(), "acessos_apagados": acessos.limpar(),
            "encerradas": exclusao.executar(), "erros_apagados": erros.limpar_antigos(),
            "feedback_imagens_apagadas": feedback.limpar_imagens_antigas()}


def _passos() -> list[tuple[str, Callable[[], object]]]:
    """As tarefas na ordem do `tudo` (os nomes de `TAREFAS`, menos `tudo`)."""
    return [
        ("assinaturas", lambda: assinaturas.executar()),
        ("pendentes", lambda: automacao.pendentes()),
        ("robo", lambda: automacao.robo()),
        ("lembretes", lambda: automacao.lembretes()),
        ("webhooks", lambda: webhooks.entregar_devidas()),
        ("conectores", lambda: conectores.devolver_notas()),  # a nota de volta ao CRM
        ("ia", _ia),
        ("picos", lambda: emails.picos()),
        ("resumo", lambda: emails.resumo()),
        ("erros", lambda: aviso_erros.aviso_diario()),
        ("limpeza", lambda: limpeza()),
    ]


def falhou(resultado: object) -> bool:
    """O resumo de uma tarefa que falhou ({erro: "TipoDoErro"})."""
    return isinstance(resultado, dict) and set(resultado) == {"erro"}


def executar(qual: str = "tudo") -> dict:
    """Roda as tarefas pedidas (na ordem acima) e devolve o resumo de cada uma. A exceção de uma tarefa vai para o
    log e para Plataforma › Erros, e as outras seguem (regras no cabeçalho)."""
    assert qual in TAREFAS
    resultado: dict = {}
    for nome, passo in _passos():
        if qual not in (nome, "tudo"):
            continue
        try:
            resultado[nome] = passo()
        except Exception as e:  # noqa: BLE001 - uma tarefa com erro não para as outras
            log.exception("Tarefa %s interrompida por um erro.", nome)
            erros.registrar_excecao(e, "tarefa", nome)
            resultado[nome] = {"erro": type(e).__name__}
    return resultado


def main(argv: list[str]) -> int:
    logs.configurar()  # sem ele, os INFO das tarefas (ex.: a exclusão automática) não apareceriam no terminal
    qual = argv[0] if argv else "tudo"
    if qual not in TAREFAS or len(argv) > 1:
        print(f"Uso: python -m toqqi.tarefas [{'|'.join(TAREFAS)}]", file=sys.stderr)
        return 2
    try:
        resultado = executar(qual)
    except Exception:  # noqa: BLE001 - sai pelo log (erros do banco sem dados de clientes), não pelo traceback cru
        log.exception("Tarefa %s interrompida por um erro.", qual)
        return 1
    print(json.dumps(resultado, ensure_ascii=False))
    return 1 if any(falhou(r) for r in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
