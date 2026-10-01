"""Tarefas periódicas: `python -m toqqi.tarefas [robo|lembretes|pendentes|webhooks|ia|picos|resumo|tudo]` (padrão:
tudo).

Também disponíveis em POST /api/v1/interno/tarefas (cabeçalho X-Tarefas-Token). Em produção, o Cron Job
`toqqi-tarefas` do Render roda este comando a cada 15 minutos; cada tarefa decide por conta se é hora de agir.
`tudo` roda na ordem: pendentes, robô, lembretes, webhooks, ia, picos, resumo (a IA antes, para os picos já usarem
as análises novas).
"""
import json
import logging
import sys

from toqqi.modulos.envios import automacao
from toqqi.modulos.ia import servico as ia
from toqqi.modulos.integracoes import webhooks
from toqqi.modulos.relatorios import emails

TAREFAS = ("robo", "lembretes", "pendentes", "webhooks", "ia", "picos", "resumo", "tudo")


def executar(qual: str = "tudo") -> dict:
    """Roda as tarefas pedidas (na ordem acima) e devolve o resumo de cada uma."""
    assert qual in TAREFAS
    resultado: dict = {}
    if qual in ("pendentes", "tudo"):
        resultado["pendentes"] = automacao.pendentes()
    if qual in ("robo", "tudo"):
        resultado["robo"] = automacao.robo()
    if qual in ("lembretes", "tudo"):
        resultado["lembretes"] = automacao.lembretes()
    if qual in ("webhooks", "tudo"):
        resultado["webhooks"] = webhooks.entregar_devidas()
    if qual in ("ia", "tudo"):
        resultado["ia"] = ia.executar()
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
