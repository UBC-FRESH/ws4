"""The SDMD read and constraint API.

The router reads a directory of the six SDMD tables, an optional diagram JSON, and
optional trajectory JSON files. It exposes the AU Explorer contract as JSON and one
validated write endpoint for an AU's constraint set. It does not run the optimizer
and does not render charts; those are later layers.

The write endpoint fails closed. Every posted constraint must pass the schema, cover
every regime for the AU, and pass :func:`ws4.sdmd.constraints.check_regime` before it
is written. A failed write leaves the stored set unchanged.
"""

from __future__ import annotations

import json
import math
import threading
from _thread import LockType
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Body, HTTPException, Query

from .au_integrity import (
    default_bec_labels,
    default_official_bec_labels,
    default_retired_bec_versions,
    default_tsa_bec_counts,
    validate_au_integrity,
    validate_au_metadata,
)
from .compile import Trajectory, assess_trajectory
from .constraints import (
    AuConstraint,
    allowed_regimes,
    check_regime,
    load_constraints,
    option_counts,
    validate_constraints,
)
from .coverage import coverage_payload, coverage_row
from .diagram import (
    SdmdDiagram,
    SdmdDiagramError,
    load_diagram,
    observed_envelope,
    place_point,
)
from .ingest import read_psp_plots, read_psp_trees
from .regimes import (
    Regime,
    SdmdRegimeError,
    available_regimes,
    get_regime,
    load_regime_library,
)
from .schema import (
    AU_CONSTRAINTS,
    REGIMES,
    REVIEW_STATUSES,
    SDMD_POINTS,
    STANDS,
    Problem,
    coerce_to_schema,
    validate_dataset,
)

API_SCHEMA_VERSION = "ws4.sdmd.api.v1"


class SdmdApiError(RuntimeError):
    """Raised when an SDMD store cannot be loaded or used."""


class SdmdNotFoundError(SdmdApiError):
    """Raised when an AU or regime is not in the store."""


class SdmdRequestError(SdmdApiError):
    """Raised when a request payload fails validation."""


@dataclass
class SdmdStore:
    """The SDMD tables and the optional diagram for one directory.

    Attributes
    ----------
    root : Path
        The directory the tables were read from.
    plots : pandas.DataFrame
        The ``plots`` table.
    trees : pandas.DataFrame
        The ``trees`` table, or an empty frame when absent.
    stands : pandas.DataFrame
        The ``stands`` table.
    points : pandas.DataFrame
        The ``sdmd_points`` table.
    regimes : tuple of Regime
        The validated regime library.
    constraints : tuple of AuConstraint
        The base constraint table.
    diagram : SdmdDiagram or None
        The diagram, when ``diagram.json`` is present.
    initial_volume : dict or None
        The measured initial volume, when ``initial_volume.json`` is present.
    """

    root: Path
    plots: pd.DataFrame
    trees: pd.DataFrame
    stands: pd.DataFrame
    points: pd.DataFrame
    regimes: tuple[Regime, ...]
    constraints: tuple[AuConstraint, ...]
    diagram: SdmdDiagram | None = None
    initial_volume: dict[str, object] | None = None
    _overrides: dict[str, tuple[AuConstraint, ...]] = field(default_factory=dict, repr=False)
    _lock: LockType = field(default_factory=threading.Lock, repr=False, compare=False)

    @classmethod
    def from_directory(cls, path: str | Path) -> SdmdStore:
        """Load and validate a store from a directory.

        Parameters
        ----------
        path : str or Path
            Directory holding ``plots.csv``, ``trees.csv``, ``stands.csv``,
            ``sdmd_points.csv``, ``regimes.csv``, ``au_constraints.csv``, and optional
            ``diagram.json``, ``initial_volume.json``, and ``trajectories/``.

        Returns
        -------
        SdmdStore
            The loaded store.

        Raises
        ------
        SdmdApiError
            If a required table is missing or the tables fail validation.
        """
        root = Path(path)
        plots = read_psp_plots(_read_csv(root, "plots"))
        label_findings: list[Problem] = []
        for au_id in sorted(set(plots["au_id"].dropna().astype(str))):
            rows = plots[plots["au_id"].astype(str) == au_id]
            becs = (
                rows["bec_zone"].astype(str)
                + rows["bec_subzone"].astype(str)
                + rows["bec_variant"].astype(str)
            ).tolist()
            tsa_values = rows["tsa"].astype(str).tolist()
            label_findings.extend(
                validate_au_metadata(au_id, bec_labels=becs, tsa_labels=tsa_values)
            )
            label_findings.extend(
                validate_au_integrity(
                    au_id,
                    known_bec=default_bec_labels(),
                    tsa_bec_counts=default_tsa_bec_counts(),
                    official_bec=default_official_bec_labels(),
                    retired_bec=default_retired_bec_versions(),
                )
            )
        if label_findings:
            detail = "; ".join(
                f"{item.code} {item.where}: {item.message}" for item in label_findings
            )
            raise SdmdApiError(detail)
        trees = (
            read_psp_trees(_read_csv(root, "trees"), plots=plots)
            if (root / "trees.csv").is_file()
            else pd.DataFrame()
        )
        stands = coerce_to_schema(_read_csv(root, "stands"), STANDS)
        points = coerce_to_schema(_read_csv(root, "sdmd_points"), SDMD_POINTS)
        raw_regimes = _read_csv(root, "regimes")
        raw_constraints = _read_csv(root, "au_constraints")
        regimes = load_regime_library(raw_regimes)
        constraints = load_constraints(raw_constraints)
        frames: dict[str, pd.DataFrame] = {
            "plots": plots,
            "stands": stands,
            "sdmd_points": points,
            "regimes": coerce_to_schema(raw_regimes, REGIMES),
            "au_constraints": coerce_to_schema(raw_constraints, AU_CONSTRAINTS),
        }
        if not trees.empty:
            frames["trees"] = trees
        problems = validate_dataset(frames)
        if problems:
            detail = "; ".join(f"{item.code} {item.where}: {item.message}" for item in problems)
            raise SdmdApiError(detail)
        diagram = None
        if (root / "diagram.json").is_file():
            try:
                diagram = load_diagram(root / "diagram.json")
            except SdmdDiagramError as error:
                raise SdmdApiError(str(error)) from error
        initial_volume = _load_initial_volume(root, plots)
        return cls(
            root=root,
            plots=plots,
            trees=trees,
            stands=stands,
            points=points,
            regimes=regimes,
            constraints=constraints,
            diagram=diagram,
            initial_volume=initial_volume,
            _overrides=_load_overrides(root),
        )

    def require_au(self, au_id: str) -> None:
        """Refuse an AU that the plot table does not contain.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Raises
        ------
        SdmdNotFoundError
            When the AU is absent.
        """
        if au_id not in set(self.plots["au_id"].dropna().astype(str)):
            raise SdmdNotFoundError(f"unknown AU {au_id!r}")

    def regions(self) -> list[str]:
        """Return the distinct regions.

        Returns
        -------
        list of str
            The sorted region names.
        """
        return sorted({str(value) for value in self.plots["region"].dropna()})

    def aus(self, region: str | None = None) -> list[dict[str, object]]:
        """Return the AUs, optionally filtered by region.

        Parameters
        ----------
        region : str, optional
            A region name.

        Returns
        -------
        list of dict
            One summary per AU.
        """
        frame = self.plots
        if region is not None:
            frame = frame.loc[frame["region"].astype("string") == region]
        return [
            self._au_summary(au_id) for au_id in sorted(set(frame["au_id"].dropna().astype(str)))
        ]

    def au(self, au_id: str) -> dict[str, object]:
        """Return one AU detail.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        dict
            The AU summary and its data gaps.
        """
        self.require_au(au_id)
        summary = self._au_summary(au_id)
        summary["constraint_count"] = len(self.constraints_for(au_id))
        summary["regime_count"] = len(available_regimes(self.regimes, au_id))
        summary["diagram"] = self._diagram_payload()
        summary["initial_volume"] = self.initial_volume
        gaps: list[str] = []
        if self.trees.empty:
            gaps.append("no tree list")
        if self.constraints_for(au_id) == ():
            gaps.append("no AU constraints")
        points = self._points_for(au_id)
        if len(points) < 3:
            gaps.append("fewer than three SDMD points")
        if self.diagram is None:
            gaps.append("no diagram")
        elif self.diagram.review.status != "reviewed":
            gaps.append(f"diagram review status is {self.diagram.review.status}")
        summary["data_gaps"] = gaps
        return summary

    def plots_for(self, au_id: str) -> list[dict[str, object]]:
        """Return the plot and stand rows for an AU.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        list of dict
            One row per plot visit.
        """
        self.require_au(au_id)
        plots = self._plots_for(au_id)
        stands = self._stands_for(au_id)
        joined = plots.merge(
            stands.drop(columns=["source", "review_status"], errors="ignore"),
            on=["plot_id", "visit_year"],
            how="left",
            suffixes=("", "_stand"),
        )
        return _records(joined)

    def yield_curve(self, au_id: str) -> list[dict[str, object]]:
        """Return the AU's stand-summary yield curve.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        list of dict
            Stand-summary rows sorted by age.
        """
        self.require_au(au_id)
        stands = self._stands_for(au_id)
        columns = [
            "plot_id",
            "visit_year",
            "age",
            "tph",
            "ba_m2_ha",
            "qmd_cm",
            "top_height_m",
            "mean_height_m",
            "volume_m3_ha",
            "crown_cover_pct",
            "source",
            "review_status",
        ]
        present = [column for column in columns if column in stands.columns]
        ordered = stands[present].sort_values(["age", "plot_id"])
        return _records(ordered)

    def sdmd(self, au_id: str) -> dict[str, object]:
        """Return the AU's SDMD points and their placement.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        dict
            ``au_id``, ``diagram`` metadata, ``points``, and ``envelope``.
        """
        self.require_au(au_id)
        points = self._points_for(au_id)
        payload = _records(points)
        if self.diagram is not None:
            for row in payload:
                tph = float(str(row["tph"]))
                volume = float(str(row["mean_tree_volume_m3"]))
                try:
                    row["placement"] = place_point(self.diagram, tph, volume).to_dict()
                except SdmdDiagramError as error:
                    row["placement"] = {"error": str(error)}
        coordinates = [
            (float(str(row["tph"])), float(str(row["mean_tree_volume_m3"]))) for row in payload
        ]
        envelope: tuple[tuple[float, float], ...] = ()
        if len(coordinates) >= 3:
            try:
                envelope = observed_envelope(coordinates)
            except SdmdDiagramError:
                envelope = ()
        return {
            "schema_version": API_SCHEMA_VERSION,
            "au_id": au_id,
            "diagram": self._diagram_payload(),
            "points": payload,
            "envelope": [list(point) for point in envelope],
        }

    def regimes_for(self, au_id: str) -> list[dict[str, object]]:
        """Return the AU's regimes and their constraint status.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        list of dict
            One row per regime, with the constraint and any findings.
        """
        self.require_au(au_id)
        constraints = {item.regime_id: item for item in self.constraints_for(au_id)}
        payload: list[dict[str, object]] = []
        for regime in available_regimes(self.regimes, au_id):
            constraint = constraints.get(regime.regime_id)
            findings = check_regime(constraint, regime) if constraint is not None else []
            row = regime.to_dict()
            row["constraint"] = asdict(constraint) if constraint is not None else None
            row["trajectory_available"] = (
                self.root / "trajectories" / au_id / f"{regime.regime_id}.json"
            ).is_file()
            row["allowed"] = constraint is not None and constraint.allowed and not findings
            row["findings"] = [
                {"code": item.code, "where": item.where, "message": item.message}
                for item in findings
            ]
            payload.append(row)
        return payload

    def trajectory(self, au_id: str, regime_id: str) -> dict[str, object]:
        """Return a stored regime trajectory and its envelope assessment.

        Parameters
        ----------
        au_id : str
            The analysis unit.
        regime_id : str
            The regime.

        Returns
        -------
        dict
            The regime, the stored points, and the assessment. When no trajectory file
            exists, the status is ``unavailable`` and a data gap names the missing file.
        """
        self.require_au(au_id)
        regime = get_regime(self.regimes, regime_id)
        if regime.au_id != au_id:
            raise SdmdNotFoundError(f"regime {regime_id!r} is not in AU {au_id!r}")
        path = self.root / "trajectories" / au_id / f"{regime_id}.json"
        gaps: list[str] = []
        points: list[list[float]] = []
        source = ""
        scenario = ""
        review_status = ""
        status = "unavailable"
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping) or not isinstance(raw.get("points"), list):
                raise SdmdRequestError(f"trajectory file {path} needs a points list")
            points = [
                [float(str(point[0])), float(str(point[1]))]
                for point in raw["points"]
                if isinstance(point, list) and len(point) == 2
            ]
            source = str(raw.get("source", ""))
            scenario = str(raw.get("scenario", ""))
            review_status = str(raw.get("review_status", ""))
            curve = self._points_for(au_id) if not self.points.empty else pd.DataFrame()
            envelope: tuple[tuple[float, float], ...] = ()
            if len(curve) >= 3:
                try:
                    envelope = observed_envelope(
                        [
                            (float(str(row.tph)), float(str(row.mean_tree_volume_m3)))
                            for row in curve.itertuples(index=False)
                        ]
                    )
                except SdmdDiagramError:
                    envelope = ()
            if envelope:
                assessment = assess_trajectory(
                    Trajectory(
                        label=regime_id,
                        points=tuple((point[0], point[1]) for point in points),
                    ),
                    envelope,
                )
                status = assessment.status
            else:
                gaps.append("fewer than three observed points for an envelope")
        else:
            gaps.append(f"no trajectory file at {path}")
        return {
            "schema_version": API_SCHEMA_VERSION,
            "au_id": au_id,
            "regime": regime.to_dict(),
            "points": points,
            "source": source,
            "scenario": scenario,
            "review_status": review_status,
            "status": status,
            "data_gaps": gaps,
        }

    def constraints_for(self, au_id: str) -> tuple[AuConstraint, ...]:
        """Return the stored constraint set for an AU.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        tuple of AuConstraint
            The override when one has been written, otherwise the base rows.
        """
        if au_id in self._overrides:
            return self._overrides[au_id]
        return tuple(item for item in self.constraints if item.au_id == au_id)

    def preview(self, au_id: str) -> dict[str, object]:
        """Return the option-space size before and after the stored constraints.

        Parameters
        ----------
        au_id : str
            The analysis unit.

        Returns
        -------
        dict
            The counts and the regimes the constraints drop.
        """
        self.require_au(au_id)
        before = available_regimes(self.regimes, au_id)
        constraints = self.constraints_for(au_id)
        after = allowed_regimes(self.regimes, constraints, au_id)
        after_ids = {item.regime_id for item in after}
        dropped = []
        by_id = {item.regime_id: item for item in constraints}
        for regime in before:
            if regime.regime_id in after_ids:
                continue
            constraint = by_id.get(regime.regime_id)
            findings = check_regime(constraint, regime) if constraint is not None else []
            dropped.append(
                {
                    "regime_id": regime.regime_id,
                    "findings": [{"code": item.code, "message": item.message} for item in findings],
                }
            )
        return {
            "schema_version": API_SCHEMA_VERSION,
            "au_id": au_id,
            "counts": option_counts(before, after),
            "dropped": dropped,
        }

    def save_constraints(self, au_id: str, payload: object) -> dict[str, object]:
        """Validate and persist a complete constraint set for an AU.

        Parameters
        ----------
        au_id : str
            The analysis unit.
        payload : object
            A JSON object with a ``constraints`` list, or a bare list.

        Returns
        -------
        dict
            The saved set and its preview.

        Raises
        ------
        SdmdRequestError
            If the payload is malformed, omits a regime, names an unknown regime, or
            fails a constraint check.
        """
        self.require_au(au_id)
        items = _constraint_items(payload)
        parsed = [_parse_constraint(au_id, item) for item in items]
        problems = validate_constraints(parsed)
        if problems:
            raise SdmdRequestError(_findings_text(problems))
        expected = {item.regime_id for item in available_regimes(self.regimes, au_id)}
        provided = {item.regime_id for item in parsed}
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        if missing or extra:
            parts: list[str] = []
            if missing:
                parts.append(f"missing regimes: {', '.join(missing)}")
            if extra:
                parts.append(f"unknown regimes: {', '.join(extra)}")
            raise SdmdRequestError("; ".join(parts))
        for constraint in parsed:
            regime = get_regime(self.regimes, constraint.regime_id)
            findings = [
                item
                for item in check_regime(constraint, regime)
                if item.code != "SDMD-CONSTRAINT-DENIED"
            ]
            if findings:
                raise SdmdRequestError(_findings_text(findings))
        with self._lock:
            directory = self.root / "constraints"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{au_id}.json"
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "schema_version": API_SCHEMA_VERSION,
                        "au_id": au_id,
                        "constraints": [asdict(item) for item in parsed],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
            self._overrides[au_id] = tuple(parsed)
        return {
            "schema_version": API_SCHEMA_VERSION,
            "au_id": au_id,
            "constraints": [asdict(item) for item in parsed],
            "preview": self.preview(au_id),
        }

    def _plots_for(self, au_id: str) -> pd.DataFrame:
        """Return the plot rows for an AU."""
        return self.plots.loc[self.plots["au_id"].astype("string") == au_id].copy()

    def _stands_for(self, au_id: str) -> pd.DataFrame:
        """Return the stand-summary rows for an AU."""
        plots = self._plots_for(au_id)[["plot_id", "visit_year"]]
        return plots.merge(self.stands, on=["plot_id", "visit_year"], how="inner")

    def _points_for(self, au_id: str) -> pd.DataFrame:
        """Return the SDMD point rows for an AU."""
        return self.points.loc[self.points["au_id"].astype("string") == au_id].copy()

    def _au_summary(self, au_id: str) -> dict[str, object]:
        """Build the shared AU summary."""
        plots = self._plots_for(au_id)
        ages = _numeric(plots, "stand_age")
        sites = _numeric(plots, "site_index")
        species = self._species_for(au_id)
        return {
            "schema_version": API_SCHEMA_VERSION,
            "au_id": au_id,
            "region": _first_text(plots, "region"),
            "plot_count": int(plots["plot_id"].nunique()),
            "visit_count": len(plots),
            "age_min": _optional_int(ages.min() if not ages.empty else None),
            "age_max": _optional_int(ages.max() if not ages.empty else None),
            "site_index_min": _optional_float(sites.min() if not sites.empty else None),
            "site_index_max": _optional_float(sites.max() if not sites.empty else None),
            "leading_species": species,
            "sources": sorted({str(value) for value in plots["sources"].dropna()}),
        }

    def _species_for(self, au_id: str) -> list[str]:
        """Return the AU's species groups by total TPH."""
        if self.trees.empty:
            return []
        plot_ids = set(self._plots_for(au_id)["plot_id"].astype(str))
        trees = self.trees.loc[self.trees["plot_id"].astype(str).isin(plot_ids)]
        if trees.empty:
            return []
        totals = trees.groupby("species", observed=True)["tph"].sum().sort_values(ascending=False)
        return [str(value) for value in totals.index]

    def _diagram_payload(self) -> dict[str, object] | None:
        """Return the diagram metadata, when one is loaded."""
        if self.diagram is None:
            return None
        return {
            "diagram_id": self.diagram.diagram_id,
            "species_group": self.diagram.species_group,
            "region": self.diagram.region,
            "bec_zone": self.diagram.bec_zone,
            "bec_subzone": self.diagram.bec_subzone,
            "bec_variant": self.diagram.bec_variant,
            "site_index": self.diagram.site_index,
            "review_status": self.diagram.review.status,
            "reviewer": self.diagram.review.reviewer,
            "source": {
                "citation": self.diagram.source.citation,
                "version": self.diagram.source.version,
                "licence": self.diagram.source.licence,
                "kind": self.diagram.source.kind,
            },
            "isopleths": [
                {
                    "kind": isopleth.kind,
                    "value": isopleth.value,
                    "unit": isopleth.unit,
                    "points": [list(point) for point in isopleth.points],
                }
                for isopleth in self.diagram.isopleths
            ],
        }


def _load_overrides(root: Path) -> dict[str, tuple[AuConstraint, ...]]:
    """Load saved constraint sets from the store's constraints directory.

    Parameters
    ----------
    root : Path
        The store directory.

    Returns
    -------
    dict of str to tuple of AuConstraint
        The saved sets, keyed by AU.

    Raises
    ------
    SdmdApiError
        If a saved file is malformed or fails validation.
    """
    directory = root / "constraints"
    if not directory.is_dir():
        return {}
    result: dict[str, tuple[AuConstraint, ...]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SdmdApiError(f"saved constraints {path} are not valid JSON") from error
        if not isinstance(raw, Mapping):
            raise SdmdApiError(f"saved constraints {path} must be an object")
        au_id = _text(raw.get("au_id"))
        if not au_id:
            raise SdmdApiError(f"saved constraints {path} need an au_id")
        items = raw.get("constraints")
        if not isinstance(items, list):
            raise SdmdApiError(f"saved constraints {path} need a constraints list")
        try:
            parsed = tuple(
                _parse_constraint(au_id, item) for item in items if isinstance(item, Mapping)
            )
        except SdmdRequestError as error:
            raise SdmdApiError(str(error)) from error
        problems = validate_constraints(parsed)
        if problems:
            raise SdmdApiError(_findings_text(problems))
        result[au_id] = parsed
    return result


def create_sdmd_router(store: SdmdStore) -> APIRouter:
    """Create the SDMD API router over a store.

    Parameters
    ----------
    store : SdmdStore
        The loaded SDMD store.

    Returns
    -------
    APIRouter
        A router with the ``/api/sdmd`` prefix.
    """
    router = APIRouter(prefix="/api/sdmd", tags=["sdmd"])

    @router.get("/regions")
    def regions() -> dict[str, object]:
        """Return the distinct regions."""
        return {"schema_version": API_SCHEMA_VERSION, "regions": store.regions()}

    @router.get("/coverage")
    def coverage(
        zone: str | None = Query(None),
        status: str | None = Query(None),
    ) -> dict[str, object]:
        """Return the BC-wide BEC coverage registry."""
        if status is not None and status not in {"reviewed", "provisional", "no-diagram"}:
            raise HTTPException(status_code=422, detail=f"unknown coverage status {status!r}")
        return coverage_payload(zone=zone, status=status)

    @router.get("/coverage/{bec}")
    def coverage_for_bec(bec: str) -> dict[str, object]:
        """Return one BEC coverage row."""
        row = coverage_row(bec)
        if row is None:
            raise HTTPException(status_code=404, detail=f"unknown current BEC label {bec!r}")
        return {"schema_version": API_SCHEMA_VERSION, "row": row}

    @router.get("/aus")
    def aus(region: str | None = Query(None)) -> dict[str, object]:
        """Return the AUs, optionally filtered by region."""
        return {
            "schema_version": API_SCHEMA_VERSION,
            "region": region,
            "aus": store.aus(region),
        }

    @router.get("/au/{au_id}")
    def au(au_id: str) -> dict[str, object]:
        """Return one AU detail."""
        try:
            return store.au(au_id)
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.get("/au/{au_id}/plots")
    def plots(au_id: str) -> dict[str, object]:
        """Return the AU's plot and stand rows."""
        try:
            return {
                "schema_version": API_SCHEMA_VERSION,
                "au_id": au_id,
                "plots": store.plots_for(au_id),
            }
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.get("/au/{au_id}/yield")
    def yield_curve(au_id: str) -> dict[str, object]:
        """Return the AU's stand-summary yield curve."""
        try:
            return {
                "schema_version": API_SCHEMA_VERSION,
                "au_id": au_id,
                "yield": store.yield_curve(au_id),
            }
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.get("/au/{au_id}/sdmd")
    def sdmd(au_id: str) -> dict[str, object]:
        """Return the AU's SDMD points."""
        try:
            return store.sdmd(au_id)
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.get("/au/{au_id}/regimes")
    def regimes(au_id: str) -> dict[str, object]:
        """Return the AU's regimes and constraint status."""
        try:
            return {
                "schema_version": API_SCHEMA_VERSION,
                "au_id": au_id,
                "regimes": store.regimes_for(au_id),
            }
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.get("/au/{au_id}/trajectory")
    def trajectory(au_id: str, regime_id: str = Query(...)) -> dict[str, object]:
        """Return a stored regime trajectory."""
        try:
            return store.trajectory(au_id, regime_id)
        except SdmdNotFoundError as error:
            raise _http(404, error) from error
        except SdmdRegimeError as error:
            raise _http(404, error) from error
        except SdmdRequestError as error:
            raise _http(422, error) from error

    @router.get("/au/{au_id}/constraint-preview")
    def constraint_preview(au_id: str) -> dict[str, object]:
        """Return the option-space preview for the stored constraints."""
        try:
            return store.preview(au_id)
        except SdmdNotFoundError as error:
            raise _http(404, error) from error

    @router.post("/au/{au_id}/constraints")
    def save_constraints(au_id: str, payload: object = Body(...)) -> dict[str, object]:
        """Validate and save a complete constraint set."""
        try:
            return store.save_constraints(au_id, payload)
        except SdmdNotFoundError as error:
            raise _http(404, error) from error
        except SdmdRequestError as error:
            raise _http(422, error) from error

    return router


def _http(status: int, error: Exception) -> HTTPException:
    """Translate a store error into an HTTP error.

    Parameters
    ----------
    status : int
        HTTP status code.
    error : SdmdApiError
        The store error.

    Returns
    -------
    HTTPException
        The HTTP exception.
    """
    return HTTPException(status_code=status, detail=str(error))


def _load_initial_volume(root: Path, plots: pd.DataFrame) -> dict[str, object] | None:
    """Load and validate the optional measured initial volume.

    Parameters
    ----------
    root : Path
        The store directory.
    plots : pandas.DataFrame
        The plot table, used to check the AU.

    Returns
    -------
    dict or None
        The normalized volume record, or None when the file is absent.

    Raises
    ------
    SdmdApiError
        If the file is malformed, names an unknown AU, or has non-positive values.
    """
    path = root / "initial_volume.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SdmdApiError(f"initial_volume.json is not valid JSON: {error}") from error
    if not isinstance(raw, Mapping):
        raise SdmdApiError("initial_volume.json must hold an object")
    au_id = str(raw.get("au_id", "")).strip()
    known = {str(value) for value in plots["au_id"].dropna()}
    if au_id not in known:
        raise SdmdApiError(f"initial_volume.json names unknown AU {au_id!r}")
    try:
        volume = float(str(raw.get("initial_volume_m3_ha", "")))
        limit = float(str(raw.get("limit_m3_ha", "")))
    except (TypeError, ValueError) as error:
        raise SdmdApiError("initial volume and limit must be numbers") from error
    if volume <= 0 or limit <= 0 or volume > limit:
        raise SdmdApiError("initial volume must be positive and at most the limit")
    source = str(raw.get("source", "")).strip()
    if not source:
        raise SdmdApiError("initial_volume.json needs a source")
    review = str(raw.get("review_status", "")).strip()
    if review not in REVIEW_STATUSES:
        raise SdmdApiError(f"initial_volume review status {review!r} is not recognized")
    return {
        "schema_version": str(raw.get("schema_version", "")),
        "au_id": au_id,
        "initial_volume_m3_ha": volume,
        "limit_m3_ha": limit,
        "source": source,
        "review_status": review,
    }


def _read_csv(root: Path, name: str) -> pd.DataFrame:
    """Read a required CSV table.

    Parameters
    ----------
    root : Path
        The store directory.
    name : str
        The table name without the suffix.

    Returns
    -------
    pandas.DataFrame
        The table.

    Raises
    ------
    SdmdApiError
        If the file is missing.
    """
    path = root / f"{name}.csv"
    if not path.is_file():
        raise SdmdApiError(f"missing SDMD table {path}")
    return pd.read_csv(path)


def _constraint_items(payload: object) -> list[Mapping[str, object]]:
    """Extract the constraint list from a request payload.

    Parameters
    ----------
    payload : object
        A mapping with a ``constraints`` list, or a bare list.

    Returns
    -------
    list of mapping
        The constraint mappings.

    Raises
    ------
    SdmdRequestError
        If the payload is not a list or a mapping with a list.
    """
    items: object
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, Mapping):
        items = payload.get("constraints")
    else:
        raise SdmdRequestError("constraint payload must be a list or an object")
    if not isinstance(items, list) or not items:
        raise SdmdRequestError("constraint payload needs a non-empty constraints list")
    result: list[Mapping[str, object]] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise SdmdRequestError("each constraint must be an object")
        result.append({str(key): value for key, value in item.items()})
    return result


def _parse_constraint(au_id: str, item: Mapping[str, object]) -> AuConstraint:
    """Build and type one posted constraint.

    Parameters
    ----------
    au_id : str
        The AU from the path.
    item : mapping
        One posted constraint.

    Returns
    -------
    AuConstraint
        The typed constraint.

    Raises
    ------
    SdmdRequestError
        If a required field is missing or mistyped.
    """
    posted_au = _text(item.get("au_id", au_id))
    if posted_au != au_id:
        raise SdmdRequestError(f"constraint au_id {posted_au!r} does not match {au_id!r}")
    return AuConstraint(
        au_id=au_id,
        regime_id=_text(_require(item, "regime_id")),
        allowed=_bool(_require(item, "allowed"), "allowed"),
        min_entry_age=_int(_require(item, "min_entry_age"), "min_entry_age"),
        max_entry_age=_int(_require(item, "max_entry_age"), "max_entry_age"),
        max_entries=_int(_require(item, "max_entries"), "max_entries"),
        min_interval_years=_int(_require(item, "min_interval_years"), "min_interval_years"),
        max_removal_fraction=_float(_require(item, "max_removal_fraction"), "max_removal_fraction"),
        required_sdmd_zone=_optional_text(item.get("required_sdmd_zone")),
        source=_text(_require(item, "source")),
        review_status=_text(_require(item, "review_status")),
    )


def _require(item: Mapping[str, object], key: str) -> object:
    """Return a required mapping value.

    Parameters
    ----------
    item : mapping
        The posted object.
    key : str
        The field name.

    Returns
    -------
    object
        The value.

    Raises
    ------
    SdmdRequestError
        If the key is absent.
    """
    if key not in item:
        raise SdmdRequestError(f"constraint is missing {key}")
    return item[key]


def _text(value: object) -> str:
    """Return trimmed text.

    Parameters
    ----------
    value : object
        The field value.

    Returns
    -------
    str
        The trimmed text, or an empty string for a missing value.
    """
    return "" if value is None else str(value).strip()


def _optional_text(value: object) -> str | None:
    """Return trimmed text or ``None``."""
    text = _text(value)
    return text or None


def _int(value: object, name: str) -> int:
    """Return an integer field."""
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise SdmdRequestError(f"{name} must be an integer") from error


def _float(value: object, name: str) -> float:
    """Return a finite float field."""
    try:
        number = float(str(value))
    except (TypeError, ValueError) as error:
        raise SdmdRequestError(f"{name} must be a number") from error
    if not math.isfinite(number):
        raise SdmdRequestError(f"{name} must be finite")
    return number


def _bool(value: object, name: str) -> bool:
    """Return a boolean field."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise SdmdRequestError(f"{name} must be a boolean")


def _findings_text(problems: Sequence[Problem]) -> str:
    """Format validation findings for an HTTP error."""
    return "; ".join(f"{item.code} {item.where}: {item.message}" for item in problems)


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Convert a frame to JSON-safe records."""
    return [
        {str(key): _json_value(value) for key, value in row.items()}
        for row in frame.to_dict("records")
    ]


def _json_value(value: object) -> object:
    """Convert a pandas or numpy scalar to a JSON-safe value."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric column, or an empty series when absent."""
    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _first_text(frame: pd.DataFrame, column: str) -> str:
    """Return the first non-null text value."""
    if column not in frame.columns or frame.empty:
        return ""
    values = frame[column].dropna()
    return "" if values.empty else str(values.iloc[0])


def _optional_int(value: object) -> int | None:
    """Return an optional integer."""
    return None if value is None else int(str(value))


def _optional_float(value: object) -> float | None:
    """Return an optional float."""
    return None if value is None else float(str(value))
