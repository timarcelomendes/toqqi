"""Importação de respostas antigas (histórico): mesmo fluxo da de contatos (analisar → conferir → importar).

Cada linha precisa do e-mail de um contato já cadastrado, da data (dd/mm/aaaa ou aaaa-mm-dd, de 2000 até hoje) e da
nota inteira de 0 a 10 ("9,0" vale 9; "8,7" é recusada). Empresa diferente da do contato só gera aviso (vale a do
contato). Já existe resposta importada do mesmo contato na mesma data → atualiza (com "atualizar quem já existe")
ou mantém. Tudo ou nada, em lote: origem e canal `importacao`, formulário padrão de NPS, grupo pela nota, temas,
`respondida_em` = data às 12:00. Não cria ação, alerta, agradecimento nem webhook e não mexe na fila de envios.
Etapa 5h: com a IA ativa na conta, as importadas agora dos últimos 90 dias com comentário vão para a fila da IA
(`ia.servico.marcar_importadas`, com o saldo do teto); a resposta traz `ia_marcadas` e a rota agenda a análise.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import Date, cast, func, select, text, update
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.relogio import FUSO_NOME
from toqqi.core.texto import interpretar_data
from toqqi.modelos import Conta, Contato, Empresa, Formulario, Importacao, Resposta
from toqqi.modulos.formularios.validacao import grupo_da_nota, pergunta_principal
from toqqi.modulos.ia.regras import ia_ativa, texto_qualifica
from toqqi.modulos.ia.servico import marcar_importadas
from toqqi.modulos.importacao.planilha import (
    CHAVES_RESPOSTAS,
    OBRIGATORIOS_RESPOSTAS,
    ROTULOS_RESPOSTAS,
)
from toqqi.modulos.respostas.registro import temas_da_resposta
from toqqi.modulos.respostas.servico import data_informada

MAX_PROBLEMAS = 500
MAX_COMENTARIO = 4000
MAX_LINHAS_AVISO = 10
MSG_NOTA = "A nota precisa ser um número inteiro de 0 a 10."
MSG_CONTATO = "Contato não encontrado: cadastre ou importe os contatos antes."
MSG_REPETIDA = "Linha repetida (mesmo contato e data)."
ROTULO_ATUALIZAR = "Atualizar as que já existem"  # o mesmo texto da opção na tela de importação de respostas


def interpretar_nota(v) -> int:
    """ "9", "9,0", "9.0" → 9. Decimal ("8,7"), fora de 0–10 ou não numérica → ValueError."""
    t = str(v).strip().replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise ValueError(MSG_NOTA)
    if not d.is_finite() or d != d.to_integral_value() or not 0 <= d <= 10:
        raise ValueError(MSG_NOTA)
    return int(d)


@dataclass
class LinhaResposta:
    numero: int
    contato_id: int
    empresa_id: int | None
    data: date
    nota: int
    comentario: str | None  # None = não informado
    existente_id: int | None = None


@dataclass
class Plano:
    prontas: list[LinhaResposta] = field(default_factory=list)
    problemas: list[dict | None] = field(default_factory=list)
    novos: list[LinhaResposta] = field(default_factory=list)
    atualizar: list[LinhaResposta] = field(default_factory=list)
    mantidos: list[LinhaResposta] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _validar_mapeamento(colunas: list[str], mapeamento: dict[str, str | None]) -> dict[str, str]:
    campos: dict[str, str] = {}
    por_campo: dict[str, str] = {}
    for coluna, campo in mapeamento.items():
        if not campo:
            continue
        if coluna not in colunas:
            campos[f"mapeamento.{coluna}"] = "Esta coluna não existe na planilha."
        elif campo not in CHAVES_RESPOSTAS:
            campos[f"mapeamento.{coluna}"] = "Campo desconhecido."
        elif campo in por_campo:
            campos[f"mapeamento.{coluna}"] = (f"O campo {ROTULOS_RESPOSTAS[campo]} já está ligado à coluna "
                                              f"{por_campo[campo]}.")
        else:
            por_campo[campo] = coluna
    faltam = [ROTULOS_RESPOSTAS[c] for c in OBRIGATORIOS_RESPOSTAS if c not in por_campo]
    if faltam and not campos:
        campos["mapeamento"] = "Escolha as colunas obrigatórias: " + ", ".join(faltam) + "."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira o mapeamento das colunas.", campos)
    return por_campo


def _ler_linha(bruta: dict, hoje: date, contatos: dict) -> tuple[dict, list[str]]:
    motivos: list[str] = []
    v: dict = {"email": None, "data": None, "nota": None}
    email = (bruta.get("email") or "").strip().lower()
    if not email:
        motivos.append("E-mail em branco.")
    elif email in contatos:  # e-mail de contato cadastrado já foi validado
        v["email"] = email
    else:
        try:
            validate_email(email, check_deliverability=False)
            v["email"] = email
        except EmailNotValidError:
            motivos.append("E-mail inválido.")
    try:
        v["data"] = interpretar_data(bruta.get("data") or "")
        if v["data"] is None:
            motivos.append("Data em branco.")
        elif v["data"] > hoje:
            motivos.append("A data não pode ser no futuro.")
        elif v["data"].year < 2000:  # mesmo limite dos filtros de período; pega ano digitado errado
            motivos.append("Data antes de 2000: confira o ano.")
    except ValueError as e:
        motivos.append(str(e))
    nota = (bruta.get("nota") or "").strip()
    if not nota:
        motivos.append("Nota em branco.")
    else:
        try:
            v["nota"] = interpretar_nota(nota)
        except ValueError as e:
            motivos.append(str(e))
    # vazio (ou coluna não ligada) = não informado: ao atualizar, o comentário (e os temas) ficam como estão
    v["comentario"] = (bruta.get("comentario") or "").strip() or None
    if v["comentario"] and len(v["comentario"]) > MAX_COMENTARIO:
        motivos.append(f"O comentário passa de {MAX_COMENTARIO} caracteres.")
    v["empresa"] = (bruta.get("empresa") or "").strip() or None
    return v, motivos


def _linhas_texto(numeros: list[int]) -> str:
    """ "linha 7", "linhas 7, 9 e 12"; mais de 10: as 10 primeiras e "e mais 4"."""
    textos = [str(n) for n in numeros]
    if len(textos) == 1:
        return f"linha {textos[0]}"
    if len(textos) > MAX_LINHAS_AVISO:
        return f"linhas {', '.join(textos[:MAX_LINHAS_AVISO])} e mais {len(textos) - MAX_LINHAS_AVISO}"
    return f"linhas {', '.join(textos[:-1])} e {textos[-1]}"


def planejar(s: Session, imp: Importacao, corpo) -> Plano:
    por_campo = _validar_mapeamento(imp.colunas, corpo.mapeamento)
    indice = {c: i for i, c in enumerate(imp.colunas)}
    hoje = relogio.hoje()
    contatos = {email.lower(): (cid, empresa_id, empresa) for cid, email, empresa_id, empresa in s.execute(
        select(Contato.id, Contato.email, Contato.empresa_id, Empresa.nome)
        .outerjoin(Empresa, Empresa.id == Contato.empresa_id).where(Contato.email.is_not(None)))}
    dia = cast(func.timezone(FUSO_NOME, Resposta.data_resposta), Date)
    importadas: dict[tuple[int, date], int] = {}
    for rid, contato_id, d in s.execute(select(Resposta.id, Resposta.contato_id, dia)
                                        .where(Resposta.origem == "importacao", Resposta.contato_id.is_not(None))
                                        .order_by(Resposta.id)):
        importadas.setdefault((contato_id, d), rid)

    plano = Plano()
    vistas: set[tuple[int, date]] = set()
    empresa_diferente: list[int] = []
    for ln in imp.dados:
        numero, celulas = ln[0], ln[1:]
        bruta = {campo: celulas[indice[col]] for campo, col in por_campo.items()}
        v, motivos = _ler_linha(bruta, hoje, contatos)
        contato = contatos.get(v["email"]) if v["email"] else None
        if v["email"] and contato is None:
            motivos.append(MSG_CONTATO)
        if contato is not None and v["data"] is not None:
            chave = (contato[0], v["data"])
            if chave in vistas:
                motivos.append(MSG_REPETIDA)
            vistas.add(chave)
        if motivos:
            plano.problemas.append({"linha": numero, "motivo": " ".join(motivos)}
                                   if len(plano.problemas) < MAX_PROBLEMAS else None)
            continue
        contato_id, empresa_id, empresa_nome = contato
        if v["empresa"] and v["empresa"].casefold() != (empresa_nome or "").casefold():
            empresa_diferente.append(numero)
        linha = LinhaResposta(numero, contato_id, empresa_id, v["data"], v["nota"], v["comentario"],
                              importadas.get((contato_id, v["data"])))
        plano.prontas.append(linha)
        if linha.existente_id is None:
            plano.novos.append(linha)
        elif corpo.atualizar_existentes:
            plano.atualizar.append(linha)
        else:
            plano.mantidos.append(linha)

    if empresa_diferente:
        n = len(empresa_diferente)
        quais = f"{n} linha" if n == 1 else f"{n} linhas"
        plano.avisos.append(f"Em {quais} a empresa da planilha é diferente da empresa do contato; vale a empresa "
                            f"do contato ({_linhas_texto(empresa_diferente)}).")
    if plano.mantidos:
        n = len(plano.mantidos)
        quem = "1 resposta já importada será mantida como está" if n == 1 else \
            f"{n} respostas já importadas serão mantidas como estão"
        plano.avisos.append(f"{quem} (ligue \"{ROTULO_ATUALIZAR}\" para trocar a nota e o comentário).")
    return plano


def resumo(plano: Plano) -> dict:
    return {
        "prontas": len(plano.prontas),
        "com_problema": len(plano.problemas),
        "novos": len(plano.novos),
        "atualizados": len(plano.atualizar),
        "problemas": [p for p in plano.problemas if p is not None],
        "avisos": plano.avisos,
    }


def _inserir(s: Session, conta_id: int, formulario_id: int, pergunta_id: str,
             linhas: list[LinhaResposta]) -> list[int]:
    """Um INSERT só para todas as linhas: um vetor por coluna, desfeito com unnest (COPY não funciona em tabela com
    RLS, e montar milhares de VALUES custa caro). Devolve os ids das respostas criadas."""
    return s.execute(text("""
        INSERT INTO respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, respostas, contexto, temas, respondida_em)
        SELECT CAST(:conta AS bigint), CAST(:formulario AS bigint), x.contato_id, x.empresa_id, 'importacao',
               'importacao', x.nota, 'nps', x.grupo, x.comentario, x.comentario,
               jsonb_build_object(CAST(:pergunta AS text), x.nota), '{}'::jsonb, string_to_array(x.temas, ','),
               x.respondida_em
          FROM unnest(CAST(:contatos AS bigint[]), CAST(:empresas AS bigint[]), CAST(:notas AS smallint[]),
                      CAST(:grupos AS text[]), CAST(:comentarios AS text[]), CAST(:temas AS text[]),
                      CAST(:datas AS timestamptz[]))
               AS x(contato_id, empresa_id, nota, grupo, comentario, temas, respondida_em)
        RETURNING id
    """), {
        "conta": conta_id, "formulario": formulario_id, "pergunta": pergunta_id,
        "contatos": [x.contato_id for x in linhas], "empresas": [x.empresa_id for x in linhas],
        "notas": [x.nota for x in linhas], "grupos": [grupo_da_nota("nps", x.nota) for x in linhas],
        "comentarios": [x.comentario or "" for x in linhas],
        "temas": [",".join(temas_da_resposta(x.comentario)) for x in linhas],
        "datas": [data_informada(x.data) for x in linhas],
    }).scalars().all()


def _atualizar(s: Session, linhas: list[LinhaResposta], pergunta_id: str, ia_ligada: bool) -> None:
    """Respostas importadas que já existiam: a nota muda (e o grupo e a nota guardada nas respostas); o comentário
    só muda se a planilha trouxer um diferente (ao atualizar, só campos preenchidos mudam), e com ele os temas, salvo
    `temas_manuais`, e a análise da IA, que descrevia o texto antigo. Como na edição do comentário: a resposta que já
    tinha passado pela IA (pelo "analisar os últimos 90 dias") volta para pendente, com as tentativas zeradas, se a
    IA da conta está ativa e o texto novo tem 3+ letras; senão a análise é apagada (situação nula)."""
    atuais = {r.id: r for r in s.execute(
        select(Resposta.id, Resposta.respostas, Resposta.temas_manuais, Resposta.o_que_faltou,
               Resposta.comentario_cliente, Resposta.ia_situacao)
        .where(Resposta.id.in_([x.existente_id for x in linhas])))}
    lotes: dict[tuple, list[dict]] = {}
    for x in linhas:
        atual = atuais[x.existente_id]
        mudanca = {"id": x.existente_id, "nota": x.nota, "grupo": grupo_da_nota("nps", x.nota),
                   "respostas": {k: x.nota for k in (atual.respostas or {})} or {pergunta_id: x.nota}}
        if x.comentario is not None and x.comentario != (atual.comentario_cliente or ""):
            mudanca.update(comentario=x.comentario, comentario_cliente=x.comentario)
            if not atual.temas_manuais:
                mudanca["temas"] = temas_da_resposta(x.comentario, atual.o_que_faltou)
            if atual.ia_situacao is not None:
                pendente = ia_ligada and texto_qualifica(x.comentario)
                mudanca.update(ia_situacao="pendente" if pendente else None, ia_tentativas=0, ia_temas=None,
                               ia_sentimento=None, ia_resumo=None, ia_modelo=None, ia_em=None)
        lotes.setdefault(tuple(sorted(mudanca)), []).append(mudanca)
    for lote in lotes.values():  # cada UPDATE em lote leva os mesmos campos em todas as linhas
        s.execute(update(Resposta), lote)


def importar(s: Session, ctx: Contexto, imp: Importacao, corpo) -> dict:
    plano = planejar(s, imp, corpo)
    if plano.problemas and not corpo.ignorar_com_problema:
        n = len(plano.problemas)
        raise AppError(422, "importacao_com_problema",
                       f"{n} linha(s) com problema. Corrija a planilha ou escolha ignorar essas linhas.")
    f = s.scalar(select(Formulario).where(Formulario.padrao_nps.is_(True)))
    principal = pergunta_principal(f.perguntas) if f else None
    if principal is None or principal["tipo"] != "nps":
        raise AppError(409, "sem_formulario_nps",
                       "Escolha um formulário padrão de NPS em Formulários antes de importar respostas.")
    novos_ids = _inserir(s, ctx.conta_id, f.id, principal["id"], plano.novos) if plano.novos else []
    if plano.atualizar:
        _atualizar(s, plano.atualizar, principal["id"], ia_ativa(s.get(Conta, ctx.conta_id)))
    contatos = sorted({x.contato_id for x in plano.novos + plano.atualizar})
    if contatos:  # última nota = a da resposta mais recente de cada contato
        s.execute(text("""
            UPDATE contatos c SET ultima_nota = x.nota
              FROM (SELECT DISTINCT ON (contato_id) contato_id, nota FROM respostas
                     WHERE conta_id = :conta AND contato_id = ANY(:ids) AND NOT arquivada AND nota IS NOT NULL
                     ORDER BY contato_id, data_resposta DESC, id DESC) x
             WHERE c.conta_id = :conta AND c.id = x.contato_id
        """), {"conta": ctx.conta_id, "ids": contatos})
    # etapa 5h: as importadas agora dos últimos 90 dias com comentário vão para a fila da IA (se ativa na conta); quem
    # chama agenda `ia.servico.processar_conta` depois do commit
    ia_marcadas = marcar_importadas(s, ctx.conta_id, [*novos_ids, *(x.existente_id for x in plano.atualizar)])
    ignorados = len(plano.problemas) + len(plano.mantidos)
    registrar(s, "importacao_respostas", "sucesso", {
        "arquivo": imp.arquivo_nome, "novos": len(plano.novos), "atualizados": len(plano.atualizar),
        "ignorados": ignorados, "com_problema": len(plano.problemas),
    }, usuario_id=ctx.usuario_id)
    s.delete(imp)
    return {"novos": len(plano.novos), "atualizados": len(plano.atualizar), "ignorados": ignorados,
            "problemas": [p for p in plano.problemas if p is not None], "ia_marcadas": ia_marcadas}
