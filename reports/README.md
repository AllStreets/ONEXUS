# Daily briefings

ONEXUS emits a kernel briefing once per UTC day, modeled on the AllStreets
daily-report convention shared by **AllStreets/ONEXUS-Agents** (nightly
catalog report) and **AllStreets/SMADP** (5-minute autopilot report). One
file per day, named `YYYY-MM-DD.md`.

## What's in it

| Section | What it shows |
|---|---|
| **Totals** | Workspace count, catalog totals (agents · runnable · built-in modules), with `(+N)` / `(—)` delta from yesterday's report |
| **Activity today (UTC)** | Chronicle events grouped by `source · action`, sorted by frequency |
| **Trust changes today** | Top trust score moves (largest absolute delta first), with reason |
| **Permission events today** | Aegis: total allowed / denied / auto-grant counts |
| **Pipeline health** | Where the kernel DB and catalog live; static-network confirmation |
| **Footer** | ISO-8601 generation timestamp |

No frontmatter, no badges, no emojis — just plain GitHub-flavored Markdown.

## How it's generated

```bash
onexus briefing daily             # write today's briefing to reports/
onexus briefing daily --dry       # print to stdout, don't write
python -m nexus.briefings.daily   # equivalent direct invocation
```

The generator reads directly from the kernel SQLite DB
(`~/.local/share/nexus/nexus.db`) and the agent catalog on disk — it does
not require the API server to be running.

## Schedule

A GitHub Actions workflow at `.github/workflows/daily-briefing.yml` runs
the generator at 13:00 UTC daily (≈ 08:00 EST / 09:00 EDT) and commits the
new report alongside whatever other automation runs the same day. Match the
ONEXUS-Agents cadence so the family of repos all publish their reports in
the same window.

## Deltas vs. yesterday

The generator opens yesterday's report (if it exists), parses the bold
`**N**` totals, and writes the difference in parentheses next to each
metric. First-ever report shows `(first report)`.
