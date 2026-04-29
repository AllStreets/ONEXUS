"""
Data models for the NEXUS workflow engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    """A single step in a workflow DAG."""
    name: str
    module: str
    message_template: str
    depends_on: list[str] = field(default_factory=list)
    condition: str | None = None
    on_failure: str = "stop"  # "stop", "skip", "continue"
    timeout: float = 60.0

    def __post_init__(self) -> None:
        if self.on_failure not in ("stop", "skip", "continue"):
            raise ValueError(
                f"Invalid on_failure policy '{self.on_failure}'; "
                f"must be 'stop', 'skip', or 'continue'"
            )


@dataclass
class Workflow:
    """A complete workflow definition -- a named DAG of steps."""
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)

    def step_names(self) -> set[str]:
        return {s.name for s in self.steps}

    def get_step(self, name: str) -> WorkflowStep | None:
        for s in self.steps:
            if s.name == name:
                return s
        return None


@dataclass
class StepResult:
    """Outcome of executing a single workflow step."""
    step_name: str
    module: str
    output: str
    success: bool
    duration: float
    error: str | None = None
    skipped: bool = False


@dataclass
class WorkflowResult:
    """Outcome of executing an entire workflow."""
    workflow_name: str
    steps: list[StepResult] = field(default_factory=list)
    success: bool = True
    total_duration: float = 0.0
    variables: dict[str, str] = field(default_factory=dict)
