"""What the store has installed, and the keys people gave it.

Install records are `{data_dir}/store/installed/<slug>.json`. Key values live apart, in
`{data_dir}/store/secrets.json` with mode 0600, the same way provider keys are kept: they
are never written to a record, a log line, the ledger or an API response.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass
class InstallRecord:
    slug: str
    image: str
    kind: str
    version: str
    command: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    env_names: list[str] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    recipe_commit: str = ""
    installed_at: str = ""
    prebuilt: bool = False


class StoreState:
    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir) / "store"
        self._installed = self.root / "installed"
        self._secrets = self.root / "secrets.json"
        self._lock = threading.Lock()

    def _path(self, slug: str) -> Path:
        if not _SLUG.match(slug):
            raise ValueError(f"not a valid slug: {slug!r}")
        return self._installed / f"{slug}.json"

    def get(self, slug: str) -> InstallRecord | None:
        try:
            p = self._path(slug)
        except ValueError:
            return None
        if not p.exists():
            return None
        try:
            return InstallRecord(**json.loads(p.read_text()))
        except (OSError, ValueError, TypeError):
            return None

    def list(self) -> list[InstallRecord]:
        if not self._installed.is_dir():
            return []
        out = []
        for p in sorted(self._installed.glob("*.json")):
            rec = self.get(p.stem)
            if rec:
                out.append(rec)
        return out

    def save(self, record: InstallRecord, secrets: dict[str, str]) -> None:
        with self._lock:
            self._installed.mkdir(parents=True, exist_ok=True)
            _write_atomic(self._path(record.slug), json.dumps(asdict(record), indent=2), mode=0o644)
            allk = self._read_secrets()
            if secrets:
                allk[record.slug] = dict(secrets)
            else:
                allk.pop(record.slug, None)
            _write_atomic(self._secrets, json.dumps(allk), mode=0o600)

    def set_hosts(self, slug: str, hosts: list[str]) -> InstallRecord | None:
        with self._lock:
            rec = self.get(slug)
            if not rec:
                return None
            rec.hosts = list(hosts)
            _write_atomic(self._path(slug), json.dumps(asdict(rec), indent=2), mode=0o644)
            return rec

    def remove(self, slug: str) -> bool:
        with self._lock:
            p = self._path(slug)
            existed = p.exists()
            if existed:
                p.unlink()
            allk = self._read_secrets()
            if allk.pop(slug, None) is not None:
                _write_atomic(self._secrets, json.dumps(allk), mode=0o600)
            return existed

    def secrets_for(self, slug: str) -> dict[str, str]:
        return dict(self._read_secrets().get(slug) or {})

    def _read_secrets(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self._secrets.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


def _write_atomic(path: Path, text: str, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
