"""Load a compiled dataset into the process engine and run a schedule."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.ecosystem.dataset import ProcessDataset, ProcessDatasetError
from ws4.ecosystem.fire import FireConfig, FireEdge
from ws4.ecosystem.regeneration import RegenerationConfig
from ws4.opt.account_compare import compare_accounts
from ws4.opt.objective import Target
from ws4.opt.process_search import ProcessSearchCandidate
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_ESTATE = Path(__file__).resolve().parents[1] / "examples" / "estate"


def _dataset(tmp_path: Path) -> Path:
    """Build the synthetic compiled dataset."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "dataset"
    )


def test_dataset_loads_fragments_tracks_curves_and_transitions(tmp_path: Path) -> None:
    prepared = ProcessDataset.from_directory(_dataset(tmp_path))

    assert prepared.state.cohorts["fragment_id"].tolist() == [1, 2]
    assert prepared.state.cohorts["track_id"].tolist() == [1, 1]
    assert prepared.state.cohorts["age"].tolist() == [40, 60]
    assert prepared.state.fragment_areas == {1: 3.0, 2: 2.0}
    assert prepared.block_fragments == {1: (1,), 2: (2,)}
    assert prepared.track_transitions == {(1, "CC"): 2}
    assert prepared.volume_labels == ("feature.Volume",)
    assert sorted(prepared.bridge.track_age_volume_curves) == [1, 2]
    assert prepared.topology is None
    assert prepared.edges == ()


def test_dataset_maps_block_topology_to_fragment_fire_edges(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    topology.write_text("src_block,dst_block,distance_m\n1,2,25\n", encoding="utf-8")

    prepared = ProcessDataset.from_directory(dataset, topology=topology)

    assert prepared.topology == topology
    assert prepared.edges == (FireEdge(1, 2, 25.0),)


def test_dataset_run_matches_the_estate_after_a_timed_harvest(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    schedule_path = tmp_path / "schedule.csv"
    pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [2]}).to_csv(
        schedule_path, index=False
    )
    estate = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule_path), years=5)
    prepared = ProcessDataset.from_directory(dataset)

    evaluation = prepared.evaluate(
        {1: (("CC", 2),)},
        horizon_years=4,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        seed=1,
    )
    row = compare_accounts(
        evaluation.accounts,
        estate,
        {"bridge.volume_m3": "feature.Volume"},
    ).rows.iloc[0]

    assert row["estate_value"] == pytest.approx(390.0)
    assert row["process_value"] == pytest.approx(390.0)
    assert row["absolute_difference"] == pytest.approx(0.0)


def test_dataset_process_matches_the_estate_across_multiple_blocks(tmp_path: Path) -> None:
    dataset = build_canonical_dataset(
        _ESTATE / "recipe.xml", _ESTATE / "fragments.csv", tmp_path / "estate"
    )
    blocks = (1, 2, 3, 4, 5)
    schedule_path = tmp_path / "schedule.csv"
    pd.DataFrame(
        {"block_id": list(blocks), "treatment": ["CC"] * len(blocks), "offset": [2] * len(blocks)}
    ).to_csv(schedule_path, index=False)
    estate = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule_path), years=5)
    final = estate[estate["offset"] == 4]
    estate_volume = float(final[final["account"].str.startswith("feature.Volume")]["value"].sum())
    prepared = ProcessDataset.from_directory(dataset, topology=_ESTATE / "topology.csv")

    evaluation = prepared.evaluate(
        dict.fromkeys(blocks, (("CC", 2),)),
        horizon_years=4,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        seed=1,
    )
    process_volume = float(
        evaluation.accounts.loc[evaluation.accounts["account"] == "bridge.volume_m3", "value"].iloc[
            0
        ]
    )

    assert process_volume == pytest.approx(estate_volume)
    assert len(prepared.edges) > 0


def test_batch_succession_matches_the_per_fragment_process(tmp_path: Path) -> None:
    prepared = ProcessDataset.from_directory(_dataset(tmp_path))
    schedule = {1: (("CC", 2),)}
    batch = prepared.evaluate(
        schedule,
        horizon_years=4,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        seed=1,
    )
    per_fragment = prepared.evaluate(
        schedule,
        horizon_years=4,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        batch_succession=False,
        seed=1,
    )

    pd.testing.assert_frame_equal(batch.state.cohorts, per_fragment.state.cohorts)
    batch_volume = float(
        batch.accounts.loc[batch.accounts["account"] == "bridge.volume_m3", "value"].iloc[0]
    )
    per_fragment_volume = float(
        per_fragment.accounts.loc[
            per_fragment.accounts["account"] == "bridge.volume_m3", "value"
        ].iloc[0]
    )
    assert batch_volume == pytest.approx(per_fragment_volume)


def test_dataset_search_carries_track_transitions_into_candidates(tmp_path: Path) -> None:
    prepared = ProcessDataset.from_directory(_dataset(tmp_path))
    candidate = ProcessSearchCandidate("base", {1: (("CC", 2),)})
    target = Target("bridge.volume_m3", period=4, minimum=390.0, maximum=390.0)

    result = prepared.search(
        (candidate,),
        horizon_years=4,
        targets=(target,),
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        seed=1,
    )

    accounts = {
        str(row.account): float(str(row.value))
        for row in result.best.evaluation.accounts.itertuples(index=False)
    }
    assert accounts["bridge.volume_m3"] == pytest.approx(390.0)
    assert result.best.objective == pytest.approx(0.0)


def test_dataset_limit_keeps_a_bounded_run(tmp_path: Path) -> None:
    prepared = ProcessDataset.from_directory(_dataset(tmp_path), max_blocks=1)

    assert list(prepared.block_fragments) == [1]
    assert prepared.state.cohorts["fragment_id"].tolist() == [1]


def test_dataset_rejects_a_missing_feature_curve(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    features = pd.read_parquet(dataset / "features.parquet")
    features.loc[:, "curve_id"] = 999
    features.to_parquet(dataset / "features.parquet", index=False)

    with pytest.raises(ProcessDatasetError, match="curve 999"):
        ProcessDataset.from_directory(dataset)


def test_dataset_rejects_a_non_positive_block_limit(tmp_path: Path) -> None:
    with pytest.raises(ProcessDatasetError, match="max_blocks"):
        ProcessDataset.from_directory(_dataset(tmp_path), max_blocks=0)
