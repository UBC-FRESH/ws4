"""Unit tests for the public-docstring auditor.

Every finding code is made to fire on a fixture that carries exactly that defect, and the real
scope is asserted clean, so the gate cannot pass by silently checking nothing.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import doc_audit

FIXTURE_PACKAGE: str = "docaudit_pkg"
FIXTURES: Path = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_codes(monkeypatch: pytest.MonkeyPatch) -> set[tuple[str, str]]:
    """Return the ``(name, code)`` findings of the fixture package."""
    monkeypatch.syspath_prepend(str(FIXTURES))
    return {(finding.name, finding.code) for finding in doc_audit.audit(FIXTURE_PACKAGE, None)}


def _variadic(a: int, *args: int, **kwargs: str) -> int:
    """Return ``a``, with parameters the audit must not require.

    Parameters
    ----------
    a : int
        The value to return.
    *args : int
        Extra positional values.
    **kwargs : str
        Extra keyword values.

    Returns
    -------
    int
        The value of ``a``.
    """
    del args, kwargs
    return a


def test_the_audit_scope_is_clean() -> None:
    """The package and the scripts, which the gate runs on, are complete."""
    assert doc_audit.audit() == []


def test_a_missing_docstring_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.no_docstring", "MISSING") in fixture_codes


def test_an_undocumented_parameter_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.undocumented", "PARAMS") in fixture_codes


def test_a_stale_parameter_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.stale", "STALE") in fixture_codes


def test_a_missing_returns_section_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.no_returns", "RETURNS") in fixture_codes


def test_a_module_without_a_docstring_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.nodoc", "MISSING") in fixture_codes


def test_an_unimportable_module_is_reported(fixture_codes: set[tuple[str, str]]) -> None:
    assert (f"{FIXTURE_PACKAGE}.broken", "IMPORT") in fixture_codes


def test_complete_objects_are_not_reported(fixture_codes: set[tuple[str, str]]) -> None:
    """A complete docstring, a documented dataclass, a derived attribute, and a protocol pass."""
    clean = {
        f"{FIXTURE_PACKAGE}.good",
        f"{FIXTURE_PACKAGE}.Documented",
        f"{FIXTURE_PACKAGE}.WithDerived",
        f"{FIXTURE_PACKAGE}.WithDerived.doubled",
        f"{FIXTURE_PACKAGE}.Shape",
        f"{FIXTURE_PACKAGE}.Shape.apply",
        f"{FIXTURE_PACKAGE}.Thing",
        f"{FIXTURE_PACKAGE}.Thing.value",
        f"{FIXTURE_PACKAGE}.Thing.undocumented",
    }
    assert {name for name, _ in fixture_codes} & clean == set()
    assert not any(name.endswith("_private_helper") for name, _ in fixture_codes)


def test_a_section_without_a_blank_line_before_it_is_reported() -> None:
    """A header that follows a description is read as part of it, so the section is lost."""

    def rushed(a: int) -> bool:
        """Return whether ``a`` is positive.

        Parameters
        ----------
        a : int
            The value.
        Returns
        -------
        bool
            Whether ``a`` is positive.
        """
        return a > 0

    findings = doc_audit.check_object("rushed", rushed)
    assert [finding.code for finding in findings] == ["SECTION"]
    assert "blank line" in findings[0].detail


def test_section_entries_reads_a_parameters_section() -> None:
    doc = """Return a value.

    Parameters
    ----------
    first : int
        The first value, whose description may wrap
        onto a second line.
    second, third : int
        Two names on one line.

    Returns
    -------
    int
        The value.
    """
    assert doc_audit.section_entries(doc, "Parameters") == ("first", "second", "third")
    assert doc_audit.section_entries(doc, "Raises") == ()
    assert doc_audit.documented_names(doc) == ("first", "second", "third")
    assert doc_audit.parameter_entries(doc) == ("first", "second", "third")
    assert doc_audit.has_section(doc, "Returns", "Yields")
    assert not doc_audit.has_section(doc, "Notes")


def test_a_section_ends_at_the_next_header() -> None:
    """A later section's entries must not be read as this section's parameters."""
    doc = """A class.

    Parameters
    ----------
    given : int
        The argument.

    Attributes
    ----------
    derived : int
        An attribute.
    """
    assert doc_audit.section_entries(doc, "Parameters") == ("given",)
    assert doc_audit.section_entries(doc, "Attributes") == ("derived",)
    assert doc_audit.parameter_entries(doc) == ("given",)


def test_signature_parameters_returns_none_for_an_uninspectable_object() -> None:
    assert doc_audit.signature_parameters(object()) is None


def test_returns_value_handles_none_and_constructors() -> None:
    def annotated_none(a: int) -> None:
        """Take a value and return nothing."""

    def annotated_value(a: int) -> int:
        """Return the value."""
        return a

    class Holder:
        def __init__(self) -> None:
            """Hold nothing."""

    assert not doc_audit.returns_value(annotated_none)
    assert doc_audit.returns_value(annotated_value)
    assert doc_audit.returns_value(print)  # a builtin, whose signature has no annotation
    assert not doc_audit.returns_value(Holder.__init__)
    assert not doc_audit.returns_value(object())


def test_variadic_parameters_are_optional_to_document() -> None:
    parameters = list(inspect.signature(_variadic).parameters.values())
    assert doc_audit.parameter_findings("variadic", parameters, ("a",), ("a",)) == []
    assert doc_audit.parameter_findings("variadic", parameters, ("a", "args"), ("a", "args")) == []
    findings = doc_audit.parameter_findings("variadic", parameters, ("a", "gone"), ("a", "gone"))
    assert [finding.code for finding in findings] == ["STALE"]


def test_a_class_reports_its_member_findings() -> None:
    class Half:
        """A class whose method is incomplete.

        Parameters
        ----------
        a : int
            The value.
        """

        def __init__(self, a: int) -> None:
            self.a = a

        def value(self, b: int) -> int:
            """Return the held value.

            Returns
            -------
            int
                The value.
            """
            del b
            return self.a

    findings = doc_audit.check_object("Half", Half) + doc_audit.member_findings("Half", Half)
    assert [(finding.name, finding.code) for finding in findings] == [("Half.value", "PARAMS")]


def test_main_reports_a_clean_scope(capsys: pytest.CaptureFixture[str]) -> None:
    assert doc_audit.main([]) == 0
    assert "every public docstring is complete" in capsys.readouterr().out


def test_main_reports_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.syspath_prepend(str(FIXTURES))
    code = doc_audit.main(["--package", FIXTURE_PACKAGE, "--scripts-dir", str(tmp_path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "MISSING" in out
    assert "incomplete docstring(s)" in out
