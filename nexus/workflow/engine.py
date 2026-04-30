"""
WorkflowEngine -- DAG-based executor for NEXUS module/agent pipelines.

Executes workflow steps in topological order, routes each step through Cortex,
handles variable substitution, conditional branching, and error policies.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.engram import Engram
    from nexus.kernel.aegis import Aegis
    from nexus.kernel.pulse import Pulse

try:
    from nexus.kernel.pulse import Message as _Message
except Exception:
    # Fallback for environments where Pulse can't be imported at module level
    # (e.g., Python 3.8 without __future__ annotations in pulse.py).
    from dataclasses import dataclass as _dataclass, field as _field
    import uuid as _uuid

    @_dataclass
    class _Message:  # type: ignore[no-redef]
        topic: str
        source: str
        payload: dict = _field(default_factory=dict)
        msg_id: str = _field(default_factory=lambda: _uuid.uuid4().hex[:12])

from nexus.workflow.conditions import ConditionEvaluator, ConditionError
from nexus.workflow.models import (
    Workflow,
    WorkflowStep,
    StepResult,
    WorkflowResult,
)


class WorkflowExecutionError(Exception):
    """Raised when a workflow execution encounters an unrecoverable error."""


class WorkflowEngine:
    """DAG-based workflow executor for NEXUS module/agent pipelines."""

    def __init__(
        self,
        cortex: Any,
        engram: Engram,
        chronicle: Chronicle,
        aegis: Aegis,
        pulse: Pulse,
    ) -> None:
        self._cortex = cortex
        self._engram = engram
        self._chronicle = chronicle
        self._aegis = aegis
        self._pulse = pulse
        self._condition_eval = ConditionEvaluator()

    # ── public API ─────────────────────────────────────────────

    async def execute(self, workflow: Workflow) -> WorkflowResult:
        """Execute a workflow DAG, respecting dependencies and conditions."""
        t0 = time.monotonic()
        variables = dict(workflow.variables)
        step_results: dict[str, StepResult] = {}
        execution_order = self._topological_sort(workflow)

        self._chronicle.log("workflow", "workflow.started", {
            "workflow": workflow.name,
            "steps": [s.name for s in workflow.steps],
        })
        await self._publish_event("workflow.started", {
            "workflow": workflow.name,
        })

        overall_success = True
        halted = False
        skip_descendants: set[str] = set()  # steps to skip due to upstream "skip" policy

        for step_name in execution_order:
            step = workflow.get_step(step_name)
            assert step is not None

            if halted:
                step_results[step_name] = StepResult(
                    step_name=step_name,
                    module=step.module,
                    output="",
                    success=False,
                    duration=0.0,
                    error="Workflow halted by prior step failure",
                    skipped=True,
                )
                continue

            # Skip steps whose upstream dependency failed with "skip" policy
            if step_name in skip_descendants:
                step_results[step_name] = StepResult(
                    step_name=step_name,
                    module=step.module,
                    output="",
                    success=True,
                    duration=0.0,
                    skipped=True,
                )
                # Propagate skip to this step's own dependents
                for other in workflow.steps:
                    if step_name in other.depends_on:
                        skip_descendants.add(other.name)
                self._chronicle.log("workflow", "step.skipped", {
                    "workflow": workflow.name,
                    "step": step_name,
                    "reason": "upstream dependency failed with skip policy",
                })
                await self._publish_event("workflow.step.completed", {
                    "workflow": workflow.name,
                    "step": step_name,
                    "skipped": True,
                })
                continue

            # Evaluate condition
            if step.condition:
                try:
                    condition_met = self._condition_eval.evaluate(
                        step.condition, step_results
                    )
                except ConditionError as exc:
                    condition_met = False
                    self._chronicle.log("workflow", "condition.error", {
                        "workflow": workflow.name,
                        "step": step_name,
                        "error": str(exc),
                    })

                if not condition_met:
                    step_results[step_name] = StepResult(
                        step_name=step_name,
                        module=step.module,
                        output="",
                        success=True,
                        duration=0.0,
                        skipped=True,
                    )
                    self._chronicle.log("workflow", "step.skipped", {
                        "workflow": workflow.name,
                        "step": step_name,
                        "reason": "condition not met",
                    })
                    await self._publish_event("workflow.step.completed", {
                        "workflow": workflow.name,
                        "step": step_name,
                        "skipped": True,
                    })
                    continue

            # Build inputs from dependency outputs
            inputs = self._gather_inputs(step, step_results, variables)

            # Execute
            result = await self.execute_step(step, inputs)
            step_results[step_name] = result

            # Store output as a variable for downstream substitution
            variables[f"{step_name}.output"] = result.output
            variables[f"{step_name}.success"] = str(result.success)

            self._chronicle.log("workflow", "step.completed", {
                "workflow": workflow.name,
                "step": step_name,
                "module": step.module,
                "success": result.success,
                "duration": result.duration,
                "error": result.error,
            })

            await self._publish_event("workflow.step.completed", {
                "workflow": workflow.name,
                "step": step_name,
                "success": result.success,
                "duration": result.duration,
            })

            if not result.success:
                overall_success = False
                if step.on_failure == "stop":
                    halted = True
                elif step.on_failure == "skip":
                    # Mark all downstream dependents for skipping
                    for other in workflow.steps:
                        if step_name in other.depends_on:
                            skip_descendants.add(other.name)
                # "continue" -- just keep going

        total_duration = time.monotonic() - t0

        wf_result = WorkflowResult(
            workflow_name=workflow.name,
            steps=list(step_results.values()),
            success=overall_success,
            total_duration=total_duration,
            variables=variables,
        )

        event_topic = "workflow.completed" if overall_success else "workflow.failed"
        self._chronicle.log("workflow", event_topic, {
            "workflow": workflow.name,
            "success": overall_success,
            "total_duration": total_duration,
        })
        await self._publish_event(event_topic, {
            "workflow": workflow.name,
            "success": overall_success,
            "total_duration": total_duration,
        })

        return wf_result

    async def execute_step(self, step: WorkflowStep, inputs: dict[str, str]) -> StepResult:
        """Execute a single workflow step by routing through Cortex."""
        message = self._render_template(step.message_template, inputs)
        t0 = time.monotonic()

        try:
            response = await asyncio.wait_for(
                self._cortex.process(message),
                timeout=step.timeout,
            )
            duration = time.monotonic() - t0
            # Consider Cortex error responses as failures
            success = not response.startswith("[Nexus]")
            return StepResult(
                step_name=step.name,
                module=step.module,
                output=response,
                success=success,
                duration=duration,
            )
        except asyncio.TimeoutError:
            duration = time.monotonic() - t0
            return StepResult(
                step_name=step.name,
                module=step.module,
                output="",
                success=False,
                duration=duration,
                error=f"Step timed out after {step.timeout}s",
            )
        except Exception as exc:
            duration = time.monotonic() - t0
            return StepResult(
                step_name=step.name,
                module=step.module,
                output="",
                success=False,
                duration=duration,
                error=str(exc),
            )

    # ── DAG utilities ──────────────────────────────────────────

    def _topological_sort(self, workflow: Workflow) -> list[str]:
        """Kahn's algorithm -- returns step names in execution order."""
        adj: dict[str, list[str]] = {s.name: [] for s in workflow.steps}
        in_degree: dict[str, int] = {s.name: 0 for s in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                adj[dep].append(step.name)
                in_degree[step.name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        # Sort the initial queue for deterministic ordering
        queue.sort()
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in sorted(adj[node]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort()

        if len(order) != len(workflow.steps):
            raise WorkflowExecutionError(
                "Cycle detected in workflow DAG -- topological sort incomplete"
            )
        return order

    # ── variable substitution ──────────────────────────────────

    _VAR_PATTERN = re.compile(r"\{([^}]+)\}")

    def _render_template(self, template: str, variables: dict[str, str]) -> str:
        """Replace {variable} placeholders in a message template."""
        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            return variables.get(key, match.group(0))
        return self._VAR_PATTERN.sub(replacer, template)

    def _gather_inputs(
        self,
        step: WorkflowStep,
        step_results: dict[str, StepResult],
        variables: dict[str, str],
    ) -> dict[str, str]:
        """Build the variable dict available for template rendering in this step."""
        inputs = dict(variables)
        for dep_name in step.depends_on:
            if dep_name in step_results:
                r = step_results[dep_name]
                inputs[f"{dep_name}.output"] = r.output
                inputs[f"{dep_name}.success"] = str(r.success)
                inputs[f"{dep_name}.error"] = r.error or ""
        return inputs

    # ── event publishing ───────────────────────────────────────

    async def _publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            await self._pulse.publish(_Message(
                topic=topic,
                source="workflow",
                payload=payload,
            ))
        except Exception:
            pass  # Never let Pulse errors break workflow execution
