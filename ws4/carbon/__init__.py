"""Forest carbon accounting support for WS4.

The carbon package contract is produced by FEMIC and consumed here. The loader in
:mod:`ws4.carbon.package` validates the package before any SIT compilation or engine
run happens.
"""

from __future__ import annotations

from .libcbm import (
    CarbonEngineError,
    CarbonRun,
    CarbonRunResult,
    carbon_accounts,
    cbm_defaults_reference,
    check_cbm_defaults,
    installed_libcbm_version,
    run_libcbm,
    write_carbon_run,
)
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
    "CarbonEngineError",
    "CarbonPackage",
    "CarbonPackageError",
    "CarbonRun",
    "CarbonRunResult",
    "CarbonSitError",
    "SitTables",
    "TrackResolution",
    "build_sit_tables",
    "carbon_accounts",
    "cbm_defaults_reference",
    "check_cbm_defaults",
    "installed_libcbm_version",
    "load_carbon_package",
    "package_fingerprint",
    "read_schedule",
    "resolve_tracks",
    "run_libcbm",
    "validate_carbon_package",
    "write_carbon_run",
    "write_sit_tables",
]
