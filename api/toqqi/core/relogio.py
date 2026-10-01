"""Relógio das regras de envio, no fuso de São Paulo.

Use sempre `relogio.agora()` / `relogio.hoje()` (acesso pelo módulo): os testes trocam `agora`.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_NOME = "America/Sao_Paulo"
FUSO = ZoneInfo(FUSO_NOME)


def agora() -> datetime:
    return datetime.now(FUSO)


def hoje() -> date:
    return agora().date()
