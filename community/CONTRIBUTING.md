# Contributing a Module to NEXUS

## Requirements

Your module submission must include:

```
community/modules/<your-github-username>/<module_name>/
├── module.py          # NexusModule subclass
├── manifest.json      # Module metadata
├── tests/
│   └── test_module.py # Minimum 4 tests
└── README.md          # Usage documentation
```

## manifest.json

```json
{
  "name": "your_module",
  "author": "your_github_username",
  "description": "One sentence describing what this module does (10-200 chars).",
  "version": "1.0.0",
  "tier": "community",
  "keywords": ["routing", "keywords", "for", "cortex"],
  "license": "Apache-2.0"
}
```

All fields are required. `tier` must be `"community"`.

## Module Rules

1. Your module must subclass `NexusModule` from `nexus.modules.base`
2. You must define `name`, `description`, and `version` class attributes
3. You must implement `async def handle(self, message: str, context: dict) -> str`
4. **Do NOT import from `nexus.kernel.*`** — use the `context` dict for all kernel access
5. License must be OSI-approved

## Submitting

1. Fork the NEXUS repository
2. Add your module to `community/modules/<your-username>/<module_name>/`
3. Open a PR against `main`
4. CI will validate your submission automatically
5. A maintainer will review and merge

## What CI Checks

- manifest.json conforms to the schema
- module.py subclasses NexusModule with required attributes
- Tests exist and pass
- No imports from nexus.kernel.*
- License is OSI-approved
