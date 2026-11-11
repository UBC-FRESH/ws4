"""Tests for the reanalysis fixture builder helpers."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pyproj import Transformer
from rasterio.transform import from_origin

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_fuel_label_mapping() -> None:
    """Standard and mixedwood codes map to supported FBP labels."""
    module: Any = importlib.import_module("build_cfsds_reanalysis_case")
    assert module._fuel_label(2) == "C-2"
    assert module._fuel_label(31) == "O-1A"
    assert module._fuel_label(0) is None
    assert module._fuel_label(101) is None
    assert module._fuel_label(415) == "M-1 (15 PC)"
    assert module._fuel_label(675) == "M-1 (75 PC)"
    with pytest.raises(ValueError, match="unsupported"):
        module._fuel_label(9999)


def test_ascii_and_kml_helpers(tmp_path: Path) -> None:
    """Helpers write readable ESRI ASCII and KML files."""
    module: Any = importlib.import_module("build_cfsds_reanalysis_case")
    ascii_path = tmp_path / "grid.asc"
    module._write_ascii(
        ascii_path,
        np.array([[1, 2], [3, 4]], dtype=np.uint8),
        xll=500000.0,
        yll=6000000.0,
        cell=100.0,
        nodata=0.0,
    )
    text = ascii_path.read_text(encoding="utf-8")
    assert "ncols 2" in text
    assert "nrows 2" in text
    assert "cellsize 100.0" in text

    mask = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    transformer = Transformer.from_crs("EPSG:26911", "EPSG:4326", always_xy=True)
    rings = module._rings(mask, from_origin(500000.0, 6000200.0, 100.0, 100.0), transformer)
    assert len(rings) == 1
    kml_path = tmp_path / "perimeter.kml"
    module._write_kml(kml_path, rings)
    assert "<Polygon>" in kml_path.read_text(encoding="utf-8")
    point_path = tmp_path / "ignition.kml"
    module._write_point(point_path, -115.0, 60.0)
    assert "<Point>" in point_path.read_text(encoding="utf-8")
