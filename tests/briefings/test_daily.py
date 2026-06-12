"""Smoke tests for the daily-briefing generator.

These tests build a throwaway SQLite database matching the kernel schema,
generate a briefing from it, and assert the output has the expected
sections in the expected order. They don't require the API server to be
running or a real ONEXUS-Agents catalog on disk."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from nexus.briefings.daily import (
    Counts,
    render_briefing,
    write_briefing,
)
import nexus.briefings.daily as daily_mod


@pytest.fixture
def tmp_kernel_db(tmp_path: Path) -> Path:
    """Create a kernel-shaped SQLite DB seeded with a small fixture of
    chronicle + trust events on today's UTC date."""
    db = tmp_path / "nexus.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE chronicle (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE aegis_trust_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            old_score REAL NOT NULL,
            new_score REAL NOT NULL,
            delta REAL NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        CREATE TABLE aegis_grants (
            agent_slug TEXT NOT NULL,
            capability TEXT NOT NULL,
            workspace_id TEXT,
            granted_at TEXT NOT NULL,
            PRIMARY KEY (agent_slug, capability, workspace_id)
        );
        """
    )
    ts = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT INTO chronicle (event_id, timestamp, source, action, payload) VALUES (?, ?, ?, ?, ?)",
        [
            ("e1", ts, "api", "server_start", "{}"),
            ("e2", ts, "cortex", "route", "{}"),
            ("e3", ts, "cortex", "route", "{}"),
            ("e4", ts, "aegis", "permission_allowed", "{}"),
            ("e5", ts, "aegis", "permission_denied", "{}"),
        ],
    )
    conn.execute(
        "INSERT INTO aegis_trust_history (module_name, old_score, new_score, delta, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        ("council", 0.30, 0.33, 0.03, "feedback_positive", ts),
    )
    conn.commit()
    conn.close()
    # Workspaces subdir so the count is realistic
    (db.parent / "workspaces" / "build").mkdir(parents=True)
    (db.parent / "workspaces" / "personal-research").mkdir()
    return db


def test_render_briefing_emits_required_sections(tmp_kernel_db: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(daily_mod, "reports_dir", lambda: tmp_path / "reports")
    monkeypatch.setattr(daily_mod, "catalog_root", lambda: None)
    text = render_briefing(db=tmp_kernel_db, today=date.today())

    # Title is the first line and ends with today's ISO date
    first = text.splitlines()[0]
    assert first.startswith("# Kernel briefing — ")

    # The five canonical sections appear, in order
    sections = ["## Totals", "## Activity today (UTC)",
                "## Trust changes today", "## Permission events today",
                "## Pipeline health"]
    positions = [text.find(s) for s in sections]
    assert all(p != -1 for p in positions), f"missing section in: {positions}"
    assert positions == sorted(positions), "sections out of expected order"

    # Footer present
    assert "---" in text
    assert re.search(r"\*generated \d{4}-\d{2}-\d{2}T", text)


def test_render_briefing_counts_seeded_data(tmp_kernel_db: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(daily_mod, "reports_dir", lambda: tmp_path / "reports")
    monkeypatch.setattr(daily_mod, "catalog_root", lambda: None)
    # The briefing windows events by UTC day and the fixture timestamps with
    # datetime.now(timezone.utc) — so pass the UTC date, not date.today(),
    # which diverges from it every evening in US timezones.
    text = render_briefing(db=tmp_kernel_db, today=datetime.now(timezone.utc).date())

    # Two workspaces seeded
    assert "Workspaces: **2**" in text

    # Two cortex route events were inserted
    assert re.search(r"`cortex` \| `route` \| 2", text)

    # Trust adjustment shows up
    assert "council" in text
    assert "+0.03" in text

    # One allowed + one denied permission
    assert "Allowed: **1**" in text
    assert "Denied: **1**" in text


def test_write_briefing_creates_dated_file(tmp_kernel_db: Path, tmp_path: Path, monkeypatch):
    target = tmp_path / "reports"
    target.mkdir()
    monkeypatch.setattr(daily_mod, "reports_dir", lambda: target)
    monkeypatch.setattr(daily_mod, "kernel_db_path", lambda: tmp_kernel_db)
    monkeypatch.setattr(daily_mod, "catalog_root", lambda: None)

    path = write_briefing(today=date(2026, 6, 9))
    assert path.name == "2026-06-09.md"
    assert path.read_text().startswith("# Kernel briefing — 2026-06-09")


def test_render_briefing_handles_missing_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(daily_mod, "reports_dir", lambda: tmp_path / "reports")
    monkeypatch.setattr(daily_mod, "catalog_root", lambda: None)
    text = render_briefing(db=tmp_path / "does-not-exist.db", today=date.today())

    # Still emits the sections, with zeros
    assert "## Totals" in text
    assert "Workspaces: **0**" in text
    assert "No chronicle events recorded today." in text
    assert "No trust adjustments today." in text


def test_render_briefing_computes_deltas_against_yesterday(tmp_kernel_db: Path, tmp_path: Path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    from datetime import timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)
    (reports / f"{yesterday.isoformat()}.md").write_text(
        "# Kernel briefing — old\n\n## Totals\n- Workspaces: **1**\n- Agents in catalog: **6,000**\n"
    )
    monkeypatch.setattr(daily_mod, "reports_dir", lambda: reports)
    monkeypatch.setattr(daily_mod, "catalog_root", lambda: None)

    text = render_briefing(db=tmp_kernel_db, today=today)
    # 2 today − 1 yesterday → (+1)
    assert "Workspaces: **2** (+1)" in text
    # Catalog 0 (no catalog) − 6000 yesterday → (-6,000)
    assert "Agents in catalog: **0** (-6,000)" in text
