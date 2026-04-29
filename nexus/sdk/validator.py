"""
Package validator for NEXUS community modules and agents.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of a package validation run."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Required manifest fields (matching community/manifest_schema.json)
_MANIFEST_REQUIRED = {"name", "author", "description", "version", "tier", "keywords", "license"}

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# Imports that community packages must never use
_KERNEL_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+nexus\.kernel\b",
    re.MULTILINE,
)


class PackageValidator:
    """Validates community module/agent packages before submission."""

    def validate(self, path: str) -> ValidationResult:
        """Run all validation checks on a package directory."""
        errors: list[str] = []
        warnings: list[str] = []

        errors.extend(self.check_manifest(path))
        errors.extend(self.check_code(path))
        errors.extend(self.check_tests(path))
        errors.extend(self.check_readme(path))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def check_manifest(self, path: str) -> list[str]:
        """Validate manifest.json schema."""
        errors: list[str] = []
        manifest_path = os.path.join(path, "manifest.json")

        if not os.path.isfile(manifest_path):
            errors.append("manifest.json not found")
            return errors

        try:
            with open(manifest_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json is not valid JSON: {exc}")
            return errors

        # Check required fields
        missing = _MANIFEST_REQUIRED - set(data.keys())
        if missing:
            errors.append(f"manifest.json missing required fields: {', '.join(sorted(missing))}")

        # Validate field values
        name = data.get("name", "")
        if name and not _NAME_PATTERN.match(name):
            errors.append(f"manifest.json 'name' must match ^[a-z][a-z0-9_]*$ (got '{name}')")

        version = data.get("version", "")
        if version and not _VERSION_PATTERN.match(version):
            errors.append(f"manifest.json 'version' must be semver (got '{version}')")

        desc = data.get("description", "")
        if isinstance(desc, str):
            if len(desc) < 10:
                errors.append("manifest.json 'description' must be at least 10 characters")
            if len(desc) > 200:
                errors.append("manifest.json 'description' must be at most 200 characters")

        tier = data.get("tier")
        if tier and tier != "community":
            errors.append(f"manifest.json 'tier' must be 'community' (got '{tier}')")

        keywords = data.get("keywords")
        if keywords is not None:
            if not isinstance(keywords, list) or len(keywords) < 1:
                errors.append("manifest.json 'keywords' must be a non-empty array")

        return errors

    def check_code(self, path: str) -> list[str]:
        """Check code structure -- correct base class, required methods, no kernel imports."""
        errors: list[str] = []

        # Determine package type from manifest
        manifest_path = os.path.join(path, "manifest.json")
        is_agent = False
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path) as f:
                    data = json.load(f)
                is_agent = data.get("type") == "agent"
            except (json.JSONDecodeError, KeyError):
                pass

        if is_agent:
            code_file = os.path.join(path, "agent.py")
            expected_base = "AgentModule"
            required_methods = ["analyze"]
        else:
            code_file = os.path.join(path, "module.py")
            expected_base = "NexusModule"
            required_methods = ["handle"]

        if not os.path.isfile(code_file):
            errors.append(f"{os.path.basename(code_file)} not found")
            return errors

        with open(code_file) as f:
            source = f.read()

        # Check base class
        if expected_base not in source:
            errors.append(f"{os.path.basename(code_file)} must subclass {expected_base}")

        # Check required methods
        for method in required_methods:
            # Match 'async def method(' or 'def method('
            pattern = re.compile(rf"\bdef\s+{method}\s*\(")
            if not pattern.search(source):
                errors.append(f"{os.path.basename(code_file)} must implement {method}()")

        # Check for kernel imports
        if _KERNEL_IMPORT_PATTERN.search(source):
            errors.append(f"{os.path.basename(code_file)} must not import from nexus.kernel")

        return errors

    def check_tests(self, path: str) -> list[str]:
        """Verify tests exist and meet minimum count."""
        errors: list[str] = []

        tests_dir = os.path.join(path, "tests")
        if not os.path.isdir(tests_dir):
            errors.append("tests/ directory not found")
            return errors

        # Find test files
        test_files = [
            f for f in os.listdir(tests_dir)
            if f.startswith("test_") and f.endswith(".py")
        ]
        if not test_files:
            errors.append("No test files found in tests/")
            return errors

        # Count test functions across all test files
        test_count = 0
        for tf in test_files:
            with open(os.path.join(tests_dir, tf)) as f:
                source = f.read()
            test_count += len(re.findall(r"\bdef\s+test_\w+\s*\(", source))

        # Determine minimum from manifest type
        manifest_path = os.path.join(path, "manifest.json")
        is_agent = False
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path) as f:
                    data = json.load(f)
                is_agent = data.get("type") == "agent"
            except (json.JSONDecodeError, KeyError):
                pass

        min_tests = 6 if is_agent else 4
        if test_count < min_tests:
            errors.append(f"Found {test_count} test(s), minimum is {min_tests}")

        return errors

    def check_readme(self, path: str) -> list[str]:
        """Verify README exists and has content."""
        errors: list[str] = []

        readme_path = os.path.join(path, "README.md")
        if not os.path.isfile(readme_path):
            errors.append("README.md not found")
            return errors

        with open(readme_path) as f:
            content = f.read().strip()

        if len(content) < 50:
            errors.append("README.md must have meaningful content (at least 50 characters)")

        return errors
