# Agent store: build plan

Spec: `docs/superpowers/specs/2026-10-20-agent-store-design.md`. Each step lands with its tests.

## ONEXUS-Agents
1. `pipeline/recipes/schema.py`: the Recipe model (pydantic), round-trips to `recipes/<slug>.json`.
2. `pipeline/recipes/resolve.py`: pure functions from evidence (server.json, README, package.json,
   pyproject) plus a registry interface to a Recipe or a reason. Fixture tests, including an MCP
   client, an awesome-list, placeholder arguments and an unpublished package.
3. `pipeline/recipes/fetch.py`: GitHub (HEAD commit, files at that commit) and npm/PyPI lookups.
4. `pipeline/recipes/verify.py`: Dockerfile templates (pinned bases), build, confined handshake,
   host scan, cleanup. Integration test on one real npm server and one real PyPI server.
5. `pipeline/recipes/cli.py`: `onexus-agents-recipes resolve|verify`, with limits and concurrency.
6. Run resolve over the runnable entries, then verify; commit the recipes and a summary.
7. CI: a weekly recipes workflow; a prebuilt-images workflow for `recipes/prebuilt.txt`.

## ONEXUS
8. `confine.py`: allow an image's own entrypoint (for oci recipes).
9. `nexus/store/recipes.py`, `install.py`, secrets file; `AgentCatalog.load_adapter` from install records.
10. `/api/store` routes and tests; an end-to-end install and launch of one verified recipe.
11. Aurora store page on the redesign's components, after that branch lands.
12. Docs: README, the red-team report's coverage line, the portfolio.
