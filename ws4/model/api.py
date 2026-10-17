"""The programmatic model API: build or patch a model in memory.

The compiled matrix is the file contract; this module is the in-memory contract. A
:class:`Model` holds one DataFrame per matrix table. Load one from a dataset, patch it
(add a track, a treatment, a fragment, a curve), and write it back. The two paths meet
at the same model (see `notes/adr/0012`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES, coerce_to_schema
from ..model.types import CanonicalDatasetManifest


class Model:
    """An in-memory forest model, one DataFrame per matrix table.

    Parameters
    ----------
    tables : dict of str to pandas.DataFrame, optional
        The tables by name. A missing table is filled with an empty frame coerced to the
        schema.
    """

    def __init__(self, tables: dict[str, pd.DataFrame] | None = None) -> None:
        """Initialize from a table map, filling any missing table with an empty frame."""
        given = tables or {}
        self.tables: dict[str, pd.DataFrame] = {
            table.name: coerce_to_schema(given.get(table.name, pd.DataFrame()), table)
            for table in TABLES
        }

    @classmethod
    def empty(cls) -> Model:
        """Return a model with every table empty.

        Returns
        -------
        Model
            The empty model.
        """
        return cls()

    @classmethod
    def from_dataset(cls, dataset_dir: Path) -> Model:
        """Load a model from a compiled dataset directory.

        Parameters
        ----------
        dataset_dir : Path
            The dataset directory.

        Returns
        -------
        Model
            The loaded model.
        """
        dataset_dir = Path(dataset_dir)
        return cls({table.name: pd.read_parquet(dataset_dir / table.file) for table in TABLES})

    def table(self, name: str) -> pd.DataFrame:
        """Return a table by name.

        Parameters
        ----------
        name : str
            The table name.

        Returns
        -------
        pandas.DataFrame
            The table, coerced to the schema.
        """
        return self.tables[name]

    def append(self, name: str, row: dict[str, object]) -> None:
        """Append a row to a table.

        Parameters
        ----------
        name : str
            The table name.
        row : dict
            The row's values.
        """
        self.tables[name] = pd.concat([self.tables[name], pd.DataFrame([row])], ignore_index=True)

    def replace(self, name: str, where: pd.Series, row: dict[str, object]) -> None:
        """Replace the rows of a table that match a boolean mask with one row.

        Parameters
        ----------
        name : str
            The table name.
        where : pandas.Series
            A boolean mask over the table's rows.
        row : dict
            The replacement row.
        """
        kept = self.tables[name][~where]
        self.tables[name] = pd.concat([kept, pd.DataFrame([row])], ignore_index=True)

    def write(self, dataset_dir: Path) -> Path:
        """Write the model to a compiled dataset directory.

        Parameters
        ----------
        dataset_dir : Path
            The directory to write into.

        Returns
        -------
        Path
            The dataset directory.
        """
        dataset_dir = Path(dataset_dir)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            coerce_to_schema(self.tables[table.name], table).to_parquet(
                dataset_dir / table.file, index=False
            )
        manifest = CanonicalDatasetManifest(
            schema_version=SCHEMA_VERSION,
            tables={table.name: table.file for table in TABLES},
            options={"source": "programmatic"},
        )
        (dataset_dir / MANIFEST_NAME).write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        return dataset_dir
