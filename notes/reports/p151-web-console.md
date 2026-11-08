# P151 Web UI power-user console

Date: 2026-11-08
Status: active
Branch: `feature/p151-web-console`
Parent issue: #789
Task issue: #790

The roadmap uses P151 for this work because P127 already names the target-chart and
Solve-semantics phase. The product request and issues are still the P127 console tasks.

## Summary

The web UI now has an opt-in, token-authenticated **Console** workspace for allowlisted
WS4 commands. It is a typed composer, not a shell.

- `ws4 simulate`, `ws4 optimize`, `ws4 state-watch`, `ws4 gpu-run`, and `ws4 report`.
- Server-built argv arrays; unknown commands, fields, flags, and invalid values are
  rejected before launch.
- Read-only input roots; output paths and job directories are server-owned.
- One active job, six starts per minute, 180-second wall clock, one-megabyte output cap.
- Process-group cancellation and timeout termination.
- Artifact listing and authenticated downloads.
- Append-only `runs/console-audit.jsonl` records with workspace, argv, dataset
  fingerprint, timestamps, exit status, and artifacts.
- Bearer token required by every console endpoint. The console API is absent unless
  `--allow-console` is set with a token.
- Browser panel with token entry, command picker, typed fields, live output, cancel, and
  artifact downloads.

## Security boundary

The child process is started with `shell=False`, a cleaned environment, a scratch working
directory, and `start_new_session=True`. No field reaches a shell. Input paths resolve
with `strict=True` and must remain under configured roots. The token is an access gate,
not a multi-user account system; operators must still provide host authentication and
network controls.

The allowlisted CLI tier does not provide a kernel sandbox or network namespace. The
sandboxed Python API runner and assistant-script review flow remain P127.2 and P127.3.

## Verification

- `tests/test_web_console.py`: 11 passed, covering auth, disabled mode, unknown commands
  and fields, traversal, shell-shaped paths, report execution, audit, artifact download,
  timeout, cancellation, output flooding, concurrency, and rate limiting.
- Browser smoke: token connect, `report` run, `Report written` output, 7 artifacts, and
  no page errors.
- Dashboard: `OVERALL: GREEN`.
