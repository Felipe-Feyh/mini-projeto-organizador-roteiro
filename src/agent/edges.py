"""Edges condicionais do grafo LangGraph.

Define as rotas e condições de transição entre nodes,
incluindo ramificação condicional e condição de parada.
"""

from __future__ import annotations

from src.agent.state import AgentState, FlowStatus


def route_after_validation(state: AgentState) -> str:
    """Edge condicional após validação.

    Decide o próximo passo baseado no resultado da validação:
    - Se falhou → vai para error_node
    - Se precisa aprovação humana → vai para human_approval
    - Se válido → vai para fetch_data (paralelização)
    """
    if state.status == FlowStatus.FAILED:
        return "error_node"

    if state.requires_human_approval:
        return "await_approval"

    return "fetch_data"


def route_after_error(state: AgentState) -> str:
    """Edge condicional após tratamento de erro.

    Condição de parada: se atingiu máximo de retries, finaliza.
    Caso contrário, volta para validação (retry).
    """
    if state.status == FlowStatus.FAILED:
        # Condição de parada: máximo de retries atingido
        return "__end__"

    # Retry: volta para validação
    return "validate_request"


def route_after_approval(state: AgentState) -> str:
    """Edge condicional após aprovação humana.

    - Se aprovado → prossegue para fetch_data
    - Se rejeitado → bloqueia execução
    """
    if state.human_approved:
        return "fetch_data"

    return "blocked"


def should_continue_to_format(state: AgentState) -> str:
    """Edge condicional após montagem do roteiro.

    Verifica se o roteiro foi gerado com sucesso.
    """
    if state.roteiro and len(state.roteiro) > 0:
        return "format_output"

    return "error_node"
