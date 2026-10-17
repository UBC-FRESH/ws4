"""A fixture submodule that fails to import, for the docstring-audit tests."""

from __future__ import annotations

raise RuntimeError("this module is meant to be unimportable")
