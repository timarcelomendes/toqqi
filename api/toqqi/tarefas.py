"""Tarefas periódicas: `python -m toqqi.tarefas [robo|lembretes|pendentes|webhooks|tudo]` (padrão: tudo).

Também disponíveis em POST /api/v1/interno/tarefas (cabeçalho X-Tarefas-Token). Em produção, o Cron Job
`toqqi-tarefas` do Render roda este comando a cada 15 minutos; cada tarefa decide por conta se é hora de agir.
"""
import json
import sys

from toqqi.modulos.envios import automacao
from toqqi.modulos.integracoes import webhooks

TAREFAS = ("robo", "lembretes", "pendentes", "webhooks", "tudo")


def executar(qual: str = "tudo") -> dict:
    """Roda as tarefas pedidas (pendentes primeiro) e devolve o resumo de cada uma."""
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
    return resultado


def main(argv: list[str]) -> int:
    qual = argv[0] if argv else "tudo"
    if qual not in TAREFAS or len(argv) > 1:
        print(f"Uso: python -m toqqi.tarefas [{'|'.join(TAREFAS)}]", file=sys.stderr)
        return 2
    print(json.dumps(executar(qual), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
