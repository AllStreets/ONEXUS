# Contributing to NEXUS

NEXUS accepts two types of community contributions: **modules** and **agents**. Both follow the same submission process but have different base classes and file structures.

---

## Modules vs. Agents

| | Module | Agent |
|---|---|---|
| **Base class** | `NexusModule` | `AgentModule` |
| **Entry point** | `handle()` | `analyze()` + `suggest()` + `monitor()` + `coordinate()` |
| **Trust model** | Binary allow/deny | Graduated sovereignty (0-100, five tiers) |
| **Directory** | `community/modules/<user>/<name>/` | `community/agents/<user>/<name>/` |
| **Use when** | Building persistent intelligence (perception, reasoning, memory) | Building a narrow task specialist that earns autonomy |

---

## Contributing a Module

### File Structure

```
community/modules/<your-github-username>/<module_name>/
├── module.py          # NexusModule subclass
├── manifest.json      # Module metadata
├── tests/
│   └── test_module.py # Minimum 4 tests
└── README.md          # Usage documentation
```

### manifest.json

```json
{
  "name": "your_module",
  "author": "your_github_username",
  "description": "One sentence describing what this module does (10-200 chars).",
  "version": "1.0.0",
  "tier": "community",
  "type": "module",
  "keywords": ["routing", "keywords", "for", "cortex"],
  "license": "Apache-2.0"
}
```

All fields are required. `tier` must be `"community"`. `type` must be `"module"`.

### Module Rules

1. Your module must subclass `NexusModule` from `nexus.modules.base`
2. You must define `name`, `description`, and `version` class attributes
3. You must implement `async def handle(self, message: str, context: dict) -> str`
4. **Do NOT import from `nexus.kernel.*`** -- use the `context` dict for all kernel access
5. License must be OSI-approved

### Minimal Example

```python
from nexus.modules.base import NexusModule

class MyModule(NexusModule):
    name = "my_module"
    description = "Does something useful."
    version = "1.0.0"

    async def handle(self, message: str, context: dict) -> str:
        return f"[{self.name}] Processed: {message}"
```

Full guide: [Build a Module](https://allstreets.github.io/NEXUS/guides/building-a-module/)

---

## Contributing an Agent

### File Structure

```
community/agents/<your-github-username>/<agent_name>/
├── agent.py           # AgentModule subclass
├── manifest.json      # Agent metadata
├── tests/
│   └── test_agent.py  # Minimum 6 tests (one per tier method + attributes + pattern-based)
└── README.md          # Usage documentation
```

### manifest.json

```json
{
  "name": "your_agent",
  "author": "your_github_username",
  "description": "One sentence describing what this agent does (10-200 chars).",
  "version": "1.0.0",
  "tier": "community",
  "type": "agent",
  "keywords": ["routing", "keywords", "for", "cortex"],
  "watch_events": ["optional.pulse.topics"],
  "coordination_targets": ["optional_agent_names"],
  "license": "Apache-2.0"
}
```

All fields are required except `watch_events` and `coordination_targets`. `tier` must be `"community"`. `type` must be `"agent"`.

### Agent Rules

1. Your agent must subclass `AgentModule` from `nexus.agents.base`
2. You must define `name`, `description`, and `version` class attributes
3. You must implement `async def analyze(self, message: str, context: dict) -> str`
4. `analyze()` must produce useful output **without an LLM** using pattern-based analysis (regex, keyword matching, structural rules). LLM enhancement is optional.
5. `suggest()`, `monitor()`, and `coordinate()` are optional but recommended
6. **Do NOT import from `nexus.kernel.*`** -- use the `context` dict for all kernel access
7. **Do NOT override `handle()`** -- AgentModule routes through trust tiers automatically
8. License must be OSI-approved

### Minimal Example

```python
from nexus.agents.base import AgentModule

class MyAgent(AgentModule):
    name = "my_agent"
    description = "Does something useful."
    version = "0.1.0"

    watch_events = ["relevant.topic"]
    coordination_targets = ["other_agent"]

    async def analyze(self, message, context):
        """Core logic. Runs at every trust level. Must work without LLM."""
        return f"[{self.name}] Analyzed: {message}"

    async def suggest(self, message, context):
        """Proactive suggestions at ADVISOR+ trust (25+)."""
        return "You might also want to check..."

    async def monitor(self, event, context):
        """Background event watching at MONITOR+ trust (50+)."""
        return None

    async def coordinate(self, result, context):
        """Cross-agent routing at SOVEREIGN trust (100)."""
        return ""
```

Full guide: [Build an Agent](https://allstreets.github.io/NEXUS/guides/building-an-agent/)

---

## Submitting

1. Fork the NEXUS repository
2. Add your contribution to the appropriate directory:
   - Modules: `community/modules/<your-username>/<module_name>/`
   - Agents: `community/agents/<your-username>/<agent_name>/`
3. Open a PR against `main`
4. CI will validate your submission automatically
5. A maintainer will review and merge

## What CI Checks

- manifest.json conforms to the schema (including `type` field)
- Module subclasses NexusModule with required attributes, or agent subclasses AgentModule
- Tests exist and pass
- No imports from nexus.kernel.*
- Agents: `analyze()` works without LLM (pattern-based test required)
- Agents: `handle()` is not overridden
- License is OSI-approved
