"""
Thesis -- academic paper analyzer and literature review assistant.
Reads paper abstracts/sections and generates structured notes with
key claims, methodology, limitations, and cross-paper comparisons.

Inspired by:
  - shubhamagarwal92/LitLLM (Apache 2.0) — RAG-based literature review toolkit
  - PouriaRouzrokh/LatteReview (MIT) — AI-powered systematic literature review
  - ParthJain18/LLM-Literature-Review-Assistant (MIT) — LLM screening for SLR
  - semanticClimate/assisted-literature-review (Apache 2.0) — open science ALR
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class PaperNote:
    title: str
    authors: str
    key_claims: list[str]
    methodology: str
    limitations: list[str]
    tags: list[str]


class ThesisModule(AgentModule):
    name = "thesis"
    description = "Academic paper analyzer — extracts claims, methodology, limitations, and generates literature review notes"
    version = "0.1.0"

    watch_events: list[str] = ["paper.uploaded", "research.query"]
    coordination_targets: list[str] = ["kindle", "compass"]

    def __init__(self):
        self._papers: list[PaperNote] = []

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract title from first line or title-like pattern."""
        lines = text.strip().split('\n')
        for line in lines[:5]:
            cleaned = line.strip()
            if 10 < len(cleaned) < 200 and not cleaned.startswith(('Abstract', 'Keywords', 'http')):
                return cleaned
        return "Untitled"

    @staticmethod
    def _extract_authors(text: str) -> str:
        """Extract author names from text."""
        # Common patterns: "by Author1, Author2" or "Author1 et al."
        patterns = [
            r'(?:by|authors?)[:\s]+([A-Z][^.\n]{5,100})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*(?:\s+et\s+al\.?))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:500])
            if match:
                return match.group(1).strip()
        return "Unknown"

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        """Extract keyword tags from text."""
        # Look for keywords section
        kw_match = re.search(r'(?:keywords?|index terms?)[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if kw_match:
            raw = kw_match.group(1)
            return [t.strip().lower() for t in re.split(r'[,;]', raw) if t.strip()][:10]

        # Fallback: extract frequent multi-word technical terms
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if w not in {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'their',
                         'which', 'would', 'could', 'should', 'about', 'these', 'those',
                         'them', 'they', 'than', 'more', 'also', 'some', 'such', 'into',
                         'other', 'based', 'using', 'each', 'method', 'result', 'paper',
                         'figure', 'table', 'approach', 'proposed', 'model', 'used'}:
                freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:8]]

    def add_paper(self, note: PaperNote) -> None:
        self._papers.append(note)

    def list_papers(self) -> list[PaperNote]:
        return list(self._papers)

    def find_gaps(self) -> list[str]:
        """Identify potential research gaps from collected papers."""
        if len(self._papers) < 2:
            return []

        gaps: list[str] = []

        # Collect all mentioned limitations
        all_limitations: list[str] = []
        for p in self._papers:
            all_limitations.extend(p.limitations)

        # Find recurring limitation themes
        limitation_words: dict[str, int] = {}
        for lim in all_limitations:
            for word in re.findall(r'\b[a-z]{5,}\b', lim.lower()):
                limitation_words[word] = limitation_words.get(word, 0) + 1

        recurring = [w for w, c in limitation_words.items() if c >= 2]
        if recurring:
            gaps.append(f"Recurring limitations across papers: {', '.join(recurring[:5])}")

        # Find methodological diversity
        methods = [p.methodology for p in self._papers if p.methodology]
        unique_methods = len(set(m.lower()[:30] for m in methods))
        if unique_methods < len(methods) * 0.5:
            gaps.append("Limited methodological diversity — most papers use similar approaches")

        return gaps

    def compare_papers(self) -> str:
        """Generate a comparison table of collected papers."""
        if not self._papers:
            return "No papers to compare."

        lines = ["Paper Comparison:"]
        for i, p in enumerate(self._papers, 1):
            lines.append(f"\n  {i}. {p.title}")
            lines.append(f"     Authors: {p.authors}")
            lines.append(f"     Method: {p.methodology}")
            lines.append(f"     Claims: {'; '.join(p.key_claims[:3])}")
            if p.limitations:
                lines.append(f"     Limits: {'; '.join(p.limitations[:2])}")
            lines.append(f"     Tags: {', '.join(p.tags[:5])}")

        return "\n".join(lines)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # If asking for comparison/review
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("compare", "review", "gap", "synthesis")):
            if self._papers:
                comparison = self.compare_papers()
                gaps = self.find_gaps()
                result = f"[Thesis] Literature Review\n\n{comparison}"
                if gaps:
                    result += "\n\n  Research Gaps Identified:"
                    for g in gaps:
                        result += f"\n    - {g}"
                return result

        # Analyze new paper
        title = self._extract_title(message)
        authors = self._extract_authors(message)
        tags = self._extract_tags(message)

        # Use LLM for deep analysis
        key_claims: list[str] = []
        methodology = ""
        limitations: list[str] = []

        if llm:
            prompt = (
                "Analyze this academic paper excerpt and extract:\n"
                "1. KEY CLAIMS: The main findings or arguments (bullet list)\n"
                "2. METHODOLOGY: Research method used (one sentence)\n"
                "3. LIMITATIONS: Stated or implied limitations (bullet list)\n"
                "4. CONTRIBUTION: What this adds to the field (one sentence)\n\n"
                f"Paper:\n{message[:3000]}\n\n"
                "Use the headers KEY CLAIMS, METHODOLOGY, LIMITATIONS, CONTRIBUTION."
            )
            try:
                analysis = await llm.complete(prompt)

                # Parse structured response
                claims_match = re.search(
                    r'KEY CLAIMS[:\s]*\n(.*?)(?=METHODOLOGY|$)',
                    analysis, re.DOTALL | re.IGNORECASE
                )
                if claims_match:
                    key_claims = [
                        l.strip().lstrip('- *')
                        for l in claims_match.group(1).strip().split('\n')
                        if l.strip() and len(l.strip()) > 10
                    ]

                meth_match = re.search(
                    r'METHODOLOGY[:\s]*\n(.*?)(?=LIMITATIONS|$)',
                    analysis, re.DOTALL | re.IGNORECASE
                )
                if meth_match:
                    methodology = meth_match.group(1).strip().split('\n')[0].strip().lstrip('- *')

                lim_match = re.search(
                    r'LIMITATIONS[:\s]*\n(.*?)(?=CONTRIBUTION|$)',
                    analysis, re.DOTALL | re.IGNORECASE
                )
                if lim_match:
                    limitations = [
                        l.strip().lstrip('- *')
                        for l in lim_match.group(1).strip().split('\n')
                        if l.strip() and len(l.strip()) > 10
                    ]
            except Exception:
                pass

        # Fallback if no LLM
        if not key_claims:
            key_claims = ["Unable to extract claims without LLM analysis"]
        if not methodology:
            methodology = "Not determined"

        note = PaperNote(
            title=title,
            authors=authors,
            key_claims=key_claims,
            methodology=methodology,
            limitations=limitations,
            tags=tags,
        )
        self.add_paper(note)

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Paper analyzed: {title} by {authors}. "
                    f"Claims: {'; '.join(key_claims[:2])}",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Thesis] Paper Analysis"]
        lines.append(f"  Title: {title}")
        lines.append(f"  Authors: {authors}")
        lines.append(f"  Tags: {', '.join(tags[:6])}")

        lines.append(f"\n  Key Claims ({len(key_claims)}):")
        for i, c in enumerate(key_claims, 1):
            lines.append(f"    {i}. {c}")

        lines.append(f"\n  Methodology: {methodology}")

        if limitations:
            lines.append(f"\n  Limitations ({len(limitations)}):")
            for i, l in enumerate(limitations, 1):
                lines.append(f"    {i}. {l}")

        lines.append(f"\n  Papers in collection: {len(self._papers)}")
        if len(self._papers) > 1:
            lines.append("  Run 'compare papers' or 'literature review' for cross-paper analysis.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # AgentModule tier methods
    # ------------------------------------------------------------------

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest a literature review when enough papers have been collected."""
        paper_count = len(self._papers)
        if paper_count >= 3:
            gaps = self.find_gaps()
            gap_hint = f" {len(gaps)} potential research gap(s) detected." if gaps else ""
            return (
                f"{paper_count} papers in the collection.{gap_hint} "
                "Run 'literature review' or 'compare papers' for a cross-paper synthesis."
            )
        if paper_count == 2:
            return (
                "2 papers collected. Add one more and Thesis can generate a comparative "
                "literature review with gap analysis."
            )
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for new papers being uploaded or research queries arriving."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "paper.uploaded":
            title = payload.get("title", "untitled")
            source = payload.get("source", "unknown")
            return (
                f"New paper uploaded: '{title}' from {source}. "
                "Thesis can analyze claims, methodology, and limitations."
            )

        if topic == "research.query":
            query = payload.get("query", "")
            if query:
                return (
                    f"Research query received: '{query[:80]}'. "
                    "Thesis can scan the paper collection for relevant findings."
                )

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route findings to kindle for writeup or compass for learning paths."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        parts: list[str] = []

        # Send to kindle for a polished literature review write-up
        try:
            kindle_result = await cortex.route(
                "kindle",
                f"Expand these academic findings into a polished literature review section:\n{analysis_result}",
                context,
            )
            if kindle_result:
                parts.append(f"[kindle] {kindle_result}")
        except Exception:
            pass

        # If gaps were identified, ask compass to build a learning path
        if "gap" in analysis_result.lower() or "limitation" in analysis_result.lower():
            try:
                compass_result = await cortex.route(
                    "compass",
                    f"Build a learning path to address these research gaps:\n{analysis_result}",
                    context,
                )
                if compass_result:
                    parts.append(f"[compass] {compass_result}")
            except Exception:
                pass

        return "\n".join(parts)
