"""Saída do log da aplicação: o logger `toqqi` (e os filhos, como `toqqi.exclusao`) num `StreamHandler` próprio, em
INFO e sem propagar para a raiz (as mensagens da aplicação, inclusive INFO, aparecem no log do Render). Usado na subida
da API (`main.py`) e na linha de comando das tarefas (`python -m toqqi.tarefas`), que sem ele só mostraria os avisos
(WARNING) — o padrão do `logging`. A limpeza dos erros do banco é outra coisa: `log_seguro`."""
import logging

FORMATO = "%(levelname)s:     toqqi - %(message)s"
NOME = "toqqi"  # nome do handler


def configurar() -> None:
    """Liga a saída uma vez por processo: com o `toqqi` já tendo handler (desta função ou de quem configurou antes),
    não mexe — chamar de novo não duplica as linhas."""
    log = logging.getLogger("toqqi")
    if log.handlers:
        return
    h = logging.StreamHandler()
    h.set_name(NOME)
    h.setFormatter(logging.Formatter(FORMATO))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False
