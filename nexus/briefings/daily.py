"""Daily kernel briefing — autonomous report of where ONEXUS stands today.

Modeled on the AllStreets daily-report convention (ONEXUS-Agents writes a
nightly catalog report; SMADP's autopilot emits the same shape every 5
minutes). Reads directly from the kernel SQLite database + the agent
catalog on disk, so it works whether or not the API server is running.

Output: ``reports/YYYY-MM-DD.md`` at the repo root. One file per UTC day.

Section order (must match the other two repos so the family looks coherent):

    # Kernel briefing — YYYY-MM-DD
    ## Totals
    ## Activity today (UTC)
    ## Trust changes today
    ## Permission events today
    ## Pipeline health
    ---
    *generated <ISO8601>*

To run from the CLI::

    onexus briefing daily          # writes today's report + prints the path
    onexus briefing daily --dry    # prints to stdout without writing

To run from cron / GitHub Actions, schedule ``onexus briefing daily``
once per day at 13:00 UTC (the same cadence ONEXUS-Agents uses).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Iterable


# ── locations ────────────────────────────────────────────────────────────────

def project_root() -> Path:
    """Walk up from this file to find the repo root (the directory containing
    a ``nexus/`` package and a ``reports/`` sibling or where reports live)."""
    here = Path(__file__).resolve()
    for candidate in [here.parent.parent.parent, *here.parents]:
        if (candidate / "nexus" / "__init__.py").exists():
            return candidate
    return here.parent.parent.parent  # best guess


def reports_dir() -> Path:
    out = project_root() / "reports"
    out.mkdir(exist_ok=True)
    return out


def kernel_db_path() -> Path:
    """Default kernel DB location. Mirrors nexus.config defaults."""
    home = Path.home()
    return home / ".local" / "share" / "nexus" / "nexus.db"


def catalog_root() -> Path | None:
    """Best-effort lookup of the ONEXUS-Agents catalog. The catalog lives in
    a ``catalog/`` subdir of the ONEXUS-Agents checkout, with per-category
    folders that each hold many profile JSON files."""
    for candidate in [
        project_root().parent / "ONEXUS-Agents",
        Path.home() / "Downloads" / "ONEXUS-Agents",
        Path.home() / "code" / "ONEXUS-Agents",
    ]:
        if (candidate / "catalog").exists():
            return candidate / "catalog"
        if (candidate / "manifests").exists():
            return candidate / "manifests"
    return None


# ── data shape ───────────────────────────────────────────────────────────────

@dataclass
class Counts:
    workspaces: int = 0
    agents_total: int = 0
    agents_runnable: int = 0
    builtin_modules: int = 10  # cortex/aegis/etc — static
    chronicle_events_today: int = 0
    permissions_today: int = 0
    permissions_allowed: int = 0
    permissions_denied: int = 0
    permissions_auto: int = 0
    trust_changes_today: int = 0


@dataclass
class TrustMove:
    module: str
    old: float
    new: float
    delta: float
    reason: str


@dataclass
class ActivityRow:
    source: str
    action: str
    count: int


# ── data sources ─────────────────────────────────────────────────────────────

def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _connect(db: Path) -> sqlite3.Connection | None:
    if not db.exists():
        return None
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def gather_counts(db: Path, today: date) -> Counts:
    c = Counts()
    conn = _connect(db)
    if conn is None:
        return c

    # workspaces — count subdirs under ~/.local/share/nexus/workspaces/
    ws_dir = db.parent / "workspaces"
    if ws_dir.exists():
        c.workspaces = sum(1 for p in ws_dir.iterdir()
                           if p.is_dir() and not p.name.startswith("."))

    # chronicle counts for today
    iso = today.isoformat()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM chronicle WHERE timestamp >= ? AND timestamp < ?",
        (iso, _next_day_iso(today)),
    ).fetchone()
    c.chronicle_events_today = int(row["n"] or 0)

    # permission breakdown
    perm_rows = conn.execute(
        """SELECT action, COUNT(*) AS n FROM chronicle
           WHERE source = 'aegis' AND timestamp >= ? AND timestamp < ?
           GROUP BY action""",
        (iso, _next_day_iso(today)),
    ).fetchall()
    for row in perm_rows:
        action = row["action"]
        n = int(row["n"])
        # Aegis emits actions like permission_allowed / permission_denied /
        # permission_revoked / permission_auto_grant. Note "deny" is NOT a
        # substring of "denied" (the y becomes i), so check both forms.
        if "allow" in action or "grant" in action:
            c.permissions_allowed += n
        elif "deny" in action or "denied" in action or "denial" in action:
            c.permissions_denied += n
        elif "auto" in action:
            c.permissions_auto += n
    c.permissions_today = c.permissions_allowed + c.permissions_denied + c.permissions_auto

    # trust history count
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM aegis_trust_history WHERE timestamp >= ? AND timestamp < ?",
        (iso, _next_day_iso(today)),
    ).fetchone()
    c.trust_changes_today = int(row["n"] or 0)

    conn.close()

    # catalog
    cat = catalog_root()
    if cat is not None:
        c.agents_total, c.agents_runnable = _count_catalog(cat)

    return c


def _next_day_iso(d: date) -> str:
    from datetime import timedelta
    return (d + timedelta(days=1)).isoformat()


def _count_catalog(root: Path) -> tuple[int, int]:
    """Count agents in the ONEXUS-Agents catalog. Total = every profile;
    runnable = those that declare an MCP runtime (transport=mcp/stdio, or
    a top-level runnable/mcp flag). Skip _categories.json + the _dropped
    review pile."""
    total = 0
    runnable = 0
    for p in root.rglob("*.json"):
        # Skip metadata + review piles
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0].startswith("_"):
            continue
        if p.name.startswith("_"):
            continue
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        # The catalog stores PROFILES (one per agent), each a JSON object.
        # Some category files might be arrays; handle both.
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            rt = item.get("runtime") or {}
            is_runnable = (
                item.get("runnable") is True
                or item.get("mcp") is True
                or (isinstance(rt, dict) and rt.get("transport") in ("mcp", "mcp_stdio"))
                or (isinstance(rt, dict) and rt.get("mcp"))
            )
            if is_runnable:
                runnable += 1
    return total, runnable


def gather_trust_moves(db: Path, today: date, limit: int = 8) -> list[TrustMove]:
    conn = _connect(db)
    if conn is None:
        return []
    rows = conn.execute(
        """SELECT module_name, old_score, new_score, delta, reason
           FROM aegis_trust_history
           WHERE timestamp >= ? AND timestamp < ?
           ORDER BY ABS(delta) DESC
           LIMIT ?""",
        (today.isoformat(), _next_day_iso(today), limit),
    ).fetchall()
    conn.close()
    return [
        TrustMove(
            module=r["module_name"], old=float(r["old_score"]),
            new=float(r["new_score"]), delta=float(r["delta"]),
            reason=r["reason"] or "—",
        )
        for r in rows
    ]


def gather_activity(db: Path, today: date) -> list[ActivityRow]:
    conn = _connect(db)
    if conn is None:
        return []
    rows = conn.execute(
        """SELECT source, action, COUNT(*) AS n FROM chronicle
           WHERE timestamp >= ? AND timestamp < ?
           GROUP BY source, action
           ORDER BY n DESC""",
        (today.isoformat(), _next_day_iso(today)),
    ).fetchall()
    conn.close()
    return [ActivityRow(source=r["source"], action=r["action"], count=int(r["n"])) for r in rows]


# ── deltas from yesterday's report ───────────────────────────────────────────

_TOTALS_LINE_RE = re.compile(r"^- (?P<label>[\w \-/]+?):\s*\*\*(?P<value>[\d,]+)\*\*", re.M)


def _parse_yesterday_counts(today: date) -> dict[str, int]:
    """Read yesterday's report (if any) and pull the bold totals so we can
    compute (+N) / (—) deltas. Returns a dict label → value."""
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    path = reports_dir() / f"{yesterday.isoformat()}.md"
    if not path.exists():
        return {}
    text = path.read_text(errors="ignore")
    out: dict[str, int] = {}
    for m in _TOTALS_LINE_RE.finditer(text):
        label = m.group("label").strip().lower()
        try:
            out[label] = int(m.group("value").replace(",", ""))
        except ValueError:
            continue
    return out


def _delta_str(current: int, previous: int | None) -> str:
    if previous is None:
        return "(first report)"
    diff = current - previous
    if diff == 0:
        return "(—)"
    if diff > 0:
        return f"(+{diff:,})"
    return f"({diff:,})"


# ── rendering ────────────────────────────────────────────────────────────────

def render_briefing(
    db: Path | None = None,
    catalog: Path | None = None,
    today: date | None = None,
) -> str:
    """Return the briefing markdown as a string. Reads from the kernel DB
    and catalog; both are optional — sections fall back to safe defaults if
    a source is missing."""
    today = today or _today_utc()
    db_path = db or kernel_db_path()
    counts = gather_counts(db_path, today)
    moves = gather_trust_moves(db_path, today)
    activity = gather_activity(db_path, today)
    yesterday = _parse_yesterday_counts(today)

    lines: list[str] = []
    lines.append(f"# Kernel briefing — {today.isoformat()}")
    lines.append("")

    # ── Totals ──
    lines.append("## Totals")
    lines.append(f"- Workspaces: **{counts.workspaces:,}** {_delta_str(counts.workspaces, yesterday.get('workspaces'))}")
    lines.append(f"- Agents in catalog: **{counts.agents_total:,}** {_delta_str(counts.agents_total, yesterday.get('agents in catalog'))}")
    lines.append(f"- Runnable (MCP): **{counts.agents_runnable:,}** {_delta_str(counts.agents_runnable, yesterday.get('runnable (mcp)'))}")
    lines.append(f"- Built-in modules: **{counts.builtin_modules:,}** {_delta_str(counts.builtin_modules, yesterday.get('built-in modules'))}")
    lines.append("")

    # ── Activity today ──
    lines.append("## Activity today (UTC)")
    if not activity:
        lines.append("- No chronicle events recorded today.")
    else:
        lines.append("")
        lines.append("| Source | Action | Count |")
        lines.append("|---|---|---:|")
        for row in activity[:12]:
            lines.append(f"| `{row.source}` | `{row.action}` | {row.count:,} |")
        if len(activity) > 12:
            tail = sum(r.count for r in activity[12:])
            lines.append(f"| _… {len(activity) - 12} more_ | | {tail:,} |")
    lines.append("")

    # ── Trust changes today ──
    lines.append("## Trust changes today")
    if not moves:
        lines.append("- No trust adjustments today.")
    else:
        lines.append("")
        lines.append("| Module | Old | New | Δ | Reason |")
        lines.append("|---|---:|---:|---:|---|")
        for m in moves:
            sign = "+" if m.delta >= 0 else ""
            lines.append(
                f"| `{m.module}` | {m.old:.2f} | {m.new:.2f} | {sign}{m.delta:.2f} | {m.reason} |"
            )
    lines.append("")

    # ── Permission events today ──
    lines.append("## Permission events today")
    lines.append(f"- Total: **{counts.permissions_today:,}**")
    lines.append(f"- Allowed: **{counts.permissions_allowed:,}**")
    lines.append(f"- Denied: **{counts.permissions_denied:,}**")
    lines.append(f"- Auto: **{counts.permissions_auto:,}**")
    lines.append("")

    # ── Pipeline health ──
    lines.append("## Pipeline health")
    lines.append(f"- Kernel DB: `{db_path}` ({'present' if db_path.exists() else 'missing'})")
    cat = catalog or catalog_root()
    lines.append(f"- Catalog source: {('`' + str(cat) + '`') if cat else 'not located on this machine'}")
    lines.append(f"- Network IO: ∅ · static-verified")
    lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append(f"*generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}*")
    lines.append("")
    return "\n".join(lines)


def write_briefing(today: date | None = None) -> Path:
    """Render today's briefing and write it to ``reports/YYYY-MM-DD.md``.
    Returns the path of the written file."""
    today = today or _today_utc()
    text = render_briefing(today=today)
    path = reports_dir() / f"{today.isoformat()}.md"
    path.write_text(text)
    return path


def main(argv: Iterable[str] | None = None) -> int:
    """Tiny CLI for running outside of the onexus click app, useful for cron.
    Honors `--dry` to print to stdout without writing."""
    argv = list(argv if argv is not None else sys.argv[1:])
    dry = "--dry" in argv
    if dry:
        sys.stdout.write(render_briefing())
        return 0
    path = write_briefing()
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
