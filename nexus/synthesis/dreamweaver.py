# nexus/synthesis/dreamweaver.py
"""Dreamweaver -- overnight synthesis (N2.2). Deterministic, kill-switched."""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.config import NexusConfig
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram

_STOPWORDS = {"user", "nexus", "the", "a", "an", "for", "and", "or", "to", "of",
              "in", "on", "is", "it", "that", "this", "with", "review", "about",
              "what", "how"}
_TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{2,}")
_MIN_FREQ = 3


def dreamweaver_enabled(config: NexusConfig) -> bool:
    if os.environ.get("NEXUS_DREAMWEAVER", "1").lower() in ("0", "false", "no"):
        return False
    return not (Path(config.data_dir) / "dreamweaver.kill").exists()


class Dreamweaver:
    def __init__(self, config: NexusConfig, engram: Engram, chronicle: Chronicle) -> None:
        self._config = config
        self._engram = engram
        self._chronicle = chronicle

    def _recurring_topics(self, limit: int = 500):
        rows = self._engram.episodic.recall_recent(limit=limit)
        counts: Counter[str] = Counter()
        for r in rows:
            for tok in _TOKEN_RE.findall(r["content"].lower()):
                if tok in _STOPWORDS:
                    continue
                counts[tok] += 1
        return [(tok, n) for tok, n in counts.most_common(20) if n >= _MIN_FREQ]

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        if not dreamweaver_enabled(self._config):
            self._chronicle.log("dreamweaver", "skipped", {"reason": "kill_switch"})
            return {"skipped": "kill_switch", "distilled_facts": 0}
        moment = now or datetime.now(timezone.utc)
        topics = self._recurring_topics()
        source_ref = f"dreamweaver:{moment.date().isoformat()}"
        distilled = 0
        for tok, freq in topics:
            self._engram.atlas.observe("day", "observed", tok,
                                       confidence=min(0.6 + 0.05 * freq, 0.95),
                                       fact_class="volatile", source_ref=source_ref, now=moment)
            distilled += 1
        if topics:
            summary = "Recurring today: " + ", ".join(f"{t} (x{n})" for t, n in topics[:8])
            self._engram.semantic.store(summary, category="dreamweaver_brief")
        headline = (f"{distilled} recurring topic(s) distilled" if distilled
                    else "Quiet day - nothing recurred above threshold")
        brief = {"headline": headline, "date": moment.date().isoformat(),
                 "topics": [{"topic": t, "count": n} for t, n in topics],
                 "distilled_facts": distilled, "generated_at": moment.isoformat(),
                 "skipped": None}
        self._chronicle.log("dreamweaver", "morning_brief", brief)
        return brief

    def latest_brief(self) -> dict[str, Any] | None:
        rows = self._chronicle.query(source="dreamweaver", action="morning_brief", limit=1)
        return rows[0]["payload"] if rows else None
