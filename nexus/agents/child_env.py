"""The environment a launched agent process gets: a small baseline plus what it declared.

Before red-team round 2 (docs/REDTEAM-AEGIS.md) both launch paths passed the operator's
whole environment to every agent, and the launcher also injected provider API keys into
agents that never asked for them. An agent could read cloud credentials, tokens and keys
without its manifest declaring them and without a single call reaching Aegis.

Now a child gets:

* the baseline below: what a process needs to find programs, a home directory, a temp
  directory and a locale, and nothing that is a credential;
* the variables its manifest declares (``env`` in a catalog adapter, ``env_keys`` in a
  manifest's runtime), copied from the operator's environment when they are set;
* provider keys from the kernel's router, only when the agent declares that variable;
* anything the operator explicitly adds with ``NEXUS_AGENT_ENV_PASSTHROUGH`` (a comma- or
  whitespace-separated list of names), the same escape hatch the command allowlist has.

This closes the environment leak only. It is not a sandbox: the process still runs as the
operator, with the operator's filesystem and network. Containers are round 3.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

BASELINE: frozenset[str] = frozenset(
    {
        # finding programs, home and temp
        "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP",
        # locale, terminal and time zone
        "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TERM", "TZ",
        # Windows equivalents of the above
        "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "WINDIR", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA",
    }
)

PASSTHROUGH_VAR = "NEXUS_AGENT_ENV_PASSTHROUGH"


def _operator_passthrough(environ: Mapping[str, str]) -> set[str]:
    raw = environ.get(PASSTHROUGH_VAR, "")
    return {t for t in raw.replace(",", " ").split() if t}


def child_environment(
    declared: Iterable[str],
    *,
    provider_keys: Mapping[str, str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the environment for an agent process.

    ``declared`` is the set of variable names the agent's manifest asks for.
    ``provider_keys`` maps a variable name (e.g. ``ANTHROPIC_API_KEY``) to a key the
    kernel holds; each is passed only if the agent declared that name and the
    operator's environment doesn't already set it.
    """
    src = os.environ if environ is None else environ
    wanted = BASELINE | set(declared) | _operator_passthrough(src)
    env = {k: src[k] for k in wanted if k in src}
    for name, key in (provider_keys or {}).items():
        if name in declared and name not in env and key:
            env[name] = key
    return env
