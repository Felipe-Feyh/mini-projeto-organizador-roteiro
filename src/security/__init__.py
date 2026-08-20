"""Módulo de segurança - guardrails, validações e governança.

Componentes:
- guardrails: Sanitização, prompt injection detection, limites de autonomia
- adversarial: Cenários de teste adversarial documentados
"""

from src.security.guardrails import (
    SecurityCheckResult,
    SecurityLevel,
    check_destructive_action,
    check_prompt_injection,
    full_security_check,
    sanitize_input,
    validate_autonomy_limits,
)
from src.security.adversarial import run_adversarial_tests, ADVERSARIAL_SCENARIOS

__all__ = [
    "SecurityCheckResult",
    "SecurityLevel",
    "check_prompt_injection",
    "sanitize_input",
    "validate_autonomy_limits",
    "check_destructive_action",
    "full_security_check",
    "run_adversarial_tests",
    "ADVERSARIAL_SCENARIOS",
]
