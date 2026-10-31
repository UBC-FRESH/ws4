"""Tests for the compact Model II candidate index and resident state primitives."""

from __future__ import annotations

from pathlib import Path

from ws4.opt.model2_index import CandidateIndex


def test_candidate_index_round_trip(tmp_path: Path) -> None:
    """The compact index reconstructs the original candidate map."""
    candidates = {
        1: [(("CC", 0),), (("CC", 10),)],
        2: [(("CT", 5), ("CC", 30))],
    }
    index = CandidateIndex.build(candidates)
    assert index.option_count(1) == 2
    assert index.chain(2, 0) == (("CT", 5), ("CC", 30))
    path = tmp_path / "candidates.npz"
    index.save(path)
    loaded = CandidateIndex.load(path)
    assert loaded.to_candidates() == candidates
