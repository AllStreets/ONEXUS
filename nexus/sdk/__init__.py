"""
NEXUS Plugin SDK -- scaffolding and validation for community modules and agents.
"""
from __future__ import annotations

from nexus.sdk.module_template import generate_module
from nexus.sdk.agent_template import generate_agent
from nexus.sdk.validator import PackageValidator, ValidationResult

__all__ = [
    "generate_module",
    "generate_agent",
    "PackageValidator",
    "ValidationResult",
]
