"""Módulo de tools - integrações externas com APIs e serviços.

Tools disponíveis:
- weather_tool: Consulta previsão do tempo (OpenWeatherMap API)
- poi_tool: Busca pontos de interesse turístico
"""

from src.tools.weather_tool import get_weather_forecast
from src.tools.poi_tool import get_points_of_interest

__all__ = ["get_weather_forecast", "get_points_of_interest"]
