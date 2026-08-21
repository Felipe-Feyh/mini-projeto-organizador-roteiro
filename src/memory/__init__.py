"""Módulo de memória - persistência e recuperação de contexto.

Estratégia:
- Memória curta: AgentState do LangGraph (durante execução do grafo)
- Memória longa: SQLite com histórico de roteiros, preferências e interações
- Recuperação contextual: combina preferências + histórico para enriquecer requests
"""

from src.memory.checkpointer import (
    get_context_for_request,
    get_execution,
    get_user_history,
    get_user_preferences,
    log_interaction,
    save_execution,
    save_user_preference,
)

__all__ = [
    "save_execution",
    "get_execution",
    "get_user_history",
    "save_user_preference",
    "get_user_preferences",
    "log_interaction",
    "get_context_for_request",
]
