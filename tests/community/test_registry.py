import json
import pytest
from pathlib import Path
from nexus.community.registry import ModuleRegistry


@pytest.fixture
def registry_file(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "modules": [
            {
                "name": "example_mod",
                "author": "testuser",
                "description": "An example module.",
                "version": "1.0.0",
                "tier": "community",
                "keywords": ["test", "example"],
                "path": "community/modules/testuser/example_mod",
                "approved_at": "2026-04-28T00:00:00Z",
            },
            {
                "name": "data_tools",
                "author": "devuser",
                "description": "Data analysis tools.",
                "version": "2.1.0",
                "tier": "community",
                "keywords": ["data", "analysis", "csv"],
                "path": "community/modules/devuser/data_tools",
                "approved_at": "2026-04-27T00:00:00Z",
            },
        ]
    }))
    return reg_path


@pytest.fixture
def empty_registry(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({"modules": []}))
    return reg_path


def test_registry_list_all(registry_file):
    reg = ModuleRegistry(registry_file)
    modules = reg.list_all()
    assert len(modules) == 2


def test_registry_search_by_name(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("example")
    assert len(results) == 1
    assert results[0]["name"] == "example_mod"


def test_registry_search_by_keyword(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("csv")
    assert len(results) == 1
    assert results[0]["name"] == "data_tools"


def test_registry_search_by_author(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("devuser")
    assert len(results) == 1


def test_registry_search_no_results(registry_file):
    reg = ModuleRegistry(registry_file)
    results = reg.search("nonexistent")
    assert len(results) == 0


def test_registry_get_by_name(registry_file):
    reg = ModuleRegistry(registry_file)
    mod = reg.get("example_mod")
    assert mod is not None
    assert mod["author"] == "testuser"


def test_registry_get_missing_returns_none(registry_file):
    reg = ModuleRegistry(registry_file)
    assert reg.get("missing") is None


def test_registry_empty(empty_registry):
    reg = ModuleRegistry(empty_registry)
    assert reg.list_all() == []
    assert reg.search("anything") == []


def test_registry_add_module(empty_registry):
    reg = ModuleRegistry(empty_registry)
    reg.add({
        "name": "new_mod",
        "author": "user1",
        "description": "New module.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["new"],
        "path": "community/modules/user1/new_mod",
    })
    assert len(reg.list_all()) == 1
    assert reg.get("new_mod") is not None


def test_registry_remove_module(registry_file):
    reg = ModuleRegistry(registry_file)
    reg.remove("example_mod")
    assert len(reg.list_all()) == 1
    assert reg.get("example_mod") is None
