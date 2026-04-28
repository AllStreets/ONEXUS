"""
ModuleInstaller — install and uninstall community modules.
Copies module files from community/modules/<author>/<name>/ to the active install dir.
"""
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InstallResult:
    success: bool
    error: str = ""
    keywords: list[str] = field(default_factory=list)


class ModuleInstaller:
    def __init__(self, community_root: Path, install_dir: Path):
        self._community_root = community_root
        self._install_dir = install_dir

    def install(self, module_path: str) -> InstallResult:
        parts = module_path.split("/")
        if len(parts) != 2:
            return InstallResult(success=False, error=f"Invalid path '{module_path}' — expected 'author/module_name'")

        author, name = parts
        source = self._community_root / "modules" / author / name
        if not source.exists():
            return InstallResult(success=False, error=f"Module '{module_path}' not found")

        dest = self._install_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

        manifest_path = dest / "manifest.json"
        keywords: list[str] = []
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            keywords = manifest.get("keywords", [])

        return InstallResult(success=True, keywords=keywords)

    def uninstall(self, module_name: str) -> InstallResult:
        dest = self._install_dir / module_name
        if not dest.exists():
            return InstallResult(success=False, error=f"Module '{module_name}' is not installed")

        shutil.rmtree(dest)
        return InstallResult(success=True)

    def list_installed(self) -> list[dict[str, Any]]:
        installed = []
        for mod_dir in sorted(self._install_dir.iterdir()):
            if not mod_dir.is_dir():
                continue
            manifest_path = mod_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                installed.append(manifest)
        return installed
