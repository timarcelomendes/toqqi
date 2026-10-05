"""Etapa 5i (desfecho pela integração): `POST /integracao/empresas` — o ERP ou o CRM cria ou atualiza uma empresa
(código externo, CNPJ/CPF ou nome), o valor mensal, a renovação do contrato e, com `situacao`, marca a perda (com o
motivo) ou o retorno. Usa as mesmas regras da tela (contatos desativados na perda, limite do plano no retorno,
webhooks `empresa.*`), com a origem `api` no histórico."""
from datetime import date
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from toqqi.core.db import em_conta
from toqqi.core.errors import AppError
from toqqi.modelos import Empresa
from toqqi.modulos.empresas import desfecho
from toqqi.modulos.empresas.esquemas import Motivo, Renovacao, Valor
from toqqi.modulos.empresas.servico import _uma
from toqqi.modulos.integracoes.chave import ContextoIntegracao
from toqqi.core.validacao import Documento, TextoAte


class EmpresaIntegracaoIn(BaseModel):
    codigo_externo: TextoAte(100) = None
    documento: Documento = None
    nome: TextoAte(200) = None
    valor_mensal: Valor | None = None
    cliente_desde: date | None = None
    renovacao_em: Renovacao = None
    situacao: Literal["ativa", "perdida"] | None = None
    perdida_em: date | None = None
    motivo_perda: Motivo | None = None
    motivo_detalhe: TextoAte(300) = None


CAMPOS = ("documento", "valor_mensal", "cliente_desde", "renovacao_em")


def salvar(ci: ContextoIntegracao, dados: EmpresaIntegracaoIn) -> tuple[dict, bool]:
    """(empresa, se foi criada)."""
    if not (dados.codigo_externo or dados.documento or dados.nome):
        msg = "Informe o código externo, o CNPJ/CPF ou o nome da empresa."
        raise AppError(422, "dados_invalidos", msg, {"codigo_externo": msg})
    ctx = SimpleNamespace(conta_id=ci.conta_id, usuario_id=None)
    enviados = dados.model_fields_set
    with em_conta(ci.conta_id) as s:
        e = None
        for coluna, valor in ((Empresa.codigo_externo, dados.codigo_externo), (Empresa.documento, dados.documento),
                              (Empresa.nome, dados.nome)):
            if valor and e is None:
                e = s.scalar(select(Empresa).where(coluna == valor).order_by(Empresa.id).limit(1))
        nova = e is None
        desfecho.marcar(s, "api", None)
        if nova:
            if not dados.nome:
                msg = "Para criar a empresa, informe o nome."
                raise AppError(422, "dados_invalidos", msg, {"nome": msg})
            e = Empresa(nome=dados.nome, codigo_externo=dados.codigo_externo)
            s.add(e)
        elif dados.nome and "nome" in enviados:
            e.nome = dados.nome
        if dados.codigo_externo and not e.codigo_externo:
            e.codigo_externo = dados.codigo_externo
        for campo in CAMPOS:
            if campo in enviados and (campo != "valor_mensal" or not e.perdida_em):
                setattr(e, campo, getattr(dados, campo))
        s.flush()
        empresa_id, perdida = e.id, e.perdida_em is not None
    if dados.situacao == "perdida" and not perdida:
        if not dados.motivo_perda:
            msg = "Informe o motivo da perda."
            raise AppError(422, "dados_invalidos", msg, {"motivo_perda": msg})
        desfecho.perder(ctx, empresa_id, SimpleNamespace(perdida_em=dados.perdida_em, motivo_perda=dados.motivo_perda,
                                                         motivo_detalhe=dados.motivo_detalhe), origem="api")
    elif dados.situacao == "ativa" and perdida:
        valor = {"valor_mensal": dados.valor_mensal} if "valor_mensal" in enviados else {}
        corpo = SimpleNamespace(reativar_contatos=True, renovacao_em=dados.renovacao_em, **valor,
                                model_fields_set={"renovacao_em"} & enviados | set(valor))
        desfecho.voltar(ctx, empresa_id, corpo, origem="api")
    with em_conta(ci.conta_id) as s:
        return _uma(s, empresa_id), nova
