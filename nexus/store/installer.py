"""Install a catalog agent from its verified recipe.

An install is a job with three steps, each reported as it runs:

  get    pull the prebuilt image, pull the published image by digest, or build the
         recipe's exact Dockerfile
  check  start it with round 3's confinement (no network) and the keys the person gave,
         and ask it for its tools over MCP
  save   write the install record, and the keys to the 0600 secrets file

Nothing is recorded unless every step passes, so a failed install leaves no trace but
the image, which is removed.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from nexus.agents.confine import Confinement, prepare
from nexus.store.handshake import handshake
from nexus.store.recipes import RecipeIndex, is_installable
from nexus.store.state import InstallRecord, StoreState

_HOST = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d{1,5})?$")
_ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
STEPS = ("get", "check", "save")


class InstallError(ValueError):
    pass


@dataclass
class Step:
    name: str
    status: str = "pending"  # pending | running | done | failed
    detail: str = ""


@dataclass
class Job:
    id: str
    slug: str
    state: str = "running"  # running | done | failed
    steps: list[Step] = field(default_factory=lambda: [Step(n) for n in STEPS])
    error: str = ""
    tools: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "slug": self.slug, "state": self.state, "error": self.error,
                "tools": self.tools, "steps": [vars(s) for s in self.steps]}


def _docker(*argv: str, input: str | None = None, timeout: int = 1200) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argv], input=input, capture_output=True, text=True, timeout=timeout)


class Installer:
    def __init__(self, state: StoreState, recipes: RecipeIndex, *,
                 docker: Callable[..., subprocess.CompletedProcess] = _docker,
                 check: Callable[..., dict] | None = None, chronicle=None) -> None:
        self.state, self.recipes = state, recipes
        self._docker = docker
        self._check = check or self._confined_handshake
        self._chronicle = chronicle
        self._jobs: dict[str, Job] = {}
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    # -- requests -------------------------------------------------------------------

    def validate(self, slug: str, hosts: list[str], env: dict[str, str]) -> dict[str, Any]:
        recipe = self.recipes.get(slug)
        if not recipe or not is_installable(recipe):
            raise InstallError(f"'{slug}' has no verified recipe, so it can't be installed")
        self.validate_hosts(hosts)
        declared = {e["name"]: e for e in recipe.get("env") or []}
        unknown = [k for k in env if k not in declared or not _ENV.match(k)]
        if unknown:
            raise InstallError(f"keys this agent doesn't declare: {', '.join(unknown)}")
        missing = [n for n, e in declared.items() if e.get("required") and not env.get(n)]
        if missing:
            raise InstallError(f"this agent needs: {', '.join(missing)}")
        return recipe

    @staticmethod
    def validate_hosts(hosts: list[str]) -> None:
        bad = [h for h in hosts if not _HOST.match(h.lower())]
        if bad:
            raise InstallError(f"not host names: {', '.join(bad)}")

    def start(self, slug: str, hosts: list[str], env: dict[str, str]) -> Job:
        recipe = self.validate(slug, hosts, env)
        with self._lock:
            if slug in self._busy:
                raise InstallError(f"'{slug}' is already installing")
            self._busy.add(slug)
            job = Job(id=uuid.uuid4().hex[:12], slug=slug)
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, recipe, [h.lower() for h in hosts], dict(env)),
                         daemon=True).start()
        return job

    def job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def uninstall(self, slug: str) -> bool:
        rec = self.state.get(slug)
        removed = self.state.remove(slug)
        if rec and not rec.prebuilt and rec.kind != "oci":
            self._docker("rmi", "-f", rec.image, timeout=120)
        if removed:
            self._log("store_uninstalled", {"slug": slug})
        return removed

    # -- the job ----------------------------------------------------------------------

    def _run(self, job: Job, recipe: dict, hosts: list[str], env: dict[str, str]) -> None:
        image = None
        try:
            image, prebuilt = self._step(
                job, "get", lambda: self._get(recipe),
                lambda out: "downloaded" if out[1] or recipe["install"]["kind"] == "oci" else "built on this machine")
            tools = self._step(job, "check", lambda: self._checked(recipe, image, env),
                               lambda out: f"started confined and offered {len(out)} tools")
            job.tools = tools
            inst = recipe["install"]
            record = InstallRecord(
                slug=recipe["slug"], image=image, kind=inst["kind"],
                version=inst.get("version") or inst.get("digest") or "",
                command=list(recipe.get("command") or []), args=list(recipe.get("args") or []),
                env_names=[e["name"] for e in recipe.get("env") or []], hosts=hosts, tools=tools,
                recipe_commit=(recipe.get("source") or {}).get("commit", ""),
                installed_at=datetime.now(UTC).isoformat(timespec="seconds"), prebuilt=prebuilt,
            )
            self._step(job, "save", lambda: self.state.save(record, {k: v for k, v in env.items() if v}),
                       lambda out: "installed")
            job.state = "done"
            self._log("store_installed", {"slug": record.slug, "image": image, "tools": tools,
                                          "hosts": hosts, "keys": sorted(k for k, v in env.items() if v)})
        except Exception as exc:  # every failure ends the job in words
            job.state, job.error = "failed", str(exc)[:600]
            if image and recipe["install"]["kind"] != "oci":
                self._docker("rmi", "-f", image, timeout=120)
            self._log("store_install_failed", {"slug": job.slug, "error": job.error})
        finally:
            with self._lock:
                self._busy.discard(job.slug)

    def _step(self, job: Job, name: str, fn, describe=lambda out: ""):
        step = next(s for s in job.steps if s.name == name)
        step.status = "running"
        try:
            out = fn()
        except Exception as exc:
            step.status, step.detail = "failed", str(exc)[:600]
            raise
        step.status, step.detail = "done", describe(out)
        return out

    def _get(self, recipe: dict) -> tuple[str, bool]:
        inst = recipe["install"]
        pre = (recipe.get("prebuilt") or {}).get("image")
        if pre:
            p = self._docker("pull", "-q", pre)
            if p.returncode == 0:
                return pre, True
        if inst["kind"] == "oci":
            ref = f"{inst['image'].split('@')[0]}@{inst['digest']}"
            p = self._docker("pull", "-q", ref)
            if p.returncode != 0:
                raise InstallError("could not download the image: " + (p.stderr or p.stdout).strip()[-300:])
            return ref, False
        tag = f"onexus-store/{recipe['slug']}:{(inst.get('version') or 'x').replace('+', '-')}"
        p = self._docker("build", "-q", "-t", tag, "-", input=recipe["dockerfile"])
        if p.returncode != 0:
            raise InstallError("the build failed: " + (p.stderr or p.stdout).strip()[-400:])
        return tag, False

    def _checked(self, recipe: dict, image: str, env: dict[str, str]) -> list[str]:
        res = self._check(recipe, image, env)
        if not res.get("ok"):
            raise InstallError("it didn't start: " + res.get("reason", "no answer"))
        return res["tools"]

    def _confined_handshake(self, recipe: dict, image: str, env: dict[str, str]) -> dict:
        command = list(recipe.get("command") or [])
        conf = Confinement(image=image, command=command[0] if command else None, entrypoint=not command)
        launch = prepare(conf, recipe["slug"], command[0] if command else "", command[1:] + list(recipe.get("args") or []), env.keys())
        # PATH and HOME are for the docker CLI on this machine; the container gets HOME=/work
        child_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/"), **env}
        try:
            return handshake(launch.argv, env=child_env)
        finally:
            launch.cleanup()

    def _log(self, event: str, payload: dict) -> None:
        if self._chronicle is not None:
            try:
                self._chronicle.log("store", event, payload)
            except Exception:
                pass

