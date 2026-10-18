"""Tests for the notebook drift check.

The check exists to catch a notebook whose committed output no longer matches what its code
produces, so every test here is built around a notebook written into a scratch directory and run
through the real checker.

``nbformat`` ships no type hints, so its builders and its reader are called with a suppression that
says so rather than being sprinkled with conversions.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
import pytest

import check_notebooks as check


def _notebook(
    path: Path, cells: list[nbformat.NotebookNode], tags: list[str] | None = None
) -> Path:
    """Write a notebook whose single code cell prints ``hello`` with the given stored output.

    Parameters
    ----------
    path : Path
        Where to write it.
    cells : list of notebook node
        The cells, already carrying whatever outputs the test wants compared.
    tags : list of str, optional
        Tags for the first code cell.

    Returns
    -------
    Path
        The notebook path.
    """
    notebook = nbformat.v4.new_notebook()  # type: ignore[no-untyped-call]
    notebook["cells"] = cells
    if tags:
        for cell in notebook["cells"]:
            if cell.cell_type == "code":
                cell["metadata"]["tags"] = tags
                break
    nbformat.write(notebook, str(path))  # type: ignore[no-untyped-call]
    return path


def _stream_cell(source: str, text: str) -> nbformat.NotebookNode:
    """Return a code cell whose stored output is a stream of text.

    Parameters
    ----------
    source : str
        The cell's code.
    text : str
        The output to store.

    Returns
    -------
    notebook node
        The cell.
    """
    cell = nbformat.v4.new_code_cell(source)  # type: ignore[no-untyped-call]
    cell["outputs"] = [
        nbformat.v4.new_output("stream", name="stdout", text=text)  # type: ignore[no-untyped-call]
    ]
    return cell  # type: ignore[no-any-return]


def test_a_current_notebook_matches(tmp_path: Path) -> None:
    """A notebook whose stored output is what its code prints is reported as a match."""
    _notebook(tmp_path / "current.ipynb", [_stream_cell('print("hello")', "hello\n")])
    assert check.main(["--notebooks", str(tmp_path), "--only", "current"]) == 0


def test_a_stale_notebook_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A stored output the code no longer produces is drift, named with its cell."""
    path = _notebook(tmp_path / "stale.ipynb", [_stream_cell('print("hello")', "goodbye\n")])
    assert path.is_file()
    assert check.main(["--notebooks", str(tmp_path), "--only", "stale"]) == 1
    printed = capsys.readouterr().out
    assert "drifted" in printed
    assert "cell [0]" in printed
    assert "hello" in printed


def test_a_cell_tagged_no_drift_check_is_skipped(tmp_path: Path) -> None:
    """A tagged cell's output is not compared, and the skip is counted."""
    path = _notebook(
        tmp_path / "tagged.ipynb",
        [_stream_cell('print("hello")', "a live render that never repeats\n")],
        tags=[check.SKIP_TAG],
    )
    assert path.is_file()
    assert check.main(["--notebooks", str(tmp_path), "--only", "tagged"]) == 0


def test_rendering_and_environment_values_do_not_count_as_drift(tmp_path: Path) -> None:
    """ANSI codes, trailing space and the environment's own numbers are normalised away."""
    stored = "\x1b[1mhello\x1b[0m   \nws4 0.1.0\nfinished in 0.42s\n"
    path = _notebook(
        tmp_path / "noisy.ipynb",
        [
            _stream_cell(
                'print("hello"); print("ws4 0.2.0"); print("finished in 0.42s")',
                stored,
            )
        ],
    )
    assert path.is_file()
    assert check.main(["--notebooks", str(tmp_path), "--only", "noisy"]) == 0


def test_a_notebook_that_no_longer_runs_is_a_finding(tmp_path: Path) -> None:
    """An exception in a cell is reported rather than crashing the check."""
    path = _notebook(tmp_path / "broken.ipynb", [_stream_cell('raise SystemExit("gone")', "")])
    assert path.is_file()
    assert check.main(["--notebooks", str(tmp_path), "--only", "broken"]) == 1


def test_the_outcome_reports_drift_per_cell(tmp_path: Path) -> None:
    """The unit-level outcome flags the drifting cell and only that one."""
    path = _notebook(
        tmp_path / "mixed.ipynb",
        [
            _stream_cell('print("one")', "one\n"),
            _stream_cell('print("two")', "not two\n"),
        ],
    )
    outcomes, ran = check.check_notebook(path, timeout=120, counts={})
    assert ran
    assert [outcome.drifted for outcome in outcomes] == [False, True]
    assert check.first_difference(outcomes[1].stored, outcomes[1].fresh).startswith("line 1:")


def test_refresh_writes_the_run_outputs_back(tmp_path: Path) -> None:
    """The remedy for drift is one command, and it makes the next check pass."""
    path = _notebook(tmp_path / "refreshed.ipynb", [_stream_cell('print("hello")', "goodbye\n")])
    assert check.main(["--notebooks", str(tmp_path), "--only", "refreshed"]) == 1
    assert check.main(["--notebooks", str(tmp_path), "--only", "refreshed", "--refresh"]) == 0
    assert check.main(["--notebooks", str(tmp_path), "--only", "refreshed"]) == 0
    refreshed = nbformat.read(path, as_version=4)  # type: ignore[no-untyped-call]
    text = "".join(refreshed.cells[0]["outputs"][0]["text"])
    assert "hello" in text
