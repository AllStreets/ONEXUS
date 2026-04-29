---
title: "Community Hub"
description: "Join the NEXUS community — contribute modules, share agents, and collaborate"
sidebar:
  order: 1
---

## Community Hub

NEXUS is built by and for its community. Every module in the system is open source, auditable, and runs on your hardware.

### Contribute

**Build a Module**
Write a NexusModule subclass, add tests, submit a PR. Your module ships to every NEXUS user. See the [Building a Module](/NEXUS/guides/building-a-module/) guide.

**Submit an Agent**
Narrow AI agents solve focused problems — meeting summaries, code review, invoice generation, vulnerability scanning. If you have a use case that NEXUS doesn't cover, build an agent and contribute it.

**Report Issues**
Found a bug or have a feature request? Open an issue on [GitHub](https://github.com/AllStreets/NEXUS/issues).

### Module Ecosystem

The community module system uses three components:

| Component | Purpose |
|-----------|---------|
| **Validator** | Checks module structure, manifest schema, and import restrictions before install |
| **Registry** | JSON-backed catalog with search by name, author, description, and keywords |
| **Installer** | Installs/uninstalls modules, registers routing keywords in Cortex automatically |

### Standards

All community modules must:

- Extend `NexusModule` base class
- Include `name`, `description`, `version` attributes
- Implement `async def handle(self, message, context) -> str`
- Pass validation checks (no kernel imports, correct manifest)
- Include tests with >80% coverage
- Credit open source inspirations in module docstring

### License

NEXUS core is open source. Community modules must use OSI-approved licenses. Attribution for open source inspirations is required in module docstrings.
