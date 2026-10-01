"""Importação por planilha: analisar → conferir → importar (tudo ou nada). Dois tipos: contatos (aqui) e
respostas antigas (`importacao.respostas`); o tipo é escolhido na análise e guardado com ela."""
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema, travar
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.planos import contatos_ativos, erro_limite, limite_da_conta
from toqqi.core.texto import (
    interpretar_booleano,
    interpretar_data,
    interpretar_valor,
    normalizar_documento,
    normalizar_telefone,
)
from toqqi.modelos import Cargo, Contato, Empresa, Grupo, Importacao, PerfilContato, Responsavel, Segmento
from toqqi.modulos.contatos.servico import novo_codigo
from toqqi.modulos.importacao import planilha
from toqqi.modulos.importacao import respostas as importacao_respostas
from toqqi.modulos.importacao.planilha import CAMPOS, CAMPOS_RESPOSTAS, CHAVES_CAMPOS, ROTULOS

VALIDADE = timedelta(hours=1)
MAX_PROBLEMAS = 500
AMOSTRA = 10
AUXILIARES = {"grupo": Grupo, "segmento": Segmento, "cargo": Cargo, "perfil": PerfilContato,
              "responsavel": Responsavel}
SINGULARES = {"empresa": "empresa", "grupo": "grupo", "segmento": "segmento", "cargo": "cargo",
              "perfil": "perfil", "responsavel": "responsável"}
PLURAIS = {"empresa": "empresas", "grupo": "grupos", "segmento": "segmentos", "cargo": "cargos",
           "perfil": "perfis", "responsavel": "responsáveis"}
LIMITES_TEXTO = {"nome": 120, "empresa": 200, "cargo": 80, "perfil": 80, "grupo": 80, "segmento": 80,
                 "responsavel": 120, "codigo_externo": 100}


# modelo de respostas antigas: cabeçalho + uma linha de exemplo
MODELO_RESPOSTAS = ("email;empresa;data;nota;comentario\r\n"
                    "maria@cliente.com.br;Mercado Bom Preço;15/03/2025;9;Entrega sempre no prazo\r\n")


def _campos_json(tipo: str = "contatos") -> list[dict]:
    campos = CAMPOS_RESPOSTAS if tipo == "respostas" else CAMPOS
    return [{"chave": c, "rotulo": r, "obrigatorio": o} for c, r, o in campos]


def modelo_csv(tipo: str = "contatos") -> bytes:
    if tipo == "respostas":
        return ("﻿" + MODELO_RESPOSTAS).encode("utf-8")
    return ("﻿" + ";".join(CHAVES_CAMPOS) + "\r\n").encode("utf-8")


# ---- analisar ---------------------------------------------------------------

def analisar(ctx: Contexto, nome_arquivo: str, conteudo: bytes, tipo: str = "contatos") -> dict:
    colunas, linhas = planilha.ler(nome_arquivo or "", conteudo)
    with modo_sistema() as s:  # limpeza global das análises vencidas (de qualquer conta)
        s.execute(delete(Importacao).where(Importacao.expira_em < func.now()))
    with em_conta(ctx.conta_id) as s:
        imp = Importacao(conta_id=ctx.conta_id, usuario_id=ctx.usuario_id, arquivo_nome=(nome_arquivo or "")[:200],
                         dados=linhas, colunas=colunas, expira_em=s.scalar(select(func.now())) + VALIDADE, tipo=tipo)
        s.add(imp)
        s.flush()
        imp_id = imp.id
    return {
        "id": str(imp_id),
        "tipo": tipo,
        "colunas": colunas,
        "mapeamento_sugerido": planilha.sugerir_mapeamento(colunas, tipo),
        "total_linhas": len(linhas),
        "amostra": [{"linha": ln[0], "valores": dict(zip(colunas, ln[1:]))} for ln in linhas[:AMOSTRA]],
        "campos": _campos_json(tipo),
    }


def _importacao(s: Session, imp_id: uuid.UUID, travar: bool = False) -> Importacao:
    imp = s.get(Importacao, imp_id, with_for_update=travar)
    if imp is None or imp.expira_em <= s.scalar(select(func.now())):
        raise AppError(404, "nao_encontrado", "Esta análise expirou ou não existe. Envie a planilha de novo.")
    return imp


# ---- plano da importação ----------------------------------------------------

@dataclass
class Linha:
    numero: int
    valores: dict
    chave: str | None
    existente_id: int | None = None


@dataclass
class Plano:
    prontas: list[Linha] = field(default_factory=list)
    problemas: list[dict] = field(default_factory=list)
    novos: list[Linha] = field(default_factory=list)
    atualizar: list[Linha] = field(default_factory=list)
    mantidos: list[Linha] = field(default_factory=list)
    criar: dict[str, list[str]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    ativos_depois: int = 0
    limite: int | None = None


def _validar_mapeamento(colunas: list[str], mapeamento: dict[str, str | None], chave: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    por_campo: dict[str, str] = {}
    for coluna, campo in mapeamento.items():
        if not campo:
            continue
        if coluna not in colunas:
            campos[f"mapeamento.{coluna}"] = "Esta coluna não existe na planilha."
        elif campo not in CHAVES_CAMPOS:
            campos[f"mapeamento.{coluna}"] = "Campo desconhecido."
        elif campo in por_campo:
            campos[f"mapeamento.{coluna}"] = f"O campo {ROTULOS[campo]} já está ligado à coluna {por_campo[campo]}."
        else:
            por_campo[campo] = coluna
    if "nome" not in por_campo:
        campos["mapeamento"] = "Escolha a coluna com o nome do contato."
    elif "email" not in por_campo and "telefone" not in por_campo:
        campos["mapeamento"] = "Escolha a coluna de e-mail ou a de telefone."
    elif chave not in por_campo:
        campos["chave"] = f"Escolha a coluna de {ROTULOS[chave]}, usada para achar contatos já cadastrados."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira o mapeamento das colunas.", campos)
    return por_campo


def _ler_linha(bruta: dict) -> tuple[dict, list[str]]:
    """Converte os valores de uma linha. Devolve (valores, motivos de problema)."""
    motivos: list[str] = []
    v: dict = {}
    for campo, limite in LIMITES_TEXTO.items():
        t = (bruta.get(campo) or "").strip()
        if len(t) > limite:
            motivos.append(f"{ROTULOS[campo]} passa de {limite} caracteres.")
        v[campo] = t or None
    if not v["nome"]:
        motivos.append("Nome em branco.")
    email = (bruta.get("email") or "").strip().lower()
    v["email"] = None
    if email:
        try:
            validate_email(email, check_deliverability=False)
            v["email"] = email
        except EmailNotValidError:
            motivos.append("E-mail inválido.")
    tel = (bruta.get("telefone") or "").strip()
    v["telefone"] = None
    if tel:
        try:
            v["telefone"] = normalizar_telefone(tel)
        except ValueError:
            motivos.append("Telefone inválido.")
    if not email and not tel:
        motivos.append("Sem e-mail e sem telefone.")
    for campo, funcao, msg in (
        ("documento_empresa", normalizar_documento, "CNPJ/CPF inválido."),
        ("valor_mensal", interpretar_valor, "Valor mensal inválido."),
        ("cliente_desde", interpretar_data, "Data inválida em cliente desde (use dd/mm/aaaa)."),
    ):
        try:
            v[campo] = funcao(bruta.get(campo) or "")
        except ValueError:
            v[campo] = None
            motivos.append(msg)
    try:
        # vazio = não informado: contato novo entra ativo, existente mantém como está
        v["ativo"] = interpretar_booleano(bruta.get("ativo"), padrao=None)
    except ValueError:
        v["ativo"] = None
        motivos.append("Valor inválido em ativo (use sim ou não).")
    return v, motivos


def _planejar(s: Session, imp: Importacao, corpo) -> Plano:
    por_campo = _validar_mapeamento(imp.colunas, corpo.mapeamento, corpo.chave)
    if corpo.grupo_id is not None and s.get(Grupo, corpo.grupo_id) is None:
        raise AppError(422, "dados_invalidos", "Grupo não encontrado.", {"grupo_id": "Grupo não encontrado."})
    indice = {c: i for i, c in enumerate(imp.colunas)}

    existentes = s.execute(select(Contato.id, Contato.email, Contato.telefone, Contato.codigo_externo,
                                  Contato.ativo).order_by(Contato.id)).all()
    por_chave: dict[str, tuple] = {}
    por_email: dict[str, int] = {}
    for c in existentes:
        k = {"email": c.email.lower() if c.email else None, "telefone": c.telefone,
             "codigo_externo": c.codigo_externo}[corpo.chave]
        if k:
            por_chave.setdefault(k, c)
        if c.email:
            por_email[c.email.lower()] = c.id

    plano = Plano()
    vistos_chave: dict[str, int] = {}
    vistos_email: dict[str, int] = {}
    ativos_ativando = 0
    ativos_desativando = 0
    for ln in imp.dados:
        numero, celulas = ln[0], ln[1:]
        bruta = {campo: celulas[indice[col]] for campo, col in por_campo.items()}
        valores, motivos = _ler_linha(bruta)
        chave = valores.get(corpo.chave)
        chave = chave.lower() if chave and corpo.chave == "email" else chave
        if chave:
            if chave in vistos_chave:
                motivos.append(f"Contato repetido na planilha ({ROTULOS[corpo.chave]} igual ao da linha "
                               f"{vistos_chave[chave]}).")
            else:
                vistos_chave[chave] = numero
        existente = por_chave.get(chave) if chave else None
        email = valores.get("email")
        if email:
            if email in vistos_email and corpo.chave != "email":
                motivos.append(f"E-mail repetido na planilha (linha {vistos_email[email]}).")
            vistos_email.setdefault(email, numero)
            dono = por_email.get(email)
            if dono is not None and (existente is None or dono != existente.id):
                motivos.append("Este e-mail já pertence a outro contato cadastrado.")
        if motivos:
            if len(plano.problemas) < MAX_PROBLEMAS:
                plano.problemas.append({"linha": numero, "motivo": " ".join(motivos)})
            else:
                plano.problemas.append(None)  # só conta
            continue
        linha = Linha(numero, valores, chave, existente.id if existente else None)
        plano.prontas.append(linha)
        ativo_novo = valores["ativo"]
        if existente is None:
            plano.novos.append(linha)
            if ativo_novo is not False:
                ativos_ativando += 1
        elif corpo.atualizar_existentes:
            plano.atualizar.append(linha)
            if ativo_novo is True and not existente.ativo:
                ativos_ativando += 1
            elif ativo_novo is False and existente.ativo:
                ativos_desativando += 1
        else:
            plano.mantidos.append(linha)

    # cadastros auxiliares e empresas que serão criados
    usados = plano.novos + plano.atualizar
    for campo, modelo in {**AUXILIARES, "empresa": Empresa}.items():
        nomes = {}
        for linha in usados:
            n = linha.valores.get(campo)
            if n:
                nomes.setdefault(n.lower(), n)
        if not nomes:
            continue
        ja = {x.lower() for x in s.scalars(select(modelo.nome).where(func.lower(modelo.nome).in_(list(nomes))))}
        faltam = [nomes[k] for k in nomes if k not in ja]
        if faltam:
            plano.criar[campo] = faltam

    plano.limite = limite_da_conta(s, imp.conta_id)
    plano.ativos_depois = contatos_ativos(s) + ativos_ativando - ativos_desativando

    if plano.mantidos:
        n = len(plano.mantidos)
        quem = "1 contato já cadastrado será mantido como está" if n == 1 else \
            f"{n} contatos já cadastrados serão mantidos como estão"
        plano.avisos.append(f"{quem} (ligue \"Atualizar quem já existe\" para trocar os dados).")
    for campo, nomes in plano.criar.items():
        amostra = ", ".join(nomes[:5]) + ("..." if len(nomes) > 5 else "")
        if len(nomes) == 1:
            genero = "Será criada 1" if campo == "empresa" else "Será criado 1"
            plano.avisos.append(f"{genero} {SINGULARES[campo]}: {amostra}.")
        else:
            plano.avisos.append(f"Serão criados {len(nomes)} {PLURAIS[campo]}: {amostra}.")
    if plano.limite is not None and plano.ativos_depois > plano.limite:
        plano.avisos.append(f"Esta importação deixaria a conta com {plano.ativos_depois} contatos ativos, "
                            f"mas o seu plano permite até {plano.limite}.")
    return plano


def _resumo(plano: Plano) -> dict:
    return {
        "prontas": len(plano.prontas),
        "com_problema": len(plano.problemas),
        "novos": len(plano.novos),
        "atualizados": len(plano.atualizar),
        "problemas": [p for p in plano.problemas if p is not None],
        "avisos": plano.avisos,
    }


def conferir(ctx: Contexto, imp_id: uuid.UUID, corpo) -> dict:
    with em_conta(ctx.conta_id) as s:
        imp = _importacao(s, imp_id)
        if imp.tipo == "respostas":  # chave e grupo_id não se aplicam
            return importacao_respostas.resumo(importacao_respostas.planejar(s, imp, corpo))
        return _resumo(_planejar(s, imp, corpo))


# ---- importar ---------------------------------------------------------------

def _mapa_nomes(s: Session, modelo) -> dict[str, int]:
    return {n.lower(): i for i, n in s.execute(select(modelo.id, modelo.nome))}


def importar(ctx: Contexto, imp_id: uuid.UUID, corpo) -> dict:
    with em_conta(ctx.conta_id) as s:
        # uma importação por vez em cada conta: duas ao mesmo tempo (ex.: a mesma planilha enviada duas vezes)
        # planejariam sobre o mesmo estado e gravariam as mesmas linhas duas vezes
        travar(s, f"importacao:{ctx.conta_id}")
        imp = _importacao(s, imp_id, travar=True)
        if imp.tipo == "respostas":
            return importacao_respostas.importar(s, ctx, imp, corpo)
        plano = _planejar(s, imp, corpo)
        if plano.problemas and not corpo.ignorar_com_problema:
            n = len(plano.problemas)
            raise AppError(422, "importacao_com_problema",
                           f"{n} linha(s) com problema. Corrija a planilha ou escolha ignorar essas linhas.")
        if plano.limite is not None and plano.ativos_depois > plano.limite:
            raise erro_limite(plano.limite)

        usados = plano.novos + plano.atualizar
        ids: dict[str, dict[str, int]] = {}
        criados: dict[str, int] = {}
        for campo, modelo in AUXILIARES.items():
            mapa = _mapa_nomes(s, modelo)
            novos = 0
            for linha in usados:
                n = linha.valores.get(campo)
                if n and n.lower() not in mapa:
                    obj = modelo(nome=n)
                    s.add(obj)
                    s.flush()
                    mapa[n.lower()] = obj.id
                    novos += 1
            ids[campo] = mapa
            if novos:
                criados[PLURAIS[campo]] = novos

        # Empresas: cada dado vem da primeira linha da planilha que o informa. Empresa que já existia
        # só muda com "atualizar existentes".
        empresas = {e.nome.lower(): e for e in s.scalars(select(Empresa))}
        definidos: dict[str, set] = {}
        empresas_novas = 0
        for linha in usados:
            v = linha.valores
            if not v.get("empresa"):
                continue
            chave = v["empresa"].lower()
            e = empresas.get(chave)
            if e is None:
                e = Empresa(nome=v["empresa"])
                s.add(e)
                empresas[chave] = e
                definidos[chave] = set()
                empresas_novas += 1
            elif corpo.atualizar_existentes:
                definidos.setdefault(chave, set())
            if chave not in definidos:
                continue
            for campo_emp, valor in (
                ("documento", v.get("documento_empresa")),
                ("grupo_id", ids["grupo"].get((v.get("grupo") or "").lower())),
                ("segmento_id", ids["segmento"].get((v.get("segmento") or "").lower())),
                ("responsavel_id", ids["responsavel"].get((v.get("responsavel") or "").lower())),
                ("valor_mensal", v.get("valor_mensal")),
                ("cliente_desde", v.get("cliente_desde")),
            ):
                if valor is not None and campo_emp not in definidos[chave]:
                    setattr(e, campo_emp, valor)
                    definidos[chave].add(campo_emp)
            if corpo.grupo_id and e.grupo_id is None:
                e.grupo_id = corpo.grupo_id
        s.flush()
        if empresas_novas:
            criados["empresas"] = empresas_novas

        def referencias(v: dict) -> dict:
            r = {}
            if v.get("empresa"):
                r["empresa_id"] = empresas[v["empresa"].lower()].id
            for campo in ("cargo", "perfil"):
                if v.get(campo):
                    r[f"{campo}_id"] = ids[campo][v[campo].lower()]
            return r

        # atualizações: desativações primeiro, para o limite do plano contar certo
        mudancas = []
        for linha in plano.atualizar:
            v = linha.valores
            m = {"id": linha.existente_id, "nome": v["nome"], **referencias(v)}
            for campo in ("email", "telefone", "codigo_externo"):
                if v.get(campo):
                    m[campo] = v[campo]
            if v["ativo"] is not None:
                m["ativo"] = v["ativo"]
            mudancas.append(m)
        mudancas.sort(key=lambda m: 0 if m.get("ativo") is False else 1)
        for m in mudancas:
            s.execute(update(Contato).where(Contato.id == m.pop("id")).values(**m))

        if plano.novos:
            usados_cod = set(s.scalars(select(Contato.codigo)))
            s.execute(insert(Contato), [
                {"conta_id": ctx.conta_id, "codigo": novo_codigo(usados_cod), "nome": v["nome"],
                 "email": v["email"], "telefone": v["telefone"], "codigo_externo": v["codigo_externo"],
                 "ativo": v["ativo"] is not False, "empresa_id": None, "cargo_id": None, "perfil_id": None,
                 **referencias(v)}
                for v in (linha.valores for linha in plano.novos)
            ])

        ignorados = len(plano.problemas) + len(plano.mantidos)
        registrar(s, "importacao", "sucesso", {
            "arquivo": imp.arquivo_nome, "novos": len(plano.novos), "atualizados": len(plano.atualizar),
            "ignorados": ignorados, "com_problema": len(plano.problemas), "criados": criados,
        }, usuario_id=ctx.usuario_id)
        s.delete(imp)
        return {"novos": len(plano.novos), "atualizados": len(plano.atualizar), "ignorados": ignorados,
                "problemas": [p for p in plano.problemas if p is not None]}
