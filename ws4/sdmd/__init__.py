"""Stand density management and AU Explorer support.

This package is a diagnostic and constraint layer over the compiled dataset and the
growth evidence. It is not a growth model. See ``notes/adr/0013-sdmd-as-constraint-layer.md``.
"""

from __future__ import annotations

from .ingest import (
    AuMatchResult,
    SdmdIngestError,
    label_synthetic,
    leading_species,
    match_plots_to_aus,
    read_lidar_evidence,
    read_psp_plots,
    read_psp_trees,
    read_vri_aus,
)
from .schema import (
    AU_CONSTRAINTS,
    PLOTS,
    REGIMES,
    REVIEW_STATUSES,
    SDMD_POINTS,
    SDMD_SCHEMA_VERSION,
    SDMD_TABLE_NAMES,
    SDMD_TABLES,
    SDMD_TABLES_BY_NAME,
    SDMD_ZONES,
    STANDS,
    TREES,
    Column,
    Problem,
    Table,
    coerce_to_schema,
    table_schema,
    validate_dataset,
    validate_frame,
)

__all__ = [
    "AU_CONSTRAINTS",
    "PLOTS",
    "REGIMES",
    "REVIEW_STATUSES",
    "SDMD_POINTS",
    "SDMD_SCHEMA_VERSION",
    "SDMD_TABLES",
    "SDMD_TABLES_BY_NAME",
    "SDMD_TABLE_NAMES",
    "SDMD_ZONES",
    "STANDS",
    "TREES",
    "AuMatchResult",
    "Column",
    "Problem",
    "SdmdIngestError",
    "Table",
    "coerce_to_schema",
    "label_synthetic",
    "leading_species",
    "match_plots_to_aus",
    "read_lidar_evidence",
    "read_psp_plots",
    "read_psp_trees",
    "read_vri_aus",
    "table_schema",
    "validate_dataset",
    "validate_frame",
]
