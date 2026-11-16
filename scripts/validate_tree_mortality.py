"""Validate the FOFEM tree-mortality equation against the public FTM database."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from ws4.fire.mortality import BARK_COEFFICIENTS, brier_score, rank_auc, species_mortality

BC_CONIFERS = ("PICO", "PSME", "PIPO", "LAOC", "ABLA", "ABCO", "PIEN", "PIMA", "PIGL")


def load_ftm(trees_path: Path, bark_path: Path) -> pd.DataFrame:
    """Load and filter FTM tree observations.

    Parameters
    ----------
    trees_path : pathlib.Path
        FTM ``FTM_trees.csv``.
    bark_path : pathlib.Path
        FTM ``Species_BarkThickness.csv``.

    Returns
    -------
    pandas.DataFrame
        Rows with a supported species, valid DBH/scorch, and 3-year status.
    """
    bark = pd.read_csv(bark_path, encoding="latin1")
    coefficients = {
        str(row.PLANTS_Species_Code): float(str(row.BT_coef))
        for row in bark.dropna(subset=["PLANTS_Species_Code", "BT_coef"]).itertuples()
    }
    supported = set(coefficients) & set(BARK_COEFFICIENTS)
    frame = pd.read_csv(
        trees_path,
        usecols=["Species", "DBH_cm", "CVS_percent", "yr3status", "Dataset", "YrFireName"],
        low_memory=False,
    )
    frame = frame.dropna(subset=["Species", "DBH_cm", "CVS_percent", "yr3status"])
    frame = frame[frame["Species"].astype(str).isin(supported)]
    frame = frame[
        (frame["DBH_cm"].astype(float) >= 2.54)
        & (frame["CVS_percent"].astype(float) >= 0.0)
        & (frame["CVS_percent"].astype(float) <= 100.0)
    ].copy()
    frame["observed"] = frame["yr3status"].astype(float)
    frame["predicted"] = [
        species_mortality(
            species_code=str(species),
            dbh_cm=float(dbh),
            crown_volume_scorched_pct=float(scorch),
        )
        for species, dbh, scorch in zip(
            frame["Species"], frame["DBH_cm"], frame["CVS_percent"], strict=True
        )
    ]
    return frame


def score(frame: pd.DataFrame) -> dict[str, object]:
    """Score one FTM subset.

    Parameters
    ----------
    frame : pandas.DataFrame
        Rows with ``observed`` and ``predicted`` columns.

    Returns
    -------
    dict
        Sample size, prevalence, AUC, Brier score, and Brier skill.
    """
    if frame.empty:
        return {"n": 0, "prevalence": None, "auc": None, "brier": None, "brier_skill": None}
    y = frame["observed"].to_numpy(dtype=float)
    p = frame["predicted"].to_numpy(dtype=float)
    prevalence = float(y.mean())
    brier = brier_score(y, p)
    baseline = float(np.mean((prevalence - y) ** 2))
    return {
        "n": len(frame),
        "prevalence": prevalence,
        "auc": rank_auc(y, p),
        "brier": brier,
        "brier_skill": 1.0 - brier / baseline if baseline > 0.0 else None,
    }


def split_by_dataset(
    frame: pd.DataFrame, fraction: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split observations by dataset identifier.

    Parameters
    ----------
    frame : pandas.DataFrame
        FTM observations with a ``Dataset`` column.
    fraction : float, optional
        Fraction of datasets assigned to the first subset (default 0.8).

    Returns
    -------
    tuple of pandas.DataFrame
        First and second subsets.
    """
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be between zero and one")
    datasets = sorted(frame["Dataset"].astype(str).unique())
    cut = min(len(datasets) - 1, max(1, round(len(datasets) * fraction)))
    first = frame[frame["Dataset"].astype(str).isin(datasets[:cut])]
    second = frame[frame["Dataset"].astype(str).isin(datasets[cut:])]
    return first, second


def main() -> None:
    """Run the FTM validation and write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trees", type=Path, required=True)
    parser.add_argument("--bark", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    frame = load_ftm(args.trees, args.bark)
    train, validation = split_by_dataset(frame)
    bc = frame[frame["Species"].astype(str).isin(BC_CONIFERS)]
    payload = {
        "dataset": "Fire and Tree Mortality Database, 2nd edition",
        "trees_sha256": hashlib.sha256(args.trees.read_bytes()).hexdigest(),
        "model": "FOFEM generic crown-scorch equation (Ryan and Amman 1994)",
        "species_coefficients": BARK_COEFFICIENTS,
        "sample": score(frame),
        "train": score(train),
        "validation": score(validation),
        "bc_conifers": score(bc),
    }
    text = json.dumps(payload, indent=2)
    if args.output is None:
        print(text)
    else:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
