"""
Kindle -- content expansion and polishing agent.
Transforms rough bullet points or outlines into polished long-form
content (blog posts, documentation, reports) in a specified tone.

Inspired by:
  - WriteFreely (AGPL 3.0) — open source publishing platform
  - markdownlint patterns — structured content formatting
  - Hemingway Editor principles — clear, readable writing
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ContentPiece:
    title: str
    sections: list[str]
    word_count: int
    tone: str
    format: str  # "blog", "docs", "report", "email"


# Tone templates
_TONES: dict[str, str] = {
    "professional": "Write in a professional, clear business tone. Be direct and avoid jargon.",
    "technical": "Write in a precise technical tone. Include relevant details and accurate terminology.",
    "casual": "Write in a friendly, conversational tone. Use simple language and short sentences.",
    "academic": "Write in a formal academic tone. Cite concepts precisely and maintain objectivity.",
    "marketing": "Write in a persuasive, engaging marketing tone. Focus on benefits and calls to action.",
}


class KindleModule(AgentModule):
    name = "kindle"
    description = "Content expander -- transforms bullet points into polished blog posts, docs, reports, and emails"
    version = "0.1.0"

    watch_events: list[str] = ["content.draft_ready", "scribe.finding"]
    coordination_targets: list[str] = ["thesis", "scribe"]

    def __init__(self):
        self._pieces: list[ContentPiece] = []

    @staticmethod
    def detect_tone(message: str) -> str:
        """Detect desired tone from the message."""
        msg_lower = message.lower()
        for tone in _TONES:
            if tone in msg_lower:
                return tone
        if any(w in msg_lower for w in ("blog", "post", "article")):
            return "casual"
        if any(w in msg_lower for w in ("report", "analysis", "memo")):
            return "professional"
        if any(w in msg_lower for w in ("docs", "documentation", "readme")):
            return "technical"
        return "professional"

    @staticmethod
    def detect_format(message: str) -> str:
        """Detect desired content format."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("blog", "post", "article")):
            return "blog"
        if any(w in msg_lower for w in ("doc", "documentation", "readme", "guide")):
            return "docs"
        if any(w in msg_lower for w in ("email", "message", "letter")):
            return "email"
        return "report"

    @staticmethod
    def extract_bullets(text: str) -> list[str]:
        """Extract bullet points from text."""
        bullets: list[str] = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped and re.match(r'^[-*+]|\d+[.)]\s', stripped):
                # Remove bullet markers
                cleaned = re.sub(r'^[-*+]\s*|\d+[.)]\s*', '', stripped)
                if cleaned:
                    bullets.append(cleaned)
        return bullets

    @staticmethod
    def extract_title(text: str) -> str:
        """Extract or generate a title."""
        lines = text.strip().split('\n')
        for line in lines[:3]:
            stripped = line.strip()
            if stripped.startswith('#'):
                return stripped.lstrip('#').strip()
            if 5 < len(stripped) < 100 and not re.match(r'^[-*+]|\d+[.)]', stripped):
                return stripped
        return "Untitled"

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        tone = self.detect_tone(message)
        content_format = self.detect_format(message)
        bullets = self.extract_bullets(message)
        title = self.extract_title(message)

        if not llm:
            # Without LLM, do basic expansion
            if not bullets:
                return "[Kindle] Provide bullet points or an outline to expand. Use - or * for bullets."

            sections: list[str] = []
            for bullet in bullets:
                sections.append(f"## {bullet}\n\n[Content about {bullet} would go here.]\n")

            word_count = sum(len(s.split()) for s in sections)
            piece = ContentPiece(title=title, sections=sections,
                                  word_count=word_count, tone=tone, format=content_format)
            self._pieces.append(piece)

            result = f"[Kindle] Content Outline ({content_format}, {tone} tone)\n\n"
            result += f"# {title}\n\n" + "\n".join(sections)
            result += f"\n\nLLM required for full content generation."
            return result

        # Build LLM prompt
        bullet_text = "\n".join(f"- {b}" for b in bullets) if bullets else message

        format_instructions = {
            "blog": "Write a blog post with an engaging introduction, clear sections with headers, and a conclusion with a call to action.",
            "docs": "Write technical documentation with clear sections, code examples where relevant, and a getting-started section.",
            "report": "Write a professional report with an executive summary, findings sections, and recommendations.",
            "email": "Write a professional email with a clear subject line suggestion, greeting, body, and sign-off.",
        }

        prompt = (
            f"Expand the following bullet points into a polished {content_format}.\n\n"
            f"Tone: {_TONES[tone]}\n"
            f"Format: {format_instructions.get(content_format, format_instructions['report'])}\n"
            f"Target: 500-1000 words\n\n"
            f"Input:\n{bullet_text[:3000]}\n\n"
            "Write the complete content now."
        )

        try:
            expanded = await llm.complete(prompt)
        except Exception:
            return "[Kindle] LLM call failed. Check model configuration."

        word_count = len(expanded.split())
        sections = expanded.split('\n\n')

        piece = ContentPiece(title=title, sections=sections,
                              word_count=word_count, tone=tone, format=content_format)
        self._pieces.append(piece)

        if engram:
            try:
                engram.episodic.store(
                    f"Content generated: {title} ({content_format}, {tone}, {word_count} words)",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Kindle] Generated {content_format.title()} ({word_count} words, {tone} tone)"]
        lines.append(f"\n{expanded[:3000]}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # AgentModule tier methods
    # ------------------------------------------------------------------

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest tone or format improvements when draft content is detected."""
        bullets = self.extract_bullets(message)
        detected_tone = self.detect_tone(message)
        detected_format = self.detect_format(message)

        if bullets:
            return (
                f"Detected {len(bullets)} bullet point(s). Kindle can expand these into a "
                f"polished {detected_format} with a {detected_tone} tone. "
                "Specify a different tone (casual, technical, academic, marketing) or format "
                "(blog, docs, report, email) to override."
            )

        # Plain prose -- offer a polish pass
        word_count = len(message.split())
        if word_count > 50:
            return (
                f"This draft is {word_count} words with a {detected_tone} tone. "
                "Kindle can restructure and polish it into a publication-ready {detected_format}."
            )

        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for draft content or scribe findings that need expansion."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "content.draft_ready":
            title = payload.get("title", "untitled")
            fmt = payload.get("format", "document")
            return f"Draft ready: '{title}' ({fmt}). Kindle can expand and polish this content."

        if topic == "scribe.finding":
            finding = payload.get("finding", "")
            if finding:
                return (
                    "Scribe published new meeting findings. "
                    "Kindle can expand the summary into a full report or email."
                )

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route academic content to thesis; meeting-derived content back to scribe."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        parts: list[str] = []
        result_lower = analysis_result.lower()

        # Academic content -- hand off to thesis for citation and claim extraction
        if any(kw in result_lower for kw in ("research", "paper", "study", "abstract",
                                              "methodology", "findings", "hypothesis")):
            try:
                thesis_result = await cortex.route(
                    "thesis",
                    f"Analyze the academic content in this expanded piece:\n{analysis_result}",
                    context,
                )
                if thesis_result:
                    parts.append(f"[thesis] {thesis_result}")
            except Exception:
                pass

        # Meeting-derived content -- offer condensed version back to scribe
        if any(kw in result_lower for kw in ("meeting", "action item", "decision", "attendee")):
            try:
                scribe_result = await cortex.route(
                    "scribe",
                    f"Extract action items from this polished meeting report:\n{analysis_result}",
                    context,
                )
                if scribe_result:
                    parts.append(f"[scribe] {scribe_result}")
            except Exception:
                pass

        return "\n".join(parts)
