"""Risco de cada conta (Plataforma › Contas; pedido do Marcelo em 08/10/2026, 10h45: "adicione uma coluna para informar
contas suspeitas, score das contas"). Contrato: docs/api-plataforma-risco.md.

Uma nota de 0 a 100, a soma dos pontos dos sinais encontrados (cada sinal vem com os dados que o explicam), para a
equipe olhar primeiro as contas que podem estar abusando do Toqqi:
- cadastro falso ou repetido para ganhar outro teste: e-mail temporário, e-mail pessoal, e-mail nunca confirmado, nome
  de teste e o mesmo CPF/CNPJ, telefone, domínio ou nome de outra conta;
- lista comprada (o que mais estraga a entrega dos e-mails do Toqqi): muita gente pedindo para sair, endereços e números
  que não existem, quase ninguém respondendo, muito envio logo nos primeiros dias;
- golpe: formulário com pergunta aberta pedindo senha, cartão, dados bancários ou código de verificação;
- pagamento estornado.

A nota é um alerta para alguém olhar, não uma decisão: nada é bloqueado por ela. Níveis: `alto` (60 ou mais), `medio`
(30 a 59), `baixo` (menos de 30). Sem IP, de propósito: os registros de acesso ficam em sigilo (Marco Civil;
`core.acessos`) e nenhuma tela os lê. As contas da equipe (algum administrador em SUPERADMIN_EMAILS) ficam sem nota
(`None`) e fora das comparações de repetidos.

Número fixo de consultas agregadas (GROUP BY), como na Visão geral: não cresce com o número de contas.
"""
import re
import unicodedata
from datetime import timedelta

from sqlalchemy import Text, cast, exists, func, select

from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.db import sem_jit
from toqqi.core.email import MSG_ENDERECO
from toqqi.core.texto import telefone_canonico
from toqqi.core.validacao import DOMINIOS_GRATUITOS, dominio_do_email
from toqqi.modelos import Assinatura, Cobranca, Conta, Convite, Descadastro, Envio, Formulario, Usuario
from toqqi.modulos.envios.fila import SAIU
from toqqi.modulos.whatsapp.graph import MSG_NUMERO

ALTO, MEDIO = 60, 30
DIAS = 30  # janela do comportamento de envio
DIAS_RESPOSTA = 3  # convites mais novos que isso ainda podem ser respondidos: ficam fora da conta de respostas
MAX_CONTAS_CITADAS = 3

# Pontos de cada sinal (os de duas faixas: o primeiro é o da faixa alta)
PONTOS = {
    "formulario_sensivel": 60,
    "email_temporario": 40,
    "descadastros": (35, 20),
    "invalidos": (30, 15),
    "documento_repetido": 30,
    "estorno": 25,
    "telefone_repetido": 20,
    "sem_respostas": 15,
    "email_nao_confirmado": 15,
    "nome_de_teste": 15,
    "nome_repetido": 15,
    "email_pessoal": 10,
    "dominio_repetido": 10,
    "volume_inicio": 10,
}

# Envio: taxas em %, com um mínimo de volume para não acusar conta pequena por acaso
MIN_DESTINATARIOS, MIN_SAIDAS, SAIDAS_ALTA, SAIDAS = 30, 3, 5, 2
MIN_TENTATIVAS, MIN_INVALIDOS, INVALIDOS_ALTA, INVALIDOS = 30, 5, 20, 8
MIN_CONVITES, RESPOSTA_MINIMA = 100, 2
DIAS_CONTA_NOVA, ENVIOS_CONTA_NOVA = 14, 500
DIAS_SEM_CONFIRMAR = 2

# Saídas pedidas por quem recebeu (a "manual" é a equipe da conta tirando alguém da lista)
ORIGENS_SAIDA = ("link", "um_clique", "whatsapp")
ERROS_INVALIDO = (MSG_ENDERECO, MSG_NUMERO)
PERGUNTAS_ABERTAS = ("texto_curto", "comentario")

DOMINIOS_PESSOAIS = DOMINIOS_GRATUITOS | frozenset({
    "msn.com", "me.com", "mac.com", "googlemail.com", "ymail.com", "rocketmail.com", "outlook.com.br",
    "hotmail.com.br", "live.com.br", "globo.com", "globomail.com", "r7.com", "zipmail.com.br", "proton.me", "pm.me",
    "gmx.com", "gmx.net", "aol.com", "mail.com", "yandex.com", "zohomail.com", "tutanota.com",
})

# Serviços de e-mail descartável conhecidos (o subdomínio de um deles também conta)
DOMINIOS_TEMPORARIOS = frozenset({
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamailblock.com", "sharklasers.com", "grr.la", "pokemail.net", "spam4.me", "10minutemail.com",
    "10minutemail.net", "temp-mail.org", "temp-mail.io", "tempmail.com", "tempmail.net", "tempmail.dev",
    "tempmailo.com", "tempr.email", "yopmail.com", "yopmail.fr", "yopmail.net", "getnada.com", "nada.email",
    "trashmail.com", "trashmail.de", "dispostable.com", "maildrop.cc", "mohmal.com", "emailondeck.com",
    "throwawaymail.com", "fakeinbox.com", "mintemail.com", "mytemp.email", "discard.email", "mailnesia.com",
    "spamgourmet.com", "tempail.com", "burnermail.io", "mail.tm", "inboxkitten.com", "1secmail.com", "1secmail.net",
    "1secmail.org", "tmpmail.org", "tmpmail.net", "emailfake.com", "moakt.com", "tempinbox.com", "jetable.org",
    "mailcatch.com", "dropmail.me", "emltmp.com", "minuteinbox.com", "fakemail.net", "mailpoof.com",
    "harakirimail.com", "wegwerfmail.de", "mailsac.com", "anonbox.net", "mailexpire.com", "byom.de",
})

# Pergunta aberta pedindo dado que um formulário de pesquisa não pede (o grupo diz o quê)
_RE_SENSIVEL = re.compile(
    r"\b(?P<senha>senhas?)\b"
    r"|\b(?P<cartao>cvv|cvc|n[uú]mero do cart[aã]o|dados do cart[aã]o|validade do cart[aã]o|c[oó]digo de seguran[cç]a)\b"
    r"|\b(?P<banco>dados banc[aá]rios|ag[eê]ncia e conta|conta banc[aá]ria)\b"
    r"|\b(?P<codigo>c[oó]digo (?:de verifica[cç][aã]o|de confirma[cç][aã]o|do sms|que (?:voc[eê] )?recebeu))\b",
    re.IGNORECASE)
# Filtro largo no banco (só os formulários que podem ter um desses trechos vêm para o Python)
_PREFILTRO = r"senha|cvv|cvc|cart|banc|ncia e conta|seguran|digo"
_RE_TAG = re.compile(r"<[^>]+>")
MAX_TRECHO = 100

# Nome que não parece de empresa: de teste, teclado, genérico
_RE_NOME_TESTE = re.compile(
    r"^(?:testes?|testing|testando|asdf\w*|qwer\w*|zxcv\w*|sdfg?\w*|hjkl|abcd?e?|xyz|foo|bar|lorem(?: ipsum)?|"
    r"fulano|ciclano|beltrano|empresa|minha empresa|nome da empresa|sem nome|nenhuma|n a|na)$"
    r"|\b(?:teste|test|testing)\b")
_RE_SUFIXO = re.compile(r"\b(?:ltda|limitada|me|mei|epp|eireli|s a|sa|cia)\b")


def _sem_acentos(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))


def nome_normal(nome: str) -> str:
    """"Distribuidora Aurora LTDA." → "distribuidora aurora": sem acento, caixa, pontuação e sufixo de tipo de empresa."""
    t = re.sub(r"[^a-z0-9]+", " ", _sem_acentos(nome or "").casefold())
    return " ".join(_RE_SUFIXO.sub(" ", t).split())


def nome_de_teste(nome: str) -> bool:
    t = " ".join(re.sub(r"[^a-z0-9]+", " ", _sem_acentos(nome or "").casefold()).split())
    if len(t) < 3 or not re.search(r"[a-z]", t) or len(set(t.replace(" ", ""))) == 1:
        return True
    return bool(_RE_NOME_TESTE.search(t))


def dominio_temporario(dominio: str) -> bool:
    return any(dominio == d or dominio.endswith(f".{d}") for d in DOMINIOS_TEMPORARIOS)


def _telefone(t: str | None) -> str | None:
    d = re.sub(r"\D", "", t or "")
    if len(d) in (10, 11):
        d = f"55{d}"
    return telefone_canonico(d) if len(d) >= 12 else None


def trecho_sensivel(perguntas: list) -> tuple[str, str] | None:
    """(termo, trecho) da primeira pergunta aberta (ou bloco de texto, num formulário com pergunta aberta) que pede
    senha, cartão, dados bancários ou código de verificação; None se nenhuma."""
    itens = [p for p in perguntas if isinstance(p, dict)]
    tem_aberta = any(p.get("tipo") in PERGUNTAS_ABERTAS for p in itens)
    for p in itens:
        if p.get("tipo") in PERGUNTAS_ABERTAS:
            texto = " ".join(str(p.get(k) or "") for k in ("titulo", "descricao"))
            trecho = str(p.get("titulo") or "") or texto
        elif p.get("tipo") == "conteudo" and tem_aberta:
            texto = trecho = " ".join(_RE_TAG.sub(" ", str(p.get("html") or "")).split())
        else:
            continue
        m = _RE_SENSIVEL.search(texto)
        if m:
            trecho = " ".join(trecho.split())
            return m.lastgroup or "senha", trecho[:MAX_TRECHO - 1] + "…" if len(trecho) > MAX_TRECHO else trecho
    return None


def _taxa(parte: int, total: int) -> int:
    return round(parte * 100 / total) if total else 0


def calcular(s) -> dict[int, dict | None]:
    """A nota de cada conta ({pontos, nivel, sinais}), ou None nas contas da equipe. `s` em modo sistema."""
    sem_jit(s)
    agora = relogio.agora()
    desde = agora - timedelta(days=DIAS)
    equipe = config().superadmins
    contas = s.execute(select(Conta.id, Conta.nome, Conta.documento, Conta.telefone, Conta.criada_em)).all()
    admins: dict[int, list[tuple[str, bool, str | None]]] = {}
    for cid, email, confirmado, telefone in s.execute(
            select(Usuario.conta_id, Usuario.email, Usuario.email_confirmado, Usuario.telefone)
            .where(Usuario.perfil == "admin").order_by(Usuario.conta_id, Usuario.id)):
        admins.setdefault(cid, []).append((email.lower(), bool(confirmado), telefone))
    da_equipe = {cid for cid, lista in admins.items() if any(e in equipe for e, _, _ in lista)}
    cobranca: dict[int, list[tuple[str | None, str | None]]] = {}
    for cid, doc, tel in s.execute(select(Assinatura.conta_id, Assinatura.documento, Assinatura.telefone)):
        cobranca.setdefault(cid, []).append((doc, tel))

    envios = {cid: resto for cid, *resto in s.execute(select(
        Envio.conta_id,
        func.count(func.distinct(Envio.para)).filter(Envio.situacao.in_(SAIU), Envio.enviado_em >= desde),
        func.count().filter(Envio.situacao.in_(SAIU)),
        func.count().filter(Envio.situacao.in_((*SAIU, "erro"))),
        func.count().filter(Envio.situacao == "erro", Envio.erro.in_(ERROS_INVALIDO)),
    ).where(Envio.criado_em >= desde).group_by(Envio.conta_id))}
    saidas = dict(s.execute(select(Descadastro.conta_id, func.count())
                            .where(Descadastro.origem.in_(ORIGENS_SAIDA), Descadastro.criado_em >= desde)
                            .group_by(Descadastro.conta_id)).all())
    saiu = exists().where(Envio.conta_id == Convite.conta_id, Envio.convite_id == Convite.id, Envio.tipo == "convite",
                          Envio.situacao.in_(SAIU))
    convites = {cid: (n, r) for cid, n, r in s.execute(
        select(Convite.conta_id, func.count(), func.count().filter(Convite.respondido_em.is_not(None)))
        .where(Convite.canal.in_(("email", "whatsapp")), Convite.criado_em >= desde,
               Convite.criado_em < agora - timedelta(days=DIAS_RESPOSTA), saiu)
        .group_by(Convite.conta_id))}
    sensiveis: dict[int, dict] = {}
    for cid, fid, nome, perguntas in s.execute(
            select(Formulario.conta_id, Formulario.id, Formulario.nome, Formulario.perguntas)
            .where(Formulario.arquivado.is_(False), cast(Formulario.perguntas, Text).op("~*")(_PREFILTRO))
            .order_by(Formulario.conta_id, Formulario.id)):
        if cid not in sensiveis and (achado := trecho_sensivel(perguntas or [])):
            sensiveis[cid] = {"formulario": {"id": fid, "nome": nome}, "termo": achado[0], "trecho": achado[1]}
    estornos = {cid: (n, quando) for cid, n, quando in s.execute(
        select(Cobranca.conta_id, func.count(), func.max(Cobranca.atualizada_em))
        .where(Cobranca.situacao == "estornada").group_by(Cobranca.conta_id))}

    # Repetidos: o mesmo valor em mais de uma conta (fora as da equipe)
    nomes = {c.id: c.nome for c in contas}
    docs: dict[str, set[int]] = {}
    tels: dict[str, set[int]] = {}
    doms: dict[str, set[int]] = {}
    iguais: dict[str, set[int]] = {}
    chaves: dict[int, dict[str, set[str]]] = {}
    for c in contas:
        if c.id in da_equipe:
            continue
        lista = admins.get(c.id, [])
        k = chaves[c.id] = {
            "docs": {d.strip().upper() for d in [c.documento, *(d for d, _ in cobranca.get(c.id, []))] if d},
            "tels": {t for t in map(_telefone, [c.telefone, *(t for _, _, t in lista),
                                               *(t for _, t in cobranca.get(c.id, []))]) if t},
            "doms": set(), "nomes": set()}
        if lista:
            dom = dominio_do_email(lista[0][0])
            if dom not in DOMINIOS_PESSOAIS and not dominio_temporario(dom):
                k["doms"].add(dom)
        if not nome_de_teste(c.nome) and (n := nome_normal(c.nome)):
            k["nomes"].add(n)
        for mapa, chave in ((docs, "docs"), (tels, "tels"), (doms, "doms"), (iguais, "nomes")):
            for v in k[chave]:
                mapa.setdefault(v, set()).add(c.id)

    def outras(mapa: dict[str, set[int]], valores: set[str], cid: int) -> list[int]:
        return sorted({o for v in valores for o in mapa.get(v, ()) if o != cid}, key=lambda o: (nomes[o].casefold(), o))

    def citadas(ids: list[int]) -> dict:
        return {"contas": [{"id": o, "nome": nomes[o]} for o in ids[:MAX_CONTAS_CITADAS]], "total": len(ids)}

    notas: dict[int, dict | None] = {}
    for c in contas:
        if c.id in da_equipe:
            notas[c.id] = None
            continue
        sinais: list[dict] = []

        def sinal(tipo: str, pontos: int | None = None, **dados) -> None:
            sinais.append({"tipo": tipo, "pontos": PONTOS[tipo] if pontos is None else pontos, **dados})

        # Quem se cadastrou: o administrador mais antigo
        lista = admins.get(c.id, [])
        if any(dominio_temporario(dominio_do_email(e)) for e, _, _ in lista):
            dom = next(dominio_do_email(e) for e, _, _ in lista if dominio_temporario(dominio_do_email(e)))
            sinal("email_temporario", dominio=dom)
        elif lista and dominio_do_email(lista[0][0]) in DOMINIOS_PESSOAIS:
            sinal("email_pessoal", dominio=dominio_do_email(lista[0][0]))
        dias = (agora - c.criada_em).days
        if lista and not lista[0][1] and dias >= DIAS_SEM_CONFIRMAR:
            sinal("email_nao_confirmado", dias=dias)
        if nome_de_teste(c.nome):
            sinal("nome_de_teste")

        k = chaves[c.id]
        if ids := outras(docs, k["docs"], c.id):
            doc = next(d for d in sorted(k["docs"]) if docs[d] - {c.id})
            sinal("documento_repetido", documento="cpf" if len(doc) == 11 else "cnpj", **citadas(ids))
        if ids := outras(tels, k["tels"], c.id):
            sinal("telefone_repetido", **citadas(ids))
        if ids := outras(doms, k["doms"], c.id):
            sinal("dominio_repetido", dominio=next(iter(k["doms"])), **citadas(ids))
        if ids := outras(iguais, k["nomes"], c.id):
            sinal("nome_repetido", **citadas(ids))

        # Envio nos últimos 30 dias
        destinatarios, enviados, tentativas, invalidos = envios.get(c.id, (0, 0, 0, 0))
        n_saidas = saidas.get(c.id, 0)
        if destinatarios >= MIN_DESTINATARIOS and n_saidas >= MIN_SAIDAS and n_saidas * 100 >= SAIDAS * destinatarios:
            alta = n_saidas * 100 >= SAIDAS_ALTA * destinatarios
            sinal("descadastros", PONTOS["descadastros"][0 if alta else 1], saidas=n_saidas,
                  destinatarios=destinatarios, taxa=_taxa(n_saidas, destinatarios))
        if tentativas >= MIN_TENTATIVAS and invalidos >= MIN_INVALIDOS and invalidos * 100 >= INVALIDOS * tentativas:
            alta = invalidos * 100 >= INVALIDOS_ALTA * tentativas
            sinal("invalidos", PONTOS["invalidos"][0 if alta else 1], invalidos=invalidos, tentativas=tentativas,
                  taxa=_taxa(invalidos, tentativas))
        n_convites, respostas = convites.get(c.id, (0, 0))
        if n_convites >= MIN_CONVITES and respostas * 100 < RESPOSTA_MINIMA * n_convites:
            sinal("sem_respostas", convites=n_convites, respostas=respostas)
        if dias < DIAS_CONTA_NOVA and enviados >= ENVIOS_CONTA_NOVA:
            sinal("volume_inicio", dias=dias, envios=enviados)

        if c.id in sensiveis:
            sinal("formulario_sensivel", **sensiveis[c.id])
        if c.id in estornos:
            sinal("estorno", quantas=estornos[c.id][0], ultima_em=estornos[c.id][1])

        sinais.sort(key=lambda x: -x["pontos"])
        pontos = min(100, sum(x["pontos"] for x in sinais))
        notas[c.id] = {"pontos": pontos, "nivel": "alto" if pontos >= ALTO else "medio" if pontos >= MEDIO else "baixo",
                       "sinais": sinais}
    return notas

