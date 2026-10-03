"""Indicações (etapa 5c; ver com `crescimento.ver`, alterar com `crescimento.tratar`): o convite de indicação na tela
final da pesquisa, a indicação feita pela página pública, a lista (filtros e resumo), a indicação registrada à mão, a
troca de situação e de responsável, a exclusão (pedido da pessoa indicada, LGPD) e o CSV.

Direito ao convite (`pode_indicar`): indicações ligadas na conta, conta liberada (`assinatura.regras.liberada`) e a nota
principal da resposta do convite (não arquivada) é de promotor (NPS 9–10) ou CSAT 5. Só no convite: o link público do
formulário não tem a quem atribuir a indicação; o formulário do convite precisa estar disponível (`publico.servico`).

Indicação pela página pública (`criar_publica`): até 3 tentativas aceitas por convite (`convites.indicacoes_feitas`,
contadas sob o FOR UPDATE do convite; a 4ª é 409). O mesmo telefone ou e-mail de uma indicação ainda aberta (nova ou
em contato) da conta não cria outra e responde igual — e gasta a vaga como uma nova, senão 201/201 contra 201/409
revelaria que o número já está no funil; responsável = o da empresa de quem indicou. Depois do commit: aviso por
e-mail ao responsável (se tiver e-mail), senão aos administradores ativos com e-mail confirmado (quem grava envolve o
trabalho em `coletar_avisos()` e agenda `enviar_avisos`; sem coletor o aviso não sai), e o webhook `indicacao.criada`
(coletor dos webhooks). O que a pessoa escreveu não vai para o log (nem o aviso, quando o provedor de e-mail não conta
como configurado: o `console` em produção imprimiria os dados).

Webhooks: `indicacao.criada` (pela pesquisa ou à mão) e `indicacao.atualizada` (quando a situação muda, com
`situacao_anterior`); o corpo é o item da lista. Auditoria sem dados pessoais: `indicacao_registrada` (à mão),
`indicacao_atualizada` (situação) e `indicacao_excluida`. A exclusão (pedido da pessoa, LGPD) também esquece as
entregas de webhook da indicação (`webhooks.esquecer_entregas`), na mesma transação.

As consultas levam `conta_id` explícito além do RLS (como o resto do código), para o banco usar os índices por conta.
"""
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy import Text, cast, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from toqqi.core import email, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, sem_jit, travar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.filtros import entre_datas
from toqqi.core.paginacao import Pagina
from toqqi.core.texto import sem_acento, so_digitos
from toqqi.modelos import (
    ConfigCrescimento,
    Conta,
    Contato,
    Convite,
    Empresa,
    Indicacao,
    Responsavel,
    Resposta,
    Usuario,
)
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.crescimento.configuracao import obter
from toqqi.modulos.crescimento.esquemas import ABERTAS
from toqqi.modulos.empresas.servico import conferir_referencias, ref
from toqqi.modulos.envios.configuracao import provedor_ok
from toqqi.modulos.integracoes.webhooks import enfileirar, esquecer_entregas
from toqqi.modulos.painel.servico import _validar_periodo
from toqqi.modulos.relatorios.regras import data_br, gerar_csv, num, sim_nao
from toqqi.modulos.respostas.registro import renderizar

log = logging.getLogger("toqqi.crescimento")

MAX_POR_CONVITE = 3
MSG_OBRIGADO = "Obrigado pela indicação!"
ROTULOS_SITUACAO = {"nova": "Nova", "em_contato": "Em contato", "cliente": "Virou cliente",
                    "nao_avancou": "Não avançou"}
ROTULOS_ORIGEM = {"pesquisa": "Pesquisa", "manual": "Registrada à mão"}
CAMINHO_TELA = "/crescimento/indicacoes"
# busca sem acento (como a busca de empresas do assistente): translate + lower no banco, sem_acento no termo
SEM_ACENTO_DE = "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ"
SEM_ACENTO_PARA = "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN"
REFERENCIAS = {
    "indicador_contato_id": (Contato, "Contato não encontrado."),
    "indicador_empresa_id": (Empresa, "Empresa não encontrada."),
    "responsavel_id": (Responsavel, "Responsável não encontrado."),
}


def telefone_legivel(t: str | None) -> str:
    """ "5511987654321" → "(11) 98765-4321"; o que não for 55 + DDD + número sai como está."""
    d = so_digitos(t or "")
    if d.startswith("55") and len(d) in (12, 13):
        numero = d[4:]
        return f"({d[2:4]}) {numero[:-4]}-{numero[-4:]}"
    return t or ""


# ---- direito ao convite e texto do cartão ------------------------------------------------

def da_direito(r: Resposta | None) -> bool:
    """Nota principal de promotor (NPS 9–10) ou CSAT 5."""
    if r is None or r.nota is None:
        return False
    return (r.tipo_nota == "nps" and r.nota >= 9) or (r.tipo_nota == "csat" and r.nota == 5)


def _config_se_pode(s: Session, r: Resposta | None) -> ConfigCrescimento | None:
    """A configuração, se a resposta dá direito, as indicações estão ligadas e a conta (da transação) está liberada."""
    if not da_direito(r):
        return None
    cfg = obter(s, criar=False)
    if not cfg.indicacoes_ativas:
        return None
    conta = s.scalar(select(Conta))
    return cfg if conta is not None and liberada(conta) else None


def pode_indicar(s: Session, r: Resposta | None) -> bool:
    """Nota que dá direito, indicações ligadas e conta liberada."""
    return _config_se_pode(s, r) is not None


def convite_de_indicacao(s: Session, r: Resposta | None, v: dict) -> dict | None:
    """{titulo, texto, recompensa} do cartão de indicação (variáveis {empresa} e {nome} trocadas), ou None."""
    cfg = _config_se_pode(s, r)
    if cfg is None:
        return None
    variaveis = {"empresa": v.get("empresa") or "", "nome": v.get("nome") or ""}
    return {"titulo": renderizar(cfg.titulo_convite, variaveis), "texto": renderizar(cfg.texto_convite, variaveis),
            "recompensa": renderizar(cfg.recompensa, variaveis) or None}


def resposta_do_convite(s: Session, convite_id: int) -> Resposta | None:
    """A resposta do convite, se não foi arquivada (arquivada não dá direito ao convite de indicação)."""
    return s.scalar(select(Resposta).where(Resposta.convite_id == convite_id, Resposta.arquivada.is_(False))
                    .order_by(Resposta.id.desc()).limit(1))


# ---- avisos por e-mail (depois do commit) ----------------------------------------------------

@dataclass
class Aviso:
    para: str
    assunto: str
    paragrafos: list[str]
    botao: tuple[str, str]
    conta_id: int


_coletados: ContextVar[list | None] = ContextVar("avisos_indicacao_apos_commit", default=None)


@contextmanager
def coletar_avisos() -> Iterator[list[Aviso]]:
    """Junta os avisos de indicação nova decididos durante o bloco, para enviar depois do commit."""
    lista: list[Aviso] = []
    marca = _coletados.set(lista)
    try:
        yield lista
    finally:
        _coletados.reset(marca)


def enviar_avisos(avisos: Iterable[Aviso]) -> None:
    """Envia um a um (e-mail do sistema: falha vai para o log sem os dados e não derruba nada). Sem provedor de e-mail
    configurado (mesma regra das pesquisas), não envia: o `console` imprimiria os dados da pessoa no log."""
    avisos = list(avisos)
    if not avisos:
        return
    if not provedor_ok():
        log.info("%d aviso(s) de indicação não enviado(s): o envio de e-mails não está configurado.", len(avisos))
        return
    for a in avisos:
        email.enviar(a.para, a.assunto, a.paragrafos, a.botao, assunto_no_log="Nova indicação", conta_id=a.conta_id,
                     tipo="indicacao")


def _quem_indicou(empresa: Empresa | None, contato: Contato | None) -> tuple[str, str]:
    """(nome curto para o assunto, descrição completa) de quem indicou."""
    if empresa is not None:
        return empresa.nome, f"{empresa.nome} ({contato.nome})" if contato is not None else empresa.nome
    if contato is not None:
        return contato.nome, contato.nome
    return "um cliente", "Um cliente"


def _coletar_aviso(s: Session, i: Indicacao) -> None:
    lista = _coletados.get()
    if lista is None:
        return
    responsavel = s.get(Responsavel, i.responsavel_id) if i.responsavel_id else None
    if responsavel is not None and responsavel.email:
        destinos = [responsavel.email]
    else:
        destinos = list(s.scalars(select(Usuario.email).where(
            Usuario.conta_id == i.conta_id, Usuario.perfil == "admin", Usuario.situacao == "ativo",
            Usuario.email_confirmado.is_(True)).order_by(Usuario.id)))
    if not destinos:
        return
    empresa = s.get(Empresa, i.indicador_empresa_id) if i.indicador_empresa_id else None
    contato = s.get(Contato, i.indicador_contato_id) if i.indicador_contato_id else None
    curto, completo = _quem_indicou(empresa, contato)
    indicado = f"{i.nome}, {i.empresa}" if i.empresa else i.nome
    paragrafos = [f"{completo} indicou {i.nome}" + (f" ({i.empresa})" if i.empresa else "") + "."]
    if i.telefone:
        paragrafos.append(f"WhatsApp ou telefone: {telefone_legivel(i.telefone)}")
    if i.email:
        paragrafos.append(f"E-mail: {i.email}")
    if i.observacao:
        paragrafos.append(f"Observação: {i.observacao}")
    paragrafos.append("Pode dizer à pessoa quem fez a indicação." if i.pode_identificar else
                      "Quem indicou pediu para não ser identificado: não diga à pessoa quem fez a indicação.")
    if responsavel is not None:
        paragrafos.append(f"Responsável: {responsavel.nome}.")
    else:
        paragrafos.append("A indicação está sem responsável: escolha quem vai cuidar dela no Toqqi.")
    botao = ("Ver indicações no Toqqi", f"{config().FRONTEND_URL.rstrip('/')}{CAMINHO_TELA}")
    for para in destinos:
        lista.append(Aviso(para, f"Nova indicação de {curto}: {indicado}", paragrafos, botao, i.conta_id))


# ---- consulta e formato -------------------------------------------------------------------

def _consulta():
    contato, empresa, responsavel = aliased(Contato), aliased(Empresa), aliased(Responsavel)
    return (select(Indicacao, contato.nome.label("contato_nome"), empresa.nome.label("empresa_nome"),
                   responsavel.nome.label("responsavel_nome"))
            .select_from(Indicacao)
            .outerjoin(contato, contato.id == Indicacao.indicador_contato_id)
            .outerjoin(empresa, empresa.id == Indicacao.indicador_empresa_id)
            .outerjoin(responsavel, responsavel.id == Indicacao.responsavel_id))


def indicacao_json(x) -> dict:
    i: Indicacao = x.Indicacao
    return {
        "id": i.id, "origem": i.origem, "nome": i.nome, "empresa": i.empresa, "telefone": i.telefone,
        "email": i.email, "observacao": i.observacao,
        "indicador": {"contato": ref(i.indicador_contato_id, x.contato_nome),
                      "empresa": ref(i.indicador_empresa_id, x.empresa_nome)},
        "pode_identificar": i.pode_identificar, "responsavel": ref(i.responsavel_id, x.responsavel_nome),
        "situacao": i.situacao, "valor_mensal": i.valor_mensal, "motivo": i.motivo,
        "criada_em": i.criada_em, "atualizada_em": i.atualizada_em,
    }


def _uma(s: Session, indicacao_id: int) -> dict:
    # populate_existing: relê do banco o que acabou de mudar (datas no mesmo formato das listas)
    x = s.execute(_consulta().where(Indicacao.id == indicacao_id)
                  .execution_options(populate_existing=True)).one_or_none()
    if x is None:
        raise nao_encontrado("Indicação não encontrada.")
    return indicacao_json(x)


def _indicacao(s: Session, indicacao_id: int, travar_linha: bool = False) -> Indicacao:
    i = s.get(Indicacao, indicacao_id, with_for_update=travar_linha)
    if i is None:
        raise nao_encontrado("Indicação não encontrada.")
    return i


def _sem_acento_sql(coluna):
    return func.lower(func.translate(cast(coluna, Text), SEM_ACENTO_DE, SEM_ACENTO_PARA))


def _busca(termo: str):
    """Nome, empresa e e-mail (sem acento, sem diferenciar maiúsculas); telefone pelos dígitos (4 ou mais)."""
    t = sem_acento(termo).lower()
    conds = [_sem_acento_sql(c).contains(t, autoescape=True)
             for c in (Indicacao.nome, Indicacao.empresa, Indicacao.email)]
    digitos = so_digitos(termo)
    if len(digitos) >= 4:
        conds.append(Indicacao.telefone.contains(digitos, autoescape=True))
    return or_(*conds)


def _condicoes(ctx: Contexto, f) -> tuple[list, list]:
    """(período e responsável — os do resumo; + situação e busca — os da lista)."""
    base = [Indicacao.conta_id == ctx.conta_id, *entre_datas(Indicacao.criada_em, f.de, f.ate)]
    if f.responsavel_id is not None:
        base.append(Indicacao.responsavel_id.is_(None) if f.responsavel_id == 0
                    else Indicacao.responsavel_id == f.responsavel_id)
    lista = list(base)
    if f.situacao:
        lista.append(Indicacao.situacao == f.situacao)
    if f.busca and f.busca.strip():
        lista.append(_busca(f.busca.strip()))
    return base, lista


# ---- lista, resumo e CSV ----------------------------------------------------------------------

def listar(ctx: Contexto, f, pg: Pagina) -> dict:
    """Mais novas primeiro; `resumo` com os mesmos filtros de período e responsável (sem situação e busca)."""
    _validar_periodo(f.de, f.ate)
    base, conds = _condicoes(ctx, f)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        total = s.scalar(select(func.count()).select_from(Indicacao).where(*conds))
        linhas = s.execute(_consulta().where(*conds).order_by(Indicacao.criada_em.desc(), Indicacao.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
        r = s.execute(select(
            func.count().filter(Indicacao.situacao == "nova"),
            func.count().filter(Indicacao.situacao == "em_contato"),
            func.count().filter(Indicacao.situacao == "cliente"),
            func.count().filter(Indicacao.situacao == "nao_avancou"),
            func.coalesce(func.sum(Indicacao.valor_mensal), 0),
        ).select_from(Indicacao).where(*base)).one()
    resumo = {"novas": r[0], "em_contato": r[1], "clientes": r[2], "nao_avancou": r[3], "receita_mensal": r[4]}
    return {**pg.resultado([indicacao_json(x) for x in linhas], total), "resumo": resumo}


CABECALHO_CSV = ["Data", "Nome", "Empresa", "Telefone", "E-mail", "Observação", "Indicada por (empresa)",
                 "Indicada por (contato)", "Pode dizer quem indicou", "Origem", "Responsável", "Situação",
                 "Valor mensal", "Motivo", "Atualizada em"]


def exportar_csv(ctx: Contexto, f) -> str:
    _validar_periodo(f.de, f.ate)
    _, conds = _condicoes(ctx, f)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        linhas = s.execute(_consulta().where(*conds)
                           .order_by(Indicacao.criada_em.desc(), Indicacao.id.desc())).all()
    return gerar_csv(CABECALHO_CSV, [linha_csv(x) for x in linhas])


def consulta_csv():
    """As linhas do CSV (a consulta da lista), sem filtro nem ordem."""
    return _consulta()


def linha_csv(x) -> list:
    """Uma linha de `CABECALHO_CSV` (para `relatorios.regras.gerar_csv`) de uma linha de `consulta_csv`."""
    i = x.Indicacao
    return [data_br(i.criada_em), i.nome, i.empresa or "", telefone_legivel(i.telefone), i.email or "",
            i.observacao or "", x.empresa_nome or "", x.contato_nome or "", sim_nao(i.pode_identificar),
            ROTULOS_ORIGEM[i.origem], x.responsavel_nome or "", ROTULOS_SITUACAO[i.situacao],
            num(i.valor_mensal), i.motivo or "", data_br(i.atualizada_em)]


def nome_csv() -> str:
    return f"indicacoes-{relogio.hoje().isoformat()}.csv"


# ---- criar ----------------------------------------------------------------------------------

def _repetida_aberta(s: Session, conta_id: int, telefone: str | None, email_: str | None) -> bool:
    conds = []
    if telefone:
        conds.append(Indicacao.telefone == telefone)
    if email_:
        conds.append(Indicacao.email == email_)
    return bool(conds) and bool(s.scalar(select(exists().where(
        Indicacao.conta_id == conta_id, Indicacao.situacao.in_(ABERTAS), or_(*conds)))))


def indisponivel() -> AppError:
    return AppError(409, "indicacao_indisponivel", "Esta pesquisa não aceita indicações.")


def criar_publica(s: Session, c: Convite, dados) -> Indicacao | None:
    """Indicação pela página pública, dentro de em_conta(conta do convite), com o convite travado (FOR UPDATE: o
    limite de 3 não corre). Toda tentativa aceita gasta uma vaga do convite, a repetida também; a repetida devolve
    None (nada é criado; quem chamou responde igual)."""
    dados.conferir_contato()
    r = resposta_do_convite(s, c.id) if c.respondido_em is not None else None
    if not pode_indicar(s, r):
        raise indisponivel()
    if c.indicacoes_feitas >= MAX_POR_CONVITE:
        raise AppError(409, "limite_indicacoes", f"Você já fez {MAX_POR_CONVITE} indicações. Obrigado!")
    c.indicacoes_feitas += 1  # antes de saber se é repetida: a resposta não pode depender disso
    travar(s, f"indicacoes:{c.conta_id}")  # a conferência de repetida e a gravação não correm entre convites
    if _repetida_aberta(s, c.conta_id, dados.telefone, dados.email):
        return None
    contato_id = r.contato_id or c.contato_id
    empresa_id = r.empresa_id or c.empresa_id
    if empresa_id is None and contato_id is not None:
        contato = s.get(Contato, contato_id)
        empresa_id = contato.empresa_id if contato is not None else None
    empresa = s.get(Empresa, empresa_id) if empresa_id is not None else None
    agora = relogio.agora()
    i = Indicacao(conta_id=c.conta_id, origem="pesquisa", convite_id=c.id, resposta_id=r.id,
                  indicador_contato_id=contato_id, indicador_empresa_id=empresa.id if empresa is not None else None,
                  pode_identificar=dados.pode_identificar, nome=dados.nome, empresa=dados.empresa,
                  telefone=dados.telefone, email=dados.email, observacao=dados.observacao, situacao="nova",
                  responsavel_id=empresa.responsavel_id if empresa is not None else None, criada_em=agora,
                  atualizada_em=agora)
    s.add(i)
    s.flush()
    _coletar_aviso(s, i)
    enfileirar(s, "indicacao.criada", _uma(s, i.id))
    return i


def criar(ctx: Contexto, dados) -> dict:
    """Indicação registrada à mão ("veio por telefone"). Sem empresa de quem indicou: a do contato; com empresa e sem
    responsável: o responsável da empresa."""
    dados.conferir_contato()
    with em_conta(ctx.conta_id) as s:
        conferir_referencias(s, dados.model_dump(), REFERENCIAS)
        contato = s.get(Contato, dados.indicador_contato_id) if dados.indicador_contato_id else None
        empresa_id = dados.indicador_empresa_id or (contato.empresa_id if contato is not None else None)
        responsavel_id = dados.responsavel_id
        if responsavel_id is None and empresa_id is not None:
            responsavel_id = s.get(Empresa, empresa_id).responsavel_id
        agora = relogio.agora()
        i = Indicacao(conta_id=ctx.conta_id, origem="manual", indicador_contato_id=dados.indicador_contato_id,
                      indicador_empresa_id=empresa_id, pode_identificar=dados.pode_identificar, nome=dados.nome,
                      empresa=dados.empresa, telefone=dados.telefone, email=dados.email, observacao=dados.observacao,
                      situacao="nova", responsavel_id=responsavel_id, criada_em=agora, atualizada_em=agora,
                      criada_por=ctx.usuario_id, atualizada_por=ctx.usuario_id)
        s.add(i)
        s.flush()
        registrar(s, "indicacao_registrada", "info", {"indicacao_id": i.id}, usuario_id=ctx.usuario_id)
        item = _uma(s, i.id)
        enfileirar(s, "indicacao.criada", item)
        return item


# ---- alterar e excluir ------------------------------------------------------------------------

def _invalido(campo: str, msg: str) -> AppError:
    return AppError(422, "dados_invalidos", "Confira os campos destacados.", {campo: msg})


def alterar(ctx: Contexto, indicacao_id: int, dados) -> dict:
    """'cliente' pede valor_mensal (>= 0); 'nao_avancou' aceita motivo; as outras situações limpam o valor (e o motivo
    só fica em 'nao_avancou'). Webhook `indicacao.atualizada` e auditoria quando a situação muda."""
    valores = {c: getattr(dados, c) for c in dados.model_fields_set}
    if valores.get("situacao", "") is None:  # obrigatória: null não muda
        del valores["situacao"]
    with em_conta(ctx.conta_id) as s:
        i = _indicacao(s, indicacao_id, travar_linha=True)
        conferir_referencias(s, valores, {"responsavel_id": REFERENCIAS["responsavel_id"]})
        antes = i.situacao
        situacao = valores.get("situacao", i.situacao)
        valor = valores["valor_mensal"] if "valor_mensal" in valores else i.valor_mensal
        motivo = valores["motivo"] if "motivo" in valores else i.motivo
        if situacao != "cliente":
            valor = None
        elif valor is None:
            raise _invalido("valor_mensal", "Informe o valor mensal do novo cliente.")
        if situacao != "nao_avancou":
            motivo = None
        i.situacao, i.valor_mensal, i.motivo = situacao, valor, motivo
        if "responsavel_id" in valores:
            i.responsavel_id = valores["responsavel_id"]
        i.atualizada_em, i.atualizada_por = relogio.agora(), ctx.usuario_id
        s.flush()
        item = _uma(s, i.id)
        if situacao != antes:
            registrar(s, "indicacao_atualizada", "info", {"indicacao_id": i.id, "de": antes, "para": situacao},
                      usuario_id=ctx.usuario_id)
            enfileirar(s, "indicacao.atualizada", {**item, "situacao_anterior": antes})
        return item


def excluir(ctx: Contexto, indicacao_id: int) -> None:
    """Pedido da pessoa indicada (LGPD): a linha some e, na mesma transação, os dados dela saem da fila dos webhooks
    (`esquecer_entregas`: as entregas pendentes somem e as já terminadas ficam no histórico sem os dados); a auditoria
    guarda só o id, a origem e a situação."""
    with em_conta(ctx.conta_id) as s:
        i = _indicacao(s, indicacao_id, travar_linha=True)
        registrar(s, "indicacao_excluida", "atencao", {"indicacao_id": i.id, "origem": i.origem,
                                                       "situacao": i.situacao}, usuario_id=ctx.usuario_id)
        esquecer_entregas(s, ctx.conta_id, "indicacao.", i.id)
        s.delete(i)
