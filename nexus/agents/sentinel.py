"""
Sentinel -- scheduled task and cron job monitor.
Tracks scheduled tasks, detects missed executions, and alerts
on failures, timeouts, and schedule drift.

Inspired by:
  - healthchecks/healthchecks (BSD 3-Clause) -- cron job monitoring service
  - cronitorio/cronitor-python (MIT) -- cron monitoring client
  - MichielMe/fastscheduler (MIT) -- decorator-first Python scheduler
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ScheduledTask:
    name: str
    schedule: str  # cron expression or interval
    last_run: str
    status: str  # "ok", "late", "failed", "missed"
    duration_ms: int = 0


@dataclass
class HealthReport:
    total_tasks: int
    healthy: int
    late: int
    failed: int
    missed: int
    tasks: list[ScheduledTask]


# Cron field names for explanation
_CRON_FIELDS = ["minute", "hour", "day_of_month", "month", "day_of_week"]

_CRON_SPECIALS: dict[str, str] = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@midnight": "0 0 * * *",
}


class SentinelModule(AgentModule):
    name = "sentinel"
    description = "Scheduled task monitor -- tracks cron jobs, detects missed runs, alerts on failures"
    version = "0.1.0"

    watch_events: list[str] = ["task.completed", "task.failed", "cron.missed"]
    coordination_targets: list[str] = ["dispatch", "vigil"]

    def __init__(self):
        self._tasks: list[ScheduledTask] = []
        self._reports: list[HealthReport] = []

    def register_task(self, name: str, schedule: str, last_run: str = "",
                       status: str = "ok", duration_ms: int = 0) -> ScheduledTask:
        """Register a scheduled task for monitoring."""
        task = ScheduledTask(name=name, schedule=schedule, last_run=last_run,
                              status=status, duration_ms=duration_ms)
        self._tasks.append(task)
        return task

    def list_tasks(self) -> list[ScheduledTask]:
        return list(self._tasks)

    @staticmethod
    def parse_cron(expression: str) -> dict[str, str]:
        """Parse a cron expression into its components."""
        expression = _CRON_SPECIALS.get(expression.lower(), expression)
        parts = expression.strip().split()
        if len(parts) < 5:
            return {"error": f"Invalid cron expression: expected 5 fields, got {len(parts)}"}
        result: dict[str, str] = {}
        for i, field_name in enumerate(_CRON_FIELDS):
            result[field_name] = parts[i]
        return result

    @staticmethod
    def explain_cron(expression: str) -> str:
        """Generate a human-readable explanation of a cron expression."""
        expression = _CRON_SPECIALS.get(expression.lower(), expression)
        parts = expression.strip().split()
        if len(parts) < 5:
            return f"Invalid cron expression: {expression}"

        minute, hour, dom, month, dow = parts[:5]
        segments: list[str] = []

        # Minute
        if minute == "*":
            segments.append("every minute")
        elif minute == "0":
            pass  # handled with hour
        elif "/" in minute:
            segments.append(f"every {minute.split('/')[1]} minutes")
        else:
            segments.append(f"at minute {minute}")

        # Hour
        if hour == "*":
            if minute != "*":
                segments.append("every hour")
        elif "/" in hour:
            segments.append(f"every {hour.split('/')[1]} hours")
        else:
            segments.append(f"at {hour}:{minute.zfill(2)}")

        # Day of month
        if dom != "*":
            if "/" in dom:
                segments.append(f"every {dom.split('/')[1]} days")
            else:
                segments.append(f"on day {dom}")

        # Month
        if month != "*":
            month_names = {
                "1": "January", "2": "February", "3": "March", "4": "April",
                "5": "May", "6": "June", "7": "July", "8": "August",
                "9": "September", "10": "October", "11": "November", "12": "December",
            }
            segments.append(f"in {month_names.get(month, month)}")

        # Day of week
        if dow != "*":
            day_names = {"0": "Sunday", "1": "Monday", "2": "Tuesday",
                         "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday"}
            segments.append(f"on {day_names.get(dow, dow)}")

        return "Runs " + ", ".join(segments) if segments else "Runs every minute"

    @staticmethod
    def parse_task_status(text: str) -> list[dict[str, str]]:
        """Parse task status reports from text."""
        tasks: list[dict[str, str]] = []
        # Match patterns like "task_name: OK 2024-01-15T14:30:00 (250ms)"
        for match in re.finditer(
            r'(\w[\w\s-]*?):\s*(OK|FAIL|LATE|MISSED|ERROR)\s*(?:(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}))?'
            r'\s*(?:\((\d+)\s*ms\))?',
            text, re.IGNORECASE,
        ):
            tasks.append({
                "name": match.group(1).strip(),
                "status": match.group(2).lower(),
                "last_run": match.group(3) or "",
                "duration_ms": match.group(4) or "0",
            })
        return tasks

    def health_check(self) -> HealthReport:
        """Generate a health report for all registered tasks."""
        healthy = sum(1 for t in self._tasks if t.status == "ok")
        late = sum(1 for t in self._tasks if t.status == "late")
        failed = sum(1 for t in self._tasks if t.status == "failed")
        missed = sum(1 for t in self._tasks if t.status == "missed")
        report = HealthReport(
            total_tasks=len(self._tasks), healthy=healthy,
            late=late, failed=failed, missed=missed, tasks=list(self._tasks),
        )
        self._reports.append(report)
        return report

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Check for cron expression to explain
        cron_match = re.search(r'(?:^|\s)((?:\S+\s+){4}\S+)(?:\s|$)', message)
        has_cron = False
        cron_explanation = ""
        if cron_match:
            candidate = cron_match.group(1).strip()
            parts = candidate.split()
            if len(parts) == 5 and all(re.match(r'^[\d*,/-]+$', p) for p in parts):
                has_cron = True
                cron_explanation = self.explain_cron(candidate)

        # Check for @shorthand
        for shorthand in _CRON_SPECIALS:
            if shorthand in message.lower():
                has_cron = True
                cron_explanation = self.explain_cron(shorthand)
                break

        # Parse any task statuses
        parsed_tasks = self.parse_task_status(message)
        for t in parsed_tasks:
            status = "ok" if t["status"] == "ok" else t["status"]
            if status == "error":
                status = "failed"
            self.register_task(
                name=t["name"], schedule="", last_run=t["last_run"],
                status=status, duration_ms=int(t["duration_ms"]),
            )

        # Generate health report if we have tasks
        report = None
        if self._tasks:
            report = self.health_check()

        if engram:
            try:
                total = len(self._tasks)
                failed_count = sum(1 for t in self._tasks if t.status in ("failed", "missed"))
                engram.episodic.store(
                    f"Task monitoring: {total} tasks, {failed_count} failures/missed",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Sentinel] Task Monitor"]

        if has_cron:
            lines.append(f"  Cron: {cron_explanation}")

        if report:
            lines.append(f"\n  Health Report:")
            lines.append(f"    Total: {report.total_tasks}")
            lines.append(f"    Healthy: {report.healthy}")
            if report.late:
                lines.append(f"    Late: {report.late}")
            if report.failed:
                lines.append(f"    Failed: {report.failed}")
            if report.missed:
                lines.append(f"    Missed: {report.missed}")

            for t in report.tasks:
                icon = "+" if t.status == "ok" else "!" if t.status == "late" else "X"
                duration = f" ({t.duration_ms}ms)" if t.duration_ms else ""
                lines.append(f"    {icon} {t.name}: {t.status.upper()}{duration}")
        elif not has_cron:
            if llm:
                prompt = (
                    "Help set up monitoring for scheduled tasks. "
                    "The user said:\n\n"
                    f"{message[:3000]}\n\n"
                    "Provide: 1) Recommended cron schedule 2) Monitoring strategy 3) Alert thresholds"
                )
                try:
                    analysis = await llm.complete(prompt)
                    lines.append(f"\n{analysis[:1500]}")
                except Exception:
                    pass
            else:
                lines.append("  Provide task statuses (name: OK/FAIL timestamp) or cron expressions to analyze.")

        if llm and report and (report.failed or report.missed):
            prompt = (
                "These scheduled tasks have issues:\n"
                + "\n".join(f"- {t.name}: {t.status}" for t in report.tasks if t.status in ("failed", "missed"))
                + "\n\nProvide: 1) Likely causes 2) Remediation steps 3) Preventive measures"
            )
            try:
                analysis = await llm.complete(prompt)
                lines.append(f"\n  -- Diagnosis --\n  {analysis[:1000]}")
            except Exception:
                pass

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest monitoring for untracked scheduled tasks detected in context."""
        msg_lower = message.lower()
        suggestions: list[str] = []

        # Detect cron-adjacent keywords that haven't been registered
        unregistered_hints = [
            kw for kw in ("backup", "cleanup", "sync", "export", "import", "report", "digest", "sweep")
            if kw in msg_lower
        ]
        registered_names = {t.name.lower() for t in self._tasks}
        unregistered = [h for h in unregistered_hints if h not in registered_names]

        if unregistered:
            suggestions.append(
                f"Detected potential scheduled operations ({', '.join(unregistered)}) "
                "not registered with Sentinel. Add them via register_task() for missed-run detection."
            )

        if self._tasks:
            problem_tasks = [t for t in self._tasks if t.status in ("failed", "missed", "late")]
            if problem_tasks:
                suggestions.append(
                    f"{len(problem_tasks)} task(s) in degraded state "
                    f"({', '.join(t.name for t in problem_tasks[:3])}). "
                    "Review logs and consider adjusting schedules or alerting thresholds."
                )

        return " ".join(suggestions)

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Watch for task completion, failure, and missed cron events."""
        topic = event.get("topic", "")
        payload = event.get("payload", {})
        task_name = payload.get("task") or payload.get("name", "unknown")

        if topic == "task.completed":
            duration = payload.get("duration_ms")
            duration_str = f" in {duration}ms" if duration else ""
            self.register_task(
                name=task_name, schedule="",
                last_run=payload.get("timestamp", ""),
                status="ok",
                duration_ms=int(duration) if duration else 0,
            )
            return f"Task '{task_name}' completed{duration_str}. Sentinel health record updated."

        if topic == "task.failed":
            error = payload.get("error") or payload.get("reason", "")
            error_str = f": {error}" if error else ""
            self.register_task(
                name=task_name, schedule="",
                last_run=payload.get("timestamp", ""),
                status="failed",
            )
            return f"Task '{task_name}' FAILED{error_str}. Escalating for review."

        if topic == "cron.missed":
            schedule = payload.get("schedule", "")
            schedule_str = f" (schedule: {schedule})" if schedule else ""
            self.register_task(
                name=task_name, schedule=schedule,
                last_run="",
                status="missed",
            )
            return f"Cron '{task_name}'{schedule_str} was MISSED. Sentinel flagged for alert routing."

        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route failure alerts to dispatch and log analysis to vigil."""
        cortex = context.get("cortex")
        if not cortex:
            return ""

        lines: list[str] = []
        result_lower = analysis_result.lower()
        has_failures = any(kw in result_lower for kw in ("failed", "missed", "x ", ": failed", ": missed"))

        if has_failures:
            # Alert dispatch to notify stakeholders
            try:
                alert_msg = (
                    f"TASK ALERT from Sentinel -- failures or missed runs detected.\n"
                    f"{analysis_result[:500]}"
                )
                dispatch_result = await cortex.send("dispatch", alert_msg, context)
                if dispatch_result:
                    lines.append(f"[dispatch] {dispatch_result}")
            except Exception:
                pass

            # Send to vigil for log correlation and pattern analysis
            try:
                vigil_result = await cortex.send("vigil", analysis_result, context)
                if vigil_result:
                    lines.append(f"[vigil] {vigil_result}")
            except Exception:
                pass

        return "\n".join(lines)
