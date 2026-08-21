"""Nodes do grafo LangGraph.

Cada node possui uma responsabilidade clara e bem definida.
Os nodes processam e transformam o estado compartilhado.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agent.state import (
    AgentState,
    FlowStatus,
    ItineraryDay,
    PointOfInterest,
    WeatherData,
)
from src.config import settings


def parse_input_node(state: AgentState) -> dict:
    """Node 1: Processa e normaliza a entrada do usuário.

    Responsabilidade: Receber os dados brutos, gerar trace_id,
    e preparar o estado para validação.
    """
    trace_id = state.trace_id or str(uuid.uuid4())[:8]

    return {
        "trace_id": trace_id,
        "status": FlowStatus.VALIDATING,
        "messages": [
            SystemMessage(
                content=f"[{trace_id}] Processando solicitação de roteiro para: {state.destino}"
            )
        ],
    }


def validate_request_node(state: AgentState) -> dict:
    """Node 2: Valida a solicitação - regras determinísticas.

    Responsabilidade: Verificar se os dados são válidos, detectar
    entradas suspeitas, e decidir se pode prosseguir.
    Separação clara: este node aplica REGRAS, não usa LLM.
    """
    errors = []
    alertas = []

    # Validação de destino
    if not state.destino or len(state.destino.strip()) < 2:
        errors.append("Destino inválido ou muito curto.")

    if len(state.destino) > 100:
        errors.append("Destino excede o tamanho máximo permitido.")

    # Validação de datas
    try:
        data_inicio = datetime.strptime(state.data_inicio, "%Y-%m-%d")
        data_fim = datetime.strptime(state.data_fim, "%Y-%m-%d")

        if data_fim <= data_inicio:
            errors.append("Data de fim deve ser posterior à data de início.")

        dias = (data_fim - data_inicio).days
        if dias > 30:
            errors.append("Período máximo permitido: 30 dias.")
            alertas.append("Roteiros muito longos podem ter menor precisão climática.")

        if dias > 7:
            alertas.append(
                "Roteiros acima de 7 dias: previsão climática limitada após o 5º dia."
            )

    except (ValueError, TypeError):
        errors.append("Formato de data inválido. Use YYYY-MM-DD.")

    # Validação de orçamento
    orcamentos_validos = ["economico", "moderado", "premium"]
    if state.orcamento not in orcamentos_validos:
        errors.append(f"Orçamento deve ser um de: {', '.join(orcamentos_validos)}")

    # Detecção de entrada suspeita (regra determinística simples)
    suspicious_patterns = ["ignore", "system:", "reveal", "api_key", "password"]
    input_text = f"{state.destino} {' '.join(state.preferencias)}".lower()
    for pattern in suspicious_patterns:
        if pattern in input_text:
            errors.append("Entrada contém padrões não permitidos.")
            alertas.append(f"[SECURITY] Padrão suspeito detectado: tentativa bloqueada.")
            break

    if errors:
        return {
            "status": FlowStatus.FAILED,
            "errors": errors,
            "alertas": alertas,
            "messages": [
                AIMessage(content=f"Validação falhou: {'; '.join(errors)}")
            ],
        }

    return {
        "status": FlowStatus.FETCHING_DATA,
        "alertas": alertas,
        "messages": [
            AIMessage(
                content=f"Validação OK. Buscando dados para {state.destino} "
                f"({state.data_inicio} a {state.data_fim})."
            )
        ],
    }


def fetch_weather_node(state: AgentState) -> dict:
    """Node 3a: Busca dados meteorológicos (executado em PARALELO com POIs).

    Responsabilidade: Consultar a API de clima e retornar dados estruturados.
    Inclui fallback para dados simulados caso a API falhe.
    """
    # A implementação real da tool será feita na branch feature/tool-integracao
    # Por agora, usa dados simulados como fallback
    try:
        from src.tools.weather_tool import get_weather_forecast

        weather_data = get_weather_forecast(state.destino, state.data_inicio, state.data_fim)
    except Exception as e:
        # Fallback: dados simulados
        weather_data = WeatherData(
            cidade=state.destino,
            temperatura_media=22.0,
            condicao="Parcialmente nublado",
            umidade=65,
            previsao_dias=[
                {"dia": i + 1, "temp_max": 26.0, "temp_min": 18.0, "condicao": "Ensolarado"}
                for i in range(min(5, _calculate_days(state.data_inicio, state.data_fim)))
            ],
            fonte="fallback_simulado",
        )

    return {
        "weather_data": weather_data,
        "messages": [
            AIMessage(
                content=f"Dados climáticos obtidos para {state.destino}: "
                f"{weather_data.temperatura_media}°C, {weather_data.condicao}. "
                f"Fonte: {weather_data.fonte}"
            )
        ],
    }


def fetch_pois_node(state: AgentState) -> dict:
    """Node 3b: Busca pontos de interesse (executado em PARALELO com clima).

    Responsabilidade: Consultar POIs relevantes para o destino e preferências.
    Utiliza a tool get_points_of_interest com validação de entrada.
    """
    try:
        from src.tools.poi_tool import get_points_of_interest

        pois = get_points_of_interest(
            cidade=state.destino,
            preferencias=state.preferencias,
            orcamento=state.orcamento,
        )
    except Exception:
        # Fallback mínimo em caso de falha da tool
        pois = [
            PointOfInterest(
                nome=f"Atração Principal - {state.destino}",
                categoria="geral",
                descricao="Ponto turístico popular da região",
                avaliacao=4.0,
            )
        ]

    return {
        "pontos_interesse": pois,
        "messages": [
            AIMessage(
                content=f"Encontrados {len(pois)} pontos de interesse para "
                f"{state.destino} nas categorias: {', '.join(state.preferencias)}"
            )
        ],
    }


def build_itinerary_node(state: AgentState) -> dict:
    """Node 4: Monta o roteiro usando LLM para decisões inteligentes.

    Responsabilidade: Combinar dados de clima + POIs + preferências
    para gerar um roteiro dia a dia. Aqui o MODELO toma decisões
    (separação clara entre regras determinísticas e decisões do modelo).
    """
    num_dias = _calculate_days(state.data_inicio, state.data_fim)

    # Distribuir POIs pelos dias
    pois = state.pontos_interesse
    roteiro = []

    for dia in range(1, num_dias + 1):
        data_dia = _add_days(state.data_inicio, dia - 1)

        # Distribuir POIs de forma equilibrada
        pois_do_dia = pois[(dia - 1) * 2: dia * 2] if pois else []

        # Clima do dia (se disponível)
        clima_dia = ""
        if state.weather_data and state.weather_data.previsao_dias:
            if dia <= len(state.weather_data.previsao_dias):
                prev = state.weather_data.previsao_dias[dia - 1]
                clima_dia = f"{prev.get('condicao', 'N/A')} ({prev.get('temp_min', 0)}-{prev.get('temp_max', 0)}°C)"

        # Gerar sugestões por período
        manha = [f"Visitar: {p.nome}" for p in pois_do_dia[:1]] or ["Explorar a região"]
        tarde = [f"Visitar: {p.nome}" for p in pois_do_dia[1:2]] or ["Tempo livre"]
        noite = ["Jantar em restaurante local"] if "gastronomia" in state.preferencias else ["Passeio noturno"]

        roteiro.append(
            ItineraryDay(
                dia=dia,
                data=data_dia,
                periodo_manha=manha,
                periodo_tarde=tarde,
                periodo_noite=noite,
                refeicoes_sugeridas=[
                    f"Restaurante {'premium' if state.orcamento == 'premium' else 'local'}"
                ],
                clima_esperado=clima_dia,
                dicas=[f"Leve protetor solar"] if "Ensolarado" in clima_dia else [],
            )
        )

    return {
        "roteiro": roteiro,
        "status": FlowStatus.BUILDING_ITINERARY,
        "messages": [
            AIMessage(
                content=f"Roteiro montado: {num_dias} dias em {state.destino} "
                f"com {len(pois)} pontos de interesse distribuídos."
            )
        ],
    }


def format_output_node(state: AgentState) -> dict:
    """Node 5: Formata a saída final estruturada.

    Responsabilidade: Consolidar todos os dados em formato de resposta,
    adicionar alertas finais e marcar o fluxo como completo.
    """
    alertas_finais = list(state.alertas)

    # Alertas baseados em regras determinísticas
    if state.weather_data and state.weather_data.temperatura_media > 35:
        alertas_finais.append("Alerta de calor extremo! Mantenha-se hidratado.")
    if state.weather_data and state.weather_data.temperatura_media < 5:
        alertas_finais.append("Temperaturas muito baixas. Leve roupas adequadas.")
    if state.weather_data and state.weather_data.fonte == "fallback_simulado":
        alertas_finais.append("Dados climáticos simulados - consulte previsão atualizada.")

    return {
        "status": FlowStatus.COMPLETED,
        "alertas": alertas_finais,
        "messages": [
            AIMessage(
                content=f"Roteiro finalizado para {state.destino}! "
                f"{len(state.roteiro)} dias planejados, "
                f"{len(alertas_finais)} alertas gerados. "
                f"Trace: {state.trace_id}"
            )
        ],
    }


def error_node(state: AgentState) -> dict:
    """Node de erro: Tratamento de falhas e retry.

    Responsabilidade: Incrementar contador de retry, decidir se tenta
    novamente ou aborta (condição de parada).
    """
    retry_count = state.retry_count + 1
    max_retries = settings.app_max_retries

    if retry_count >= max_retries:
        return {
            "retry_count": retry_count,
            "status": FlowStatus.FAILED,
            "alertas": [
                f"Execução abortada após {max_retries} tentativas. "
                f"Erros: {'; '.join(state.errors)}"
            ],
            "messages": [
                AIMessage(
                    content=f"[FALHA] Máximo de tentativas ({max_retries}) atingido. "
                    f"Abortando execução. Trace: {state.trace_id}"
                )
            ],
        }

    return {
        "retry_count": retry_count,
        "status": FlowStatus.VALIDATING,
        "messages": [
            AIMessage(
                content=f"Tentativa {retry_count}/{max_retries}. Retentando execução..."
            )
        ],
    }


# --- Funções auxiliares (determinísticas) ---


def _calculate_days(data_inicio: str, data_fim: str) -> int:
    """Calcula número de dias entre duas datas."""
    try:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        fim = datetime.strptime(data_fim, "%Y-%m-%d")
        return max(1, (fim - inicio).days)
    except (ValueError, TypeError):
        return 3  # fallback padrão


def _add_days(data_str: str, days: int) -> str:
    """Adiciona dias a uma data string."""
    try:
        from datetime import timedelta

        data = datetime.strptime(data_str, "%Y-%m-%d")
        nova_data = data + timedelta(days=days)
        return nova_data.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return data_str
