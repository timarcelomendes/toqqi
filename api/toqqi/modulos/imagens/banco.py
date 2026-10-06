"""Banco de imagens da conta (etapa 5e): as imagens que a conta pode usar no visual dos e-mails (a imagem de topo).

Tudo com `configuracoes.gerenciar`. São linhas de `imagens` com `uso = 'banco'`: PNG ou JPEG conferidos pelos bytes,
até 1 MB e até 30 por conta (a 31ª é 409 `limite_imagens`; a contagem roda sob uma trava por conta, então dois envios
ao mesmo tempo não passam de 30). Cada uma guarda o nome do arquivo enviado (limpo, até 120) e as dimensões lidas do
cabeçalho (nulas se não deu para ler), e sai sem login pelo `/publico/imagens/{chave}` de sempre (chave aleatória).

`em_uso` = é a imagem de topo dos e-mails (`config_envios.email_imagem_topo_id`) ou, desde a etapa 5l, aparece num
formulário não arquivado (no HTML ou no logo, publicado ou rascunho). Imagem em uso não pode ser excluída
(409 `imagem_em_uso`): a exclusão trava a imagem (FOR UPDATE) antes de conferir, e o PUT da configuração de envios
confere a imagem com FOR KEY SHARE, então os dois não se cruzam (se cruzassem, a chave estrangeira ainda deixaria a
imagem de topo nula, nunca quebrada). A mensagem diz onde a imagem está (os e-mails ou o formulário). Imagem de outra
conta, inexistente ou que é um logo → 404.

Auditoria: `imagem_enviada` ({nome, tipo, tamanho}) e `imagem_excluida` ({nome}). Os logos (conta e formulário)
continuam com 300 KB e não aparecem aqui. As consultas levam `conta_id` explícito além do RLS.
"""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, travar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.modelos import ConfigEnvios, Imagem
from toqqi.modulos.imagens.servico import (
    citadas_em_formularios,
    dimensoes,
    formulario_que_cita,
    nova_imagem,
    url_publica,
)

LIMITE = 30
MSG_LIMITE = "O banco de imagens tem até 30 imagens. Exclua uma para enviar outra."
MSG_EM_USO = "Esta imagem está no visual dos e-mails. Troque a imagem de topo antes de excluir."
MSG_NAO_ENCONTRADA = "Imagem não encontrada."
MSG_EM_FORMULARIO = "Esta imagem está no formulário “{nome}”. Tire a imagem do formulário antes de excluir."


def _imagem_de_topo(s: Session, conta_id: int) -> int | None:
    return s.scalar(select(ConfigEnvios.email_imagem_topo_id).where(ConfigEnvios.conta_id == conta_id))


def item_json(i: Imagem, topo_id: int | None, nos_formularios: str = "") -> dict:
    """`nos_formularios`: o JSON dos formulários da conta (`citadas_em_formularios`); a imagem citada lá está em uso."""
    return {"id": i.id, "url": url_publica(i.chave), "nome": i.nome, "tipo": i.tipo, "tamanho": i.tamanho,
            "largura": i.largura, "altura": i.altura, "criada_em": i.criada_em,
            "em_uso": i.id == topo_id or i.chave in nos_formularios}


def listar(ctx: Contexto) -> dict:
    """As imagens do banco, das mais novas para as mais antigas, e o limite."""
    with em_conta(ctx.conta_id) as s:
        topo = _imagem_de_topo(s, ctx.conta_id)
        imagens = s.scalars(select(Imagem).where(Imagem.conta_id == ctx.conta_id, Imagem.uso == "banco")
                            .order_by(Imagem.criada_em.desc(), Imagem.id.desc())).all()
        nos_formularios = citadas_em_formularios(s, ctx.conta_id) if imagens else ""
        return {"itens": [item_json(i, topo, nos_formularios) for i in imagens], "limite": LIMITE}


def enviar(ctx: Contexto, dados: bytes, tipo: str, nome: str | None) -> dict:
    """Grava a imagem (já conferida: PNG/JPEG de até 1 MB) e devolve o item. 409 com o banco cheio."""
    largura, altura = dimensoes(dados, tipo)
    with em_conta(ctx.conta_id) as s:
        travar(s, f"banco_imagens:{ctx.conta_id}")  # dois envios ao mesmo tempo não passam do limite
        total = s.scalar(select(func.count()).select_from(Imagem)
                         .where(Imagem.conta_id == ctx.conta_id, Imagem.uso == "banco"))
        if total >= LIMITE:
            raise AppError(409, "limite_imagens", MSG_LIMITE)
        imagem = nova_imagem(ctx.conta_id, "banco", dados, tipo, nome=nome, largura=largura, altura=altura)
        s.add(imagem)
        s.flush()
        s.refresh(imagem, ["criada_em"])  # relê do banco: a data sai como nas outras listas
        registrar(s, "imagem_enviada", "info", {"nome": nome, "tipo": tipo, "tamanho": len(dados)},
                  usuario_id=ctx.usuario_id)
        return item_json(imagem, None)


def excluir(ctx: Contexto, imagem_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        imagem = s.scalar(select(Imagem).where(Imagem.id == imagem_id, Imagem.conta_id == ctx.conta_id,
                                               Imagem.uso == "banco").with_for_update())
        if imagem is None:
            raise nao_encontrado(MSG_NAO_ENCONTRADA)
        if _imagem_de_topo(s, ctx.conta_id) == imagem.id:
            raise AppError(409, "imagem_em_uso", MSG_EM_USO)
        formulario = formulario_que_cita(s, ctx.conta_id, imagem.chave)
        if formulario is not None:
            raise AppError(409, "imagem_em_uso", MSG_EM_FORMULARIO.format(nome=formulario))
        nome = imagem.nome
        s.execute(delete(Imagem).where(Imagem.id == imagem.id, Imagem.conta_id == ctx.conta_id)
                  .execution_options(synchronize_session=False))
        registrar(s, "imagem_excluida", "info", {"nome": nome}, usuario_id=ctx.usuario_id)
