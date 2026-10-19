"""The product table must not multiply an account, and the loader must say when it would.

A product row is recorded once per treated fragment, so an exact repeat multiplies the account. A
repeated key with a different curve is a component to be summed and is legitimate. These tests pin
both sides: the unit rules, the builder that applies them, and the warning a reader sees for a
dataset that was compiled before the rule existed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.model.checks import (
    area_products_with_rate_curves,
    duplicate_product_keys,
    unique_product_rows,
)
from ws4.sim.engine import Simulator

_RECIPE = Path(__file__).resolve().parents[1] / "examples" / "synthetic" / "recipe.xml"
_DUPLICATE_PRODUCT = """      <attribute label="product.Volume">
        <curve idref="natural_volume"/>
      </attribute>
"""


def _products() -> pd.DataFrame:
    """Return a product table with an exact duplicate, a component pair and a unique key."""
    return pd.DataFrame(
        [
            {"track_id": 1, "treatment": "CC", "label": "product.Treated", "curve_id": 1},
            {"track_id": 1, "treatment": "CC", "label": "product.Treated", "curve_id": 1},
            {"track_id": 1, "treatment": "CC", "label": "product.Treated", "curve_id": 1},
            {"track_id": 2, "treatment": "FT", "label": "product.Volume", "curve_id": 2},
            {"track_id": 2, "treatment": "FT", "label": "product.Volume", "curve_id": 3},
            {"track_id": 3, "treatment": "", "label": "product.Volume", "curve_id": 2},
        ]
    )


def test_duplicate_keys_are_counted_and_distinguished_from_components() -> None:
    """Three rows with one curve are redundant; two rows with two curves are components."""
    duplicates = duplicate_product_keys(_products())
    first = duplicates.iloc[0]
    assert first["track_id"] == 1
    assert int(first["rows"]) == 3
    assert int(first["curves"]) == 1
    component = duplicates[duplicates["label"] == "product.Volume"].iloc[0]
    assert int(component["rows"]) == 2
    assert int(component["curves"]) == 2
    assert (
        len(
            duplicate_product_keys(
                pd.DataFrame([{"track_id": 1, "treatment": "CC", "label": "x", "curve_id": 1}])
            )
        )
        == 0
    )


def test_unique_rows_drop_exact_duplicates_but_keep_components() -> None:
    """One row per key and curve: the Treated repeat collapses, the Volume pair survives."""
    unique = unique_product_rows(_products())
    treated = unique[(unique["track_id"] == 1) & (unique["label"] == "product.Treated")]
    assert len(treated) == 1
    volume = unique[(unique["track_id"] == 2) & (unique["label"] == "product.Volume")]
    assert sorted(volume["curve_id"]) == [2, 3]


def test_area_products_with_rate_curves_flags_only_area_labels() -> None:
    """A Treated curve of 4.0 is not a share; a Yield curve of 10 is not an area label."""
    products = pd.DataFrame(
        [
            {
                "track_id": 1,
                "treatment": "FT",
                "label": "product.Treated.managed.FT",
                "curve_id": 1,
            },
            {
                "track_id": 1,
                "treatment": "FT",
                "label": "product.Treated.managed.Rate",
                "curve_id": 2,
            },
            {
                "track_id": 1,
                "treatment": "FT",
                "label": "product.Yield.managed.Total",
                "curve_id": 3,
            },
        ]
    )
    curves = pd.DataFrame(
        [
            {"curve_id": 1, "x": 0.0, "y": 1.0},
            {"curve_id": 2, "x": 0.0, "y": 4.0},
            {"curve_id": 3, "x": 0.0, "y": 10.0},
        ]
    )
    flagged = area_products_with_rate_curves(products, curves)
    assert list(flagged["label"]) == ["product.Treated.managed.Rate"]
    assert float(flagged["max_y"].iloc[0]) == 4.0


def _compiled(tmp_path: Path, *, duplicate_product: bool) -> Path:
    """Build a small dataset, optionally with the same product declared twice."""
    recipe = tmp_path / "recipe.xml"
    text = _RECIPE.read_text(encoding="utf-8")
    if duplicate_product:
        text = text.replace("  </products>", _DUPLICATE_PRODUCT + "  </products>", 1)
    recipe.write_text(text, encoding="utf-8")
    fragments = tmp_path / "fragments.csv"
    fragments.write_text(
        "BLOCK,AREA_HA,F_AGE,AU,IFM\n1,10,50,1,unmanaged\n2,10,20,1,unmanaged\n3,10,60,1,managed\n",
        encoding="utf-8",
    )
    return build_canonical_dataset(recipe, fragments, tmp_path / "compiled")


def test_the_builder_emits_one_row_per_product_key_and_curve(tmp_path: Path) -> None:
    """A recipe that declares the same product twice compiles to one row."""
    dataset = _compiled(tmp_path, duplicate_product=True)
    products = pd.read_parquet(dataset / "products.parquet")
    assert not products.duplicated(["track_id", "treatment", "label", "curve_id"]).any()
    volume = products[products["label"] == "product.Volume"]
    assert len(volume) == 1


def test_the_simulator_warns_when_a_dataset_repeats_a_product_row(tmp_path: Path) -> None:
    """A dataset compiled before the rule is loaded with a named warning, not silently."""
    dataset = _compiled(tmp_path, duplicate_product=False)
    products = pd.read_parquet(dataset / "products.parquet")
    products = pd.concat([products, products.iloc[[0]]], ignore_index=True)
    products.to_parquet(dataset / "products.parquet", index=False)
    with pytest.warns(UserWarning, match="redundant product rows"):
        Simulator.from_dataset(dataset)


def test_a_clean_dataset_loads_without_a_product_warning(tmp_path: Path) -> None:
    """The builder's own output does not warn about products."""
    import warnings

    dataset = _compiled(tmp_path, duplicate_product=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Simulator.from_dataset(dataset)
    assert not [item for item in caught if "product" in str(item.message)]
