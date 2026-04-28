import json
import pytest
from pathlib import Path
from nexus.community.installer import ModuleInstaller


@pytest.fixture
def community_root(tmp_path):
    mod_dir = tmp_path / "community" / "modules" / "testuser" / "greet"
    mod_dir.mkdir(parents=True)

    (mod_dir / "manifest.json").write_text(json.dumps({
        "name": "greet",
        "author": "testuser",
        "description": "A greeting module.",
        "version": "1.0.0",
        "tier": "community",
        "keywords": ["hello", "greet", "welcome"],
        "license": "MIT",
    }))

    (mod_dir / "module.py").write_text('''
from nexus.modules.base import NexusModule
from typing import Any

class GreetModule(NexusModule):
    name = "greet"
    description = "A greeting module."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        return "Hello!"
''')

    tests_dir = mod_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_greet.py").write_text("def test_ok(): assert True")

    return tmp_path / "community"


@pytest.fixture
def install_dir(tmp_path):
    d = tmp_path / "installed"
    d.mkdir()
    return d


@pytest.fixture
def installer(community_root, install_dir):
    return ModuleInstaller(community_root=community_root, install_dir=install_dir)


def test_install_copies_module(installer, install_dir):
    result = installer.install("testuser/greet")
    assert result.success is True
    assert (install_dir / "greet").exists()
    assert (install_dir / "greet" / "module.py").exists()
    assert (install_dir / "greet" / "manifest.json").exists()


def test_install_returns_keywords(installer):
    result = installer.install("testuser/greet")
    assert result.keywords == ["hello", "greet", "welcome"]


def test_install_nonexistent_module(installer):
    result = installer.install("nobody/nothing")
    assert result.success is False
    assert "not found" in result.error.lower()


def test_uninstall_removes_module(installer, install_dir):
    installer.install("testuser/greet")
    assert (install_dir / "greet").exists()

    result = installer.uninstall("greet")
    assert result.success is True
    assert not (install_dir / "greet").exists()


def test_uninstall_nonexistent(installer):
    result = installer.uninstall("nonexistent")
    assert result.success is False


def test_list_installed(installer, install_dir):
    assert installer.list_installed() == []
    installer.install("testuser/greet")
    installed = installer.list_installed()
    assert len(installed) == 1
    assert installed[0]["name"] == "greet"
