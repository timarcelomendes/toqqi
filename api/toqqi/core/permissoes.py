"""Catálogo de permissões e padrões por perfil."""
from sqlalchemy import insert
from sqlalchemy.orm import Session

from toqqi.modelos import PerfilPermissao

# (chave, rótulo, grupo)
CATALOGO: list[tuple[str, str, str]] = [
    ("painel.ver", "Ver o painel", "Painel"),
    ("painel.exportar", "Exportar dados do painel", "Painel"),
    ("contatos.ver", "Ver contatos", "Contatos"),
    ("contatos.editar", "Adicionar e editar contatos", "Contatos"),
    ("contatos.excluir", "Excluir contatos", "Contatos"),
    ("importacao.usar", "Importar planilhas de contatos", "Contatos"),
    ("envios.ver", "Ver envios", "Envios"),
    ("envios.disparar", "Disparar pesquisas", "Envios"),
    ("formularios.ver", "Ver formulários", "Formulários"),
    ("formularios.editar", "Criar e editar formulários", "Formulários"),
    ("respostas.ver", "Ver respostas", "Respostas"),
    ("respostas.editar", "Editar respostas", "Respostas"),
    ("acoes.ver", "Ver planos de ação", "Planos de ação"),
    ("acoes.tratar", "Tratar planos de ação", "Planos de ação"),
    ("acoes.excluir", "Excluir planos de ação", "Planos de ação"),
    ("crescimento.ver", "Ver indicações e oportunidades", "Crescimento"),
    ("crescimento.tratar", "Tratar indicações e registrar ofertas", "Crescimento"),
    ("relatorios.ver", "Ver relatórios", "Relatórios"),
    ("equipe.gerenciar", "Gerenciar a equipe e as permissões", "Administração"),
    ("configuracoes.gerenciar", "Alterar as configurações da conta", "Administração"),
    ("assinatura.gerenciar", "Gerenciar a assinatura e o pagamento", "Administração"),
    ("auditoria.ver", "Ver o registro de atividades", "Administração"),
    ("zona_risco.usar", "Usar a zona de risco (ações irreversíveis)", "Administração"),
]

TODAS = [c for c, _, _ in CATALOGO]
CHAVES = frozenset(TODAS)
SOMENTE_ADMIN = frozenset({
    "equipe.gerenciar", "configuracoes.gerenciar", "assinatura.gerenciar", "auditoria.ver", "zona_risco.usar",
})

PADRAO = {
    "gestor": [p for p in TODAS if p not in SOMENTE_ADMIN],
    "consulta": [
        "painel.ver", "contatos.ver", "envios.ver", "formularios.ver",
        "respostas.ver", "acoes.ver", "acoes.tratar", "crescimento.ver", "relatorios.ver",
    ],
}


def catalogo_json() -> list[dict]:
    return [
        {"chave": c, "rotulo": r, "grupo": g, "somente_admin": c in SOMENTE_ADMIN}
        for c, r, g in CATALOGO
    ]


def ordenar(perms) -> list[str]:
    """Ordena na ordem do catálogo, ignorando o que não existe mais."""
    conj = set(perms)
    return [p for p in TODAS if p in conj]


def semear_padrao(s: Session, conta_id: int) -> None:
    linhas = [
        {"conta_id": conta_id, "perfil": perfil, "permissao": p}
        for perfil, perms in PADRAO.items()
        for p in perms
    ]
    s.execute(insert(PerfilPermissao), linhas)
