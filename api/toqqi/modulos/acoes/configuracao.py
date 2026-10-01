"""Prazos das ações automáticas por grupo e "criar ação também para promotores" (1 linha por conta)."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.modelos import ConfigAcoes

PADROES = {"prazo_detrator": 2, "prazo_neutro": 5, "prazo_promotor": 7, "acao_promotor": False}
CAMPOS = tuple(PADROES)


def obter(s: Session, criar: bool = True, travar: bool = False) -> ConfigAcoes:
    """Configuração da conta da transação. Sem registro: cria com os padrões (ou, com criar=False, devolve um
    objeto com os padrões que não é gravado)."""
    consulta = select(ConfigAcoes)
    if travar:
        consulta = consulta.with_for_update()
    cfg = s.scalar(consulta)
    if cfg is not None:
        return cfg
    if not criar:
        return ConfigAcoes(**PADROES)
    s.execute(insert(ConfigAcoes).values(**PADROES).on_conflict_do_nothing())
    return s.scalar(consulta)


def config_json(cfg: ConfigAcoes) -> dict:
    return {c: getattr(cfg, c) for c in CAMPOS}
