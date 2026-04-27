# NEXUS Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the NEXUS documentation site with Astro Starlight, dark NEXUS brand theme, auto-generated module/kernel reference docs, interactive landing page, and GitHub Pages deployment.

**Architecture:** Astro Starlight site in `site/` at the repo root. A Python pre-build script uses `ast` to scan `nexus/` and generate reference markdown pages. GitHub Actions deploys on push to `main`.

**Tech Stack:** Astro 5.x, Starlight, TypeScript, Python 3.11+ (ast module), GitHub Actions, GitHub Pages

---

## File Structure

```
site/
├── astro.config.mjs          ← Starlight config, sidebar, dark theme
├── package.json               ← Astro + Starlight dependencies
├── tsconfig.json              ← TypeScript config
├── src/
│   ├── content.config.ts      ← Starlight content config
│   ├── content/docs/
│   │   ├── index.mdx          ← Landing page (hero, module grid, quickstart)
│   │   ├── getting-started/
│   │   │   ├── installation.md
│   │   │   ├── quickstart.md
│   │   │   └── configuration.md
│   │   ├── architecture/
│   │   │   ├── overview.md
│   │   │   ├── kernel.md
│   │   │   └── modules.md
│   │   ├── concepts/
│   │   │   ├── earned-autonomy.md
│   │   │   ├── memory-tiers.md
│   │   │   ├── audit-trail.md
│   │   │   └── design-philosophy.md
│   │   ├── guides/
│   │   │   ├── building-a-module.md
│   │   │   ├── connecting-an-llm.md
│   │   │   └── running-tests.md
│   │   └── reference/         ← Auto-generated (do not hand-edit)
│   │       ├── _routing.md    ← Keyword routing table
│   │       ├── modules/       ← One .md per module
│   │       └── kernel/        ← One .md per kernel component
│   ├── components/
│   │   ├── Hero.astro         ← Full-width landing hero
│   │   ├── ModuleCard.astro   ← Glowing module card
│   │   └── ModuleGrid.astro   ← Tier-organized module grid
│   └── styles/
│       └── custom.css         ← NEXUS brand overrides
├── public/
│   └── favicon.svg            ← NEXUS favicon
└── scripts/
    └── generate-docs.py       ← AST-based doc generator

.github/
└── workflows/
    └── deploy-site.yml        ← GitHub Actions deployment

tests/
└── site/
    └── test_generate_docs.py  ← Tests for doc generator
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `site/package.json`
- Create: `site/astro.config.mjs`
- Create: `site/tsconfig.json`
- Create: `site/src/content.config.ts`
- Create: `site/src/content/docs/index.mdx` (minimal placeholder)
- Create: `site/src/styles/custom.css`
- Create: `site/public/favicon.svg`

- [ ] **Step 1: Create `site/package.json`**

```json
{
  "name": "nexus-site",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview"
  },
  "dependencies": {
    "astro": "^5.7.0",
    "@astrojs/starlight": "^0.34.0",
    "sharp": "^0.33.0"
  }
}
```

- [ ] **Step 2: Create `site/astro.config.mjs`**

```javascript
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://allstreets.github.io',
  base: '/NEXUS',
  integrations: [
    starlight({
      title: 'NEXUS',
      description: 'Neural Executive for Unified Superintelligence',
      customCss: ['./src/styles/custom.css'],
      favicon: '/favicon.svg',
      head: [
        {
          tag: 'link',
          attrs: {
            rel: 'preconnect',
            href: 'https://fonts.googleapis.com',
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'preconnect',
            href: 'https://fonts.gstatic.com',
            crossorigin: true,
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'stylesheet',
            href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap',
          },
        },
      ],
      social: {
        github: 'https://github.com/AllStreets/NEXUS',
      },
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Installation', slug: 'getting-started/installation' },
            { label: 'Quickstart', slug: 'getting-started/quickstart' },
            { label: 'Configuration', slug: 'getting-started/configuration' },
          ],
        },
        {
          label: 'Architecture',
          items: [
            { label: 'Overview', slug: 'architecture/overview' },
            { label: 'Kernel', slug: 'architecture/kernel' },
            { label: 'Modules', slug: 'architecture/modules' },
          ],
        },
        {
          label: 'Concepts',
          items: [
            { label: 'Earned Autonomy', slug: 'concepts/earned-autonomy' },
            { label: 'Memory Tiers', slug: 'concepts/memory-tiers' },
            { label: 'Audit Trail', slug: 'concepts/audit-trail' },
            { label: 'Design Philosophy', slug: 'concepts/design-philosophy' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Building a Module', slug: 'guides/building-a-module' },
            { label: 'Connecting an LLM', slug: 'guides/connecting-an-llm' },
            { label: 'Running Tests', slug: 'guides/running-tests' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Routing Table', slug: 'reference/routing' },
            {
              label: 'Kernel',
              autogenerate: { directory: 'reference/kernel' },
            },
            {
              label: 'Modules',
              autogenerate: { directory: 'reference/modules' },
            },
          ],
        },
      ],
    }),
  ],
});
```

- [ ] **Step 3: Create `site/tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict"
}
```

- [ ] **Step 4: Create `site/src/content.config.ts`**

```typescript
import { defineCollection } from 'astro:content';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({ schema: docsSchema() }),
};
```

- [ ] **Step 5: Create `site/src/styles/custom.css`**

```css
/* NEXUS Brand Theme — Dark Only */

:root {
  /* Colors */
  --nexus-bg-base: #0a0a0f;
  --nexus-bg-surface: #12121f;
  --nexus-bg-surface-hover: #1a1a2e;
  --nexus-text-primary: #e0e2eb;
  --nexus-text-secondary: #8888a0;
  --nexus-accent-primary: #00d4ff;
  --nexus-accent-secondary: #7b5cff;
  --nexus-accent-danger: #ff9d00;
  --nexus-border: #1e1e3a;
  --nexus-glow-primary: 0 0 12px rgba(0, 212, 255, 0.3);
  --nexus-glow-secondary: 0 0 12px rgba(123, 92, 255, 0.3);
}

/* Starlight dark theme overrides */
:root,
[data-theme='dark'] {
  --sl-color-bg: var(--nexus-bg-base);
  --sl-color-bg-nav: var(--nexus-bg-surface);
  --sl-color-bg-sidebar: var(--nexus-bg-surface);
  --sl-color-bg-inline-code: var(--nexus-bg-surface);
  --sl-color-hairline-light: var(--nexus-border);
  --sl-color-hairline: var(--nexus-border);
  --sl-color-white: var(--nexus-text-primary);
  --sl-color-gray-1: var(--nexus-text-primary);
  --sl-color-gray-2: #c0c2d0;
  --sl-color-gray-3: var(--nexus-text-secondary);
  --sl-color-gray-4: #555570;
  --sl-color-gray-5: #333350;
  --sl-color-gray-6: var(--nexus-bg-surface);
  --sl-color-accent-low: #0a1a2f;
  --sl-color-accent: var(--nexus-accent-primary);
  --sl-color-accent-high: #b0f0ff;
  --sl-color-text: var(--nexus-text-primary);
  --sl-color-text-accent: var(--nexus-accent-primary);

  /* Typography */
  --sl-font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --sl-font-mono: 'JetBrains Mono', ui-monospace, monospace;

  /* Borders */
  --sl-border-radius: 4px;
}

/* Force dark mode — no light mode */
:root[data-theme='light'] {
  --sl-color-bg: var(--nexus-bg-base);
  --sl-color-bg-nav: var(--nexus-bg-surface);
  --sl-color-bg-sidebar: var(--nexus-bg-surface);
  --sl-color-bg-inline-code: var(--nexus-bg-surface);
  --sl-color-hairline-light: var(--nexus-border);
  --sl-color-hairline: var(--nexus-border);
  --sl-color-white: var(--nexus-text-primary);
  --sl-color-gray-1: var(--nexus-text-primary);
  --sl-color-gray-2: #c0c2d0;
  --sl-color-gray-3: var(--nexus-text-secondary);
  --sl-color-gray-4: #555570;
  --sl-color-gray-5: #333350;
  --sl-color-gray-6: var(--nexus-bg-surface);
  --sl-color-accent-low: #0a1a2f;
  --sl-color-accent: var(--nexus-accent-primary);
  --sl-color-accent-high: #b0f0ff;
  --sl-color-text: var(--nexus-text-primary);
  --sl-color-text-accent: var(--nexus-accent-primary);
  --sl-font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --sl-font-mono: 'JetBrains Mono', ui-monospace, monospace;
  --sl-border-radius: 4px;
}

/* Headings in JetBrains Mono */
h1, h2, h3, h4, h5, h6,
.sl-markdown-content h1,
.sl-markdown-content h2,
.sl-markdown-content h3,
.sl-markdown-content h4 {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  letter-spacing: -0.02em;
}

/* Sidebar styling */
nav.sidebar {
  border-right: 1px solid var(--nexus-border);
}

/* Links glow on hover */
a:hover {
  text-shadow: var(--nexus-glow-primary);
}

/* Code blocks */
.expressive-code pre {
  background: var(--nexus-bg-surface) !important;
  border: 1px solid var(--nexus-border);
}

/* Hide theme toggle — dark only */
starlight-theme-select,
[data-theme-toggle] {
  display: none !important;
}
```

- [ ] **Step 6: Create `site/public/favicon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="4" fill="#0a0a0f"/>
  <text x="16" y="22" font-family="monospace" font-size="18" font-weight="bold" fill="#00d4ff" text-anchor="middle">N</text>
</svg>
```

- [ ] **Step 7: Create minimal `site/src/content/docs/index.mdx`**

```mdx
---
title: NEXUS
description: Neural Executive for Unified Superintelligence
template: splash
hero:
  title: N E X U S
  tagline: An autonomous intelligence operating system that runs on your hardware, answers to no cloud, and gets smarter the longer it runs.
  actions:
    - text: Get Started
      link: /NEXUS/getting-started/installation/
      icon: right-arrow
    - text: GitHub
      link: https://github.com/AllStreets/NEXUS
      icon: external
      variant: minimal
---

Site under construction.
```

- [ ] **Step 8: Install dependencies and verify build**

Run: `cd site && npm install && npm run build`
Expected: Astro build completes without errors, `dist/` directory created.

- [ ] **Step 9: Commit**

```bash
git add site/
git commit -m "feat(site): scaffold Astro Starlight project with NEXUS dark theme"
```

---

### Task 2: Doc Generation Script + Tests

**Files:**
- Create: `site/scripts/generate-docs.py`
- Create: `tests/site/test_generate_docs.py`

- [ ] **Step 1: Write the tests**

```python
"""Tests for the AST-based documentation generator."""
import ast
import textwrap
from pathlib import Path

import pytest

# We'll import these after creating the script
from site.scripts.generate_docs import (
    extract_module_info,
    extract_cortex_keywords,
    render_module_page,
    render_kernel_page,
    render_routing_page,
)


# --- extract_module_info ---

def test_extract_module_info_basic_class():
    source = textwrap.dedent('''
        """Module docstring."""
        from nexus.modules.base import NexusModule
        from typing import Any

        class FooModule(NexusModule):
            name = "foo"
            description = "A foo module"
            version = "0.1.0"

            async def handle(self, message: str, context: dict[str, Any]) -> str:
                """Handle a message."""
                return "ok"
    ''')
    info = extract_module_info(source, "foo.py")
    assert info["class_name"] == "FooModule"
    assert info["name"] == "foo"
    assert info["description"] == "A foo module"
    assert info["version"] == "0.1.0"
    assert info["module_docstring"] == "Module docstring."
    assert len(info["methods"]) >= 1
    handle = [m for m in info["methods"] if m["name"] == "handle"][0]
    assert handle["docstring"] == "Handle a message."
    assert "message" in handle["signature"]


def test_extract_module_info_with_dataclasses():
    source = textwrap.dedent('''
        """Module with types."""
        from dataclasses import dataclass
        from nexus.modules.base import NexusModule
        from typing import Any

        @dataclass
        class Widget:
            name: str
            weight: float = 1.0

        class BarModule(NexusModule):
            name = "bar"
            description = "A bar module"
            version = "0.1.0"

            async def handle(self, message: str, context: dict[str, Any]) -> str:
                return "ok"
    ''')
    info = extract_module_info(source, "bar.py")
    assert len(info["dataclasses"]) == 1
    dc = info["dataclasses"][0]
    assert dc["name"] == "Widget"
    assert len(dc["fields"]) == 2
    assert dc["fields"][0]["name"] == "name"
    assert dc["fields"][0]["type"] == "str"
    assert dc["fields"][1]["name"] == "weight"
    assert dc["fields"][1]["default"] == "1.0"


def test_extract_module_info_skips_private_methods():
    source = textwrap.dedent('''
        """Test module."""
        from nexus.modules.base import NexusModule
        from typing import Any

        class BazModule(NexusModule):
            name = "baz"
            description = "A baz module"
            version = "0.1.0"

            def _private(self):
                pass

            def public_method(self) -> list[str]:
                """Do something public."""
                return []

            async def handle(self, message: str, context: dict[str, Any]) -> str:
                return "ok"
    ''')
    info = extract_module_info(source, "baz.py")
    method_names = [m["name"] for m in info["methods"]]
    assert "_private" not in method_names
    assert "public_method" in method_names
    assert "handle" in method_names


def test_extract_module_info_no_class_returns_none():
    source = "# just a comment\nx = 1\n"
    info = extract_module_info(source, "empty.py")
    assert info is None


# --- extract_cortex_keywords ---

def test_extract_cortex_keywords():
    source = textwrap.dedent('''
        class Cortex:
            _MODULE_KEYWORDS: dict[str, list[str]] = {
                "oracle": ["trigger", "alert", "monitor"],
                "sentry": ["focus", "fatigue"],
            }
    ''')
    keywords = extract_cortex_keywords(source)
    assert keywords["oracle"] == ["trigger", "alert", "monitor"]
    assert keywords["sentry"] == ["focus", "fatigue"]


def test_extract_cortex_keywords_empty_source():
    keywords = extract_cortex_keywords("x = 1")
    assert keywords == {}


# --- render functions ---

def test_render_module_page_has_frontmatter():
    info = {
        "class_name": "OracleModule",
        "name": "oracle",
        "description": "Anticipatory trigger engine",
        "version": "0.1.0",
        "module_docstring": "Oracle scans for patterns.",
        "methods": [
            {
                "name": "handle",
                "signature": "(self, message: str, context: dict) -> str",
                "docstring": "Handle a message.",
                "is_async": True,
            },
            {
                "name": "evaluate",
                "signature": "(self, text: str) -> list[dict]",
                "docstring": "Score text against rules.",
                "is_async": False,
            },
        ],
        "dataclasses": [
            {
                "name": "TriggerRule",
                "fields": [
                    {"name": "name", "type": "str", "default": None},
                    {"name": "threshold", "type": "float", "default": None},
                ],
            },
        ],
    }
    keywords = ["trigger", "alert", "monitor"]
    page = render_module_page(info, keywords)
    assert "---" in page
    assert "title: Oracle" in page
    assert "Oracle scans for patterns." in page
    assert "`trigger`" in page
    assert "TriggerRule" in page
    assert "evaluate" in page
    assert "async" in page.lower()


def test_render_kernel_page_has_frontmatter():
    info = {
        "class_name": "Engram",
        "name": "engram",
        "description": None,
        "version": None,
        "module_docstring": "Three-tier memory system.",
        "methods": [
            {
                "name": "store",
                "signature": "(self, text: str) -> None",
                "docstring": "Store a memory.",
                "is_async": False,
            },
        ],
        "dataclasses": [],
    }
    page = render_kernel_page(info)
    assert "title: Engram" in page
    assert "Three-tier memory system." in page


def test_render_routing_page():
    keywords = {
        "oracle": ["trigger", "alert"],
        "sentry": ["focus", "fatigue"],
    }
    page = render_routing_page(keywords)
    assert "---" in page
    assert "oracle" in page
    assert "trigger" in page
    assert "sentry" in page
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/site/test_generate_docs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'site.scripts.generate_docs'`

- [ ] **Step 3: Write the doc generation script**

Create `site/scripts/generate-docs.py`:

```python
#!/usr/bin/env python3
"""
AST-based documentation generator for NEXUS.
Scans nexus/modules/ and nexus/kernel/ to produce Starlight-compatible
markdown reference pages. No runtime imports — pure syntax tree parsing.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEXUS_DIR = REPO_ROOT / "nexus"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "content" / "docs" / "reference"

SKIP_FILES = {"__init__.py", "base.py"}

# --- Tier mapping for sidebar ordering ---
MODULE_TIERS = {
    "oracle": ("Perception", 1),
    "sentry": ("Perception", 2),
    "atlas": ("Intelligence", 3),
    "prism": ("Intelligence", 4),
    "cipher": ("Intelligence", 5),
    "wraith": ("Action", 6),
    "echo": ("Action", 7),
    "sigil": ("Action", 8),
    "herald": ("Action", 9),
    "weave": ("Action", 10),
    "specter": ("Advanced Intelligence", 11),
    "chronos": ("Advanced Intelligence", 12),
    "dreamweaver": ("Advanced Intelligence", 13),
    "serendipity": ("Advanced Intelligence", 14),
    "forge": ("Advanced Intelligence", 15),
    "collective": ("Network", 16),
    "legacy": ("Network", 17),
    "general": ("Core", 0),
}

KERNEL_ORDER = {
    "cortex": 1,
    "engram": 2,
    "pulse": 3,
    "chronicle": 4,
    "aegis": 5,
}


def extract_module_info(source: str, filename: str) -> dict | None:
    """Extract class info from a module source file using AST parsing."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    module_docstring = ast.get_docstring(tree)

    # Find dataclasses
    dataclasses = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_dataclass = any(
            (isinstance(d, ast.Name) and d.id == "dataclass")
            or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            or (isinstance(d, ast.Call) and (
                (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
            ))
            for d in node.decorator_list
        )
        if is_dataclass:
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_info = {
                        "name": item.target.id,
                        "type": ast.unparse(item.annotation) if item.annotation else "Any",
                        "default": ast.unparse(item.value) if item.value else None,
                    }
                    fields.append(field_info)
            dataclasses.append({"name": node.name, "fields": fields})

    # Find the primary class (first non-dataclass class)
    primary_class = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            is_dc = any(
                (isinstance(d, ast.Name) and d.id == "dataclass")
                or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                for d in node.decorator_list
            )
            if not is_dc:
                primary_class = node
                break

    if primary_class is None:
        return None

    # Extract class-level string attributes (name, description, version)
    attrs = {}
    for item in primary_class.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                    attrs[target.id] = item.value.value

    # Extract public methods
    methods = []
    for item in primary_class.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("_") and item.name != "__init__":
                continue
            sig_parts = []
            for arg in item.args.args:
                ann = ast.unparse(arg.annotation) if arg.annotation else ""
                part = f"{arg.arg}: {ann}" if ann else arg.arg
                sig_parts.append(part)
            returns = ast.unparse(item.returns) if item.returns else ""
            sig = f"({', '.join(sig_parts)})"
            if returns:
                sig += f" -> {returns}"
            methods.append({
                "name": item.name,
                "signature": sig,
                "docstring": ast.get_docstring(item),
                "is_async": isinstance(item, ast.AsyncFunctionDef),
            })

    return {
        "class_name": primary_class.name,
        "name": attrs.get("name", filename.replace(".py", "")),
        "description": attrs.get("description"),
        "version": attrs.get("version"),
        "module_docstring": module_docstring,
        "methods": methods,
        "dataclasses": dataclasses,
    }


def extract_cortex_keywords(source: str) -> dict[str, list[str]]:
    """Extract _MODULE_KEYWORDS dict from Cortex source using AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Cortex":
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "_MODULE_KEYWORDS":
                    # Evaluate the dict literal safely
                    result = {}
                    if isinstance(item.value, ast.Dict):
                        for key, value in zip(item.value.keys, item.value.values):
                            if isinstance(key, ast.Constant) and isinstance(value, ast.List):
                                kw_list = [
                                    elt.value for elt in value.elts
                                    if isinstance(elt, ast.Constant)
                                ]
                                result[key.value] = kw_list
                    return result
    return {}


def render_module_page(info: dict, keywords: list[str] | None = None) -> str:
    """Render a Starlight-compatible markdown page for a module."""
    name = info["name"]
    title = name.capitalize()
    tier, order = MODULE_TIERS.get(name, ("Other", 99))

    lines = [
        "---",
        f"title: {title}",
        f"description: {info.get('description') or f'{title} module'}",
        f"sidebar:",
        f"  order: {order}",
        "---",
        "",
    ]

    # Overview
    if info.get("module_docstring"):
        lines.append("## Overview")
        lines.append("")
        lines.append(info["module_docstring"])
        lines.append("")

    # Tier badge
    lines.append(f"**Tier:** {tier}")
    if info.get("version"):
        lines.append(f" | **Version:** {info['version']}")
    lines.append("")

    # Routing keywords
    if keywords:
        lines.append("## Routing Keywords")
        lines.append("")
        lines.append("Cortex routes messages containing these keywords to this module:")
        lines.append("")
        lines.append(", ".join(f"`{kw}`" for kw in keywords))
        lines.append("")

    # Dataclasses / Types
    if info.get("dataclasses"):
        lines.append("## Types")
        lines.append("")
        for dc in info["dataclasses"]:
            lines.append(f"### `{dc['name']}`")
            lines.append("")
            lines.append("| Field | Type | Default |")
            lines.append("|-------|------|---------|")
            for f in dc["fields"]:
                default = f"`{f['default']}`" if f["default"] else "--"
                lines.append(f"| `{f['name']}` | `{f['type']}` | {default} |")
            lines.append("")

    # API / Methods
    if info.get("methods"):
        lines.append("## API")
        lines.append("")
        lines.append(f"### `class {info['class_name']}`")
        lines.append("")
        for method in info["methods"]:
            prefix = "async " if method["is_async"] else ""
            lines.append(f"#### `{prefix}{method['name']}{method['signature']}`")
            lines.append("")
            if method.get("docstring"):
                lines.append(method["docstring"])
                lines.append("")

    return "\n".join(lines)


def render_kernel_page(info: dict) -> str:
    """Render a Starlight-compatible markdown page for a kernel component."""
    name = info.get("name") or info["class_name"].lower()
    title = info["class_name"]
    order = KERNEL_ORDER.get(name, 99)

    lines = [
        "---",
        f"title: {title}",
        f"description: {info.get('description') or f'{title} kernel component'}",
        f"sidebar:",
        f"  order: {order}",
        "---",
        "",
    ]

    if info.get("module_docstring"):
        lines.append("## Overview")
        lines.append("")
        lines.append(info["module_docstring"])
        lines.append("")

    if info.get("dataclasses"):
        lines.append("## Types")
        lines.append("")
        for dc in info["dataclasses"]:
            lines.append(f"### `{dc['name']}`")
            lines.append("")
            lines.append("| Field | Type | Default |")
            lines.append("|-------|------|---------|")
            for f in dc["fields"]:
                default = f"`{f['default']}`" if f["default"] else "--"
                lines.append(f"| `{f['name']}` | `{f['type']}` | {default} |")
            lines.append("")

    if info.get("methods"):
        lines.append("## API")
        lines.append("")
        lines.append(f"### `class {title}`")
        lines.append("")
        for method in info["methods"]:
            prefix = "async " if method["is_async"] else ""
            lines.append(f"#### `{prefix}{method['name']}{method['signature']}`")
            lines.append("")
            if method.get("docstring"):
                lines.append(method["docstring"])
                lines.append("")

    return "\n".join(lines)


def render_routing_page(keywords: dict[str, list[str]]) -> str:
    """Render the keyword routing table page."""
    lines = [
        "---",
        "title: Routing Table",
        "description: How Cortex routes messages to modules",
        "sidebar:",
        "  order: 0",
        "---",
        "",
        "## Keyword Routing",
        "",
        "Cortex uses keyword matching to route user messages to the appropriate module.",
        "When a message contains keywords associated with a module, that module handles the request.",
        "If no keywords match, the message falls through to the `general` module.",
        "",
        "| Module | Keywords |",
        "|--------|----------|",
    ]

    for module, kws in sorted(keywords.items()):
        kw_str = ", ".join(f"`{kw}`" for kw in kws)
        lines.append(f"| **{module}** | {kw_str} |")

    lines.append("")
    return "\n".join(lines)


def main():
    """Scan NEXUS source and generate reference documentation."""
    # Read Cortex keywords
    cortex_path = NEXUS_DIR / "kernel" / "cortex.py"
    cortex_source = cortex_path.read_text()
    all_keywords = extract_cortex_keywords(cortex_source)

    # Generate module pages
    modules_out = OUTPUT_DIR / "modules"
    modules_out.mkdir(parents=True, exist_ok=True)
    modules_dir = NEXUS_DIR / "modules"

    module_count = 0
    for py_file in sorted(modules_dir.glob("*.py")):
        if py_file.name in SKIP_FILES:
            continue
        source = py_file.read_text()
        info = extract_module_info(source, py_file.name)
        if info is None:
            continue
        keywords = all_keywords.get(info["name"], [])
        page = render_module_page(info, keywords)
        out_path = modules_out / f"{info['name']}.md"
        out_path.write_text(page)
        module_count += 1
        print(f"  module: {info['name']} -> {out_path.name}")

    # Generate kernel pages
    kernel_out = OUTPUT_DIR / "kernel"
    kernel_out.mkdir(parents=True, exist_ok=True)
    kernel_dir = NEXUS_DIR / "kernel"

    kernel_count = 0
    for py_file in sorted(kernel_dir.glob("*.py")):
        if py_file.name in SKIP_FILES:
            continue
        source = py_file.read_text()
        info = extract_module_info(source, py_file.name)
        if info is None:
            continue
        page = render_kernel_page(info)
        out_path = kernel_out / f"{info['name']}.md"
        out_path.write_text(page)
        kernel_count += 1
        print(f"  kernel: {info['name']} -> {out_path.name}")

    # Generate routing table
    routing_page = render_routing_page(all_keywords)
    routing_path = OUTPUT_DIR / "routing.md"
    routing_path.write_text(routing_page)
    print(f"  routing table -> {routing_path.name}")

    print(f"\nGenerated {module_count} module pages, {kernel_count} kernel pages, 1 routing table.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Make tests importable**

The test file needs to import from `site/scripts/generate_docs.py`. Since "site" is not a Python package, the tests should add the script directory to `sys.path`. Update the test file imports at the top:

```python
"""Tests for the AST-based documentation generator."""
import sys
from pathlib import Path

# Add the scripts directory to path so we can import generate_docs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "site" / "scripts"))

# The script filename has a hyphen, so we rename the import
import importlib
generate_docs = importlib.import_module("generate-docs")
extract_module_info = generate_docs.extract_module_info
extract_cortex_keywords = generate_docs.extract_cortex_keywords
render_module_page = generate_docs.render_module_page
render_kernel_page = generate_docs.render_kernel_page
render_routing_page = generate_docs.render_routing_page
```

Remove the original `from site.scripts.generate_docs import ...` block.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/connorevans/Downloads/NEXUS && .venv/bin/pytest tests/site/test_generate_docs.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 6: Run the script against the real codebase**

Run: `cd /Users/connorevans/Downloads/NEXUS && python site/scripts/generate-docs.py`
Expected: Output showing 18 module pages, 5 kernel pages, 1 routing table generated. Files appear in `site/src/content/docs/reference/`.

- [ ] **Step 7: Verify generated files look correct**

Run: `head -20 site/src/content/docs/reference/modules/oracle.md && echo "---" && head -20 site/src/content/docs/reference/kernel/cortex.md && echo "---" && head -20 site/src/content/docs/reference/routing.md`
Expected: Each file starts with valid YAML frontmatter and has the expected sections.

- [ ] **Step 8: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests pass (233 existing + 9 new = 242).

- [ ] **Step 9: Commit**

```bash
git add site/scripts/generate-docs.py tests/site/test_generate_docs.py
git commit -m "feat(site): AST-based doc generator with 9 tests"
```

---

### Task 3: Landing Page

**Files:**
- Create: `site/src/components/Hero.astro`
- Create: `site/src/components/ModuleCard.astro`
- Create: `site/src/components/ModuleGrid.astro`
- Modify: `site/src/content/docs/index.mdx`
- Modify: `site/src/styles/custom.css`

- [ ] **Step 1: Create `site/src/components/ModuleCard.astro`**

```astro
---
interface Props {
  name: string;
  description: string;
  tier: string;
  status?: string;
}

const { name, description, tier, status = 'BUILT' } = Astro.props;

const tierColors: Record<string, string> = {
  'Kernel': '#00d4ff',
  'Perception': '#7b5cff',
  'Intelligence': '#7b5cff',
  'Action': '#ff9d00',
  'Advanced Intelligence': '#ff4d6a',
  'Network': '#00ff88',
};

const color = tierColors[tier] || '#00d4ff';
---

<div class="module-card" style={`--card-accent: ${color}`}>
  <div class="card-header">
    <span class="card-name">{name}</span>
    <span class="card-status" data-status={status}>{status}</span>
  </div>
  <p class="card-description">{description}</p>
  <span class="card-tier">{tier}</span>
</div>

<style>
  .module-card {
    background: var(--nexus-bg-surface);
    border: 1px solid var(--nexus-border);
    padding: 1.25rem;
    transition: border-color 0.2s, box-shadow 0.2s;
    cursor: default;
  }

  .module-card:hover {
    border-color: var(--card-accent);
    box-shadow: 0 0 16px color-mix(in srgb, var(--card-accent) 25%, transparent);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .card-name {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 1rem;
    color: var(--card-accent);
  }

  .card-status {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    padding: 0.15rem 0.5rem;
    border: 1px solid var(--nexus-border);
    color: var(--nexus-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .card-status[data-status='BUILT'] {
    border-color: #00ff88;
    color: #00ff88;
  }

  .card-description {
    font-size: 0.85rem;
    color: var(--nexus-text-secondary);
    margin: 0 0 0.75rem 0;
    line-height: 1.4;
  }

  .card-tier {
    font-size: 0.7rem;
    color: var(--nexus-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.6;
  }
</style>
```

- [ ] **Step 2: Create `site/src/components/ModuleGrid.astro`**

```astro
---
import ModuleCard from './ModuleCard.astro';

const modules = [
  // Kernel
  { name: 'Cortex', description: 'Keyword-scored router and orchestrator', tier: 'Kernel' },
  { name: 'Engram', description: 'Three-tier memory: working, episodic, semantic', tier: 'Kernel' },
  { name: 'Pulse', description: 'Async pub/sub message bus with priority queuing', tier: 'Kernel' },
  { name: 'Chronicle', description: 'Immutable audit trail for every system action', tier: 'Kernel' },
  { name: 'Aegis', description: 'Graduated trust engine with outcome-based adjustment', tier: 'Kernel' },
  // Perception
  { name: 'Oracle', description: 'Anticipatory trigger engine with keyword-weighted scoring', tier: 'Perception' },
  { name: 'Sentry', description: 'Real-time cognitive state model and flow detection', tier: 'Perception' },
  // Intelligence
  { name: 'Atlas', description: 'Temporal knowledge graph with confidence decay', tier: 'Intelligence' },
  { name: 'Prism', description: 'Cross-domain synthesis across calendar, email, finance', tier: 'Intelligence' },
  { name: 'Cipher', description: 'Source trust registry and provenance chains', tier: 'Intelligence' },
  // Action
  { name: 'Wraith', description: 'Ephemeral micro-agents with death clocks', tier: 'Action' },
  { name: 'Echo', description: 'Behavioral fingerprinting and voice matching', tier: 'Action' },
  { name: 'Sigil', description: 'Severity-prioritized ambient threat radar', tier: 'Action' },
  { name: 'Herald', description: 'A2A agent communication and reputation tracking', tier: 'Action' },
  { name: 'Weave', description: 'Social graph intelligence and relationship health', tier: 'Action' },
  // Advanced Intelligence
  { name: 'Specter', description: 'Adversarial red-team and counter-argument generation', tier: 'Advanced Intelligence' },
  { name: 'Chronos', description: 'Temporal branching and probabilistic future modeling', tier: 'Advanced Intelligence' },
  { name: 'Dreamweaver', description: 'Overnight synthesis and morning briefings', tier: 'Advanced Intelligence' },
  { name: 'Serendipity', description: 'Anti-optimization for surprising cross-domain connections', tier: 'Advanced Intelligence' },
  { name: 'Forge', description: 'Autonomous multi-round negotiation with escalation', tier: 'Advanced Intelligence' },
  // Network
  { name: 'Collective', description: 'Federated learning with differential privacy', tier: 'Network' },
  { name: 'Legacy', description: 'Knowledge crystallization into frameworks and playbooks', tier: 'Network' },
];

const tiers = ['Kernel', 'Perception', 'Intelligence', 'Action', 'Advanced Intelligence', 'Network'];
---

<div class="module-grid-container">
  {tiers.map(tier => (
    <div class="tier-section">
      <h3 class="tier-label">{tier}</h3>
      <div class="tier-grid">
        {modules.filter(m => m.tier === tier).map(m => (
          <ModuleCard name={m.name} description={m.description} tier={m.tier} />
        ))}
      </div>
    </div>
  ))}
</div>

<style>
  .module-grid-container {
    max-width: 72rem;
    margin: 0 auto;
    padding: 2rem 1.5rem;
  }

  .tier-section {
    margin-bottom: 2.5rem;
  }

  .tier-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--nexus-text-secondary);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--nexus-border);
  }

  .tier-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }
</style>
```

- [ ] **Step 3: Create `site/src/components/Hero.astro`**

```astro
---
---

<div class="nexus-hero">
  <div class="hero-grid-bg"></div>
  <div class="hero-content">
    <h1 class="hero-title">N E X U S</h1>
    <p class="hero-subtitle">Neural Executive for Unified Superintelligence</p>
    <p class="hero-tagline">
      An autonomous intelligence operating system that runs on your hardware,
      answers to no cloud, and gets smarter the longer it runs.
    </p>
    <div class="hero-stats">
      <div class="stat">
        <span class="stat-value">23</span>
        <span class="stat-label">Modules</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">233</span>
        <span class="stat-label">Tests</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">8GB</span>
        <span class="stat-label">Min RAM</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-value">0</span>
        <span class="stat-label">Cloud Dependencies</span>
      </div>
    </div>
    <div class="hero-actions">
      <a href="/NEXUS/getting-started/installation/" class="btn-primary">Get Started</a>
      <a href="https://github.com/AllStreets/NEXUS" class="btn-secondary">GitHub</a>
    </div>

    <div class="hero-quickstart">
      <div class="quickstart-header">quickstart</div>
      <pre><code>git clone https://github.com/AllStreets/NEXUS.git
cd NEXUS && pip install -e .
nexus run</code></pre>
    </div>
  </div>
</div>

<style>
  .nexus-hero {
    position: relative;
    min-height: 90vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--nexus-bg-base);
  }

  .hero-grid-bg {
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(circle at 1px 1px, rgba(0, 212, 255, 0.06) 1px, transparent 0);
    background-size: 40px 40px;
    pointer-events: none;
  }

  .hero-content {
    position: relative;
    text-align: center;
    max-width: 48rem;
    padding: 2rem 1.5rem;
  }

  .hero-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: clamp(2.5rem, 8vw, 5rem);
    font-weight: 700;
    color: var(--nexus-accent-primary);
    letter-spacing: 0.3em;
    margin: 0 0 0.5rem 0;
    text-shadow: 0 0 40px rgba(0, 212, 255, 0.3), 0 0 80px rgba(0, 212, 255, 0.1);
  }

  .hero-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: var(--nexus-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin: 0 0 1.5rem 0;
  }

  .hero-tagline {
    font-size: 1.1rem;
    color: var(--nexus-text-primary);
    line-height: 1.6;
    margin: 0 0 2.5rem 0;
    max-width: 36rem;
    margin-left: auto;
    margin-right: auto;
  }

  .hero-stats {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 2rem;
    margin-bottom: 2.5rem;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--nexus-accent-primary);
  }

  .stat-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--nexus-text-secondary);
    margin-top: 0.25rem;
  }

  .stat-divider {
    width: 1px;
    height: 2.5rem;
    background: var(--nexus-border);
  }

  .hero-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin-bottom: 3rem;
  }

  .btn-primary {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    padding: 0.75rem 2rem;
    background: var(--nexus-accent-primary);
    color: var(--nexus-bg-base);
    text-decoration: none;
    font-weight: 600;
    transition: box-shadow 0.2s;
    border: none;
  }

  .btn-primary:hover {
    box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
    text-shadow: none;
  }

  .btn-secondary {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    padding: 0.75rem 2rem;
    background: transparent;
    color: var(--nexus-text-primary);
    text-decoration: none;
    border: 1px solid var(--nexus-border);
    font-weight: 500;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .btn-secondary:hover {
    border-color: var(--nexus-accent-secondary);
    box-shadow: 0 0 12px rgba(123, 92, 255, 0.2);
    text-shadow: none;
  }

  .hero-quickstart {
    max-width: 28rem;
    margin: 0 auto;
    text-align: left;
    background: var(--nexus-bg-surface);
    border: 1px solid var(--nexus-border);
    overflow: hidden;
  }

  .quickstart-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--nexus-text-secondary);
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--nexus-border);
    background: rgba(255, 255, 255, 0.02);
  }

  .hero-quickstart pre {
    margin: 0;
    padding: 1rem;
    background: transparent !important;
    border: none !important;
  }

  .hero-quickstart code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--nexus-text-primary);
    line-height: 1.6;
  }

  @media (max-width: 640px) {
    .stat-divider { display: none; }
    .hero-stats { gap: 1.5rem; }
  }
</style>
```

- [ ] **Step 4: Update `site/src/content/docs/index.mdx`**

```mdx
---
title: NEXUS
description: Neural Executive for Unified Superintelligence
template: splash
hero:
  title: ' '
  tagline: ' '
---

import Hero from '../../components/Hero.astro';
import ModuleGrid from '../../components/ModuleGrid.astro';

<Hero />

<div style="max-width: 72rem; margin: 0 auto; padding: 2rem 1.5rem;">

## 23 Modules. One Kernel. Your Hardware.

Five kernel components, eighteen intelligence modules, zero cloud dependencies.
Everything runs locally in a single SQLite database. The smallest useful
configuration fits in 8GB of RAM.

</div>

<ModuleGrid />

<div style="max-width: 72rem; margin: 0 auto; padding: 2rem 1.5rem;">

## Hardware Requirements

| RAM | What you get |
|-----|-------------|
| **8 GB** | Kernel + 3 modules, Qwen 3 8B Q4_K_M (~4.5 GB model) |
| **16 GB** | Kernel + 10 modules, larger context windows |
| **32 GB+** | All 23 modules, bigger models, concurrent agents |

</div>
```

- [ ] **Step 5: Add landing page styles to `site/src/styles/custom.css`**

Append to the existing `custom.css`:

```css

/* Landing page — hide default Starlight hero on splash template */
[data-page-type='splash'] .hero {
  display: none;
}

[data-page-type='splash'] .sl-markdown-content {
  max-width: none;
  padding: 0;
}

[data-page-type='splash'] header {
  background: var(--nexus-bg-base);
  border-bottom: 1px solid var(--nexus-border);
}
```

- [ ] **Step 6: Generate reference docs and build**

Run:
```bash
cd /Users/connorevans/Downloads/NEXUS
python site/scripts/generate-docs.py
cd site && npm run build
```
Expected: Build succeeds. `dist/` contains the built site with the landing page and reference docs.

- [ ] **Step 7: Commit**

```bash
git add site/src/components/ site/src/content/docs/index.mdx site/src/styles/custom.css
git commit -m "feat(site): landing page with hero, module grid, and quickstart"
```

---

### Task 4: Documentation Pages

**Files:**
- Create: `site/src/content/docs/getting-started/installation.md`
- Create: `site/src/content/docs/getting-started/quickstart.md`
- Create: `site/src/content/docs/getting-started/configuration.md`
- Create: `site/src/content/docs/architecture/overview.md`
- Create: `site/src/content/docs/architecture/kernel.md`
- Create: `site/src/content/docs/architecture/modules.md`
- Create: `site/src/content/docs/concepts/earned-autonomy.md`
- Create: `site/src/content/docs/concepts/memory-tiers.md`
- Create: `site/src/content/docs/concepts/audit-trail.md`
- Create: `site/src/content/docs/concepts/design-philosophy.md`
- Create: `site/src/content/docs/guides/building-a-module.md`
- Create: `site/src/content/docs/guides/connecting-an-llm.md`
- Create: `site/src/content/docs/guides/running-tests.md`

- [ ] **Step 1: Create Getting Started pages**

`site/src/content/docs/getting-started/installation.md`:

```markdown
---
title: Installation
description: Install NEXUS on your machine
sidebar:
  order: 1
---

## Prerequisites

- Python 3.11 or higher
- 8 GB RAM minimum
- No GPU required (CPU inference via llama.cpp)

## Install from Source

```bash
git clone https://github.com/AllStreets/NEXUS.git
cd NEXUS
pip install -e .
```

This installs the `nexus` CLI and all Python dependencies.

## Verify Installation

```bash
nexus status
```

You should see the system state: database path, model status, and loaded modules.

## Optional: Local LLM

For full intelligence capability, run a local model with llama.cpp:

```bash
# Download a model (Qwen 3 8B recommended, ~4.5 GB)
# Place it in models/ directory

llama-server -m models/qwen3-8b-q4_k_m.gguf -c 4096 --port 8384
```

NEXUS detects the model server automatically on startup.
```

`site/src/content/docs/getting-started/quickstart.md`:

```markdown
---
title: Quickstart
description: Get NEXUS running in two minutes
sidebar:
  order: 2
---

## Start a Session

```bash
nexus run
```

This launches an interactive session with all permitted modules loaded. In offline mode (no LLM server), NEXUS uses its built-in keyword routing and module logic without generative AI responses.

## With a Local LLM

Start a llama.cpp server in a separate terminal:

```bash
llama-server -m models/qwen3-8b-q4_k_m.gguf -c 4096 --port 8384
```

Then start NEXUS:

```bash
nexus run
```

NEXUS auto-detects the model server and routes messages through the LLM for richer responses.

## Enable Modules

By default, modules start at trust level 0. Grant permission to use a module:

```bash
nexus allow oracle
nexus allow atlas
```

## Check System State

```bash
nexus status
```

Shows: database path, model connection, port, and which modules are currently permitted.
```

`site/src/content/docs/getting-started/configuration.md`:

```markdown
---
title: Configuration
description: Configure NEXUS paths, models, and environment
sidebar:
  order: 3
---

## Data Directory

NEXUS follows XDG conventions. By default, data lives at:

- **macOS/Linux:** `~/.local/share/nexus/`
- **Override:** Set `NEXUS_DATA_DIR` environment variable

The data directory contains:
- `nexus.db` -- SQLite database (memory, audit trail, trust scores)
- `models/` -- GGUF model files (if stored locally)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_DATA_DIR` | `~/.local/share/nexus` | Data directory path |
| `NEXUS_LLM_PORT` | `8384` | Port for llama.cpp HTTP server |
| `NEXUS_LLM_HOST` | `localhost` | Host for LLM server |
| `NEXUS_LOG_LEVEL` | `INFO` | Logging verbosity |

## Model Selection

NEXUS works with any GGUF model served over HTTP. Recommended models (MIT/Apache 2.0 licensed):

| Model | Size | RAM Needed | Best For |
|-------|------|-----------|----------|
| Qwen 3 8B Q4_K_M | ~4.5 GB | 8 GB | Default, good all-around |
| Qwen 3 32B Q4_K_M | ~18 GB | 32 GB | Higher reasoning quality |
| DeepSeek-V3 (quantized) | ~20 GB | 32 GB | Complex multi-step tasks |
| Phi-4 Q4_K_M | ~3.5 GB | 8 GB | Lighter alternative |

Swap models at any time -- just point llama-server at a different GGUF file and restart it. NEXUS reconnects automatically.
```

- [ ] **Step 2: Create Architecture pages**

`site/src/content/docs/architecture/overview.md`:

```markdown
---
title: Overview
description: How NEXUS is designed
sidebar:
  order: 1
---

## Microkernel Architecture

NEXUS is a microkernel. A small, stable core (~500 lines across five files) manages everything else. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on.

The kernel handles five concerns: routing (Cortex), memory (Engram), messaging (Pulse), auditing (Chronicle), and trust (Aegis). Everything else is a loadable module.

## How a Message Flows

1. User sends a message
2. **Cortex** scores the message against keyword tables and selects the best module
3. **Aegis** checks if that module has permission to respond
4. **Chronicle** logs the routing decision
5. **Engram** stores the user message in episodic memory
6. The selected module processes the message (optionally using the LLM)
7. **Engram** stores the module's response
8. **Chronicle** logs the response
9. **Pulse** publishes the response for any listening modules

Every step is logged. Every permission is checked. Every interaction is remembered.

## Design Constraints

- **Local-first.** No feature requires a network connection.
- **8 GB floor.** The smallest useful configuration runs on 8 GB RAM.
- **Model-agnostic.** Any GGUF model served over HTTP works. No vendor lock-in.
- **Apache 2.0.** The core is open source. Models are MIT/Apache 2.0 only.
```

`site/src/content/docs/architecture/kernel.md`:

```markdown
---
title: Kernel
description: The five kernel components
sidebar:
  order: 2
---

## The Five Components

The kernel is five components, each with one job:

### Cortex (Router)

Receives all user input and decides which module should handle it. Uses keyword-weighted scoring against a configurable routing table. Falls back to the `general` module when no keywords match.

Cortex also enforces permissions -- it checks with Aegis before dispatching to any module. If a module is denied, the user is told how to enable it.

**Key method:** `process(message)` -- routes, checks permissions, dispatches, logs, returns response.

### Engram (Memory)

Three-tier memory system:

- **Working memory** -- ephemeral key-value store for current session context
- **Episodic memory** -- time-stamped events with full-text search (SQLite FTS5)
- **Semantic memory** -- vector embeddings for similarity search (sqlite-vec)

All modules read from and write to Engram. This is how cross-domain synthesis happens -- the memory is shared, not siloed.

### Pulse (Message Bus)

Async pub/sub message bus with priority queuing and wildcard topic matching. Modules communicate through Pulse without knowing about each other. Each message carries a topic, source, priority, and payload.

### Chronicle (Audit Trail)

Immutable audit log. Every routing decision, permission check, module response, and trust adjustment is recorded with timestamps. Uses SQLite WAL mode for concurrent read/write. Designed for SOC 2 and HIPAA compliance exports.

### Aegis (Trust Engine)

Graduated trust from 0 to 100, per module. Actions are checked against the trust threshold. Positive outcomes increase trust, negative outcomes decrease it. Trust history is stored permanently -- you can always see why a module has its current score.
```

`site/src/content/docs/architecture/modules.md`:

```markdown
---
title: Modules
description: How NEXUS modules work
sidebar:
  order: 3
---

## Module Architecture

Every NEXUS module extends `NexusModule` and implements three things:

1. **`name`** -- unique string identifier (e.g., `"oracle"`)
2. **`description`** -- human-readable one-liner
3. **`handle(message, context)`** -- async method that processes user messages

```python
from nexus.modules.base import NexusModule
from typing import Any

class MyModule(NexusModule):
    name = "my_module"
    description = "Does something useful"
    version = "0.1.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "Response from my module"
```

## Lifecycle

- **`on_load()`** -- called when the module is registered with Cortex
- **`handle(message, context)`** -- called for each routed message
- **`on_unload()`** -- called when the module is removed

## Context

The `context` dict passed to `handle()` provides access to kernel services:

| Key | Type | What it provides |
|-----|------|-----------------|
| `llm` | callable | LLM inference function (None if no model connected) |
| `engram` | `Engram` | Memory system (working, episodic, semantic) |
| `chronicle` | `Chronicle` | Audit logging |
| `pulse` | `Pulse` | Message bus for inter-module communication |

## Module Tiers

Modules are organized into tiers by function:

- **Perception** -- bring information into the system (Oracle, Sentry)
- **Intelligence** -- reason about information (Atlas, Prism, Cipher)
- **Action** -- do things in the world (Wraith, Echo, Sigil, Herald, Weave)
- **Advanced Intelligence** -- higher-order reasoning (Specter, Chronos, Dreamweaver, Serendipity, Forge)
- **Network** -- multi-instance and persistence (Collective, Legacy)
```

- [ ] **Step 3: Create Concepts pages**

`site/src/content/docs/concepts/earned-autonomy.md`:

```markdown
---
title: Earned Autonomy
description: How NEXUS modules earn trust over time
sidebar:
  order: 1
---

## Trust is Earned, Not Assumed

Every module starts at trust level 0. It can observe but not act. The user grants permissions explicitly with `nexus allow <module>`, and the system tracks outcomes.

Aegis maintains a trust score from 0 to 100 for each module. The score adjusts based on results:

- **Positive outcomes** increase trust -- the module earns more latitude
- **Negative outcomes** decrease trust -- the module loses autonomy
- **Every adjustment is logged** in Chronicle with the reason

This is not a binary switch. It is a continuous score, per module, enforced on every call.

## How Trust Flows

```
User grants permission -> Module starts at base trust
Module produces good result -> Trust increases
Module produces bad result -> Trust decreases
Trust drops below threshold -> Module requires approval for actions
Trust rises above threshold -> Module acts autonomously
```

## Why This Matters

Most AI systems ask for blanket permission upfront. NEXUS inverts this: it proves competence before gaining autonomy. You can always see why a module has its current trust level, and you can revoke it at any time with `nexus deny <module>`.
```

`site/src/content/docs/concepts/memory-tiers.md`:

```markdown
---
title: Memory Tiers
description: How NEXUS remembers -- working, episodic, and semantic memory
sidebar:
  order: 2
---

## Three Tiers of Memory

Engram manages three distinct memory systems:

### Working Memory

Ephemeral key-value store for the current session. Cleared on restart. Used for conversation context, active tasks, and temporary state.

### Episodic Memory

Time-stamped records of every interaction, stored in SQLite with FTS5 full-text search. This is the "what happened" layer -- every user message, every module response, every routing decision is recorded here.

Searchable by content, time range, and source module. Used by Dreamweaver for overnight synthesis and by Chronos for temporal analysis.

### Semantic Memory

Vector embeddings for similarity search. Facts, patterns, and learned preferences are embedded and stored via sqlite-vec. This is the "what does it mean" layer -- it enables cross-domain connections and pattern matching.

## All Modules Share Memory

The critical design choice: memory is not siloed per module. Oracle's triggers, Atlas's knowledge graph, Echo's behavioral patterns, and Prism's cross-domain insights all read from and write to the same Engram. This shared memory is what enables cross-domain synthesis -- connections that no single module could find alone.
```

`site/src/content/docs/concepts/audit-trail.md`:

```markdown
---
title: Audit Trail
description: How Chronicle logs every action for accountability
sidebar:
  order: 3
---

## Immutable Logging

Chronicle records every significant action in the system:

- **Routing decisions** -- which module was selected and why
- **Permission checks** -- which modules were allowed or denied
- **Module responses** -- what each module returned
- **Trust adjustments** -- when and why trust scores changed
- **Memory operations** -- what was stored and retrieved

Every record has a timestamp. Records are append-only -- they cannot be modified or deleted (except via the explicit `nexus forget --yes` GDPR command, which wipes everything).

## Storage

Chronicle uses SQLite in WAL (Write-Ahead Logging) mode for concurrent read/write access. This means modules can log events while other processes read the audit trail without blocking.

## Compliance

The audit trail is designed to support:

- **SOC 2** -- complete audit of system actions and access
- **HIPAA** -- full record of data access and processing
- **GDPR Art. 17** -- right to erasure via `nexus forget --yes`

You can always answer the question: "Why did the system do that?"
```

`site/src/content/docs/concepts/design-philosophy.md`:

```markdown
---
title: Design Philosophy
description: The principles behind NEXUS
sidebar:
  order: 4
---

## Local-First

Your data never leaves your machine unless you tell it to. There are no analytics, no telemetry, no training on your data, no API keys required. The full system runs on a laptop.

## Anti-Fragile

NEXUS includes systems designed to make you more robust, not more dependent:

- **Specter** stress-tests your decisions before you make them
- **Serendipity** fights filter bubbles by surfacing connections from fields you are not looking at
- **Cipher** tracks the trustworthiness of information sources
- **Sigil** watches for threats and anomalies

The system argues with itself so you don't have to.

## Compounding Value

NEXUS does not reset between sessions. Through behavioral fingerprinting (Echo), knowledge crystallization (Legacy), and long-term memory (Engram), the system becomes more valuable over months and years. It builds a persistent, evolving model of your world.

## Microkernel, Not Monolith

The kernel is ~500 lines across five files. If you can read Python, you can understand the entire core. Modules are loaded and unloaded without restarting. If a module misbehaves, deny it and move on. The system is designed so that a single developer can understand the full architecture.

## Model-Agnostic

Qwen, DeepSeek, Phi, Gemma -- anything served over HTTP works. NEXUS speaks one protocol (llama.cpp HTTP API). Swap in Ollama. Swap in a remote endpoint. The kernel does not care. Models are MIT or Apache 2.0 licensed only -- no vendor lock-in, no usage restrictions.
```

- [ ] **Step 4: Create Guide pages**

`site/src/content/docs/guides/building-a-module.md`:

```markdown
---
title: Building a Module
description: How to create a custom NEXUS module
sidebar:
  order: 1
---

## 1. Create the Module File

Create a new file in `nexus/modules/`:

```python
# nexus/modules/my_module.py
"""
MyModule — does something useful.
Short description of what this module does and why.
"""
from typing import Any
from nexus.modules.base import NexusModule


class MyModule(NexusModule):
    name = "my_module"
    description = "Does something useful"
    version = "0.1.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        """Process a user message and return a response."""
        # Access kernel services via context
        llm = context.get("llm")
        engram = context["engram"]
        chronicle = context["chronicle"]

        # Your logic here
        return "[MyModule] Response"
```

Three attributes are required: `name`, `description`, `version`. The `handle()` method is the entry point for all routed messages.

## 2. Add Routing Keywords

In `nexus/kernel/cortex.py`, add keywords to `_MODULE_KEYWORDS`:

```python
_MODULE_KEYWORDS: dict[str, list[str]] = {
    # ... existing entries ...
    "my_module": ["keyword1", "keyword2", "keyword3"],
}
```

When a user message contains these keywords, Cortex routes it to your module.

## 3. Write Tests

Create `tests/modules/test_my_module.py`:

```python
import pytest
from nexus.modules.my_module import MyModule


@pytest.fixture
def module():
    return MyModule()


def test_module_attributes(module):
    assert module.name == "my_module"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module):
    ctx = {"engram": None, "chronicle": None, "pulse": None, "llm": None}
    result = await module.handle("test message", ctx)
    assert isinstance(result, str)
    assert len(result) > 0
```

## 4. Run Tests

```bash
pytest tests/modules/test_my_module.py -v
```

## 5. Enable the Module

```bash
nexus allow my_module
```
```

`site/src/content/docs/guides/connecting-an-llm.md`:

```markdown
---
title: Connecting an LLM
description: How to set up local LLM inference for NEXUS
sidebar:
  order: 2
---

## Default: llama.cpp

NEXUS communicates with LLMs over HTTP. The default setup uses llama.cpp:

```bash
# Install llama.cpp (macOS)
brew install llama.cpp

# Or build from source
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && make
```

## Download a Model

NEXUS uses GGUF-format models. Recommended (all MIT or Apache 2.0 licensed):

| Model | Download Size | RAM Usage |
|-------|--------------|-----------|
| Qwen 3 8B Q4_K_M | ~4.5 GB | ~5.5 GB |
| Phi-4 Q4_K_M | ~3.5 GB | ~4.5 GB |

Download from HuggingFace and place in your preferred directory.

## Start the Server

```bash
llama-server -m /path/to/model.gguf -c 4096 --port 8384
```

NEXUS connects to `localhost:8384` by default. Override with environment variables:

```bash
export NEXUS_LLM_HOST=localhost
export NEXUS_LLM_PORT=8384
```

## Using Ollama

Ollama serves models with a compatible HTTP API:

```bash
ollama serve
ollama pull qwen3:8b
```

Point NEXUS to Ollama's port:

```bash
export NEXUS_LLM_PORT=11434
nexus run
```

## Remote Endpoints

Any HTTP endpoint that accepts the llama.cpp chat completion format works. Set the host and port accordingly. The kernel does not care where inference happens -- it speaks one protocol.
```

`site/src/content/docs/guides/running-tests.md`:

```markdown
---
title: Running Tests
description: How to run and write tests for NEXUS
sidebar:
  order: 3
---

## Run All Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

233 tests. Under two seconds. No network, no mocks of external services, no flaky anything.

## Test Structure

```
tests/
├── kernel/          ← Tests for Cortex, Engram, Pulse, Chronicle, Aegis
├── modules/         ← Tests for each module (oracle, sentry, atlas, ...)
├── inference/       ← Tests for LLM client
├── site/            ← Tests for doc generation script
├── test_integration.py
├── test_batch2_integration.py
├── test_batch3_integration.py
├── test_batch4_integration.py
└── test_batch5_integration.py
```

## Run Specific Tests

```bash
# Single file
pytest tests/modules/test_oracle.py -v

# Single test
pytest tests/modules/test_oracle.py::test_evaluate_fires_matching_rule -v

# By keyword
pytest tests/ -k "cortex" -v
```

## Writing Tests

Every module test follows the same pattern:

1. Create a `@pytest.fixture` that instantiates the module
2. Test that `name`, `description`, and `version` are set
3. Test `handle()` returns a non-empty string
4. Test module-specific logic (methods, edge cases)
5. Use `@pytest.mark.asyncio` for async tests

Tests use no external services. Memory tests use temporary SQLite databases via `tmp_path`. No mocks of external APIs.
```

- [ ] **Step 5: Build and verify**

Run:
```bash
cd /Users/connorevans/Downloads/NEXUS
python site/scripts/generate-docs.py
cd site && npm run build
```
Expected: Build succeeds with all documentation pages.

- [ ] **Step 6: Commit**

```bash
git add site/src/content/docs/getting-started/ site/src/content/docs/architecture/ site/src/content/docs/concepts/ site/src/content/docs/guides/
git commit -m "docs(site): getting started, architecture, concepts, and guides pages"
```

---

### Task 5: GitHub Actions Deployment

**Files:**
- Create: `.github/workflows/deploy-site.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Deploy NEXUS Site

on:
  push:
    branches: [main]
    paths:
      - 'site/**'
      - 'nexus/**'
      - '.github/workflows/deploy-site.yml'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: site/package-lock.json

      - name: Generate reference docs
        run: python site/scripts/generate-docs.py

      - name: Install site dependencies
        run: cd site && npm ci

      - name: Build site
        run: cd site && npm run build

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/dist

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Verify the workflow file is valid YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-site.yml'))" 2>&1 || echo "Install pyyaml or just verify manually"`
Expected: No errors, or manual verification that the YAML structure is correct.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-site.yml
git commit -m "ci: GitHub Actions workflow for NEXUS site deployment"
```

---

### Task 6: Final Build Verification + README Update

**Files:**
- Modify: `README.md` (update NEXUS SITE roadmap entry and add site link)
- Modify: `site/src/content/docs/reference/` (regenerate from latest source)

- [ ] **Step 1: Run the full pipeline locally**

```bash
cd /Users/connorevans/Downloads/NEXUS
python site/scripts/generate-docs.py
cd site && npm run build
```

Expected: Clean build, no errors, `dist/` contains complete site.

- [ ] **Step 2: Run all tests**

```bash
cd /Users/connorevans/Downloads/NEXUS
.venv/bin/pytest tests/ -v
```

Expected: All tests pass (242+).

- [ ] **Step 3: Update README roadmap**

In `README.md`, change the NEXUS SITE entry from:

```
    NEXUS SITE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ░░░░░░░░░░ PLANNED
    └── Community site ·· documentation & module catalog
```

to:

```
    NEXUS SITE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ██████████ BUILT
    └── Community site ·· documentation & module catalog
```

- [ ] **Step 4: Commit and push**

```bash
git add README.md site/src/content/docs/reference/
git commit -m "feat(site): complete NEXUS documentation site — mark roadmap BUILT"
git push
```

Expected: Push triggers the GitHub Actions workflow. Site deploys to `https://allstreets.github.io/NEXUS/`.
