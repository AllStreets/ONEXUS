"""Tests for nexus.workflow.models."""
from __future__ import annotations

import pytest

from nexus.workflow.models import Workflow, WorkflowStep, StepResult, WorkflowResult


class TestWorkflowStep:
    def test_defaults(self):
        step = WorkflowStep(name="s1", module="vex", message_template="scan")
        assert step.depends_on == []
        assert step.condition is None
        assert step.on_failure == "stop"
        assert step.timeout == 60.0

    def test_invalid_on_failure(self):
        with pytest.raises(ValueError, match="Invalid on_failure"):
            WorkflowStep(name="s1", module="vex", message_template="x", on_failure="crash")

    def test_valid_on_failure_values(self):
        for policy in ("stop", "skip", "continue"):
            step = WorkflowStep(name="s", module="m", message_template="x", on_failure=policy)
            assert step.on_failure == policy


class TestWorkflow:
    def test_step_names(self):
        wf = Workflow(
            name="test",
            description="d",
            steps=[
                WorkflowStep(name="a", module="m", message_template="x"),
                WorkflowStep(name="b", module="m", message_template="y"),
            ],
        )
        assert wf.step_names() == {"a", "b"}

    def test_get_step(self):
        step = WorkflowStep(name="alpha", module="m", message_template="x")
        wf = Workflow(name="test", description="d", steps=[step])
        assert wf.get_step("alpha") is step
        assert wf.get_step("missing") is None


class TestStepResult:
    def test_defaults(self):
        r = StepResult(step_name="s", module="m", output="ok", success=True, duration=1.0)
        assert r.error is None
        assert r.skipped is False


class TestWorkflowResult:
    def test_defaults(self):
        r = WorkflowResult(workflow_name="wf")
        assert r.steps == []
        assert r.success is True
        assert r.total_duration == 0.0
        assert r.variables == {}
