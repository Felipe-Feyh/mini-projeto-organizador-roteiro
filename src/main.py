"""Ponto de entrada principal da aplicação - API FastAPI."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
    """Endpoint principal - gera um roteiro de viagem personalizado."""
    # Será implementado com o grafo LangGraph na próxima fase
    raise HTTPException(status_code=501, detail="Fluxo LangGraph será implementado na próxima fase")


@app.post("/roteiro/validar")
async def validate_request(request: TravelRequest) -> dict:
    """Endpoint para validar uma solicitação antes de processar."""
    return {
        "valid": True,
        "destino": request.destino,
        "dias": "cálculo será implementado",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
