---
title: "Routing Keywords"
description: "Cortex keyword routing table — how messages are dispatched to modules."
sidebar:
  order: 0
---

## Routing Table

Cortex uses keyword matching to route each message to the best-fit module.
The module with the highest keyword hit score receives the request.

| Module | Keywords |
|--------|----------|
| `oracle` | `trigger`, `alert`, `monitor`, `scan`, `anticipat`, `pattern` |
| `sentry` | `cognitive`, `focus`, `fatigue`, `stress`, `flow`, `state`, `energy`, `tired` |
| `atlas` | `fact`, `know about`, `world model`, `knowledge`, `who is`, `what is` |
| `prism` | `synthesize`, `connection`, `cross-domain`, `insight`, `relate` |
| `cipher` | `trust`, `source`, `provenance`, `conflict`, `verify`, `credib` |
| `wraith` | `phantom`, `spawn`, `agent`, `swarm`, `research task` |
| `echo` | `behavioral`, `fingerprint`, `style`, `voice`, `profile`, `writing` |
| `sigil` | `threat`, `danger`, `security`, `breach`, `risk`, `radar` |
| `herald` | `external agent`, `a2a`, `communicate`, `connected agent` |
| `weave` | `contact`, `network`, `relationship`, `social graph`, `reconnect` |
| `specter` | `red team`, `adversarial`, `counter-argument`, `devil's advocate`, `risk analysis` |
| `chronos` | `timeline`, `future`, `branch`, `counterfactual`, `what if`, `temporal` |
| `dreamweaver` | `morning brief`, `overnight`, `synthesis`, `sleep`, `idle`, `pattern` |
| `serendipity` | `surprising`, `unexpected`, `serendip`, `random`, `adjacent`, `diverse` |
| `forge` | `negotiat`, `bargain`, `offer`, `counter-offer`, `concession`, `deal` |
| `collective` | `federated`, `peer`, `distributed`, `swarm learning`, `model sharing` |
| `legacy` | `crystallize`, `distill`, `framework`, `playbook`, `wisdom`, `pattern extract` |
