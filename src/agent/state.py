"""Estado compartilhado tipado do grafo LangGraph.

Define a estrutura de dados que percorre todos os nodes do fluxo,
garantindo tipagem forte e rastreabilidade das decisões.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class FlowStatus(str, Enum):
    """Status possíveis do fluxo de execução."""

    PENDING = "pending"
    VALIDATING = "validating"
    FETCHING_DATA = "fetching_data"
    BUILDING_ITINERARY = "building_itinerary"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class WeatherData(BaseModel):
    """Dados meteorológicos retornados pela tool de clima."""

    cidade: str = ""
    temperatura_media: float = 0.0
    condicao: str = ""
    umidade: int = 0
    previsao_dias: list[dict] = Field(default_factory=list)
    fonte: str = "openweathermap"


class PointOfInterest(BaseModel):
    """Ponto de interesse turístico."""

    nome: str
    categoria: str
    descricao: str = ""
    avaliacao: float = 0.0
    endereco: str = ""
    horario_funcionamento: str = ""


class ItineraryDay(BaseModel):
    """Roteiro de um dia específico."""

    dia: int
    data: str
    periodo_manha: list[str] = Field(default_factory=list)
    periodo_tarde: list[str] = Field(default_factory=list)
    periodo_noite: list[str] = Field(default_factory=list)
    refeicoes_sugeridas: list[str] = Field(default_factory=list)
    clima_esperado: str = ""
    dicas: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    """Estado principal do agente - percorre todos os nodes do grafo.

    Atributos:
        messages: Histórico de mensagens (LangChain)
        destino: Cidade/região de destino
        data_inicio: Data de início da viagem
        data_fim: Data de fim da viagem
        preferencias: Lista de preferências do viajante
        orcamento: Faixa de orçamento
        restricoes: Restrições do viajante
        status: Status atual do fluxo
        weather_data: Dados meteorológicos coletados
        pontos_interesse: POIs encontrados
        roteiro: Roteiro montado dia a dia
        alertas: Avisos e alertas gerados
        errors: Erros ocorridos durante a execução
        retry_count: Contador de tentativas (para condição de parada)
        trace_id: ID de rastreamento da execução
        requires_human_approval: Se precisa de aprovação humana
        human_approved: Se o humano aprovou
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Entrada do usuário
    destino: str = ""
    data_inicio: str = ""
    data_fim: str = ""
    preferencias: list[str] = Field(default_factory=list)
    orcamento: str = "moderado"
    restricoes: list[str] = Field(default_factory=list)

    # Controle de fluxo
    status: FlowStatus = FlowStatus.PENDING
    retry_count: int = 0
    trace_id: str = ""
    requires_human_approval: bool = False
    human_approved: bool = False

    # Dados coletados pelas tools
    weather_data: WeatherData | None = None
    pontos_interesse: list[PointOfInterest] = Field(default_factory=list)

    # Saída
    roteiro: list[ItineraryDay] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
