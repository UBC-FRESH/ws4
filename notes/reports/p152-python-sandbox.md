# P152 Sandboxed Python runner

Date: 2026-11-08
Status: complete
Branch: `feature/p152-python-sandbox`
Parent issue: #901
Task issue: #902
Merge commit: `345a86d`

## Summary

The console now has a second tier for explicitly reviewed WS4 Python API scripts. The
worker applies Landlock filesystem and TCP policy, runs inside a new user/PID/network
namespace through `unshare`, sets resource limits, and then execs the reviewed script.

Allowed reads:

- the mounted dataset;
- selected input files or directories inside configured read-only roots;
- the Python runtime and installed WS4 package;
- the job scratch directory.

Allowed writes:

- the job scratch directory only.

Denied:

- host files such as `/etc/passwd`;
- the instance tree and other run directories;
- network access;
- inherited console tokens and host credentials;
- package installation and interactive terminals.

The API rejects a script unless `reviewed: true` is present. The browser requires a
visible **I reviewed this script** checkbox. If Landlock or a functional unshare probe is
unavailable, the job is refused; there is no unsandboxed fallback.

## Limits

- 180 seconds wall clock and CPU ceiling;
- 2 GB address space;
- 64 MB per file;
- 64 processes;
- 256 open files;
- one active job, six starts per minute;
- one-megabyte captured output.

## Verification

- `tests/test_web_console.py`: 14 passed, including sandbox host-read, input-write,
  other-run read, network, and inherited-token checks, plus selected run-directory input.
- Browser smoke: reviewed script wrote `hello.txt` and printed `sandbox-ok`.
- Portal smoke with `WS4_CONSOLE_TOKEN` and `WS4_CONSOLE_PYTHON=1`: summary reported
  `console: true` and `console_python: true`; a reviewed script printed
  `portal-sandbox-ok`. The live portal without those variables reports both capabilities
  false and has no console API.
- Dashboard: `OVERALL: GREEN`.
