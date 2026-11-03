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
    if parts.bec not in set(known_bec):
        findings.append(Problem("SDMD-AU-BEC", label, f"unknown BEC label {parts.bec!r}"))
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
def default_tsa_bec_counts() -> Mapping[tuple[str, str], int]:
    """Return the packaged public TSA/BEC PSP counts.

    Returns
    -------
    mapping of (str, str) to int
        The TSA/BEC support counts.
    """
    return load_tsa_bec_counts(_DEFAULT_DATA / "tsa_bec_counts.csv")
