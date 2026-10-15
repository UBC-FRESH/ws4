"""Command-line interface for WS4: build, simulate, optimize, and validate."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer
from rich import print
from rich.table import Table

from .build.compiler import build_canonical_dataset
from .build.legacy import ingest_legacy_matrix
from .model.schema import validate_dataset
from .opt.engine import OptimizeConfig, Optimizer
from .opt.objective import load_targets
from .patch.edge import load_edge_elements
from .report import write_report
from .roads.accounts import load_route_config
from .sim.engine import Simulator

app = typer.Typer(help="WS4 — Wood Supply Simulation System (Spatially explicit)")


@app.command()
def build(
    xml: Path = typer.Option(..., "--xml", exists=True, help="Forest-model XML recipe"),
    fragments: Path = typer.Option(
        ..., "--fragments", exists=True, help="Fragment inventory (CSV or Parquet)"
    ),
    out: Path = typer.Option(..., "--out", help="Output directory for canonical dataset"),
) -> None:
    """Compile a canonical dataset from an XML recipe and a *fragments* shapefile.

    Notes
    -----
      • Launch control files are not required here (they are used to *launch*,
        not *build*).
      • Block geometry is not required to build (it is a runtime view).
    """
    out = build_canonical_dataset(xml_path=xml, fragments_path=fragments, out_dir=out)
    print(f"[bold green]Built dataset[/] → {out}")


@app.command()
def simulate(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    schedule: Path = typer.Option(
        ..., exists=True, help="CSV: block_id,treatment,period (period in years)"
    ),
    years: int = typer.Option(200, help="Simulation horizon in years"),
    out: Path = typer.Option(..., help="Output directory"),
    topology: Path = typer.Option(None, exists=True, help="Block topology for spatial metrics"),
    route_config: Path = typer.Option(
        None, "--route-config", exists=True, help="Optional route model and route accounts (YAML)"
    ),
    edge_elements: Path = typer.Option(
        None, "--edge-elements", exists=True, help="Optional edge contrast elements (CSV)"
    ),
    core_buffer_m: float = typer.Option(
        None, "--core-buffer-m", help="Core-area buffer, in metres"
    ),
    min_core_area_ha: float = typer.Option(
        None, "--min-core-area-ha", help="Minimum core area, in hectares"
    ),
) -> None:
    """Simulate a schedule over a compiled dataset and write a run directory."""
    sim = Simulator.from_dataset(dataset)
    elements = load_edge_elements(edge_elements) if edge_elements is not None else ()
    config = load_route_config(route_config) if route_config is not None else None
    sim.run(
        schedule_csv=schedule,
        years=years,
        out_dir=out,
        topology_csv=topology,
        route_model=config.model if config is not None else None,
        route_accounts=config.route_accounts if config is not None else (),
        duplicate_accounts=config.duplicate_accounts if config is not None else (),
        edge_elements=elements,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
    )
    print(f"[bold green]Simulation complete[/] → {out}")


@app.command()
def optimize(
    dataset: Path = typer.Option(..., exists=True),
    targets: Path = typer.Option(..., exists=True),
    weights: Path = typer.Option(..., exists=True),
    threads: int = typer.Option(8, min=1),
    time_limit: str = typer.Option("01:00:00", help="HH:MM:SS"),
    seed: int = typer.Option(42),
    out: Path = typer.Option(...),
    topology: Path = typer.Option(None, exists=True, help="Block topology for spatial constraints"),
    route_config: Path = typer.Option(
        None, "--route-config", exists=True, help="Optional route model and route accounts (YAML)"
    ),
    edge_elements: Path = typer.Option(
        None, "--edge-elements", exists=True, help="Optional edge contrast elements (CSV)"
    ),
    core_buffer_m: float = typer.Option(
        None, "--core-buffer-m", help="Core-area buffer, in metres"
    ),
    min_core_area_ha: float = typer.Option(
        None, "--min-core-area-ha", help="Minimum core area, in hectares"
    ),
    max_opening_ha: float = typer.Option(None, help="Maximum opening size, in hectares"),
    min_green_up_years: int = typer.Option(None, help="Green-up interval, in years"),
    spatial_override: bool = typer.Option(
        False, "--spatial-override", help="Allow schedules that violate the spatial constraints"
    ),
) -> None:
    """Search for a schedule that satisfies the targets and write a summary."""
    cfg = OptimizeConfig(
        threads=threads,
        time_limit=time_limit,
        seed=seed,
        targets_path=str(targets),
        weights_path=str(weights),
        topology_path=str(topology) if topology is not None else "",
        route_config_path=str(route_config) if route_config is not None else "",
        edge_elements_path=str(edge_elements) if edge_elements is not None else "",
        max_opening_ha=max_opening_ha,
        min_green_up_years=min_green_up_years,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
        allow_spatial_override=spatial_override,
    )
    opt = Optimizer.from_dataset(dataset, cfg)
    result = opt.run(out)
    table = Table(title="Optimization Summary")
    table.add_column("key")
    table.add_column("value")
    for k, v in result.items():
        table.add_row(k, str(v))
    print(table)


@app.command()
def ingest(
    matrix: Path = typer.Option(..., "--matrix", exists=True, help="Legacy matrix directory"),
    fragments: Path = typer.Option(
        ..., "--fragments", exists=True, help="Fragment inventory (CSV or Parquet)"
    ),
    out: Path = typer.Option(..., "--out", help="Output directory for the canonical dataset"),
) -> None:
    """Ingest a legacy matrix dataset into the WS4 schema."""
    out = ingest_legacy_matrix(matrix, fragments, out)
    print(f"[bold green]Ingested dataset[/] → {out}")


@app.command()
def report(
    run: Path = typer.Option(..., "--run", exists=True, help="A run directory"),
    targets: Path = typer.Option(None, "--targets", help="Optional targets YAML"),
    out: Path = typer.Option(None, "--out", help="Output directory (defaults to the run)"),
) -> None:
    """Write an account summary and a target status for a run."""
    values = pd.read_csv(run / "account_values.csv")
    target_list = load_targets(targets) if targets is not None else []
    write_report(values, target_list, out if out is not None else run)
    print(f"[bold green]Report written[/] → {out if out is not None else run}")


@app.command()
def validate(dataset: Path = typer.Option(..., exists=True)) -> None:
    """Validate a compiled dataset against its manifest and schema invariants."""
    problems = validate_dataset(dataset)
    if not problems:
        print(f"[bold green]Dataset is valid[/] → {dataset}")
        return
    table = Table(title="Validation problems")
    table.add_column("code")
    table.add_column("where")
    table.add_column("message")
    for problem in problems:
        table.add_row(problem.code, problem.where, problem.message)
    print(table)
    raise typer.Exit(code=1)
