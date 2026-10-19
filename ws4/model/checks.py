"""Load-time checks on a compiled dataset that catch accounts which cannot mean what they say.

A compiled dataset is the contract between ingestion and execution, so a defect that makes an
account
*wrong* belongs at the boundary, where the user can still see which dataset it is. Two are known and
cheap to detect:

- **A repeated product row.** The product table is keyed by ``(track_id, treatment, label)`` and the
  simulator records every row once per treated fragment. Two identical rows therefore double the
  account, silently. The TSA23 fuel-treatment dataset carried the same key up to four times for
  ``product.Treated.managed.FT``, which made it report 4.0000 times the treated hectares.

  A repeated key is not always a defect: the same label may carry *different* curves for different
  areas, which are components to be summed. Only rows identical in both key and curve are redundant,
  and only those are removed by :func:`unique_product_rows`.
- **An area-shaped product with a rate-shaped curve.** A product whose label names an area or a
  treated block should yield a *share* (0 to 1) at each age; a curve above 1.0 means the account is
  not hectares. This one is advisory: WS4 reports what the dataset says, and the reference does the
  same.
"""

from __future__ import annotations

import pandas as pd

#: The product-table key: one row per track, treatment and label.
PRODUCT_KEY = ["track_id", "treatment", "label"]

#: Label fragments that describe an area or a treated block rather than a flow or a rate.
AREA_LABEL = r"Area|Treated"


def duplicate_product_keys(products: pd.DataFrame) -> pd.DataFrame:
    """Return the product keys that appear more than once, with their row counts.

    Parameters
    ----------
    products : pandas.DataFrame
        The compiled ``products`` table, with ``track_id``, ``treatment`` and ``label``.

    Returns
    -------
    pandas.DataFrame
        One row per repeated key — ``track_id``, ``treatment``, ``label``, ``rows`` (how many rows
        carry the key) and ``curves`` (how many distinct curves they hold) — sorted by the number of
        rows, largest first. Empty when every key is unique.
    """
    columns = [*PRODUCT_KEY, "rows", "curves"]
    if products.empty:
        return pd.DataFrame(columns=columns)
    grouped = products.groupby(PRODUCT_KEY, dropna=False)
    counts = grouped.size()
    repeated = counts[counts > 1]
    if repeated.empty:
        return pd.DataFrame(columns=columns)
    frame = repeated.rename("rows").reset_index()
    frame["curves"] = (
        grouped["curve_id"]
        .nunique()
        .reindex(pd.MultiIndex.from_frame(frame[PRODUCT_KEY]))
        .to_numpy()
    )
    return frame.sort_values(["rows", "label"], ascending=[False, True], ignore_index=True)


def unique_product_rows(products: pd.DataFrame) -> pd.DataFrame:
    """Return the product table with exact duplicate rows removed.

    A row is redundant only when it repeats both the key and the curve. A repeated key with a
    different curve is a component of the account and is kept.

    Parameters
    ----------
    products : pandas.DataFrame
        The compiled ``products`` table.

    Returns
    -------
    pandas.DataFrame
        The table with one row per ``(track_id, treatment, label, curve_id)``, in input order.
    """
    return products.drop_duplicates([*PRODUCT_KEY, "curve_id"], ignore_index=True)


def area_products_with_rate_curves(products: pd.DataFrame, curves: pd.DataFrame) -> pd.DataFrame:
    """Return area-shaped products whose curve exceeds 1.0 somewhere.

    Parameters
    ----------
    products : pandas.DataFrame
        The compiled ``products`` table.
    curves : pandas.DataFrame
        The compiled ``curves`` table, with ``curve_id`` and ``y``.

    Returns
    -------
    pandas.DataFrame
        One row per affected ``(track_id, treatment, label, curve_id)``, with ``max_y``. Empty when
        every area-shaped product is a share.
    """
    columns = ["track_id", "treatment", "label", "curve_id", "max_y"]
    if products.empty or curves.empty:
        return pd.DataFrame(columns=columns)
    area = products[products["label"].str.contains(AREA_LABEL, case=False, regex=True)]
    if area.empty:
        return pd.DataFrame(columns=columns)
    maxima = curves.groupby("curve_id")["y"].max()
    flagged = area.assign(max_y=area["curve_id"].map(maxima))
    flagged = flagged[flagged["max_y"] > 1.0]
    unique = flagged.drop_duplicates([*PRODUCT_KEY, "curve_id"])
    return unique.loc[:, columns].reset_index(drop=True)
