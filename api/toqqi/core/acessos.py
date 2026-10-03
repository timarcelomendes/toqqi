"""Registros de acesso (Marco Civil da Internet, art. 15: data, hora e IP de cada acesso, guardados por 6 meses, em
sigilo). Etapa 5f.

O que entra (na transação do próprio evento, com o IP já resolvido por `core.requisicao.IpDoCliente`):
- `login` (entrou); `login_falhou` (senha errada, e-mail não confirmado, acesso pendente ou bloqueado; e-mail
  desconhecido → sem conta nem usuário, numa transação própria em modo sistema; nunca o e-mail digitado);
- `cadastro` (conta criada); `pedido_acesso` (quando o pedido cria o usuário); `senha_redefinida` (pelo link do
  e-mail);
- `resposta` (resposta pelo convite ou pelo link público; `item_id` = a resposta) e `indicacao` (indicação pela página
  pública; `item_id` = a indicação). Envio repetido que não grava nada entra sem `item_id`.

Não entram: abrir páginas, imagens, descadastro, rotas da chave de integração, avisos da Meta e do Asaas e as chamadas
da sessão (o `login` identifica a sessão; a auditoria guarda o IP de cada ação). Só o IP: a porta de origem não chega
ao Toqqi.

Nenhuma tela lê esta tabela: o RLS só deixa a aplicação gravar (em conta, com a própria conta); ler e apagar, só em
modo sistema — a equipe técnica, por SQL, para atender ordem judicial (arts. 10 e 15), e a limpeza diária. Por isso o
INSERT vai sem RETURNING (o RLS não deixa ler a linha gravada). Sem FK: a linha sobrevive à exclusão do usuário e da
conta. A tarefa `limpeza` apaga o que passou de 184 dias (6 meses cheios), em lotes (`limpar`).
"""
from datetime import datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import modo_sistema
from toqqi.core.requisicao import ip_cliente
from toqqi.modelos import RegistroAcesso

EVENTOS = ("login", "login_falhou", "cadastro", "pedido_acesso", "senha_redefinida", "resposta", "indicacao")
DIAS_GUARDADOS = 184  # 6 meses cheios
LOTE_LIMPEZA = 5000
MAX_IP = 64
# texto puro: o INSERT do ORM pediria RETURNING (ou buscaria o id antes), e em conta o RLS não deixa ler a linha
_INSERIR = text("INSERT INTO registros_acesso (evento, conta_id, usuario_id, item_id, ip) "
                "VALUES (:evento, :conta_id, :usuario_id, :item_id, :ip)")


def registrar(s: Session, evento: str, *, conta_id: int | None, usuario_id: int | None = None,
              item_id: int | None = None) -> None:
    """Grava o acesso na transação de `s` (em conta: `conta_id` precisa ser a da transação)."""
    assert evento in EVENTOS, f"evento de acesso desconhecido: {evento}"
    ip = ip_cliente.get()
    s.execute(_INSERIR, {"evento": evento, "conta_id": conta_id, "usuario_id": usuario_id, "item_id": item_id,
                         "ip": ip[:MAX_IP] if ip else None})


def registrar_avulso(evento: str, *, conta_id: int | None = None, usuario_id: int | None = None) -> None:
    """`registrar` numa transação própria em modo sistema (ex.: entrada com e-mail desconhecido)."""
    with modo_sistema() as s:
        registrar(s, evento, conta_id=conta_id, usuario_id=usuario_id)


def limpar(agora: datetime | None = None) -> int:
    """Apaga os registros com mais de 184 dias (todas as contas), em lotes. Devolve quantos apagou."""
    limite = (agora or relogio.agora()) - timedelta(days=DIAS_GUARDADOS)
    apagados = 0
    while True:
        with modo_sistema() as s:  # só o modo sistema lê e apaga esta tabela
            lote = (select(RegistroAcesso.id).where(RegistroAcesso.criado_em < limite).limit(LOTE_LIMPEZA)
                    .scalar_subquery())
            n = s.execute(delete(RegistroAcesso).where(RegistroAcesso.id.in_(lote))
                          .execution_options(synchronize_session=False)).rowcount
        apagados += n
        if n < LOTE_LIMPEZA:
            return apagados
