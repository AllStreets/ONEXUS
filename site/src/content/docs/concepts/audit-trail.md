---
title: Audit Trail
description: Chronicle's append-only audit log — what it records, how it works, and compliance implications.
sidebar:
  order: 3
---

## What Chronicle Records

Chronicle logs every event that passes through the kernel. Nothing is excluded.

| Event Type | What Is Recorded |
|------------|-----------------|
| Inbound message | Timestamp, source, content, SHA-256 hash |
| Routing decision | Target module, keyword match, Cortex decision |
| Permission check | Module name, trust score at time of check, pass/fail |
| Module response | Source module, content, response time |
| Trust score change | Module name, previous score, new score, reason |
| Pulse event | Topic, publisher, subscriber list |
| Memory operation | Tier (working/episodic/semantic), operation type |
| Session start/end | Timestamp, active modules at session open |

This is not sampling — every event is logged.

## Append-Only Design

Chronicle uses SQLite in WAL (Write-Ahead Log) mode. The schema has no UPDATE or DELETE statements. Records can only be inserted.

Each record includes a `prev_hash` field: the SHA-256 hash of the previous record. This creates a hash chain — any modification to a historical record invalidates all subsequent hashes, making tampering detectable.

The chain is verifiable:

```bash
nexus chronicle verify
# All 4,821 records: chain intact
```

If verification fails, Chronicle reports the first broken link with the timestamp and record ID of the tampered entry.

## Querying the Audit Log

Chronicle is queryable through the module context:

```python
# From a module
records = await context["chronicle"].query(
    module="atlas",
    event_type="response",
    since="2025-01-01",
    limit=50,
)

# Filter by trust changes
changes = await context["chronicle"].query(
    event_type="trust_change",
    module="specter",
)
```

## Compliance

The append-only, hash-chained design satisfies the evidence requirements for several compliance frameworks:

**SOC 2 Type II** — Logical access controls require evidence that access was logged and that logs were not modified. Chronicle's hash chain and WAL mode provide this evidence.

**HIPAA Audit Controls (§ 164.312(b))** — Requires audit controls that record and examine activity in systems containing protected health information. Chronicle logs all access with timestamps and module attribution.

**GDPR Article 17 (Right to Erasure)** — When user data is deleted from Engram, Chronicle retains the deletion event: timestamp, what category of data was deleted, and the initiating command. The personal data is gone; the fact that it existed and was deleted is preserved. This satisfies the accountability requirement without retaining the data itself.

## Retention

Chronicle does not have a built-in retention policy — by default it retains everything. To manage size:

- Archive older records by copying `chronicle.db` and truncating the live database (the chain remains valid for the archive)
- Set `NEXUS_LOG_LEVEL=WARNING` to reduce the volume of low-priority events logged

Chronicle's database typically grows at 1–5 MB per day of active use, depending on message volume.
