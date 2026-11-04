"""AU label and BEC/TSA integrity checks.

The AU identifier encodes the BEC label, an optional TSA, and a species group,
for example ``AU-IDFdk3-TSA23-FDI``. This module refuses a malformed label, an
unknown BEC label, or a TSA/BEC pair that has no public PSP support.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .schema import Problem

__all__ = [
    "AuParts",
    "default_bec_aliases",
    "default_bec_labels",
    "default_official_bec_labels",
    "default_retired_bec_versions",
    "default_tsa_bec_counts",
    "load_tsa_bec_counts",
    "normalize_bec_label",
    "normalize_tsa",
    "parse_au_label",
    "validate_au_integrity",
    "validate_au_metadata",
]

_DEFAULT_DATA = Path(__file__).resolve().parent / "data" / "sdmd"

_AU_LABEL = re.compile(r"^AU-(?P<bec>[A-Za-z]+\w*?)(?:-TSA(?P<tsa>\d+))?-(?P<species>[A-Za-z]+)$")


@dataclass(frozen=True)
class AuParts:
    """The decoded parts of an AU label.

    Attributes
    ----------
    bec : str
        BEC label, without the ``AU-`` prefix.
    tsa : str or None
        TSA number, when the label carries one.
    species : str
        Species group code.
    """

    bec: str
    tsa: str | None
    species: str


def parse_au_label(label: str) -> AuParts:
    """Parse an AU label.

    Parameters
    ----------
    label : str
        An identifier such as ``AU-IDFdk3-TSA23-FDI``.

    Returns
    -------
    AuParts
        The decoded parts.

    Raises
    ------
    ValueError
        If the label does not match the AU convention.
    """
    match = _AU_LABEL.match(label.strip())
    if match is None:
        raise ValueError(f"AU label must look like AU-<bec>[-TSA<number>]-<species>, got {label!r}")
    return AuParts(
        bec=match.group("bec"),
        tsa=match.group("tsa"),
        species=match.group("species"),
    )


@lru_cache(maxsize=1)
def default_bec_aliases() -> Mapping[str, str]:
    """Return phase and spelling aliases mapped to canonical BEC labels.

    Returns
    -------
    mapping of str to str
        Alias labels from the BECdb ``bgc_no_space`` field mapped to ``bec``.
    """
    aliases: dict[str, str] = {}
    for name in ("bec_official.csv", "bec_retired.csv"):
        frame = pd.read_csv(_DEFAULT_DATA / name, dtype=str).fillna("")
        for row in frame.itertuples(index=False):
            canonical = str(row.bec).strip()
            for alias in str(row.bgc_no_space).split(";"):
                alias = alias.strip()
                if alias and alias != canonical:
                    aliases[alias] = canonical
    return aliases


def normalize_bec_label(label: str) -> str:
    """Return a canonical BEC label without spaces or a phase alias.

    Parameters
    ----------
    label : str
        A BEC label, possibly a phase or an alias such as ``ICHmc1a``.

    Returns
    -------
    str
        The canonical BEC label, or the compact input when no alias exists.
    """
    compact = "".join(str(label).split())
    return default_bec_aliases().get(compact, compact)


def normalize_tsa(value: object) -> str | None:
    """Return the numeric TSA part of a value, or None.

    Parameters
    ----------
    value : object
        A TSA value such as ``TSA-24``, ``TSA 24``, ``24``, or an integer.

    Returns
    -------
    str or None
        The first digit run, or None when the value has no digits.
    """
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else None


def validate_au_metadata(
    label: str,
    *,
    bec_labels: Collection[str],
    tsa_labels: Collection[str],
) -> tuple[Problem, ...]:
    """Compare an AU label with its plot BEC and TSA columns.

    Parameters
    ----------
    label : str
        The AU identifier.
    bec_labels : collection of str
        BEC labels from the plot rows for this AU.
    tsa_labels : collection of str
        TSA values from the plot rows for this AU.

    Returns
    -------
    tuple of Problem
        Mismatch findings; empty when the columns agree with the label.
    """
    try:
        parts = parse_au_label(label)
    except ValueError as error:
        return (Problem("SDMD-AU-LABEL", label, str(error)),)
    findings: list[Problem] = []
    expected_bec = normalize_bec_label(parts.bec)
    normal_becs = {normalize_bec_label(value) for value in bec_labels if str(value).strip()}
    if not normal_becs:
        findings.append(Problem("SDMD-AU-BEC-MISSING", label, "plot rows have no BEC label"))
    for value in sorted(normal_becs):
        if value != expected_bec:
            findings.append(
                Problem(
                    "SDMD-AU-BEC-MISMATCH",
                    label,
                    f"AU label BEC {parts.bec!r} does not match plot BEC {value!r}",
                )
            )
    if parts.tsa is not None:
        expected_tsa = normalize_tsa(parts.tsa)
        normal_tsas = {
            value for value in (normalize_tsa(item) for item in tsa_labels) if value is not None
        }
        if not normal_tsas:
            findings.append(Problem("SDMD-AU-TSA-MISSING", label, "plot rows have no TSA"))
        for value in sorted(normal_tsas):
            if value != expected_tsa:
                findings.append(
                    Problem(
                        "SDMD-AU-TSA-MISMATCH",
                        label,
                        f"AU label TSA {expected_tsa!r} does not match plot TSA {value!r}",
                    )
                )
    return tuple(findings)


def load_tsa_bec_counts(path: str | Path) -> dict[tuple[str, str], int]:
    """Load the public TSA/BEC PSP counts.

    Parameters
    ----------
    path : str or Path
        CSV with ``tsa``, ``bec``, and ``psp_site_count`` columns.

    Returns
    -------
    dict of (str, str) to int
        Non-zero site counts keyed by TSA and BEC.
    """
    frame = pd.read_csv(path, dtype={"tsa": str, "bec": str}).fillna("")
    aliases = default_bec_aliases()
    return {
        (str(row.tsa), aliases.get(str(row.bec), str(row.bec))): int(str(row.psp_site_count))
        for row in frame.itertuples(index=False)
        if int(str(row.psp_site_count)) > 0
        and str(getattr(row, "bec_level", "variant")) != "subzone"
    }


def validate_au_integrity(
    label: str,
    *,
    known_bec: Collection[str],
    tsa_bec_counts: Mapping[tuple[str, str], int],
    official_bec: Collection[str] | None = None,
    retired_bec: Mapping[str, str] | None = None,
) -> tuple[Problem, ...]:
    """Validate an AU label against BEC coverage and public PSP support.

    Parameters
    ----------
    label : str
        The AU identifier.
    known_bec : collection of str
        BEC labels in the coverage table.
    tsa_bec_counts : mapping of (str, str) to int
        Public PSP site counts by TSA and BEC.
    official_bec : collection of str, optional
        Current BEC 13 labels. None uses the packaged BECdb table. A current
        label absent from the WS4 coverage table is a coverage gap, not unknown.
    retired_bec : mapping of str to str, optional
        Retired BEC labels mapped to their retirement version. None uses the
        packaged BECdb table. A retired label is refused.

    Returns
    -------
    tuple of Problem
        Findings; empty when the label is valid.
    """
    try:
        parts = parse_au_label(label)
    except ValueError as error:
        return (Problem("SDMD-AU-LABEL", label, str(error)),)
    findings: list[Problem] = []
    known = {normalize_bec_label(value) for value in known_bec}
    official = (
        default_official_bec_labels()
        if official_bec is None
        else {normalize_bec_label(value) for value in official_bec}
    )
    retired = default_retired_bec_versions() if retired_bec is None else retired_bec
    bec = normalize_bec_label(parts.bec)
    if bec in retired:
        findings.append(
            Problem(
                "SDMD-AU-BEC-RETIRED",
                label,
                f"BEC label {parts.bec!r} was retired in BEC version {retired[bec]}",
            )
        )
    elif bec not in known:
        if bec in official:
            findings.append(
                Problem(
                    "SDMD-AU-BEC-NO-COVERAGE",
                    label,
                    f"current BEC label {parts.bec!r} has no SDMD coverage",
                )
            )
        else:
            findings.append(Problem("SDMD-AU-BEC", label, f"unknown BEC label {parts.bec!r}"))
    if parts.tsa is not None:
        tsa = normalize_tsa(parts.tsa)
        if tsa is None or (tsa, bec) not in tsa_bec_counts:
            findings.append(
                Problem(
                    "SDMD-AU-TSA-BEC",
                    label,
                    f"no public PSP support for TSA {parts.tsa} / {parts.bec}",
                )
            )
    return tuple(findings)


@lru_cache(maxsize=1)
def default_bec_labels() -> frozenset[str]:
    """Return the BEC labels in the packaged coverage table.

    Returns
    -------
    frozenset of str
        The WS4 BEC labels.
    """
    frame = pd.read_csv(_DEFAULT_DATA / "bec_variants.csv", dtype=str).fillna("")
    return frozenset((frame["zone"] + frame["subzone"] + frame["variant"]).astype(str))


@lru_cache(maxsize=1)
def default_official_bec_labels() -> frozenset[str]:
    """Return the current BEC 13 labels in the packaged BECdb table.

    Returns
    -------
    frozenset of str
        The current official BEC labels.
    """
    frame = pd.read_csv(_DEFAULT_DATA / "bec_official.csv", dtype=str).fillna("")
    return frozenset(frame["bec"].astype(str))


@lru_cache(maxsize=1)
def default_retired_bec_versions() -> Mapping[str, str]:
    """Return retired BEC labels mapped to their retirement version.

    Returns
    -------
    mapping of str to str
        The retirement version keyed by BEC label.
    """
    frame = pd.read_csv(_DEFAULT_DATA / "bec_retired.csv", dtype=str).fillna("")
    return {
        str(row.bec): str(row.retired_version)
        for row in frame.itertuples(index=False)
        if str(row.retired_version)
    }


@lru_cache(maxsize=1)
def default_tsa_bec_counts() -> Mapping[tuple[str, str], int]:
    """Return the packaged public TSA/BEC PSP counts.

    Returns
    -------
    mapping of (str, str) to int
        The TSA/BEC support counts.
    """
    return load_tsa_bec_counts(_DEFAULT_DATA / "tsa_bec_counts.csv")
