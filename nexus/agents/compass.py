"""
Compass -- personalized learning roadmap generator.
Creates structured learning plans with milestones, resources,
and time estimates for any technical skill.

Inspired by:
  - bootdotdev/curriculum (MIT) — open backend dev curriculum with roadmap
  - AgenticAiLabs/Ai-Engineering-Roadmap (MIT) — curated AI/ML curriculum
  - roadmap.sh community roadmaps — structured technical learning paths
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class Milestone:
    title: str
    description: str
    resources: list[str]
    duration_weeks: int
    checkpoint: str = ""


@dataclass
class Roadmap:
    skill: str
    level: str  # "beginner", "intermediate", "advanced"
    total_weeks: int
    milestones: list[Milestone]


# Pre-built roadmap templates for common skills
_SKILL_TEMPLATES: dict[str, dict[str, Any]] = {
    "python": {
        "milestones": [
            {"title": "Fundamentals", "weeks": 2, "topics": "Variables, types, control flow, functions, error handling"},
            {"title": "Data Structures", "weeks": 2, "topics": "Lists, dicts, sets, tuples, comprehensions, generators"},
            {"title": "OOP and Modules", "weeks": 2, "topics": "Classes, inheritance, packages, virtual environments"},
            {"title": "File I/O and APIs", "weeks": 2, "topics": "File reading/writing, JSON, requests, REST APIs"},
            {"title": "Testing", "weeks": 1, "topics": "pytest, unit tests, mocking, TDD basics"},
            {"title": "Project: Build a CLI Tool", "weeks": 3, "topics": "Click, argparse, packaging, publishing to PyPI"},
        ],
    },
    "rust": {
        "milestones": [
            {"title": "Ownership and Borrowing", "weeks": 3, "topics": "Ownership, references, lifetimes, the borrow checker"},
            {"title": "Structs and Enums", "weeks": 2, "topics": "Structs, enums, pattern matching, Option/Result"},
            {"title": "Traits and Generics", "weeks": 2, "topics": "Traits, generics, trait bounds, associated types"},
            {"title": "Error Handling", "weeks": 1, "topics": "Result, ?, custom errors, anyhow/thiserror"},
            {"title": "Concurrency", "weeks": 2, "topics": "Threads, channels, Arc/Mutex, async/await, tokio"},
            {"title": "Project: Build a CLI Tool", "weeks": 2, "topics": "clap, serde, file I/O, cargo publish"},
        ],
    },
    "javascript": {
        "milestones": [
            {"title": "Core Language", "weeks": 2, "topics": "Variables, functions, closures, prototypes, ES6+ features"},
            {"title": "Async Programming", "weeks": 2, "topics": "Promises, async/await, event loop, fetch API"},
            {"title": "DOM and Browser APIs", "weeks": 2, "topics": "DOM manipulation, events, localStorage, Web APIs"},
            {"title": "Node.js Basics", "weeks": 2, "topics": "npm, modules, fs, http, Express basics"},
            {"title": "Testing", "weeks": 1, "topics": "Jest, Vitest, testing library, mocking"},
            {"title": "Project: Full-Stack App", "weeks": 3, "topics": "REST API + frontend, deployment"},
        ],
    },
}


class CompassModule(AgentModule):
    name = "compass"
    description = "Learning roadmap generator -- creates personalized study plans with milestones and resources"
    version = "0.1.0"

    watch_events: list[str] = ["skill.gap_detected", "learning.request"]
    coordination_targets: list[str] = ["thesis", "mnemonic"]

    def __init__(self):
        self._roadmaps: list[Roadmap] = []

    @staticmethod
    def detect_skill(message: str) -> str:
        """Detect the skill from the message."""
        msg_lower = message.lower()
        for skill in _SKILL_TEMPLATES:
            if skill in msg_lower:
                return skill
        # Extract the main noun as the skill
        match = re.search(r'learn\s+(\w+(?:\s+\w+)?)', msg_lower)
        if match:
            return match.group(1).strip()
        return msg_lower.strip()[:30]

    @staticmethod
    def detect_level(message: str) -> str:
        """Detect current skill level from the message."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("beginner", "start", "scratch", "new to", "never")):
            return "beginner"
        if any(w in msg_lower for w in ("advanced", "expert", "deep", "master")):
            return "advanced"
        return "intermediate"

    def generate_roadmap(self, skill: str, level: str) -> Roadmap:
        """Generate a roadmap from templates or a generic structure."""
        template = _SKILL_TEMPLATES.get(skill.lower())

        if template:
            milestones = []
            for m in template["milestones"]:
                milestones.append(Milestone(
                    title=m["title"],
                    description=m["topics"],
                    resources=[],
                    duration_weeks=m["weeks"],
                    checkpoint=f"Complete exercises for {m['title']}",
                ))
            total = sum(m.duration_weeks for m in milestones)
            return Roadmap(skill=skill, level=level, total_weeks=total, milestones=milestones)

        # Generic roadmap for unknown skills
        milestones = [
            Milestone("Fundamentals", f"Core concepts of {skill}", [], 3, f"Explain {skill} basics"),
            Milestone("Intermediate Concepts", f"Deeper {skill} patterns and practices", [], 3, "Build a small project"),
            Milestone("Advanced Topics", f"Expert-level {skill} techniques", [], 3, "Contribute to open source"),
            Milestone("Capstone Project", f"Full {skill} project end-to-end", [], 3, "Ship a complete project"),
        ]
        return Roadmap(skill=skill, level=level, total_weeks=12, milestones=milestones)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        skill = self.detect_skill(message)
        level = self.detect_level(message)

        # Generate base roadmap
        roadmap = self.generate_roadmap(skill, level)

        # Enhance with LLM for resources and customization
        if llm:
            prompt = (
                f"Create a personalized learning roadmap for someone at the {level} level "
                f"wanting to learn {skill}.\n\n"
                "For each phase, suggest:\n"
                "1. Specific free resources (official docs, tutorials, books)\n"
                "2. A hands-on exercise or project\n"
                "3. A checkpoint to verify understanding\n\n"
                "Be specific and actionable. Recommend the single best resource for each topic, "
                "not a long list."
            )
            try:
                llm_response = await llm.complete(prompt)
                # Append LLM suggestions to the last milestone's resources
                if roadmap.milestones:
                    roadmap.milestones[-1].resources.append(f"AI-curated: {llm_response[:500]}")
            except Exception:
                pass

        self._roadmaps.append(roadmap)

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Learning roadmap created: {skill} ({level}), {roadmap.total_weeks} weeks",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Compass] Learning Roadmap: {skill.title()}"]
        lines.append(f"  Level: {level.title()}")
        lines.append(f"  Duration: ~{roadmap.total_weeks} weeks")
        lines.append("")

        week_counter = 0
        for i, ms in enumerate(roadmap.milestones, 1):
            week_start = week_counter + 1
            week_end = week_counter + ms.duration_weeks
            week_counter = week_end

            lines.append(f"  Phase {i}: {ms.title} (Weeks {week_start}-{week_end})")
            lines.append(f"    Topics: {ms.description}")
            if ms.checkpoint:
                lines.append(f"    Checkpoint: {ms.checkpoint}")
            if ms.resources:
                for r in ms.resources:
                    lines.append(f"    Resource: {r}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # AgentModule tier methods
    # ------------------------------------------------------------------

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest a learning path when a skill gap is detected in the message."""
        msg_lower = message.lower()
        gap_signals = [
            "don't know", "don't understand", "struggling with", "never learned",
            "need to learn", "how do i", "where do i start", "skill gap",
            "weak in", "unfamiliar with",
        ]
        matched = [s for s in gap_signals if s in msg_lower]
        if matched:
            skill = self.detect_skill(message)
            level = self.detect_level(message)
            return (
                f"Detected a possible skill gap around '{skill}' ({level} level). "
                "Compass can generate a structured roadmap with milestones and checkpoints."
            )
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for skill gap detections and explicit learning requests."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "skill.gap_detected":
            skill = payload.get("skill", "unknown")
            user = payload.get("user", "user")
            return (
                f"Skill gap detected for {user}: '{skill}'. "
                "Compass can generate a personalized learning roadmap."
            )

        if topic == "learning.request":
            skill = payload.get("skill", "unknown")
            level = payload.get("level", "beginner")
            return (
                f"Learning request received: {skill} ({level}). "
                "Compass will build a milestone-based roadmap."
            )

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route to thesis for academic resources or mnemonic for storing progress."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        parts: list[str] = []

        # Ask thesis for relevant academic papers and research context
        skill_line = next(
            (line for line in analysis_result.split("\n") if "Roadmap:" in line), ""
        )
        skill_hint = skill_line.replace("[Compass] Learning Roadmap:", "").strip() or "the skill"
        try:
            thesis_result = await cortex.route(
                "thesis",
                f"Find academic papers and research relevant to learning {skill_hint}.",
                context,
            )
            if thesis_result:
                parts.append(f"[thesis] {thesis_result}")
        except Exception:
            pass

        # Store the roadmap and progress baseline in mnemonic
        try:
            mem_result = await cortex.route(
                "mnemonic",
                f"Store learning roadmap and progress baseline:\n{analysis_result}",
                context,
            )
            if mem_result:
                parts.append(f"[mnemonic] {mem_result}")
        except Exception:
            pass

        return "\n".join(parts)
