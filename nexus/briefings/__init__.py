"""ONEXUS daily briefings — autonomous reports of kernel state and activity.

Public surface:
    from nexus.briefings.daily import render_briefing, write_briefing

The briefing format intentionally mirrors the ONEXUS-Agents and SMADP daily
report conventions so all three AllStreets repos share a consistent voice.
"""
from nexus.briefings.daily import render_briefing, write_briefing

__all__ = ["render_briefing", "write_briefing"]
