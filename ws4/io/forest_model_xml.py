"""Parse a forest-model XML recipe into canonical logical parts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..model.types import CurvePoint, Destination, Track


class ForestModelImporter:
    """Parse a forest-model XML recipe into canonical parts.

    This importer focuses on *logical* content:
      • tracks
      • treatments (with operability in offset-age terms)
      • curves (long format)
      • products & destinations

    Fragment-level assignment is executed later in the compiler using
    fragment attributes. The recipe is a compile-time input; launch control
    files and block geometry are not read here.
    """

    def __init__(self, xml_path: Path) -> None:
        """Store the path to the recipe to be parsed.

        Parameters
        ----------
        xml_path : Path
            Path to the forest-model XML recipe.
        """
        self.xml_path = Path(xml_path)

    def parse(self) -> dict[str, Any]:
        """Parse the recipe into tracks, treatments, curves, products, and destinations.

        Returns
        -------
        dict of str to Any
            The canonical parts, keyed by ``tracks``, ``treatments``, ``curves``,
            ``products``, and ``destinations``.
        """
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        ns = {"pw": root.tag.split("}")[0].strip("{")}

        # The exact tags vary; here we sketch common ones.
        # Tracks
        tracks = []
        for t in root.findall(".//pw:track", ns):
            track_id = int(t.attrib.get("id", len(tracks) + 1))
            name = t.attrib.get("name", f"track_{track_id}")
            tracks.append(Track(track_id=track_id, name=name).model_dump())

        # Treatments (with rough extraction of label and new track)
        treatments = []
        for tr in root.findall(".//pw:treatment", ns):
            tid = int(tr.attrib.get("id", len(treatments) + 1))
            label = tr.attrib.get("label", f"T{tid}")
            oper = tr.attrib.get("operable", tr.attrib.get("operability", "true"))
            new_track = tr.attrib.get("newTrack") or tr.attrib.get("new_track_id")
            treatments.append(
                {
                    "treatment_id": tid,
                    "label": label,
                    "eligibility_expr": tr.attrib.get("eligibility", "true"),
                    "operability_expr": oper,
                    "new_track_id": int(new_track) if new_track else None,
                    "reset_offset": True,
                }
            )

        # Curves (assumes nested points per curve)
        curves = []
        for c in root.findall(".//pw:curve", ns):
            curve_id = int(c.attrib.get("id", len(curves) + 1))
            feature_id = int(c.attrib.get("feature_id", c.attrib.get("feature", 0)))
            for pt in c.findall(".//pw:pt", ns):
                age = int(pt.attrib.get("age", pt.attrib.get("x", 0)))
                val = float(pt.attrib.get("value", pt.attrib.get("y", 0.0)))
                curves.append(
                    CurvePoint(
                        curve_id=curve_id, feature_id=feature_id, age=age, value=val
                    ).model_dump()
                )

        # Products & destinations (very schematic)
        products = []
        for p in root.findall(".//pw:product", ns):
            pid = int(p.attrib.get("id", len(products) + 1))
            products.append(
                {
                    "product_id": pid,
                    "name": p.attrib.get("name", f"P{pid}"),
                    "yield_curve_id": int(p.attrib.get("curve_id", 0)),
                    "dest_eligibility": set(),
                }
            )

        destinations = []
        for d in root.findall(".//pw:destination", ns):
            did = int(d.attrib.get("id", len(destinations) + 1))
            destinations.append(
                Destination(dest_id=did, name=d.attrib.get("name", f"D{did}")).model_dump()
            )

        return {
            "tracks": tracks,
            "treatments": treatments,
            "curves": curves,
            "products": products,
            "destinations": destinations,
        }
