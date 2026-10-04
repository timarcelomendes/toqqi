"""Etapa 5g: os números do site da raiz (`web/index.html`) são os padrões do código (`core.parametros`). O HTML fica com
eles (buscadores e quem não roda JavaScript) e o `site.ts` troca pelos de agora (GET /publico/planos); o teste do site
(vitest) compara o HTML com uma cópia dos padrões em TypeScript, e este compara com a fonte: mudar um padrão no código
sem mudar o HTML (ou o contrário) quebra aqui."""
import re
from decimal import Decimal

from toqqi.core import parametros
from toqqi.core.db import RAIZ_API

INDEX = RAIZ_API.parent / "web" / "index.html"
RESPONDIDAS = 3  # perguntas já respondidas na conversa parada do HTML: `data-restam` = cota do Profissional − 3
MARCA = re.compile(r'<span\b([^>]*?)\bdata-p="([^"]+)"([^>]*)>([^<]*)</span>')
RESTAM = re.compile(r'<span\b[^>]*\bdata-restam\b[^>]*>([^<]*)</span>')


def texto_do_site(chave: str, valor, maiuscula: bool = False) -> str:
    """Como o site escreve o número (`textoNumeroSite` do site): preço inteiro "149" (com centavos, "149,90"), "1.500",
    null "sem limite" (`data-p-maiuscula`: "Sem limite")."""
    if valor is None:
        return "Sem limite" if maiuscula else "sem limite"
    if parametros.CAMPOS[chave].tipo == "dinheiro":
        v = Decimal(valor)
        return parametros.numero(int(v)) if v == v.to_integral_value() else parametros.reais(v).removeprefix("R$ ")
    return parametros.numero(int(valor))


def conferir(html: str) -> list[str]:
    """O que não bate entre o HTML e os padrões do código (vazio = tudo certo)."""
    erros: list[str] = []
    marcas = MARCA.findall(html)
    if len(marcas) != html.count("data-p="):
        erros.append(f"{html.count('data-p=')} data-p no HTML, {len(marcas)} em <span> só com o número")
    for antes, chave, depois, texto in marcas:
        if chave not in parametros.CAMPOS:
            erros.append(f"data-p desconhecido: {chave}")
            continue
        esperado = texto_do_site(chave, parametros.padrao(chave), "data-p-maiuscula" in antes + depois)
        if texto.strip() != esperado:
            erros.append(f"{chave}: o HTML diz {texto.strip()!r}, o padrão do código é {esperado!r}")
    restam = RESTAM.findall(html)
    esperado = parametros.numero(parametros.padrao("ia.cota.profissional") - RESPONDIDAS)
    if restam != [esperado]:
        erros.append(f"data-restam: o HTML diz {restam}, a conversa parada pede [{esperado!r}]")
    return erros


def test_cada_data_p_do_site_traz_o_padrao_do_codigo():
    assert INDEX.is_file(), f"{INDEX} não encontrado (o teste lê o site da raiz do repositório)"
    html = INDEX.read_text(encoding="utf-8")
    assert conferir(html) == []
    chaves = {chave for _, chave, _, _ in MARCA.findall(html)}  # o parser achou as marcas principais
    assert {f"planos.{p}.preco" for p in parametros.PLANOS} | {"teste.dias", "ia.cota.profissional"} <= chaves


def test_a_conferencia_acha_o_numero_que_nao_bate():
    html = INDEX.read_text(encoding="utf-8")
    trocado = html.replace('data-p="planos.empresa.preco">799<', 'data-p="planos.empresa.preco">899<', 1)
    assert trocado != html
    assert conferir(trocado) == ["planos.empresa.preco: o HTML diz '899', o padrão do código é '799'"]
    sem_limite = html.replace('data-p-maiuscula>Sem limite<', 'data-p-maiuscula>sem limite<', 1)
    assert conferir(sem_limite) == [
        "planos.empresa.contatos: o HTML diz 'sem limite', o padrão do código é 'Sem limite'"]
    restam = html.replace("<span data-restam>497</span>", "<span data-restam>499</span>", 1)
    assert conferir(restam) == ["data-restam: o HTML diz ['499'], a conversa parada pede ['497']"]
    assert texto_do_site("planos.essencial.preco", Decimal("149.90")) == "149,90"
    assert texto_do_site("planos.essencial.preco", Decimal("1234.00")) == "1.234"
