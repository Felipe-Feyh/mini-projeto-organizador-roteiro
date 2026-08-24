"""Tool de consulta de clima - integração com OpenWeatherMap API.

Esta tool é integrada ao fluxo do agente LangGraph e consulta
a previsão do tempo para o destino da viagem.

Características:
- Validação de entradas e saídas com Pydantic
- Timeout configurável (padrão: 10s)
- Retry com exponential backoff (max 3 tentativas)
- Fallback para dados simulados em caso de falha
- Tratamento de erros estruturado
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.agent.state import WeatherData
from src.config import settings


# --- Schemas de validação (entrada/saída) ---


class WeatherToolInput(BaseModel):
    """Schema de entrada validado para a tool de clima."""

    cidade: str = Field(..., min_length=2, max_length=100, description="Nome da cidade")
    data_inicio: str = Field(..., description="Data de início (YYYY-MM-DD)")
    data_fim: str = Field(..., description="Data de fim (YYYY-MM-DD)")

    @field_validator("cidade")
    @classmethod
    def validate_cidade(cls, v: str) -> str:
        """Valida que o nome da cidade não contém caracteres suspeitos."""
        forbidden = ["<", ">", "{", "}", "script", "ignore", "system:"]
        for pattern in forbidden:
            if pattern.lower() in v.lower():
                raise ValueError(f"Cidade contém padrão não permitido: {pattern}")
        return v.strip()

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Valida formato de data YYYY-MM-DD."""
        from datetime import datetime

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Data inválida: {v}. Formato esperado: YYYY-MM-DD")
        return v


class WeatherToolOutput(BaseModel):
    """Schema de saída validado da tool de clima."""

    success: bool
    data: WeatherData | None = None
    error: str | None = None
    source: str = "openweathermap"
    latency_ms: float = 0.0


# --- Exceções customizadas ---


class WeatherAPIError(Exception):
    """Erro na comunicação com a API de clima."""

    pass


class WeatherAPITimeoutError(WeatherAPIError):
    """Timeout na comunicação com a API de clima."""

    pass


# --- Implementação da Tool ---


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, WeatherAPITimeoutError)),
    reraise=True,
)
def _call_weather_api_sync(cidade: str) -> dict:
    """Chama a API OpenWeatherMap de forma síncrona com retry e timeout.

    Args:
        cidade: Nome da cidade para consulta.

    Returns:
        Dados brutos da API.

    Raises:
        WeatherAPITimeoutError: Quando a API não responde no tempo.
        WeatherAPIError: Quando a API retorna erro.
    """
    api_key = settings.openweather_api_key
    timeout = settings.app_timeout_seconds

    if not api_key:
        raise WeatherAPIError("OPENWEATHER_API_KEY não configurada")

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": cidade,
        "appid": api_key,
        "units": "metric",
        "lang": "pt_br",
        "cnt": 40,  # 5 dias de previsão (8 intervalos por dia)
    }

    try:
        response = httpx.get(url, params=params, timeout=timeout)

        if response.status_code == 401:
            raise WeatherAPIError("API key inválida ou expirada")
        if response.status_code == 404:
            raise WeatherAPIError(f"Cidade não encontrada: {cidade}")
        if response.status_code >= 500:
            raise WeatherAPIError(f"Erro no servidor da API: {response.status_code}")

        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException:
        raise WeatherAPITimeoutError(
            f"Timeout ({timeout}s) ao consultar clima para {cidade}"
        )
    except httpx.HTTPStatusError as e:
        raise WeatherAPIError(f"Erro HTTP: {e.response.status_code}")


def _parse_weather_response(raw_data: dict, cidade: str) -> WeatherData:
    """Converte resposta bruta da API em WeatherData estruturado.

    Args:
        raw_data: Dados JSON brutos da API.
        cidade: Nome da cidade consultada.

    Returns:
        WeatherData com dados normalizados.
    """
    forecasts = raw_data.get("list", [])

    if not forecasts:
        return WeatherData(cidade=cidade, fonte="openweathermap_vazio")

    # Calcular médias
    temps = [f["main"]["temp"] for f in forecasts if "main" in f]
    humidades = [f["main"]["humidity"] for f in forecasts if "main" in f]

    temp_media = sum(temps) / len(temps) if temps else 0
    umidade_media = int(sum(humidades) / len(humidades)) if humidades else 0

    # Condição predominante
    condicoes = [
        f["weather"][0]["description"]
        for f in forecasts
        if f.get("weather")
    ]
    condicao_predominante = max(set(condicoes), key=condicoes.count) if condicoes else "N/A"

    # Previsão por dia (agrupar por data)
    previsao_dias = []
    dias_processados = set()

    for forecast in forecasts:
        data = forecast.get("dt_txt", "")[:10]
        if data and data not in dias_processados:
            dias_processados.add(data)
            temps_dia = [
                f["main"]["temp"]
                for f in forecasts
                if f.get("dt_txt", "").startswith(data)
            ]
            condicoes_dia = [
                f["weather"][0]["description"]
                for f in forecasts
                if f.get("dt_txt", "").startswith(data) and f.get("weather")
            ]

            previsao_dias.append({
                "dia": len(previsao_dias) + 1,
                "data": data,
                "temp_max": round(max(temps_dia), 1) if temps_dia else 0,
                "temp_min": round(min(temps_dia), 1) if temps_dia else 0,
                "condicao": condicoes_dia[0] if condicoes_dia else "N/A",
            })

    return WeatherData(
        cidade=cidade,
        temperatura_media=round(temp_media, 1),
        condicao=condicao_predominante,
        umidade=umidade_media,
        previsao_dias=previsao_dias[:7],  # Max 7 dias
        fonte="openweathermap",
    )


def _get_fallback_weather(cidade: str, data_inicio: str, data_fim: str) -> WeatherData:
    """Retorna dados climáticos simulados como fallback.

    Usado quando a API está indisponível ou sem configuração.
    """
    from datetime import datetime

    try:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        fim = datetime.strptime(data_fim, "%Y-%m-%d")
        num_dias = max(1, (fim - inicio).days)
    except (ValueError, TypeError):
        num_dias = 3

    previsao = []
    for i in range(min(num_dias, 7)):
        previsao.append({
            "dia": i + 1,
            "temp_max": 26.0 + (i % 3),
            "temp_min": 17.0 + (i % 2),
            "condicao": ["Ensolarado", "Parcialmente nublado", "Nublado"][i % 3],
        })

    return WeatherData(
        cidade=cidade,
        temperatura_media=22.5,
        condicao="Parcialmente nublado (dados simulados)",
        umidade=65,
        previsao_dias=previsao,
        fonte="fallback_simulado",
    )


# --- Função principal da Tool ---


def get_weather_forecast(
    cidade: str,
    data_inicio: str,
    data_fim: str,
) -> WeatherData:
    """Tool principal: obtém previsão do tempo para o destino.

    Fluxo:
    1. Valida entrada com Pydantic
    2. Tenta chamar API (com retry + timeout)
    3. Se falha → usa fallback simulado

    Args:
        cidade: Cidade de destino.
        data_inicio: Data de início (YYYY-MM-DD).
        data_fim: Data de fim (YYYY-MM-DD).

    Returns:
        WeatherData com a previsão (real ou fallback).
    """
    import time

    # 1. Validar entrada
    try:
        validated_input = WeatherToolInput(
            cidade=cidade,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
    except Exception:
        # Input inválido → fallback
        return _get_fallback_weather(cidade, data_inicio, data_fim)

    # 2. Tentar chamar API real (síncrono)
    start_time = time.time()
    try:
        raw_data = _call_weather_api_sync(validated_input.cidade)
        latency = (time.time() - start_time) * 1000
        weather_data = _parse_weather_response(raw_data, validated_input.cidade)
        return weather_data

    except (WeatherAPIError, WeatherAPITimeoutError, Exception) as e:
        # 3. Fallback
        return _get_fallback_weather(
            validated_input.cidade,
            validated_input.data_inicio,
            validated_input.data_fim,
        )
