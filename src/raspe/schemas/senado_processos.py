"""Schemas de ``raspe.senado_processos().raspar()``: processos legislativos na API de Dados Abertos do Senado."""

from pydantic import Field

from .base import AnoMixin, IntervaloDatasMixin, OutputBase, PaginasMixin, PesquisaOpcionalMixin


class InputSenadoProcessos(PaginasMixin, AnoMixin, IntervaloDatasMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperSenadoProcessos.raspar()``.

    ``data_inicio`` e ``data_fim`` (do mixin) filtram pela data de apresentação do processo.
    A busca precisa de ``ano`` ou de ``data_inicio``.
    """

    pesquisa: str | list[str] = Field(
        default="",
        description=(
            "Termo procurado nas palavras-chave do processo. Uma lista dispara uma busca por item, e a coluna "
            "`termo_busca` diz de qual item veio cada linha. Vazio busca só pelos demais filtros."
        ),
        examples=["telemedicina", ["telemedicina", "doenças raras"]],
    )
    ano: int | None = Field(
        default=None,
        description=(
            "Ano da identificação do processo (o 2020 de PL 696/2020), com quatro dígitos. Pode não ser o ano "
            "de apresentação, que se filtra com `data_inicio` e `data_fim`."
        ),
        examples=[2020],
    )
    sigla_tipo: str = Field(
        default="",
        description="Sigla da identificação do processo, como o Senado a escreve; vazio não filtra.",
        examples=["PL", "PEC"],
    )
    paginas: range | None = Field(
        default=None,
        description=(
            "A API devolve cada consulta inteira numa página só, então `paginas` só existe aqui por paridade com "
            "os outros raspadores: `range(1, 2)` ou nenhum valor baixam tudo, também na busca dividida por período."
        ),
    )


class OutputSenadoProcessos(OutputBase):
    """Processos legislativos da API de Dados Abertos do Senado Federal (``/processo``).

    As colunas "ou nulo" são os campos que a API só manda para parte dos processos.
    """

    id: int = Field(description="Identificador do processo no Senado.", examples=[7879650])
    codigo_materia: int = Field(
        description="Código da matéria no sistema anterior do Senado (MATE).", examples=[141263]
    )
    identificacao: str = Field(description="Sigla, número e ano do processo.", examples=["PL 696/2020"])
    apelido: str | None = Field(
        description="Nome pelo qual o processo ficou conhecido, ou nulo.",
        examples=["Marco Legal da Inteligência Artificial"],
    )
    ementa: str = Field(
        description="Ementa do processo.",
        examples=["Dispõe sobre o uso da telemedicina durante a crise causada pelo coronavírus"],
    )
    tipo_documento: str = Field(
        description="Tipo do documento que iniciou o processo.", examples=["Projeto de Lei Ordinária"]
    )
    tipo_conteudo: str = Field(description="Tipo de conteúdo do documento inicial.", examples=["Norma Geral"])
    autoria: str = Field(description="Autor ou autores do processo.", examples=["Câmara dos Deputados"])
    objetivo: str | None = Field(
        description="Papel do Senado no processo (como iniciadora ou revisora), ou nulo.", examples=["Revisora"]
    )
    casa_identificadora: str = Field(
        description="Casa que identifica o processo: `SF` (Senado Federal) ou `CN` (Congresso Nacional).",
        examples=["SF"],
    )
    ente_identificador: str = Field(
        description="Sigla do ente (casa, comissão ou colegiado) que identifica o processo.", examples=["SF"]
    )
    data_apresentacao: str = Field(description="Data de apresentação, em AAAA-MM-DD.", examples=["2020-03-26"])
    tramitando: str = Field(
        description="Se o processo ainda tramita: `Sim` ou `Não`, como a API devolve.", examples=["Não"]
    )
    situacao_atual: str | None = Field(
        description="Situação atual do processo, ou nulo.",
        examples=["TRANSFORMADA EM NORMA JURÍDICA COM VETO PARCIAL"],
    )
    data_situacao_atual: str | None = Field(
        description="Data da situação atual, em AAAA-MM-DD, ou nulo.", examples=["2020-04-16"]
    )
    data_deliberacao: str | None = Field(
        description="Data da deliberação, em AAAA-MM-DD, ou nulo quando ainda não houve.", examples=["2020-03-31"]
    )
    sigla_tipo_deliberacao: str | None = Field(
        description="Sigla do tipo de deliberação, ou nulo quando ainda não houve.",
        examples=["APROVADA_NO_PLENARIO"],
    )
    norma_gerada: str | None = Field(
        description="Norma em que o processo se transformou, ou nulo.", examples=["Lei nº 13.989 de 15/04/2020"]
    )
    ultima_informacao_atualizada: str | None = Field(
        description="Tipo da última informação atualizada no processo, ou nulo.", examples=["EVENTO_LEGISLATIVO"]
    )
    data_ultima_atualizacao: str | None = Field(
        description="Data e hora da última atualização, em ISO 8601 sem fuso, ou nulo.",
        examples=["2026-07-01T09:07:06.075"],
    )
    url_documento: str | None = Field(
        description="Endereço do documento inicial do processo, ou nulo.",
        examples=[
            "https://legis.senado.gov.br/sdleg-getter/dadosabertos/documento/aeb2ac05-c25d-40bb-ba82-710cef32ae5c"
        ],
    )
