"""The typed ecological state schema, cohort state, and the null yield bridge.

The ecosystem package declares its state variables and stores cohorts as area fractions of
a fragment. This module validates those declarations, builds the typed cohort table, and
aggregates cohorts back to fragments and blocks. The null bridge is the explicit no-op that
keeps the compiled management dataset authoritative until a calibrated bridge lands.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

from ..model.schema import Problem

STATE_DTYPES: Final[tuple[str, ...]] = ("float", "int", "bool", "string")
STATE_SCOPES: Final[tuple[str, ...]] = ("cohort", "fragment", "site", "landscape")
FIXED_COHORT_VARIABLES: Final[dict[str, str]] = {
    "species": "string",
    "age": "int",
    "area_fraction": "float",
    "biomass_t_ha": "float",
    "fuel_t_ha": "float",
    "snag_t_ha": "float",
}
FRACTION_TOLERANCE: Final[float] = 1e-6

JsonScalar = str | int | float | bool | None


class StateError(ValueError):
    """Raised when an ecological state declaration or bridge is invalid."""


class CohortStateError(ValueError):
    """Raised when a cohort table cannot be turned into a typed state.

    Parameters
    ----------
    findings : sequence of Problem
        The validation findings.
    """

    def __init__(self, findings: Sequence[Problem]) -> None:
        """Store the findings and build a readable message."""
        self.findings: tuple[Problem, ...] = tuple(findings)
        message = "; ".join(f"{item.code}: {item.message}" for item in self.findings)
        super().__init__(message or "invalid cohort state")


@dataclass(frozen=True)
class StateVariable:
    """One declared ecological state variable.

    Parameters
    ----------
    name : str
        The variable name, unique within the package.
    dtype : str
        One of ``float``, ``int``, ``bool``, or ``string``.
    scope : str
        One of ``cohort``, ``fragment``, ``site``, or ``landscape``.
    unit : str
        The unit label, or an empty string for a dimensionless value.
    default : str, int, float, bool, or None
        The default value, parsed from the package declaration.
    description : str
        A human-readable description.
    """

    name: str
    dtype: str
    scope: str
    unit: str
    default: JsonScalar
    description: str


@dataclass(frozen=True)
class BridgeSpec:
    """One declared bridge from ecological state to management state.

    Parameters
    ----------
    bridge_id : str
        The bridge identifier, unique within the package.
    type : str
        The bridge type. Only ``null`` is implemented.
    params : dict of str to object
        The bridge parameters, parsed from ``params_json``.
    state_reads : tuple of str
        The declared state variables the bridge reads.
    state_writes : tuple of str
        The declared state variables the bridge writes.
    """

    bridge_id: str
    type: str
    params: dict[str, object]
    state_reads: tuple[str, ...]
    state_writes: tuple[str, ...]


@dataclass(frozen=True)
class StateSchema:
    """The declared state variables and bridges of an ecosystem package.

    Parameters
    ----------
    variables : dict of str to StateVariable
        The declared variables by name.
    bridges : tuple of BridgeSpec
        The declared bridges.
    """

    variables: dict[str, StateVariable]
    bridges: tuple[BridgeSpec, ...]

    def variable(self, name: str) -> StateVariable:
        """Return one declared variable.

        Parameters
        ----------
        name : str
            The variable name.

        Returns
        -------
        StateVariable
            The variable.

        Raises
        ------
        KeyError
            If the variable is not declared.
        """
        return self.variables[name]

    def bridge(self, bridge_id: str | None = None) -> BridgeSpec:
        """Return a declared bridge, by id or the first one.

        Parameters
        ----------
        bridge_id : str or None, optional
            The bridge identifier. None returns the first bridge.

        Returns
        -------
        BridgeSpec
            The bridge specification.

        Raises
        ------
        StateError
            If no bridge is declared or the id is unknown.
        """
        if bridge_id is None:
            if not self.bridges:
                raise StateError("the package declares no bridge")
            return self.bridges[0]
        for bridge in self.bridges:
            if bridge.bridge_id == bridge_id:
                return bridge
        raise StateError(f"unknown bridge {bridge_id!r}")

    def null_bridge(self) -> NullBridge:
        """Return the first null bridge.

        Returns
        -------
        NullBridge
            The null bridge.

        Raises
        ------
        StateError
            If the package declares no null bridge.
        """
        for bridge in self.bridges:
            if bridge.type == "null":
                return NullBridge(bridge)
        raise StateError("the package declares no null bridge")


@dataclass(frozen=True)
class NullBridge:
    """The explicit no-op bridge that leaves the management state unchanged.

    Parameters
    ----------
    spec : BridgeSpec
        The bridge specification. Its type must be ``null``.
    """

    spec: BridgeSpec

    def __post_init__(self) -> None:
        """Validate that the specification is a null bridge."""
        if self.spec.type != "null":
            raise StateError(f"bridge {self.spec.bridge_id!r} is not a null bridge")

    def apply(self, management: pd.DataFrame, ecological: pd.DataFrame) -> pd.DataFrame:
        """Return the management frame unchanged.

        Parameters
        ----------
        management : pandas.DataFrame
            The management state, keyed by fragment.
        ecological : pandas.DataFrame
            The aggregated ecological state. The null bridge ignores it.

        Returns
        -------
        pandas.DataFrame
            A shallow copy of the management frame.
        """
        del ecological
        return management.copy(deep=False)


@dataclass(frozen=True)
class CohortState:
    """The typed cohort state of one ecosystem package and one compiled dataset.

    Parameters
    ----------
    cohorts : pandas.DataFrame
        The typed cohort table.
    schema : StateSchema
        The declared state schema.
    fragment_areas : dict of int to float
        The area of every dataset fragment, in hectares.
    """

    cohorts: pd.DataFrame
    schema: StateSchema
    fragment_areas: dict[int, float]

    @classmethod
    def from_tables(
        cls,
        cohorts: pd.DataFrame,
        schema: StateSchema,
        fragment_areas: Mapping[int, float],
    ) -> CohortState:
        """Validate raw cohort rows and build a typed cohort state.

        Parameters
        ----------
        cohorts : pandas.DataFrame
            The raw cohort table, with string values as read from CSV.
        schema : StateSchema
            The declared state schema.
        fragment_areas : mapping of int to float
            The area of every dataset fragment, in hectares.

        Returns
        -------
        CohortState
            The typed cohort state.

        Raises
        ------
        CohortStateError
            If a cohort row is invalid, a fragment is unknown, or the area fractions of a
            fragment do not sum to one.
        """
        areas = {int(fragment): float(area) for fragment, area in fragment_areas.items()}
        for fragment, area in areas.items():
            if fragment <= 0:
                raise CohortStateError(
                    [
                        problem(
                            "ECOSYSTEM-FRAGMENT-ID",
                            str(fragment),
                            "fragment id must be positive",
                        )
                    ]
                )
            if not math.isfinite(area) or area <= 0.0:
                raise CohortStateError(
                    [
                        problem(
                            "ECOSYSTEM-FRAGMENT-AREA",
                            str(fragment),
                            "fragment area must be finite and positive",
                        )
                    ]
                )
        typed, findings = _typed_cohorts(cohorts, schema)
        unknown = sorted(set(typed["fragment_id"]) - set(areas))
        for fragment in unknown:
            findings.append(
                problem(
                    "ECOSYSTEM-UNKNOWN-FRAGMENT",
                    str(fragment),
                    "the cohort table names a fragment outside the dataset",
                )
            )
        if findings:
            raise CohortStateError(findings)
        return cls(cohorts=typed, schema=schema, fragment_areas=areas)

    def aggregate_to_fragments(self) -> pd.DataFrame:
        """Aggregate cohorts to area-weighted fragment state.

        Returns
        -------
        pandas.DataFrame
            One row per fragment with cohorts: ``fragment_id``, ``area_ha``,
            ``cohort_count``, and area-weighted ``age``, ``biomass_t_ha``, ``fuel_t_ha``,
            and ``snag_t_ha``.
        """
        columns = [
            "fragment_id",
            "area_ha",
            "cohort_count",
            "age",
            "biomass_t_ha",
            "fuel_t_ha",
            "snag_t_ha",
        ]
        if self.cohorts.empty:
            return pd.DataFrame(columns=columns)
        rows: list[dict[str, object]] = []
        for fragment_id, group in self.cohorts.groupby("fragment_id", sort=True):
            total = float(group["area_fraction"].sum())
            if total <= 0.0:
                continue
            rows.append(
                {
                    "fragment_id": _key_int(fragment_id),
                    "area_ha": self.fragment_areas[_key_int(fragment_id)],
                    "cohort_count": len(group),
                    "age": float((group["age"] * group["area_fraction"]).sum() / total),
                    "biomass_t_ha": float(
                        (group["biomass_t_ha"] * group["area_fraction"]).sum() / total
                    ),
                    "fuel_t_ha": float((group["fuel_t_ha"] * group["area_fraction"]).sum() / total),
                    "snag_t_ha": float((group["snag_t_ha"] * group["area_fraction"]).sum() / total),
                }
            )
        return pd.DataFrame(rows, columns=columns)

    def species_fractions(self) -> pd.DataFrame:
        """Return the species area fractions of every fragment.

        Returns
        -------
        pandas.DataFrame
            One row per fragment and species with ``fragment_id``, ``species``,
            ``area_fraction``, and ``area_ha``.
        """
        columns = ["fragment_id", "species", "area_fraction", "area_ha"]
        if self.cohorts.empty:
            return pd.DataFrame(columns=columns)
        grouped = (
            self.cohorts.groupby(["fragment_id", "species"], sort=True)["area_fraction"]
            .sum()
            .reset_index()
        )
        grouped["fragment_id"] = grouped["fragment_id"].astype(int)
        grouped["area_ha"] = grouped["area_fraction"] * grouped["fragment_id"].map(
            self.fragment_areas
        )
        return grouped[columns]

    def cohort_areas(self) -> pd.DataFrame:
        """Return the cohort table with its fragment area and absolute cohort area.

        Returns
        -------
        pandas.DataFrame
            The cohort rows plus ``fragment_area_ha`` and ``area_ha``.
        """
        frame = self.cohorts.copy()
        frame["fragment_area_ha"] = [
            self.fragment_areas[int(fragment)] for fragment in frame["fragment_id"]
        ]
        frame["area_ha"] = frame["area_fraction"] * frame["fragment_area_ha"]
        return frame

    def missing_fragments(self) -> tuple[int, ...]:
        """Return the dataset fragments that the package does not cover.

        Returns
        -------
        tuple of int
            The sorted fragment ids without cohorts.
        """
        covered = {int(fragment) for fragment in self.cohorts["fragment_id"]}
        return tuple(sorted(set(self.fragment_areas) - covered))

    def check_area_conservation(self) -> None:
        """Check that every covered fragment's cohorts fill its area exactly.

        Raises
        ------
        CohortStateError
            If a fragment's area fractions do not sum to one or its cohort areas do not
            sum to the fragment area.
        """
        findings: list[Problem] = []
        for fragment_id, group in self.cohorts.groupby("fragment_id", sort=True):
            fraction = float(group["area_fraction"].sum())
            if abs(fraction - 1.0) > FRACTION_TOLERANCE:
                findings.append(
                    problem(
                        "ECOSYSTEM-COHORT-FRACTION",
                        str(_key_int(fragment_id)),
                        f"area fractions sum to {fraction:.9f}, not 1",
                    )
                )
            fragment_area = self.fragment_areas[_key_int(fragment_id)]
            area = float((group["area_fraction"] * fragment_area).sum())
            expected = self.fragment_areas[_key_int(fragment_id)]
            if abs(area - expected) > FRACTION_TOLERANCE * max(1.0, expected):
                findings.append(
                    problem(
                        "ECOSYSTEM-COHORT-AREA",
                        str(_key_int(fragment_id)),
                        f"cohort area {area:.9f} ha does not match {expected:.9f} ha",
                    )
                )
        if findings:
            raise CohortStateError(findings)


def problem(code: str, where: str, message: str) -> Problem:
    """Build one validation finding.

    Parameters
    ----------
    code : str
        The stable finding code.
    where : str
        The file, field, or row the finding applies to.
    message : str
        A human-readable description.

    Returns
    -------
    Problem
        The finding.
    """
    return Problem(code, where, message)


def _key_int(value: object) -> int:
    """Return an integer from a group key or array scalar."""
    return int(str(value))


def _text(value: object, field: str) -> str:
    """Return a stripped string, allowing an empty value."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise StateError(f"{field} must be a string")
    return value.strip()


def _integer(value: object, field: str) -> int:
    """Return an integer parsed from a string or an integer."""
    if isinstance(value, bool):
        raise StateError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as error:
            raise StateError(f"{field} must be an integer") from error
    raise StateError(f"{field} must be an integer")


def _number(value: object, field: str) -> float:
    """Return a finite float parsed from a string or a number."""
    if isinstance(value, bool):
        raise StateError(f"{field} must be a number")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError as error:
            raise StateError(f"{field} must be a number") from error
    else:
        raise StateError(f"{field} must be a number")
    if not math.isfinite(number):
        raise StateError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _bool(value: object, field: str) -> bool:
    """Return a boolean parsed from a string or a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "false"}:
            return text == "true"
    raise StateError(f"{field} must be true or false")


def _default(value: object, dtype: str, field: str) -> JsonScalar:
    """Return a typed default value, or None for an empty declaration."""
    text = _text(value, field)
    if text == "":
        return None
    if dtype == "float":
        return _number(text, field)
    if dtype == "int":
        return _integer(text, field)
    if dtype == "bool":
        return _bool(text, field)
    return text


def _json_object(value: object, field: str, *, scalars_only: bool) -> dict[str, object]:
    """Return a JSON object, optionally restricted to scalar values."""
    text = _text(value, field)
    if text == "":
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise StateError(f"{field} must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise StateError(f"{field} must be a JSON object")
    result: dict[str, object] = {}
    for key, item in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise StateError(f"{field} keys must be non-empty strings")
        if scalars_only and not (item is None or isinstance(item, (str, int, float, bool))):
            raise StateError(f"{field} values must be JSON scalars")
        if isinstance(item, float) and not math.isfinite(item):
            raise StateError(f"{field} values must be finite")
        result[key.strip()] = item
    return result


def _typed_value(value: object, dtype: str, field: str) -> JsonScalar:
    """Return one value coerced to the declared dtype."""
    if value is None:
        return None
    if dtype == "float":
        return _number(value, field)
    if dtype == "int":
        return _integer(value, field)
    if dtype == "bool":
        return _bool(value, field)
    if not isinstance(value, str):
        raise StateError(f"{field} must be a string")
    return value


def _parse_state_variables(frame: pd.DataFrame) -> tuple[dict[str, StateVariable], list[Problem]]:
    """Parse and validate the state-variable table."""
    findings: list[Problem] = []
    variables: dict[str, StateVariable] = {}
    for index, row in frame.iterrows():
        where = f"state_variables[{index}]"
        try:
            name = _text(row["name"], f"{where}.name")
            if not name:
                raise StateError("name must be non-empty")
            if name in variables:
                raise StateError(f"duplicate state variable {name!r}")
            dtype = _text(row["dtype"], f"{where}.dtype")
            if dtype not in STATE_DTYPES:
                raise StateError(f"dtype must be one of {', '.join(STATE_DTYPES)}")
            scope = _text(row["scope"], f"{where}.scope")
            if scope not in STATE_SCOPES:
                raise StateError(f"scope must be one of {', '.join(STATE_SCOPES)}")
            variables[name] = StateVariable(
                name=name,
                dtype=dtype,
                scope=scope,
                unit=_text(row["unit"], f"{where}.unit"),
                default=_default(row["default"], dtype, f"{where}.default"),
                description=_text(row["description"], f"{where}.description"),
            )
        except StateError as error:
            findings.append(problem("ECOSYSTEM-STATE", where, str(error)))
    for name, expected in FIXED_COHORT_VARIABLES.items():
        variable = variables.get(name)
        if variable is None:
            findings.append(
                problem(
                    "ECOSYSTEM-STATE-MISSING",
                    f"state_variables.{name}",
                    f"the cohort state requires {name!r}",
                )
            )
            continue
        if variable.dtype != expected or variable.scope != "cohort":
            findings.append(
                problem(
                    "ECOSYSTEM-STATE-TYPE",
                    f"state_variables.{name}",
                    f"expected dtype {expected!r} and scope 'cohort'",
                )
            )
    return variables, findings


def _parse_bridges(
    frame: pd.DataFrame, variables: Mapping[str, StateVariable]
) -> tuple[tuple[BridgeSpec, ...], list[Problem]]:
    """Parse and validate the bridge table."""
    findings: list[Problem] = []
    bridges: list[BridgeSpec] = []
    seen: set[str] = set()
    if frame.empty:
        findings.append(
            problem(
                "ECOSYSTEM-BRIDGE-MISSING",
                "bridges",
                "the package must declare at least one bridge",
            )
        )
        return (), findings
    for index, row in frame.iterrows():
        where = f"bridges[{index}]"
        try:
            bridge_id = _text(row["bridge_id"], f"{where}.bridge_id")
            if not bridge_id:
                raise StateError("bridge_id must be non-empty")
            if bridge_id in seen:
                raise StateError(f"duplicate bridge {bridge_id!r}")
            seen.add(bridge_id)
            bridge_type = _text(row["type"], f"{where}.type")
            if bridge_type != "null":
                raise StateError(
                    f"bridge type {bridge_type!r} is not implemented; only 'null' is supported"
                )
            params = _json_object(row["params_json"], f"{where}.params_json", scalars_only=False)
            reads = _names(row["state_reads"], f"{where}.state_reads")
            writes = _names(row["state_writes"], f"{where}.state_writes")
            for name in reads + writes:
                if name not in variables:
                    raise StateError(f"unknown state variable {name!r}")
            if writes:
                raise StateError("the null bridge must not declare state_writes")
            bridges.append(
                BridgeSpec(
                    bridge_id=bridge_id,
                    type=bridge_type,
                    params=params,
                    state_reads=reads,
                    state_writes=writes,
                )
            )
        except StateError as error:
            findings.append(problem("ECOSYSTEM-BRIDGE", where, str(error)))
    return tuple(bridges), findings


def _names(value: object, field: str) -> tuple[str, ...]:
    """Return a semicolon-separated list of state-variable names."""
    text = _text(value, field)
    if not text:
        return ()
    names = tuple(part.strip() for part in text.split(";") if part.strip())
    if len(set(names)) != len(names):
        raise StateError(f"{field} names must be unique")
    return names


def _parse_state_schema(
    state_variables: pd.DataFrame, bridges: pd.DataFrame
) -> tuple[StateSchema, list[Problem]]:
    """Parse the state schema and return every finding."""
    variables, findings = _parse_state_variables(state_variables)
    bridge_specs, bridge_findings = _parse_bridges(bridges, variables)
    findings.extend(bridge_findings)
    return StateSchema(variables=variables, bridges=bridge_specs), findings


def _typed_cohorts(frame: pd.DataFrame, schema: StateSchema) -> tuple[pd.DataFrame, list[Problem]]:
    """Validate raw cohort rows and return a typed frame plus findings."""
    findings: list[Problem] = []
    rows: list[dict[str, object]] = []
    fractions: dict[int, float] = {}
    seen: set[tuple[int, int]] = set()
    for index, row in frame.iterrows():
        where = f"cohorts[{index}]"
        try:
            fragment_id = _integer(row["fragment_id"], f"{where}.fragment_id")
            if fragment_id <= 0:
                raise StateError("fragment_id must be positive")
            cohort_id = _integer(row["cohort_id"], f"{where}.cohort_id")
            if cohort_id <= 0:
                raise StateError("cohort_id must be positive")
            key = (fragment_id, cohort_id)
            if key in seen:
                raise StateError(f"duplicate cohort {key}")
            seen.add(key)
            species = _text(row["species"], f"{where}.species")
            if not species:
                raise StateError("species must be non-empty")
            age = _integer(row["age"], f"{where}.age")
            if age < 0:
                raise StateError("age must be non-negative")
            fraction = _number(row["area_fraction"], f"{where}.area_fraction")
            if fraction <= 0.0 or fraction > 1.0:
                raise StateError("area_fraction must be in (0, 1]")
            biomass = _cohort_number(row, "biomass_t_ha", schema, where)
            fuel = _cohort_number(row, "fuel_t_ha", schema, where)
            snag = _cohort_number(row, "snag_t_ha", schema, where)
            attributes = _json_object(
                row["attributes_json"], f"{where}.attributes_json", scalars_only=True
            )
            for name, value in attributes.items():
                variable = schema.variables.get(name)
                if variable is None or variable.scope != "cohort":
                    raise StateError(f"unknown cohort attribute {name!r}")
                if name in FIXED_COHORT_VARIABLES:
                    raise StateError(f"attribute {name!r} is already a cohort column")
                _typed_value(value, variable.dtype, f"{where}.attributes_json.{name}")
            fractions[fragment_id] = fractions.get(fragment_id, 0.0) + fraction
            rows.append(
                {
                    "fragment_id": fragment_id,
                    "cohort_id": cohort_id,
                    "species": species,
                    "age": age,
                    "area_fraction": fraction,
                    "biomass_t_ha": biomass,
                    "fuel_t_ha": fuel,
                    "snag_t_ha": snag,
                    "attributes_json": _text(row["attributes_json"], f"{where}.attributes_json"),
                }
            )
        except StateError as error:
            findings.append(problem("ECOSYSTEM-COHORT", where, str(error)))
    for fragment_id, total in sorted(fractions.items()):
        if abs(total - 1.0) > FRACTION_TOLERANCE:
            findings.append(
                problem(
                    "ECOSYSTEM-COHORT-FRACTION",
                    str(fragment_id),
                    f"area fractions sum to {total:.9f}, not 1",
                )
            )
    columns = [
        "fragment_id",
        "cohort_id",
        "species",
        "age",
        "area_fraction",
        "biomass_t_ha",
        "fuel_t_ha",
        "snag_t_ha",
        "attributes_json",
    ]
    return pd.DataFrame(rows, columns=columns), findings


def _cohort_number(row: pd.Series, name: str, schema: StateSchema, where: str) -> float:
    """Return a cohort numeric value, falling back to the declared default."""
    raw = _text(row[name], f"{where}.{name}")
    if raw != "":
        value = _number(raw, f"{where}.{name}")
        if value < 0.0:
            raise StateError(f"{name} must be non-negative")
        return value
    variable = schema.variables.get(name)
    if variable is None or not isinstance(variable.default, (int, float)):
        raise StateError(f"{name} is blank and has no numeric default")
    value = float(variable.default)
    if value < 0.0:
        raise StateError(f"{name} default must be non-negative")
    return value
