"""Export the v1 manifest pydantic model as JSON Schema (Draft 2020-12)."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.agents.manifest import Manifest

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "manifest.v1.json"


def export_schema() -> dict:
    """Generate the JSON Schema dict for Manifest."""
    return Manifest.model_json_schema(mode="validation")


def write_schema() -> Path:
    """Write the schema to nexus/schemas/manifest.v1.json and return the path."""
    _SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SCHEMA_PATH.write_text(json.dumps(export_schema(), indent=2))
    return _SCHEMA_PATH


if __name__ == "__main__":
    path = write_schema()
    print(f"Wrote schema to {path}")
