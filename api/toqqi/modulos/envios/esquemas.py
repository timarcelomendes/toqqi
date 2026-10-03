import re
from datetime import time
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, model_validator
from pydantic_core import PydanticCustomError

from toqqi.core.filtros import DataFiltro
from toqqi.core.validacao import Email, EmailOpcional, IdBanco, Texto, TextoAte
from toqqi.modulos.crescimento.esquemas import limpar

MSG_COR = "Use uma cor no formato #RRGGBB, como #D63A18."
_RE_COR = re.compile(r"#[0-9a-fA-F]{6}")


def _hora(v):
    if isinstance(v, time):
        return v
    if not isinstance(v, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v.strip()):
        raise PydanticCustomError("toqqi_hora", "Use o formato HH:MM, como 08:00.")
    h, m = v.strip().split(":")
    return time(int(h), int(m))


def _uma_linha(v):
    if isinstance(v, str) and ("\n" in v or "\r" in v):
        raise PydanticCustomError("toqqi_linha", "Use uma linha só.")
    return v


def _vazio_none(v):
    return None if v == "" else v


def _cor(v):
    """#RRGGBB (maiúsculas ou minúsculas), guardada como #RRGGBB em maiúsculas; vazio ou nulo = nula."""
    if v is None or v == "":
        return None
    if not isinstance(v, str) or not _RE_COR.fullmatch(v.strip()):
        raise PydanticCustomError("toqqi_cor", MSG_COR)
    return v.strip().upper()


def _texto_do_email(maximo: int):
    """Assinatura e rodapé dos e-mails: texto puro sem caracteres de controle (menos a quebra de linha; tab vira
    espaço), nem controles bidirecionais; vazio ou nulo = nulo; acima de `maximo` (depois da limpeza) = 422."""
    longo = f"Use no máximo {maximo} caracteres."

    def validar(v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise PydanticCustomError("toqqi_texto", "Informe um texto.")
        if len(v) > maximo * 4:  # nem limpa: a limpeza percorre o texto inteiro
            raise PydanticCustomError("toqqi_texto", longo)
        v = limpar(v, linhas=True)
        if len(v) > maximo:
            raise PydanticCustomError("toqqi_texto", longo)
        return v or None
    return Annotated[str | None, BeforeValidator(validar)]


Hora = Annotated[time, BeforeValidator(_hora)]
Assunto = Annotated[Texto, Field(min_length=1, max_length=150), AfterValidator(_uma_linha)]
TextoLongo = Annotated[Texto, Field(min_length=1, max_length=2000)]
Dia = Annotated[int, Field(ge=1, le=30)]
CorEmail = Annotated[str | None, BeforeValidator(_cor)]
Assinatura = _texto_do_email(300)
Rodape = _texto_do_email(500)


class AgradecimentoIn(BaseModel):
    promotor: TextoLongo
    neutro: TextoLongo
    detrator: TextoLongo


class ConfigIn(BaseModel):
    """Corpo parcial: só os campos enviados mudam."""
    envios_ativos: bool | None = None
    envio_automatico: bool | None = None
    formulario_id: int | None = None
    intervalo_dias: Annotated[int, Field(ge=30, le=365)] | None = None
    descanso_dias: Annotated[int, Field(ge=0, le=180)] | None = None
    lembretes: Annotated[int, Field(ge=0, le=3)] | None = None
    dias_lembretes: Annotated[list[Dia], Field(max_length=3)] | None = None
    janela_inicio: Hora | None = None
    janela_fim: Hora | None = None
    so_dias_uteis: bool | None = None
    responder_para: EmailOpcional = None
    remetente_nome: Annotated[Annotated[Texto, Field(max_length=80), AfterValidator(_uma_linha)] | None,
                              BeforeValidator(_vazio_none)] = None
    assunto_convite: Assunto | None = None
    texto_convite: TextoLongo | None = None
    assunto_lembrete: Assunto | None = None
    texto_lembrete: TextoLongo | None = None
    texto_whatsapp: TextoLongo | None = None
    agradecimento_ativo: bool | None = None
    agradecimento: AgradecimentoIn | None = None
    canal: Literal["email", "whatsapp", "whatsapp_e_email"] | None = None
    # etapa 5e: visual dos e-mails de pesquisa (nulo apaga a cor, a imagem, a assinatura e o rodapé)
    email_cor: CorEmail = None
    email_mostrar_logo: bool | None = None
    email_imagem_topo_id: IdBanco | None = None
    email_assinatura: Assinatura = None
    email_rodape: Rodape = None


Opcional = BeforeValidator(_vazio_none)
SITUACOES = Literal["inativo", "saiu_da_lista", "nao_saiu", "enviando", "aguardando", "respondeu", "na_fila",
                    "aguardando_intervalo"]


class FiltrosFila(BaseModel):
    situacao: Annotated[SITUACOES | None, Opcional] = None
    busca: Annotated[Annotated[str, Field(max_length=100)] | None, Opcional] = None
    grupo_id: Annotated[int | None, Opcional] = None
    responsavel_id: Annotated[int | None, Opcional] = None
    empresa_id: Annotated[int | None, Opcional] = None
    proximo_de: DataFiltro = None
    proximo_ate: DataFiltro = None
    ultimo_de: DataFiltro = None
    ultimo_ate: DataFiltro = None
    lembrete: Annotated[Literal["hoje", "amanha"] | None, Opcional] = None
    mostrar_inativos: bool = False


class DispararIn(BaseModel):
    contato_ids: Annotated[list[int], Field(min_length=1, max_length=500)] | None = None
    toda_fila: bool = False
    filtros: FiltrosFila | None = None
    ignorar_descanso: bool = False

    @model_validator(mode="after")
    def _um_dos_dois(self):
        if bool(self.contato_ids) == self.toda_fila:
            raise PydanticCustomError("toqqi_disparo", "Escolha os contatos ou toda a fila.")
        return self


class FiltrosHistorico(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None
    tipo: Annotated[Literal["convite", "lembrete", "agradecimento"] | None, Opcional] = None
    canal: Annotated[Literal["email", "whatsapp"] | None, Opcional] = None
    situacao: Annotated[Literal["pendente", "enviado", "entregue", "lido", "erro", "aberto_no_whatsapp"] | None,
                        Opcional] = None
    busca: Annotated[Annotated[str, Field(max_length=100)] | None, Opcional] = None
    contato_id: Annotated[int | None, Opcional] = None


class DescadastroManualIn(BaseModel):
    email: Email
    motivo: TextoAte(300) = None


class DescadastroPublicoIn(BaseModel):
    motivo: TextoAte(300) = None
    voltar: bool = False


class WhatsappIn(BaseModel):
    formulario_id: int | None = None
