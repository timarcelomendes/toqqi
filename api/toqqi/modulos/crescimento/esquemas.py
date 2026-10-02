"""Entradas do Crescimento. Os textos perdem os caracteres de controle, os controles bidirecionais (que disfarçam
nomes no e-mail e no CSV) e os surrogates soltos; os de uma linha também juntam os espaços (quebra de linha e tab viram
espaço). Texto muito maior que o permitido é recusado antes de ser limpo (a limpeza percorre o texto inteiro).
Telefone pela regra brasileira de sempre (celular ou fixo, `core.validacao.telefone_br`), guardado só com dígitos e
com 55. Ids dentro do bigint (`core.validacao.MAX_ID`): fora disso o banco recusaria a consulta."""
import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

from toqqi.core.errors import AppError
from toqqi.core.filtros import DataFiltro
from toqqi.core.validacao import MAX_ID, EmailOpcional, IdBanco, TelefoneBr
from toqqi.modulos.empresas.esquemas import Valor
from toqqi.modulos.respostas.esquemas import Opcional

SITUACOES = ("nova", "em_contato", "cliente", "nao_avancou")
ABERTAS = ("nova", "em_contato")
LISTAS = ("pode_crescer", "promotores")
RESULTADOS = ("aceitou", "recusou", "sem_resposta")
MSG_CONTATO = "Informe um telefone (WhatsApp) ou um e-mail."
MSG_CONFIRMO = "Confirme que a pessoa aceita receber o contato."

Situacao = Literal[SITUACOES]  # type: ignore[valid-type]
Lista = Literal[LISTAS]  # type: ignore[valid-type]
Resultado = Literal[RESULTADOS]  # type: ignore[valid-type]

# Controles bidirecionais (Bidi_Control do Unicode): ALM, LRM, RLM, LRE…RLO e LRI…PDI. Invisíveis, invertem a ordem
# do texto em volta (um nome "inocente" no e-mail ou no CSV pode esconder outro).
BIDI = frozenset("\u061c\u200e\u200f" + "".join(map(chr, range(0x202A, 0x202F))) +
                 "".join(map(chr, range(0x2066, 0x206A))))
# texto maior que `maximo` × isto é recusado antes da limpeza (folga para os espaços e controles que somem)
FOLGA_ANTES_DE_LIMPAR = 4


def _some(ch: str) -> bool:
    return ch in BIDI or unicodedata.category(ch) == "Cs"


def limpar(v: str, linhas: bool = False) -> str:
    """Sem controles (Cc), controles bidirecionais (BIDI) nem surrogates soltos (Cs). `linhas`: mantém as quebras de
    linha (CRLF e CR viram LF, tab vira espaço); sem, tudo vira uma linha com espaços simples."""
    if linhas:
        v = v.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
        v = "".join(ch for ch in v if ch == "\n" or not (_some(ch) or unicodedata.category(ch) == "Cc"))
        return "\n".join(linha.strip() for linha in v.split("\n")).strip()
    v = "".join(" " if unicodedata.category(ch) == "Cc" else ch for ch in v if not _some(ch))
    return " ".join(v.split())


def _texto(maximo: int, vazio: str | None, minimo: int = 1, linhas: bool = False):
    """Tipo de texto limpo, de `minimo` a `maximo` caracteres. `vazio` None = opcional (vazio ou nulo vira None)."""
    faixa = f"de {minimo} a {maximo}" if minimo > 1 else f"no máximo {maximo:,}".replace(",", ".")
    longo = f"Use {faixa} caracteres."

    def validar(v):
        if v is None:
            if vazio is None:
                return None
            raise PydanticCustomError("toqqi_texto", vazio)
        if not isinstance(v, str):
            raise PydanticCustomError("toqqi_texto", "Informe um texto.")
        if len(v) > maximo * FOLGA_ANTES_DE_LIMPAR:  # nem limpa: um corpo com 10 MB de texto prenderia a API
            raise PydanticCustomError("toqqi_texto", longo)
        v = limpar(v, linhas)
        if not v:
            if vazio is None:
                return None
            raise PydanticCustomError("toqqi_texto", vazio)
        if len(v) > maximo or len(v) < minimo:
            raise PydanticCustomError("toqqi_texto", longo)
        return v
    return Annotated[str | None if vazio is None else str, BeforeValidator(validar)]


Nome = _texto(120, "Informe o nome de quem você indica.", minimo=2)
EmpresaIndicada = _texto(120, None)
Observacao = _texto(500, None, linhas=True)
Motivo = _texto(300, None, linhas=True)
TituloConvite = _texto(120, "Escreva o título do convite.")
TextoConvite = _texto(500, "Escreva o texto do convite.", linhas=True)
Recompensa = _texto(300, None, linhas=True)
TextoOferta = _texto(1000, "Escreva o texto da oferta.", linhas=True)
TextoOfertaFeita = _texto(2000, "Escreva o texto da oferta.", linhas=True)
Busca = _texto(100, None)  # sem controles (o NUL o banco nem aceitaria); vazio = sem busca

# filtros (query): vazio = sem filtro; `IdOuSem` aceita 0 = "sem responsável"
IdFiltro = Annotated[Annotated[int, Field(ge=1, le=MAX_ID)] | None, Opcional]
IdOuSem = Annotated[Annotated[int, Field(ge=0, le=MAX_ID)] | None, Opcional]


def _confirmado(v: bool) -> bool:
    if v is not True:
        raise PydanticCustomError("toqqi_confirmo", MSG_CONFIRMO)
    return v


class _Indicado(BaseModel):
    nome: Nome
    empresa: EmpresaIndicada = None
    telefone: TelefoneBr = None
    email: EmailOpcional = None
    observacao: Observacao = None

    def conferir_contato(self) -> None:
        """Telefone ou e-mail: pelo menos um (422 nos dois campos)."""
        if not self.telefone and not self.email:
            raise AppError(422, "dados_invalidos", "Confira os campos destacados.",
                           {"telefone": MSG_CONTATO, "email": MSG_CONTATO})


class IndicacaoPublicaIn(_Indicado):
    """POST /publico/convites/{token}/indicacoes."""
    pode_identificar: bool = True
    confirmo: Annotated[bool, AfterValidator(_confirmado), Field(validate_default=True)] = False


class IndicacaoIn(_Indicado):
    """POST /crescimento/indicacoes (registrada à mão: quem registra responde pelo consentimento)."""
    indicador_contato_id: IdBanco | None = None
    indicador_empresa_id: IdBanco | None = None
    responsavel_id: IdBanco | None = None
    pode_identificar: bool = True


class IndicacaoAlterarIn(BaseModel):
    """Corpo parcial. 'cliente' pede valor_mensal; motivo só vale com 'nao_avancou'; null em responsavel_id limpa."""
    situacao: Situacao | None = None
    valor_mensal: Valor | None = None
    motivo: Motivo = None
    responsavel_id: IdBanco | None = None


class FiltrosIndicacoes(BaseModel):
    situacao: Annotated[Situacao | None, Opcional] = None
    responsavel_id: IdOuSem = None  # 0 = sem responsável
    de: DataFiltro = None
    ate: DataFiltro = None
    busca: Busca = None


class FiltrosOportunidades(BaseModel):
    lista: Annotated[Lista | None, Opcional] = None  # vazio = pode_crescer
    grupo_id: IdFiltro = None
    responsavel_id: IdOuSem = None  # 0 = sem responsável


class OfertaIn(BaseModel):
    empresa_id: IdBanco
    contato_id: IdBanco | None = None
    lista: Lista
    texto: TextoOfertaFeita
    canal: Literal["whatsapp", "email"] = "whatsapp"  # e-mail: o contato sem telefone (mailto:)


class OfertaAlterarIn(BaseModel):
    """Corpo parcial. resultado null = sem resultado; valor só com 'aceitou' (outros resultados limpam o valor; com
    'aceitou', valor ausente ou null mantém o que já havia — regra em `oportunidades.alterar_oferta`)."""
    resultado: Resultado | None = None
    valor: Valor | None = None


class PeriodoIn(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None


class ConfigCrescimentoIn(BaseModel):
    """Corpo parcial: só os campos enviados mudam (null nos textos obrigatórios não muda; recompensa vazia limpa)."""
    indicacoes_ativas: bool | None = None
    titulo_convite: TituloConvite | None = None
    texto_convite: TextoConvite | None = None
    recompensa: Recompensa = None
    texto_oferta: TextoOferta | None = None
