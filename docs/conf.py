"""Sphinx configuration for WS4."""

import sys
from pathlib import Path

project = "WS4"
author = "UBC-FRESH"
copyright = "2026, UBC-FRESH"

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT))

extensions: list[str] = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_member_order = "bysource"
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = True
napoleon_use_rtype = False

html_theme = "sphinx_rtd_theme"
html_title = "WS4"
html_extra_path = ["llms.txt"]
