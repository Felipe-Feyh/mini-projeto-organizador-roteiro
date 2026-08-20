"""Configurações centralizadas da aplicação via variáveis de ambiente."""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # API de Clima
    openweather_api_key: str = ""

    # App
    app_env: str = "development"
    app_log_level: str = "INFO"
    app_max_retries: int = 3
    app_timeout_seconds: int = 10

    # Webhooks
    webhook_url: str = ""
    discord_webhook_url: str = ""


settings = Settings()
