"""Atalhos para as telas (§5.4): chave → rótulo, caminho e quem pode abrir. Usados nas respostas do assistente e nas
seções da Ajuda (`atalho`). A API tira os atalhos sem permissão, repetidos ou desconhecidos."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Atalho:
    chave: str
    rotulo: str
    caminho: str
    permissao: str | None = None  # None = todos os logados
    so_admin: bool = False


ATALHOS: dict[str, Atalho] = {a.chave: a for a in (
    Atalho("inicio", "Início", "/inicio"),
    Atalho("contatos", "Contatos", "/contatos", "contatos.ver"),
    Atalho("importar_contatos", "Importar contatos", "/contatos/importar", "importacao.usar"),
    Atalho("envios", "Envios", "/envios", "envios.ver"),
    Atalho("formularios", "Formulários", "/formularios", "formularios.ver"),
    Atalho("respostas", "Respostas", "/respostas", "respostas.ver"),
    Atalho("planos_de_acao", "Planos de ação", "/planos-de-acao", "acoes.ver"),
    Atalho("crescimento", "Crescimento", "/crescimento/indicacoes", "crescimento.ver"),
    Atalho("relatorios", "Relatórios", "/relatorios/empresas", "relatorios.ver"),
    Atalho("equipe", "Equipe", "/equipe", "equipe.gerenciar"),
    Atalho("config_empresa", "Dados da empresa", "/configuracoes/empresa", "configuracoes.gerenciar"),
    Atalho("config_envios", "Configurações de envio", "/configuracoes/envios", "configuracoes.gerenciar"),
    Atalho("config_acoes", "Configurações de ações", "/configuracoes/acoes", "configuracoes.gerenciar"),
    Atalho("config_ia", "Configurações de IA", "/configuracoes/ia", "configuracoes.gerenciar"),
    Atalho("seguranca", "Segurança", "/configuracoes/seguranca", "configuracoes.gerenciar"),
    Atalho("integracoes", "Integrações", "/integracoes", so_admin=True),
    Atalho("assinatura", "Assinatura", "/assinatura", "assinatura.gerenciar"),
    Atalho("minha_conta", "Minha conta", "/minha-conta"),
    Atalho("ajuda", "Ajuda", "/ajuda"),
)}
CHAVES: tuple[str, ...] = tuple(ATALHOS)
MAX_ATALHOS = 2


def pode_abrir(atalho: Atalho, perfil: str, permissoes) -> bool:
    if atalho.so_admin:
        return perfil == "admin"
    return atalho.permissao is None or atalho.permissao in permissoes


def filtrar(chaves, perfil: str, permissoes) -> list[dict]:
    """Até 2 atalhos {chave, rotulo, caminho}, na ordem dada, sem os desconhecidos, repetidos ou sem permissão."""
    itens: list[dict] = []
    vistos: set[str] = set()
    for chave in chaves or ():
        atalho = ATALHOS.get(chave) if isinstance(chave, str) else None
        if atalho is None or chave in vistos or not pode_abrir(atalho, perfil, permissoes):
            continue
        vistos.add(chave)
        itens.append({"chave": atalho.chave, "rotulo": atalho.rotulo, "caminho": atalho.caminho})
        if len(itens) == MAX_ATALHOS:
            break
    return itens
