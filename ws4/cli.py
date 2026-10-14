"""Command-line interface for WS4: build, simulate, optimize, and validate."""

from __future__ import annotations

from pathlib import Path

import typer
from rich import print
from rich.table import Table

from .build.compiler import build_canonical_dataset
from .build.legacy import ingest_legacy_matrix
from .model.schema import validate_dataset
from .opt.engine import OptimizeConfig, Optimizer
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
) -> None:
    """Simulate a schedule over a compiled dataset and write a run directory."""
    sim = Simulator.from_dataset(dataset)
    sim.run(schedule_csv=schedule, years=years, out_dir=out)
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
) -> None:
    """Search for a schedule that satisfies the targets and write a summary."""
    cfg = OptimizeConfig(
        threads=threads,
        time_limit=time_limit,
        seed=seed,
        targets_path=str(targets),
        weights_path=str(weights),
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
