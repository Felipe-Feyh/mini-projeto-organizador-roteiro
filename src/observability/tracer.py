"""Módulo de traces e métricas para correlação de execuções.

Implementa o segundo sinal de observabilidade (trace) que, combinado
com os logs estruturados, permite reconstruir qualquer execução.

Sinais produzidos:
1. Logs estruturados JSON (logger.py) - por node/ação
2. Traces correlacionados (este módulo) - visão completa da execução
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACES_DIR = Path("logs/traces")
TRACES_DIR.mkdir(parents=True, exist_ok=True)


def save_trace(trace_id: str, trace_data: dict) -> None:
    """Persiste um trace completo em arquivo JSON.

    Args:
        trace_id: ID de correlação.
        trace_data: Dados completos do trace.
    """
    trace_file = TRACES_DIR / f"{trace_id}.json"
    try:
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_trace(trace_id: str) -> dict | None:
    """Carrega um trace pelo ID.

    Args:
        trace_id: ID de correlação.

    Returns:
        Dados do trace ou None se não encontrado.
    """
    trace_file = TRACES_DIR / f"{trace_id}.json"
    if not trace_file.exists():
        return None

    try:
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_recent_traces(limit: int = 20) -> list[dict]:
    """Lista traces recentes.

    Args:
        limit: Máximo de traces a retornar.

    Returns:
        Lista de resumos de traces.
    """
    trace_files = sorted(TRACES_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    traces = []

    for trace_file in trace_files[:limit]:
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                traces.append({
                    "trace_id": data.get("trace_id", trace_file.stem),
                    "total_steps": data.get("total_steps", 0),
                    "total_latency_ms": data.get("total_latency_ms", 0),
                    "errors_count": data.get("errors_count", 0),
                    "started_at": data.get("started_at", ""),
                })
        except Exception:
            continue

    return traces


def get_metrics_summary() -> dict:
    """Calcula métricas agregadas dos traces disponíveis.

    Returns:
        Dicionário com métricas: total execuções, latência média,
        taxa de erro, nodes mais lentos.
    """
    traces = []
    for trace_file in TRACES_DIR.glob("*.json"):
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                traces.append(json.load(f))
        except Exception:
            continue

    if not traces:
        return {
            "total_executions": 0,
            "avg_latency_ms": 0,
            "error_rate": 0,
            "node_latencies": {},
        }

    total = len(traces)
    latencies = [t.get("total_latency_ms", 0) for t in traces]
    errors = sum(1 for t in traces if t.get("errors_count", 0) > 0)

    # Latência por node
    node_latencies: dict[str, list[float]] = {}
    for trace in traces:
        for step in trace.get("steps", []):
            node = step.get("node", "unknown")
            lat = step.get("latency_ms", 0)
            node_latencies.setdefault(node, []).append(lat)

    avg_node_latencies = {
        node: round(sum(lats) / len(lats), 2)
        for node, lats in node_latencies.items()
    }

    return {
        "total_executions": total,
        "avg_latency_ms": round(sum(latencies) / total, 2) if total else 0,
        "max_latency_ms": round(max(latencies), 2) if latencies else 0,
        "min_latency_ms": round(min(latencies), 2) if latencies else 0,
        "error_rate": round(errors / total * 100, 2) if total else 0,
        "node_avg_latencies": avg_node_latencies,
    }
