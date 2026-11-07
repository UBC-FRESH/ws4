"""Scenario ensembles, risk aggregation, and sample-average approximation.

The deterministic estate model evaluates one schedule against one world. A scenario ensemble
evaluates the same decision against several worlds, each with its own random tape seed and
optional process overrides. Common random numbers hold because every decision is evaluated on
the same scenario seeds.

This module owns the scenario definition, the risk aggregation of account values, and the
sample-average-approximation loop. It does not run the estate optimizer itself: a caller
supplies an evaluator that maps a decision and a scenario to account values, so the same layer
serves the fire process, a compiled estate model, or a future full scenario simulator.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

import pandas as pd
import yaml

from ..opt.objective import Target, objective, objective_terms, period_value
from .fire import FireConfig, FireEdge, FireRun
from .state import CohortState

SCENARIO_SCHEMA_VERSION: Final[str] = "ws4.scenario.v1"

RISK_AGGREGATIONS: Final[tuple[str, ...]] = (
    "single",
    "mean",
    "min",
    "max",
    "cvar",
    "cvar_lower",
    "cvar_upper",
    "quantile",
    "probability",
    "regret",
)

#: The evaluator contract: a decision and a scenario produce account values.
ScenarioEvaluator = Callable[[object, "Scenario"], pd.DataFrame]


class ScenarioError(ValueError):
    """Raised when a scenario set, an aggregation, or an evaluation is invalid."""


def _text(value: object, field: str) -> str:
    """Return a non-empty, stripped string."""
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScenarioError(f"{field} must be an integer")
    return value


def _finite(value: object, field: str) -> float:
    """Return a finite float, normalizing negative zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ScenarioError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True)
class Scenario:
    """One stochastic world in a scenario ensemble.

    Parameters
    ----------
    scenario_id : str
        Stable identifier, unique within the set.
    seed : int
        The random-tape seed. Decisions evaluated on the same scenario share it, which is the
        common-random-numbers mechanism.
    weight : float, optional
        The scenario weight, positive (default 1.0).
    overrides : mapping of str to object, optional
        Process or climate overrides. The evaluator interprets them; this layer only carries
        them.
    description : str, optional
        A human-readable description (default empty).
    """

    scenario_id: str
    seed: int
    weight: float = 1.0
    overrides: Mapping[str, object] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        """Validate the scenario and freeze its override mapping."""
        scenario_id = _text(self.scenario_id, "scenario_id")
        seed = _integer(self.seed, "seed")
        if seed < 0:
            raise ScenarioError("seed must be non-negative")
        weight = _finite(self.weight, "weight")
        if weight <= 0.0:
            raise ScenarioError("weight must be positive")
        if not isinstance(self.overrides, Mapping):
            raise ScenarioError("overrides must be a mapping")
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "seed", seed)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "overrides", dict(self.overrides))
        object.__setattr__(self, "description", str(self.description).strip())

    def to_dict(self) -> dict[str, object]:
        """Return the scenario as a JSON/YAML-serializable mapping.

        Returns
        -------
        dict
            The scenario fields.
        """
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "weight": self.weight,
            "overrides": dict(self.overrides),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Scenario:
        """Validate and construct a scenario from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping with ``scenario_id`` (or ``id``), ``seed``, and optional ``weight``,
            ``overrides``, and ``description``.

        Returns
        -------
        Scenario
            The validated scenario.

        Raises
        ------
        ScenarioError
            If the mapping is invalid.
        """
        if not isinstance(payload, Mapping):
            raise ScenarioError("scenario must be a mapping")
        raw_id = payload.get("scenario_id", payload.get("id"))
        if raw_id is None:
            raise ScenarioError("scenario is missing scenario_id")
        if "seed" not in payload:
            raise ScenarioError("scenario is missing seed")
        overrides = payload.get("overrides", {})
        if overrides is None:
            overrides = {}
        if not isinstance(overrides, Mapping):
            raise ScenarioError("overrides must be a mapping")
        description = payload.get("description", "")
        return cls(
            scenario_id=_text(raw_id, "scenario_id"),
            seed=_integer(payload["seed"], "seed"),
            weight=_finite(payload.get("weight", 1.0), "weight"),
            overrides=overrides,
            description="" if description is None else str(description),
        )


@dataclass(frozen=True)
class ScenarioSet:
    """A named, ordered ensemble of scenarios.

    Parameters
    ----------
    scenarios : tuple of Scenario
        The scenarios, at least one, with unique ids.
    name : str, optional
        The ensemble name (default ``default``).
    """

    scenarios: tuple[Scenario, ...]
    name: str = "default"

    def __post_init__(self) -> None:
        """Validate the ensemble and its unique scenario ids."""
        scenarios = tuple(self.scenarios)
        if not scenarios:
            raise ScenarioError("a scenario set needs at least one scenario")
        seen: set[str] = set()
        for scenario in scenarios:
            if not isinstance(scenario, Scenario):
                raise ScenarioError("scenarios must contain Scenario records")
            if scenario.scenario_id in seen:
                raise ScenarioError(f"duplicate scenario id: {scenario.scenario_id!r}")
            seen.add(scenario.scenario_id)
        object.__setattr__(self, "scenarios", scenarios)
        object.__setattr__(self, "name", _text(self.name, "name"))

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        """Return the scenario ids in order.

        Returns
        -------
        tuple of str
            The ids.
        """
        return tuple(scenario.scenario_id for scenario in self.scenarios)

    def weights(self) -> dict[str, float]:
        """Return the scenario weights by id.

        Returns
        -------
        dict of str to float
            The weights.
        """
        return {scenario.scenario_id: scenario.weight for scenario in self.scenarios}

    def split(self, train_fraction: float = 0.7) -> tuple[ScenarioSet, ScenarioSet]:
        """Split the ensemble into a training set and a validation set.

        Parameters
        ----------
        train_fraction : float, optional
            The share of scenarios in the training set, in (0, 1) (default 0.7).

        Returns
        -------
        tuple of ScenarioSet
            The training and validation sets, in the original order.

        Raises
        ------
        ScenarioError
            If there are fewer than two scenarios or the fraction is not in (0, 1).
        """
        if len(self.scenarios) < 2:
            raise ScenarioError("an out-of-sample split needs at least two scenarios")
        if not 0.0 < train_fraction < 1.0:
            raise ScenarioError("train_fraction must be between 0 and 1")
        count = round(len(self.scenarios) * train_fraction)
        count = min(max(1, count), len(self.scenarios) - 1)
        return (
            ScenarioSet(self.scenarios[:count], name=f"{self.name}.train"),
            ScenarioSet(self.scenarios[count:], name=f"{self.name}.validation"),
        )

    @classmethod
    def from_seeds(
        cls,
        seeds: Sequence[int],
        *,
        name: str = "default",
        weights: Sequence[float] | None = None,
    ) -> ScenarioSet:
        """Build a scenario set from seeds.

        Parameters
        ----------
        seeds : sequence of int
            The scenario seeds.
        name : str, optional
            The ensemble name (default ``default``).
        weights : sequence of float or None, optional
            The weights, one per seed. None uses 1.0 for every scenario.

        Returns
        -------
        ScenarioSet
            The ensemble.

        Raises
        ------
        ScenarioError
            If the seeds are empty or the weights differ in length.
        """
        if not seeds:
            raise ScenarioError("at least one seed is required")
        if weights is not None and len(weights) != len(seeds):
            raise ScenarioError("weights and seeds must have the same length")
        scenarios = tuple(
            Scenario(
                scenario_id=f"s{index + 1}",
                seed=seed,
                weight=1.0 if weights is None else weights[index],
            )
            for index, seed in enumerate(seeds)
        )
        return cls(scenarios, name=name)

    def to_dict(self) -> dict[str, object]:
        """Return the ensemble as a JSON/YAML-serializable mapping.

        Returns
        -------
        dict
            The schema version, name, and scenarios.
        """
        return {
            "schema_version": SCENARIO_SCHEMA_VERSION,
            "name": self.name,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ScenarioSet:
        """Validate and construct an ensemble from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping with a ``scenarios`` list and optional ``name`` and ``schema_version``.
            A bare list of scenarios is also accepted.

        Returns
        -------
        ScenarioSet
            The validated ensemble.

        Raises
        ------
        ScenarioError
            If the mapping is invalid or the schema version is unsupported.
        """
        if not isinstance(payload, Mapping):
            raise ScenarioError("scenario set must be a mapping")
        version = payload.get("schema_version")
        if version is not None and version != SCENARIO_SCHEMA_VERSION:
            raise ScenarioError(
                f"scenario schema_version must be {SCENARIO_SCHEMA_VERSION!r}; got {version!r}"
            )
        raw_scenarios = payload.get("scenarios")
        if not isinstance(raw_scenarios, list):
            raise ScenarioError("scenario set is missing a scenarios list")
        scenarios = []
        for item in raw_scenarios:
            if not isinstance(item, Mapping):
                raise ScenarioError("scenario entries must be mappings")
            scenarios.append(Scenario.from_dict(item))
        return cls(tuple(scenarios), name=str(payload.get("name", "default")))

    def write(self, path: Path) -> None:
        """Write the ensemble as YAML or JSON.

        Parameters
        ----------
        path : Path
            The destination. A ``.json`` suffix writes JSON; ``.yaml`` or ``.yml`` writes
            YAML. Parent directories are created.

        Raises
        ------
        ScenarioError
            If the suffix is unsupported.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix == ".json":
            text = json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        elif suffix in {".yaml", ".yml"}:
            text = yaml.safe_dump(self.to_dict(), sort_keys=False)
        else:
            raise ScenarioError("scenario files must be JSON or YAML")
        path.write_text(text, encoding="utf-8")


def load_scenarios(path: Path) -> ScenarioSet:
    """Load a scenario ensemble from YAML or JSON.

    Parameters
    ----------
    path : Path
        The scenario file.

    Returns
    -------
    ScenarioSet
        The validated ensemble.

    Raises
    ------
    ScenarioError
        If the file is missing, malformed, or has an unsupported suffix.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ScenarioError("scenario files must be JSON or YAML")
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise ScenarioError(f"cannot read scenario set {path}: {error}") from error
    if isinstance(payload, list):
        payload = {"scenarios": payload}
    if not isinstance(payload, Mapping):
        raise ScenarioError("scenario file must contain a mapping or a scenario list")
    return ScenarioSet.from_dict(payload)


@dataclass(frozen=True)
class ScenarioEvaluation:
    """The evaluation of one decision over a scenario ensemble.

    Attributes
    ----------
    decision : object
        The evaluated decision.
    scenarios : ScenarioSet
        The ensemble used.
    values : pandas.DataFrame
        Per-scenario account values with ``offset``, ``account``, ``value``, and
        ``scenario`` columns.
    aggregated : pandas.DataFrame
        The risk pseudo-account rows with ``offset``, ``account``, ``value``, and
        ``scenario`` columns.
    targets : tuple of Target
        The effective risk targets used by the objective.
    objective : float
        The weighted-goal objective of the aggregated values.
    penalties : tuple of float
        One penalty per effective target.
    """

    decision: object
    scenarios: ScenarioSet
    values: pd.DataFrame
    aggregated: pd.DataFrame
    targets: tuple[Target, ...]
    objective: float
    penalties: tuple[float, ...]

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the evaluation.

        Returns
        -------
        dict
            The objective, scenario ids, and target penalties.
        """
        return {
            "objective": self.objective,
            "scenario_count": len(self.scenarios.scenarios),
            "scenario_ids": list(self.scenarios.scenario_ids),
            "targets": [
                {"account": target.account, "penalty": penalty}
                for target, penalty in zip(self.targets, self.penalties, strict=True)
            ],
        }


@dataclass(frozen=True)
class OutOfSampleReport:
    """A train-versus-validation comparison for one decision.

    Attributes
    ----------
    decision : object
        The evaluated decision.
    train : ScenarioEvaluation
        The training evaluation.
    validation : ScenarioEvaluation
        The held-out evaluation.
    """

    decision: object
    train: ScenarioEvaluation
    validation: ScenarioEvaluation

    @property
    def generalization_gap(self) -> float:
        """Return the validation objective minus the training objective.

        Returns
        -------
        float
            The gap; positive means the decision looks worse out of sample.
        """
        return self.validation.objective - self.train.objective

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the report.

        Returns
        -------
        dict
            The training and validation summaries and the generalization gap.
        """
        return {
            "generalization_gap": self.generalization_gap,
            "train": self.train.summary(),
            "validation": self.validation.summary(),
        }

    def write(self, out_dir: Path) -> None:
        """Write the train and validation values, aggregates, and summary.

        Parameters
        ----------
        out_dir : Path
            The output directory. It is created when missing.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.train.values.to_csv(out_dir / "train_values.csv", index=False)
        self.validation.values.to_csv(out_dir / "validation_values.csv", index=False)
        self.train.aggregated.to_csv(out_dir / "train_aggregated.csv", index=False)
        self.validation.aggregated.to_csv(out_dir / "validation_aggregated.csv", index=False)
        (out_dir / "summary.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _value_index(frame: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index an account frame by ``(offset, account)``."""
    return {
        (int(float(str(row.offset))), str(row.account)): float(str(row.value))
        for row in frame.itertuples(index=False)
    }


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return the weighted mean of the values."""
    total = sum(weights)
    if total <= 0.0:
        raise ScenarioError("scenario weights must have a positive sum")
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / total


def _quantile(values: Sequence[float], weights: Sequence[float], alpha: float) -> float:
    """Return the weighted quantile at ``alpha`` with linear interpolation."""
    ordered = sorted(zip(values, weights, strict=True))
    total = sum(weights)
    if total <= 0.0:
        raise ScenarioError("scenario weights must have a positive sum")
    threshold = alpha * total
    cumulative = 0.0
    for position, (value, weight) in enumerate(ordered):
        if cumulative + weight >= threshold:
            if position == 0 or weight <= 0.0 or cumulative >= threshold:
                return value
            previous = ordered[position - 1][0]
            fraction = (threshold - cumulative) / weight
            return previous + (value - previous) * fraction
        cumulative += weight
    return ordered[-1][0]


def _cvar(values: Sequence[float], weights: Sequence[float], alpha: float, *, upper: bool) -> float:
    """Return the weighted lower- or upper-tail CVaR at level ``alpha``."""
    ordered = sorted(zip(values, weights, strict=True), reverse=upper)
    total = sum(weights)
    if total <= 0.0:
        raise ScenarioError("scenario weights must have a positive sum")
    target = (1.0 - alpha) * total
    tail: list[tuple[float, float]] = []
    accumulated = 0.0
    for value, weight in ordered:
        if accumulated + weight <= target:
            tail.append((value, weight))
            accumulated += weight
        else:
            take = target - accumulated
            if take > 0.0:
                tail.append((value, take))
            break
    if not tail:
        tail = [ordered[0]]
    return _weighted_mean([value for value, _ in tail], [weight for _, weight in tail])


def _probability(values: Sequence[float], weights: Sequence[float], target: Target) -> float:
    """Return the weighted probability that a scenario meets the target bounds."""
    if target.minimum is None and target.maximum is None:
        raise ScenarioError("probability aggregation needs a minimum or a maximum")
    flags: list[float] = []
    for value in values:
        above = target.minimum is None or value >= target.minimum
        below = target.maximum is None or value <= target.maximum
        flags.append(1.0 if above and below else 0.0)
    return _weighted_mean(flags, weights)


def _regret(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return the range of the scenario values."""
    del weights
    return max(values) - min(values)


def _aggregate(values: Sequence[float], weights: Sequence[float], target: Target) -> float:
    """Apply one target's aggregation to its per-scenario values."""
    if target.aggregation in {"mean"}:
        return _weighted_mean(values, weights)
    if target.aggregation == "min":
        return min(values)
    if target.aggregation == "max":
        return max(values)
    if target.aggregation in {"cvar", "cvar_lower"}:
        return _cvar(values, weights, target.risk_alpha, upper=False)
    if target.aggregation == "cvar_upper":
        return _cvar(values, weights, target.risk_alpha, upper=True)
    if target.aggregation == "quantile":
        return _quantile(values, weights, target.risk_alpha)
    if target.aggregation == "probability":
        return _probability(values, weights, target)
    if target.aggregation == "regret":
        return _regret(values, weights)
    raise ScenarioError(f"unsupported risk aggregation: {target.aggregation!r}")


def _risk_account_name(index: int, target: Target) -> str:
    """Return the pseudo-account name of one risk target."""
    return f"risk.{target.aggregation}.{index}.{target.account}"


def _effective_bounds(target: Target) -> tuple[float | None, float | None]:
    """Return the bounds the effective risk target applies."""
    if target.aggregation in {"probability", "regret"}:
        return target.risk_minimum, target.risk_maximum
    minimum = target.risk_minimum if target.risk_minimum is not None else target.minimum
    maximum = target.risk_maximum if target.risk_maximum is not None else target.maximum
    return minimum, maximum


def risk_account_values(
    values: pd.DataFrame,
    targets: Sequence[Target],
    *,
    scenario_ids: Sequence[str] | None = None,
    weights: Mapping[str, float] | None = None,
) -> tuple[pd.DataFrame, list[Target]]:
    """Aggregate per-scenario account values into risk pseudo-accounts.

    The input must carry ``offset`` (or ``year``), ``account``, ``value``, and ``scenario``
    columns. A target with ``aggregation="single"`` is rejected when the frame has a scenario
    dimension; set ``aggregation="mean"`` or another risk statistic. A target with a flow term
    is also rejected, because a flow penalty is a whole-profile comparison rather than a
    period statistic.

    Parameters
    ----------
    values : pandas.DataFrame
        Per-scenario account values.
    targets : sequence of Target
        The targets whose aggregation fields drive the result.
    scenario_ids : sequence of str or None, optional
        The full scenario list. None infers it from the frame's ``scenario`` column.
    weights : mapping of str to float or None, optional
        Scenario weights by id. None gives every scenario weight 1.0.

    Returns
    -------
    tuple of (pandas.DataFrame, list of Target)
        The risk pseudo-account rows and the effective targets.

    Raises
    ------
    ScenarioError
        If the frame is missing a required column, a target is incompatible, or a scenario
        weight is not positive.
    """
    if not isinstance(values, pd.DataFrame):
        raise ScenarioError("values must be a pandas DataFrame")
    frame = values.copy()
    if "offset" not in frame.columns:
        if "year" not in frame.columns:
            raise ScenarioError("values need an offset or year column")
        frame["offset"] = frame["year"]
    for column in ("offset", "account", "value"):
        if column not in frame.columns:
            raise ScenarioError(f"values need a {column!r} column")
    if "scenario" not in frame.columns:
        return frame, list(targets)
    ids = (
        tuple(str(item) for item in scenario_ids)
        if scenario_ids is not None
        else tuple(sorted(str(item) for item in frame["scenario"].unique()))
    )
    if not ids:
        raise ScenarioError("the scenario column is empty")
    weight_map = dict.fromkeys(ids, 1.0)
    if weights is not None:
        for scenario_id in ids:
            if scenario_id not in weights:
                raise ScenarioError(f"missing weight for scenario {scenario_id!r}")
            weight = _finite(weights[scenario_id], "weight")
            if weight <= 0.0:
                raise ScenarioError("scenario weights must be positive")
            weight_map[scenario_id] = weight
    rows: list[dict[str, object]] = []
    effective: list[Target] = []
    for index, target in enumerate(targets):
        if target.aggregation == "single":
            raise ScenarioError(
                f"target {target.account!r} uses aggregation 'single' with a scenario "
                "dimension; set aggregation='mean' or another risk statistic"
            )
        if target.flow:
            raise ScenarioError("flow targets cannot be risk-aggregated")
        per_scenario: list[float] = []
        for scenario_id in ids:
            subset = frame[frame["scenario"].astype(str) == scenario_id]
            per_scenario.append(period_value(_value_index(subset), target))
        statistic = _aggregate(
            per_scenario,
            [weight_map[scenario_id] for scenario_id in ids],
            target,
        )
        minimum, maximum = _effective_bounds(target)
        account = _risk_account_name(index, target)
        rows.append(
            {
                "offset": target.end_offset(),
                "account": account,
                "value": statistic,
                "scenario": "aggregate",
            }
        )
        effective.append(
            replace(
                target,
                account=account,
                aggregation="single",
                minimum=minimum,
                maximum=maximum,
            )
        )
    return pd.DataFrame(rows, columns=["offset", "account", "value", "scenario"]), effective


class SampleAverageApproximation:
    """Evaluate decisions over a scenario ensemble with common random numbers.

    Parameters
    ----------
    scenarios : ScenarioSet
        The training ensemble.
    evaluator : ScenarioEvaluator
        Maps a decision and a scenario to account values. The evaluator must use the scenario
        seed for its random tape; that is what makes two decisions share the same draws.
    targets : sequence of Target
        The targets. Their ``aggregation`` fields select the risk statistic.
    """

    def __init__(
        self,
        scenarios: ScenarioSet,
        evaluator: ScenarioEvaluator,
        targets: Sequence[Target],
    ) -> None:
        """Retain the ensemble, evaluator, and targets."""
        if not scenarios.scenarios:
            raise ScenarioError("a scenario set needs at least one scenario")
        self.scenarios = scenarios
        self.evaluator = evaluator
        self.targets = tuple(targets)

    def evaluate(
        self, decision: object, scenarios: ScenarioSet | None = None
    ) -> ScenarioEvaluation:
        """Evaluate one decision over an ensemble.

        Parameters
        ----------
        decision : object
            The decision passed to the evaluator.
        scenarios : ScenarioSet or None, optional
            The ensemble to use. None uses the training ensemble.

        Returns
        -------
        ScenarioEvaluation
            The per-scenario values, risk aggregation, and objective.

        Raises
        ------
        ScenarioError
            If the evaluator returns an invalid frame or a target cannot be aggregated.
        """
        scenario_set = self.scenarios if scenarios is None else scenarios
        frames: list[pd.DataFrame] = []
        for scenario in scenario_set.scenarios:
            frame = self.evaluator(decision, scenario)
            if not isinstance(frame, pd.DataFrame):
                raise ScenarioError("the evaluator must return a pandas DataFrame")
            frame = frame.copy()
            if "offset" not in frame.columns:
                if "year" not in frame.columns:
                    raise ScenarioError("evaluator values need an offset or year column")
                frame["offset"] = frame["year"]
            for column in ("offset", "account", "value"):
                if column not in frame.columns:
                    raise ScenarioError(f"evaluator values need a {column!r} column")
            frame["scenario"] = scenario.scenario_id
            frames.append(frame)
        values = pd.concat(frames, ignore_index=True)
        aggregated, effective = risk_account_values(
            values,
            self.targets,
            scenario_ids=scenario_set.scenario_ids,
            weights=scenario_set.weights(),
        )
        penalties = tuple(objective_terms(aggregated, effective))
        return ScenarioEvaluation(
            decision=decision,
            scenarios=scenario_set,
            values=values,
            aggregated=aggregated,
            targets=tuple(effective),
            objective=objective(aggregated, effective),
            penalties=penalties,
        )

    def best(
        self, decisions: Iterable[object], scenarios: ScenarioSet | None = None
    ) -> ScenarioEvaluation:
        """Evaluate a finite decision set and return the lowest objective.

        Parameters
        ----------
        decisions : iterable of object
            The candidate decisions. For a larger search, call :meth:`evaluate` from the
            search loop instead.
        scenarios : ScenarioSet or None, optional
            The ensemble. None uses the training ensemble.

        Returns
        -------
        ScenarioEvaluation
            The best evaluation.

        Raises
        ------
        ScenarioError
            If the decision set is empty.
        """
        evaluations = [self.evaluate(decision, scenarios) for decision in decisions]
        if not evaluations:
            raise ScenarioError("at least one decision is required")
        return min(evaluations, key=lambda evaluation: evaluation.objective)

    def out_of_sample(self, decision: object, validation: ScenarioSet) -> ScenarioEvaluation:
        """Evaluate one decision on a held-out ensemble.

        Parameters
        ----------
        decision : object
            The decision.
        validation : ScenarioSet
            The held-out ensemble.

        Returns
        -------
        ScenarioEvaluation
            The validation evaluation.
        """
        return self.evaluate(decision, validation)

    def report(self, decision: object, validation: ScenarioSet) -> OutOfSampleReport:
        """Build a train-versus-validation report for one decision.

        Parameters
        ----------
        decision : object
            The decision.
        validation : ScenarioSet
            The held-out ensemble.

        Returns
        -------
        OutOfSampleReport
            The report.
        """
        return OutOfSampleReport(
            decision=decision,
            train=self.evaluate(decision),
            validation=self.out_of_sample(decision, validation),
        )


def fire_evaluator(state: CohortState, edges: Sequence[FireEdge], years: int) -> ScenarioEvaluator:
    """Build a scenario evaluator for the fire process.

    The decision is a :class:`~ws4.ecosystem.fire.FireConfig`. The evaluator copies the initial
    state for every run, uses the scenario seed for the tape, and returns the fire accounts with
    an ``offset`` column. It does not interpret scenario overrides; wrap it if a study needs
    them.

    Parameters
    ----------
    state : CohortState
        The initial cohort state.
    edges : sequence of FireEdge
        The landscape graph.
    years : int
        The fire horizon.

    Returns
    -------
    ScenarioEvaluator
        The evaluator.

    Raises
    ------
    ScenarioError
        If the horizon is not positive.
    """
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ScenarioError("years must be a positive integer")

    def evaluate(decision: object, scenario: Scenario) -> pd.DataFrame:
        """Evaluate one fire configuration on one scenario."""
        if not isinstance(decision, FireConfig):
            raise ScenarioError("the fire evaluator decision must be a FireConfig")
        fresh = CohortState(
            cohorts=state.cohorts.copy(deep=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )
        result = FireRun(
            fresh,
            edges,
            decision,
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
        ).run(years)
        frame = result.accounts.copy()
        frame["offset"] = frame["year"]
        return frame

    return evaluate
