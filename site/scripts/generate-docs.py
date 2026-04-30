"""
generate-docs.py — AST-based documentation generator for NEXUS.

Parses nexus/modules/ and nexus/kernel/ source files without importing them,
then writes Starlight-compatible Markdown pages to:
  site/src/content/docs/reference/modules/
  site/src/content/docs/reference/kernel/
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = REPO_ROOT / "nexus" / "modules"
KERNEL_DIR = REPO_ROOT / "nexus" / "kernel"
OUTPUT_DIR = REPO_ROOT / "site" / "src" / "content" / "docs" / "reference"

# ---------------------------------------------------------------------------
# Tier / ordering tables
# ---------------------------------------------------------------------------

MODULE_TIER: dict[str, int] = {
    "council": 1,
    "specter": 2,
    "autonomic": 3,
    "oracle": 4,
    "wraith": 5,
    "legacy": 6,
    "consciousness": 7,
    "sentry": 8,
    "echo": 9,
}

KERNEL_ORDER: dict[str, int] = {
    "cortex": 1,
    "engram": 2,
    "pulse": 3,
    "chronicle": 4,
    "aegis": 5,
}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _get_string_attr(class_node: ast.ClassDef, attr_name: str) -> str | None:
    """Return the string value of a class-level assignment like `name = "foo"`."""
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == attr_name:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == attr_name:
                if node.value and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def _get_docstring(node: ast.AST) -> str:
    """Return the docstring of a function/class/module node, or empty string."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        return ast.get_docstring(node) or ""
    return ""


def _extract_dataclasses(tree: ast.Module) -> list[dict[str, Any]]:
    """Extract @dataclass classes from module AST."""
    result = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_dc = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "dataclass":
                is_dc = True
            elif isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
                is_dc = True
        if not is_dc:
            continue

        fields: list[dict[str, Any]] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fname = item.target.id
                ftype = ast.unparse(item.annotation) if item.annotation else "Any"
                fdefault: str | None = None
                if item.value is not None:
                    fdefault = ast.unparse(item.value)
                fields.append({"name": fname, "type": ftype, "default": fdefault})
        result.append({"name": node.name, "fields": fields})
    return result


def _extract_methods(class_node: ast.ClassDef) -> list[dict[str, Any]]:
    """Extract public methods (non-private, including __init__-like skipping)."""
    methods = []
    for item in class_node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        mname = item.name
        # Skip private methods (starting with _) — but include __init__ is explicitly
        # kept out per spec: "not starting with _, except __init__"
        # Re-reading spec: "Public methods (not starting with `_`, except `__init__`)"
        # means skip ALL starting with _, including __init__
        if mname.startswith("_"):
            continue

        is_async = isinstance(item, ast.AsyncFunctionDef)
        args = item.args

        # Build readable signature
        parts: list[str] = []
        all_args = args.args
        defaults = args.defaults
        # Pad defaults to align with args
        n_no_default = len(all_args) - len(defaults)
        for i, arg in enumerate(all_args):
            aname = arg.arg
            atype = ast.unparse(arg.annotation) if arg.annotation else None
            adefault_idx = i - n_no_default
            adefault = ast.unparse(defaults[adefault_idx]) if adefault_idx >= 0 else None

            if atype and adefault:
                parts.append(f"{aname}: {atype} = {adefault}")
            elif atype:
                parts.append(f"{aname}: {atype}")
            elif adefault:
                parts.append(f"{aname} = {adefault}")
            else:
                parts.append(aname)

        ret = f" -> {ast.unparse(item.returns)}" if item.returns else ""
        sig = f"{mname}({', '.join(parts)}){ret}"

        methods.append({
            "name": mname,
            "signature": sig,
            "docstring": _get_docstring(item),
            "is_async": is_async,
        })
    return methods


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_module_info(source: str, filename: str) -> dict | None:
    """
    Parse a NEXUS module source string with AST and return extracted info dict.

    Returns None if no suitable class is found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    module_docstring = _get_docstring(tree)

    # Collect only top-level classes (not nested)
    top_level_classes: list[ast.ClassDef] = [
        node for node in tree.body if isinstance(node, ast.ClassDef)
    ]

    if not top_level_classes:
        return None

    # Strategy 1: find a class with bases (subclass — typical for modules)
    # Strategy 2: find a class whose name matches the filename (e.g. Chronicle -> chronicle.py)
    # Strategy 3: find a class with name/description/version string attrs
    # Strategy 4: use the last top-level class (main class usually last in kernel files)
    stem = Path(filename).stem.lower()
    target_class: ast.ClassDef | None = None

    # Prefer a class whose lowercased name matches the file stem (e.g. Chronicle, Cortex, Engram)
    for cls in top_level_classes:
        if cls.name.lower() == stem:
            target_class = cls
            break

    if target_class is None:
        # Find first subclass
        for cls in top_level_classes:
            if cls.bases:
                target_class = cls
                break

    if target_class is None:
        # Find first class with name/description attrs
        for cls in top_level_classes:
            if _get_string_attr(cls, "name"):
                target_class = cls
                break

    if target_class is None:
        # Fall back to last top-level class
        target_class = top_level_classes[-1]

    if target_class is None:
        return None

    name = _get_string_attr(target_class, "name") or Path(filename).stem
    description = _get_string_attr(target_class, "description") or ""
    version = _get_string_attr(target_class, "version") or "0.1.0"
    dataclasses = _extract_dataclasses(tree)
    methods = _extract_methods(target_class)

    return {
        "class_name": target_class.name,
        "name": name,
        "description": description,
        "version": version,
        "module_docstring": module_docstring,
        "methods": methods,
        "dataclasses": dataclasses,
    }


def extract_cortex_keywords(source: str) -> dict[str, list[str]]:
    """
    Parse Cortex source and extract the _MODULE_KEYWORDS dict literal.

    Returns {} if not found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        # Identify target name
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_MODULE_KEYWORDS":
                    value = node.value
                    return _parse_str_list_dict(value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "_MODULE_KEYWORDS":
                if node.value:
                    return _parse_str_list_dict(node.value)

    return {}


def _parse_str_list_dict(node: ast.expr) -> dict[str, list[str]]:
    """Parse a dict literal of {str: [str, ...]} from an AST node."""
    if not isinstance(node, ast.Dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, val in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            continue
        if not isinstance(val, ast.List):
            continue
        items = []
        for elt in val.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                items.append(elt.value)
        result[key.value] = items
    return result


# ---------------------------------------------------------------------------
# Rendering functions
# ---------------------------------------------------------------------------

def render_module_page(info: dict) -> str:
    """Render a Starlight Markdown page for an ONEXUS cognitive module."""
    name = info["name"]
    description = info["description"]
    version = info["version"]
    class_name = info["class_name"]
    module_docstring = info["module_docstring"]
    methods = info["methods"]
    dataclasses = info["dataclasses"]
    tier = MODULE_TIER.get(name, 0)

    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f'title: "{class_name}"')
    lines.append(f'description: "{description}"')
    lines.append("sidebar:")
    lines.append(f'  order: {tier}')
    lines.append("---")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    if module_docstring:
        lines.append(module_docstring)
    else:
        lines.append(description)
    lines.append("")

    # Meta
    lines.append(f"- **Version:** `{version}`")
    lines.append(f"- **Class:** `{class_name}`")
    lines.append(f"- **Module name:** `{name}`")
    lines.append("")

    # Tier
    lines.append("## Tier")
    lines.append("")
    if tier > 0:
        lines.append(f"Tier {tier} module.")
    else:
        lines.append("General purpose module.")
    lines.append("")

    # Types / Dataclasses
    if dataclasses:
        lines.append("## Types")
        lines.append("")
        for dc in dataclasses:
            lines.append(f"### `{dc['name']}`")
            lines.append("")
            lines.append("| Field | Type | Default |")
            lines.append("|-------|------|---------|")
            for field in dc["fields"]:
                fname = field["name"]
                ftype = field["type"] or "Any"
                fdefault = field["default"] if field["default"] is not None else "—"
                lines.append(f"| `{fname}` | `{ftype}` | `{fdefault}` |")
            lines.append("")

    # API / Methods
    if methods:
        lines.append("## API")
        lines.append("")
        for method in methods:
            async_prefix = "async " if method["is_async"] else ""
            lines.append(f"### `{async_prefix}{method['signature']}`")
            lines.append("")
            if method["docstring"]:
                lines.append(method["docstring"])
                lines.append("")

    return "\n".join(lines)


def render_kernel_page(info: dict) -> str:
    """Render a Starlight Markdown page for a NEXUS kernel component."""
    name = info["name"]
    description = info["description"]
    version = info["version"]
    class_name = info["class_name"]
    module_docstring = info["module_docstring"]
    methods = info["methods"]
    dataclasses = info["dataclasses"]
    order = KERNEL_ORDER.get(name, 99)

    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f'title: "{class_name}"')
    lines.append(f'description: "{description}"')
    lines.append("sidebar:")
    lines.append(f'  order: {order}')
    lines.append("---")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    if module_docstring:
        lines.append(module_docstring)
    else:
        lines.append(description)
    lines.append("")

    # Meta
    lines.append(f"- **Version:** `{version}`")
    lines.append(f"- **Class:** `{class_name}`")
    lines.append("")

    # Types / Dataclasses
    if dataclasses:
        lines.append("## Types")
        lines.append("")
        for dc in dataclasses:
            lines.append(f"### `{dc['name']}`")
            lines.append("")
            lines.append("| Field | Type | Default |")
            lines.append("|-------|------|---------|")
            for field in dc["fields"]:
                fname = field["name"]
                ftype = field["type"] or "Any"
                fdefault = field["default"] if field["default"] is not None else "—"
                lines.append(f"| `{fname}` | `{ftype}` | `{fdefault}` |")
            lines.append("")

    # API / Methods
    if methods:
        lines.append("## API")
        lines.append("")
        for method in methods:
            async_prefix = "async " if method["is_async"] else ""
            lines.append(f"### `{async_prefix}{method['signature']}`")
            lines.append("")
            if method["docstring"]:
                lines.append(method["docstring"])
                lines.append("")

    return "\n".join(lines)


def render_routing_page(keywords: dict[str, list[str]]) -> str:
    """Render the Cortex keyword routing table page."""
    lines: list[str] = []

    lines.append("---")
    lines.append('title: "Routing Keywords"')
    lines.append('description: "Cortex keyword routing table — how messages are dispatched to modules."')
    lines.append("sidebar:")
    lines.append("  order: 0")
    lines.append("---")
    lines.append("")
    lines.append("## Routing Table")
    lines.append("")
    lines.append("Cortex uses keyword matching to route each message to the best-fit module.")
    lines.append("The module with the highest keyword hit score receives the request.")
    lines.append("")
    lines.append("| Module | Keywords |")
    lines.append("|--------|----------|")
    for module_name, kws in sorted(keywords.items(), key=lambda x: MODULE_TIER.get(x[0], 99)):
        kw_str = ", ".join(f"`{kw}`" for kw in kws)
        lines.append(f"| `{module_name}` | {kw_str} |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    modules_out = OUTPUT_DIR / "modules"
    kernel_out = OUTPUT_DIR / "kernel"
    modules_out.mkdir(parents=True, exist_ok=True)
    kernel_out.mkdir(parents=True, exist_ok=True)

    # Clean old generated module docs before regenerating
    for old_md in modules_out.glob("*.md"):
        old_md.unlink()

    # Generate module pages (9 cognitive modules only)
    skipped = {"__init__.py", "base.py"}
    for py_file in sorted(MODULES_DIR.glob("*.py")):
        if py_file.name in skipped:
            continue
        source = py_file.read_text(encoding="utf-8")
        info = extract_module_info(source, py_file.name)
        if info is None:
            print(f"  [skip] {py_file.name} -- no class found")
            continue
        module_name = info["name"]
        page = render_module_page(info)
        out_path = modules_out / f"{module_name}.md"
        out_path.write_text(page, encoding="utf-8")
        print(f"  [ok]   modules/{module_name}.md")

    # Generate kernel pages
    for py_file in sorted(KERNEL_DIR.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        info = extract_module_info(source, py_file.name)
        if info is None:
            print(f"  [skip] kernel/{py_file.name} -- no class found")
            continue
        comp_name = py_file.stem
        page = render_kernel_page(info)
        out_path = kernel_out / f"{comp_name}.md"
        out_path.write_text(page, encoding="utf-8")
        print(f"  [ok]   kernel/{comp_name}.md")

    # Remove stale routing page (Cortex now uses semantic intent classification)
    routing_path = OUTPUT_DIR / "routing.md"
    if routing_path.exists():
        routing_path.unlink()

    print(f"\nDone. Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
