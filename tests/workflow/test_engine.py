"""Tests for nexus.workflow.engine."""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.workflow.engine import WorkflowEngine, WorkflowExecutionError
from nexus.workflow.models import Workflow, WorkflowStep, StepResult, WorkflowResult


# ── helpers ────────────────────────────────────────────────────

def _mock_cortex(responses: dict[str, str] | None = None):
    """Create a mock Cortex that returns predictable responses."""
    cortex = MagicMock()
    default = "module response"

    async def _process(message: str):
        if responses:
            for keyword, resp in responses.items():
                if keyword in message:
                    return resp
        return default

    cortex.process = AsyncMock(side_effect=_process)
    return cortex


def _mock_kernel(cortex=None):
    cortex = cortex or _mock_cortex()
    engram = MagicMock()
    chronicle = MagicMock()
    chronicle.log = MagicMock(return_value="evt123")
    aegis = MagicMock()
    pulse = MagicMock()
    pulse.publish = AsyncMock()
    return cortex, engram, chronicle, aegis, pulse


def _simple_workflow() -> Workflow:
    return Workflow(
        name="test_wf",
        description="test",
        steps=[
            WorkflowStep(name="s1", module="vex", message_template="scan target"),
            WorkflowStep(name="s2", module="arbiter", message_template="review {s1.output}", depends_on=["s1"]),
        ],
        variables={"target": "example.com"},
    )


# ── tests ──────────────────────────────────────────────────────

class TestTopologicalSort:
    @pytest.mark.asyncio
    async def test_linear_chain(self):
        cortex, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)
        wf = Workflow(
            name="linear",
            description="",
            steps=[
                WorkflowStep(name="c", module="m", message_template="x", depends_on=["b"]),
                WorkflowStep(name="a", module="m", message_template="x"),
                WorkflowStep(name="b", module="m", message_template="x", depends_on=["a"]),
            ],
        )
        order = engine._topological_sort(wf)
        assert order == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_diamond(self):
        cortex, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)
        wf = Workflow(
            name="diamond",
            description="",
            steps=[
                WorkflowStep(name="a", module="m", message_template="x"),
                WorkflowStep(name="b", module="m", message_template="x", depends_on=["a"]),
                WorkflowStep(name="c", module="m", message_template="x", depends_on=["a"]),
                WorkflowStep(name="d", module="m", message_template="x", depends_on=["b", "c"]),
            ],
        )
        order = engine._topological_sort(wf)
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")


class TestExecuteWorkflow:
    @pytest.mark.asyncio
    async def test_simple_two_step(self):
        cortex = _mock_cortex({"scan": "vulnerabilities found", "review": "looks bad"})
        cortex, engram, chronicle, aegis, pulse = _mock_kernel(cortex)
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        result = await engine.execute(_simple_workflow())

        assert result.workflow_name == "test_wf"
        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0].step_name == "s1"
        assert result.steps[0].output == "vulnerabilities found"
        assert result.steps[1].step_name == "s2"
        assert result.total_duration > 0

    @pytest.mark.asyncio
    async def test_chronicle_logging(self):
        cortex, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        await engine.execute(_simple_workflow())

        # Should log: workflow.started, step.completed x2, workflow.completed
        actions = [call.args[1] for call in chronicle.log.call_args_list]
        assert "workflow.started" in actions
        assert actions.count("step.completed") == 2
        assert "workflow.completed" in actions

    @pytest.mark.asyncio
    async def test_pulse_events(self):
        cortex, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        await engine.execute(_simple_workflow())

        topics = [call.args[0].topic for call in pulse.publish.call_args_list]
        assert "workflow.started" in topics
        assert "workflow.step.completed" in topics
        assert "workflow.completed" in topics

    @pytest.mark.asyncio
    async def test_variable_substitution(self):
        cortex = _mock_cortex()
        cortex, engram, chronicle, aegis, pulse = _mock_kernel(cortex)
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="vars",
            description="",
            steps=[
                WorkflowStep(name="s1", module="m", message_template="process {target}"),
            ],
            variables={"target": "myfile.py"},
        )
        await engine.execute(wf)
        # Cortex should have received the rendered message
        cortex.process.assert_called_once_with("process myfile.py")


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_on_failure_stop(self):
        cortex = MagicMock()
        cortex.process = AsyncMock(side_effect=RuntimeError("boom"))
        _, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="fail",
            description="",
            steps=[
                WorkflowStep(name="s1", module="m", message_template="x", on_failure="stop"),
                WorkflowStep(name="s2", module="m", message_template="y", depends_on=["s1"]),
            ],
        )
        result = await engine.execute(wf)
        assert result.success is False
        assert result.steps[0].success is False
        assert result.steps[0].error == "boom"
        # s2 should be skipped due to halt
        assert result.steps[1].skipped is True

    @pytest.mark.asyncio
    async def test_on_failure_continue(self):
        call_count = 0

        async def _process(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first fails")
            return "second ok"

        cortex = MagicMock()
        cortex.process = AsyncMock(side_effect=_process)
        _, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="cont",
            description="",
            steps=[
                WorkflowStep(name="s1", module="m", message_template="x", on_failure="continue"),
                WorkflowStep(name="s2", module="m", message_template="y"),
            ],
        )
        result = await engine.execute(wf)
        assert result.success is False  # overall fails because s1 failed
        assert result.steps[0].success is False
        assert result.steps[1].success is True
        assert result.steps[1].output == "second ok"

    @pytest.mark.asyncio
    async def test_timeout(self):
        async def _slow(msg):
            await asyncio.sleep(10)
            return "never"

        cortex = MagicMock()
        cortex.process = AsyncMock(side_effect=_slow)
        _, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="timeout",
            description="",
            steps=[
                WorkflowStep(name="s1", module="m", message_template="x", timeout=0.05),
            ],
        )
        result = await engine.execute(wf)
        assert result.steps[0].success is False
        assert "timed out" in result.steps[0].error

    @pytest.mark.asyncio
    async def test_cortex_error_response_detected(self):
        cortex = MagicMock()
        cortex.process = AsyncMock(return_value="[Nexus] Module 'm' encountered an error")
        _, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="cerr",
            description="",
            steps=[
                WorkflowStep(name="s1", module="m", message_template="x", on_failure="continue"),
            ],
        )
        result = await engine.execute(wf)
        assert result.steps[0].success is False


class TestConditionalExecution:
    @pytest.mark.asyncio
    async def test_condition_met(self):
        cortex = _mock_cortex({"scan": "found issues", "notify": "sent"})
        cortex, engram, chronicle, aegis, pulse = _mock_kernel(cortex)
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="cond",
            description="",
            steps=[
                WorkflowStep(name="scan", module="m", message_template="scan stuff"),
                WorkflowStep(
                    name="notify",
                    module="m",
                    message_template="notify about {scan.output}",
                    depends_on=["scan"],
                    condition="scan.success",
                ),
            ],
        )
        result = await engine.execute(wf)
        assert result.steps[1].skipped is False
        assert result.steps[1].output == "sent"

    @pytest.mark.asyncio
    async def test_condition_not_met(self):
        cortex = MagicMock()
        cortex.process = AsyncMock(side_effect=RuntimeError("fail"))
        _, engram, chronicle, aegis, pulse = _mock_kernel()
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        wf = Workflow(
            name="cond_skip",
            description="",
            steps=[
                WorkflowStep(name="scan", module="m", message_template="x", on_failure="continue"),
                WorkflowStep(
                    name="notify",
                    module="m",
                    message_template="y",
                    depends_on=["scan"],
                    condition="scan.success",
                ),
            ],
        )
        result = await engine.execute(wf)
        assert result.steps[1].skipped is True


class TestExecuteStep:
    @pytest.mark.asyncio
    async def test_execute_step_directly(self):
        cortex = _mock_cortex({"hello": "world"})
        cortex, engram, chronicle, aegis, pulse = _mock_kernel(cortex)
        engine = WorkflowEngine(cortex, engram, chronicle, aegis, pulse)

        step = WorkflowStep(name="s", module="m", message_template="hello {name}")
        result = await engine.execute_step(step, {"name": "nexus"})
        assert result.success is True
        assert result.output == "world"
        cortex.process.assert_called_once_with("hello nexus")
