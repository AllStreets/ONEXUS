"""
ModuleRegistry — reads, queries, and manages the community module registry.
Registry data lives in community/registry.json.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ModuleRegistry:
    def __init__(self, registry_path: Path):
        self._path = registry_path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {"modules": []}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._data["modules"])

    def get(self, name: str) -> dict[str, Any] | None:
        for mod in self._data["modules"]:
            if mod["name"] == name:
                return mod
        return None

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        results = []
        for mod in self._data["modules"]:
            if (q in mod["name"].lower()
                    or q in mod.get("author", "").lower()
                    or q in mod.get("description", "").lower()
                    or any(q in kw.lower() for kw in mod.get("keywords", []))):
                results.append(mod)
        return results

    def add(self, module_info: dict[str, Any]) -> None:
        if "approved_at" not in module_info:
            module_info["approved_at"] = datetime.now(timezone.utc).isoformat()
        self._data["modules"].append(module_info)
        self._save()

    def remove(self, name: str) -> None:
        self._data["modules"] = [m for m in self._data["modules"] if m["name"] != name]
        self._save()
