"""Read the catalog's recipes: how to install each agent as a confined MCP server.

Recipes live in the ONEXUS-Agents checkout under recipes/<slug>.json, written by its
resolver and verifier (pipeline/recipes/). The store offers only verified ones: built
from their recipe, started confined, and answered the MCP handshake.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecipeIndex:
    def __init__(self, catalog_root: str | Path) -> None:
        root = Path(catalog_root)
        # accept the ONEXUS-Agents checkout or its catalog/ folder
        self._dir = root.parent / "recipes" if root.name == "catalog" else root / "recipes"
        self._cache: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._cache is None:
            out: dict[str, dict[str, Any]] = {}
            if self._dir.is_dir():
                for p in sorted(self._dir.glob("[!_]*.json")):
                    try:
                        data = json.loads(p.read_text())
                    except (OSError, ValueError) as exc:
                        logger.warning("Unreadable recipe %s: %s", p, exc)
                        continue
                    if isinstance(data, dict) and data.get("slug"):
                        out[data["slug"]] = data
            self._cache = out
        return self._cache

    def reload(self) -> None:
        self._cache = None

    def get(self, slug: str) -> dict[str, Any] | None:
        return self._load().get(slug)

    def installable(self) -> list[dict[str, Any]]:
        return [r for r in self._load().values() if is_installable(r)]

    def summary(self) -> dict[str, Any]:
        p = self._dir / "_summary.json"
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            return {}


def is_installable(recipe: dict[str, Any]) -> bool:
    v = recipe.get("verified") or {}
    kind = (recipe.get("install") or {}).get("kind")
    if not v.get("ok") or kind not in ("npm", "pypi", "oci"):
        return False
    return bool(recipe.get("dockerfile")) if kind in ("npm", "pypi") else bool((recipe.get("install") or {}).get("digest"))
