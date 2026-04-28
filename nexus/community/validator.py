"""
ModuleValidator — validates community module submissions.
Checks manifest schema, file structure, import restrictions, and test presence.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


REQUIRED_MANIFEST_FIELDS = {"name", "author", "description", "version", "tier", "keywords", "license"}
KERNEL_IMPORT_PATTERN = re.compile(r"from\s+nexus\.kernel|import\s+nexus\.kernel")
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ModuleValidator:
    def validate(self, module_dir: Path) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        manifest_path = module_dir / "manifest.json"
        module_path = module_dir / "module.py"
        tests_dir = module_dir / "tests"

        if not manifest_path.exists():
            errors.append("Missing manifest.json")
        if not module_path.exists():
            errors.append("Missing module.py")
        if not tests_dir.exists() or not tests_dir.is_dir():
            errors.append("Missing tests/ directory")
        elif not list(tests_dir.glob("test_*.py")):
            errors.append("No test files found in tests/ (must match test_*.py)")

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in manifest.json: {e}")
                return ValidationResult(valid=False, errors=errors, warnings=warnings)

            missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
            if missing:
                errors.append(f"Missing required manifest fields: {', '.join(sorted(missing))}")

            if manifest.get("tier") != "community":
                errors.append("Manifest tier must be 'community'")

            name = manifest.get("name", "")
            if name and not NAME_PATTERN.match(name):
                errors.append(f"Invalid module name '{name}' — must be lowercase, start with letter, alphanumeric + underscores only")

            desc = manifest.get("description", "")
            if len(desc) < 10:
                errors.append("Description must be at least 10 characters")

        if module_path.exists():
            source = module_path.read_text()
            if KERNEL_IMPORT_PATTERN.search(source):
                errors.append("Module imports from nexus.kernel — modules must use context dict only, no direct kernel imports")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
