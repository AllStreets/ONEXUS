"""
Axiom -- automated test case generator.
Analyzes code and generates unit test stubs, edge cases,
and test scenarios for Python functions and classes.

Inspired by:
  - se2p/pynguin (LGPL 3.0) -- Python automated unit test generator
  - laffra/auger (Apache 2.0) -- automated unittest generation
  - herchila/unittest-ai-agent (MIT) -- AI-powered test generation
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class FunctionSignature:
    name: str
    params: list[str]
    return_type: str
    is_async: bool
    docstring: str


@dataclass
class GeneratedTest:
    function: str
    name: str
    description: str
    code: str
    category: str  # "happy_path", "edge_case", "error", "boundary"


# Common edge cases by parameter type hint
_EDGE_CASES: dict[str, list[str]] = {
    "str": ['""', '"hello"', '" "', '"a" * 1000', 'None'],
    "int": ["0", "1", "-1", "2**31 - 1", "-(2**31)"],
    "float": ["0.0", "1.0", "-1.0", "float('inf')", "float('nan')"],
    "list": ["[]", "[1]", "[1, 2, 3]", "list(range(100))"],
    "dict": ["{}", '{"key": "value"}', '{i: i for i in range(100)}'],
    "bool": ["True", "False"],
    "None": ["None"],
}


class AxiomModule(AgentModule):
    name = "axiom"
    description = "Test case generator -- creates unit test stubs, edge cases, and scenarios from code"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["carve"]

    def __init__(self):
        self._generated: list[dict[str, Any]] = []

    @staticmethod
    def extract_functions(code: str) -> list[FunctionSignature]:
        """Extract function signatures from Python code."""
        functions: list[FunctionSignature] = []

        pattern = r'(async\s+)?def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*(\w[\w\[\], ]*))?\s*:'
        for match in re.finditer(pattern, code, re.DOTALL):
            is_async = bool(match.group(1))
            name = match.group(2)
            params_str = match.group(3)
            return_type = match.group(4) or ""

            # Parse params
            params: list[str] = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param and param != "self" and param != "cls":
                        params.append(param)

            # Extract docstring
            docstring = ""
            func_start = match.end()
            doc_match = re.search(r'"""(.*?)"""', code[func_start:func_start + 500], re.DOTALL)
            if not doc_match:
                doc_match = re.search(r"'''(.*?)'''", code[func_start:func_start + 500], re.DOTALL)
            if doc_match:
                docstring = doc_match.group(1).strip()

            functions.append(FunctionSignature(
                name=name, params=params, return_type=return_type,
                is_async=is_async, docstring=docstring,
            ))

        return functions

    @staticmethod
    def generate_test_cases(func: FunctionSignature) -> list[GeneratedTest]:
        """Generate test cases for a function."""
        cases: list[GeneratedTest] = []
        prefix = "async " if func.is_async else ""
        await_kw = "await " if func.is_async else ""
        decorator = "@pytest.mark.asyncio\n" if func.is_async else ""

        # Happy path test
        cases.append(GeneratedTest(
            function=func.name,
            name=f"test_{func.name}_basic",
            description=f"Test basic functionality of {func.name}",
            code=(
                f"{decorator}    {prefix}def test_{func.name}_basic():\n"
                f"        result = {await_kw}{func.name}()\n"
                f"        assert result is not None"
            ),
            category="happy_path",
        ))

        # Parameter-based edge cases
        for param in func.params:
            param_name = param.split(':')[0].strip().split('=')[0].strip()
            type_hint = ""
            if ':' in param:
                type_hint = param.split(':')[1].strip().split('=')[0].strip().lower()

            edge_values = _EDGE_CASES.get(type_hint, [])
            if edge_values:
                for val in edge_values[:2]:
                    cases.append(GeneratedTest(
                        function=func.name,
                        name=f"test_{func.name}_{param_name}_{val.replace(' ', '_')[:20]}",
                        description=f"Test {func.name} with {param_name}={val}",
                        code=(
                            f"{decorator}    {prefix}def test_{func.name}_{param_name}_edge():\n"
                            f"        result = {await_kw}{func.name}({param_name}={val})\n"
                            f"        # Assert expected behavior"
                        ),
                        category="edge_case",
                    ))

            # None test for any param
            cases.append(GeneratedTest(
                function=func.name,
                name=f"test_{func.name}_{param_name}_none",
                description=f"Test {func.name} with None for {param_name}",
                code=(
                    f"{decorator}    {prefix}def test_{func.name}_{param_name}_none():\n"
                    f"        with pytest.raises((TypeError, ValueError)):\n"
                    f"            {await_kw}{func.name}({param_name}=None)"
                ),
                category="error",
            ))

        # Return type test
        if func.return_type:
            cases.append(GeneratedTest(
                function=func.name,
                name=f"test_{func.name}_return_type",
                description=f"Test {func.name} returns {func.return_type}",
                code=(
                    f"{decorator}    {prefix}def test_{func.name}_return_type():\n"
                    f"        result = {await_kw}{func.name}()\n"
                    f"        assert isinstance(result, {func.return_type})"
                ),
                category="happy_path",
            ))

        return cases

    @staticmethod
    def format_test_file(func_name: str, cases: list[GeneratedTest]) -> str:
        """Format test cases into a test file."""
        lines = [
            "import pytest",
            f"# Auto-generated tests for {func_name}",
            "",
        ]
        for case in cases:
            lines.append(f"\n{case.code}")
            lines.append("")
        return "\n".join(lines)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        functions = self.extract_functions(message)

        if not functions:
            if llm:
                prompt = (
                    "Generate comprehensive unit tests for the following code:\n\n"
                    f"```python\n{message[:4000]}\n```\n\n"
                    "Include:\n"
                    "1. Happy path tests\n"
                    "2. Edge cases (empty inputs, None, boundaries)\n"
                    "3. Error cases (invalid inputs)\n"
                    "4. Use pytest style with descriptive names"
                )
                try:
                    tests = await llm.complete(prompt)
                    return f"[Axiom] Generated Tests\n\n{tests[:3000]}"
                except Exception:
                    pass
            return "[Axiom] Provide Python function code to generate test cases."

        all_cases: list[GeneratedTest] = []
        for func in functions:
            cases = self.generate_test_cases(func)
            all_cases.extend(cases)

        self._generated.append({"functions": len(functions), "cases": len(all_cases)})

        if engram:
            try:
                engram.episodic.store(
                    f"Tests generated: {len(all_cases)} cases for {len(functions)} functions",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Axiom] Test Cases Generated"]
        lines.append(f"  Functions found: {len(functions)}")
        lines.append(f"  Test cases: {len(all_cases)}")

        for func in functions:
            func_cases = [c for c in all_cases if c.function == func.name]
            lines.append(f"\n  {func.name}({', '.join(func.params)}):")
            by_cat: dict[str, list[GeneratedTest]] = {}
            for c in func_cases:
                by_cat.setdefault(c.category, []).append(c)
            for cat, cases in by_cat.items():
                lines.append(f"    {cat}: {len(cases)} cases")

        lines.append(f"\n  -- Generated Code --")
        for func in functions[:3]:
            func_cases = [c for c in all_cases if c.function == func.name]
            test_code = self.format_test_file(func.name, func_cases[:5])
            lines.append(f"\n{test_code[:1000]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest test generation when functions are present but no tests are mentioned."""
        has_functions = bool(self.extract_functions(message))
        has_test_mention = any(kw in message for kw in ("test", "pytest", "unittest", "assert"))
        if has_functions and not has_test_mention:
            funcs = self.extract_functions(message)
            count = len(funcs)
            return f"{count} function(s) found with no test coverage mentioned -- generate test stubs now."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Flag cortex responses containing function definitions with no test mentions."""
        response = event.get("data", {}).get("response", "")
        funcs = self.extract_functions(response)
        if funcs and not any(kw in response for kw in ("test", "pytest", "assert")):
            names = ", ".join(f.name for f in funcs[:4])
            return (
                f"Cortex response defines {len(funcs)} function(s) ({names}) "
                f"with no associated tests -- test generation recommended."
            )
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route tested functions to carve to check complexity before finalising."""
        return "carve: measure complexity of the functions being tested -- simplify any that score high before finalising"
