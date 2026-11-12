"""Stochastic landscape processes over the deterministic WS4 estate model.

The package starts with the shared event record, the counter-based random tape, and the
replayable event log (P144.2). Later tasks add the ecosystem package, the cohort state
extension, the fire process, and scenario-aware risk targets. The compiled management
dataset remains the contract; this package is the optional ecological layer over it.
"""

from __future__ import annotations

from .events import EVENT_PHASES, EVENT_SCHEMA_VERSION, Event, EventError
from .executor import ExecutionResult, Executor
from .fire import (
    FireBehaviourConfig,
    FireConfig,
    FireEdge,
    FireError,
    FireProcess,
    FireResult,
    FireRun,
    SalvageSource,
    run_fire_demo,
    synthetic_grid,
)
from .log import (
    EVENT_LOG_SCHEMA_VERSION,
    EventLog,
    EventLogBuilder,
    EventLogMetadata,
    ReplayError,
    ReplayRunner,
)
from .package import (
    EcosystemManifest,
    EcosystemPackage,
    EcosystemPackageError,
    EcosystemProducer,
    EcosystemSource,
    find_ecosystem_package,
    load_dataset_ecosystem,
    load_ecosystem_package,
    package_fingerprint,
    validate_ecosystem_package,
)
from .process import (
    DecisionSource,
    Process,
    ProcessContext,
    ProcessError,
    validate_process,
    validate_sources,
)
from .scenarios import (
    RISK_AGGREGATIONS,
    SCENARIO_SCHEMA_VERSION,
    OutOfSampleReport,
    SampleAverageApproximation,
    Scenario,
    ScenarioError,
    ScenarioEvaluation,
    ScenarioEvaluator,
    ScenarioSet,
    fire_evaluator,
    load_scenarios,
    risk_account_values,
)
from .state import (
    BridgeSpec,
    CohortState,
    CohortStateError,
    NullBridge,
    StateError,
    StateSchema,
    StateVariable,
)
from .tape import TAPE_ALGORITHM, DrawKey, RandomTape, TapeError

__all__ = [
    "EVENT_LOG_SCHEMA_VERSION",
    "EVENT_PHASES",
    "EVENT_SCHEMA_VERSION",
    "RISK_AGGREGATIONS",
    "SCENARIO_SCHEMA_VERSION",
    "TAPE_ALGORITHM",
    "BridgeSpec",
    "CohortState",
    "CohortStateError",
    "DecisionSource",
    "DrawKey",
    "EcosystemManifest",
    "EcosystemPackage",
    "EcosystemPackageError",
    "EcosystemProducer",
    "EcosystemSource",
    "Event",
    "EventError",
    "EventLog",
    "EventLogBuilder",
    "EventLogMetadata",
    "ExecutionResult",
    "Executor",
    "FireBehaviourConfig",
    "FireConfig",
    "FireEdge",
    "FireError",
    "FireProcess",
    "FireResult",
    "FireRun",
    "NullBridge",
    "OutOfSampleReport",
    "Process",
    "ProcessContext",
    "ProcessError",
    "RandomTape",
    "ReplayError",
    "ReplayRunner",
    "SalvageSource",
    "SampleAverageApproximation",
    "Scenario",
    "ScenarioError",
    "ScenarioEvaluation",
    "ScenarioEvaluator",
    "ScenarioSet",
    "StateError",
    "StateSchema",
    "StateVariable",
    "TapeError",
    "find_ecosystem_package",
    "fire_evaluator",
    "load_dataset_ecosystem",
    "load_ecosystem_package",
    "load_scenarios",
    "package_fingerprint",
    "risk_account_values",
    "run_fire_demo",
    "synthetic_grid",
    "validate_ecosystem_package",
    "validate_process",
    "validate_sources",
]
