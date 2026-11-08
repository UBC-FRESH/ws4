# P153 Assistant script review handoff

Date: 2026-11-08
Status: complete
Branch: `feature/p153-assistant-script-review`
Parent issue: #906
Task issue: #907
Merge commit: `772d45b`

## Summary

The assistant can now end a reply with a `stage_script` chip containing bounded Python
source. The chip is intentionally side-effect free:

- the server validates and returns the source text;
- the browser opens Console and fills the editor;
- the review checkbox is cleared;
- no job API is called until the user ticks the confirmation and selects **Run reviewed
  script**;
- the existing Landlock/unshare runner remains the only execution path.

The chat agent's environment is also scrubbed of `WS4_CONSOLE_TOKEN` and
`WS4_CONSOLE_PYTHON`, so an assistant cannot call the console API on its own.

## Verification

- `tests/test_web.py`: chip validation and `_agent_environment` secret removal pass.
- Assistant-staged code still requires the P152 reviewed-script submission.
- The public portal branch deployed the same chip and environment scrub.
- Dashboard: `OVERALL: GREEN`.
