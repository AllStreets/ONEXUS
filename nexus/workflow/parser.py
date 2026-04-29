"""
YAML workflow parser for NEXUS.

Loads workflow definitions from YAML files or strings, validates the DAG
(references and cycles), and returns a Workflow object.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from nexus.workflow.models import Workflow, WorkflowStep


class WorkflowParseError(Exception):
    """Raised when a workflow YAML definition is invalid."""


class WorkflowParser:
    """Parse and validate YAML workflow definitions."""

    def parse_file(self, path: str | Path) -> Workflow:
        """Load a workflow from a YAML file on disk."""
        text = Path(path).read_text(encoding="utf-8")
        return self.parse_string(text)

    def parse_string(self, text: str) -> Workflow:
        """Parse a workflow from a YAML string."""
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise WorkflowParseError("Workflow YAML must be a mapping at the top level")
        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any]) -> Workflow:
        """Build a Workflow from a raw dictionary (already loaded from YAML/JSON)."""
        name = data.get("name")
        if not name:
            raise WorkflowParseError("Workflow must have a 'name' field")

        description = data.get("description", "")
        variables = data.get("variables", {})
        if not isinstance(variables, dict):
            raise WorkflowParseError("'variables' must be a mapping")

        raw_steps = data.get("steps")
        if not raw_steps or not isinstance(raw_steps, list):
            raise WorkflowParseError("Workflow must have a non-empty 'steps' list")

        steps = [self._parse_step(s, i) for i, s in enumerate(raw_steps)]

        # Validate
        self._validate_unique_names(steps)
        step_names = {s.name for s in steps}
        self._validate_dependencies(steps, step_names)
        self._validate_no_cycles(steps)

        return Workflow(
            name=str(name),
            description=str(description),
            steps=steps,
            variables={str(k): str(v) for k, v in variables.items()},
        )

    # ── step parsing ───────────────────────────────────────────

    def _parse_step(self, raw: Any, index: int) -> WorkflowStep:
        if not isinstance(raw, dict):
            raise WorkflowParseError(f"Step at index {index} must be a mapping")

        name = raw.get("name")
        if not name:
            raise WorkflowParseError(f"Step at index {index} missing 'name'")

        module = raw.get("module")
        if not module:
            raise WorkflowParseError(f"Step '{name}' missing 'module'")

        message = raw.get("message", raw.get("message_template", ""))
        if not message:
            raise WorkflowParseError(f"Step '{name}' missing 'message'")

        depends_on = raw.get("depends_on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        if not isinstance(depends_on, list):
            raise WorkflowParseError(f"Step '{name}': depends_on must be a list")

        condition = raw.get("condition")
        on_failure = raw.get("on_failure", "stop")
        timeout = raw.get("timeout", 60.0)

        return WorkflowStep(
            name=str(name),
            module=str(module),
            message_template=str(message),
            depends_on=[str(d) for d in depends_on],
            condition=str(condition) if condition else None,
            on_failure=str(on_failure),
            timeout=float(timeout),
        )

    # ── validation ─────────────────────────────────────────────

    def _validate_unique_names(self, steps: list[WorkflowStep]) -> None:
        seen: set[str] = set()
        for s in steps:
            if s.name in seen:
                raise WorkflowParseError(f"Duplicate step name: '{s.name}'")
            seen.add(s.name)

    def _validate_dependencies(
        self, steps: list[WorkflowStep], valid_names: set[str]
    ) -> None:
        for s in steps:
            for dep in s.depends_on:
                if dep not in valid_names:
                    raise WorkflowParseError(
                        f"Step '{s.name}' depends on '{dep}', which does not exist"
                    )
                if dep == s.name:
                    raise WorkflowParseError(
                        f"Step '{s.name}' depends on itself"
                    )

    def _validate_no_cycles(self, steps: list[WorkflowStep]) -> None:
        """Detect cycles using iterative DFS with three-color marking."""
        adj: dict[str, list[str]] = {s.name: list(s.depends_on) for s in steps}
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in adj}

        for start in adj:
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            color[start] = GRAY
            while stack:
                node, idx = stack.pop()
                neighbors = adj[node]
                if idx < len(neighbors):
                    stack.append((node, idx + 1))
                    neighbor = neighbors[idx]
                    if color[neighbor] == GRAY:
                        raise WorkflowParseError(
                            f"Circular dependency detected involving step '{neighbor}'"
                        )
                    if color[neighbor] == WHITE:
                        color[neighbor] = GRAY
                        stack.append((neighbor, 0))
                else:
                    color[node] = BLACK
