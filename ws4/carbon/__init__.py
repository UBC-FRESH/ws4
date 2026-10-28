"""Forest carbon accounting support for WS4.

The carbon package contract is produced by FEMIC and consumed here. The loader in
:mod:`ws4.carbon.package` validates the package before any SIT compilation or engine
run happens. :mod:`ws4.carbon.hwp` adds the explicit product lifecycle, and
:mod:`ws4.carbon.curves` compiles the simulated-clearcut curve artifact.
"""

from __future__ import annotations

from .curves import CarbonCurveResult, generate_carbon_curves
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
    with_fertilization_recovery,
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
from .hwp import (
    HwpConfig,
    HwpConfigError,
    hwp_accounts,
    hwp_manifest,
    load_hwp_config,
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
    filter_carbon_package,
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
    "CarbonCurveResult",
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
    "HwpConfig",
    "HwpConfigError",
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
    "filter_carbon_package",
    "gcbm_accounts",
    "generate_carbon_curves",
    "hwp_accounts",
    "hwp_manifest",
    "installed_libcbm_version",
    "load_carbon_package",
    "load_fertilization_config",
    "load_hwp_config",
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
    "with_fertilization_recovery",
    "write_carbon_run",
    "write_gcbm_results",
    "write_sit_tables",
]
