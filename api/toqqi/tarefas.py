"""Tarefas periódicas: `python -m toqqi.tarefas
[assinaturas|robo|lembretes|pendentes|webhooks|ia|picos|resumo|limpeza|tudo]` (padrão: tudo).

Também disponíveis em POST /api/v1/interno/tarefas (cabeçalho X-Tarefas-Token). Em produção, o Cron Job
`toqqi-tarefas` do Render roda este comando a cada 15 minutos; cada tarefa decide por conta se é hora de agir.
`tudo` roda na ordem: assinaturas, pendentes, robô, lembretes, webhooks, ia, picos, resumo, limpeza (assinaturas
primeiro, para a liberação dos envios já valer; a IA antes dos picos, para eles já usarem as análises novas; a limpeza
por último, depois de tudo o que manda e-mails).

A tarefa `ia` analisa as respostas pendentes e, depois, no mesmo tempo da rodada, sugere os passos das ações
pendentes (etapa 5d): {analisadas, falharam, limite, passos: {prontas, falharam, limite}}.

A tarefa `limpeza` (etapa 5e) apaga o que passou do prazo de guarda: os e-mails enviados com mais de 90 dias, em
lotes ({emails_apagados}). Etapa 5f: também os registros de acesso com mais de 184 dias ({acessos_apagados},
`core.acessos`) e, a partir das 9h, uma vez por dia, a exclusão automática das contas encerradas ({encerradas}: o
resumo da rodada, ou null quando ela pulou; `assinatura.exclusao`, com `EXCLUSAO_AUTOMATICA` = ligada para agir,
qualquer outro valor só simula).

Pela linha de comando, o log da aplicação sai como na API (`core.logs.configurar`: INFO, "INFO:     toqqi - ...").
"""
import json
import logging
import sys
import time as relogio_real

from toqqi.core import acessos, logs
from toqqi.modulos.acoes import passos
from toqqi.modulos.assinatura import conferencia as assinaturas
from toqqi.modulos.assinatura import exclusao
from toqqi.modulos.auditoria import emails as emails_enviados
from toqqi.modulos.envios import automacao
from toqqi.modulos.ia import servico as ia
from toqqi.modulos.integracoes import webhooks
from toqqi.modulos.relatorios import emails

TAREFAS = ("assinaturas", "robo", "lembretes", "pendentes", "webhooks", "ia", "picos", "resumo", "limpeza", "tudo")


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
    if qual in ("limpeza", "tudo"):
        resultado["limpeza"] = limpeza()
    return resultado


def limpeza() -> dict:
    """Tarefa `limpeza`: apaga o que passou do prazo de guarda (e-mails enviados com mais de 90 dias, registros de
    acesso com mais de 184) e roda a exclusão automática das contas encerradas (uma vez por dia, a partir das 9h)."""
    return {"emails_apagados": emails_enviados.limpar(), "acessos_apagados": acessos.limpar(),
            "encerradas": exclusao.executar()}


def main(argv: list[str]) -> int:
    logs.configurar()  # sem ele, os INFO das tarefas (ex.: a exclusão automática) não apareceriam no terminal
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
