"""Validação das respostas de um formulário, variáveis nos textos e gravação da resposta.

Etapa 5l: as respostas passam pela lógica do formulário (`formularios/logica.py`): só valem as do caminho (as de fora
são descartadas), a obrigatória só é cobrada no caminho e o final sai de `escolher_final` (`tela_final`).

O cliente pode mudar a resposta (docs/api-editar-resposta.md): com `formularios.permite_editar`, até 7 dias depois de
responder (`PRAZO_EDICAO`, contado de `criada_em`), `editar_resposta` troca os valores na mesma linha."""
import copy
import re
from datetime import date, datetime, timedelta
from typing import Any

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toqqi.core.errors import AppError
from toqqi.core.html_seguro import proteger_citacoes, renderizar_html
from toqqi.core.texto import so_digitos
from toqqi.modelos import Contato, Formulario, Resposta
from toqqi.modulos.formularios.logica import caminho, escolher_final, respondivel, sem_citacoes
from toqqi.modulos.formularios.validacao import (
    LIMITE_TEXTO,
    TIPOS_NOTA,
    faixa,
    grupo_da_nota,
    pergunta_principal,
    tipo_nota_de,
)
from toqqi.modulos.imagens.servico import prefixo_publico
from toqqi.modulos.respostas.eventos import ao_editar_resposta, ao_registrar_resposta
from toqqi.modulos.respostas.temas import detectar

ASSUNTO_PADRAO = "o nosso atendimento"
MAX_RESUMO = 2000
ORIGENS = ("pesquisa", "manual", "importacao")
SEPARADOR_COMENTARIOS = " · "  # entre duas perguntas de comentário da mesma resposta
TIPOS_ESCOLHA = ("escolha_unica", "escolha_multipla")


# ---- variáveis --------------------------------------------------------------

def variaveis(empresa: str, nome_contato: str | None = None, assunto: str | None = None,
              referencia: str | None = None) -> dict:
    primeiro = (nome_contato or "").strip().split(" ")[0] if nome_contato else ""
    return {"empresa": empresa or "", "nome": primeiro, "assunto": assunto or ASSUNTO_PADRAO,
            "referencia": referencia or ""}


def renderizar(texto: str | None, v: dict) -> str | None:
    """Troca as variáveis de `v` (ex.: {empresa} {nome} {assunto} {referencia}). Variável vazia some junto
    com o espaço antes; {nome} vazio também leva a vírgula: "Olá, {nome}!" → "Olá!". As citações `{{ID}}` (etapa 5l)
    ficam como estão: quem troca é o navegador, com as respostas que tem."""
    if not texto or "{" not in texto:
        return texto
    texto, restaurar = proteger_citacoes(texto, v.values())
    for chave in v:
        marca = "{" + chave + "}"
        if marca not in texto:
            continue
        valor = v.get(chave) or ""
        if valor:
            texto = texto.replace(marca, valor)
            continue
        if chave == "nome":
            texto = re.sub(r",[ \t]*\{nome\}", "", texto)
            inicio = texto.startswith(marca)
            texto = re.sub(r"^\{nome\}\s*[,!]?\s*", "", texto)
            if inicio and texto:
                texto = texto[0].upper() + texto[1:]
        texto = re.sub(r"[ \t]*" + re.escape(marca), "", texto)
    return restaurar(re.sub(r"[ \t]{2,}", " ", texto).strip())


def formulario_publico(f: Formulario, v: dict) -> dict:
    """O formulário da página pública (etapa 5l, §4.3): com a lógica; títulos e descrições com as variáveis (as
    citações `{{ID}}` ficam para o navegador); blocos de conteúdo com o HTML e as variáveis escapadas (o nome interno
    do bloco não vai); `prefixo_imagens` (o DOMPurify do site só aceita imagens da plataforma) e `tem_finais`. Os
    finais não vão: quem escolhe é a API, ao receber a resposta."""
    perguntas = copy.deepcopy(f.perguntas)
    for p in perguntas:
        if p.get("tipo") == "conteudo":
            p["titulo"] = ""
            p["html"] = renderizar_html(p.get("html") or "", v)
            continue
        p["titulo"] = renderizar(p.get("titulo"), v)
        p["descricao"] = renderizar(p.get("descricao"), v)
    tema = {k: renderizar(x, v) if isinstance(x, str) else x for k, x in (f.tema or {}).items()}
    return {"nome": f.nome, "perguntas": perguntas, "tema": tema, "prefixo_imagens": prefixo_publico(),
            "tem_finais": bool(f.finais)}


def texto_final(f: Formulario, v: dict) -> dict:
    """O final padrão (o do tema)."""
    tema = f.tema or {}
    return {"titulo_final": renderizar(tema.get("titulo_final") or "Obrigado!", v),
            "texto_final": renderizar(tema.get("texto_final") or "", v)}


def tela_final(f: Formulario, v: dict, respostas: dict) -> dict:
    """{titulo_final, texto_final, final_id, html_final, botao_final} (§4.3): o 1º final da lista cuja condição vale
    com as respostas do caminho. No final escolhido, `titulo_final` é o título dele (as citações ficam para o
    navegador), `texto_final` é "" e `html_final` é o HTML dele com as variáveis escapadas ("" se não tiver). Nenhum
    final vale: o padrão do tema, com `final_id`, `html_final` e `botao_final` nulos."""
    final_id = escolher_final(f.finais, f.perguntas, respostas)
    final = next((x for x in f.finais or [] if x.get("id") == final_id), None) if final_id else None
    if final is None:
        return {**texto_final(f, v), "final_id": None, "html_final": None, "botao_final": None}
    botao = final.get("botao")
    return {"titulo_final": renderizar(final.get("titulo") or "", v), "texto_final": "", "final_id": final_id,
            "html_final": renderizar_html(final.get("html") or "", v),
            "botao_final": {"texto": renderizar(botao.get("texto") or "", v), "url": botao.get("url")}
            if botao else None}


# ---- validação --------------------------------------------------------------

def _vazio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def _valor(p: dict, v: Any) -> Any:
    tipo = p["tipo"]
    if tipo in TIPOS_NOTA:
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("Escolha uma nota.")
        mn, mx = faixa(p)
        if not mn <= v <= mx:
            raise ValueError(f"Escolha uma nota de {mn} a {mx}.")
        return v
    if tipo in ("texto_curto", "comentario"):
        if not isinstance(v, str):
            raise ValueError("Resposta inválida.")
        v = v.strip()
        if len(v) > LIMITE_TEXTO[tipo]:
            raise ValueError(f"Use no máximo {LIMITE_TEXTO[tipo]} caracteres.")
        formato = p.get("formato", "texto")
        if tipo == "texto_curto" and formato == "email":
            try:
                validate_email(v, check_deliverability=False)
            except EmailNotValidError:
                raise ValueError("Informe um e-mail válido.")
            v = v.lower()
        elif tipo == "texto_curto" and formato == "telefone":
            if len(so_digitos(v)) < 8:
                raise ValueError("Informe um telefone válido.")
        elif tipo == "texto_curto" and formato == "numero":
            try:
                float(v.replace(".", "").replace(",", ".") if "," in v else v)
            except ValueError:
                raise ValueError("Informe um número.")
        return v
    if tipo == "escolha_unica":
        if v not in p.get("opcoes", []):
            raise ValueError("Escolha uma das opções.")
        return v
    if tipo == "escolha_multipla":
        if not isinstance(v, list) or any(x not in p.get("opcoes", []) for x in v):
            raise ValueError("Escolha entre as opções.")
        marcadas = [o for o in p["opcoes"] if o in v]
        maximo = p.get("max_selecoes")
        if maximo and len(marcadas) > maximo:
            raise ValueError(f"Escolha no máximo {maximo} opções.")
        return marcadas
    if tipo == "sim_nao":
        if not isinstance(v, bool):
            raise ValueError("Responda sim ou não.")
        return v
    if tipo == "data":
        try:
            if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Informe uma data no formato AAAA-MM-DD.")
        return v
    raise ValueError("Resposta inválida.")


def validar_respostas(perguntas: list[dict], brutas: Any) -> tuple[dict, int | None, str | None, str | None]:
    """Devolve (respostas limpas, nota, tipo_nota, grupo). Valida o tipo de cada valor enviado (ids desconhecidos e
    itens que não são pergunta são ignorados), calcula o caminho com os valores válidos, cobra só os itens do caminho
    (valor inválido ou obrigatória sem resposta) e descarta as respostas fora dele. Levanta 422 com campos por id de
    pergunta. A nota sai da nota principal (sempre no caminho)."""
    if not isinstance(brutas, dict):
        raise AppError(422, "dados_invalidos", "Confira as respostas.", {"respostas": "Formato inválido."})
    erros_de_valor: dict[str, str] = {}
    valores: dict[str, Any] = {}
    reais = [p for p in perguntas if respondivel(p.get("tipo"))]
    for p in reais:
        v = brutas.get(p["id"])
        if _vazio(v):
            continue
        try:
            valores[p["id"]] = _valor(p, v)
        except ValueError as e:
            erros_de_valor[p["id"]] = str(e)
    no_caminho = set(caminho(perguntas, valores))
    campos: dict[str, str] = {}
    limpas: dict[str, Any] = {}
    for p in reais:
        if p["id"] not in no_caminho:
            continue
        if p["id"] in erros_de_valor:
            campos[p["id"]] = erros_de_valor[p["id"]]
        elif p["id"] in valores:
            limpas[p["id"]] = valores[p["id"]]
        elif p.get("obrigatoria"):
            campos[p["id"]] = "Responda esta pergunta."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira as respostas destacadas.", campos)
    if not limpas:
        raise AppError(422, "dados_invalidos", "Responda pelo menos uma pergunta.")
    principal = pergunta_principal(perguntas)
    nota = limpas.get(principal["id"]) if principal else None
    tipo_nota = tipo_nota_de(principal) if nota is not None else None
    return limpas, nota, tipo_nota, grupo_da_nota(tipo_nota, nota)


def formatar_valor(v: Any) -> str:
    if isinstance(v, bool):
        return "Sim" if v else "Não"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        a, m, d = v.split("-")
        return f"{d}/{m}/{a}"
    return str(v)


def resumo(perguntas: list[dict], respostas: dict, v: dict) -> str:
    """ "Pergunta: resposta | ..." sem a nota principal, até 2000 caracteres."""
    principal = pergunta_principal(perguntas)
    partes = []
    for p in perguntas:
        if not respondivel(p["tipo"]) or p is principal or p["id"] not in respostas:
            continue
        titulo = sem_citacoes(renderizar(p["titulo"], v)).strip()
        # "Pergunta?: resposta" fica estranho; pontuação no fim dispensa os dois-pontos
        sep = " " if titulo.endswith(("?", "!", ":", ".")) else ": "
        partes.append((titulo, f"{titulo}{sep}{formatar_valor(respostas[p['id']])}", formatar_valor(respostas[p["id"]])))
    # uma única resposta extra (o caso comum: "o que pesou na nota?") vira só o texto do cliente
    texto = partes[0][2] if len(partes) == 1 else " | ".join(parte for _, parte, _ in partes)
    return texto if len(texto) <= MAX_RESUMO else texto[:MAX_RESUMO - 1] + "…"


def comentario_do_cliente(perguntas: list[dict] | None, respostas: dict | None) -> str:
    """O que o cliente escreveu numa resposta de pesquisa: as respostas das perguntas de comentário, na ordem do
    formulário (lidas das respostas, não do resumo: um " | " no texto do cliente não atrapalha). Nome, e-mail,
    telefone, número, nota, data, sim/não e opções marcadas não são comentário."""
    respostas = respostas or {}
    partes = []
    for p in perguntas or []:
        valor = respostas.get(p.get("id"))
        if p.get("tipo") == "comentario" and isinstance(valor, str) and valor.strip():
            partes.append(valor.strip())
    return SEPARADOR_COMENTARIOS.join(partes)


def escolhas_do_cliente(perguntas: list[dict] | None, respostas: dict | None) -> list[str]:
    """As opções marcadas em cada pergunta de escolha (ex.: "Atrasou, Produto avariado")."""
    respostas = respostas or {}
    return [formatar_valor(respostas[p["id"]]) for p in perguntas or []
            if p.get("tipo") in TIPOS_ESCOLHA and p.get("id") in respostas]


def temas_da_resposta(comentario_cliente: str | None, o_que_faltou: str | None = None,
                      perguntas: list[dict] | None = None, respostas: dict | None = None) -> list[str]:
    """Temas: palavras-chave no comentário do cliente, nas opções que ele marcou e em "o que faltou"."""
    return detectar("\n".join((comentario_cliente or "", " ".join(escolhas_do_cliente(perguntas, respostas)),
                               o_que_faltou or "")))


def email_informado(perguntas: list[dict], respostas: dict) -> str | None:
    for p in perguntas:
        if p["tipo"] == "texto_curto" and p.get("formato") == "email" and respostas.get(p["id"]):
            return respostas[p["id"]]
    return None


# ---- gravação ---------------------------------------------------------------

def atualizar_ultima_nota(s: Session, contato_id: int | None) -> None:
    """`ultima_nota` do contato = nota da resposta mais recente dele (pela data da resposta; arquivadas e
    respostas sem nota não contam). Sem nenhuma, fica vazia."""
    if contato_id is None:
        return
    contato = s.get(Contato, contato_id)
    if contato is None:
        return
    # conta explícita (além do RLS): o banco usa o índice (conta_id, contato_id)
    contato.ultima_nota = s.scalar(
        select(Resposta.nota)
        .where(Resposta.conta_id == contato.conta_id, Resposta.contato_id == contato_id,
               Resposta.arquivada.is_(False), Resposta.nota.is_not(None))
        .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(1))


def gravar_resposta(
    s: Session,
    f: Formulario,
    brutas: Any,
    canal: str,
    v: dict,
    contato: Contato | None = None,
    empresa_id: int | None = None,
    convite_id: int | None = None,
    contexto: dict | None = None,
    referencia: str | None = None,
    ip_hash: str | None = None,
    respostas_validadas: tuple | None = None,
    origem: str = "pesquisa",
    comentario: str | None = None,
    respondida_em=None,
    registrada_por: int | None = None,
) -> Resposta:
    """Valida, grava (com grupo, comentário do cliente e temas) e chama o ponto único `ao_registrar_resposta`. Deve
    rodar dentro de em_conta. `origem`: pesquisa (páginas públicas), manual (registrada por alguém da conta) ou
    importacao. `comentario` substitui o resumo das respostas (resposta à mão) e é o próprio comentário do cliente."""
    assert origem in ORIGENS
    limpas, nota, tipo_nota, grupo = respostas_validadas or validar_respostas(f.perguntas, brutas)
    if contato is None:
        email = email_informado(f.perguntas, limpas)
        if email:
            contato = s.scalar(select(Contato).where(Contato.email == email))
    if contato is not None and empresa_id is None:
        empresa_id = contato.empresa_id
    if comentario is None:
        comentario = resumo(f.perguntas, limpas, v)
        cliente = comentario_do_cliente(f.perguntas, limpas) if origem == "pesquisa" else comentario
    else:
        cliente = comentario.strip()
    r = Resposta(
        formulario_id=f.id, convite_id=convite_id, contato_id=contato.id if contato else None,
        empresa_id=empresa_id, canal=canal, nota=nota, tipo_nota=tipo_nota, grupo=grupo,
        comentario=comentario, comentario_cliente=cliente, respostas=limpas, contexto=contexto or {},
        referencia=referencia or None, ip_hash=ip_hash, origem=origem, respondida_em=respondida_em,
        registrada_por=registrada_por, temas=temas_da_resposta(cliente, None, f.perguntas, limpas),
        formulario_versao=f.versao,
    )
    s.add(r)
    s.flush()
    if contato is not None and nota is not None:
        atualizar_ultima_nota(s, contato.id)
    ao_registrar_resposta(s, r)
    return r


# ---- o cliente muda a resposta (docs/api-editar-resposta.md) ----------------------------------------------------

PRAZO_EDICAO = timedelta(days=7)


def prazo_edicao(r: Resposta) -> datetime:
    """Até quando o cliente pode mudar a resposta: 7 dias depois de responder (a primeira vez)."""
    return r.criada_em + PRAZO_EDICAO


def pode_editar(f: Formulario, r: Resposta | None, agora: datetime) -> bool:
    """Formulário com a edição ligada, resposta de pesquisa (não a registrada à mão nem a importada), não arquivada e
    ainda dentro do prazo."""
    return (bool(f.permite_editar) and r is not None and r.origem == "pesquisa" and not r.arquivada
            and agora < prazo_edicao(r))


def editar_resposta(s: Session, f: Formulario, r: Resposta, brutas: Any, v: dict) -> Resposta:
    """O cliente mudou a resposta: valida como uma nova (a lógica do formulário publicado hoje), troca respostas, nota,
    grupo, comentário, temas (menos os temas escolhidos à mão) e a versão do formulário na mesma linha; data, convite,
    contato, empresa, canal, contexto e referência ficam. Marca `editada_em`/`edicoes`, acerta a última nota do contato
    e chama o ponto único `ao_editar_resposta` com os valores de antes. Deve rodar dentro de em_conta, com quem chama já
    conferindo `pode_editar`."""
    limpas, nota, tipo_nota, grupo = validar_respostas(f.perguntas, brutas)
    antes = {"nota": r.nota, "grupo": r.grupo, "tipo_nota": r.tipo_nota, "comentario_cliente": r.comentario_cliente,
             "respostas": copy.deepcopy(r.respostas)}
    cliente = comentario_do_cliente(f.perguntas, limpas)
    r.respostas = limpas
    r.nota, r.tipo_nota, r.grupo = nota, tipo_nota, grupo
    r.comentario = resumo(f.perguntas, limpas, v)
    r.comentario_cliente = cliente
    if not r.temas_manuais:
        r.temas = temas_da_resposta(cliente, r.o_que_faltou, f.perguntas, limpas)
    r.formulario_versao = f.versao
    r.editada_em = func.now()
    r.edicoes = (r.edicoes or 0) + 1
    s.flush()
    if r.contato_id is not None and nota != antes["nota"]:
        atualizar_ultima_nota(s, r.contato_id)
    ao_editar_resposta(s, r, antes)
    return r
