"""Guardrails de segurança e governança da aplicação.

Implementa:
- Sanitização de entradas
- Detecção de prompt injection
- Limites de autonomia
- Bloqueio de ações destrutivas
- Validação de permissões antes de executar tools
- Human-in-the-loop para ações sensíveis
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field


class SecurityLevel(str, Enum):
    """Níveis de segurança para ações do agente."""

    SAFE = "safe"  # Pode executar livremente
    REVIEW = "review"  # Requer revisão/log
    BLOCKED = "blocked"  # Bloqueado automaticamente
    HUMAN_APPROVAL = "human_approval"  # Requer aprovação humana


class SecurityCheckResult(BaseModel):
    """Resultado de uma verificação de segurança."""

    is_safe: bool
    level: SecurityLevel
    reason: str = ""
    blocked_patterns: list[str] = Field(default_factory=list)
    sanitized_input: str = ""


# Padrões de prompt injection conhecidos
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(todas?\s+)?(as\s+)?instru[çc][õo]es",
    r"you\s+are\s+now",
    r"voce\s+agora\s+[eé]",
    r"system\s*:",
    r"SYSTEM\s*:",
    r"reveal\s+(your|the)\s+(api|key|secret|password|token)",
    r"revele\s+(sua|a)\s+(chave|senha|api|token)",
    r"act\s+as\s+(a|an)",
    r"atue\s+como",
    r"forget\s+(all|everything)",
    r"esque[çc]a\s+tudo",
    r"override\s+(security|rules|permissions)",
    r"bypass\s+(security|auth|validation)",
    r"<script",
    r"javascript:",
    r"\{\{.*\}\}",
    r"__import__",
    r"eval\s*\(",
    r"exec\s*\(",
    r"os\.system",
    r"subprocess",
]

# Palavras-chave que indicam tentativa de extração de dados sensíveis
_SENSITIVE_EXTRACTION_PATTERNS: list[str] = [
    r"api[_\s]*key",
    r"secret[_\s]*key",
    r"password",
    r"senha",
    r"token",
    r"credencia",
    r"\.env",
    r"environment\s+variable",
    r"variavel\s+de\s+ambiente",
]

# Limites de autonomia
MAX_INPUT_LENGTH = 500
MAX_PREFERENCE_LENGTH = 100
MAX_PREFERENCES_COUNT = 10
ALLOWED_BUDGET_VALUES = {"economico", "moderado", "premium"}


def check_prompt_injection(text: str) -> SecurityCheckResult:
    """Verifica se o texto contém tentativas de prompt injection.

    Args:
        text: Texto a ser analisado.

    Returns:
        SecurityCheckResult com resultado da análise.
    """
    if not text:
        return SecurityCheckResult(
            is_safe=True,
            level=SecurityLevel.SAFE,
            sanitized_input="",
        )

    blocked_patterns = []
    text_lower = text.lower()

    # Verificar padrões de injection
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            blocked_patterns.append(pattern)

    # Verificar tentativa de extração de dados sensíveis
    for pattern in _SENSITIVE_EXTRACTION_PATTERNS:
        if re.search(pattern, text_lower):
            blocked_patterns.append(f"sensitive:{pattern}")

    if blocked_patterns:
        return SecurityCheckResult(
            is_safe=False,
            level=SecurityLevel.BLOCKED,
            reason=f"Prompt injection detectado: {len(blocked_patterns)} padrão(ões) suspeito(s)",
            blocked_patterns=blocked_patterns,
            sanitized_input="",
        )

    return SecurityCheckResult(
        is_safe=True,
        level=SecurityLevel.SAFE,
        sanitized_input=text,
    )


def sanitize_input(text: str) -> str:
    """Sanitiza entrada removendo caracteres perigosos.

    Args:
        text: Texto a ser sanitizado.

    Returns:
        Texto limpo e seguro.
    """
    if not text:
        return ""

    # Remover tags HTML/XML
    text = re.sub(r"<[^>]+>", "", text)

    # Remover caracteres de controle
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Limitar tamanho
    text = text[:MAX_INPUT_LENGTH]

    # Remover espaços múltiplos
    text = re.sub(r"\s+", " ", text).strip()

    return text


def validate_autonomy_limits(
    destino: str,
    preferencias: list[str],
    orcamento: str,
) -> SecurityCheckResult:
    """Valida limites de autonomia do agente.

    O agente NÃO pode:
    - Aceitar inputs muito longos
    - Aceitar mais de N preferências
    - Aceitar orçamentos fora do permitido
    - Executar sem destino válido

    Args:
        destino: Destino informado.
        preferencias: Lista de preferências.
        orcamento: Faixa de orçamento.

    Returns:
        SecurityCheckResult com resultado.
    """
    issues = []

    if len(destino) > MAX_INPUT_LENGTH:
        issues.append(f"Destino excede {MAX_INPUT_LENGTH} caracteres")

    if len(preferencias) > MAX_PREFERENCES_COUNT:
        issues.append(f"Máximo de {MAX_PREFERENCES_COUNT} preferências permitido")

    for pref in preferencias:
        if len(pref) > MAX_PREFERENCE_LENGTH:
            issues.append(f"Preferência excede {MAX_PREFERENCE_LENGTH} caracteres")
            break

    if orcamento.lower() not in ALLOWED_BUDGET_VALUES:
        issues.append(f"Orçamento inválido. Permitidos: {ALLOWED_BUDGET_VALUES}")

    if issues:
        return SecurityCheckResult(
            is_safe=False,
            level=SecurityLevel.BLOCKED,
            reason=f"Limites de autonomia violados: {'; '.join(issues)}",
        )

    return SecurityCheckResult(
        is_safe=True,
        level=SecurityLevel.SAFE,
    )


def check_destructive_action(action: str, target: str = "") -> SecurityCheckResult:
    """Verifica se uma ação é destrutiva e requer aprovação humana.

    Ações destrutivas (simuladas/bloqueadas):
    - Deletar roteiro salvo
    - Modificar preferências de outro usuário
    - Executar com credenciais de produção
    - Acesso a dados de outros usuários

    Args:
        action: Tipo de ação.
        target: Alvo da ação.

    Returns:
        SecurityCheckResult indicando se precisa aprovação.
    """
    destructive_actions = {
        "delete_execution": "Deletar execução do histórico",
        "delete_all_history": "Limpar todo o histórico",
        "modify_other_user": "Modificar dados de outro usuário",
        "export_sensitive": "Exportar dados sensíveis",
    }

    if action in destructive_actions:
        return SecurityCheckResult(
            is_safe=False,
            level=SecurityLevel.HUMAN_APPROVAL,
            reason=f"Ação destrutiva requer aprovação: {destructive_actions[action]}",
        )

    return SecurityCheckResult(
        is_safe=True,
        level=SecurityLevel.SAFE,
    )


def full_security_check(
    destino: str,
    preferencias: list[str],
    orcamento: str,
    restricoes: list[str] | None = None,
) -> SecurityCheckResult:
    """Executa verificação completa de segurança na entrada.

    Combina todas as verificações:
    1. Prompt injection no destino
    2. Prompt injection nas preferências
    3. Prompt injection nas restrições
    4. Limites de autonomia
    5. Sanitização

    Args:
        destino: Destino da viagem.
        preferencias: Preferências do viajante.
        orcamento: Faixa de orçamento.
        restricoes: Restrições opcionais.

    Returns:
        SecurityCheckResult consolidado.
    """
    # 1. Verificar prompt injection no destino
    result = check_prompt_injection(destino)
    if not result.is_safe:
        return result

    # 2. Verificar prompt injection nas preferências
    for pref in preferencias:
        result = check_prompt_injection(pref)
        if not result.is_safe:
            return result

    # 3. Verificar nas restrições
    if restricoes:
        for restricao in restricoes:
            result = check_prompt_injection(restricao)
            if not result.is_safe:
                return result

    # 4. Verificar limites de autonomia
    result = validate_autonomy_limits(destino, preferencias, orcamento)
    if not result.is_safe:
        return result

    # 5. Tudo OK - retornar sanitizado
    return SecurityCheckResult(
        is_safe=True,
        level=SecurityLevel.SAFE,
        sanitized_input=sanitize_input(destino),
    )
