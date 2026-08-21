"""Ponto de entrada principal da aplicação - API FastAPI."""

import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.graph import travel_agent_graph
from src.agent.state import AgentState, FlowStatus
from src.config import settings
from src.memory.checkpointer import (
    get_context_for_request,
    get_execution,
    get_user_history,
    log_interaction,
    save_execution,
    save_user_preference,
)
from src.observability.logger import ExecutionTracer, StructuredLogger
from src.observability.tracer import (
    get_metrics_summary,
    list_recent_traces,
    load_trace,
    save_trace,
)

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
    start_time = time.time()
    tracer = ExecutionTracer(trace_id="")

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
        with tracer.start_step("graph", "invoke_langgraph"):
            result = travel_agent_graph.invoke(initial_state.model_dump())
        tracer.trace_id = result.get("trace_id", "unknown")
    except Exception as e:
        tracer.record_step("graph", "invoke_langgraph", 0, "error", str(e))
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

    trace_id = result.get("trace_id", "")

    # Persistir execução na memória longa
    try:
        save_execution(
            trace_id=trace_id,
            destino=request.destino,
            data_inicio=request.data_inicio,
            data_fim=request.data_fim,
            preferencias=request.preferencias,
            orcamento=request.orcamento,
            status="completed",
            roteiro=roteiro_dicts,
            alertas=result.get("alertas", []),
        )
        log_interaction(
            action="criar_roteiro",
            input_summary=f"{request.destino} ({request.data_inicio} a {request.data_fim})",
            output_summary=f"{len(roteiro_dicts)} dias, {len(pois_dicts)} POIs",
            success=True,
            latency_ms=(time.time() - start_time) * 1000,
            trace_id=trace_id,
        )
        # Salvar trace completo
        save_trace(trace_id, tracer.get_summary())
    except Exception:
        pass  # Falha na persistência não deve impedir a resposta

    return TravelResponse(
        destino=result.get("destino", request.destino),
        periodo=f"{request.data_inicio} a {request.data_fim}",
        roteiro=roteiro_dicts,
        clima_previsto=weather,
        pontos_interesse=pois_dicts,
        alertas=result.get("alertas", []),
        trace_id=trace_id,
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


# --- Endpoints de Memória e Contexto ---


@app.get("/memoria/historico")
async def get_history(user_id: str = "default", limit: int = 10) -> dict:
    """Recupera histórico de roteiros anteriores do usuário."""
    history = get_user_history(user_id, limit)
    return {"user_id": user_id, "total": len(history), "executions": history}


@app.get("/memoria/contexto")
async def get_context(user_id: str = "default") -> dict:
    """Recupera contexto acumulado do usuário para enriquecer próximas solicitações."""
    context = get_context_for_request(user_id)
    return {"user_id": user_id, "context": context}


@app.get("/memoria/execucao/{trace_id}")
async def get_execution_by_trace(trace_id: str) -> dict:
    """Recupera detalhes de uma execução específica pelo trace_id."""
    execution = get_execution(trace_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"Execução {trace_id} não encontrada.")
    return execution


@app.post("/memoria/preferencias")
async def save_preference(user_id: str = "default", key: str = "", value: str = "") -> dict:
    """Salva uma preferência do usuário para uso futuro."""
    if not key or not value:
        raise HTTPException(status_code=422, detail="key e value são obrigatórios.")
    save_user_preference(user_id, key, value)
    return {"saved": True, "user_id": user_id, "key": key, "value": value}


# --- Endpoints de Segurança ---


@app.post("/seguranca/verificar")
async def security_check_endpoint(request: TravelRequest) -> dict:
    """Verifica segurança de uma entrada sem executar o fluxo."""
    from src.security.guardrails import full_security_check

    result = full_security_check(
        destino=request.destino,
        preferencias=request.preferencias,
        orcamento=request.orcamento,
        restricoes=request.restricoes,
    )
    return {
        "is_safe": result.is_safe,
        "level": result.level,
        "reason": result.reason,
        "blocked_patterns": result.blocked_patterns,
    }


@app.get("/seguranca/adversarial")
async def run_adversarial_endpoint() -> dict:
    """Executa cenários adversariais e retorna resultados de teste."""
    from src.security.adversarial import run_adversarial_tests

    results = run_adversarial_tests()
    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    return {
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


# --- Endpoints de Observabilidade ---


@app.get("/observabilidade/traces")
async def get_traces(limit: int = 20) -> dict:
    """Lista traces de execuções recentes."""
    traces = list_recent_traces(limit)
    return {"total": len(traces), "traces": traces}


@app.get("/observabilidade/trace/{trace_id}")
async def get_trace_detail(trace_id: str) -> dict:
    """Recupera trace completo de uma execução específica."""
    trace = load_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} não encontrado.")
    return trace


@app.get("/observabilidade/metricas")
async def get_metrics() -> dict:
    """Retorna métricas agregadas das execuções."""
    return get_metrics_summary()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
