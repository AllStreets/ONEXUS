"""
Dispatch -- multi-channel notification routing agent.
Routes messages to appropriate channels (email, slack, webhook, sms)
based on priority, content, and recipient preferences.

Inspired by:
  - novuhq/novu (MIT) -- open-source notification infrastructure
  - caronc/apprise (BSD 2-Clause) -- push notification library
  - tata1mg/notifyone (MIT) -- event-driven notification system
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class Notification:
    channel: str  # "email", "slack", "webhook", "sms", "push"
    recipient: str
    subject: str
    body: str
    priority: str  # "critical", "high", "normal", "low"
    tags: list[str] = field(default_factory=list)


@dataclass
class RoutingRule:
    name: str
    condition: str  # keyword or pattern to match
    channel: str
    priority: str


# Default routing rules
_DEFAULT_RULES: list[dict[str, str]] = [
    {"name": "urgent_email", "condition": "urgent|critical|emergency", "channel": "email", "priority": "critical"},
    {"name": "alert_slack", "condition": "alert|warning|attention", "channel": "slack", "priority": "high"},
    {"name": "deploy_webhook", "condition": "deploy|release|publish", "channel": "webhook", "priority": "high"},
    {"name": "report_email", "condition": "report|summary|digest", "channel": "email", "priority": "normal"},
    {"name": "info_slack", "condition": "update|info|fyi", "channel": "slack", "priority": "low"},
]


class DispatchModule(AgentModule):
    name = "dispatch"
    description = "Multi-channel notification router -- routes alerts to email, slack, webhook, sms by priority"
    version = "0.1.0"

    watch_events: list[str] = ["alert.triggered", "notification.queued"]
    coordination_targets: list[str] = ["sentinel", "bastion"]

    def __init__(self):
        self._rules: list[RoutingRule] = [
            RoutingRule(name=r["name"], condition=r["condition"],
                        channel=r["channel"], priority=r["priority"])
            for r in _DEFAULT_RULES
        ]
        self._sent: list[Notification] = []

    def add_rule(self, name: str, condition: str, channel: str, priority: str = "normal") -> None:
        """Add a custom routing rule."""
        self._rules.append(RoutingRule(name=name, condition=condition,
                                        channel=channel, priority=priority))

    def list_rules(self) -> list[RoutingRule]:
        return list(self._rules)

    @staticmethod
    def detect_priority(message: str) -> str:
        """Detect message priority from content."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("critical", "emergency", "outage", "down", "p0")):
            return "critical"
        if any(w in msg_lower for w in ("urgent", "important", "alert", "warning", "p1")):
            return "high"
        if any(w in msg_lower for w in ("low", "fyi", "minor", "info")):
            return "low"
        return "normal"

    @staticmethod
    def detect_channel(message: str) -> str:
        """Detect target channel from message."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("email", "mail", "inbox")):
            return "email"
        if any(w in msg_lower for w in ("slack", "channel", "chat")):
            return "slack"
        if any(w in msg_lower for w in ("webhook", "hook", "api")):
            return "webhook"
        if any(w in msg_lower for w in ("sms", "text", "phone")):
            return "sms"
        if any(w in msg_lower for w in ("push", "notification", "mobile")):
            return "push"
        return "slack"

    @staticmethod
    def extract_recipients(text: str) -> list[str]:
        """Extract recipient identifiers from text."""
        recipients: list[str] = []
        # Email addresses
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        recipients.extend(emails)
        # @mentions
        mentions = re.findall(r'@(\w+)', text)
        for m in mentions:
            if '.' not in m and m not in [r.split('@')[0] for r in emails]:
                recipients.append(f"@{m}")
        # Phone numbers
        phones = re.findall(r'\+?\d[\d\s-]{9,}', text)
        recipients.extend(p.strip() for p in phones)
        return list(dict.fromkeys(recipients))

    def route(self, message: str) -> list[dict[str, str]]:
        """Determine routing based on rules."""
        msg_lower = message.lower()
        matched: list[dict[str, str]] = []
        for rule in self._rules:
            if re.search(rule.condition, msg_lower):
                matched.append({
                    "rule": rule.name,
                    "channel": rule.channel,
                    "priority": rule.priority,
                })
        return matched

    def create_notification(self, message: str, channel: str = "",
                            priority: str = "", recipient: str = "") -> Notification:
        """Create a notification from message text."""
        if not channel:
            channel = self.detect_channel(message)
        if not priority:
            priority = self.detect_priority(message)
        if not recipient:
            recipients = self.extract_recipients(message)
            recipient = recipients[0] if recipients else "default"

        # Extract subject (first line or first 60 chars)
        lines = message.strip().split('\n')
        subject = lines[0][:60] if lines else message[:60]
        body = message

        notification = Notification(
            channel=channel, recipient=recipient,
            subject=subject, body=body, priority=priority,
        )
        self._sent.append(notification)
        return notification

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        priority = self.detect_priority(message)
        channel = self.detect_channel(message)
        recipients = self.extract_recipients(message)
        routes = self.route(message)

        notification = self.create_notification(message, channel, priority)

        # LLM-enhanced message formatting
        llm_formatted = ""
        if llm:
            prompt = (
                f"Format this notification for {channel} delivery at {priority} priority.\n\n"
                f"Original message:\n{message[:2000]}\n\n"
                f"Create a well-formatted notification with:\n"
                "1. Clear subject line\n"
                "2. Formatted body appropriate for the channel\n"
                "3. Action items if any"
            )
            try:
                llm_formatted = await llm.complete(prompt)
            except Exception:
                pass

        if engram:
            try:
                engram.episodic.store(
                    f"Notification dispatched: {channel}/{priority} to {notification.recipient}",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Dispatch] Notification Routed"]
        lines.append(f"  Channel: {channel}")
        lines.append(f"  Priority: {priority}")
        if recipients:
            lines.append(f"  Recipients: {', '.join(recipients[:5])}")
        lines.append(f"  Subject: {notification.subject}")

        if routes:
            lines.append(f"\n  Matching Rules ({len(routes)}):")
            for r in routes:
                lines.append(f"    {r['rule']} -> {r['channel']} ({r['priority']})")

        if llm_formatted:
            lines.append(f"\n  -- Formatted Message --\n  {llm_formatted[:1000]}")
        else:
            lines.append(f"\n  Body preview: {notification.body[:200]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest routing improvements when patterns indicate suboptimal channel use."""
        priority = self.detect_priority(message)
        channel = self.detect_channel(message)
        suggestions: list[str] = []

        if priority == "critical" and channel not in ("email", "sms"):
            suggestions.append(
                f"Critical-priority message routed to '{channel}'. "
                "Consider email or SMS for guaranteed delivery on P0 incidents."
            )

        routes = self.route(message)
        if not routes:
            suggestions.append(
                "No routing rules matched this message. "
                "Add a custom rule via add_rule() to cover this message pattern."
            )
        elif len(routes) > 3:
            suggestions.append(
                f"{len(routes)} routing rules matched. "
                "Review rule overlap to avoid duplicate notifications."
            )

        return " ".join(suggestions)

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for incoming alert and queued notification events and route them."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})

        if topic == "alert.triggered":
            alert_id = payload.get("alert_id") or payload.get("id", "unknown")
            severity = payload.get("severity") or payload.get("level", "unknown")
            return (
                f"Alert '{alert_id}' triggered (severity: {severity}). "
                "Dispatch will route to appropriate channels based on priority rules."
            )

        if topic == "notification.queued":
            notif_id = payload.get("notification_id") or payload.get("id", "unknown")
            channel = payload.get("channel", "unknown")
            return (
                f"Notification '{notif_id}' queued for '{channel}'. "
                "Dispatch processing queue."
            )

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route task failures to sentinel and security alerts to bastion."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        lines: list[str] = []
        result_lower = analysis_result.lower()

        # Task failure signals go to sentinel for monitoring
        if any(kw in result_lower for kw in ("task", "job", "cron", "scheduled", "failed", "missed")):
            try:
                sentinel_result = await cortex.send("sentinel", analysis_result, context)
                if sentinel_result:
                    lines.append(f"[sentinel] {sentinel_result}")
            except Exception:
                pass

        # Security alert signals go to bastion for deeper scanning
        if any(kw in result_lower for kw in ("security", "vulnerability", "exploit", "breach", "auth")):
            try:
                bastion_result = await cortex.send("bastion", analysis_result, context)
                if bastion_result:
                    lines.append(f"[bastion] {bastion_result}")
            except Exception:
                pass

        return "\n".join(lines)
