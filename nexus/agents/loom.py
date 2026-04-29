"""
Loom -- data pipeline and ETL workflow builder.
Defines, validates, and visualizes data transformation pipelines
with dependency resolution and execution planning.

Inspired by:
  - apache/airflow (Apache 2.0) -- workflow orchestration platform
  - spotify/luigi (Apache 2.0) -- batch job pipeline builder
  - PrefectHQ/prefect (Apache 2.0) -- workflow orchestration framework
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class PipelineStep:
    name: str
    operation: str  # "extract", "transform", "load", "validate", "filter", "join"
    source: str
    target: str
    config: dict[str, str] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Pipeline:
    name: str
    steps: list[PipelineStep]
    execution_order: list[str]
    is_valid: bool
    errors: list[str]


# Common ETL operation patterns
_OPERATION_KEYWORDS: dict[str, list[str]] = {
    "extract": ["extract", "read", "fetch", "pull", "ingest", "source"],
    "transform": ["transform", "convert", "map", "clean", "normalize", "parse"],
    "load": ["load", "write", "insert", "push", "sink", "output", "export"],
    "validate": ["validate", "check", "verify", "test", "assert"],
    "filter": ["filter", "where", "select", "exclude", "remove"],
    "join": ["join", "merge", "combine", "union", "enrich"],
}


class LoomModule(AgentModule):
    name = "loom"
    description = "Data pipeline builder -- defines ETL workflows with dependency resolution and validation"
    version = "0.1.0"

    watch_events: list[str] = []
    coordination_targets: list[str] = []

    def __init__(self):
        self._pipelines: list[Pipeline] = []

    @staticmethod
    def detect_operation(text: str) -> str:
        """Detect the ETL operation type from text."""
        text_lower = text.lower()
        for op, keywords in _OPERATION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return op
        return "transform"

    @staticmethod
    def parse_steps(text: str) -> list[PipelineStep]:
        """Parse pipeline steps from text description."""
        steps: list[PipelineStep] = []

        # Match numbered or bulleted steps
        step_pattern = r'(?:^|\n)\s*(?:\d+[.)]\s*|[-*]\s*)(.+)'
        matches = re.findall(step_pattern, text)

        for i, match in enumerate(matches):
            match = match.strip()
            name = f"step_{i + 1}"

            # Try to extract a name
            name_match = re.match(r'^(\w[\w\s]+?)(?:\s*[-:]\s*|\s*\()', match)
            if name_match:
                name = name_match.group(1).strip().lower().replace(' ', '_')

            # Detect operation
            operation = LoomModule.detect_operation(match)

            # Extract source/target
            source = ""
            target = ""
            arrow_match = re.search(r'(\S+)\s*(?:->|-->|=>)\s*(\S+)', match)
            if arrow_match:
                source = arrow_match.group(1)
                target = arrow_match.group(2)
            else:
                from_match = re.search(r'from\s+(\S+)', match, re.IGNORECASE)
                to_match = re.search(r'(?:to|into)\s+(\S+)', match, re.IGNORECASE)
                if from_match:
                    source = from_match.group(1)
                if to_match:
                    target = to_match.group(1)

            steps.append(PipelineStep(
                name=name, operation=operation,
                source=source, target=target,
            ))

        # Set implicit dependencies (sequential)
        for i in range(1, len(steps)):
            steps[i].depends_on = [steps[i - 1].name]

        return steps

    @staticmethod
    def topological_sort(steps: list[PipelineStep]) -> tuple[list[str], list[str]]:
        """Resolve execution order using topological sort."""
        graph: dict[str, list[str]] = {s.name: list(s.depends_on) for s in steps}
        all_names = {s.name for s in steps}
        errors: list[str] = []

        # Check for missing dependencies
        for name, deps in graph.items():
            for dep in deps:
                if dep not in all_names:
                    errors.append(f"Step '{name}' depends on unknown step '{dep}'")

        if errors:
            return [], errors

        # Kahn's algorithm
        in_degree: dict[str, int] = {name: 0 for name in all_names}
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    pass  # dep is a prerequisite, we count edges into dependents
        for name, deps in graph.items():
            in_degree[name] = len(deps)

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            queue.sort()
            node = queue.pop(0)
            order.append(node)
            for name, deps in graph.items():
                if node in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        if len(order) != len(all_names):
            errors.append("Circular dependency detected in pipeline")

        return order, errors

    def create_pipeline(self, name: str, steps: list[PipelineStep]) -> Pipeline:
        """Create and validate a pipeline."""
        execution_order, errors = self.topological_sort(steps)
        pipeline = Pipeline(
            name=name, steps=steps,
            execution_order=execution_order,
            is_valid=len(errors) == 0, errors=errors,
        )
        self._pipelines.append(pipeline)
        return pipeline

    @staticmethod
    def visualize(pipeline: Pipeline) -> str:
        """Create a text visualization of the pipeline."""
        if not pipeline.steps:
            return "  (empty pipeline)"

        lines: list[str] = []
        for i, step_name in enumerate(pipeline.execution_order):
            step = next((s for s in pipeline.steps if s.name == step_name), None)
            if not step:
                continue
            prefix = "  " if i == 0 else "  |-> "
            source = f" [{step.source}]" if step.source else ""
            target = f" -> [{step.target}]" if step.target else ""
            lines.append(f"{prefix}{step.name} ({step.operation}){source}{target}")

        return "\n".join(lines)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        steps = self.parse_steps(message)

        if not steps:
            if llm:
                prompt = (
                    "Design a data pipeline for the following requirement:\n\n"
                    f"{message[:3000]}\n\n"
                    "Provide:\n"
                    "1. Pipeline steps (extract, transform, load)\n"
                    "2. Data sources and sinks\n"
                    "3. Validation and error handling\n"
                    "4. Execution order"
                )
                try:
                    design = await llm.complete(prompt)
                    return f"[Loom] Pipeline Design\n\n{design[:2000]}"
                except Exception:
                    pass
            return "[Loom] Describe pipeline steps using numbered or bulleted lists."

        # Extract pipeline name
        name_match = re.search(r'(?:pipeline|workflow|etl)\s*[:\-]\s*(\w[\w\s]+)', message, re.IGNORECASE)
        pipeline_name = name_match.group(1).strip() if name_match else "pipeline_1"

        pipeline = self.create_pipeline(pipeline_name, steps)
        visualization = self.visualize(pipeline)

        if engram:
            try:
                engram.episodic.store(
                    f"Pipeline '{pipeline_name}': {len(steps)} steps, "
                    f"valid={pipeline.is_valid}",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Loom] Pipeline: {pipeline.name}"]
        lines.append(f"  Steps: {len(pipeline.steps)}")
        lines.append(f"  Valid: {'Yes' if pipeline.is_valid else 'No'}")

        if pipeline.errors:
            lines.append(f"\n  Errors:")
            for err in pipeline.errors:
                lines.append(f"    X {err}")

        lines.append(f"\n  Execution Order:")
        lines.append(visualization)

        # Step details
        lines.append(f"\n  Step Details:")
        for step in pipeline.steps:
            lines.append(f"    {step.name}:")
            lines.append(f"      Operation: {step.operation}")
            if step.source:
                lines.append(f"      Source: {step.source}")
            if step.target:
                lines.append(f"      Target: {step.target}")
            if step.depends_on:
                lines.append(f"      Depends on: {', '.join(step.depends_on)}")

        if llm:
            prompt = (
                f"Review this ETL pipeline and suggest improvements:\n\n"
                + "\n".join(f"- {s.name}: {s.operation} ({s.source} -> {s.target})" for s in steps)
                + "\n\nSuggest: error handling, retry logic, monitoring points."
            )
            try:
                review = await llm.complete(prompt)
                lines.append(f"\n  -- Suggestions --\n  {review[:1000]}")
            except Exception:
                pass

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        if re.search(
            r'\b(extract|transform|load|ingest|pipeline|etl|workflow|process|clean|normalize)\b',
            message, re.IGNORECASE
        ):
            return "Describe your data processing steps as a numbered list and Loom will build an ETL pipeline."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        return ""
