"""
Scribe -- meeting transcript summarizer and action item extractor.
Converts raw meeting transcripts or notes into structured summaries with
action items, decisions, and key discussion points.

Inspired by:
  - riscv-admin/local-llm-meeting-summary (MIT) — local LLM summarization
  - itsmetamike/vtt-summarizer (MIT) — structured extraction from transcripts
  - GetStream/meeting-summary-ollama-gemma (Apache 2.0) — Ollama-based summaries
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class MeetingRecord:
    summary: str
    action_items: list[str]
    decisions: list[str]
    key_points: list[str]
    participants: list[str]


class ScribeModule(AgentModule):
    name = "scribe"
    description = "Meeting transcript summarizer — extracts action items, decisions, and key discussion points"
    version = "0.1.0"

    watch_events: list[str] = ["meeting.started", "transcript.uploaded"]
    coordination_targets: list[str] = ["kindle", "mnemonic"]

    def __init__(self):
        self._records: list[MeetingRecord] = []

    @staticmethod
    def _extract_participants(text: str) -> list[str]:
        """Extract likely speaker names from transcript-style text."""
        # Match "Name:" or "Name -" patterns at line start
        speakers = re.findall(r'^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*[:\-]', text, re.MULTILINE)
        return sorted(set(speakers))

    @staticmethod
    def _extract_action_items(text: str) -> list[str]:
        """Extract action items from text using common patterns."""
        patterns = [
            r'(?:action item|todo|to-do|task)[:\s]+(.+?)(?:\n|$)',
            r'(?:will|should|needs? to|has to|must)\s+(.+?)(?:\.|;|\n|$)',
            r'\[\s*\]\s+(.+?)(?:\n|$)',  # Checkbox items
        ]
        items = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            items.extend(m.strip() for m in matches if len(m.strip()) > 10)
        return list(dict.fromkeys(items))[:20]  # Deduplicate, cap at 20

    @staticmethod
    def _extract_decisions(text: str) -> list[str]:
        """Extract decisions from text using common patterns."""
        patterns = [
            r'(?:decided|agreed|decision)[:\s]+(.+?)(?:\.|;|\n|$)',
            r'(?:we will|the plan is|going forward)[,\s]+(.+?)(?:\.|;|\n|$)',
        ]
        decisions = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            decisions.extend(m.strip() for m in matches if len(m.strip()) > 10)
        return list(dict.fromkeys(decisions))[:10]

    def store_record(self, record: MeetingRecord) -> None:
        self._records.append(record)

    def list_records(self) -> list[MeetingRecord]:
        return list(self._records)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")
        pulse = context.get("pulse")

        # Pre-extract structured data without LLM
        participants = self._extract_participants(message)
        action_items = self._extract_action_items(message)
        decisions = self._extract_decisions(message)

        # Use LLM for summary and key points
        prompt = (
            "You are a meeting summarizer. Analyze the following transcript and provide:\n"
            "1. A concise 2-3 sentence summary\n"
            "2. Key discussion points (bullet list)\n"
            "3. Any additional action items not already listed\n"
            "4. Any additional decisions not already listed\n\n"
            f"Transcript:\n{message[:3000]}\n\n"
            "Respond in a structured format with headers: SUMMARY, KEY POINTS, "
            "ADDITIONAL ACTIONS, ADDITIONAL DECISIONS."
        )

        try:
            llm_response = await llm.complete(prompt) if llm else ""
        except Exception:
            llm_response = ""

        # Parse LLM response for key points
        key_points = []
        if llm_response:
            kp_match = re.search(
                r'KEY POINTS[:\s]*\n(.*?)(?=ADDITIONAL|$)',
                llm_response, re.DOTALL | re.IGNORECASE
            )
            if kp_match:
                key_points = [
                    line.strip().lstrip('- *')
                    for line in kp_match.group(1).strip().split('\n')
                    if line.strip() and len(line.strip()) > 5
                ]

            # Extract additional actions from LLM
            aa_match = re.search(
                r'ADDITIONAL ACTIONS[:\s]*\n(.*?)(?=ADDITIONAL DECISIONS|$)',
                llm_response, re.DOTALL | re.IGNORECASE
            )
            if aa_match:
                for line in aa_match.group(1).strip().split('\n'):
                    cleaned = line.strip().lstrip('- *')
                    if cleaned and len(cleaned) > 10 and cleaned not in action_items:
                        action_items.append(cleaned)

            # Extract summary from LLM
            sum_match = re.search(
                r'SUMMARY[:\s]*\n(.*?)(?=KEY POINTS|$)',
                llm_response, re.DOTALL | re.IGNORECASE
            )
            summary = sum_match.group(1).strip() if sum_match else llm_response[:300]
        else:
            summary = f"Meeting transcript with {len(message.split())} words."
            if participants:
                summary += f" Participants: {', '.join(participants[:5])}."

        record = MeetingRecord(
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            key_points=key_points,
            participants=participants,
        )
        self.store_record(record)

        # Store in episodic memory
        if engram:
            try:
                engram.episodic.store(
                    f"Meeting summary: {summary}",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Scribe] Meeting Summary"]
        lines.append(f"  {summary}")

        if participants:
            lines.append(f"\n  Participants: {', '.join(participants)}")

        if action_items:
            lines.append(f"\n  Action Items ({len(action_items)}):")
            for i, item in enumerate(action_items, 1):
                lines.append(f"    {i}. {item}")

        if decisions:
            lines.append(f"\n  Decisions ({len(decisions)}):")
            for i, d in enumerate(decisions, 1):
                lines.append(f"    {i}. {d}")

        if key_points:
            lines.append(f"\n  Key Points ({len(key_points)}):")
            for i, kp in enumerate(key_points, 1):
                lines.append(f"    {i}. {kp}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # AgentModule tier methods
    # ------------------------------------------------------------------

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest summarization when transcript-like text is detected."""
        # Look for speaker-turn patterns or common meeting keywords
        speaker_turns = len(re.findall(r'^[A-Z][a-zA-Z]+\s*[:\-]', message, re.MULTILINE))
        meeting_words = sum(1 for w in ("agenda", "minutes", "attendees", "action item",
                                        "meeting", "discussion", "recap")
                            if w in message.lower())
        if speaker_turns >= 2 or meeting_words >= 2:
            return (
                "This looks like meeting content. Run Scribe to extract action items, "
                "decisions, and a structured summary."
            )
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for new transcripts and meeting start events."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "meeting.started":
            meeting_name = payload.get("name", "unnamed meeting")
            return f"Meeting started: '{meeting_name}'. Ready to summarize when transcript is available."

        if topic == "transcript.uploaded":
            source = payload.get("source", "unknown")
            size = payload.get("size_words", 0)
            return (
                f"Transcript uploaded from {source} ({size} words). "
                "Scribe can extract action items and decisions."
            )

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route summaries to kindle for expansion or mnemonic for storage."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        parts: list[str] = []

        # Send to mnemonic for long-term storage
        try:
            mem_result = await cortex.route(
                "mnemonic",
                f"Store meeting summary:\n{analysis_result}",
                context,
            )
            if mem_result:
                parts.append(f"[mnemonic] {mem_result}")
        except Exception:
            pass

        # Offer expanded write-up via kindle if action items were found
        if "Action Items" in analysis_result:
            try:
                kindle_result = await cortex.route(
                    "kindle",
                    f"Expand this meeting summary into a polished report:\n{analysis_result}",
                    context,
                )
                if kindle_result:
                    parts.append(f"[kindle] {kindle_result}")
            except Exception:
                pass

        return "\n".join(parts)
