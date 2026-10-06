"""Exportar todos os dados da conta (Configurações › Dados da conta; só o administrador, também com a conta encerrada).
Etapa 5f.

`GET /conta/exportacao.zip` → `toqqi-{slug da conta}-{AAAA-MM-DD}.zip` com `LEIA-ME.txt` e um CSV por assunto (`ARQUIVOS`),
em ordem de id, na convenção dos CSV do Toqqi: `;`, UTF-8 com BOM, CRLF, datas e horas de São Paulo, vírgula decimal,
"Sim"/"Não", proteção contra fórmula e os rótulos das telas.

Nunca vão: `senha_hash`, `token_hash`, `token_semente`, hashes e segredos cifrados (chave de integração, webhooks,
WhatsApp), `teams_webhook`, `foto_url`, `ip_hash`, `wamid`, ids do Asaas, IP e navegador dos aceites, imagens, os
resumos e pareceres da IA do painel e dos relatórios (`ia_pareceres`) e os registros de acesso.

Sem tudo na memória: o zip é escrito num arquivo temporário (ZIP_DEFLATED), cada CSV direto na entrada do zip
(`zf.open(nome, "w", force_zip64=True)` + `TextIOWrapper`), as consultas vêm aos poucos (`yield_per(2000)`) e a
resposta (`ArquivoTemporario`) apaga o arquivo depois de enviar (e na falha). Tudo numa transação REPEATABLE READ
somente leitura (`em_conta(conta, leitura=True)`): um retrato só da conta. Uma exportação por vez por conta
(`pg_try_advisory_xact_lock('exportacao:{conta}')` ocupada → 409 `exportacao_em_andamento`). Auditoria
`exportacao_conta` (info) `{arquivos, linhas: {arquivo: n}, bytes}` numa transação própria, depois de gerar.
"""
import contextlib
import csv
import io
import json
import os
import re
import tempfile
import zipfile
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session, aliased
from starlette.responses import FileResponse

from toqqi.core import relogio
from toqqi.core.auditoria import GRUPOS, ROTULOS, grupo_de, registrar
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.email import TIPOS as TIPOS_EMAIL
from toqqi.core.errors import AppError
from toqqi.core.permissoes import CATALOGO, PADRAO
from toqqi.core.planos import NOMES as NOMES_PLANOS
from toqqi.core.texto import sem_acento
from toqqi.modelos import (
    Acao,
    AceiteTermos,
    Auditoria,
    Cargo,
    Cobranca,
    Conta,
    Contato,
    Convite,
    Descadastro,
    DominioLiberado,
    EmailEnviado,
    Empresa,
    Envio,
    Formulario,
    Grupo,
    Indicacao,
    IntegracaoChave,
    Oferta,
    PerfilContato,
    PerfilPermissao,
    Responsavel,
    Resposta,
    Segmento,
    Usuario,
    Webhook,
    WhatsappConta,
)
from toqqi.modulos.acoes import configuracao as config_acoes
from toqqi.modulos.assinatura import servico as assinaturas
from toqqi.modulos.crescimento import configuracao as config_crescimento
from toqqi.modulos.crescimento import indicacoes
from toqqi.modulos.crescimento.indicacoes import telefone_legivel
from toqqi.modulos.envios import configuracao as config_envios
from toqqi.modulos.envios.mensagens import link_formulario_publico
from toqqi.modulos.formularios.servico import ROTULOS_CONTEXTO, _celula
from toqqi.modulos.formularios.logica import respondivel, sem_citacoes
from toqqi.modulos.formularios.validacao import tipo_principal
from toqqi.modulos.relatorios.regras import FUSO, Numero, num
from toqqi.modulos.respostas import servico as respostas
from toqqi.modulos.respostas.convites import CHAVES_CONTEXTO
from toqqi.modulos.respostas.indicadores import ROTULOS_GRUPO, ROTULOS_TIPO
from toqqi.modulos.respostas.registro import formatar_valor, renderizar, variaveis

LOTE = 2000
MSG_EM_ANDAMENTO = "Já tem uma exportação sendo gerada nesta conta. Aguarde terminar."

ROTULOS_PRIORIDADE = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
ROTULOS_SITUACAO_ACAO = {"a_fazer": "A fazer", "em_andamento": "Em andamento", "concluida": "Concluída"}
ROTULOS_ORIGEM_ACAO = {"automatica": "Automática", "manual": "Manual"}
ROTULOS_TIPO_FORM = {"nps": "NPS", "csat": "CSAT", "personalizado": "Personalizado"}
ROTULOS_TIPO_ENVIO = {"convite": "Pesquisa", "lembrete": "Lembrete", "agradecimento": "Agradecimento", "retorno": "Retorno ao cliente"}
ROTULOS_ORIGEM_ENVIO = {"manual": "Enviado por alguém da equipe", "automatico": "Envio automático",
                        "lembrete": "Lembrete automático", "resposta": "Depois da resposta"}
ROTULOS_SITUACAO_ENVIO = {"pendente": "Enviando...", "enviado": "Enviado", "entregue": "Entregue", "lido": "Lido",
                          "erro": "Não saiu", "aberto_no_whatsapp": "Aberto no WhatsApp"}
ROTULOS_ORIGEM_DESCADASTRO = {"link": "Pelo link do e-mail", "um_clique": "Pelo botão do programa de e-mail",
                              "manual": "Registrado pela equipe", "whatsapp": "Pediu pelo WhatsApp (SAIR)"}
ROTULOS_SITUACAO_COBRANCA = {"pendente": "Pendente", "paga": "Paga", "vencida": "Vencida", "estornada": "Estornada",
                             "removida": "Removida"}
ROTULOS_FORMA = {"pix": "Pix", "boleto": "Boleto", "cartao": "Cartão"}
ROTULOS_LISTA = {"pode_crescer": "Pode crescer", "promotores": "Promotores recentes"}
ROTULOS_CANAL_OFERTA = {"whatsapp": "WhatsApp", "email": "E-mail"}
ROTULOS_RESULTADO = {"aceitou": "Aceitou", "recusou": "Recusou", "sem_resposta": "Sem resposta"}
ROTULOS_PERFIL = {"admin": "Administrador", "gestor": "Gestor", "consulta": "Consulta"}
ROTULOS_SITUACAO_USUARIO = {"ativo": "Ativo", "pendente": "Pendente", "bloqueado": "Bloqueado"}
ROTULOS_ORIGEM_ACEITE = {"cadastro": "Cadastro", "tela": "Tela de aceite"}
ROTULOS_GRAVIDADE = {"info": "Informação", "sucesso": "Sucesso", "atencao": "Atenção", "erro": "Erro"}
ROTULOS_SITUACAO_EMAIL = {"enviado": "Enviado", "falhou": "Falhou"}
ROTULOS_SITUACAO_CONTA = {"teste": "Em teste", "teste_expirado": "Teste encerrado", "cortesia": "Cortesia",
                          "ativa": "Ativa", "atrasada": "Atrasada", "cancelada": "Cancelada"}
ROTULOS_CANAL_ENVIOS = {"email": "E-mail", "whatsapp": "WhatsApp", "whatsapp_e_email": "WhatsApp e e-mail"}

# (arquivo, cabeçalho, o que é) — na ordem do zip e do LEIA-ME
ARQUIVOS: list[tuple[str, list[str], str]] = [
    ("empresas.csv", ["ID", "Nome", "CPF/CNPJ", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde",
                      "Código externo", "Ativa", "Criada em"], "Empresas clientes."),
    ("responsaveis.csv", ["ID", "Nome", "Função", "E-mail", "Criado em"], "Responsáveis pela carteira de clientes."),
    ("cadastros.csv", ["Tipo", "Nome", "Criado em"],
     "Grupos, segmentos, perfis de contato e cargos (Configurações › Cadastros)."),
    ("contatos.csv", ["ID", "Código", "Nome", "E-mail", "Telefone", "ID da empresa", "Empresa", "Cargo", "Perfil",
                      "Código externo", "Recebe pesquisas", "Ativo", "Última nota", "Último envio", "Próximo envio",
                      "Criado em"], "Contatos que recebem as pesquisas."),
    ("formularios.csv", ["ID", "Nome", "Descrição", "Tipo", "Ativo", "Público", "Padrão", "Arquivado", "Link público",
                         "Criado em", "Atualizado em", "Perguntas (JSON)", "Tema (JSON)", "Finais (JSON)"],
     "Formulários de pesquisa (a versão publicada), com as perguntas, o tema e os finais em JSON."),
    ("respostas.csv", ["ID", "Formulário", "ID do contato", "ID da empresa", "ID do convite", *respostas.CABECALHO_CSV,
                       "Data de entrada"],
     "Todas as respostas, inclusive as arquivadas (as colunas do CSV de Respostas, com os ids)."),
    ("respostas-perguntas.csv", ["ID da resposta", "Formulário", "ID da pergunta", "Pergunta", "Resposta"],
     "Uma linha por pergunta respondida em cada resposta."),
    ("planos-de-acao.csv", ["ID", "Título", "Descrição", "Prioridade", "Situação", "Prazo", "Origem", "Categoria",
                            "Tipo", "Nota", "ID da resposta", "ID da empresa", "Empresa", "ID do contato", "Contato",
                            "Responsável", "Resolução", "Passos da IA", "Criada por", "Criada em", "Iniciada em",
                            "Concluída em", "Concluída por"], "Planos de ação."),
    ("convites.csv", ["ID", "Data", "Formulário", "ID do contato", "Contato", "E-mail", "ID da empresa", "Canal",
                      "Assunto", "Referência", "Evento", *[ROTULOS_CONTEXTO[k] for k in CHAVES_CONTEXTO],
                      "Lembretes enviados", "Respondido em"],
     "Convites de pesquisa (cada link enviado ou gerado; o link em si não vai)."),
    ("envios.csv", ["ID", "Data", "ID do convite", "ID do contato", "Contato", "Para", "Canal", "Tipo", "Origem",
                    "Situação", "Erro", "Lembrete", "Enviado em", "Enviado por"],
     "Envios por e-mail e WhatsApp (pesquisas, lembretes e agradecimentos)."),
    ("descadastros.csv", ["E-mail", "Telefone", "Motivo", "Origem", "Data", "Registrado por"],
     "Lista de quem pediu para não receber mais pesquisas."),
    ("cobrancas.csv", ["Vencimento", "Valor", "Situação", "Forma", "Pago em"],
     "Faturas da assinatura (do ambiente atual da cobrança)."),
    ("indicacoes.csv", ["ID", *indicacoes.CABECALHO_CSV], "Indicações de clientes (Crescimento)."),
    ("ofertas.csv", ["ID", "Data", "ID da empresa", "Empresa", "Contato", "Lista", "Canal", "Texto", "Feita por",
                     "Resultado", "Valor", "Resultado em"], "Ofertas feitas a clientes (Crescimento)."),
    ("equipe.csv", ["ID", "Nome", "E-mail", "Cargo", "Telefone", "Perfil", "Situação", "E-mail confirmado",
                    "Último acesso", "Criado em", "Recebe resumo semanal", "Recebe alertas"],
     "Pessoas da equipe com acesso ao Toqqi (sem as senhas)."),
    ("aceites-dos-termos.csv", ["Nome", "E-mail", "Versão", "Aceito em", "Origem", "Retirado em"],
     "Aceites dos Termos de uso e da Política de privacidade."),
    ("auditoria.csv", ["Data", "Evento", "Código", "Grupo", "Gravidade", "Usuário", "Detalhe (JSON)", "IP"],
     "Registro de atividades (Auditoria)."),
    ("emails-enviados.csv", ["Data", "Tipo", "Destinatário", "Assunto", "Situação", "Erro"],
     "E-mails enviados em nome da conta (os últimos 90 dias)."),
    ("configuracoes.csv", ["Seção", "Item", "Valor"],
     "Configurações da conta: empresa, plano, segurança, envios, planos de ação, crescimento, IA, permissões, "
     "webhooks, WhatsApp e chave de integração (só o começo dela)."),
]
CABECALHOS = {nome: cabecalho for nome, cabecalho, _ in ARQUIVOS}


# ---- formato ------------------------------------------------------------------------------------

def data_hora(v: datetime | None) -> str:
    return "" if v is None else v.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def _valor(v):
    """Célula no formato dos CSV do Toqqi; textos protegidos contra fórmula."""
    if v is None:
        return ""
    if isinstance(v, Numero):
        return v
    if isinstance(v, bool):
        return "Sim" if v else "Não"
    if isinstance(v, str):
        return _celula(v)
    if isinstance(v, datetime):
        return data_hora(v)
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, Decimal):
        return num(v)
    if isinstance(v, (dict, list)):
        return _celula(_json(v))
    return v


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def slug(nome: str | None) -> str:
    """Como o do CSV do formulário; vazio → "conta"."""
    return re.sub(r"[^a-z0-9]+", "-", sem_acento((nome or "").lower())).strip("-") or "conta"


def nome_zip(conta_nome: str | None, hoje: date) -> str:
    return f"toqqi-{slug(conta_nome)}-{hoje.isoformat()}.zip"


class _Zip:
    """Escreve os CSV direto nas entradas do zip e conta as linhas de cada um."""

    def __init__(self, zf: zipfile.ZipFile):
        self.zf = zf
        self.linhas: dict[str, int] = {}

    def csv(self, nome: str, linhas) -> None:
        n = 0
        with self.zf.open(nome, "w", force_zip64=True) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="utf-8", newline="")
            texto.write("﻿")
            w = csv.writer(texto, delimiter=";", lineterminator="\r\n")
            w.writerow(CABECALHOS[nome])
            for linha in linhas:
                w.writerow([_valor(v) for v in linha])
                n += 1
            texto.flush()
            texto.detach()
        self.linhas[nome] = n

    def texto(self, nome: str, conteudo: str) -> None:
        self.zf.writestr(nome, conteudo.replace("\n", "\r\n").encode("utf-8"))


def _aos_poucos(s: Session, consulta):
    return s.execute(consulta.execution_options(yield_per=LOTE))


# ---- os arquivos ----------------------------------------------------------------------------------

def _empresas(s: Session, c: int):
    for e, grupo, segmento, responsavel in _aos_poucos(s, select(Empresa, Grupo.nome, Segmento.nome,
                                                                 Responsavel.nome)
                                                       .outerjoin(Grupo, Grupo.id == Empresa.grupo_id)
                                                       .outerjoin(Segmento, Segmento.id == Empresa.segmento_id)
                                                       .outerjoin(Responsavel, Responsavel.id == Empresa.responsavel_id)
                                                       .where(Empresa.conta_id == c).order_by(Empresa.id)):
        yield [e.id, e.nome, e.documento, grupo, segmento, responsavel, e.valor_mensal, e.cliente_desde,
               e.codigo_externo, e.ativa, e.criada_em]


def _responsaveis(s: Session, c: int):
    for r in _aos_poucos(s, select(Responsavel.id, Responsavel.nome, Responsavel.funcao, Responsavel.email,
                                   Responsavel.criado_em).where(Responsavel.conta_id == c).order_by(Responsavel.id)):
        yield list(r)


def _cadastros(s: Session, c: int):
    for rotulo, modelo in (("Grupo", Grupo), ("Segmento", Segmento), ("Perfil de contato", PerfilContato),
                           ("Cargo", Cargo)):
        for nome, criado_em in s.execute(select(modelo.nome, modelo.criado_em).where(modelo.conta_id == c)
                                         .order_by(modelo.id)):
            yield [rotulo, nome, criado_em]


def _contatos(s: Session, c: int):
    for x, empresa, cargo, perfil in _aos_poucos(s, select(Contato, Empresa.nome, Cargo.nome, PerfilContato.nome)
                                                 .outerjoin(Empresa, Empresa.id == Contato.empresa_id)
                                                 .outerjoin(Cargo, Cargo.id == Contato.cargo_id)
                                                 .outerjoin(PerfilContato, PerfilContato.id == Contato.perfil_id)
                                                 .where(Contato.conta_id == c).order_by(Contato.id)):
        yield [x.id, x.codigo, x.nome, x.email, telefone_legivel(x.telefone), x.empresa_id, empresa, cargo, perfil,
               x.codigo_externo, x.recebe_pesquisas, x.ativo, x.ultima_nota, x.ultimo_envio, x.proximo_envio,
               x.criado_em]


def _formularios(formularios: list[Formulario]):
    for f in formularios:
        yield [f.id, f.nome, f.descricao, ROTULOS_TIPO_FORM[tipo_principal(f.perguntas)], f.ativo, f.publico,
               f.padrao_nps or f.padrao_csat, f.arquivado, link_formulario_publico(f.codigo_publico), f.criado_em,
               f.atualizado_em, _json(f.perguntas), _json(f.tema), _json(f.finais or [])]


def _respostas(s: Session, c: int):
    consulta = (respostas.consulta_csv(Resposta.id.label("id"), Formulario.nome.label("formulario"),
                                       Resposta.contato_id, Resposta.empresa_id, Resposta.convite_id,
                                       Resposta.criada_em)
                .join(Formulario, Formulario.id == Resposta.formulario_id)
                .where(Resposta.conta_id == c).order_by(Resposta.id))
    for x in _aos_poucos(s, consulta):
        yield [x.id, x.formulario, x.contato_id, x.empresa_id, x.convite_id, *respostas.linha_csv(x), x.criada_em]


def _respostas_perguntas(s: Session, c: int, formularios: list[Formulario], conta_nome: str):
    v = variaveis(conta_nome)
    por_form = {f.id: (f.nome, [(p["id"], sem_citacoes(renderizar(p["titulo"], v)) or p["id"]) for p in f.perguntas
                                if respondivel(p.get("tipo"))]) for f in formularios}
    for rid, formulario_id, dadas in _aos_poucos(s, select(Resposta.id, Resposta.formulario_id, Resposta.respostas)
                                                 .where(Resposta.conta_id == c).order_by(Resposta.id)):
        nome, perguntas = por_form.get(formulario_id, ("", []))
        dadas = dadas or {}
        conhecidas = set()
        for pid, titulo in perguntas:
            conhecidas.add(pid)
            if pid in dadas:
                yield [rid, nome, pid, titulo, formatar_valor(dadas[pid])]
        for pid, valor in dadas.items():  # resposta a uma pergunta que saiu do formulário depois
            if pid not in conhecidas:
                yield [rid, nome, pid, respostas.PERGUNTA_REMOVIDA, formatar_valor(valor)]


def _acoes(s: Session, c: int):
    criou, concluiu = aliased(Usuario, name="criou"), aliased(Usuario, name="concluiu")
    consulta = (select(Acao, Empresa.nome, Contato.nome, Responsavel.nome, criou.nome, concluiu.nome)
                .outerjoin(Empresa, Empresa.id == Acao.empresa_id)
                .outerjoin(Contato, Contato.id == Acao.contato_id)
                .outerjoin(Responsavel, Responsavel.id == Acao.responsavel_id)
                .outerjoin(criou, criou.id == Acao.criado_por)
                .outerjoin(concluiu, concluiu.id == Acao.concluida_por)
                .where(Acao.conta_id == c).order_by(Acao.id))
    for a, empresa, contato, responsavel, criou_nome, concluiu_nome in _aos_poucos(s, consulta):
        passos = " | ".join(a.ia_passos or []) if a.ia_passos_situacao == "pronta" else ""
        yield [a.id, a.titulo, a.descricao, ROTULOS_PRIORIDADE.get(a.prioridade, a.prioridade),
               ROTULOS_SITUACAO_ACAO.get(a.situacao, a.situacao), a.prazo, ROTULOS_ORIGEM_ACAO.get(a.origem, a.origem),
               ROTULOS_GRUPO.get(a.grupo, ""), ROTULOS_TIPO.get(a.tipo_nota, ""), a.nota, a.resposta_id,
               a.empresa_id, empresa, a.contato_id, contato, responsavel, a.resolucao, passos, criou_nome,
               a.criada_em, a.iniciada_em, a.concluida_em, concluiu_nome]


def _convites(s: Session, c: int):
    consulta = (select(Convite.id, Convite.criado_em, Formulario.nome, Convite.contato_id, Contato.nome,
                       Contato.email, Convite.empresa_id, Convite.canal, Convite.assunto, Convite.referencia,
                       Convite.evento, Convite.contexto, Convite.lembretes_enviados, Convite.respondido_em)
                .join(Formulario, Formulario.id == Convite.formulario_id)
                .outerjoin(Contato, Contato.id == Convite.contato_id)
                .where(Convite.conta_id == c).order_by(Convite.id))
    for x in _aos_poucos(s, consulta):
        contexto = x.contexto or {}
        yield [x.id, x.criado_em, x[2], x.contato_id, x[4], x.email, x.empresa_id,
               respostas.ROTULOS_CANAL.get(x.canal, x.canal), x.assunto, x.referencia, x.evento,
               *[contexto.get(k) for k in CHAVES_CONTEXTO], x.lembretes_enviados, x.respondido_em]


def _envios(s: Session, c: int):
    consulta = (select(Envio, Contato.nome, Usuario.nome)
                .outerjoin(Contato, Contato.id == Envio.contato_id)
                .outerjoin(Usuario, Usuario.id == Envio.usuario_id)
                .where(Envio.conta_id == c).order_by(Envio.id))
    for e, contato, usuario in _aos_poucos(s, consulta):
        yield [e.id, e.criado_em, e.convite_id, e.contato_id, contato, e.para,
               respostas.ROTULOS_CANAL.get(e.canal, e.canal), ROTULOS_TIPO_ENVIO.get(e.tipo, e.tipo),
               ROTULOS_ORIGEM_ENVIO.get(e.origem, e.origem), ROTULOS_SITUACAO_ENVIO.get(e.situacao, e.situacao),
               e.erro, e.lembrete, e.enviado_em, usuario]


def _descadastros(s: Session, c: int):
    for d, usuario in _aos_poucos(s, select(Descadastro, Usuario.nome)
                                  .outerjoin(Usuario, Usuario.id == Descadastro.usuario_id)
                                  .where(Descadastro.conta_id == c).order_by(Descadastro.id)):
        yield [d.email, telefone_legivel(d.telefone), d.motivo,
               ROTULOS_ORIGEM_DESCADASTRO.get(d.origem, d.origem), d.criado_em, usuario]


def _cobrancas(s: Session, c: int):
    hoje = relogio.hoje()
    for x in s.scalars(select(Cobranca).where(Cobranca.conta_id == c,
                                              Cobranca.assinatura_id.in_(assinaturas.ids_do_ambiente()))
                       .order_by(Cobranca.id)):
        situacao = assinaturas.situacao_exibida(x, hoje)
        yield [x.vencimento, x.valor, ROTULOS_SITUACAO_COBRANCA.get(situacao, situacao),
               ROTULOS_FORMA.get(x.forma, x.forma), x.pago_em]


def _indicacoes(s: Session, c: int):
    for x in _aos_poucos(s, indicacoes.consulta_csv().where(Indicacao.conta_id == c).order_by(Indicacao.id)):
        yield [x.Indicacao.id, *indicacoes.linha_csv(x)]


def _ofertas(s: Session, c: int):
    for o, empresa, contato, usuario in _aos_poucos(s, select(Oferta, Empresa.nome, Contato.nome, Usuario.nome)
                                                    .outerjoin(Empresa, Empresa.id == Oferta.empresa_id)
                                                    .outerjoin(Contato, Contato.id == Oferta.contato_id)
                                                    .outerjoin(Usuario, Usuario.id == Oferta.usuario_id)
                                                    .where(Oferta.conta_id == c).order_by(Oferta.id)):
        yield [o.id, o.criada_em, o.empresa_id, empresa, contato, ROTULOS_LISTA.get(o.lista, o.lista),
               ROTULOS_CANAL_OFERTA.get(o.canal, o.canal), o.texto, usuario,
               ROTULOS_RESULTADO.get(o.resultado, o.resultado), o.valor, o.resultado_em]


def _equipe(s: Session, c: int):
    for u in s.scalars(select(Usuario).where(Usuario.conta_id == c).order_by(Usuario.id)):
        yield [u.id, u.nome, u.email, u.cargo, telefone_legivel(u.telefone), ROTULOS_PERFIL.get(u.perfil, u.perfil),
               ROTULOS_SITUACAO_USUARIO.get(u.situacao, u.situacao), u.email_confirmado, u.ultimo_acesso,
               u.criado_em, u.recebe_resumo_semanal, u.recebe_alertas]


def _aceites(s: Session, c: int):
    for a in s.scalars(select(AceiteTermos).where(AceiteTermos.conta_id == c).order_by(AceiteTermos.id)):
        yield [a.usuario_nome, a.usuario_email, a.versao, a.aceito_em, ROTULOS_ORIGEM_ACEITE.get(a.origem, a.origem),
               a.revogado_em]


def _auditoria(s: Session, c: int):
    for a, usuario in _aos_poucos(s, select(Auditoria, Usuario.nome)
                                  .outerjoin(Usuario, Usuario.id == Auditoria.usuario_id)
                                  .where(Auditoria.conta_id == c).order_by(Auditoria.id)):
        yield [a.criado_em, ROTULOS.get(a.evento, a.evento), a.evento, GRUPOS[grupo_de(a.evento)],
               ROTULOS_GRAVIDADE.get(a.gravidade, a.gravidade), usuario, _json(a.detalhe or {}), a.ip]


def _emails(s: Session, c: int):
    for e in _aos_poucos(s, select(EmailEnviado.criado_em, EmailEnviado.tipo, EmailEnviado.destinatario,
                                   EmailEnviado.assunto, EmailEnviado.situacao, EmailEnviado.erro)
                         .where(EmailEnviado.conta_id == c).order_by(EmailEnviado.id)):
        yield [e.criado_em, TIPOS_EMAIL.get(e.tipo, e.tipo), e.destinatario, e.assunto,
               ROTULOS_SITUACAO_EMAIL.get(e.situacao, e.situacao), e.erro]


# ---- configurações -----------------------------------------------------------------------------

ITENS_EMPRESA = {"nome": "Nome", "razao_social": "Razão social", "documento": "CPF/CNPJ", "telefone": "Telefone",
                 "email_contato": "E-mail de contato", "site": "Site", "cep": "CEP", "logradouro": "Logradouro",
                 "numero": "Número", "complemento": "Complemento", "bairro": "Bairro", "cidade": "Cidade",
                 "uf": "UF"}
ITENS_ENVIOS = {
    "envios_ativos": "Envios ligados", "envio_automatico": "Envio automático",
    "formulario_id": "Formulário do envio automático", "intervalo_dias": "Intervalo entre pesquisas (dias)",
    "descanso_dias": "Descanso depois de qualquer envio (dias)", "lembretes": "Lembretes",
    "dias_lembretes": "Dias dos lembretes", "janela_inicio": "Janela de envio: início",
    "janela_fim": "Janela de envio: fim", "so_dias_uteis": "Só em dias úteis", "responder_para": "Responder para",
    "remetente_nome": "Nome do remetente", "assunto_convite": "Assunto do convite", "texto_convite": "Texto do convite",
    "assunto_lembrete": "Assunto do lembrete", "texto_lembrete": "Texto do lembrete",
    "texto_whatsapp": "Texto do WhatsApp", "agradecimento_ativo": "Agradecimento ligado",
    "agradecimento": "Textos de agradecimento", "canal": "Canal", "email_cor": "Cor de destaque dos e-mails",
    "email_mostrar_logo": "Mostrar o logo nos e-mails", "email_imagem_topo": "Imagem de topo dos e-mails",
    "email_assinatura": "Assinatura dos e-mails", "email_rodape": "Rodapé dos e-mails",
}
ITENS_ACOES = {"prazo_detrator": "Prazo para detratores (dias)", "prazo_neutro": "Prazo para neutros (dias)",
               "prazo_promotor": "Prazo para promotores (dias)", "acao_promotor": "Criar ação para promotores"}
ITENS_CRESCIMENTO = {"indicacoes_ativas": "Indicações ligadas", "titulo_convite": "Título do convite de indicação",
                     "texto_convite": "Texto do convite de indicação", "recompensa": "Recompensa",
                     "texto_oferta": "Texto da oferta"}
ROTULOS_PERMISSAO = {chave: rotulo for chave, rotulo, _ in CATALOGO}


def _texto_config(v) -> str | None:
    if isinstance(v, (list, dict)):
        return _json(v)
    return v


def _configuracoes(s: Session, conta: Conta):
    c = conta.id
    sec = "Dados da empresa"
    for campo, rotulo in ITENS_EMPRESA.items():
        yield [sec, rotulo, getattr(conta, campo)]
    sec = "Plano e situação"
    yield [sec, "Plano", NOMES_PLANOS.get(conta.plano, conta.plano)]
    yield [sec, "Situação", ROTULOS_SITUACAO_CONTA.get(conta.situacao, conta.situacao)]
    yield [sec, "Teste até", conta.teste_ate]
    yield [sec, "Pago até", conta.pago_ate]
    yield [sec, "Em atraso desde", conta.atrasada_desde]
    yield [sec, "Conta criada em", conta.criada_em]
    sec = "Segurança"
    yield [sec, "Duração da sessão (minutos)", conta.sessao_minutos]
    dominios = s.scalars(select(DominioLiberado.dominio).where(DominioLiberado.conta_id == c)
                         .order_by(DominioLiberado.dominio)).all()
    yield [sec, "Domínios liberados", ", ".join(dominios)]
    sec = "Envios"
    cfg = config_envios.obter(s, criar=False)
    dados = config_envios.config_json(cfg, config_envios.imagem_topo(s, cfg))
    if dados.get("formulario_id"):
        dados["formulario_id"] = s.scalar(select(Formulario.nome).where(Formulario.id == dados["formulario_id"]))
    if dados.get("email_imagem_topo"):
        dados["email_imagem_topo"] = dados["email_imagem_topo"]["url"]
    dados["canal"] = ROTULOS_CANAL_ENVIOS.get(dados.get("canal"), dados.get("canal"))
    for campo, valor in dados.items():
        yield [sec, ITENS_ENVIOS.get(campo, campo), _texto_config(valor)]
    sec = "Planos de ação"
    for campo, valor in config_acoes.config_json(config_acoes.obter(s, criar=False)).items():
        yield [sec, ITENS_ACOES.get(campo, campo), valor]
    sec = "Crescimento"
    for campo, valor in config_crescimento.config_json(config_crescimento.obter(s, criar=False)).items():
        yield [sec, ITENS_CRESCIMENTO.get(campo, campo), valor]
    sec = "IA"
    yield [sec, "Análise das respostas pela IA", conta.ia_analise_respostas]
    yield [sec, "Modelo", conta.ia_modelo]
    yield [sec, "Estilo", conta.ia_estilo]
    yield [sec, "Passos sugeridos nas ações", conta.ia_passos_acoes]
    sec = "Permissões"
    dadas = {(p, perm) for p, perm in s.execute(select(PerfilPermissao.perfil, PerfilPermissao.permissao)
                                                 .where(PerfilPermissao.conta_id == c))}
    for perfil in PADRAO:
        for chave, rotulo, _ in CATALOGO:
            yield [sec, f"{ROTULOS_PERFIL[perfil]}: {rotulo}", (perfil, chave) in dadas]
    sec = "Webhooks"
    for w in s.scalars(select(Webhook).where(Webhook.conta_id == c).order_by(Webhook.id)):
        yield [sec, f"Webhook {w.id}: endereço", w.url]
        yield [sec, f"Webhook {w.id}: eventos", ", ".join(w.eventos)]
        yield [sec, f"Webhook {w.id}: ativo", w.ativo]
    sec = "WhatsApp"
    wc = s.scalar(select(WhatsappConta).where(WhatsappConta.conta_id == c))
    if wc is None:
        yield [sec, "Conectado", False]
    else:
        yield [sec, "Número", wc.numero_exibicao]
        yield [sec, "Nome verificado", wc.nome_verificado]
        yield [sec, "Modelo", f"{wc.modelo_nome} ({wc.modelo_idioma})"]
        yield [sec, "Ativo", wc.ativo]
    sec = "Chave de integração"
    prefixo = s.scalar(select(IntegracaoChave.prefixo).where(IntegracaoChave.conta_id == c))
    yield [sec, "Começo da chave", prefixo or "Nenhuma chave gerada"]


# ---- LEIA-ME e geração ------------------------------------------------------------------------------

def leia_me(conta_nome: str, gerado_em: datetime) -> str:
    linhas = [
        f"Toqqi: todos os dados da conta {conta_nome}",
        f"Gerado em {data_hora(gerado_em)} (horário de Brasília).",
        "",
        "Cada arquivo .csv é uma planilha. Para abrir no Excel: Dados › De Texto/CSV (ou dê dois cliques).",
        "Convenção: separador ponto e vírgula (;), UTF-8 com BOM, datas e horas no horário de Brasília (dd/mm/aaaa",
        "hh:mm), vírgula decimal, \"Sim\"/\"Não\". Textos que começariam com =, +, - ou @ ganham um apóstrofo na",
        "frente (proteção contra fórmulas). As linhas estão em ordem de criação (ID).",
        "",
        "Arquivos:",
        *[f"- {nome}: {descricao}" for nome, _, descricao in ARQUIVOS],
        "",
        "O que não vai: senhas, chaves e segredos (só o começo da chave de integração), os links dos convites, ids de",
        "sistemas de cobrança, IP e navegador dos aceites, imagens (logos e banco de imagens), resumos e pareceres da",
        "IA do painel e dos relatórios e os registros de acesso (guardados à parte, por exigência legal).",
    ]
    return "\n".join(linhas) + "\n"


def _gerar(s: Session, conta: Conta, z: _Zip) -> None:
    c = conta.id
    formularios = s.scalars(select(Formulario).where(Formulario.conta_id == c).order_by(Formulario.id)).all()
    z.texto("LEIA-ME.txt", leia_me(conta.nome, relogio.agora()))
    z.csv("empresas.csv", _empresas(s, c))
    z.csv("responsaveis.csv", _responsaveis(s, c))
    z.csv("cadastros.csv", _cadastros(s, c))
    z.csv("contatos.csv", _contatos(s, c))
    z.csv("formularios.csv", _formularios(formularios))
    z.csv("respostas.csv", _respostas(s, c))
    z.csv("respostas-perguntas.csv", _respostas_perguntas(s, c, formularios, conta.nome))
    z.csv("planos-de-acao.csv", _acoes(s, c))
    z.csv("convites.csv", _convites(s, c))
    z.csv("envios.csv", _envios(s, c))
    z.csv("descadastros.csv", _descadastros(s, c))
    z.csv("cobrancas.csv", _cobrancas(s, c))
    z.csv("indicacoes.csv", _indicacoes(s, c))
    z.csv("ofertas.csv", _ofertas(s, c))
    z.csv("equipe.csv", _equipe(s, c))
    z.csv("aceites-dos-termos.csv", _aceites(s, c))
    z.csv("auditoria.csv", _auditoria(s, c))
    z.csv("emails-enviados.csv", _emails(s, c))
    z.csv("configuracoes.csv", _configuracoes(s, conta))


class ArquivoTemporario(FileResponse):
    """FileResponse que apaga o arquivo depois de enviar (e se o envio falhar)."""

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.remove(self.path)


def gerar(ctx: Contexto) -> tuple[str, str, dict]:
    """Gera o zip num arquivo temporário. Devolve (caminho, nome do arquivo, {arquivos, linhas, bytes})."""
    descritor, caminho = tempfile.mkstemp(prefix="toqqi-exportacao-", suffix=".zip")
    os.close(descritor)
    try:
        with em_conta(ctx.conta_id, leitura=True) as s:
            livre = s.scalar(text("select pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
                             {"k": f"exportacao:{ctx.conta_id}"})
            if not livre:
                raise AppError(409, "exportacao_em_andamento", MSG_EM_ANDAMENTO)
            sem_jit(s)
            conta = s.get(Conta, ctx.conta_id)
            with zipfile.ZipFile(caminho, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                z = _Zip(zf)
                _gerar(s, conta, z)
            nome = nome_zip(conta.nome, relogio.hoje())
        resumo = {"arquivos": len(z.linhas) + 1, "linhas": z.linhas, "bytes": os.path.getsize(caminho)}
        with em_conta(ctx.conta_id) as s:  # a transação da leitura é somente leitura
            registrar(s, "exportacao_conta", "info", resumo, usuario_id=ctx.usuario_id)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.remove(caminho)
        raise
    return caminho, nome, resumo


def resposta(ctx: Contexto) -> ArquivoTemporario:
    caminho, nome, _ = gerar(ctx)
    return ArquivoTemporario(caminho, media_type="application/zip", filename=nome)
