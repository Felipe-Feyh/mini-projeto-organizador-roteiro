"""Logger estruturado JSON para observabilidade.

Produz logs estruturados com campos padronizados:
- timestamp: ISO 8601
- trace_id: ID de correlação da execução
- node: Nome do node do grafo em execução
- action: Ação realizada
- latency_ms: Tempo de execução
- status: success/error
- level: INFO/WARNING/ERROR

Permite investigar qualquer execução pelo trace_id.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.config import settings


# Configurar structlog para JSON
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

# Diretório para logs persistentes
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def get_logger(node: str = "", trace_id: str = "") -> structlog.stdlib.BoundLogger:
    """Cria um logger com contexto de node e trace_id.

    Args:
        node: Nome do node do grafo.
        trace_id: ID de correlação da execução.

    Returns:
        Logger bound com contexto.
    """
    logger = structlog.get_logger()
    if node:
        logger = logger.bind(node=node)
    if trace_id:
        logger = logger.bind(trace_id=trace_id)
    return logger


class StructuredLogger:
    """Logger estruturado que persiste logs em arquivo JSON.

    Garante correlação entre todos os eventos de uma execução
    através do trace_id compartilhado.
    """

    def __init__(self, trace_id: str, node: str = ""):
        self.trace_id = trace_id
        self.node = node
        self._logger = get_logger(node=node, trace_id=trace_id)
        self._log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def _persist(self, entry: dict) -> None:
        """Persiste entrada de log em arquivo JSONL."""
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Não falhar por causa de log

    def info(self, action: str, **kwargs: Any) -> None:
        """Log de informação."""
        entry = self._build_entry("INFO", action, "success", **kwargs)
        self._logger.info(action, **kwargs)
        self._persist(entry)

    def warning(self, action: str, **kwargs: Any) -> None:
        """Log de aviso."""
        entry = self._build_entry("WARNING", action, "warning", **kwargs)
        self._logger.warning(action, **kwargs)
        self._persist(entry)

    def error(self, action: str, **kwargs: Any) -> None:
        """Log de erro."""
        entry = self._build_entry("ERROR", action, "error", **kwargs)
        self._logger.error(action, **kwargs)
        self._persist(entry)

    def _build_entry(self, level: str, action: str, status: str, **kwargs: Any) -> dict:
        """Constrói entrada de log estruturada."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "trace_id": self.trace_id,
            "node": self.node,
            "action": action,
            "status": status,
            "environment": settings.app_env,
            **kwargs,
        }


class ExecutionTracer:
    """Rastreador de execução completa com métricas.

    Registra início, fim e latência de cada etapa do fluxo,
    permitindo reconstruir toda a execução pelo trace_id.
    """

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.start_time = time.time()
        self.steps: list[dict] = []
        self._logger = StructuredLogger(trace_id=trace_id, node="tracer")

    def start_step(self, node: str, action: str = "") -> "StepContext":
        """Inicia rastreamento de uma etapa.

        Returns:
            StepContext para uso com context manager.
        """
        return StepContext(self, node, action)

    def record_step(
        self,
        node: str,
        action: str,
        latency_ms: float,
        status: str = "success",
        error: str = "",
    ) -> None:
        """Registra uma etapa completa no trace."""
        step = {
            "trace_id": self.trace_id,
            "node": node,
            "action": action,
            "latency_ms": round(latency_ms, 2),
            "status": status,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step_number": len(self.steps) + 1,
        }
        self.steps.append(step)

        logger = StructuredLogger(trace_id=self.trace_id, node=node)
        if status == "error":
            logger.error(action, latency_ms=latency_ms, error=error)
        else:
            logger.info(action, latency_ms=latency_ms)

    def get_summary(self) -> dict:
        """Retorna resumo completo da execução."""
        total_latency = (time.time() - self.start_time) * 1000
        errors = [s for s in self.steps if s["status"] == "error"]

        return {
            "trace_id": self.trace_id,
            "total_steps": len(self.steps),
            "total_latency_ms": round(total_latency, 2),
            "errors_count": len(errors),
            "steps": self.steps,
            "started_at": datetime.fromtimestamp(
                self.start_time, tz=timezone.utc
            ).isoformat(),
        }


class StepContext:
    """Context manager para rastrear tempo de uma etapa."""

    def __init__(self, tracer: ExecutionTracer, node: str, action: str):
        self.tracer = tracer
        self.node = node
        self.action = action
        self.start_time = 0.0

    def __enter__(self) -> "StepContext":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        latency_ms = (time.time() - self.start_time) * 1000
        status = "error" if exc_type else "success"
        error = str(exc_val) if exc_val else ""
        self.tracer.record_step(
            node=self.node,
            action=self.action,
            latency_ms=latency_ms,
            status=status,
            error=error,
        )
