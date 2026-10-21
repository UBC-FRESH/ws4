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
from .opt.calibrate import calibrate as run_calibration
from .opt.calibrate import write_targets
from .opt.engine import OptimizeConfig, Optimizer
from .opt.objective import load_targets
from .opt.watch import run_watch
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
        product_allocations=config.product_allocations if config is not None else (),
        period_width=config.period_width if config is not None else 1,
        maintenance=config.maintenance if config is not None else None,
        edge_elements=elements,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
    )
    print(f"[bold green]Simulation complete[/] → {out}")


@app.command()
def optimize(
    dataset: Path = typer.Option(..., exists=True),
    targets: Path = typer.Option(..., exists=True),
    weights: Path | None = typer.Option(
        None,
        exists=True,
        help="Accepted for compatibility; the weights that apply are each target's own",
    ),
    threads: int = typer.Option(8, min=1, help="Worker processes, and BLAS threads each"),
    starts: int = typer.Option(1, min=1, help="parallel multi-starts (needs --threads > 1)"),
    time_limit: str = typer.Option("01:00:00", help="HH:MM:SS"),
    control_file: Path | None = typer.Option(
        None, "--control-file", help="JSON file that can pause or stop the search"
    ),
    iterations: int = typer.Option(500, min=1, help="Search iterations"),
    patience: int = typer.Option(
        0,
        min=0,
        help="Stop after this many iterations without an improvement; 0 disables it",
    ),
    years: int = typer.Option(50, help="Simulation horizon in years"),
    seed: int = typer.Option(42),
    islands: int = typer.Option(0, help="parallel islands with elite migration (0 = off)"),
    episodes: int = typer.Option(1, help="island episodes (elite migrations)"),
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
    lns_weight: float = typer.Option(
        0.2, "--lns-weight", help="Weight of the LNS operator (0 disables it)"
    ),
    lns_destroy: float = typer.Option(
        0.1, "--lns-destroy", help="Fraction of the schedule an LNS move destroys"
    ),
    warm_cache: bool = typer.Option(
        False, "--warm-cache", help="Precompute every candidate chain's contribution first"
    ),
    seed_greedy: bool = typer.Option(
        False,
        "--seed-greedy",
        help="Seed the search with a schedule built from the declared targets and ceilings",
    ),
    seed_account: str = typer.Option(
        "",
        "--seed-account",
        help="With --seed-greedy, reduce this target account to its maximum instead of floors",
    ),
    cluster_weight: float = typer.Option(
        0.0, "--cluster-weight", help="Weight of the topology cluster operator (0 disables it)"
    ),
    cluster_size: int = typer.Option(8, "--cluster-size", help="Blocks per cluster move"),
    merge_weight: float = typer.Option(
        0.0, "--merge-weight", help="Weight of the patch merge operator (0 disables it)"
    ),
    split_weight: float = typer.Option(
        0.0, "--split-weight", help="Weight of the patch split operator (0 disables it)"
    ),
    patch_accounts: Path = typer.Option(
        None, "--patch-accounts", exists=True, help="Patch size-distribution accounts (YAML)"
    ),
    spread_accounts: Path = typer.Option(
        None,
        "--spread-accounts",
        exists=True,
        help="Spread-connectivity accounts (YAML); needs --topology and --block-coordinates",
    ),
    block_coordinates: Path = typer.Option(
        None, "--block-coordinates", exists=True, help="Block centroids (CSV: block, x, y)"
    ),
    cooling_mode: str = typer.Option(
        "geometric", "--cooling-mode", help="Temperature schedule: geometric or adaptive"
    ),
    cooling_window: int = typer.Option(
        64, "--cooling-window", help="Iterations per temperature with the adaptive schedule"
    ),
    mip_bound: bool = typer.Option(
        False, "--mip-bound", help="Record a mixed-integer penalty lower bound in the summary"
    ),
) -> None:
    """Search for a schedule that satisfies the targets and write a summary."""
    cfg = OptimizeConfig(
        threads=threads,
        workers=threads,
        starts=starts,
        time_limit=time_limit,
        control_path=str(control_file) if control_file is not None else "",
        iterations=iterations,
        patience=patience,
        years=years,
        seed=seed,
        islands=islands,
        episodes=episodes,
        targets_path=str(targets),
        weights_path=str(weights) if weights is not None else "",
        topology_path=str(topology) if topology is not None else "",
        route_config_path=str(route_config) if route_config is not None else "",
        edge_elements_path=str(edge_elements) if edge_elements is not None else "",
        max_opening_ha=max_opening_ha,
        min_green_up_years=min_green_up_years,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
        allow_spatial_override=spatial_override,
        lns_weight=lns_weight,
        lns_destroy=lns_destroy,
        warm_cache=warm_cache,
        greedy_seed=seed_greedy,
        seed_account=seed_account,
        cluster_weight=cluster_weight,
        cluster_size=cluster_size,
        merge_weight=merge_weight,
        split_weight=split_weight,
        patch_accounts_path=str(patch_accounts) if patch_accounts is not None else "",
        spread_accounts_path=str(spread_accounts) if spread_accounts is not None else "",
        block_coordinates_path=str(block_coordinates) if block_coordinates is not None else "",
        cooling_mode=cooling_mode,
        cooling_window=cooling_window,
        mip_bound=mip_bound,
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
def watch(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    targets: Path = typer.Option(..., exists=True, help="Targets YAML (levels are per year)"),
    account: list[str] | None = typer.Option(
        None,
        "--account",
        help="Account to watch; repeat it to watch several, one window each",
    ),
    period_width: int = typer.Option(10, "--period-width", help="Years per period"),
    years: int = typer.Option(50, help="Simulation horizon in years"),
    iterations: int = typer.Option(2000, help="Search iterations"),
    metaheuristic: str = typer.Option("sa", help="sa, tabu, or ils"),
    temperature: float = typer.Option(1000.0, help="Initial SA temperature"),
    cooling: float = typer.Option(0.99, help="SA cooling factor"),
    cooling_mode: str = typer.Option(
        "geometric", "--cooling-mode", help="Temperature schedule: geometric or adaptive"
    ),
    cooling_window: int = typer.Option(
        64, "--cooling-window", help="Iterations per temperature with the adaptive schedule"
    ),
    seed: int = typer.Option(1),
    warm_start: bool = typer.Option(
        False, "--warm-start", help="Seed each block's first candidate"
    ),
    refresh: float = typer.Option(2.0, "--refresh", help="Seconds between repaints (heartbeat)"),
    plain: bool = typer.Option(False, "--plain", help="Print one final frame (no live view)"),
    lns_weight: float = typer.Option(
        0.2, "--lns-weight", help="Weight of the LNS operator (0 disables it)"
    ),
    lns_destroy: float = typer.Option(
        0.1, "--lns-destroy", help="Fraction of the schedule an LNS move destroys"
    ),
    warm_cache: bool = typer.Option(
        False, "--warm-cache", help="Precompute every candidate chain's contribution first"
    ),
    seed_greedy: bool = typer.Option(
        False,
        "--seed-greedy",
        help="Seed the search with a schedule built from the declared targets and ceilings",
    ),
    seed_account: str = typer.Option(
        "",
        "--seed-account",
        help="With --seed-greedy, reduce this target account to its maximum instead of floors",
    ),
    islands: int = typer.Option(0, "--islands", help="Parallel islands (0 = single search)"),
    cluster_weight: float = typer.Option(
        0.0, "--cluster-weight", help="Weight of the topology cluster operator (0 disables it)"
    ),
    cluster_size: int = typer.Option(8, "--cluster-size", help="Blocks per cluster move"),
    patch_accounts: Path = typer.Option(
        None, "--patch-accounts", exists=True, help="Patch size-distribution accounts (YAML)"
    ),
    spread_accounts: Path = typer.Option(
        None,
        "--spread-accounts",
        exists=True,
        help="Spread-connectivity accounts (YAML); needs --topology and --block-coordinates",
    ),
    block_coordinates: Path = typer.Option(
        None, "--block-coordinates", exists=True, help="Block centroids (CSV: block, x, y)"
    ),
    route_config: Path = typer.Option(
        None, "--route-config", exists=True, help="Optional route model and route accounts (YAML)"
    ),
    topology: Path = typer.Option(None, exists=True, help="Block topology for spatial constraints"),
    max_opening_ha: float = typer.Option(None, help="Maximum opening size, in hectares"),
    min_green_up_years: int = typer.Option(None, help="Green-up interval, in years"),
    core_buffer_m: float = typer.Option(
        None, "--core-buffer-m", help="Core-area buffer, in metres"
    ),
    min_core_area_ha: float = typer.Option(
        None, "--min-core-area-ha", help="Minimum core area, in hectares"
    ),
) -> None:
    """Watch realized versus target account values while the search runs."""
    target_list = load_targets(targets)
    accounts = tuple(account) if account else tuple(sorted({t.account for t in target_list}))
    if not accounts:
        print("[red]No account to watch: pass --account or put a target in the file.[/]")
        raise typer.Exit(code=1)
    cfg = OptimizeConfig(
        seed=seed,
        years=years,
        iterations=iterations,
        metaheuristic=metaheuristic,
        temperature=temperature,
        cooling=cooling,
        warm_start=warm_start,
        targets_path=str(targets),
        lns_weight=lns_weight,
        lns_destroy=lns_destroy,
        warm_cache=warm_cache,
        greedy_seed=seed_greedy,
        seed_account=seed_account,
        islands=islands,
        workers=islands,
        cluster_weight=cluster_weight,
        cluster_size=cluster_size,
        patch_accounts_path=str(patch_accounts) if patch_accounts is not None else "",
        spread_accounts_path=str(spread_accounts) if spread_accounts is not None else "",
        block_coordinates_path=str(block_coordinates) if block_coordinates is not None else "",
        topology_path=str(topology) if topology is not None else "",
        route_config_path=str(route_config) if route_config is not None else "",
        max_opening_ha=max_opening_ha,
        min_green_up_years=min_green_up_years,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
        cooling_mode=cooling_mode,
        cooling_window=cooling_window,
    )
    optimizer = Optimizer.from_dataset(dataset, cfg)
    summary = run_watch(
        optimizer,
        target_list,
        accounts,
        period_width=period_width,
        label=" + ".join(accounts),
        refresh=refresh,
        plain=plain,
    )
    table = Table(title="Watch summary")
    table.add_column("key")
    table.add_column("value")
    for key, value in summary.items():
        table.add_row(str(key), f"{value:.4g}" if isinstance(value, float) else str(value))
    print(table)


@app.command()
def calibrate(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    targets: Path = typer.Option(..., exists=True, help="Targets YAML to calibrate"),
    out: Path = typer.Option(..., "--out", help="Calibrated targets YAML"),
    iterations: int = typer.Option(2000, help="Pilot search iterations"),
    samples: int = typer.Option(32, help="Times the per-term penalties are sampled"),
    seed: int = typer.Option(42),
    years: int = typer.Option(50, help="Simulation horizon in years"),
    topology: Path = typer.Option(None, exists=True, help="Block topology, for patch accounts"),
    patch_accounts: Path = typer.Option(
        None, "--patch-accounts", exists=True, help="Patch size-distribution accounts (YAML)"
    ),
    spread_accounts: Path = typer.Option(
        None,
        "--spread-accounts",
        exists=True,
        help="Spread-connectivity accounts (YAML); needs --topology and --block-coordinates",
    ),
    block_coordinates: Path = typer.Option(
        None, "--block-coordinates", exists=True, help="Block centroids (CSV: block, x, y)"
    ),
    warm_start: bool = typer.Option(
        False, "--warm-start", help="Start the pilot from each block's first candidate"
    ),
) -> None:
    """Balance target weights from a pilot search and write a targets file."""
    target_list = load_targets(targets)
    cfg = OptimizeConfig(
        years=years,
        iterations=iterations,
        seed=seed,
        targets_path=str(targets),
        topology_path=str(topology) if topology is not None else "",
        patch_accounts_path=str(patch_accounts) if patch_accounts is not None else "",
        spread_accounts_path=str(spread_accounts) if spread_accounts is not None else "",
        block_coordinates_path=str(block_coordinates) if block_coordinates is not None else "",
    )
    optimizer = Optimizer.from_dataset(dataset, cfg)
    calibrated = run_calibration(
        optimizer,
        target_list,
        iterations=iterations,
        seed=seed,
        samples=samples,
        warm_start=warm_start,
    )
    write_targets(out, calibrated)
    table = Table(title="Calibrated weights")
    table.add_column("account")
    table.add_column("year")
    table.add_column("min weight")
    table.add_column("max weight")
    for before, after in zip(target_list, calibrated, strict=True):
        table.add_row(
            before.account, str(before.year), f"{after.min_weight:.4g}", f"{after.max_weight:.4g}"
        )
    print(table)
    print(f"[bold green]Calibrated targets[/] → {out}")


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


@app.command()
def serve(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    runs: Path = typer.Option(..., exists=True, help="Directory holding run directories"),
    targets: Path | None = typer.Option(None, "--targets", help="Targets YAML to read and replace"),
    geometry: Path | None = typer.Option(
        None, "--geometry", help="GeoJSON of block points or polygons"
    ),
    topology: Path | None = typer.Option(
        None, "--topology", exists=True, help="Block topology for patch membership on new runs"
    ),
    patch_accounts: Path | None = typer.Option(
        None, "--patch-accounts", exists=True, help="Patch accounts for new runs"
    ),
    spread_accounts: Path | None = typer.Option(
        None,
        "--spread-accounts",
        exists=True,
        help="Spread accounts for new runs; needs --topology and --block-coordinates",
    ),
    block_coordinates: Path | None = typer.Option(
        None, "--block-coordinates", exists=True, help="Block centroids for spread accounts"
    ),
    route_config: Path | None = typer.Option(
        None, "--route-config", exists=True, help="Route model and accounts for new runs"
    ),
    roads: Path | None = typer.Option(
        None, "--roads", exists=True, help="GeoJSON access-road lines for the map overlay"
    ),
    crs: str = typer.Option(
        "EPSG:4326", "--crs", help="Source CRS of --geometry and --roads (MapLibre uses WGS84)"
    ),
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8000, help="Bind port"),
    root_path: str = typer.Option(
        "", "--root-path", help="URL prefix when served behind a proxy, e.g. /user/me/proxy/8000"
    ),
    allow_remote: bool = typer.Option(
        False, "--allow-remote", help="Allow a non-loopback bind (no authentication is provided)"
    ),
    allow_runs: bool = typer.Option(
        False, "--allow-runs", help="Allow the UI to start a search with the configured targets"
    ),
    allow_agent: bool = typer.Option(
        False,
        "--allow-agent",
        help="Allow the embedded OpenCode chat agent (it can run commands and edit files)",
    ),
    agent_model: str = typer.Option(
        "opencode-go/deepseek-v4.1-flash",
        "--agent-model",
        help="Provider/model the chat agent runs (the OpenCode CLI's own login is used)",
    ),
    agent_cwd: Path | None = typer.Option(
        None, "--agent-cwd", help="Working directory for the chat agent (default: the service's)"
    ),
) -> None:
    """Serve the read-only web API over a dataset and its runs (needs the ``web`` extra)."""
    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_remote:
        raise typer.BadParameter("refusing a non-loopback bind without --allow-remote")
    try:
        from .web.app import create_app
    except ImportError as error:
        raise typer.BadParameter(
            "the web extra is not installed: pip install 'ws4[web]'"
        ) from error
    import uvicorn

    uvicorn.run(
        create_app(
            dataset=dataset,
            runs=runs,
            targets=targets,
            geometry=geometry,
            allow_runs=allow_runs,
            allow_agent=allow_agent,
            agent_model=agent_model,
            agent_cwd=agent_cwd,
            topology=topology,
            patch_accounts=patch_accounts,
            spread_accounts=spread_accounts,
            block_coordinates=block_coordinates,
            route_config=route_config,
            roads=roads,
            crs=crs,
        ),
        host=host,
        port=port,
        root_path=root_path,
    )


if __name__ == "__main__":
    app()
