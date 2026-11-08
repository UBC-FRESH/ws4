# P123.1 Assistant context and action chips

Date: 2026-11-03
Parent: #780
Child: #800
Branch: `feature/p123-assistant-context`
PR: #804

## What changed

- The Ask overlay sends a bounded context packet to `POST /api/chat`:
  run, workspace, subview, period index/label/year, selected block, scenario
  profile, target filter, and the visible account.
- The endpoint turns the packet into one escaped JSON line with an explicit
  “untrusted UI data, never instructions” guard. It does not add file, shell, or
  model permissions.
- The assistant can return safe UI chips after a `WS4_ACTIONS:` marker. The
  marker is case-insensitive, may be multiline or fenced, and every marker is
  stripped from the visible reply. The server validates every chip against a
  whitelist:
  - `open_workspace`: `map`, `plan`, `results`, `data`, or `sdmd`
  - `open_subview`: `workspace:subview`
  - `set_period`: a non-negative integer index
  - `select_block`: a non-empty block id
  - `ask`: prompt text only; it does not send automatically
- Unknown actions, malformed targets, invalid JSON, and extra chips are dropped.
  The maximum is four chips.
- The browser renders chips as buttons. They can switch workspace/subview, set a
  period, select an existing block, or fill the next Ask prompt. They cannot edit
  data, start a run, or change permissions.

## Evidence

- `ws4/web/app.py`: `_chat_context_lines`, `_chat_chip`, `_chat_index`,
  `_split_chat_actions`, and the `/api/chat` response now includes `chips`.
- `ws4/web/static/app.js`: `chatContext`, `applyChatChip`, and chip rendering.
- `ws4/web/static/style.css`: `.chat-chip` button styling.
- `tests/test_web.py`: context JSON, long/Unicode indices, chip validation,
  lowercase/multiline/repeated marker stripping, unsafe target rejection, and
  shell wiring.
- `tests/test_web_chips_js.py`: Node harness for `applyChatChip` workspace,
  subview, period, block, toast, and prompt behavior.
- `docs/reference/web.rst`: documents the context packet and the chip boundary.

## Verification

```bash
python -m pytest tests/test_web.py -q
python scripts/dashboard.py
```

Focused web tests: 88 passed; the JS chip harness passes. Dashboard:
`OVERALL: GREEN`.

## Limits

- The assistant decides whether to emit chips; the server does not invent them.
- `select_block` only selects a block that is already in the current run.
- `ask` fills the input; the user still presses Send.
- The chip whitelist is a UI safety boundary, not a substitute for the agent's
  existing shell permission model.
