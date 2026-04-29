---
title: "Community Hub"
description: "Join the NEXUS community -- contribute modules, share agents, get involved"
sidebar:
  order: 1
---

## Community Hub

NEXUS is built by and for its community. Every module in the system is open source, auditable, and runs on your hardware. The project ships with 51 modules -- 26 core intelligence modules and 25 narrow AI agents -- all built on the same `NexusModule` interface.

---

### Get Involved

There are several ways to contribute to NEXUS, whether you write code or not.

**Build a Module**
Write a `NexusModule` subclass, add tests, submit a PR. Your module ships to every NEXUS user. The [Building a Module](/NEXUS/guides/building-a-module/) guide covers the full workflow from scaffold to merge.

**Build an Agent**
Narrow AI agents solve focused problems -- meeting summaries, code review, invoice generation, vulnerability scanning. If you have a use case that NEXUS doesn't cover, build an agent. Agents follow the same `NexusModule` base class and the same contribution process. See the [Agent Discovery](/NEXUS/community/agents/) page for the full catalog.

**Report Bugs & Request Features**
Found a bug or have an idea? Open an issue on [GitHub](https://github.com/AllStreets/NEXUS/issues). Include steps to reproduce, expected vs. actual behavior, and your Python version.

**Improve Documentation**
The docs site lives in `site/src/content/docs/`. Every page is markdown. Fix a typo, clarify a concept, add an example -- all welcome.

---

### Module Ecosystem

The community module system is built on three components that handle the full lifecycle from submission to installation.

| Component | What it Does |
|-----------|-------------|
| **Validator** | Checks module structure, manifest schema, file layout, and kernel import restrictions before installation. Rejects modules that import kernel internals directly. |
| **Registry** | JSON-backed module catalog with search by name, author, description, and keywords. Rebuilt automatically on merge. |
| **Installer** | Installs and uninstalls community modules. Automatically registers routing keywords in Cortex so your module is immediately routable. |

Community modules live in `community/modules/<author>/<name>/` with a standard layout:

```
community/modules/yourname/my_agent/
├── manifest.json       # name, author, version, description, keywords
├── my_agent.py         # NexusModule subclass
├── tests/
│   └── test_my_agent.py
└── README.md
```

**Install a community module:**
```bash
nexus install yourname/my_agent
```

**Uninstall:**
```bash
nexus uninstall my_agent
```

**Browse available modules:**
```bash
nexus community list
nexus community search "code review"
```

---

### Contribution Standards

All community modules must meet these requirements before merge:

| Requirement | Details |
|-------------|---------|
| **Base class** | Extend `NexusModule` from `nexus.modules.base` |
| **Attributes** | Include `name`, `description`, `version` class attributes |
| **Handler** | Implement `async def handle(self, message: str, context: dict) -> str` |
| **Validation** | Pass `ModuleValidator` checks -- no kernel imports, correct manifest schema |
| **Tests** | Include tests with >80% coverage. Use `pytest` and `pytest-asyncio`. |
| **Attribution** | Credit open source inspirations in module docstring with project name and license |
| **License** | Use an OSI-approved license. Apache 2.0 and MIT preferred. |

**What gets rejected:**

- Modules that import kernel internals (`nexus.kernel.*`) directly
- Missing or malformed `manifest.json`
- No tests, or tests that require a running LLM
- Network access without `requires_network = True`
- Modules that modify global state outside their own scope

---

### Architecture for Contributors

Understanding how your module fits into the system:

```
  User message
       |
  Cortex (keyword routing)
       |
  Aegis (trust check)
       |
  Your Module.handle(message, context)
       |
  context["llm"]        -->  LLM inference (optional)
  context["engram"]     -->  Memory storage & retrieval
  context["chronicle"]  -->  Audit logging
  context["pulse"]      -->  Event bus (subscribe/publish)
```

Your module receives a `message` string and a `context` dictionary. The context provides access to all kernel services. Your module returns a string response. That's it.

**Key rules:**
- Modules don't know about each other. They communicate through `Pulse` events.
- Modules don't import kernel classes directly. They use the `context` dictionary.
- Modules are stateless across requests unless they store to `Engram`.
- Every action is logged to `Chronicle` automatically by the kernel.

---

### Open Source Credits

NEXUS agents credit the open source projects that inspired them. Every agent module includes attribution in its docstring with the project name and license. Here are some of the projects that informed the agent designs:

| Domain | Inspirations |
|--------|-------------|
| Code security | semgrep (LGPL 2.1), bandit (Apache 2.0), Snyk CLI (Apache 2.0) |
| Code review | reviewdog (MIT), danger-js (MIT), CodeClimate (MIT) |
| NLP & text | sumy (Apache 2.0), spaCy (MIT), WriteFreely (AGPL 3.0) |
| Data & SQL | sqlcoder (Apache 2.0), Spider benchmark (CC BY-SA 4.0) |
| Finance | ledger-cli (BSD 3-Clause), hledger (GPL 3.0) |
| Compliance | OWASP checklists (CC BY-SA 4.0), CIS Benchmarks |
| Pipelines | Apache Airflow (Apache 2.0), Luigi (Apache 2.0), Prefect (Apache 2.0) |
| Testing | Pynguin (LGPL 3.0), Hypothesis (MPL 2.0) |
| Web scraping | Scrapy (BSD 3-Clause), Crawl4AI (Apache 2.0) |

Full attribution is in each module's source file docstring.

---

### License

NEXUS core is Apache 2.0. Community modules must use OSI-approved licenses. The core will always be open.
