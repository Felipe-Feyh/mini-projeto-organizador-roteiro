"""Módulo de configuração do LLM.

Suporta Groq (gratuito) e OpenAI como provedores.
O modelo é configurado via variável de ambiente LLM_PROVIDER.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from src.config import settings


def get_llm() -> BaseChatModel | None:
    """Retorna instância do LLM configurado.

    Prioridade: Groq (gratuito) > OpenAI > None (modo determinístico).

    Returns:
        Instância do ChatModel ou None se nenhuma key configurada.
    """
    # Em ambiente de teste, usa modo determinístico (sem chamadas externas)
    if settings.app_env == "testing":
        return None

    provider = settings.llm_provider.lower()

    if provider == "groq" and settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq

            return ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=0.3,
                max_tokens=2048,
            )
        except ImportError:
            pass

    if provider == "openai" and settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=0.3,
                max_tokens=2048,
            )
        except ImportError:
            pass

    # Fallback: tentar Groq mesmo se provider for outro
    if settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq

            return ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=0.3,
                max_tokens=2048,
            )
        except ImportError:
            pass

    # Nenhum LLM configurado - aplicação funciona em modo determinístico
    return None
