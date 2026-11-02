"""Named scenario profiles for the LTSY watcher.

A profile file is a small YAML library. Each profile names a target file, the accounts to
watch, and an optional schedule output. Paths are resolved relative to the library's
``base_dir``; the watcher and CLI consume the same resolved paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProfileError(ValueError):
    """Raised when a scenario-profile library is invalid."""


@dataclass(frozen=True)
class ScenarioProfile:
    """One named scenario profile.

    Parameters
    ----------
    name : str
        Stable profile name.
    description : str
        Human-readable description.
    targets : pathlib.Path
        Resolved target YAML.
    accounts : tuple of str
        Accounts to watch.
    schedule_out : pathlib.Path or None
        Default schedule output.
    profile_file : pathlib.Path
        Source library path.
    """

    name: str
    description: str
    targets: Path
    accounts: tuple[str, ...]
    schedule_out: Path | None
    profile_file: Path

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation with resolved paths.

        Returns
        -------
        dict of str to Any
            Profile fields.
        """
        return {
            "name": self.name,
            "description": self.description,
            "targets": str(self.targets),
            "accounts": list(self.accounts),
            "schedule_out": str(self.schedule_out) if self.schedule_out is not None else None,
            "profile_file": str(self.profile_file),
        }


def load_profiles(path: str | Path) -> dict[str, ScenarioProfile]:
    """Load and validate a scenario-profile library.

    Parameters
    ----------
    path : str or pathlib.Path
        YAML library path.

    Returns
    -------
    dict of str to ScenarioProfile
        Profiles keyed by name.

    Raises
    ------
    ProfileError
        If the file is missing, malformed, duplicated, or names a missing target.
    """
    library = Path(path)
    if not library.is_file():
        raise ProfileError(f"profile library does not exist: {library}")
    try:
        payload = yaml.safe_load(library.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ProfileError(f"cannot read profile library {library}: {error}") from error
    if not isinstance(payload, dict):
        raise ProfileError("profile library must be a mapping")
    raw_base = payload.get("base_dir", ".")
    if not isinstance(raw_base, str):
        raise ProfileError("base_dir must be a string")
    base_dir = (library.parent / raw_base).resolve()
    entries = payload.get("profiles")
    if not isinstance(entries, list) or not entries:
        raise ProfileError("profiles must be a non-empty list")
    profiles: dict[str, ScenarioProfile] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ProfileError(f"profile {index} must be a mapping")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ProfileError(f"profile {index} needs a name")
        if name in profiles:
            raise ProfileError(f"duplicate profile name: {name}")
        raw_targets = entry.get("targets")
        if not isinstance(raw_targets, str) or not raw_targets:
            raise ProfileError(f"profile {name} needs targets")
        targets = (base_dir / raw_targets).resolve()
        if not targets.is_file():
            raise ProfileError(f"profile {name} target does not exist: {targets}")
        raw_accounts = entry.get("accounts", [])
        if not isinstance(raw_accounts, list) or not all(
            isinstance(account, str) and account for account in raw_accounts
        ):
            raise ProfileError(f"profile {name} accounts must be a list of strings")
        raw_schedule = entry.get("schedule_out")
        if raw_schedule is not None and not isinstance(raw_schedule, str):
            raise ProfileError(f"profile {name} schedule_out must be a string")
        schedule_out = (base_dir / raw_schedule).resolve() if raw_schedule else None
        profiles[name] = ScenarioProfile(
            name=name,
            description=str(entry.get("description", "")),
            targets=targets,
            accounts=tuple(raw_accounts),
            schedule_out=schedule_out,
            profile_file=library.resolve(),
        )
    return profiles


def get_profile(profiles: dict[str, ScenarioProfile], name: str) -> ScenarioProfile:
    """Return one profile or raise a helpful error.

    Parameters
    ----------
    profiles : dict of str to ScenarioProfile
        Loaded profile library.
    name : str
        Profile name.

    Returns
    -------
    ScenarioProfile
        The requested profile.

    Raises
    ------
    ProfileError
        If the name is absent.
    """
    try:
        return profiles[name]
    except KeyError as error:
        available = ", ".join(sorted(profiles))
        raise ProfileError(f"unknown profile {name!r}; available: {available}") from error
