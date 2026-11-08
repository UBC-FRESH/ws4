"""Rootless sandbox primitives for collaborator Python jobs.

The sandbox uses two kernel features:

* a new user, PID, and network namespace created by ``unshare``;
* a Landlock filesystem and TCP policy applied by the worker before it execs the script.

Landlock is the authority for file access. The worker allows the Python runtime, the
installed WS4 package, explicitly selected read-only inputs, and the job scratch directory.
Everything else is denied. The network namespace has no external interfaces, and the
Landlock network domain denies TCP bind/connect as a second layer.

If Landlock or ``unshare`` is unavailable, the caller must refuse the job. There is no
unsandboxed fallback for this tier.
"""

from __future__ import annotations

import ctypes
import functools
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

#: Landlock syscall numbers on x86_64.
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446

LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1

ACCESS_FS_EXECUTE = 1 << 0
ACCESS_FS_WRITE_FILE = 1 << 1
ACCESS_FS_READ_FILE = 1 << 2
ACCESS_FS_READ_DIR = 1 << 3
ACCESS_FS_REMOVE_DIR = 1 << 4
ACCESS_FS_REMOVE_FILE = 1 << 5
ACCESS_FS_MAKE_CHAR = 1 << 6
ACCESS_FS_MAKE_DIR = 1 << 7
ACCESS_FS_MAKE_REG = 1 << 8
ACCESS_FS_MAKE_SOCK = 1 << 9
ACCESS_FS_MAKE_FIFO = 1 << 10
ACCESS_FS_MAKE_BLOCK = 1 << 11
ACCESS_FS_MAKE_SYM = 1 << 12
ACCESS_FS_REFER = 1 << 13
ACCESS_FS_TRUNCATE = 1 << 14
ACCESS_FS_IOCTL_DEV = 1 << 15

ACCESS_NET_BIND_TCP = 1 << 0
ACCESS_NET_CONNECT_TCP = 1 << 1

PR_SET_NO_NEW_PRIVS = 38

READ_ACCESS = ACCESS_FS_EXECUTE | ACCESS_FS_READ_FILE
READ_DIR_ACCESS = READ_ACCESS | ACCESS_FS_READ_DIR
WRITE_ACCESS = (
    READ_DIR_ACCESS
    | ACCESS_FS_WRITE_FILE
    | ACCESS_FS_REMOVE_DIR
    | ACCESS_FS_REMOVE_FILE
    | ACCESS_FS_MAKE_DIR
    | ACCESS_FS_MAKE_REG
    | ACCESS_FS_MAKE_SYM
    | ACCESS_FS_MAKE_FIFO
    | ACCESS_FS_TRUNCATE
    | ACCESS_FS_REFER
)


class SandboxUnavailableError(RuntimeError):
    """The host cannot enforce the required sandbox boundary."""


class _RulesetAttr(ctypes.Structure):
    """The Landlock ruleset attribute layout used by ABI 4 and later."""

    _fields_ = (
        ("handled_access_fs", ctypes.c_uint64),
        ("handled_access_net", ctypes.c_uint64),
        ("scoped", ctypes.c_uint64),
    )


class _PathBeneathAttr(ctypes.Structure):
    """One path-beneath rule."""

    _fields_ = (
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
        ("reserved", ctypes.c_uint32),
    )


def _libc() -> ctypes.CDLL:
    """Return libc with the syscall return convention set."""
    library = ctypes.CDLL(None, use_errno=True)
    library.syscall.restype = ctypes.c_long
    return library


def _syscall(library: ctypes.CDLL, number: int, *args: object) -> int:
    """Call one syscall and turn a negative result into ``OSError``."""
    result = int(library.syscall(number, *args))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def landlock_abi() -> int:
    """Return the Landlock ABI version, or zero when it is unavailable.

    Returns
    -------
    int
        The kernel ABI version, or zero when Landlock cannot be queried.
    """
    try:
        library = _libc()
        result = int(
            library.syscall(
                SYS_LANDLOCK_CREATE_RULESET,
                ctypes.c_void_p(0),
                ctypes.c_size_t(0),
                ctypes.c_uint32(LANDLOCK_CREATE_RULESET_VERSION),
            )
        )
    except (AttributeError, OSError, ValueError):
        return 0
    return max(0, result)


def unshare_path() -> str | None:
    """Return the host ``unshare`` executable, when present.

    Returns
    -------
    str or None
        The executable path, or None when it is not installed.
    """
    return shutil.which("unshare")


@functools.lru_cache(maxsize=1)
def sandbox_available() -> bool:
    """Return whether Landlock and an unprivileged namespace probe both work."""
    unshare = unshare_path()
    if landlock_abi() < 1 or unshare is None:
        return False
    try:
        probe = subprocess.run(
            [
                unshare,
                "--user",
                "--map-root-user",
                "--pid",
                "--net",
                "--fork",
                "--kill-child",
                "true",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _handled_fs(abi: int) -> int:
    """Return the filesystem rights this ABI can handle."""
    handled = (
        ACCESS_FS_EXECUTE
        | ACCESS_FS_WRITE_FILE
        | ACCESS_FS_READ_FILE
        | ACCESS_FS_READ_DIR
        | ACCESS_FS_REMOVE_DIR
        | ACCESS_FS_REMOVE_FILE
        | ACCESS_FS_MAKE_CHAR
        | ACCESS_FS_MAKE_DIR
        | ACCESS_FS_MAKE_REG
        | ACCESS_FS_MAKE_SOCK
        | ACCESS_FS_MAKE_FIFO
        | ACCESS_FS_MAKE_BLOCK
        | ACCESS_FS_MAKE_SYM
    )
    if abi >= 2:
        handled |= ACCESS_FS_REFER
    if abi >= 3:
        handled |= ACCESS_FS_TRUNCATE
    if abi >= 5:
        handled |= ACCESS_FS_IOCTL_DEV
    return handled


def _add_rule(
    library: ctypes.CDLL,
    ruleset_fd: int,
    path: Path,
    allowed_access: int,
) -> None:
    """Add one path-beneath rule when the path exists."""
    try:
        resolved = path.resolve()
    except OSError:
        return
    if not resolved.exists():
        return
    try:
        parent_fd = os.open(resolved, os.O_PATH | os.O_CLOEXEC)
    except OSError:
        return
    try:
        attribute = _PathBeneathAttr(
            allowed_access=allowed_access,
            parent_fd=parent_fd,
            reserved=0,
        )
        _syscall(
            library,
            SYS_LANDLOCK_ADD_RULE,
            ctypes.c_int(ruleset_fd),
            ctypes.c_uint32(LANDLOCK_RULE_PATH_BENEATH),
            ctypes.byref(attribute),
            ctypes.c_uint32(0),
        )
    finally:
        os.close(parent_fd)


def _runtime_paths() -> list[Path]:
    """Return interpreter and package paths the script must be able to read."""
    paths = [
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(sys.executable),
        Path(sys.executable).resolve().parent,
        Path(__file__).resolve().parents[2],
    ]
    for value in ("/usr", "/lib", "/lib64", "/etc/ld.so.cache", "/etc/localtime"):
        candidate = Path(value)
        if candidate.exists():
            paths.append(candidate)
    return paths


def _device_paths() -> list[Path]:
    """Return the minimal device files a Python process may use."""
    return [
        path
        for path in (Path("/dev/null"), Path("/dev/urandom"), Path("/dev/random"))
        if path.exists()
    ]


def apply_filesystem_policy(read_roots: Sequence[Path], scratch: Path) -> int:
    """Apply the Landlock policy and return the ABI version used.

    Parameters
    ----------
    read_roots : sequence of Path
        Existing files or directories the script may read.
    scratch : Path
        The job scratch directory. The script may read and write here.

    Returns
    -------
    int
        The Landlock ABI version.

    Raises
    ------
    SandboxUnavailableError
        When Landlock cannot be queried or applied.
    """
    abi = landlock_abi()
    if abi < 1:
        raise SandboxUnavailableError("Landlock is not available on this kernel")
    library = _libc()
    handled_fs = _handled_fs(abi)
    handled_net = ACCESS_NET_BIND_TCP | ACCESS_NET_CONNECT_TCP if abi >= 4 else 0
    size = (
        ctypes.sizeof(_RulesetAttr)
        if abi >= 6
        else (ctypes.sizeof(ctypes.c_uint64) * 2 if abi >= 4 else ctypes.sizeof(ctypes.c_uint64))
    )
    ruleset = _RulesetAttr(handled_access_fs=handled_fs, handled_access_net=handled_net, scoped=0)
    ruleset_fd = _syscall(
        library,
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(ruleset),
        ctypes.c_size_t(size),
        ctypes.c_uint32(0),
    )
    try:
        for path in _runtime_paths():
            allowed = READ_DIR_ACCESS if path.is_dir() else READ_ACCESS
            _add_rule(library, ruleset_fd, path, allowed)
        for path in read_roots:
            allowed = READ_DIR_ACCESS if path.is_dir() else READ_ACCESS
            _add_rule(library, ruleset_fd, path, allowed)
        _add_rule(library, ruleset_fd, scratch, WRITE_ACCESS)
        for path in _device_paths():
            _add_rule(library, ruleset_fd, path, READ_ACCESS | ACCESS_FS_WRITE_FILE)
        if int(library.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) != 0:
            error = ctypes.get_errno()
            raise SandboxUnavailableError(f"could not set no_new_privs: {os.strerror(error)}")
        _syscall(library, SYS_LANDLOCK_RESTRICT_SELF, ctypes.c_int(ruleset_fd), ctypes.c_uint32(0))
    except OSError as error:
        raise SandboxUnavailableError(f"could not apply Landlock policy: {error}") from error
    finally:
        os.close(ruleset_fd)
    return abi


def sandbox_argv(
    script: Path,
    scratch: Path,
    read_roots: Iterable[Path],
    *,
    timeout_seconds: float,
    memory_bytes: int,
    max_file_bytes: int,
) -> list[str]:
    """Build the unshare worker argv for one Python job.

    Parameters
    ----------
    script : Path
        Script inside the scratch directory.
    scratch : Path
        Job scratch directory.
    read_roots : iterable of Path
        Read-only inputs available to the script.
    timeout_seconds : float
        Wall-clock and CPU ceiling.
    memory_bytes : int
        Address-space ceiling.
    max_file_bytes : int
        Largest file the script may create.

    Returns
    -------
    list of str
        The argv, without a shell.

    Raises
    ------
    SandboxUnavailableError
        When the host does not expose the required primitives.
    """
    unshare = unshare_path()
    if unshare is None:
        raise SandboxUnavailableError("the host does not provide unshare")
    if landlock_abi() < 1:
        raise SandboxUnavailableError("the host does not provide Landlock")
    command = [
        unshare,
        "--user",
        "--map-root-user",
        "--pid",
        "--net",
        "--fork",
        "--kill-child",
        sys.executable,
        "-B",
        "-m",
        "ws4.web.sandbox_worker",
        "--script",
        str(script),
        "--scratch",
        str(scratch),
        "--memory-bytes",
        str(int(memory_bytes)),
        "--cpu-seconds",
        str(max(1, int(timeout_seconds))),
        "--max-file-bytes",
        str(int(max_file_bytes)),
    ]
    for root in read_roots:
        command.extend(["--read-root", str(root)])
    return command
