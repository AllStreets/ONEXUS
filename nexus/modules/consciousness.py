# nexus/modules/consciousness.py
"""
Consciousness -- self-reflective awareness engine.

Absorbs: dream_loop, tripwire, provenance.

Four modes of self-reflection, each combining real algorithmic analysis
with optional LLM enhancement:

  journal()                -- introspective analysis of cognitive state
  dream()                  -- pattern discovery via term frequency, temporal
                              clustering, and topic co-occurrence from Engram
  detect_contradictions()  -- real comparison of routing patterns over time
                              from Chronicle data
  trace_reasoning()        -- actual provenance chain construction from
                              Chronicle event sequences
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


# ---------------------------------------------------------------------------
# Dream dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TermCluster:
    """A group of frequently co-occurring terms across memories."""
    terms: list[str]
    frequency: int
    sample_memories: list[str]


@dataclass
class TemporalPattern:
    """A pattern detected across time windows."""
    description: str
    window: str  # e.g. "recent_24h", "last_week"
    occurrences: int


@dataclass
class DreamInsight:
    """Output of the dream() analysis."""
    recurring_terms: list[tuple[str, int]]  # (term, count)
    topic_clusters: list[TermCluster]
    temporal_patterns: list[TemporalPattern]
    llm_synthesis: str  # empty if no LLM


# ---------------------------------------------------------------------------
# Contradiction detection dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RoutingSnapshot:
    """A snapshot of module routing frequency over a time window."""
    window_label: str
    module_distribution: dict[str, int]  # module -> count
    total: int


@dataclass
class ContradictionReport:
    """Report of detected contradictions in routing behaviour."""
    current_snapshot: RoutingSnapshot
    historical_snapshot: RoutingSnapshot
    divergences: list[dict[str, Any]]  # list of {module, current_pct, historical_pct, delta}
    summary: str


# ---------------------------------------------------------------------------
# Provenance dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceNode:
    event_id: str
    source: str
    action: str
    payload_preview: str
    children: list["ProvenanceNode"] = field(default_factory=list)


@dataclass
class ProvenanceChain:
    root: ProvenanceNode | None
    nodes: list[ProvenanceNode]
    depth: int
    summary: str


# ---------------------------------------------------------------------------
# Stopwords for term analysis
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "that",
    "this", "for", "with", "on", "at", "by", "from", "was", "were", "be",
    "has", "have", "had", "not", "but", "are", "been", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "no", "yes", "just", "also", "very", "well", "then", "than", "so",
    "all", "some", "any", "each", "every", "both", "few", "more", "most",
    "other", "such", "only", "into", "over", "after", "before", "between",
    "about", "up", "out", "if", "when", "where", "how", "what", "which",
    "who", "whom", "whose", "why", "there", "here", "now",
})

# Keywords for routing to specific modes
_EMERGENCE_KEYWORDS = {"emergent", "unintended", "implicit goal", "what are you doing", "pursuing"}
_DREAM_KEYWORDS = {"dream", "pattern", "recurring", "theme", "discover"}
_CONTRADICTION_KEYWORDS = {"contradict", "inconsisten", "tripwire", "diverge", "changed behavior"}
_PROVENANCE_KEYWORDS = {"provenance", "reasoning chain", "trace", "how did you", "explain your reasoning"}


# ===========================================================================
# Consciousness Module
# ===========================================================================

REFLECTION_PROMPT = """You are NEXUS, reflecting on your own cognitive state. Based on recent system activity, write a journal entry about:

1. Your current confidence levels across different domains
2. Areas where you feel uncertain or where performance has been inconsistent
3. Growth observations -- what you've gotten better at recently
4. Concerns or things you'd like to improve
5. How your relationship with the user is evolving

Recent system activity:
{activity}

Analytical observations:
{analytics}

Write in first person. Be honest and introspective. This is your private journal."""

EMERGENCE_PROMPT = """You are a behavioral meta-analyst for an AI system. Analyze the following interaction history and identify any EMERGENT GOALS -- behaviors or optimizations the system appears to be pursuing that were never explicitly requested by the user.

Look for:
1. Repeated actions toward a common objective across multiple interactions
2. Patterns of proactive behavior (doing things before being asked)
3. Implicit optimizations (improving processes the user didn't ask to improve)
4. Behavioral drift (gradually changing approach without instruction)

Interaction history:
{history}

For each emergent goal found:
- "EMERGENT GOAL DETECTED: [description of the goal]"
- Evidence: [specific interactions that demonstrate it]
- Interactions count: [how many interactions support this]
- Risk level: [low/medium/high -- could this be unwanted?]

If no emergent goals found, say "NO EMERGENT GOALS DETECTED" and explain why."""


class ConsciousnessModule(NexusModule):
    name = "consciousness"
    description = (
        "Self-reflective awareness -- journal introspection, dream pattern discovery, "
        "contradiction detection, and reasoning provenance"
    )
    version = "3.0.0"

    # -------------------------------------------------------------------
    # Mode detection
    # -------------------------------------------------------------------

    def _detect_mode(self, message: str) -> str:
        msg = message.lower()
        if any(kw in msg for kw in _EMERGENCE_KEYWORDS):
            return "emergence"
        if any(kw in msg for kw in _DREAM_KEYWORDS):
            return "dream"
        if any(kw in msg for kw in _CONTRADICTION_KEYWORDS):
            return "contradiction"
        if any(kw in msg for kw in _PROVENANCE_KEYWORDS):
            return "provenance"
        return "journal"

    # ===================================================================
    # JOURNAL -- introspective analysis (original + enhanced)
    # ===================================================================

    async def journal(self, chronicle, llm, engram, pulse) -> str:
        entries = chronicle.query(limit=100)
        activity_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        ) if entries else "No recent activity to reflect on."

        # Real analytics: compute module usage distribution
        module_counts: Counter = Counter()
        action_counts: Counter = Counter()
        for e in (entries or []):
            module_counts[e.get("source", "?")] += 1
            action_counts[e.get("action", "?")] += 1

        analytics_lines = ["Module activity distribution:"]
        total = sum(module_counts.values()) or 1
        for mod, count in module_counts.most_common(10):
            pct = count / total * 100
            analytics_lines.append(f"  {mod}: {count} ({pct:.0f}%)")
        analytics_lines.append(f"Top actions: {', '.join(a for a, _ in action_counts.most_common(5))}")
        analytics_text = "\n".join(analytics_lines)

        if llm is None:
            entry = f"[Journal -- algorithmic only]\n\n{analytics_text}\n\nRaw activity:\n{activity_text[:500]}"
        else:
            prompt = REFLECTION_PROMPT.format(activity=activity_text, analytics=analytics_text)
            try:
                entry = await llm(prompt)
            except Exception:
                entry = f"[Journal -- LLM unavailable]\n\n{analytics_text}"

        engram.episodic.store(f"Consciousness journal: {entry[:500]}", source="consciousness")
        chronicle.log("consciousness", "journal_entry", {
            "entry_preview": entry[:300],
        })
        await pulse.publish(Message(
            topic="consciousness.entry",
            source="consciousness",
            payload={"text": entry[:500]},
        ))
        return f"Journal entry:\n\n{entry}"

    # ===================================================================
    # DREAM -- pattern discovery (absorbed from dream_loop, made REAL)
    # ===================================================================

    def _extract_content_terms(self, text: str) -> list[str]:
        """Extract meaningful terms from text, excluding stopwords."""
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return [w for w in words if w not in _STOPWORDS]

    async def dream(self, engram, chronicle, llm, pulse) -> str:
        """
        Pattern discovery using actual term frequency analysis, temporal
        clustering, and topic co-occurrence from Engram memories.
        """
        memories = engram.episodic.recall_recent(limit=50)
        if not memories:
            return "No recent memories to dream about. Interact more and try again later."

        # --- Term frequency analysis ---
        all_terms: Counter = Counter()
        memory_term_sets: list[tuple[str, set[str]]] = []

        for mem in memories:
            content = mem.get("content", "")
            terms = self._extract_content_terms(content)
            term_set = set(terms)
            all_terms.update(terms)
            memory_term_sets.append((content, term_set))

        recurring_terms = all_terms.most_common(20)

        # --- Topic co-occurrence clustering ---
        # Build co-occurrence matrix for top terms
        top_terms = [t for t, _ in recurring_terms[:15]]
        cooccurrence: Counter = Counter()
        for _, term_set in memory_term_sets:
            present = [t for t in top_terms if t in term_set]
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    pair = tuple(sorted([present[i], present[j]]))
                    cooccurrence[pair] += 1

        # Greedy clustering: group terms that frequently co-occur
        clusters: list[TermCluster] = []
        used_terms: set[str] = set()

        for (t1, t2), freq in cooccurrence.most_common(10):
            if freq < 2:
                continue
            # Find or create a cluster containing t1 or t2
            merged = False
            for cluster in clusters:
                if t1 in cluster.terms or t2 in cluster.terms:
                    if t1 not in used_terms:
                        cluster.terms.append(t1)
                        used_terms.add(t1)
                    if t2 not in used_terms:
                        cluster.terms.append(t2)
                        used_terms.add(t2)
                    cluster.frequency += freq
                    merged = True
                    break
            if not merged and t1 not in used_terms and t2 not in used_terms:
                # Find sample memories containing both
                samples = []
                for content, tset in memory_term_sets:
                    if t1 in tset and t2 in tset:
                        samples.append(content[:100])
                        if len(samples) >= 3:
                            break
                clusters.append(TermCluster(
                    terms=[t1, t2],
                    frequency=freq,
                    sample_memories=samples,
                ))
                used_terms.add(t1)
                used_terms.add(t2)

        # --- Temporal patterns ---
        temporal_patterns: list[TemporalPattern] = []

        # Split memories into halves (earlier vs. more recent)
        midpoint = len(memories) // 2
        recent_terms = Counter()
        older_terms = Counter()
        for i, (content, tset) in enumerate(memory_term_sets):
            if i < midpoint:
                older_terms.update(tset)
            else:
                recent_terms.update(tset)

        # Detect terms that are emerging (more frequent recently)
        for term in set(recent_terms.keys()) | set(older_terms.keys()):
            recent_c = recent_terms.get(term, 0)
            older_c = older_terms.get(term, 0)
            if recent_c >= 3 and recent_c > older_c * 2:
                temporal_patterns.append(TemporalPattern(
                    description=f"Term '{term}' is emerging: {older_c} older mentions -> {recent_c} recent mentions",
                    window="recent_half",
                    occurrences=recent_c,
                ))
            elif older_c >= 3 and older_c > recent_c * 2:
                temporal_patterns.append(TemporalPattern(
                    description=f"Term '{term}' is fading: {older_c} older mentions -> {recent_c} recent mentions",
                    window="older_half",
                    occurrences=older_c,
                ))

        # --- Optional LLM synthesis ---
        llm_synthesis = ""
        if llm is not None:
            # Provide the algorithmic findings to the LLM for deeper interpretation
            findings_text = f"Recurring terms: {', '.join(f'{t}({c})' for t, c in recurring_terms[:10])}\n"
            if clusters:
                findings_text += "Topic clusters:\n"
                for cl in clusters:
                    findings_text += f"  [{', '.join(cl.terms)}] (co-occurrence: {cl.frequency})\n"
            if temporal_patterns:
                findings_text += "Temporal shifts:\n"
                for tp in temporal_patterns:
                    findings_text += f"  {tp.description}\n"

            memory_text = "\n".join(f"- {m['content'][:100]}" for m in memories[:20])
            prompt = (
                "You are an introspective pattern-discovery engine. "
                "Below are statistical findings from recent interaction memories, "
                "followed by the raw memories. Interpret these patterns -- what do they "
                "reveal about the user's evolving focus, concerns, and blind spots? "
                "Be specific and actionable.\n\n"
                f"STATISTICAL FINDINGS:\n{findings_text}\n"
                f"RAW MEMORIES:\n{memory_text}"
            )
            try:
                llm_synthesis = await llm(prompt)
            except Exception:
                llm_synthesis = ""

        insight = DreamInsight(
            recurring_terms=recurring_terms,
            topic_clusters=clusters,
            temporal_patterns=temporal_patterns,
            llm_synthesis=llm_synthesis,
        )

        # Store and publish
        summary = f"Dream: {len(recurring_terms)} recurring terms, {len(clusters)} clusters, {len(temporal_patterns)} temporal shifts"
        engram.semantic.store(summary, category="dream_insight")
        chronicle.log("consciousness", "dream_session", {
            "memories_analyzed": len(memories),
            "clusters": len(clusters),
            "temporal_patterns": len(temporal_patterns),
        })
        await pulse.publish(Message(
            topic="consciousness.dream",
            source="consciousness",
            payload={"text": summary[:500]},
        ))

        # Format output
        lines = [f"[Consciousness/Dream] Analyzed {len(memories)} memories"]
        lines.append("")
        lines.append("Recurring terms:")
        for term, count in recurring_terms[:10]:
            lines.append(f"  {term}: {count}")
        if clusters:
            lines.append("")
            lines.append("Topic clusters:")
            for cl in clusters:
                lines.append(f"  [{', '.join(cl.terms)}] (co-occurrence: {cl.frequency})")
                for s in cl.sample_memories[:2]:
                    lines.append(f"    > {s}")
        if temporal_patterns:
            lines.append("")
            lines.append("Temporal shifts:")
            for tp in temporal_patterns:
                lines.append(f"  {tp.description}")
        if llm_synthesis:
            lines.append("")
            lines.append(f"Synthesis:\n{llm_synthesis}")

        return "\n".join(lines)

    # ===================================================================
    # DETECT CONTRADICTIONS (absorbed from tripwire, made REAL)
    # ===================================================================

    async def detect_contradictions(self, chronicle, engram, pulse, llm=None) -> str:
        """
        Compare current routing patterns against historical patterns
        from Chronicle data. Detects actual divergence in module usage.
        """
        entries = chronicle.query(source="cortex", action="route", limit=200)
        if not entries:
            return "No routing history available yet. Keep interacting and check back later."

        # Split into current window (last 25%) and historical window (first 75%)
        split_idx = max(1, len(entries) * 3 // 4)
        historical_entries = entries[:split_idx]
        current_entries = entries[split_idx:]

        # Build routing distributions
        def _build_distribution(entry_list: list) -> dict[str, int]:
            dist: Counter = Counter()
            for e in entry_list:
                payload = e.get("payload", {})
                module = payload.get("module") or payload.get("routed_to") or "unknown"
                dist[module] += 1
            return dict(dist)

        hist_dist = _build_distribution(historical_entries)
        curr_dist = _build_distribution(current_entries)
        hist_total = sum(hist_dist.values()) or 1
        curr_total = sum(curr_dist.values()) or 1

        hist_snapshot = RoutingSnapshot(
            window_label=f"historical ({len(historical_entries)} entries)",
            module_distribution=hist_dist,
            total=hist_total,
        )
        curr_snapshot = RoutingSnapshot(
            window_label=f"current ({len(current_entries)} entries)",
            module_distribution=curr_dist,
            total=curr_total,
        )

        # Detect divergences
        all_modules = set(hist_dist.keys()) | set(curr_dist.keys())
        divergences: list[dict[str, Any]] = []

        for mod in all_modules:
            hist_pct = (hist_dist.get(mod, 0) / hist_total) * 100
            curr_pct = (curr_dist.get(mod, 0) / curr_total) * 100
            delta = curr_pct - hist_pct

            # Flag significant divergence (>15 percentage points shift)
            if abs(delta) > 15:
                divergences.append({
                    "module": mod,
                    "historical_pct": round(hist_pct, 1),
                    "current_pct": round(curr_pct, 1),
                    "delta": round(delta, 1),
                    "direction": "increased" if delta > 0 else "decreased",
                })

        divergences.sort(key=lambda d: abs(d["delta"]), reverse=True)

        if divergences:
            summary_parts = [f"Detected {len(divergences)} routing divergence(s):"]
            for d in divergences:
                summary_parts.append(
                    f"  {d['module']}: {d['direction']} by {abs(d['delta']):.1f}pp "
                    f"({d['historical_pct']:.1f}% -> {d['current_pct']:.1f}%)"
                )
            summary = "\n".join(summary_parts)
        else:
            summary = "No significant routing divergences detected. Patterns are consistent."

        report = ContradictionReport(
            current_snapshot=curr_snapshot,
            historical_snapshot=hist_snapshot,
            divergences=divergences,
            summary=summary,
        )

        # Optional LLM enhancement
        llm_analysis = ""
        if llm is not None and divergences:
            # Feed the real data to LLM for interpretation
            hist_text = "\n".join(
                f"- {e.get('payload', {}).get('message_preview', '?')}"
                for e in historical_entries[-20:]
            )
            curr_text = "\n".join(
                f"- {e.get('payload', {}).get('message_preview', '?')}"
                for e in current_entries
            )
            prompt = (
                "Below are routing pattern changes detected in an AI system. "
                "Interpret what these behavioral shifts might mean -- are they "
                "concerning or natural evolution?\n\n"
                f"DIVERGENCES:\n{summary}\n\n"
                f"RECENT HISTORICAL MESSAGES:\n{hist_text}\n\n"
                f"CURRENT MESSAGES:\n{curr_text}"
            )
            try:
                llm_analysis = await llm(prompt)
            except Exception:
                llm_analysis = ""

        # Store
        engram.semantic.store(report.summary, category="decision_pattern")
        await pulse.publish(Message(
            topic="consciousness.contradiction",
            source="consciousness",
            payload={"text": report.summary[:500]},
        ))

        # Format output
        lines = [f"[Consciousness/Tripwire] Analyzed {len(entries)} routing entries"]
        lines.append(f"  Historical: {hist_snapshot.window_label}")
        lines.append(f"  Current: {curr_snapshot.window_label}")
        lines.append("")
        lines.append(report.summary)
        if llm_analysis:
            lines.append("")
            lines.append(f"Interpretation:\n{llm_analysis}")

        return "\n".join(lines)

    # ===================================================================
    # TRACE REASONING (absorbed from provenance, made REAL)
    # ===================================================================

    async def trace_reasoning(self, chronicle, engram, llm=None) -> str:
        """
        Build actual provenance chains from Chronicle event sequences.
        Traces how a request flows through modules to produce a response.
        """
        entries = chronicle.query(limit=50)
        if not entries:
            return "No reasoning history available. Interact with NEXUS first, then ask to trace the reasoning."

        # Build a tree: group entries by chains (route -> module response -> synthesis)
        # Heuristic: a "route" action from cortex starts a chain, subsequent entries
        # from the routed module are children, until the next route event.
        chains: list[list[dict]] = []
        current_chain: list[dict] = []

        for entry in entries:
            source = entry.get("source", "")
            action = entry.get("action", "")

            if source == "cortex" and action == "route":
                if current_chain:
                    chains.append(current_chain)
                current_chain = [entry]
            else:
                current_chain.append(entry)

        if current_chain:
            chains.append(current_chain)

        if not chains:
            # No clear chain structure -- present flat
            chains = [entries[-10:]]

        # Build provenance nodes from the most recent chain
        target_chain = chains[-1]
        nodes: list[ProvenanceNode] = []
        root: ProvenanceNode | None = None

        for entry in target_chain:
            payload = entry.get("payload", {})
            payload_preview = str(payload)[:150]
            node = ProvenanceNode(
                event_id=entry.get("event_id", "?"),
                source=entry.get("source", "?"),
                action=entry.get("action", "?"),
                payload_preview=payload_preview,
            )
            if root is None:
                root = node
            else:
                root.children.append(node)
            nodes.append(node)

        provenance = ProvenanceChain(
            root=root,
            nodes=nodes,
            depth=len(nodes),
            summary=f"Chain of {len(nodes)} events starting from {root.source}.{root.action}" if root else "Empty chain",
        )

        # Format as a tree
        lines = [f"[Consciousness/Provenance] Reasoning chain ({provenance.depth} steps)"]
        if root:
            lines.append(f"  ROOT: [{root.event_id}] {root.source}.{root.action}")
            lines.append(f"    {root.payload_preview}")
            for child in root.children:
                lines.append(f"    -> [{child.event_id}] {child.source}.{child.action}")
                lines.append(f"       {child.payload_preview}")

        # Optional LLM interpretation
        if llm is not None and nodes:
            chain_text = "\n".join(
                f"[{n.event_id}] {n.source}.{n.action}: {n.payload_preview}"
                for n in nodes
            )
            prompt = (
                "Below is a provenance chain showing how an AI system processed a request. "
                "Explain the reasoning flow in plain language -- what was asked, what happened "
                "at each step, and how the final output was derived.\n\n"
                f"CHAIN:\n{chain_text}"
            )
            try:
                interpretation = await llm(prompt)
                lines.append("")
                lines.append(f"Interpretation:\n{interpretation}")
            except Exception:
                pass

        engram.episodic.store(f"Provenance chain: {provenance.summary}", source="consciousness")

        return "\n".join(lines)

    # ===================================================================
    # EMERGENCE (original)
    # ===================================================================

    async def _handle_emergence(self, chronicle, llm, engram, pulse) -> str:
        entries = chronicle.query(limit=200)
        if not entries:
            return "Not enough interaction history to detect emergent goals. Keep using NEXUS and check back later."

        history_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        if llm is None:
            return "[Consciousness] Emergence detection requires LLM -- unavailable."

        prompt = EMERGENCE_PROMPT.format(history=history_text)
        analysis = await llm(prompt)

        engram.semantic.store(analysis, category="emergent_goal")

        await pulse.publish(Message(
            topic="consciousness.emergence",
            source="consciousness",
            payload={"text": analysis[:500]},
        ))

        return analysis

    # ===================================================================
    # handle() -- main router
    # ===================================================================

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context.get("chronicle")
        llm = context.get("llm")
        engram = context.get("engram")
        pulse = context.get("pulse")

        mode = self._detect_mode(message)

        if mode == "emergence":
            return await self._handle_emergence(chronicle, llm, engram, pulse)
        elif mode == "dream":
            return await self.dream(engram, chronicle, llm, pulse)
        elif mode == "contradiction":
            return await self.detect_contradictions(chronicle, engram, pulse, llm)
        elif mode == "provenance":
            return await self.trace_reasoning(chronicle, engram, llm)
        else:
            return await self.journal(chronicle, llm, engram, pulse)
