# Phase close-out report: P123 assistant context and action chips

Phase: P123 Assistant context and action chips
Parent issue: #780
Child issue: #800
Branch: `feature/p123-assistant-context`
PR: #804
Head: `884e466`
Date: 2026-11-04
Status: queued for maintainer approval. Not merged.

## Recommendation

Queue PR #804 for `feature/p123-assistant-context` into `main` and wait for the
maintainer's approval.

After approval:

1. Squash-merge PR #804.
2. Delete `feature/p123-assistant-context`.
3. Close #780 and #800 with a comment that cites the merge commit.
4. Do not launch the next phase until the maintainer names it.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Send the current screen context | `chatContext` sends run, workspace, subview, period, block, profile, filter, and account | met |
| Bound the context prompt | `_chat_context_lines` accepts only known scalar fields | met |
| Parse assistant chips | `_split_chat_actions` reads one `WS4_ACTIONS:` JSON line and strips it | met |
| Validate safe actions | `_chat_chip` whitelists workspace, subview, period, block, and prompt actions | met |
| Render safe chips | `applyChatChip` switches view, sets period, selects an existing block, or fills the prompt | met |
| Preserve permissions | No file, shell, run, or edit capability is added | met |
| Tests | context, validation, unsafe targets, malformed marker, shell wiring | met |
| Dashboard green | `OVERALL: GREEN` at `884e466` | met |

## 2. Workflow compliance

- Parent issue #780 and child #800, linked as a sub-issue.
- Branch `feature/p123-assistant-context`.
- Commit messages start with P123.
- PR #804 is open and queued; it is not merged.
- No tag, release, visibility, or settings change was made.

## 3. Evidence

- `ws4/web/app.py`: context packet, prompt lines, chip validation, marker
  stripping, and the `chips` response field.
- `ws4/web/static/app.js`: `chatContext`, `applyChatChip`, and chip rendering.
- `ws4/web/static/style.css`: `.chat-chip` button styling.
- `tests/test_web.py`: 86 focused tests.
- `docs/reference/web.rst`: assistant context and chip boundary.
- `notes/reports/p123-assistant-context.md`: task evidence.

CI run `41743605008` passed all five checks. The dashboard gate reported
`OVERALL: GREEN`.

## 4. Known limits

- The assistant decides whether to emit chips; the server does not invent them.
- `select_block` only selects a block already present in the current run.
- `ask` fills the input; it does not send automatically.
- The whitelist is a UI safety boundary, not a replacement for the agent's
  existing shell permission model.
- The context packet is bounded display state, not a dataset contract.

## 5. Verification

```bash
python -m pytest tests/test_web.py -q
python scripts/dashboard.py
```

Focused web tests: 86 passed. Dashboard: `OVERALL: GREEN`.

## 6. Pull request

PR #804 names the phase, branch, head, context packet, chip whitelist, tests, and
limits. It is queued for approval. No merge, tag, release, or settings change is
performed by this report.
