"""Ponto de entrada principal da aplicação - API FastAPI."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.graph import travel_agent_graph
from src.agent.state import AgentState, FlowStatus
from src.config import settings

app = FastAPI(
    title="Organizador Inteligente de Roteiros de Viagem",
    description="Agente IA que organiza roteiros de viagem personalizados usando LangGraph",
    version="1.0.0",
)


class TravelRequest(BaseModel):
    """Schema de entrada para solicitação de roteiro."""

    destino: str = Field(..., min_length=2, max_length=100, description="Cidade/região de destino")
    data_inicio: str = Field(..., description="Data de início (YYYY-MM-DD)")
    data_fim: str = Field(..., description="Data de fim (YYYY-MM-DD)")
    preferencias: list[str] = Field(
        default_factory=list,
        description="Preferências do viajante (ex: cultura, gastronomia, aventura)",
    )
    orcamento: str = Field(
        default="moderado",
        description="Faixa de orçamento: economico, moderado, premium",
    )
    restricoes: list[str] = Field(
        default_factory=list,
        description="Restrições (ex: acessibilidade, alimentares)",
    )


class TravelResponse(BaseModel):
    """Schema de saída do roteiro gerado."""

    destino: str
    periodo: str
    roteiro: list[dict]
    clima_previsto: dict
    pontos_interesse: list[dict]
    alertas: list[str]
    trace_id: str


@app.get("/health")
async def health_check() -> dict:
    """Endpoint de saúde da aplicação."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.post("/roteiro", response_model=TravelResponse)
async def create_itinerary(request: TravelRequest) -> TravelResponse:
    """Endpoint principal - gera um roteiro de viagem personalizado.

    Executa o grafo LangGraph completo:
    parse_input → validate → [weather || pois] → build_itinerary → format_output
    """
    # Preparar estado inicial
    initial_state = AgentState(
        destino=request.destino,
        data_inicio=request.data_inicio,
        data_fim=request.data_fim,
        preferencias=request.preferencias,
        orcamento=request.orcamento,
        restricoes=request.restricoes,
    )

    # Executar o grafo LangGraph
    try:
        result = travel_agent_graph.invoke(initial_state.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro na execução do agente: {str(e)}",
        )

    # Verificar se o fluxo falhou
    if result.get("status") == FlowStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail={
                "errors": result.get("errors", []),
                "alertas": result.get("alertas", []),
                "trace_id": result.get("trace_id", ""),
            },
        )

    if result.get("status") == FlowStatus.BLOCKED:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Execução bloqueada - aprovação humana negada",
                "trace_id": result.get("trace_id", ""),
            },
        )

    # Montar resposta estruturada
    weather = result.get("weather_data") or {}
    if hasattr(weather, "model_dump"):
        weather = weather.model_dump()

    pois = result.get("pontos_interesse", [])
    pois_dicts = [p.model_dump() if hasattr(p, "model_dump") else p for p in pois]

    roteiro = result.get("roteiro", [])
    roteiro_dicts = [r.model_dump() if hasattr(r, "model_dump") else r for r in roteiro]

    return TravelResponse(
        destino=result.get("destino", request.destino),
        periodo=f"{request.data_inicio} a {request.data_fim}",
        roteiro=roteiro_dicts,
        clima_previsto=weather,
        pontos_interesse=pois_dicts,
        alertas=result.get("alertas", []),
        trace_id=result.get("trace_id", ""),
    )


@app.post("/roteiro/validar")
async def validate_request(request: TravelRequest) -> dict:
    """Endpoint para validar uma solicitação antes de processar."""
    from datetime import datetime

    try:
        inicio = datetime.strptime(request.data_inicio, "%Y-%m-%d")
        fim = datetime.strptime(request.data_fim, "%Y-%m-%d")
        dias = (fim - inicio).days
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de data inválido.")

    return {
        "valid": True,
        "destino": request.destino,
        "dias": dias,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
