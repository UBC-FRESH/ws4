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
    merge_carbon_accounts,
    run_libcbm,
    run_libcbm_tables,
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
from .parity import (
    FrameComparison,
    RunComparison,
    compare_carbon_runs,
    compare_frames,
    mass_balance,
    replay_equal,
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
    "FrameComparison",
    "RunComparison",
    "SitTables",
    "TrackResolution",
    "build_sit_tables",
    "carbon_accounts",
    "cbm_defaults_reference",
    "check_cbm_defaults",
    "compare_carbon_runs",
    "compare_frames",
    "installed_libcbm_version",
    "load_carbon_package",
    "mass_balance",
    "merge_carbon_accounts",
    "package_fingerprint",
    "read_schedule",
    "replay_equal",
    "resolve_tracks",
    "run_libcbm",
    "run_libcbm_tables",
    "validate_carbon_package",
    "write_carbon_run",
    "write_sit_tables",
]
