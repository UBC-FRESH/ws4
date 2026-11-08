"""Contract tests for regime sequences and AU constraints."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from ws4.sdmd.constraints import (
    AuConstraint,
    SdmdConstraintError,
    allowed_regimes,
    check_regime,
    load_constraints,
    option_counts,
    validate_constraint,
    validate_constraints,
)
from ws4.sdmd.regimes import (
    Regime,
    SdmdRegimeError,
    available_regimes,
    get_regime,
    load_regime_library,
    validate_regime,
    validate_regime_library,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"


def _regimes() -> tuple[Regime, ...]:
    """Load the fixture regime library.

    Returns
    -------
    tuple of Regime
        The 13 fixture regimes.
    """
    return load_regime_library(pd.read_csv(FIXTURE / "regimes.csv"))


def _constraints() -> tuple[AuConstraint, ...]:
    """Load the fixture constraint table.

    Returns
    -------
    tuple of AuConstraint
        The 13 fixture constraints.
    """
    return load_constraints(pd.read_csv(FIXTURE / "au_constraints.csv"))


def _constraint(regime_id: str) -> AuConstraint:
    """Return one fixture constraint by regime id.

    Parameters
    ----------
    regime_id : str
        The regime identifier.

    Returns
    -------
    AuConstraint
        The matching constraint.
    """
    return next(item for item in _constraints() if item.regime_id == regime_id)


def test_fixture_library_has_the_two_au_regimes() -> None:
    """The fixture carries 13 regimes across two AUs."""
    regimes = _regimes()
    assert len(regimes) == 13
    assert {item.au_id for item in regimes} == {"AU-IDFdk3-FDI", "AU-IDFdk3-PLI"}


def test_available_regimes_filters_by_au_and_sdmd() -> None:
    """The AU filter and the even-aged filter compose."""
    regimes = _regimes()
    assert len(available_regimes(regimes, "AU-IDFdk3-FDI")) == 7
    assert len(available_regimes(regimes, "AU-IDFdk3-FDI", sdmd_only=True)) == 6
    assert len(available_regimes(regimes, "AU-IDFdk3-PLI")) == 6


def test_entry_ages_expand_the_cycle() -> None:
    """A repeated entry is a sequence, not one age."""
    shelterwood = get_regime(_regimes(), "REG-A-SHELTERWOOD40")
    assert shelterwood.entry_ages() == (90, 110)
    assert shelterwood.entry_count() == 2


def test_untreated_has_no_entries() -> None:
    """The baseline is not an entry."""
    untreated = get_regime(_regimes(), "REG-A-UNTREATED")
    assert untreated.is_untreated
    assert untreated.entry_ages() == ()
    assert untreated.entry_count() == 0


def test_selection_is_outside_the_even_aged_diagram() -> None:
    """The diagram does not describe selection regimes."""
    selection = get_regime(_regimes(), "REG-A-SELECTION80")
    assert not selection.is_sdmd_valid
    assert get_regime(_regimes(), "REG-A-CT60").is_sdmd_valid


def test_get_regime_rejects_an_unknown_id() -> None:
    """An unknown regime is a named error."""
    with pytest.raises(SdmdRegimeError, match="unknown regime"):
        get_regime(_regimes(), "REG-MISSING")


def test_regime_serializes() -> None:
    """The regime payload is JSON-serializable."""
    payload = get_regime(_regimes(), "REG-A-VR20").to_dict()
    assert payload["entry_ages"] == [75, 90]
    assert payload["sdmd_valid"] is True
    json.dumps(payload)


def test_valid_library_has_no_findings() -> None:
    """The fixture library is internally consistent."""
    assert validate_regime_library(_regimes()) == []


def test_regime_rejects_an_unknown_entry_type() -> None:
    """The entry type is a closed set."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), entry_type="seedtree")
    assert "SDMD-REGIME-ENTRY-TYPE" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_a_negative_entry_age() -> None:
    """An entry age is not negative."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), entry_age=-1)
    assert "SDMD-REGIME-AGE" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_an_out_of_range_removal() -> None:
    """A removal fraction is a fraction."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), removal_fraction=1.5)
    assert "SDMD-REGIME-REMOVAL" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_a_repeat_without_a_cycle() -> None:
    """Repeating an entry needs a positive interval."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), repeat_count=2, cycle_length=0)
    assert "SDMD-REGIME-CYCLE" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_a_treated_untreated_baseline() -> None:
    """The baseline removes no basal area."""
    regime = replace(get_regime(_regimes(), "REG-A-UNTREATED"), removal_fraction=0.2)
    assert "SDMD-REGIME-UNTREATED" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_a_blank_identity() -> None:
    """An empty id or name is not a regime."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), regime_id="  ")
    assert "SDMD-REGIME-FIELD" in {item.code for item in validate_regime(regime)}


def test_regime_rejects_a_bad_review_status() -> None:
    """Review status is a closed set."""
    regime = replace(get_regime(_regimes(), "REG-A-CT60"), review_status="signed-off")
    assert "SDMD-REGIME-REVIEW" in {item.code for item in validate_regime(regime)}


def test_library_rejects_a_duplicate_regime() -> None:
    """Two regimes with one id would be indistinguishable."""
    regimes = _regimes()
    problems = validate_regime_library((*regimes, regimes[0]))
    assert "SDMD-REGIME-DUPLICATE" in {item.code for item in problems}


def test_load_library_rejects_a_schema_problem() -> None:
    """A bad removal fraction fails at load."""
    frame = pd.read_csv(FIXTURE / "regimes.csv")
    frame.loc[0, "removal_fraction"] = 1.5
    with pytest.raises(SdmdRegimeError, match="SDMD-RANGE"):
        load_regime_library(frame)


def test_fixture_constraints_load() -> None:
    """The fixture carries one constraint per regime."""
    constraints = _constraints()
    assert len(constraints) == 13
    assert sum(1 for item in constraints if item.allowed) == 12


def test_load_constraints_rejects_an_inverted_window() -> None:
    """A minimum above a maximum is contradictory."""
    frame = pd.read_csv(FIXTURE / "au_constraints.csv")
    frame.loc[0, "min_entry_age"] = 120
    frame.loc[0, "max_entry_age"] = 60
    with pytest.raises(SdmdConstraintError):
        load_constraints(frame)


def test_load_constraints_rejects_a_duplicate_key() -> None:
    """One AU/regime pair has one constraint."""
    frame = pd.read_csv(FIXTURE / "au_constraints.csv")
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(SdmdConstraintError):
        load_constraints(frame)


def test_validate_constraint_rejects_bad_fields() -> None:
    """Field limits, review status, and zone are closed or bounded."""
    constraint = _constraint("REG-A-CT60")
    assert validate_constraint(constraint) == []
    assert "SDMD-CONSTRAINT-RANGE" in {
        item.code for item in validate_constraint(replace(constraint, max_entries=-1))
    }
    assert "SDMD-CONSTRAINT-WINDOW" in {
        item.code
        for item in validate_constraint(replace(constraint, min_entry_age=100, max_entry_age=90))
    }
    assert "SDMD-CONSTRAINT-REMOVAL" in {
        item.code for item in validate_constraint(replace(constraint, max_removal_fraction=1.5))
    }
    assert "SDMD-CONSTRAINT-ZONE" in {
        item.code for item in validate_constraint(replace(constraint, required_sdmd_zone="unknown"))
    }
    assert "SDMD-CONSTRAINT-REVIEW" in {
        item.code for item in validate_constraint(replace(constraint, review_status="pending"))
    }
    assert "SDMD-CONSTRAINT-FIELD" in {
        item.code for item in validate_constraint(replace(constraint, source="  "))
    }


def test_validate_constraints_rejects_a_duplicate() -> None:
    """The pair key is unique in the object table too."""
    constraints = _constraints()
    problems = validate_constraints((*constraints, constraints[0]))
    assert "SDMD-CONSTRAINT-DUPLICATE" in {item.code for item in problems}


def test_check_regime_accepts_an_allowed_regime() -> None:
    """The fixture clearcut satisfies its constraint."""
    assert (
        check_regime(_constraint("REG-A-CLEARCUT"), get_regime(_regimes(), "REG-A-CLEARCUT")) == []
    )


def test_check_regime_reports_a_denied_regime() -> None:
    """A denied regime fails closed."""
    problems = check_regime(_constraint("REG-B-CLEARCUT"), get_regime(_regimes(), "REG-B-CLEARCUT"))
    assert "SDMD-CONSTRAINT-DENIED" in {item.code for item in problems}


def test_check_regime_reports_a_mismatched_pair() -> None:
    """A constraint only applies to its own regime."""
    problems = check_regime(_constraint("REG-A-CT60"), get_regime(_regimes(), "REG-A-FUEL50"))
    assert "SDMD-CONSTRAINT-REGIME" in {item.code for item in problems}


def test_check_regime_reports_an_entry_window_violation() -> None:
    """The first entry must fall inside the window."""
    constraint = replace(_constraint("REG-A-CT60"), min_entry_age=100)
    problems = check_regime(constraint, get_regime(_regimes(), "REG-A-CT60"))
    assert "SDMD-CONSTRAINT-ENTRY" in {item.code for item in problems}


def test_check_regime_reports_an_entry_cap_violation() -> None:
    """A repeated regime can exceed the entry cap."""
    constraint = replace(_constraint("REG-A-SHELTERWOOD40"), max_entries=1)
    problems = check_regime(constraint, get_regime(_regimes(), "REG-A-SHELTERWOOD40"))
    assert "SDMD-CONSTRAINT-ENTRIES" in {item.code for item in problems}


def test_check_regime_reports_an_interval_violation() -> None:
    """A cycle shorter than the minimum interval is forbidden."""
    constraint = replace(_constraint("REG-A-VR20"), min_interval_years=30)
    problems = check_regime(constraint, get_regime(_regimes(), "REG-A-VR20"))
    assert "SDMD-CONSTRAINT-INTERVAL" in {item.code for item in problems}


def test_check_regime_reports_a_removal_violation() -> None:
    """A removal above the AU limit is forbidden."""
    constraint = replace(_constraint("REG-A-CLEARCUT"), max_removal_fraction=0.3)
    problems = check_regime(constraint, get_regime(_regimes(), "REG-A-CLEARCUT"))
    assert "SDMD-CONSTRAINT-REMOVAL" in {item.code for item in problems}


def test_check_regime_exempts_the_untreated_baseline() -> None:
    """The baseline is not an entry and has no window."""
    constraint = replace(_constraint("REG-A-UNTREATED"), min_entry_age=90)
    assert check_regime(constraint, get_regime(_regimes(), "REG-A-UNTREATED")) == []


def test_check_regime_flags_selection_outside_the_diagram() -> None:
    """A required SDMD zone cannot be met by a selection regime."""
    problems = check_regime(
        _constraint("REG-A-SELECTION80"), get_regime(_regimes(), "REG-A-SELECTION80")
    )
    assert "SDMD-REGIME-OUTSIDE-SDMD" in {item.code for item in problems}


def test_allowed_regimes_filters_both_aus() -> None:
    """The allowed set drops a denied clearcut and an out-of-diagram selection."""
    constraints = _constraints()
    regimes = _regimes()
    first = allowed_regimes(regimes, constraints, "AU-IDFdk3-FDI")
    second = allowed_regimes(regimes, constraints, "AU-IDFdk3-PLI")
    assert len(first) == 6
    assert len(second) == 5
    assert "REG-A-SELECTION80" not in {item.regime_id for item in first}
    assert "REG-B-CLEARCUT" not in {item.regime_id for item in second}


def test_option_counts_report_the_reduction() -> None:
    """The before and after counts are the benchmark's input."""
    constraints = _constraints()
    regimes = _regimes()
    before = available_regimes(regimes, "AU-IDFdk3-FDI")
    after = allowed_regimes(regimes, constraints, "AU-IDFdk3-FDI")
    counts = option_counts(before, after)
    assert counts == {
        "regimes_before": 7,
        "regimes_after": 6,
        "entries_before": 11,
        "entries_after": 7,
    }
