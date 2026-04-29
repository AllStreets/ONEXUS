"""
Scaffold -- project boilerplate generator.
Generates complete project structures from natural language descriptions
including directory trees, config files, Docker setup, and starter code.

Inspired by:
  - cookiecutter/cookiecutter (BSD 3-Clause) — template-based project generation
  - hay-kot/scaffold (MIT) — in-project scaffolding for code patterns
  - pyscaffold/pyscaffold (MIT) — Python project template generator
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ProjectFile:
    path: str
    content: str
    description: str = ""


# Common project templates
_TEMPLATES: dict[str, dict[str, Any]] = {
    "python": {
        "files": [
            ("pyproject.toml", '[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n\n[build-system]\nrequires = ["setuptools>=68.0"]\nbuild-backend = "setuptools.backends._legacy:_Backend"'),
            ("src/{name}/__init__.py", '"""Top-level package for {name}."""\n__version__ = "0.1.0"'),
            ("src/{name}/main.py", 'def main():\n    print("Hello from {name}")\n\nif __name__ == "__main__":\n    main()'),
            ("tests/__init__.py", ""),
            ("tests/test_main.py", 'from {name}.main import main\n\ndef test_main(capsys):\n    main()\n    assert "Hello" in capsys.readouterr().out'),
            ("README.md", "# {name}\n\n{description}\n\n## Setup\n```bash\npip install -e .\n```\n\n## Test\n```bash\npytest tests/ -v\n```"),
            (".gitignore", "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/\n.pytest_cache/"),
        ],
        "keywords": ["python", "pip", "pytest", "package"],
    },
    "fastapi": {
        "files": [
            ("pyproject.toml", '[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = ["fastapi>=0.110", "uvicorn[standard]>=0.29"]\n\n[project.optional-dependencies]\ndev = ["pytest>=8.0", "httpx>=0.27"]'),
            ("src/app/main.py", 'from fastapi import FastAPI\n\napp = FastAPI(title="{name}")\n\n@app.get("/health")\nasync def health():\n    return {{"status": "ok"}}\n\n@app.get("/")\nasync def root():\n    return {{"message": "Welcome to {name}"}}'),
            ("src/app/__init__.py", ""),
            ("src/app/models.py", "from pydantic import BaseModel\n\n# Define your data models here"),
            ("src/app/routes/__init__.py", ""),
            ("tests/__init__.py", ""),
            ("tests/test_api.py", 'from fastapi.testclient import TestClient\nfrom app.main import app\n\nclient = TestClient(app)\n\ndef test_health():\n    r = client.get("/health")\n    assert r.status_code == 200\n    assert r.json()["status"] == "ok"'),
            ("Dockerfile", 'FROM python:3.12-slim\nWORKDIR /app\nCOPY pyproject.toml .\nRUN pip install .\nCOPY src/ src/\nEXPOSE 8000\nCMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]'),
            (".gitignore", "__pycache__/\n*.pyc\n.venv/\n.env\n"),
            ("README.md", "# {name}\n\n{description}\n\n## Run\n```bash\nuvicorn app.main:app --reload\n```\n\n## Test\n```bash\npytest tests/ -v\n```"),
        ],
        "keywords": ["fastapi", "api", "rest", "backend", "server", "endpoint"],
    },
    "cli": {
        "files": [
            ("pyproject.toml", '[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = ["click>=8.0"]\n\n[project.scripts]\n{name} = "{name}.cli:main"'),
            ("{name}/__init__.py", '__version__ = "0.1.0"'),
            ("{name}/cli.py", 'import click\n\n@click.group()\n@click.version_option()\ndef main():\n    """{description}"""\n    pass\n\n@main.command()\n@click.argument("name")\ndef greet(name: str):\n    """Greet someone."""\n    click.echo(f"Hello, {{name}}!")'),
            ("tests/__init__.py", ""),
            ("tests/test_cli.py", 'from click.testing import CliRunner\nfrom {name}.cli import main\n\ndef test_greet():\n    runner = CliRunner()\n    result = runner.invoke(main, ["greet", "World"])\n    assert result.exit_code == 0\n    assert "Hello, World!" in result.output'),
            (".gitignore", "__pycache__/\n*.pyc\n.venv/\ndist/\n"),
            ("README.md", "# {name}\n\n{description}\n\n## Install\n```bash\npip install -e .\n```\n\n## Usage\n```bash\n{name} greet World\n```"),
        ],
        "keywords": ["cli", "command", "terminal", "tool"],
    },
}


class ScaffoldModule(AgentModule):
    name = "scaffold"
    description = "Project boilerplate generator -- creates complete project structures from natural language descriptions"
    version = "0.1.0"

    watch_events: list[str] = []
    coordination_targets: list[str] = ["axiom"]

    def __init__(self):
        self._generated: list[dict[str, Any]] = []

    def detect_template(self, description: str) -> str:
        """Detect which template best matches the description."""
        desc_lower = description.lower()
        best_template = "python"
        best_score = 0

        for template_name, template in _TEMPLATES.items():
            score = sum(1 for kw in template["keywords"] if kw in desc_lower)
            if score > best_score:
                best_score = score
                best_template = template_name

        return best_template

    def extract_project_name(self, description: str) -> str:
        """Extract a project name from the description."""
        # Look for quoted names
        quoted = re.search(r'["\']([a-zA-Z_][a-zA-Z0-9_-]+)["\']', description)
        if quoted:
            return quoted.group(1).lower().replace('-', '_')

        # Look for "called X" or "named X"
        named = re.search(r'(?:called|named)\s+([a-zA-Z_]\w+)', description, re.IGNORECASE)
        if named:
            return named.group(1).lower().replace('-', '_')

        return "my_project"

    def generate(self, name: str, description: str, template: str) -> list[ProjectFile]:
        """Generate project files from a template."""
        tmpl = _TEMPLATES.get(template, _TEMPLATES["python"])
        files: list[ProjectFile] = []

        for path_template, content_template in tmpl["files"]:
            path = path_template.format(name=name, description=description)
            content = content_template.format(name=name, description=description)
            files.append(ProjectFile(path=path, content=content))

        return files

    def list_templates(self) -> list[str]:
        return list(_TEMPLATES.keys())

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Detect template and project name
        template = self.detect_template(message)
        name = self.extract_project_name(message)
        description = message.strip()[:200]

        # Generate files
        files = self.generate(name, description, template)

        # If LLM available, enhance with custom files
        if llm:
            prompt = (
                f"I'm scaffolding a {template} project called '{name}'.\n"
                f"Description: {description}\n\n"
                "Suggest 2-3 additional files that would be useful for this specific project. "
                "For each file, provide the path and brief content. "
                "Format: FILE: path/to/file\nCONTENT:\n<content>\nEND\n"
            )
            try:
                llm_response = await llm.complete(prompt)
                # Parse LLM suggestions
                file_blocks = re.findall(
                    r'FILE:\s*(.+?)\nCONTENT:\n(.*?)END',
                    llm_response, re.DOTALL
                )
                for path, content in file_blocks:
                    files.append(ProjectFile(
                        path=path.strip(),
                        content=content.strip(),
                        description="LLM-suggested",
                    ))
            except Exception:
                pass

        # Store record
        self._generated.append({
            "name": name,
            "template": template,
            "file_count": len(files),
        })

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Scaffolded project '{name}' using {template} template ({len(files)} files)",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Scaffold] Project '{name}' ({template} template)"]
        lines.append(f"  Files generated: {len(files)}")
        lines.append("")

        # Show directory tree
        lines.append("  Directory structure:")
        paths = sorted(f.path for f in files)
        for p in paths:
            depth = p.count('/')
            indent = "    " + "  " * depth
            basename = p.split('/')[-1]
            lines.append(f"{indent}{basename}")

        lines.append("")
        lines.append("  File contents:")
        for f in files:
            lines.append(f"\n  -- {f.path} --")
            preview = f.content[:300]
            for line in preview.split('\n'):
                lines.append(f"  | {line}")
            if len(f.content) > 300:
                lines.append("  | ...")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest scaffolding when a new project is being discussed."""
        new_project_indicators = ("new project", "start a", "create a", "build a", "scaffold", "boilerplate", "template")
        msg_lower = message.lower()
        if any(indicator in msg_lower for indicator in new_project_indicators):
            template = self.detect_template(message)
            return f"New project detected -- scaffold a {template} project structure to get started fast."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Scaffold has no background monitoring -- passive agent."""
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route scaffolded project to axiom for initial test stubs."""
        return "axiom: generate test stubs for the scaffolded project entry points"
