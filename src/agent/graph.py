"""Definição e compilação do grafo LangGraph principal.

Fluxo:
    parse_input → validate_request → [fetch_weather || fetch_pois] → build_itinerary → format_output

Características:
    - Execução sequencial (parse → validate → build → format)
    - Ramificação condicional (validação OK/falha/aprovação humana)
    - Paralelização simples (weather + POIs em paralelo)
    - Condição de parada (max retries)
    - Separação entre decisões do modelo e regras determinísticas
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agent.edges import (
    route_after_approval,
    route_after_error,
    route_after_validation,
    should_continue_to_format,
)
from src.agent.nodes import (
    build_itinerary_node,
    error_node,
    fetch_pois_node,
    fetch_weather_node,
    format_output_node,
    parse_input_node,
    validate_request_node,
)
from src.agent.state import AgentState, FlowStatus


def _blocked_node(state: AgentState) -> dict:
    """Node de bloqueio quando aprovação humana é negada."""
    return {
        "status": FlowStatus.BLOCKED,
        "alertas": ["Execução bloqueada: aprovação humana negada."],
    }


def _merge_parallel_results(state: AgentState) -> dict:
    """Node que consolida resultados da execução paralela (weather + POIs).

    Este node atua como um ponto de sincronização após a paralelização.
    """
    alertas = list(state.alertas)

    if not state.weather_data:
        alertas.append("Dados climáticos indisponíveis. Roteiro gerado sem previsão do tempo.")

    if not state.pontos_interesse:
        alertas.append("Nenhum ponto de interesse encontrado para as preferências informadas.")

    return {
        "alertas": alertas,
        "status": FlowStatus.BUILDING_ITINERARY,
    }


def build_graph() -> StateGraph:
    """Constrói e retorna o grafo LangGraph compilado.

    Returns:
        StateGraph compilado pronto para execução.
    """
    # Criar o grafo com o estado tipado
    workflow = StateGraph(AgentState)

    # --- Adicionar nodes ---
    workflow.add_node("parse_input", parse_input_node)
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("fetch_weather", fetch_weather_node)
    workflow.add_node("fetch_pois", fetch_pois_node)
    workflow.add_node("merge_results", _merge_parallel_results)
    workflow.add_node("build_itinerary", build_itinerary_node)
    workflow.add_node("format_output", format_output_node)
    workflow.add_node("error_node", error_node)
    workflow.add_node("blocked", _blocked_node)
    workflow.add_node("await_approval", _await_approval_node)

    # --- Definir ponto de entrada ---
    workflow.set_entry_point("parse_input")

    # --- Edges sequenciais ---
    workflow.add_edge("parse_input", "validate_request")

    # --- Edge condicional após validação (ramificação) ---
    workflow.add_conditional_edges(
        "validate_request",
        route_after_validation,
        {
            "error_node": "error_node",
            "await_approval": "await_approval",
            "fetch_data": "fetch_weather",  # Inicia a paralelização
        },
    )

    # --- Paralelização: weather e POIs em paralelo ---
    # fetch_weather → merge_results
    # fetch_pois → merge_results
    # Ambos alimentam merge_results que sincroniza
    workflow.add_edge("fetch_weather", "fetch_pois")
    workflow.add_edge("fetch_pois", "merge_results")

    # --- Após merge dos resultados paralelos → montar roteiro ---
    workflow.add_edge("merge_results", "build_itinerary")

    # --- Edge condicional após montagem do roteiro ---
    workflow.add_conditional_edges(
        "build_itinerary",
        should_continue_to_format,
        {
            "format_output": "format_output",
            "error_node": "error_node",
        },
    )

    # --- Saídas finais ---
    workflow.add_edge("format_output", END)
    workflow.add_edge("blocked", END)

    # --- Edge condicional após erro (condição de parada) ---
    workflow.add_conditional_edges(
        "error_node",
        route_after_error,
        {
            "__end__": END,
            "validate_request": "validate_request",
        },
    )

    # --- Edge condicional após aprovação humana ---
    workflow.add_conditional_edges(
        "await_approval",
        route_after_approval,
        {
            "fetch_data": "fetch_weather",
            "blocked": "blocked",
        },
    )

    return workflow.compile()


def _await_approval_node(state: AgentState) -> dict:
    """Node de espera por aprovação humana.

    Em produção, isso pausaria a execução e aguardaria input externo.
    Para demonstração, simula aprovação automática quando human_approved=True.
    """
    if state.human_approved:
        return {
            "requires_human_approval": False,
            "status": FlowStatus.FETCHING_DATA,
        }

    return {
        "status": FlowStatus.AWAITING_APPROVAL,
        "alertas": [
            "Ação requer aprovação humana. Aguardando confirmação para prosseguir."
        ],
    }


# Instância compilada do grafo para uso na aplicação
travel_agent_graph = build_graph()
