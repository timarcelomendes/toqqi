"""Tarefas periódicas: `python -m toqqi.tarefas
[assinaturas|robo|lembretes|pendentes|webhooks|ia|picos|resumo|tudo]` (padrão: tudo).

Também disponíveis em POST /api/v1/interno/tarefas (cabeçalho X-Tarefas-Token). Em produção, o Cron Job
`toqqi-tarefas` do Render roda este comando a cada 15 minutos; cada tarefa decide por conta se é hora de agir.
`tudo` roda na ordem: assinaturas, pendentes, robô, lembretes, webhooks, ia, picos, resumo (assinaturas primeiro,
para a liberação dos envios já valer; a IA antes dos picos, para eles já usarem as análises novas).

A tarefa `ia` analisa as respostas pendentes e, depois, no mesmo tempo da rodada, sugere os passos das ações
pendentes (etapa 5d): {analisadas, falharam, limite, passos: {prontas, falharam, limite}}.
"""
import json
import logging
import sys
import time as relogio_real

from toqqi.modulos.acoes import passos
from toqqi.modulos.assinatura import conferencia as assinaturas
from toqqi.modulos.envios import automacao
from toqqi.modulos.ia import servico as ia
from toqqi.modulos.integracoes import webhooks
from toqqi.modulos.relatorios import emails

TAREFAS = ("assinaturas", "robo", "lembretes", "pendentes", "webhooks", "ia", "picos", "resumo", "tudo")


def executar(qual: str = "tudo") -> dict:
    """Roda as tarefas pedidas (na ordem acima) e devolve o resumo de cada uma."""
    assert qual in TAREFAS
    resultado: dict = {}
    if qual in ("assinaturas", "tudo"):
        resultado["assinaturas"] = assinaturas.executar()
    if qual in ("pendentes", "tudo"):
        resultado["pendentes"] = automacao.pendentes()
    if qual in ("robo", "tudo"):
        resultado["robo"] = automacao.robo()
    if qual in ("lembretes", "tudo"):
        resultado["lembretes"] = automacao.lembretes()
    if qual in ("webhooks", "tudo"):
        resultado["webhooks"] = webhooks.entregar_devidas()
    if qual in ("ia", "tudo"):
        inicio = relogio_real.monotonic()
        resultado["ia"] = {**ia.executar(), "passos": passos.executar(inicio)}
    if qual in ("picos", "tudo"):
        resultado["picos"] = emails.picos()
    if qual in ("resumo", "tudo"):
        resultado["resumo"] = emails.resumo()
    return resultado


def main(argv: list[str]) -> int:
    qual = argv[0] if argv else "tudo"
    if qual not in TAREFAS or len(argv) > 1:
        print(f"Uso: python -m toqqi.tarefas [{'|'.join(TAREFAS)}]", file=sys.stderr)
        return 2
    try:
        resultado = executar(qual)
    except Exception:  # noqa: BLE001 - sai pelo log (erros do banco sem dados de clientes), não pelo traceback cru
        logging.getLogger("toqqi.tarefas").exception("Tarefa %s interrompida por um erro.", qual)
        return 1
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
