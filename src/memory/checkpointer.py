"""Checkpointer SQLite para persistência de estado entre sessões.

Permite que o agente mantenha histórico de execuções anteriores,
recupere preferências do usuário e continue de onde parou.

Estratégia de memória:
- Memória curta: state do LangGraph (durante execução)
- Memória longa: SQLite com histórico de roteiros e preferências
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings


DB_PATH = Path("data/memory.db")


def _ensure_db() -> sqlite3.Connection:
    """Garante que o banco existe e retorna conexão."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    """Cria tabelas do banco de memória se não existirem."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT UNIQUE NOT NULL,
            user_id TEXT DEFAULT 'default',
            destino TEXT NOT NULL,
            data_inicio TEXT,
            data_fim TEXT,
            preferencias TEXT,
            orcamento TEXT,
            status TEXT,
            roteiro_json TEXT,
            alertas_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, key)
        );

        CREATE TABLE IF NOT EXISTS interaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            trace_id TEXT,
            action TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            success INTEGER DEFAULT 1,
            latency_ms REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_executions_user ON executions(user_id);
        CREATE INDEX IF NOT EXISTS idx_executions_trace ON executions(trace_id);
        CREATE INDEX IF NOT EXISTS idx_history_user ON interaction_history(user_id);
    """)
    conn.commit()


# --- Funções de persistência de execuções ---


def save_execution(
    trace_id: str,
    destino: str,
    data_inicio: str,
    data_fim: str,
    preferencias: list[str],
    orcamento: str,
    status: str,
    roteiro: list[dict] | None = None,
    alertas: list[str] | None = None,
    user_id: str = "default",
) -> None:
    """Salva uma execução completa no banco de memória.

    Args:
        trace_id: ID de rastreamento da execução.
        destino: Destino da viagem.
        data_inicio: Data de início.
        data_fim: Data de fim.
        preferencias: Preferências do usuário.
        orcamento: Faixa de orçamento.
        status: Status final da execução.
        roteiro: Roteiro gerado (se houver).
        alertas: Alertas gerados.
        user_id: Identificador do usuário.
    """
    conn = _ensure_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO executions
               (trace_id, user_id, destino, data_inicio, data_fim,
                preferencias, orcamento, status, roteiro_json, alertas_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace_id,
                user_id,
                destino,
                data_inicio,
                data_fim,
                json.dumps(preferencias),
                orcamento,
                status,
                json.dumps(roteiro) if roteiro else None,
                json.dumps(alertas) if alertas else None,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_execution(trace_id: str) -> dict | None:
    """Recupera uma execução pelo trace_id.

    Args:
        trace_id: ID de rastreamento.

    Returns:
        Dicionário com os dados da execução, ou None se não encontrada.
    """
    conn = _ensure_db()
    try:
        row = conn.execute(
            "SELECT * FROM executions WHERE trace_id = ?", (trace_id,)
        ).fetchone()

        if row is None:
            return None

        return {
            "trace_id": row["trace_id"],
            "user_id": row["user_id"],
            "destino": row["destino"],
            "data_inicio": row["data_inicio"],
            "data_fim": row["data_fim"],
            "preferencias": json.loads(row["preferencias"]) if row["preferencias"] else [],
            "orcamento": row["orcamento"],
            "status": row["status"],
            "roteiro": json.loads(row["roteiro_json"]) if row["roteiro_json"] else None,
            "alertas": json.loads(row["alertas_json"]) if row["alertas_json"] else [],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def get_user_history(user_id: str = "default", limit: int = 10) -> list[dict]:
    """Recupera histórico de execuções de um usuário.

    Permite ao agente lembrar de viagens anteriores e adaptar sugestões.

    Args:
        user_id: Identificador do usuário.
        limit: Máximo de registros a retornar.

    Returns:
        Lista de execuções anteriores (mais recentes primeiro).
    """
    conn = _ensure_db()
    try:
        rows = conn.execute(
            """SELECT trace_id, destino, data_inicio, data_fim,
                      preferencias, orcamento, status, created_at
               FROM executions
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()

        return [
            {
                "trace_id": row["trace_id"],
                "destino": row["destino"],
                "data_inicio": row["data_inicio"],
                "data_fim": row["data_fim"],
                "preferencias": json.loads(row["preferencias"]) if row["preferencias"] else [],
                "orcamento": row["orcamento"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


# --- Funções de preferências do usuário ---


def save_user_preference(user_id: str, key: str, value: str) -> None:
    """Salva ou atualiza uma preferência do usuário.

    Exemplos de preferências:
    - destinos_favoritos: "Paris, Tokyo, Porto Alegre"
    - restricoes_alimentares: "vegetariano"
    - orcamento_padrao: "moderado"
    - estilo_viagem: "cultural"

    Args:
        user_id: Identificador do usuário.
        key: Chave da preferência.
        value: Valor da preferência.
    """
    conn = _ensure_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO user_preferences (user_id, key, value, updated_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, key, value, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_preferences(user_id: str = "default") -> dict[str, str]:
    """Recupera todas as preferências de um usuário.

    Args:
        user_id: Identificador do usuário.

    Returns:
        Dicionário chave→valor das preferências.
    """
    conn = _ensure_db()
    try:
        rows = conn.execute(
            "SELECT key, value FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        return {row["key"]: row["value"] for row in rows}
    finally:
        conn.close()


# --- Funções de histórico de interações ---


def log_interaction(
    action: str,
    input_summary: str = "",
    output_summary: str = "",
    success: bool = True,
    latency_ms: float = 0.0,
    trace_id: str = "",
    user_id: str = "default",
) -> None:
    """Registra uma interação no histórico para recuperação futura.

    Args:
        action: Tipo de ação (ex: "criar_roteiro", "consultar_clima").
        input_summary: Resumo da entrada.
        output_summary: Resumo da saída.
        success: Se a interação foi bem-sucedida.
        latency_ms: Latência em milissegundos.
        trace_id: ID de rastreamento.
        user_id: Identificador do usuário.
    """
    conn = _ensure_db()
    try:
        conn.execute(
            """INSERT INTO interaction_history
               (user_id, trace_id, action, input_summary, output_summary,
                success, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                trace_id,
                action,
                input_summary,
                output_summary,
                1 if success else 0,
                latency_ms,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_context_for_request(user_id: str = "default") -> dict[str, Any]:
    """Recupera contexto relevante para enriquecer uma nova solicitação.

    Combina histórico + preferências para que o agente possa:
    - Sugerir destinos baseados em viagens anteriores
    - Aplicar preferências salvas automaticamente
    - Evitar repetir destinos recentes

    Args:
        user_id: Identificador do usuário.

    Returns:
        Dicionário com contexto recuperado da memória.
    """
    preferences = get_user_preferences(user_id)
    history = get_user_history(user_id, limit=5)

    destinos_anteriores = [h["destino"] for h in history]
    preferencias_frequentes = {}

    for h in history:
        for pref in h.get("preferencias", []):
            preferencias_frequentes[pref] = preferencias_frequentes.get(pref, 0) + 1

    return {
        "user_preferences": preferences,
        "recent_destinations": destinos_anteriores,
        "frequent_preferences": dict(
            sorted(preferencias_frequentes.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "total_trips": len(history),
        "has_context": bool(preferences or history),
    }
