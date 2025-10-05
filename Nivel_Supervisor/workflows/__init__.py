"""
Workflows para automatización de CLAUDIO
"""

from .workflow_orchestrator import (
    homing_simple,
    inicio_simple,
    inicio_completo,
    inicio_completo_hard,
    cosecha_interactiva
)

__all__ = [
    'homing_simple',
    'inicio_simple',
    'inicio_completo',
    'inicio_completo_hard',
    'cosecha_interactiva'
]
