"""Forest carbon accounting support for WS4.

The carbon package contract is produced by FEMIC and consumed here. The loader in
:mod:`ws4.carbon.package` validates the package before any SIT compilation or engine
run happens.
"""

from __future__ import annotations

from .package import (
    CarbonPackage,
    CarbonPackageError,
    TrackResolution,
    load_carbon_package,
    package_fingerprint,
    resolve_tracks,
    validate_carbon_package,
)
from .sit import (
    CarbonSitError,
    SitTables,
    build_sit_tables,
    read_schedule,
    write_sit_tables,
)

__all__ = [
    "CarbonPackage",
    "CarbonPackageError",
    "CarbonSitError",
    "SitTables",
    "TrackResolution",
    "build_sit_tables",
    "load_carbon_package",
    "package_fingerprint",
    "read_schedule",
    "resolve_tracks",
    "validate_carbon_package",
    "write_sit_tables",
]
