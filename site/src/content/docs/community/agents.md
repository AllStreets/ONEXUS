---
title: "Agent Discovery"
description: "Browse 25 graduated sovereignty agents -- task specialists that earn autonomy through demonstrated reliability"
sidebar:
  order: 2
---

## Agent Discovery

NEXUS ships with 25 agents built on the `AgentModule` base class. Each agent starts as a passive skill (trust 0) and earns autonomy through five trust tiers: SKILL, ADVISOR, MONITOR, AUTONOMOUS, and SOVEREIGN. Every agent works standalone using pattern-based analysis (no LLM required), enhances with LLM when available, runs locally, requires no cloud services, and fits within the 8GB RAM floor.

### By Category

#### Code & Development

| Agent | What It Does |
|-------|-------------|
| [Vex](/NEXUS/reference/modules/vex/) | Scans code for 28 vulnerability patterns (injection, XSS, credentials, deserialization) |
| [Arbiter](/NEXUS/reference/modules/arbiter/) | Reviews code diffs and source for quality issues, style violations, anti-patterns |
| [Carve](/NEXUS/reference/modules/carve/) | Measures complexity, finds long functions, deep nesting, duplicate code |
| [Remedy](/NEXUS/reference/modules/remedy/) | Diagnoses error messages and stack traces, suggests fixes for 17 common types |
| [Scaffold](/NEXUS/reference/modules/scaffold/) | Generates Python, FastAPI, CLI project boilerplate from templates |
| [Axiom](/NEXUS/reference/modules/axiom/) | Generates test case stubs with edge cases from function signatures |
| [Rune](/NEXUS/reference/modules/rune/) | Builds, explains, and tests regex patterns from descriptions |

#### Data & Analysis

| Agent | What It Does |
|-------|-------------|
| [Flux](/NEXUS/reference/modules/flux/) | Converts natural language questions into SQL queries with schema awareness |
| [Vigil](/NEXUS/reference/modules/vigil/) | Parses log files, detects anomaly patterns, generates incident timelines |
| [Gauge](/NEXUS/reference/modules/gauge/) | Analyzes performance metrics, identifies bottlenecks in latency/CPU/memory |
| [Quarry](/NEXUS/reference/modules/quarry/) | Extracts structured data from HTML -- links, headings, tables, metadata |
| [Loom](/NEXUS/reference/modules/loom/) | Defines ETL pipelines with dependency resolution and topological ordering |

#### Business & Finance

| Agent | What It Does |
|-------|-------------|
| [Ledger](/NEXUS/reference/modules/ledger/) | Categorizes bank transactions, generates spending summaries, flags anomalies |
| [Tally](/NEXUS/reference/modules/tally/) | Builds financial projections with revenue modeling and runway calculation |
| [Mint](/NEXUS/reference/modules/mint/) | Generates invoices from line items with tax calculation and formatting |
| [Redline](/NEXUS/reference/modules/redline/) | Scans contracts for 15 risky clause patterns and missing protections |
| [Mandate](/NEXUS/reference/modules/mandate/) | Assesses compliance against GDPR, SOC2, HIPAA with gap analysis |

#### Content & Communication

| Agent | What It Does |
|-------|-------------|
| [Scribe](/NEXUS/reference/modules/scribe/) | Summarizes meeting transcripts -- participants, action items, decisions |
| [Kindle](/NEXUS/reference/modules/kindle/) | Expands bullet points into polished blog posts, docs, reports, emails |
| [Thesis](/NEXUS/reference/modules/thesis/) | Analyzes academic papers -- claims, methodology, limitations, gaps |
| [Compass](/NEXUS/reference/modules/compass/) | Generates personalized learning roadmaps for programming languages |

#### Infrastructure & Ops

| Agent | What It Does |
|-------|-------------|
| [Bastion](/NEXUS/reference/modules/bastion/) | Scans API endpoints for BOLA, auth gaps, mass assignment, OWASP risks |
| [Dispatch](/NEXUS/reference/modules/dispatch/) | Routes notifications to email, Slack, webhook, SMS by priority rules |
| [Sentinel](/NEXUS/reference/modules/sentinel/) | Monitors cron jobs, explains expressions, detects missed runs |
| [Mnemonic](/NEXUS/reference/modules/mnemonic/) | Personal knowledge base with keyword search and auto-tagging |

### How Agents Work

Every agent follows the graduated sovereignty model:

1. **Cortex routes** the message based on keyword matching
2. **AgentModule checks trust** via Aegis to determine which tiers are active
3. **`analyze()`** runs first (pattern-based, no LLM needed) -- this is the core logic
4. **`suggest()`** appends proactive suggestions at ADVISOR+ trust (25+)
5. **LLM enhancement** adds deeper analysis when a model is available
6. **`monitor()`** watches Pulse events in the background at MONITOR+ trust (50+)
7. **`coordinate()`** routes to other agents at SOVEREIGN trust (100)
8. **Results stored** in Engram and logged to Chronicle

Trust is always revocable. One bad outcome and Aegis dials it back.

### Building Your Own Agent

```python
from nexus.agents.base import AgentModule, TrustTier

class MyAgent(AgentModule):
    name = "my_agent"
    description = "Does something useful"
    version = "0.1.0"

    watch_events = ["relevant.topic"]
    coordination_targets = ["other_agent"]

    async def analyze(self, message, context):
        """Core logic. Runs at every trust level."""
        return "[MyAgent] Result"

    async def suggest(self, message, context):
        """Proactive suggestions at ADVISOR+ trust."""
        return "You might also want to..."

    async def monitor(self, event, context):
        """Background event watching at MONITOR+ trust."""
        return "Detected something interesting"

    async def coordinate(self, analysis_result, context):
        """Cross-agent routing at SOVEREIGN trust."""
        return ""
```

See the [Earned Autonomy](/NEXUS/concepts/earned-autonomy/) page for how trust tiers work, and the [Building a Module](/NEXUS/guides/building-a-module/) guide for the full spec.
