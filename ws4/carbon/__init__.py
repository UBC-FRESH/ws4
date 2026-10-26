"""Forest carbon accounting support for WS4.

The carbon package contract is produced by FEMIC and consumed here. The loader in
:mod:`ws4.carbon.package` validates the package before any SIT compilation or engine
run happens.
"""

from __future__ import annotations

from .fertilization import (
    FERTILIZATION_TREATMENTS,
    FertilizationApplication,
    FertilizationConfig,
    FertilizationConfigError,
    block_areas_from_dataset,
    fertilization_accounts,
    load_fertilization_config,
    with_fertilization_curves,
    with_fertilization_disturbances,
)
from .gcbm import (
    GcbmResults,
    GcbmResultsError,
    GcbmRunResult,
    compare_gcbm_to_carbon,
    gcbm_accounts,
    read_gcbm_results,
    write_gcbm_results,
)
from .ledger import CarbonLedger
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
    build_sit_tables_from_tables,
    read_dataset_tables,
    read_schedule,
    write_sit_tables,
)

__all__ = [
    "FERTILIZATION_TREATMENTS",
    "CarbonEngineError",
    "CarbonLedger",
    "CarbonPackage",
    "CarbonPackageError",
    "CarbonRun",
    "CarbonRunResult",
    "CarbonSitError",
    "FertilizationApplication",
    "FertilizationConfig",
    "FertilizationConfigError",
    "FrameComparison",
    "GcbmResults",
    "GcbmResultsError",
    "GcbmRunResult",
    "RunComparison",
    "SitTables",
    "TrackResolution",
    "block_areas_from_dataset",
    "build_sit_tables",
    "build_sit_tables_from_tables",
    "carbon_accounts",
    "cbm_defaults_reference",
    "check_cbm_defaults",
    "compare_carbon_runs",
    "compare_frames",
    "compare_gcbm_to_carbon",
    "fertilization_accounts",
    "gcbm_accounts",
    "installed_libcbm_version",
    "load_carbon_package",
    "load_fertilization_config",
    "mass_balance",
    "merge_carbon_accounts",
    "package_fingerprint",
    "read_dataset_tables",
    "read_gcbm_results",
    "read_schedule",
    "replay_equal",
    "resolve_tracks",
    "run_libcbm",
    "run_libcbm_tables",
    "validate_carbon_package",
    "with_fertilization_curves",
    "with_fertilization_disturbances",
    "write_carbon_run",
    "write_gcbm_results",
    "write_sit_tables",
]
