"""
Workflow -- DAG-based pipeline engine for NEXUS module/agent chains.
"""
from __future__ import annotations

from nexus.workflow.models import Workflow, WorkflowStep, StepResult, WorkflowResult
from nexus.workflow.parser import WorkflowParser
from nexus.workflow.conditions import ConditionEvaluator

# WorkflowEngine is imported lazily to avoid pulling in kernel modules
# (which may use syntax unsupported on Python <3.10 without __future__).


def _get_engine():
    from nexus.workflow.engine import WorkflowEngine
    return WorkflowEngine


__all__ = [
    "Workflow",
    "WorkflowStep",
    "StepResult",
    "WorkflowResult",
    "WorkflowEngine",
    "WorkflowParser",
    "ConditionEvaluator",
]


def __getattr__(name: str):
    if name == "WorkflowEngine":
        from nexus.workflow.engine import WorkflowEngine
        return WorkflowEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
