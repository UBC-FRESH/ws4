"""Parse a forest-model XML recipe into canonical matrix tables.

The recipe describes the *logical* model: tracks, treatments, curves, features, and
products. Fragment-level assignment happens later in the compiler, using fragment
attributes. The recipe is a compile-time input; launch control files and block
geometry are not read here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

Row = dict[str, Any]


class ForestModelImporter:
    """Parse a forest-model XML recipe into schema-conforming rows."""

    def __init__(self, xml_path: Path) -> None:
        """Store the path to the recipe to be parsed.

        Parameters
        ----------
        xml_path : Path
            Path to the forest-model XML recipe.
        """
        self.xml_path = Path(xml_path)

    def parse(self) -> dict[str, list[Row]]:
        """Parse the recipe into the tables that do not depend on the inventory.

        Returns
        -------
        dict of str to list of dict
            The tables ``tracks``, ``strata``, ``treatments``, ``curves``,
            ``features``, and ``products``.
        """
        root = ET.parse(self.xml_path).getroot()
        return {
            "tracks": self._tracks(root),
            "strata": self._strata(root),
            "treatments": self._treatments(root),
            "curves": self._curves(root),
            "features": self._features(root),
            "products": self._products(root),
        }

    def _tracks(self, root: ET.Element) -> list[Row]:
        """Return the track rows."""
        rows: list[Row] = []
        for element in root.findall("./tracks/track"):
            track_id = int(element.get("id", len(rows) + 1))
            rows.append({"track_id": track_id, "name": element.get("name", f"track_{track_id}")})
        return rows

    def _strata(self, root: ET.Element) -> list[Row]:
        """Return the stratum rows, one per track at offset zero."""
        rows: list[Row] = []
        for element in root.findall("./tracks/track"):
            track_id = int(element.get("id", len(rows) + 1))
            rows.append(
                {
                    "track_id": track_id,
                    "offset": 0,
                    "next_age": int(element.get("max_age", 0)),
                    "cycle": 0,
                }
            )
        return rows

    def _treatments(self, root: ET.Element) -> list[Row]:
        """Return the treatment rows."""
        rows: list[Row] = []
        for element in root.findall("./treatments/treatment"):
            rows.append(
                {
                    "track_id": int(element.get("track", 0)),
                    "begin": int(element.get("begin", 0)),
                    "end": int(element.get("end", 0)),
                    "treatment": element.get("label", element.get("id", "?")),
                    "new_track": int(element.get("new_track", element.get("track", 0))),
                    "offset": int(element.get("offset", 0)),
                    "retain": int(element.get("retain", 0)),
                }
            )
        return rows

    def _curves(self, root: ET.Element) -> list[Row]:
        """Return the curve points in long format."""
        rows: list[Row] = []
        for element in root.findall("./curves/curve"):
            curve_id = int(element.get("id", 0))
            for point in element.findall("./point"):
                rows.append(
                    {
                        "curve_id": curve_id,
                        "x": float(point.get("x", 0.0)),
                        "y": float(point.get("y", 0.0)),
                    }
                )
        return rows

    def _features(self, root: ET.Element) -> list[Row]:
        """Return the per-track feature rows."""
        return [
            {
                "track_id": int(element.get("track", 0)),
                "label": element.get("label", "feature"),
                "curve_id": int(element.get("curve", 0)),
            }
            for element in root.findall("./features/feature")
        ]

    def _products(self, root: ET.Element) -> list[Row]:
        """Return the product rows."""
        return [
            {
                "track_id": int(element.get("track", 0)),
                "treatment": element.get("treatment", ""),
                "label": element.get("label", "product"),
                "curve_id": int(element.get("curve", 0)),
            }
            for element in root.findall("./products/product")
        ]
