"""Configurações › Crescimento (1 linha por conta, como `config_acoes`; sem linha valem os padrões).

Variáveis dos textos:
- convite de indicação (título, texto e recompensa): {empresa} (nome da conta) e {nome} (primeiro nome de quem
  respondeu), trocadas pela API na tela final da pesquisa (`convite_de_indicacao`);
- oferta: {nome} (primeiro nome do contato), {empresa} (nome da conta), {empresa_cliente} (empresa do contato) e
  {representante} (primeiro nome de quem está logado), trocadas pela tela ao montar o link do WhatsApp.
Variável vazia some como nos outros textos (`respostas.registro.renderizar`).
"""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.modelos import ConfigCrescimento

PADROES = {
    "indicacoes_ativas": False,
    "titulo_convite": "Que bom que você gostou!",
    "texto_convite": "Conhece outra empresa que ganharia com a {empresa}? Indique e a gente entra em contato com "
                     "cuidado.",
    "recompensa": None,
    "texto_oferta": "Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma "
                    "condição especial para a {empresa_cliente}. Posso te contar?",
}
CAMPOS = tuple(PADROES)
EXEMPLO_RECOMPENSA = "Se a indicação virar cliente, você ganha 10% no próximo pedido."
VARIAVEIS_CONVITE = ("empresa", "nome")
VARIAVEIS_OFERTA = ("nome", "empresa", "empresa_cliente", "representante")


def obter(s: Session, criar: bool = True, travar: bool = False) -> ConfigCrescimento:
    """Configuração da conta da transação. Sem registro: cria com os padrões (ou, com criar=False, devolve um
    objeto com os padrões que não é gravado)."""
    consulta = select(ConfigCrescimento)
    if travar:
        consulta = consulta.with_for_update()
    cfg = s.scalar(consulta)
    if cfg is not None:
        return cfg
    if not criar:
        return ConfigCrescimento(**PADROES)
    s.execute(insert(ConfigCrescimento).values(**PADROES).on_conflict_do_nothing())
    return s.scalar(consulta)


def config_json(cfg: ConfigCrescimento) -> dict:
    return {c: getattr(cfg, c) for c in CAMPOS}


def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return config_json(obter(s, criar=False))


def salvar(ctx: Contexto, dados) -> dict:
    """Corpo parcial: só os campos enviados mudam (null nos obrigatórios não muda; recompensa vazia ou null limpa)."""
    novos = {c: getattr(dados, c) for c in dados.model_fields_set
             if getattr(dados, c) is not None or c == "recompensa"}
    with em_conta(ctx.conta_id) as s:
        cfg = obter(s, travar=True)
        antes = config_json(cfg)
        for campo, valor in novos.items():
            setattr(cfg, campo, valor)
        cfg.atualizado_em = relogio.agora()
        s.flush()
        depois = config_json(cfg)
        mudou = sorted(c for c in depois if depois[c] != antes[c])
        if mudou:
            registrar(s, "config_crescimento", "info", {"campos": mudou}, usuario_id=ctx.usuario_id)
        return depois
