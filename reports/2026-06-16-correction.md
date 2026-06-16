# Correction & status — 2026-06-16

A one-time explainer covering what drifted off track and what is now repaired,
written alongside the SMADP and ONEXUS-Agents corrections of the same date.

## What went off track

NEXUS fared better than its siblings, but a few threads were left loose:

- **The nightly catalog image rebuild failed on 2026-06-09 and 06-10.** The
  GHCR tag was built from an un-lowercased `GITHUB_REPOSITORY`, which the
  registry rejects, so the nightly `onexus` image did not refresh on those days.
- **The elevation work sat on an unpushed branch.** The "Missing Minds" build
  (N1 Sigil/Atlas/live kernel viz, N2 Prism/Chronos/Dreamweaver, N3 Herald
  negotiation/federation/Serendipity/Aurora v3) and the operator's Aurora UX
  feedback list were complete locally but not yet on `main`.
- **Outstanding Aurora UX feedback.** Markdown did not render in agent
  responses; a dispatched agent could error out in zero seconds with no useful
  state; there was no true token streaming; no access to local codebase roots;
  and the UI could imply capabilities it did not have.
- **No in-app way to restart Ollama.** When the operator quit Ollama, the
  local-inference slot went dead with no way to recover without leaving the app.

## What is now on track

- **Nightly catalog is fixed and green.** The tag is now lowercased; the
  nightly image has rebuilt successfully every night since 2026-06-11.
- **Elevation is merged to `main`.** 1,338 tests pass; the kernel invariant
  (only Aegis touches the network) holds. The Aurora feedback branch landed
  alongside it: markdown rendering, honest dispatch error states, real
  streaming, local codebase roots, and truthful capability grounding.
- **Ollama can be restarted from the app.** `POST /api/providers/ollama/restart`
  locates the binary across the common install prefixes, terminates any running
  `ollama serve`, and spawns a fresh detached one; Aurora's Settings → Providers
  panel now has a "Restart Ollama" button wired to it. Covered by tests.
- **The live laptop app already reflects all of this** — it runs from an
  editable install, so the file-watcher reloaded the new routes and UI without a
  manual reinstall. Dependabot is clean (0 open).

## What to watch

- To refresh the local agent catalog view, `git pull` the sibling
  `ONEXUS-Agents` clone and restart the server (the catalog loads once at
  startup).
- Manifest-v1 modules remain at ADVISOR trust (0.30) until earned upward; that
  gate is intentional, not a regression.
