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
    "default_bec_labels",
    "default_official_bec_labels",
    "default_retired_bec_versions",
    "default_tsa_bec_counts",
    "load_tsa_bec_counts",
    "parse_au_label",
    "validate_au_integrity",
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
    frame = pd.read_csv(path, dtype={"tsa": str, "bec": str})
    return {
        (str(row.tsa), str(row.bec)): int(str(row.psp_site_count))
        for row in frame.itertuples(index=False)
        if int(str(row.psp_site_count)) > 0
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
        Current BEC 13 labels. When supplied, a current label that is absent from
        the WS4 coverage table is reported as a coverage gap instead of an
        unknown label.
    retired_bec : mapping of str to str, optional
        Retired BEC labels mapped to their retirement version. When supplied, a
        known WS4 label that has been retired is refused.

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
    known = set(known_bec)
    if parts.bec not in known:
        if official_bec is not None and parts.bec in set(official_bec):
            findings.append(
                Problem(
                    "SDMD-AU-BEC-NO-COVERAGE",
                    label,
                    f"current BEC label {parts.bec!r} has no SDMD coverage",
                )
            )
        else:
            findings.append(Problem("SDMD-AU-BEC", label, f"unknown BEC label {parts.bec!r}"))
    elif retired_bec is not None and parts.bec in retired_bec:
        findings.append(
            Problem(
                "SDMD-AU-BEC-RETIRED",
                label,
                f"BEC label {parts.bec!r} was retired in BEC version {retired_bec[parts.bec]}",
            )
        )
    if parts.tsa is not None and (parts.tsa, parts.bec) not in tsa_bec_counts:
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
