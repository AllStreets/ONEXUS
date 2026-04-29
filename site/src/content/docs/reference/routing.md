---
title: "Routing Keywords"
description: "Cortex keyword routing table — how messages are dispatched to all 51 modules."
sidebar:
  order: 0
---

## Overview

Cortex uses keyword matching to route each message to the best-fit module. When a user sends a message, Cortex scores it against every module's keyword list. The module with the highest keyword hit count receives the request.

If no keywords match, the message falls through to the **general** module.

## Routing Table

### Kernel-Adjacent

| Module | Keywords |
|--------|----------|
| **general** | Catch-all fallback -- receives messages that match no other module |

### Perception

| Module | Keywords |
|--------|----------|
| **oracle** | trigger, alert, monitor, scan, anticipat, pattern |
| **sentry** | cognitive, focus, fatigue, stress, flow, state, energy, tired |

### Intelligence

| Module | Keywords |
|--------|----------|
| **atlas** | fact, know about, world model, knowledge, who is, what is |
| **prism** | synthesize, connection, cross-domain, insight, relate |
| **cipher** | trust, source, provenance, conflict, verify, credib |

### Action

| Module | Keywords |
|--------|----------|
| **wraith** | phantom, spawn, agent, swarm, research task |
| **echo** | behavioral, fingerprint, style, voice, profile, writing |
| **sigil** | threat, danger, security, breach, risk, radar |
| **herald** | external agent, a2a, communicate, connected agent |
| **weave** | contact, network, relationship, social graph, reconnect |

### Advanced Intelligence

| Module | Keywords |
|--------|----------|
| **specter** | counter-argument, devil's advocate, risk analysis, stress test this decision |
| **serendipity** | surprising, unexpected, serendip, random, adjacent, diverse |
| **forge** | negotiat, bargain, offer, counter-offer, concession, deal |

### Orchestration

| Module | Keywords |
|--------|----------|
| **council** | deliberate, debate, council, perspectives, weigh, consider, should i, decide, pros and cons, think through, advise |
| **autonomic** | automate, routine, autopilot, autonomous, on my behalf, handle it, take care of, manage for me, do it for me, autonomic, trust status, domain trust |

### Network

| Module | Keywords |
|--------|----------|
| **collective** | federated, peer, distributed, swarm learning, model sharing |
| **legacy** | crystallize, distill, framework, playbook, wisdom, pattern extract |

### Differentiation

| Module | Keywords |
|--------|----------|
| **dream_loop** | dream, dreams, insights, idle, background, patterns while idle |
| **adversarial** | stress test, red team, self improve, vulnerability, harden |
| **tripwire** | my patterns, decision history, contradictions, tripwire, mirror |
| **provenance** | why do you think, reasoning, show reasoning, provenance, trace, how did you |
| **sandbox** | what if, simulate, hypothetical, sandbox, fork, test scenario |
| **symbiosis** | neural pathways, module connections, routing map, symbiosis |
| **consciousness** | how are you, journal, self reflect, introspect, consciousness, emergent goals, unintended behavior, what are you doing, implicit goals |
| **ethical_prism** | ethically, ethical, moral, ethics, right thing, should i morally |

### Agents -- Code & Development

| Module | Keywords |
|--------|----------|
| **vex** | vulnerability, security scan, owasp, exploit, code security, sast |
| **arbiter** | code review, review this, pull request, diff, review code, pr review |
| **carve** | refactor, complexity, extract function, code smell, nesting, simplify code |
| **remedy** | error, traceback, stack trace, exception, debug, diagnose |
| **scaffold** | scaffold, boilerplate, project template, generate project, new project, starter |
| **axiom** | test case, generate tests, unit test, test stub, edge case, test for |
| **rune** | regex, regular expression, pattern match, regexp, pattern for, match string |

### Agents -- Data & Analysis

| Module | Keywords |
|--------|----------|
| **flux** | sql, query, database, table schema, select from, natural language sql |
| **vigil** | log analysis, logs, anomaly, incident, root cause, log file, timeline |
| **gauge** | performance, latency, throughput, benchmark, bottleneck, response time, metrics |
| **quarry** | scrape, extract data, html, web page, crawl, parse html, web content |
| **loom** | pipeline, etl, data flow, workflow, extract transform, data pipeline |

### Agents -- Business & Finance

| Module | Keywords |
|--------|----------|
| **ledger** | transaction, bank statement, spending, budget, categorize, financial |
| **tally** | projection, runway, forecast, revenue model, burn rate, financial model |
| **mint** | invoice, receipt, billing, line items, generate invoice, bill to |
| **redline** | contract, legal, agreement, clause, terms, nda, liability |
| **mandate** | compliance, gdpr, soc2, hipaa, audit, regulatory, gap analysis |

### Agents -- Content & Communication

| Module | Keywords |
|--------|----------|
| **scribe** | meeting, transcript, minutes, action items, summarize meeting, notes |
| **kindle** | expand, blog post, polish, content, write up, draft, outline to prose |
| **thesis** | paper, literature, academic, research paper, abstract, citation |
| **compass** | learn, roadmap, study plan, curriculum, learning path, teach me |

### Agents -- Infrastructure & Ops

| Module | Keywords |
|--------|----------|
| **bastion** | api security, endpoint, openapi, swagger, api scan, rest api, api audit |
| **dispatch** | notify, notification, alert to, send message, slack, email alert, webhook |
| **sentinel** | cron, scheduled task, job monitor, crontab, missed run, task health |
| **mnemonic** | remember, knowledge base, recall, notes, store note, look up, retrieve |
