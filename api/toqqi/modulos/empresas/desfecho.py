"""Etapa 5i, desfecho das empresas (docs/api-etapa-5i.md §2): "Marcar como perdida" e "Voltou a ser cliente".

O banco faz o resto: o gatilho `empresas_historico` grava a linha do tempo (perda, retorno e cada mudança do valor
mensal, com a origem e quem fez, lidos de `app.*` desta transação) e o `contatos_empresa_perdida` recusa contato ativo
em empresa perdida (409 `empresa_perdida`). Perder desativa os contatos ativos da empresa (param as pesquisas e saem
do limite do plano); voltar reativa os que a perda desativou (402 se passar do limite do plano, sem mudar nada)."""
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from toqqi.core import planos, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.modelos import Contato, Empresa, EmpresaHistorico

MOTIVOS = {
    "preco": "Preço",
    "concorrente": "Foi para um concorrente",
    "atendimento": "Atendimento ou qualidade",
    "produto": "O produto não atendeu",
    "encerrou": "Encerrou a atividade",
    "outro": "Outro",
}


def marcar(s: Session, origem: str, usuario_id: int | None, contatos: list[int] | None = None) -> None:
    """Diz ao gatilho do histórico de onde vem a escrita (só nesta transação)."""
    s.execute(text("select set_config('app.empresa_origem', :o, true), set_config('app.usuario_id', :u, true), "
                   "set_config('app.hoje', :h, true), set_config('app.contatos_desativados', :c, true)"),
              {"o": origem, "u": str(usuario_id or ""), "h": relogio.hoje().isoformat(),
               "c": ",".join(map(str, contatos or []))})


def _avisar(s: Session, evento: str, e: Empresa) -> None:
    """Webhook `empresa.perdida` / `empresa.reativada` (só os dados da empresa, sem contatos)."""
    from toqqi.modulos.integracoes.webhooks import enfileirar

    enfileirar(s, evento, {"empresa": {"id": e.id, "nome": e.nome, "documento": e.documento,
                                       "codigo_externo": e.codigo_externo, "valor_mensal": e.valor_mensal},
                           "perdida_em": e.perdida_em, "motivo": e.motivo_perda,
                           "motivo_rotulo": MOTIVOS.get(e.motivo_perda), "motivo_detalhe": e.motivo_detalhe,
                           "renovacao_em": e.renovacao_em})


def situacao(e: Empresa) -> str:
    return "perdida" if e.perdida_em else ("ativa" if e.ativa else "pausada")


def _empresa(s: Session, empresa_id: int) -> Empresa:
    e = s.get(Empresa, empresa_id, with_for_update=True)
    if e is None:
        raise nao_encontrado("Empresa não encontrada.")
    return e


def _invalido(campos: dict) -> AppError:
    return AppError(422, "dados_invalidos", "Confira os campos destacados.", campos)


def perder(ctx: Contexto, empresa_id: int, dados, origem: str = "tela") -> dict:
    from toqqi.modulos.empresas.servico import _uma

    hoje = relogio.hoje()
    data = dados.perdida_em or hoje
    detalhe = (dados.motivo_detalhe or "").strip() or None
    with em_conta(ctx.conta_id) as s:
        e = _empresa(s, empresa_id)
        if e.perdida_em:
            raise AppError(409, "ja_perdida", "Esta empresa já está marcada como perdida.")
        campos = {}
        if data > hoje:
            campos["perdida_em"] = "A data não pode ser no futuro."
        elif e.cliente_desde and data < e.cliente_desde:
            campos["perdida_em"] = "A data não pode ser antes de “Cliente desde”."
        else:
            ultima = s.scalar(select(func.max(EmpresaHistorico.data)).where(EmpresaHistorico.empresa_id == e.id))
            if ultima and data < ultima:
                campos["perdida_em"] = f"A data não pode ser antes de {ultima.strftime('%d/%m/%Y')}, a última mudança da empresa."
        if dados.motivo_perda == "outro" and len(detalhe or "") < 3:
            campos["motivo_detalhe"] = "Conte em poucas palavras o motivo."
        if campos:
            raise _invalido(campos)
        ativos = list(s.scalars(select(Contato.id).where(Contato.empresa_id == e.id, Contato.ativo.is_(True))))
        marcar(s, origem, ctx.usuario_id, ativos)
        if ativos:
            s.execute(update(Contato).where(Contato.id.in_(ativos)).values(ativo=False))
        e.ativa, e.perdida_em, e.motivo_perda, e.motivo_detalhe = False, data, dados.motivo_perda, detalhe
        s.flush()
        _avisar(s, "empresa.perdida", e)
        registrar(s, "empresa_perdida", "info",
                  {"empresa": {"id": e.id, "nome": e.nome}, "motivo": dados.motivo_perda, "contatos": len(ativos)},
                  usuario_id=ctx.usuario_id)
        return _uma(s, e.id) | {"contatos_desativados": len(ativos)}


def corrigir_perda(ctx: Contexto, empresa_id: int, dados, origem: str = "tela") -> dict:
    """Corrige a data, o motivo ou o detalhe de uma perda já marcada. O histórico (a linha da perda) acompanha pelo
    gatilho do banco; os contatos não mudam."""
    from toqqi.modulos.empresas.servico import _uma

    enviados = dados.model_fields_set
    hoje = relogio.hoje()
    with em_conta(ctx.conta_id) as s:
        e = _empresa(s, empresa_id)
        if not e.perdida_em:
            raise AppError(409, "nao_perdida", "Esta empresa não está marcada como perdida.")
        data = dados.perdida_em if "perdida_em" in enviados and dados.perdida_em else e.perdida_em
        motivo = dados.motivo_perda if "motivo_perda" in enviados and dados.motivo_perda else e.motivo_perda
        detalhe = ((dados.motivo_detalhe or "").strip() or None) if "motivo_detalhe" in enviados else e.motivo_detalhe
        campos = {}
        if data > hoje:
            campos["perdida_em"] = "A data não pode ser no futuro."
        elif e.cliente_desde and data < e.cliente_desde:
            campos["perdida_em"] = "A data não pode ser antes de “Cliente desde”."
        else:
            linha = s.scalar(select(func.max(EmpresaHistorico.id)).where(EmpresaHistorico.empresa_id == e.id,
                                                                         EmpresaHistorico.tipo == "perdida"))
            anterior = s.scalar(select(func.max(EmpresaHistorico.data)).where(
                EmpresaHistorico.empresa_id == e.id, EmpresaHistorico.id < (linha or 0)))
            if anterior and data < anterior:
                campos["perdida_em"] = f"A data não pode ser antes de {anterior.strftime('%d/%m/%Y')}, a mudança anterior da empresa."
        if motivo == "outro" and len(detalhe or "") < 3:
            campos["motivo_detalhe"] = "Conte em poucas palavras o motivo."
        if campos:
            raise _invalido(campos)
        if (data, motivo, detalhe) != (e.perdida_em, e.motivo_perda, e.motivo_detalhe):
            marcar(s, origem, ctx.usuario_id)
            e.perdida_em, e.motivo_perda, e.motivo_detalhe = data, motivo, detalhe
            s.flush()
            registrar(s, "empresa_perda_corrigida", "info",
                      {"empresa": {"id": e.id, "nome": e.nome}, "motivo": motivo, "perdida_em": data.isoformat()},
                      usuario_id=ctx.usuario_id)
        return _uma(s, e.id)


def voltar(ctx: Contexto, empresa_id: int, dados, origem: str = "tela") -> dict:
    from toqqi.modulos.empresas.servico import _uma

    enviados = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        e = _empresa(s, empresa_id)
        if not e.perdida_em:
            raise AppError(409, "nao_perdida", "Esta empresa não está marcada como perdida.")
        guardados = s.scalar(select(EmpresaHistorico.contatos).where(
            EmpresaHistorico.empresa_id == e.id, EmpresaHistorico.tipo == "perdida")
            .order_by(EmpresaHistorico.data.desc(), EmpresaHistorico.id.desc()).limit(1)) or []
        reativar = []
        if dados.reativar_contatos and guardados:
            reativar = list(s.scalars(select(Contato.id).where(
                Contato.id.in_(guardados), Contato.empresa_id == e.id, Contato.ativo.is_(False))))
        if reativar:
            planos.travar_contatos(s, ctx.conta_id)
            limite = planos.limite_da_conta(s, ctx.conta_id)
            if limite is not None and planos.contatos_ativos(s) + len(reativar) > limite:
                raise planos.erro_limite(limite)
        marcar(s, origem, ctx.usuario_id)
        if "valor_mensal" in enviados:
            e.valor_mensal = dados.valor_mensal
        if "renovacao_em" in enviados:
            e.renovacao_em = dados.renovacao_em
        e.ativa, e.perdida_em, e.motivo_perda, e.motivo_detalhe = True, None, None, None
        s.flush()
        if reativar:
            s.execute(update(Contato).where(Contato.id.in_(reativar)).values(ativo=True))
        _avisar(s, "empresa.reativada", e)
        registrar(s, "empresa_reativada", "info",
                  {"empresa": {"id": e.id, "nome": e.nome}, "contatos": len(reativar)}, usuario_id=ctx.usuario_id)
        return _uma(s, e.id) | {"contatos_reativados": len(reativar)}


ORIGENS = {"tela": "pela tela", "importacao": "pela importação", "api": "pela integração", "migracao": "no início do histórico",
           "sistema": "pelo sistema"}


def historico(ctx: Contexto, empresa_id: int) -> dict:
    """A linha do tempo da empresa (até 200, do mais recente ao mais antigo): entrada, mudanças de valor, perdas e
    retornos, com quem fez e por onde."""
    from toqqi.modelos import Usuario

    with em_conta(ctx.conta_id) as s:
        if s.get(Empresa, empresa_id) is None:
            raise nao_encontrado("Empresa não encontrada.")
        linhas = s.execute(select(EmpresaHistorico, Usuario.nome).outerjoin(Usuario, Usuario.id == EmpresaHistorico.usuario_id)
                           .where(EmpresaHistorico.empresa_id == empresa_id)
                           .order_by(EmpresaHistorico.data.desc(), EmpresaHistorico.id.desc()).limit(200)).all()
    return {"itens": [{
        "id": h.id, "tipo": h.tipo, "data": h.data, "valor_antes": h.valor_antes, "valor_depois": h.valor_depois,
        "motivo": h.motivo, "motivo_rotulo": MOTIVOS.get(h.motivo), "motivo_detalhe": h.motivo_detalhe,
        "contatos": len(h.contatos) if h.contatos is not None else None, "origem": h.origem,
        "origem_rotulo": ORIGENS.get(h.origem, h.origem),
        "usuario": {"id": h.usuario_id, "nome": nome} if h.usuario_id else None, "criado_em": h.criado_em,
    } for h, nome in linhas]}
