"""Tests for nexus.workflow.parser."""
from __future__ import annotations

import textwrap

import pytest

from nexus.workflow.parser import WorkflowParser, WorkflowParseError


@pytest.fixture
def parser():
    return WorkflowParser()


VALID_YAML = textwrap.dedent("""\
    name: test_workflow
    description: A test workflow
    variables:
      target: example.com
    steps:
      - name: step_a
        module: vex
        message: "scan {target}"
        on_failure: continue
      - name: step_b
        module: bastion
        message: "check {target}"
        on_failure: continue
      - name: step_c
        module: arbiter
        message: "review {step_a.output} and {step_b.output}"
        depends_on: [step_a, step_b]
""")


class TestParseString:
    def test_valid_yaml(self, parser):
        wf = parser.parse_string(VALID_YAML)
        assert wf.name == "test_workflow"
        assert wf.description == "A test workflow"
        assert wf.variables == {"target": "example.com"}
        assert len(wf.steps) == 3
        assert wf.steps[2].depends_on == ["step_a", "step_b"]

    def test_minimal_yaml(self, parser):
        yaml_str = textwrap.dedent("""\
            name: minimal
            steps:
              - name: only
                module: vex
                message: hello
        """)
        wf = parser.parse_string(yaml_str)
        assert wf.name == "minimal"
        assert wf.steps[0].on_failure == "stop"

    def test_not_a_mapping(self, parser):
        with pytest.raises(WorkflowParseError, match="mapping"):
            parser.parse_string("- just a list")

    def test_missing_name(self, parser):
        with pytest.raises(WorkflowParseError, match="name"):
            parser.parse_string("description: no name here\nsteps:\n  - name: s\n    module: m\n    message: x")

    def test_missing_steps(self, parser):
        with pytest.raises(WorkflowParseError, match="steps"):
            parser.parse_string("name: x\n")


class TestStepValidation:
    def test_missing_module(self, parser):
        yaml_str = "name: x\nsteps:\n  - name: s\n    message: hi"
        with pytest.raises(WorkflowParseError, match="module"):
            parser.parse_string(yaml_str)

    def test_missing_message(self, parser):
        yaml_str = "name: x\nsteps:\n  - name: s\n    module: m"
        with pytest.raises(WorkflowParseError, match="message"):
            parser.parse_string(yaml_str)

    def test_duplicate_step_names(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: dup
                module: m
                message: a
              - name: dup
                module: m
                message: b
        """)
        with pytest.raises(WorkflowParseError, match="Duplicate"):
            parser.parse_string(yaml_str)


class TestDependencyValidation:
    def test_missing_dependency(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: s1
                module: m
                message: a
                depends_on: [nonexistent]
        """)
        with pytest.raises(WorkflowParseError, match="does not exist"):
            parser.parse_string(yaml_str)

    def test_self_dependency(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: s1
                module: m
                message: a
                depends_on: [s1]
        """)
        with pytest.raises(WorkflowParseError, match="depends on itself"):
            parser.parse_string(yaml_str)

    def test_circular_dependency(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: a
                module: m
                message: x
                depends_on: [b]
              - name: b
                module: m
                message: y
                depends_on: [a]
        """)
        with pytest.raises(WorkflowParseError, match="[Cc]ircular"):
            parser.parse_string(yaml_str)

    def test_three_node_cycle(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: a
                module: m
                message: x
                depends_on: [c]
              - name: b
                module: m
                message: y
                depends_on: [a]
              - name: c
                module: m
                message: z
                depends_on: [b]
        """)
        with pytest.raises(WorkflowParseError, match="[Cc]ircular"):
            parser.parse_string(yaml_str)


class TestStringDependsOn:
    def test_string_depends_on_converted_to_list(self, parser):
        yaml_str = textwrap.dedent("""\
            name: x
            steps:
              - name: a
                module: m
                message: hi
              - name: b
                module: m
                message: bye
                depends_on: a
        """)
        wf = parser.parse_string(yaml_str)
        assert wf.steps[1].depends_on == ["a"]
