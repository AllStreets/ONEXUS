---
title: "Use Cases"
description: "Real-world problems NEXUS agents solve -- pick your scenario, find the right agent"
sidebar:
  order: 3
---

## Use Cases

You don't need to understand the architecture to use NEXUS. Find your problem, find the agent.

---

### Security & Code Quality

**"I need to check my codebase for vulnerabilities before shipping."**

Use **Vex**. Point it at a file or directory and it scans for 28 vulnerability patterns -- SQL injection, XSS, hardcoded credentials, insecure deserialization, path traversal. No LLM required. Works on any Python, JavaScript, or config file.

```
> scan this code for vulnerabilities
[vex] 3 issues found in src/api/auth.py
  HIGH   Hardcoded credential on line 14
  MEDIUM SQL injection risk on line 47 (string concatenation in query)
  LOW    Missing input validation on line 23
```

**"I want a second opinion on my code before I merge."**

Use **Arbiter**. It reviews diffs and source files for quality issues, style violations, and anti-patterns. Checks cyclomatic complexity, function length, naming conventions, and common mistakes.

**"Our API endpoints might have security holes."**

Use **Bastion**. Feed it your OpenAPI spec or endpoint descriptions and it checks for BOLA (broken object-level authorization), missing authentication, mass assignment vulnerabilities, and other OWASP API Security Top 10 risks.

---

### Financial & Business

**"I have a CSV of bank transactions and want to understand my spending."**

Use **Ledger**. It parses bank statements, categorizes transactions into spending categories (food, transport, subscriptions, etc.), generates summaries, and flags anomalies like duplicate charges or unusual amounts.

```
> categorize these transactions
[ledger] 47 transactions categorized
  Food & Dining      $842.30  (28%)
  Transportation     $234.50  (8%)
  Subscriptions      $189.99  (6%)
  ANOMALY: Duplicate charge $49.99 on Mar 12 and Mar 13
```

**"I need to generate an invoice for a client."**

Use **Mint**. Give it line items and client info, it calculates tax by region, formats the invoice, and outputs it. Handles US sales tax, EU VAT, Australian GST, and Canadian HST.

**"I'm reviewing a contract and want to know what's risky."**

Use **Redline**. It scans agreements for 15 risky clause patterns -- unlimited liability, unilateral termination, automatic renewal, non-compete overreach, IP assignment, and missing protections like limitation of liability or data handling clauses.

**"I need financial projections for my startup pitch."**

Use **Tally**. Feed it your revenue assumptions and it builds best/base/worst case projections with monthly burn rate, runway calculation, and break-even analysis.

**"Do we comply with GDPR / SOC2 / HIPAA?"**

Use **Mandate**. Describe your current practices and it runs a gap analysis against the framework's control requirements, categorizing each as met, partial, or missing.

---

### Data & Analysis

**"I have a question about my data but don't know SQL."**

Use **Flux**. Describe your tables and ask a question in plain English. It generates the SQL query with complexity scoring. Requires LLM for the natural language to SQL conversion.

```
> which customers spent more than $1000 last month?
[flux] Generated SQL (complexity: moderate)
  SELECT customer_name, SUM(amount) as total
  FROM orders
  WHERE order_date >= '2026-03-01'
  GROUP BY customer_name
  HAVING SUM(amount) > 1000
  ORDER BY total DESC;
```

**"My server logs are a mess and I need to find what went wrong."**

Use **Vigil**. It parses common log formats (ISO timestamp, syslog, bracketed level), detects anomaly patterns like error spikes, and generates incident timelines showing what happened and when.

**"I need to extract structured data from a web page."**

Use **Quarry**. Give it HTML content and it extracts links, headings, tables, and metadata into structured output. No browser needed -- it works directly on HTML.

**"Our API response times are getting worse and I don't know why."**

Use **Gauge**. Feed it performance metrics (latency, CPU, memory, throughput) and it identifies bottlenecks, flags values above warning/critical thresholds, and compares before/after snapshots.

---

### Content & Communication

**"I had a long meeting and need to share the key points."**

Use **Scribe**. Paste the transcript and it extracts participants, action items, decisions, and key topics into a structured summary.

**"I have bullet points and need them turned into a real document."**

Use **Kindle**. It expands bullet points into polished prose -- blog posts, documentation, reports, or emails. Detects tone (professional, technical, casual, academic, marketing) and format automatically.

**"I need to evaluate a research paper for my literature review."**

Use **Thesis**. It extracts claims, methodology, limitations, and research gaps from academic papers. Useful for literature surveys or quickly assessing whether a paper is relevant.

**"I want to learn Rust but don't know where to start."**

Use **Compass**. Tell it your current experience level and target language, and it generates a personalized learning roadmap with phases, resources, and milestones.

---

### Development Workflow

**"My code is getting hard to maintain -- where should I refactor?"**

Use **Carve**. It measures complexity metrics, finds functions over 30 lines, detects deep nesting (4+ levels), identifies duplicate string literals, and flags chained elif blocks.

**"I have an error and don't understand the stack trace."**

Use **Remedy**. Paste the error message or stack trace and it identifies the error type, explains what went wrong, and suggests fixes for 17 common error patterns.

**"I need to write tests but don't know where to start."**

Use **Axiom**. Point it at a function and it generates test case stubs -- happy path, edge cases (empty input, None, boundary values), and error cases based on type hints.

**"I need a regex but I can never remember the syntax."**

Use **Rune**. Describe what you want to match in plain English and it builds the pattern, explains each part, and tests it against sample strings. Also explains existing regex patterns.

**"I need a new Python project with the right structure."**

Use **Scaffold**. Tell it what kind of project (Python library, FastAPI app, CLI tool) and it generates the boilerplate with the right directory layout, config files, and entry points.

---

### Infrastructure & Ops

**"I need to send alerts to different channels based on severity."**

Use **Dispatch**. Configure routing rules and it sends notifications to email, Slack, webhooks, or SMS based on priority. Critical alerts go everywhere, low-priority alerts go to a log channel.

**"I need to monitor my cron jobs."**

Use **Sentinel**. Register your scheduled tasks and it tracks execution, explains cron expressions in plain English, and detects missed runs.

**"I want a personal knowledge base I can search."**

Use **Mnemonic**. Store notes with auto-tagging, then search by keyword. It indexes everything locally and retrieves by relevance with title weighting.

**"I need to define an ETL pipeline with proper ordering."**

Use **Loom**. Describe your pipeline steps and dependencies, and it resolves the execution order using topological sorting. Detects circular dependencies and generates a visual DAG.
