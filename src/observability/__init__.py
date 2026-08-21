"""Módulo de observabilidade - logs estruturados, traces e métricas.

Dois sinais de observabilidade correlacionados:
1. Logs estruturados JSON (por node, com trace_id)
2. Traces completos (visão da execução inteira)

Ambos correlacionados pelo trace_id, permitindo investigar
qualquer execução da aplicação.
"""

from src.observability.logger import ExecutionTracer, StructuredLogger, get_logger
from src.observability.tracer import (
    get_metrics_summary,
    list_recent_traces,
    load_trace,
    save_trace,
)

__all__ = [
    "ExecutionTracer",
    "StructuredLogger",
    "get_logger",
    "save_trace",
    "load_trace",
    "list_recent_traces",
    "get_metrics_summary",
]
