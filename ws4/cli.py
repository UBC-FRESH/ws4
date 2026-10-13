from __future__ import annotations
import json
from pathlib import Path
import typer
from rich import print
from rich.table import Table

from .build.compiler import build_canonical_dataset
from .sim.engine import Simulator
from .opt.engine import Optimizer, OptimizeConfig

app = typer.Typer(help="WS4 — Wood Supply Simulation System (Spatially explicit)")

@app.command()
def build(
    xml: Path = typer.Option(..., "--xml", exists=True, help="Patchworks ForestModel XML"),
    fragments: Path = typer.Option(..., "--fragments", exists=True, help="Fragments shapefile (polygons)"),
    out: Path = typer.Option(..., "--out", help="Output directory for canonical dataset"),
):
    """Compile a canonical dataset from Patchworks-style XML and a *fragments* shapefile.

    Notes:
      • PIN files are not required here (they're used to *launch*, not *build*).
      • Blocks shapefile is not required to build (used at runtime for reporting/launch).
    """
    out = build_canonical_dataset(xml_path=xml, fragments_path=fragments, out_dir=out)
    print(f"[bold green]Built dataset[/] → {out}")

@app.command()
def simulate(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    schedule: Path = typer.Option(..., exists=True, help="CSV: block_id,treatment,period (period in years)"),
    years: int = typer.Option(200, help="Simulation horizon in years"),
    out: Path = typer.Option(..., help="Output directory"),
):
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
):
    cfg = OptimizeConfig(threads=threads, time_limit=time_limit, seed=seed,
                         targets_path=str(targets), weights_path=str(weights))
    opt = Optimizer.from_dataset(dataset, cfg)
    result = opt.run(out)
    table = Table(title="Optimization Summary")
    table.add_column("key"); table.add_column("value")
    for k, v in result.items():
        table.add_row(k, str(v))
    print(table)

@app.command()
def validate(dataset: Path = typer.Option(..., exists=True)):
    # TODO: implement schema checks, monotonicity, consistency
    print(f"[yellow]Validation stub for[/] {dataset}")
