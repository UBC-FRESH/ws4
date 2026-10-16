"""Parity tests for the optional native kernels.

The numba path must agree with the pure-Python path exactly. When numba is not installed the
tests skip; CI installs it (``requirements-dev.txt``) so the gate runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.sim import engine as sim_engine
from ws4.sim.engine import Simulator
from ws4.sim.kernels import HAVE_NUMBA, ProductKernel

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
pytestmark = pytest.mark.skipif(not HAVE_NUMBA, reason="numba is not installed")


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "c"
    )


def _python_products(
    simulator: Simulator, block: int, events: list[tuple[str, int]], monkeypatch: pytest.MonkeyPatch
) -> dict[tuple[int, str], float]:
    """Return the product cells using the pure-Python path."""
    monkeypatch.setattr(sim_engine, "HAVE_NUMBA", False)
    simulator._product_kernel = None
    return simulator.block_chain_products(block, events)


def test_kernel_matches_the_python_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel and the Python loop return identical product cells."""
    dataset = _dataset(tmp_path)
    simulator = Simulator.from_dataset(dataset)
    for events in ([("CC", 0)], [("CC", 0), ("CC", 2)], []):
        kernel = ProductKernel(simulator).products(1, events)
        python = _python_products(simulator, 1, events, monkeypatch)
        assert kernel == python


def test_kernel_path_is_used_when_numba_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The simulator builds a kernel and it produces the same cells as the Python path."""
    dataset = _dataset(tmp_path)
    simulator = Simulator.from_dataset(dataset)
    events = [("CC", 0)]
    fast = simulator.block_chain_products(1, events)
    assert simulator._product_kernel is not None
    assert fast == _python_products(simulator, 1, events, monkeypatch)


def test_kernel_is_rebuilt_after_a_reset(tmp_path: Path) -> None:
    """A state change drops the prepared kernel, so it never serves stale ages."""
    dataset = _dataset(tmp_path)
    simulator = Simulator.from_dataset(dataset)
    simulator.block_chain_products(1, [("CC", 0)])
    assert simulator._product_kernel is not None
    simulator.reset()
    assert simulator._product_kernel is None
