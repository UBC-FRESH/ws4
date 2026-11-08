"""Apply the Python-job sandbox and exec the collaborator script.

This module is intentionally small and imports only the standard library plus the
sandbox primitives. The public API launches it through ``unshare``; it enforces resource
limits and Landlock before replacing itself with the user's script.
"""

from __future__ import annotations

import argparse
import os
import resource
import sys
from pathlib import Path

from .sandbox import SandboxUnavailableError, apply_filesystem_policy


def _bounded(value: int, name: str) -> int:
    """Return a positive integer limit."""
    if value <= 0:
        raise SystemExit(f"{name} must be positive")
    return int(value)


def main(argv: list[str] | None = None) -> int:
    """Apply limits and policy, then exec the script.

    Parameters
    ----------
    argv : list of str or None, optional
        Command arguments; None uses ``sys.argv``.

    Returns
    -------
    int
        Process exit status. The normal path does not return because it execs the script.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--cpu-seconds", type=int, required=True)
    parser.add_argument("--max-file-bytes", type=int, required=True)
    parser.add_argument("--read-root", action="append", type=Path, default=[])
    args = parser.parse_args(argv)

    script = args.script.resolve()
    scratch = args.scratch.resolve()
    memory = _bounded(args.memory_bytes, "memory")
    cpu_seconds = _bounded(args.cpu_seconds, "cpu")
    max_file = _bounded(args.max_file_bytes, "max-file-bytes")
    if script != scratch and scratch not in script.parents:
        raise SystemExit("script is outside the job scratch directory")
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "home").mkdir(exist_ok=True)
    (scratch / "tmp").mkdir(exist_ok=True)
    os.umask(0o077)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))
    except (OSError, ValueError) as error:
        raise SystemExit(f"could not set resource limits: {error}") from error

    try:
        apply_filesystem_policy([*args.read_root, script], scratch)
    except SandboxUnavailableError as error:
        print(f"sandbox unavailable: {error}", file=sys.stderr)
        return 126
    os.chdir(scratch)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(scratch / "home"),
        "TMPDIR": str(scratch / "tmp"),
        "XDG_CACHE_HOME": str(scratch / "home" / ".cache"),
        "MPLCONFIGDIR": str(scratch / "home" / ".matplotlib"),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    inherited_path = os.environ.get("PYTHONPATH")
    if inherited_path:
        env["PYTHONPATH"] = inherited_path
    os.execve(sys.executable, [sys.executable, "-B", str(script)], env)


if __name__ == "__main__":
    raise SystemExit(main())
