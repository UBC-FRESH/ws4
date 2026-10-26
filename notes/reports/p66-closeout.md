# Phase close-out report: P66 Assistant panel visibility

Phase: P66, Assistant panel visibility
Parent issue: #473
Pull request: #476
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P66 pull request and delete `feature/p66-assistant-visibility`.
2. Close task #474 and parent #473.
3. Deploy `v74` to the live services.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Disabled service uses zero vertical assistant space. | c5 without `--allow-agent`: panel and splitter hidden, panel height 0. | Met |
| Enabled service keeps the assistant. | TSA 46 with `--allow-agent`: panel and splitter visible. | Met |
| Sidebar uses recovered height. | c5 sidebar body enlarges when the panel is hidden. | Met |
| No overflow or console errors. | Browser check exits 0; map remains visible. | Met |
| Dashboard green. | Green at the report commit. | Met |

## What changed

- The assistant panel and splitter are hidden by default in the shell.
- `/api/agent` controls visibility: show only when `enabled` and `available`.
- Disabled, unavailable, and failed agent checks hide the panel.
- Enabled and available services keep the existing resizable panel.
- Version bumped to `v74`.

## Evidence

`scripts/check_assistant_visibility.py`:

- c5 expected hidden: panel hidden, splitter hidden, panel height 0.
- TSA 46 expected visible: panel visible, splitter visible, panel height 240 px.

No service permissions changed. A service launched without `--allow-agent` still cannot enable
the assistant from the browser.

## Limits

- No collapsed "enable assistant" affordance; enabling requires restarting with `--allow-agent`.
- If `--allow-agent` is set but `opencode` is missing, the panel is hidden and the shell remains usable.
