#!/usr/bin/env python3
"""Execute the example notebooks and report output that has drifted from what is committed.

The gallery renders the notebooks' **stored** outputs and the docs build never executes them
(``nbsphinx_execute = "never"``), so an example can show output the current code no longer produces
and the docs will publish it anyway. This script closes that gap: it re-runs each notebook in
memory and compares what it produces, cell by cell, with what is committed — reporting the
differences and leaving the repository untouched.

What it cannot compare, and what it does about it:

- **The environment's own banner.** Python, ws4 and the optional dependencies report their versions,
  and a path reports the machine's layout. Those are normalised away, and the number of times each
  normalisation fired is printed, so nothing is smoothed silently.
- **Time and rate.** A duration or a throughput depends on the host, not on the code.
- **Terminal rendering.** ANSI escapes are stripped, and cells whose output is a live render
  rather than a result can be tagged ``no-drift-check`` in the notebook itself, which is visible in
  the source rather than hidden here. The count of skipped cells is reported.

Everything else is compared exactly. If the check reports drift, either the notebook is stale
(re-run it and commit the new outputs) or something changed that the example should have caught.

When the check reports drift, the remedy is to run it with ``--refresh``, which executes the
notebooks and writes their new outputs back, so the commit that follows is the one the check would
have asked for. Nothing is refreshed silently: the default reports and exits non-zero.

Command-line usage::

    python scripts/check_notebooks.py
    python scripts/check_notebooks.py --only 070_library_path
    python scripts/check_notebooks.py --refresh
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient

# Terminal rendering, not content: colour and cursor codes.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# What the environment produces rather than the code. Each is named so the report can count them.
_NORMALISATIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("duration", re.compile(r"\b\d+(?:\.\d+)?\s?(?:s|ms|us|µs)\b"), "<duration>"),
    ("rate", re.compile(r"\b\d+(?:\.\d+)?\s?[a-z]+/s\b"), "<rate>"),
    ("memory", re.compile(r"\b\d+(?:\.\d+)?\s?(?:MB|GB|KB)\b"), "<memory>"),
    (
        "version",
        re.compile(r"^(python|ws4|numba|scipy|geopandas|shapely)\s+\S+", re.M),
        r"\1 <version>",
    ),
    ("path", re.compile(r"/(?:tmp|home|srv|Users)/\S*"), "<path>"),
    # a progress table prints the elapsed time as a bare number, with no unit to key on
    ("elapsed", re.compile(r"(elapsed\s*[|│]\s*)[\d.]+"), r"\1<elapsed>"),
)

#: A cell tagged with this is not compared: its output is a live render or an environment report.
SKIP_TAG = "no-drift-check"


@dataclass
class CellOutcome:
    """One code cell's comparison.

    Attributes
    ----------
    index : int
        The cell's position in the notebook.
    skipped : bool
        True when the cell is tagged as not comparable.
    stored : str
        The committed output's normalised text.
    fresh : str
        The re-run output's normalised text.
    """

    index: int
    skipped: bool
    stored: str
    fresh: str

    @property
    def drifted(self) -> bool:
        """Whether the cell's output changed, ignoring cells that are not compared.

        Returns
        -------
        bool
            True when the cell is compared and its outputs differ.
        """
        return not self.skipped and self.stored != self.fresh


def output_text(cell: dict[str, Any]) -> str:
    """Return a cell's combined output as text.

    Parameters
    ----------
    cell : dict
        A notebook cell.

    Returns
    -------
    str
        The stream and text/plain outputs concatenated, or an empty string.
    """
    parts: list[str] = []
    for output in cell.get("outputs", []):
        text = output.get("text")
        if text is None:
            data = output.get("data", {})
            text = data.get("text/plain", "") if isinstance(data, dict) else ""
        parts.append("".join(text) if isinstance(text, list) else str(text))
    return "\n".join(part for part in parts if part)


def normalise(text: str, counts: dict[str, int]) -> str:
    """Strip rendering and mask what the environment produces, counting every mask.

    Parameters
    ----------
    text : str
        The output text.
    counts : dict of str to int
        Incremented in place per normalisation applied.

    Returns
    -------
    str
        The normalised text: ANSI stripped, trailing whitespace removed, unstable values masked.
    """
    masked = _ANSI.sub("", text)
    for name, pattern, replacement in _NORMALISATIONS:
        masked, fired = pattern.subn(replacement, masked)
        counts[name] = counts.get(name, 0) + fired
    return "\n".join(line.rstrip() for line in masked.splitlines()).strip("\n")


def first_difference(stored: str, fresh: str) -> str:
    """Return the first line where two outputs differ, with both sides.

    Parameters
    ----------
    stored : str
        The committed text.
    fresh : str
        The re-run text.

    Returns
    -------
    str
        A one-line description of the first difference.
    """
    stored_lines = stored.splitlines()
    fresh_lines = fresh.splitlines()
    for position in range(max(len(stored_lines), len(fresh_lines))):
        old = stored_lines[position] if position < len(stored_lines) else "<missing>"
        new = fresh_lines[position] if position < len(fresh_lines) else "<missing>"
        if old != new:
            return f"line {position + 1}: committed {old.strip()!r} now {new.strip()!r}"
    return "outputs differ in shape only"


def check_notebook(
    path: Path, timeout: int, counts: dict[str, int], refresh: bool = False
) -> tuple[list[CellOutcome], bool]:
    """Re-run one notebook and compare its outputs with the committed ones.

    Parameters
    ----------
    path : Path
        The notebook to check.
    timeout : int
        Seconds to allow for each cell.
    counts : dict of str to int
        Incremented in place per normalisation applied.
    refresh : bool
        Whether to write the executed notebook back over the committed one.

    Returns
    -------
    tuple of (list of CellOutcome, bool)
        One outcome per code cell, and whether the notebook executed at all.
    """
    # nbformat ships no type hints, so the reader is untyped
    committed = nbformat.read(path, as_version=4)  # type: ignore[no-untyped-call]
    # one entry per *code* cell: markdown cells carry no output, and a positional list over
    # every cell would compare each output against the wrong one
    stored = [output_text(cell) for cell in committed.cells if cell.cell_type == "code"]

    fresh = copy.deepcopy(committed)
    for cell in fresh.cells:
        if cell.cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    resources = {"metadata": {"path": str(Path.cwd())}}
    client = NotebookClient(fresh, timeout=timeout, resources=resources)
    try:
        client.execute()
    except Exception as error:  # any execution failure is the finding, not a crash to hide
        print(f"  ! {path.name} did not run: {type(error).__name__}: {error}")
        return ([], False)

    outcomes: list[CellOutcome] = []
    position = 0
    for index, cell in enumerate(fresh.cells):
        if cell.cell_type != "code":
            continue
        skipped = SKIP_TAG in cell.get("metadata", {}).get("tags", [])
        outcomes.append(
            CellOutcome(
                index=index,
                skipped=skipped,
                stored=normalise(stored[position], counts),
                fresh=normalise(output_text(cell), counts),
            )
        )
        position += 1
    if refresh:
        # the committed notebook with the run's outputs: the file's metadata and markdown are kept
        for index, cell in enumerate(committed.cells):
            if cell.cell_type == "code":
                cell["outputs"] = fresh.cells[index]["outputs"]
                cell["execution_count"] = fresh.cells[index]["execution_count"]
        nbformat.write(committed, str(path))  # type: ignore[no-untyped-call]
    return (outcomes, True)


def main(argv: list[str] | None = None) -> int:
    """Execute the notebooks and report any output that drifted.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments.

    Returns
    -------
    int
        Zero when every compared cell matches, one otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notebooks", type=Path, default=Path("examples"))
    parser.add_argument("--only", default=None, help="a notebook stem to check on its own")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per cell")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="execute the notebooks and write their new outputs back",
    )
    args = parser.parse_args(argv)

    paths = sorted(args.notebooks.glob("*.ipynb"))
    if args.only:
        paths = [path for path in paths if path.stem == args.only]
    if not paths:
        print(f"no notebooks in {args.notebooks}")
        return 1

    counts: dict[str, int] = {}
    drifted = 0
    skipped = 0
    compared = 0
    unrunnable = 0
    for path in paths:
        outcomes, ran = check_notebook(path, args.timeout, counts, refresh=args.refresh)
        if not ran:
            unrunnable += 1
        cells_compared = sum(1 for outcome in outcomes if not outcome.skipped)
        cells_skipped = sum(1 for outcome in outcomes if outcome.skipped)
        bad = [outcome for outcome in outcomes if outcome.drifted]
        compared += cells_compared
        skipped += cells_skipped
        drifted += len(bad)
        state = "did not run" if not ran else ("drifted" if bad else "matches")
        if args.refresh and ran:
            state += ", refreshed"
        print(f"{path.name}: {state} ({cells_compared} compared, {cells_skipped} skipped)")
        for outcome in bad:
            print(f"    cell [{outcome.index}] {first_difference(outcome.stored, outcome.fresh)}")

    normalised = ", ".join(f"{name} x{value}" for name, value in sorted(counts.items()))
    print(
        f"\n{compared} cells compared, {skipped} skipped, {drifted} drifted,"
        f" {unrunnable} unrunnable"
    )
    print(f"normalised: {normalised or 'nothing'}")
    if args.refresh:
        return 1 if unrunnable else 0
    return 1 if drifted or unrunnable else 0


if __name__ == "__main__":
    sys.exit(main())
