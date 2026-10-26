"""Command-line interface for WS4: build, simulate, optimize, and validate."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import typer
from rich import print
from rich.table import Table

from .build.compiler import build_canonical_dataset
from .build.legacy import ingest_legacy_matrix
from .carbon import (
    CarbonEngineError,
    GcbmResultsError,
    block_areas_from_dataset,
    build_sit_tables,
    build_sit_tables_from_tables,
    compare_gcbm_to_carbon,
    fertilization_accounts,
    load_carbon_package,
    load_fertilization_config,
    merge_carbon_accounts,
    read_dataset_tables,
    read_gcbm_results,
    read_schedule,
    run_libcbm,
    with_fertilization_curves,
    with_fertilization_disturbances,
    with_fertilization_recovery,
    write_carbon_run,
    write_gcbm_results,
    write_sit_tables,
)
from .disturbance import (
    DisturbanceError,
    events_for_block,
    load_disturbance_events,
    summarize_disturbance_events,
)
from .io.hydrology import (
    HYDROLOGY_READINESS_POLICIES,
    FemicHydrologyError,
    assess_femic_hydrology_readiness,
    bundle_pin,
    enforce_hydrology_readiness,
    load_femic_hydrology_bundle,
    load_hydrology_crosswalk,
    load_hydrology_mapping,
    load_registered_femic_hydrology_bundle,
    map_femic_hydrology_to_dataset,
    register_femic_hydrology_bundle,
    screen_schedule_flood_risk,
    validate_femic_hydrology_bundle,
    validate_registered_femic_hydrology,
    write_hydrology_mapping,
    write_hydrology_screen,
)
from .io.lidar import (
    FemicLidarError,
    integrate_lidar_mapping_into_dataset,
    load_registered_femic_lidar_bundle,
    map_femic_canopy_to_fragments,
    map_femic_lidar_to_fragments,
    read_registered_femic_lidar,
    register_femic_lidar_bundle,
    validate_registered_femic_lidar,
    write_canopy_mapping,
    write_lidar_mapping,
)
from .model.schema import validate_dataset
from .opt.calibrate import calibrate as run_calibration
from .opt.calibrate import write_targets
from .opt.engine import OptimizeConfig, Optimizer, load_schedule_csv
from .opt.exact import solve_option_model, write_exact_result
from .opt.objective import load_targets
from .opt.repro import dataset_quality
from .opt.watch import run_watch
from .patch.accounts import load_patch_accounts
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
    lidar_bundle: Path | None = typer.Option(
        None,
        "--lidar-bundle",
        exists=True,
        file_okay=False,
        help="Optional FEMIC LidarBC bundle to register in the dataset",
    ),
    lidar_bundle_id: str | None = typer.Option(
        None, "--lidar-bundle-id", help="Expected FEMIC bundle id"
    ),
    lidar_bundle_version: str | None = typer.Option(
        None, "--lidar-bundle-version", help="Expected FEMIC bundle version"
    ),
) -> None:
    """Compile a canonical dataset from an XML recipe and a *fragments* shapefile.

    Notes
    -----
      • Launch control files are not required here (they are used to *launch*,
        not *build*).
      • Block geometry is not required to build (it is a runtime view).
    """
    out = build_canonical_dataset(xml_path=xml, fragments_path=fragments, out_dir=out)
    if lidar_bundle is not None:
        try:
            registration = register_femic_lidar_bundle(
                out,
                lidar_bundle,
                expected_bundle_id=lidar_bundle_id,
                expected_bundle_version=lidar_bundle_version,
            )
        except FemicLidarError as error:
            raise typer.BadParameter(str(error)) from error
        print(f"[bold green]Registered LidarBC bundle[/] → {registration['bundle_id']}")
    print(f"[bold green]Built dataset[/] → {out}")


@app.command()
def simulate(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    schedule: Path = typer.Option(..., exists=True, help="CSV: block_id,treatment,offset"),
    years: int = typer.Option(200, help="Simulation horizon in years"),
    out: Path = typer.Option(..., help="Output directory"),
    topology: Path = typer.Option(None, exists=True, help="Block topology for spatial metrics"),
    patch_accounts: Path = typer.Option(
        None, "--patch-accounts", exists=True, help="Patch size-distribution accounts (YAML)"
    ),
    patch_membership: bool = typer.Option(
        False, "--patch-membership", help="Write patch_membership.csv"
    ),
    route_config: Path = typer.Option(
        None, "--route-config", exists=True, help="Optional route model and route accounts (YAML)"
    ),
    flood_screen_config: Path | None = typer.Option(
        None,
        "--flood-screen-config",
        exists=True,
        dir_okay=False,
        help="Optional flood-screen config (hydrology response accounts)",
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
        patch_accounts=load_patch_accounts(patch_accounts) if patch_accounts is not None else (),
        patch_membership=patch_membership,
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
def carbon(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    package: Path = typer.Option(..., exists=True, help="FEMIC carbon package directory"),
    schedule: Path = typer.Option(..., exists=True, help="CSV: block_id,treatment,offset"),
    out: Path = typer.Option(..., help="Output directory for the carbon run"),
    years: int | None = typer.Option(
        None, help="Annual timesteps; defaults to the latest schedule offset plus one"
    ),
    audit_sit: bool = typer.Option(
        False, "--audit-sit", help="Write the generated SIT tables under carbon_sit/"
    ),
    allow_defaults_mismatch: bool = typer.Option(
        False,
        "--allow-defaults-mismatch",
        help="Allow a package/cbm_defaults mismatch for an explicit comparison",
    ),
    density: bool = typer.Option(
        False, "--density", help="Write tC/ha instead of tC in the pool and flux tables"
    ),
    fertilization_config: Path | None = typer.Option(
        None,
        "--fertilization-config",
        exists=True,
        help="Fertilization YAML; enables f1/f2/f3 curves, growth, and emissions accounts",
    ),
    merge_into: Path | None = typer.Option(
        None,
        "--merge-into",
        exists=True,
        help="Optional simulation run directory to receive the carbon accounts",
    ),
) -> None:
    """Run libcbm for a compiled dataset, a carbon package, and a schedule."""
    schedule_frame = read_schedule(schedule)
    latest_offset = int(schedule_frame["offset"].max()) if not schedule_frame.empty else -1
    n_steps = int(years) if years is not None else latest_offset + 1
    if n_steps <= latest_offset:
        print("[red]--years must run past the latest scheduled offset[/red]")
        raise typer.Exit(code=1)
    fertilization = None
    try:
        loaded = load_carbon_package(package)
        run_fertilization = None
        simulation_schedule = schedule_frame
        if fertilization_config is not None:
            fertilization = load_fertilization_config(fertilization_config)
            if fertilization.uses_curves:
                fragments, tracks, treatments = read_dataset_tables(dataset)
                loaded, tracks, treatments = with_fertilization_curves(
                    loaded,
                    tracks,
                    treatments,
                    fertilization,
                )
                simulation_schedule = with_fertilization_recovery(
                    schedule_frame,
                    fragments,
                    tracks,
                    fertilization,
                )
                tables = build_sit_tables_from_tables(
                    loaded,
                    fragments,
                    tracks,
                    treatments,
                    simulation_schedule,
                )
            else:
                loaded = with_fertilization_disturbances(loaded, fertilization)
                run_fertilization = fertilization
                tables = build_sit_tables(loaded, dataset, schedule_frame)
        else:
            tables = build_sit_tables(loaded, dataset, schedule_frame)
        if years is None and not simulation_schedule.empty:
            n_steps = max(n_steps, int(simulation_schedule["offset"].max()) + 1)
        if audit_sit:
            write_sit_tables(tables, out / "carbon_sit")
        run = run_libcbm(
            loaded,
            tables,
            n_steps=n_steps,
            density=density,
            allow_defaults_mismatch=allow_defaults_mismatch,
            fertilization=run_fertilization,
        )
        extra_accounts = None
        extra_manifest = None
        if fertilization is not None:
            extra_accounts = fertilization_accounts(
                schedule_frame,
                block_areas_from_dataset(dataset),
                fertilization,
            )
            extra_manifest = fertilization.manifest()
            if not extra_accounts.empty:
                extra_manifest["total_area_ha"] = float(
                    extra_accounts.loc[
                        extra_accounts["account"] == "fertilization.area_ha", "value"
                    ].sum()
                )
                extra_manifest["total_co2e_t"] = float(
                    extra_accounts.loc[
                        extra_accounts["account"] == "fertilization.co2e_t", "value"
                    ].sum()
                )
        result = write_carbon_run(
            run,
            out,
            package=loaded,
            dataset_dir=dataset,
            schedule=schedule_frame,
            n_steps=n_steps,
            density=density,
            extra_accounts=extra_accounts,
            extra_manifest=extra_manifest,
        )
    except CarbonEngineError as exc:
        print(f"[red]Carbon run failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        print(f"[red]Carbon run failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if merge_into is not None:
        try:
            merge_carbon_accounts(
                merge_into,
                result.accounts_path,
                carbon_manifest=result.manifest_path,
            )
        except CarbonEngineError as exc:
            print(f"[red]Carbon account merge failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        print(f"[green]Carbon accounts merged[/green] → {merge_into}")

    print(f"[bold green]Carbon run complete[/] → {out}")
    print(
        f"timesteps={result.n_steps} ecosystem_start_tc={result.ecosystem_start_tc:.1f} "
        f"ecosystem_end_tc={result.ecosystem_end_tc:.1f}"
    )
    print(f"pools: {result.pools_path}")
    print(f"flux: {result.flux_path}")
    print(f"accounts: {result.accounts_path}")
    print(f"manifest: {result.manifest_path}")


@app.command()
def gcbm(
    results: Path = typer.Option(..., "--results", exists=True, help="GCBM gcbm_output.db"),
    out: Path = typer.Option(..., help="Output directory for the GCBM summary"),
    compare_carbon: Path | None = typer.Option(
        None,
        "--compare-carbon",
        exists=True,
        help="Optional WS4 carbon run directory to compare against",
    ),
) -> None:
    """Read a raw GCBM results database and optionally compare it with WS4."""
    try:
        loaded = read_gcbm_results(results)
        summary = write_gcbm_results(loaded, out)
    except GcbmResultsError as exc:
        print(f"[red]GCBM results failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    print(f"[bold green]GCBM results summarized[/] → {out}")
    print(
        f"locations={loaded.locations['location_id'].nunique()} "
        f"steps={loaded.dates['step'].nunique()} "
        f"ecosystem_start_tc={summary.ecosystem_start_tc:.1f} "
        f"ecosystem_end_tc={summary.ecosystem_end_tc:.1f}"
    )
    print(f"pools: {summary.pools_path}")
    print(f"fluxes: {summary.fluxes_path}")
    print(f"accounts: {summary.accounts_path}")
    if compare_carbon is not None:
        carbon_accounts = compare_carbon / "carbon_accounts.csv"
        if not carbon_accounts.is_file():
            print(f"[red]Missing WS4 carbon accounts:[/red] {carbon_accounts}")
            raise typer.Exit(code=1)
        comparison = compare_gcbm_to_carbon(pd.read_csv(summary.accounts_path), carbon_accounts)
        comparison_path = out / "gcbm_compare.csv"
        comparison.to_csv(comparison_path, index=False)
        max_abs = float(comparison["difference_tc"].abs().max()) if not comparison.empty else 0.0
        print(f"comparison: {comparison_path} max_abs_tc={max_abs:.3f}")


@app.command()
def optimize(
    dataset: Path = typer.Option(..., exists=True),
    targets: Path = typer.Option(..., exists=True),
    initial_schedule: Path | None = typer.Option(
        None,
        "--initial-schedule",
        exists=True,
        help="Schedule CSV (block_id,treatment,period) to start the search from",
    ),
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
    reversion: int = typer.Option(
        0,
        "--reversion",
        min=0,
        help="Reset the current solution to the incumbent every N accepted moves; 0 disables it",
    ),
    engine: str = typer.Option(
        "sa", "--engine", "--metaheuristic", help="sa, tabu, ils, or threshold"
    ),
    threshold: float = typer.Option(
        1.0, "--threshold", help="Initial threshold for the threshold-accepting engine"
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
    flood_screen_config: Path | None = typer.Option(
        None,
        "--flood-screen-config",
        exists=True,
        dir_okay=False,
        help="Optional flood-screen config (hydrology response accounts)",
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
    spatial_weight: float = typer.Option(
        1.0,
        "--spatial-weight",
        help="Weight on the opening/green-up/core-area penalty",
    ),
    spatial_override: bool = typer.Option(
        False, "--spatial-override", help="Allow schedules that violate the spatial constraints"
    ),
    constraint_strategy: str = typer.Option(
        "penalize",
        "--constraint-strategy",
        help="Spatial policy: penalize (default), reject, or repair",
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
    coalesce_weight: float = typer.Option(
        0.0,
        "--coalesce-weight",
        help="Weight of the coalesce operator, which aligns a connected cluster to one year",
    ),
    coalesce_size: int = typer.Option(8, "--coalesce-size", help="Blocks per coalesce move"),
    coalesce_min_area_ha: float = typer.Option(
        5.0,
        "--coalesce-min-area-ha",
        help="Smallest opening area a coalesce move will build",
    ),
    coalesce_max_area_ha: float = typer.Option(
        40.0,
        "--coalesce-max-area-ha",
        help="Largest opening area a coalesce move will build",
    ),
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
    carbon_package: Path | None = typer.Option(
        None,
        "--carbon-package",
        exists=True,
        help="FEMIC carbon package; enables carbon accounts and carbon.* targets",
    ),
    carbon_fertilization: Path | None = typer.Option(
        None,
        "--carbon-fertilization",
        exists=True,
        help="Fertilization YAML; adds f1/f2/f3 growth response and emissions to the ledger",
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
    lp_bound: bool = typer.Option(
        False, "--lp-bound", help="Record an LP relaxation bound and gap in the summary"
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
        reversion=reversion,
        metaheuristic=engine,
        threshold=threshold,
        years=years,
        seed=seed,
        islands=islands,
        episodes=episodes,
        targets_path=str(targets),
        initial_schedule_path=(str(initial_schedule) if initial_schedule is not None else ""),
        weights_path=str(weights) if weights is not None else "",
        topology_path=str(topology) if topology is not None else "",
        route_config_path=str(route_config) if route_config is not None else "",
        flood_screen_config_path=(
            str(flood_screen_config) if flood_screen_config is not None else ""
        ),
        edge_elements_path=str(edge_elements) if edge_elements is not None else "",
        max_opening_ha=max_opening_ha,
        min_green_up_years=min_green_up_years,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
        spatial_weight=spatial_weight,
        allow_spatial_override=spatial_override,
        constraint_strategy=constraint_strategy,
        lns_weight=lns_weight,
        lns_destroy=lns_destroy,
        warm_cache=warm_cache,
        greedy_seed=seed_greedy,
        seed_account=seed_account,
        cluster_weight=cluster_weight,
        cluster_size=cluster_size,
        coalesce_weight=coalesce_weight,
        coalesce_size=coalesce_size,
        coalesce_min_area_ha=coalesce_min_area_ha,
        coalesce_max_area_ha=coalesce_max_area_ha,
        merge_weight=merge_weight,
        split_weight=split_weight,
        patch_accounts_path=str(patch_accounts) if patch_accounts is not None else "",
        carbon_package_path=str(carbon_package) if carbon_package is not None else "",
        carbon_fertilization_path=(
            str(carbon_fertilization) if carbon_fertilization is not None else ""
        ),
        spread_accounts_path=str(spread_accounts) if spread_accounts is not None else "",
        block_coordinates_path=str(block_coordinates) if block_coordinates is not None else "",
        cooling_mode=cooling_mode,
        cooling_window=cooling_window,
        mip_bound=mip_bound,
        lp_bound=lp_bound,
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
def quality(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    targets: Path = typer.Option(None, exists=True, help="Optional targets YAML for coverage"),
    sidecar: Path = typer.Option(
        None, exists=True, help="Copy this provenance sidecar into the dataset first"
    ),
    out: Path = typer.Option(None, help="Write quality.json and quality.md here"),
    check: bool = typer.Option(
        False, "--check", help="Fail when provenance is missing or the report is not ok"
    ),
) -> None:
    """Inspect a compiled dataset's provenance and data-quality checks."""
    if sidecar is not None:
        destination = dataset / "data_quality.yaml"
        if sidecar.resolve() != destination.resolve():
            shutil.copyfile(sidecar, destination)
    report = dataset_quality(dataset, targets)
    summary = report["summary"]
    assert isinstance(summary, dict)
    table = Table(title="Dataset quality")
    table.add_column("key")
    table.add_column("value")
    for key in ("status", "provenance_supplied", "metadata_supplied", "table_count"):
        table.add_row(key, str(summary.get(key)))
    for item_check in report["checks"]:
        assert isinstance(item_check, dict)
        table.add_row(f"{item_check['name']} ({item_check['status']})", str(item_check["detail"]))
    print(table)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "quality.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        lines = [
            "# Dataset quality",
            "",
            f"- Status: {summary.get('status')}",
            f"- Provenance supplied: {summary.get('provenance_supplied')}",
            f"- Metadata supplied: {summary.get('metadata_supplied')}",
            "",
            "## Checks",
        ]
        for item_check in report["checks"]:
            assert isinstance(item_check, dict)
            lines.append(
                f"- {item_check['name']}: **{item_check['status']}** — {item_check['detail']}"
            )
        lines.extend(["", "## Limitations"])
        for item in report["limitations"]:
            lines.append(f"- {item}")
        (out / "quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if check and (not summary.get("provenance_supplied") or summary.get("status") != "ok"):
        raise typer.Exit(code=1)


@app.command()
def solve_mip(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    targets: Path = typer.Option(..., exists=True, help="Targets YAML"),
    out: Path = typer.Option(..., help="Output directory"),
    years: int = typer.Option(50, help="Simulation horizon in years"),
    topology: Path = typer.Option(None, exists=True, help="Block topology for opening rows"),
    max_opening_ha: float = typer.Option(
        None, "--max-opening-ha", help="Maximum opening area for the option model"
    ),
    limit_blocks: int = typer.Option(
        None, "--limit-blocks", help="Keep only the first N blocks as a diagnostic subproblem"
    ),
) -> None:
    """Solve the option-selection model exactly for a small instance or subset.

    The model prices additive targets and optional stand-centred opening rows. It does not
    model green-up, core area, patch distribution, routes, or spread connectivity; the
    written report names that boundary and replays the schedule.
    """
    goal_list = load_targets(targets)
    result = solve_option_model(
        dataset,
        goal_list,
        years,
        topology_path=topology,
        max_opening_ha=max_opening_ha,
        limit_blocks=limit_blocks,
    )
    report = write_exact_result(
        out,
        dataset,
        goal_list,
        years,
        result,
        topology_path=topology,
        max_opening_ha=max_opening_ha,
        limit_blocks=limit_blocks,
    )
    table = Table(title="Option-model solve")
    table.add_column("key")
    table.add_column("value")
    for key, value in report.items():
        table.add_row(key, str(value))
    print(table)


@app.command()
def watch(
    dataset: Path = typer.Option(..., exists=True, help="Compiled dataset directory"),
    targets: Path = typer.Option(..., exists=True, help="Targets YAML (levels are per year)"),
    initial_schedule: Path | None = typer.Option(
        None,
        "--initial-schedule",
        exists=True,
        help="Schedule CSV (block_id,treatment,offset) to start the search from",
    ),
    account: list[str] | None = typer.Option(
        None,
        "--account",
        help="Account to watch; repeat it to watch several, one window each",
    ),
    period_width: int = typer.Option(10, "--period-width", help="Years per period"),
    years: int = typer.Option(50, help="Simulation horizon in years"),
    iterations: int = typer.Option(2000, help="Search iterations"),
    metaheuristic: str = typer.Option(
        "sa", "--metaheuristic", "--engine", help="sa, tabu, ils, or threshold"
    ),
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
    flood_screen_config: Path | None = typer.Option(
        None,
        "--flood-screen-config",
        exists=True,
        dir_okay=False,
        help="Optional flood-screen config (hydrology response accounts)",
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
        flood_screen_config_path=(
            str(flood_screen_config) if flood_screen_config is not None else ""
        ),
        max_opening_ha=max_opening_ha,
        min_green_up_years=min_green_up_years,
        core_buffer_m=core_buffer_m,
        min_core_area_ha=min_core_area_ha,
        cooling_mode=cooling_mode,
        cooling_window=cooling_window,
    )
    optimizer = Optimizer.from_dataset(dataset, cfg)
    initial = load_schedule_csv(initial_schedule) if initial_schedule is not None else None
    summary = run_watch(
        optimizer,
        target_list,
        accounts,
        period_width=period_width,
        label=" + ".join(accounts),
        refresh=refresh,
        plain=plain,
        initial=initial,
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
    flood_screen_config: Path | None = typer.Option(
        None,
        "--flood-screen-config",
        exists=True,
        dir_okay=False,
        help="Optional flood-screen config (hydrology response accounts)",
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
        flood_screen_config_path=(
            str(flood_screen_config) if flood_screen_config is not None else ""
        ),
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
def disturbance(
    events: Path = typer.Option(
        ..., "--events", exists=True, help="A femic.disturbance.v1 JSON table"
    ),
    block_id: int | None = typer.Option(
        None, "--block-id", help="Report only events that name this block"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the summary as JSON"),
) -> None:
    """Summarize a FEMIC disturbance table without changing the model."""
    try:
        rows = load_disturbance_events(events)
        if block_id is not None:
            rows = events_for_block(rows, block_id)
    except DisturbanceError as error:
        raise typer.BadParameter(str(error)) from error
    if not rows:
        print(f"[yellow]No disturbance events[/] for block {block_id}")
        return
    summary = summarize_disturbance_events(rows)
    if json_output:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    table = Table(title="Disturbance events")
    table.add_column("event")
    table.add_column("year")
    table.add_column("type")
    table.add_column("severity")
    table.add_column("blocks")
    table.add_column("area_ha", justify="right")
    for event in rows:
        blocks = ", ".join(str(block) for block in event.block_ids) or "-"
        area = f"{event.area_ha:.1f}" if event.area_ha is not None else "-"
        table.add_row(
            event.event_id,
            str(event.year),
            event.event_type,
            event.severity_class,
            blocks,
            area,
        )
    print(table)
    affected_blocks = summary["affected_blocks"]
    block_count = len(affected_blocks) if isinstance(affected_blocks, list) else 0
    print(
        f"[bold]events[/]: {summary['event_count']}  "
        f"[bold]years[/]: {summary['year_min']}-{summary['year_max']}  "
        f"[bold]blocks[/]: {block_count}"
    )


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
    geometry_overview: Path | None = typer.Option(
        None,
        "--geometry-overview",
        help="Coarser GeoJSON for low-zoom tiles; detail zooms use --geometry",
    ),
    land_base: Path | None = typer.Option(
        None,
        "--land-base",
        help="Optional GeoJSON polygon drawn under the blocks as non-forest land",
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
    tile_cache: Path | None = typer.Option(
        None,
        "--tile-cache",
        help="Directory for durable MVT tiles (default: memory only)",
    ),
    crs: str = typer.Option(
        "EPSG:4326",
        "--crs",
        help="Source CRS of --geometry, --land-base and --roads (MapLibre uses WGS84)",
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
    if patch_accounts is not None and topology is None:
        raise typer.BadParameter("--patch-accounts needs --topology")
    if spread_accounts is not None and (topology is None or block_coordinates is None):
        raise typer.BadParameter("--spread-accounts needs --topology and --block-coordinates")
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
            geometry_overview=geometry_overview,
            land_base=land_base,
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
            tile_cache_dir=tile_cache,
            crs=crs,
        ),
        host=host,
        port=port,
        root_path=root_path,
    )


lidar_app = typer.Typer(help="Register and inspect FEMIC LidarBC products.")


@lidar_app.command("register")
def lidar_register(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
    bundle: Path = typer.Option(..., "--bundle", exists=True, file_okay=False),
    bundle_id: str | None = typer.Option(None, "--bundle-id"),
    bundle_version: str | None = typer.Option(None, "--bundle-version"),
) -> None:
    """Register a validated FEMIC bundle in a compiled dataset."""
    try:
        registration = register_femic_lidar_bundle(
            dataset,
            bundle,
            expected_bundle_id=bundle_id,
            expected_bundle_version=bundle_version,
        )
    except FemicLidarError as error:
        print(f"[bold red]LidarBC registration failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(
        f"[bold green]Registered[/] {registration['bundle_id']} @ {registration['bundle_version']}"
    )


@lidar_app.command("inspect")
def lidar_inspect(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
) -> None:
    """Print the FEMIC bundle pin registered in a dataset."""
    try:
        registration = read_registered_femic_lidar(dataset)
    except FemicLidarError as error:
        print(f"[bold red]LidarBC inspect failed:[/] {error}")
        raise typer.Exit(code=1) from error
    if registration is None:
        print("No FEMIC LidarBC product is registered.")
        return
    print(json.dumps(registration, indent=2, sort_keys=True))


@lidar_app.command("validate")
def lidar_validate(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
) -> None:
    """Revalidate the FEMIC bundle currently pinned by a dataset."""
    try:
        report = validate_registered_femic_lidar(dataset)
    except FemicLidarError as error:
        print(f"[bold red]LidarBC validation failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if not report.is_valid:
        raise typer.Exit(code=1)


@lidar_app.command("map")
def lidar_map(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
    fragments: Path = typer.Option(..., "--fragments", exists=True),
    out: Path = typer.Option(..., "--out", help="Mapping output directory"),
    product: list[str] | None = typer.Option(
        None, "--product", help="Product to map; repeat for multiple products"
    ),
    statistic: list[str] | None = typer.Option(
        None, "--statistic", help="Statistic to compute; repeat for multiple statistics"
    ),
    fragment_id_field: str = typer.Option("fragment_id", "--fragment-id-field"),
    block_id_field: str = typer.Option("block_id", "--block-id-field"),
    area_field: str = typer.Option("area_ha", "--area-field"),
) -> None:
    """Map registered terrain/canopy products to fragment and block support."""
    try:
        bundle = load_registered_femic_lidar_bundle(dataset)
        result = map_femic_lidar_to_fragments(
            bundle,
            fragments,
            products=tuple(product or ("slope", "chm")),
            statistics=tuple(statistic or ("mean", "p95")),
            id_field=fragment_id_field,
            block_field=block_id_field,
            area_field=area_field,
        )
        paths = write_lidar_mapping(result, out)
    except FemicLidarError as error:
        print(f"[bold red]LidarBC map failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(f"fragments: {len(result.fragments)}")
    print(f"blocks: {len(result.blocks)}")
    print(f"fragments_csv: {paths['fragments']}")
    print(f"blocks_csv: {paths['blocks']}")
    print(f"manifest: {paths['manifest']}")


@lidar_app.command("canopy")
def lidar_canopy(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
    fragments: Path = typer.Option(..., "--fragments", exists=True),
    out: Path = typer.Option(..., "--out", help="Canopy mapping output directory"),
    vri: Path | None = typer.Option(None, "--vri", help="Optional VRI layer"),
    vri_height_field: str = typer.Option("proj_height_1", "--vri-height-field"),
    vri_cover_field: str = typer.Option("crown_closure", "--vri-cover-field"),
    tree_product: str | None = typer.Option(
        None, "--tree-product", help="Optional individual-tree bundle product name"
    ),
    tree_height_field: str = typer.Option("height_m", "--tree-height-field"),
    tree_species_field: str = typer.Option("species", "--tree-species-field"),
    fragment_id_field: str = typer.Option("fragment_id", "--fragment-id-field"),
    block_id_field: str = typer.Option("block_id", "--block-id-field"),
    area_field: str = typer.Option("area_ha", "--area-field"),
) -> None:
    """Map CHM/canopy metrics, VRI uncertainty, and optional trees to WS4 support."""
    try:
        bundle = load_registered_femic_lidar_bundle(dataset)
        result = map_femic_canopy_to_fragments(
            bundle,
            fragments,
            vri_path=vri,
            vri_height_field=vri_height_field,
            vri_cover_field=vri_cover_field,
            tree_product=tree_product,
            tree_height_field=tree_height_field,
            tree_species_field=tree_species_field,
            id_field=fragment_id_field,
            block_field=block_id_field,
            area_field=area_field,
        )
        paths = write_canopy_mapping(result, out)
    except FemicLidarError as error:
        print(f"[bold red]LidarBC canopy mapping failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(f"fragments: {len(result.fragments)}")
    print(f"blocks: {len(result.blocks)}")
    if result.vri_summary is not None:
        print(f"vri_matched_supports: {result.vri_summary['matched_supports']}")
    if result.tree_summary is not None:
        print(f"trees: {result.tree_summary['tree_count']}")
    print(f"fragments_csv: {paths['fragments']}")
    print(f"blocks_csv: {paths['blocks']}")
    print(f"manifest: {paths['manifest']}")


@lidar_app.command("integrate")
def lidar_integrate(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False),
    fragments_mapping: Path = typer.Option(
        ..., "--fragments-mapping", exists=True, help="lidar_fragments.csv"
    ),
    blocks_mapping: Path | None = typer.Option(
        None, "--blocks-mapping", exists=True, help="lidar_blocks.csv or canopy_blocks.csv"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing LiDAR fields"),
) -> None:
    """Write LiDAR mapping fields into the compiled dataset."""
    try:
        result = integrate_lidar_mapping_into_dataset(
            dataset,
            fragments_mapping,
            block_mapping_path=blocks_mapping,
            overwrite=overwrite,
        )
    except FemicLidarError as error:
        print(f"[bold red]LidarBC integration failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(f"bundle_id: {result.bundle_id}")
    print(f"fragment_fields: {', '.join(result.fragment_fields)}")
    print(f"block_fields: {', '.join(result.block_fields)}")
    print(f"fragment_rows: {result.fragment_rows}")
    print(f"block_rows: {result.block_rows}")


hydrology_app = typer.Typer(
    help="Register, inspect, and validate FEMIC hydrology response bundles."
)


@hydrology_app.command("readiness")
def hydrology_readiness(
    bundle: Path | None = typer.Argument(None, exists=True, help="Bundle directory or manifest"),
    dataset: Path | None = typer.Option(
        None,
        "--dataset",
        exists=True,
        file_okay=False,
        help="Read evidence from the hydrology bundle registered in a dataset",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON evidence report"
    ),
) -> None:
    """Report FEMIC validation-report and model-card evidence."""
    if (bundle is None) == (dataset is None):
        print("[bold red]Provide exactly one of BUNDLE or --dataset.[/]")
        raise typer.Exit(code=1)
    try:
        if dataset is not None:
            loaded = load_registered_femic_hydrology_bundle(dataset)
        else:
            assert bundle is not None
            loaded = load_femic_hydrology_bundle(bundle)
        readiness = assess_femic_hydrology_readiness(loaded)
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology readiness failed:[/] {error}")
        raise typer.Exit(code=1) from error
    if json_output:
        typer.echo(json.dumps(readiness.to_dict(), indent=2, sort_keys=True))
        return
    print(f"status: {readiness.status}")
    print(f"review_status: {readiness.review_status or '(missing)'}")
    print(f"validation_report_id: {readiness.validation_report_id or '(missing)'}")
    print(f"model_card_id: {readiness.model_card_id or '(missing)'}")
    print(f"hydrologist_review_recorded: {readiness.hydrologist_review_recorded}")
    print(f"tail_check_failures: {len(readiness.tail_check_failures)}")
    print(f"benchmark_not_evaluated: {readiness.benchmark_not_evaluated}")
    print(f"evidence_sha256: {readiness.evidence_sha256}")
    for warning in readiness.warnings:
        print(f"warning: {warning}")


@hydrology_app.command("map")
def hydrology_map(
    dataset: Path = typer.Option(
        ..., "--dataset", exists=True, file_okay=False, help="Compiled WS4 dataset"
    ),
    crosswalk: Path = typer.Option(
        ..., "--crosswalk", exists=True, dir_okay=False, help="Explicit crosswalk CSV"
    ),
    metadata: Path | None = typer.Option(
        None,
        "--metadata",
        exists=True,
        dir_okay=False,
        help="Optional crosswalk review metadata JSON",
    ),
    out: Path = typer.Option(..., "--out", help="Mapping output directory"),
    allow_partial: bool = typer.Option(
        False, "--allow-partial", help="Record unmapped supports instead of failing"
    ),
) -> None:
    """Map explicit crosswalk rows to FEMIC units, watersheds, and receptors."""
    try:
        bundle = load_registered_femic_hydrology_bundle(dataset)
        loaded = load_hydrology_crosswalk(crosswalk, metadata_path=metadata)
        mapping = map_femic_hydrology_to_dataset(
            dataset,
            bundle,
            loaded,
            allow_partial=allow_partial,
        )
        paths = write_hydrology_mapping(mapping, out)
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology mapping failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(f"mapping_id: {mapping.mapping_id}")
    print(f"review_status: {mapping.review_status}")
    print(f"fragments: {len(mapping.fragments)}")
    print(f"blocks: {len(mapping.blocks)}")
    coverage = mapping.coverage
    unmapped_fragments = coverage.get("unmapped_fragments", [])
    unmapped_blocks = coverage.get("unmapped_blocks", [])
    print(
        "unmapped_fragments: "
        f"{len(unmapped_fragments) if isinstance(unmapped_fragments, list) else 0}"
    )
    print(f"unmapped_blocks: {len(unmapped_blocks) if isinstance(unmapped_blocks, list) else 0}")
    for warning in mapping.warnings:
        print(f"warning: {warning}")
    print(f"fragments_csv: {paths['fragments']}")
    print(f"blocks_csv: {paths['blocks']}")
    print(f"manifest: {paths['manifest']}")


@hydrology_app.command("screen")
def hydrology_screen(
    dataset: Path = typer.Option(
        ..., "--dataset", exists=True, file_okay=False, help="Compiled WS4 dataset"
    ),
    mapping: Path = typer.Option(
        ..., "--mapping", exists=True, help="Mapping directory or manifest"
    ),
    schedule: Path = typer.Option(
        ..., "--schedule", exists=True, dir_okay=False, help="WS4 schedule CSV"
    ),
    out: Path = typer.Option(..., "--out", help="Screening output directory"),
    covariates: Path | None = typer.Option(
        None,
        "--covariates",
        exists=True,
        dir_okay=False,
        help="Optional JSON object of global response covariates",
    ),
    scenario_tolerance: float = typer.Option(
        0.05,
        "--scenario-tolerance",
        min=0.000001,
        help="Maximum feature difference when selecting a response scenario",
    ),
    allow_refused: bool = typer.Option(
        False, "--allow-refused", help="Write inside-domain rows plus refusals"
    ),
    readiness_policy: str = typer.Option(
        "allow_provisional",
        "--readiness-policy",
        help="Readiness policy: " + ", ".join(HYDROLOGY_READINESS_POLICIES),
    ),
    allow_tail_failures: bool = typer.Option(
        False,
        "--allow-tail-failures",
        help="Explicitly permit tail-check-blocked evidence under allow_provisional",
    ),
) -> None:
    """Screen a schedule against FEMIC response and flood-risk rows."""
    try:
        bundle = load_registered_femic_hydrology_bundle(dataset)
        readiness = assess_femic_hydrology_readiness(bundle)
        enforce_hydrology_readiness(
            readiness,
            policy=readiness_policy,
            allow_tail_failures=allow_tail_failures,
        )
        loaded_mapping = load_hydrology_mapping(mapping)
        supplied: dict[str, float] = {}
        if covariates is not None:
            payload = json.loads(covariates.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise FemicHydrologyError("Covariates must be a JSON object.")
            supplied = {str(key): float(value) for key, value in payload.items()}
        mapping_manifest = mapping / "hydrology_mapping.json" if mapping.is_dir() else mapping
        result = screen_schedule_flood_risk(
            dataset,
            bundle,
            loaded_mapping,
            schedule,
            mapping_manifest_path=mapping_manifest,
            covariates=supplied,
            scenario_tolerance=scenario_tolerance,
            allow_refused=allow_refused,
        )
        paths = write_hydrology_screen(result, out)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[bold red]Hydrology screening failed:[/] {error}")
        raise typer.Exit(code=1) from error
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology screening failed:[/] {error}")
        raise typer.Exit(code=1) from error
    print(f"screen_id: {result.screen_id}")
    print(f"rows: {len(result.rows)}")
    print(f"refusals: {len(result.refusals)}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    print(f"screen_csv: {paths['rows']}")
    print(f"manifest: {paths['manifest']}")


@hydrology_app.command("register")
def hydrology_register(
    dataset: Path = typer.Option(
        ..., "--dataset", exists=True, file_okay=False, help="Compiled WS4 dataset"
    ),
    bundle: Path = typer.Option(
        ..., "--bundle", exists=True, file_okay=False, help="FEMIC hydrology bundle"
    ),
    bundle_id: str | None = typer.Option(None, "--bundle-id"),
    bundle_version: str | None = typer.Option(None, "--bundle-version"),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON registration record"
    ),
) -> None:
    """Register a validated FEMIC hydrology bundle in a compiled dataset."""
    try:
        registration = register_femic_hydrology_bundle(
            dataset,
            bundle,
            expected_bundle_id=bundle_id,
            expected_bundle_version=bundle_version,
        )
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology registration failed:[/] {error}")
        raise typer.Exit(code=1) from error
    if json_output:
        typer.echo(json.dumps(registration, indent=2, sort_keys=True))
        return
    print(f"bundle_id: {registration['bundle_id']}")
    print(f"bundle_version: {registration['bundle_version']}")
    print(f"bundle_dir: {registration['bundle_dir']}")
    print(f"manifest_sha256: {registration['manifest_sha256']}")


@hydrology_app.command("inspect")
def hydrology_inspect(
    bundle: Path | None = typer.Argument(None, exists=True, help="Bundle directory or manifest"),
    dataset: Path | None = typer.Option(
        None,
        "--dataset",
        exists=True,
        file_okay=False,
        help="Inspect the hydrology bundle registered in a compiled dataset",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of a summary"
    ),
) -> None:
    """Print the stable pin for a validated FEMIC hydrology bundle."""
    if (bundle is None) == (dataset is None):
        print("[bold red]Provide exactly one of BUNDLE or --dataset.[/]")
        raise typer.Exit(code=1)
    try:
        if dataset is not None:
            loaded = load_registered_femic_hydrology_bundle(dataset)
        else:
            assert bundle is not None
            report = validate_femic_hydrology_bundle(bundle)
            if not report.is_valid:
                typer.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))
                raise typer.Exit(code=1)
            loaded = load_femic_hydrology_bundle(bundle)
        pin = bundle_pin(loaded)
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology inspect failed:[/] {error}")
        raise typer.Exit(code=1) from error
    if json_output:
        typer.echo(json.dumps(pin, indent=2, sort_keys=True))
        return
    print(f"bundle_id: {pin['bundle_id']}")
    print(f"bundle_version: {pin['bundle_version']}")
    print(f"response_surface_id: {pin['response_surface_id']}")
    print(f"domain_id: {pin['domain_id']}")
    print(f"ledger_id: {pin['ledger_id']}")
    print(f"manifest_sha256: {pin['manifest_sha256']}")
    artifacts = pin["artifacts"]
    if isinstance(artifacts, dict):
        for role in sorted(artifacts):
            print(f"artifact: {role}")


@hydrology_app.command("validate")
def hydrology_validate(
    bundle: Path | None = typer.Argument(None, exists=True, help="Bundle directory or manifest"),
    dataset: Path | None = typer.Option(
        None,
        "--dataset",
        exists=True,
        file_okay=False,
        help="Validate the hydrology bundle registered in a compiled dataset",
    ),
    bundle_id: str | None = typer.Option(None, "--bundle-id"),
    bundle_version: str | None = typer.Option(None, "--bundle-version"),
    json_output: bool = typer.Option(
        True, "--json/--no-json", help="Emit deterministic JSON validation report"
    ),
) -> None:
    """Validate a FEMIC hydrology bundle and its artifact checksums."""
    if (bundle is None) == (dataset is None):
        print("[bold red]Provide exactly one of BUNDLE or --dataset.[/]")
        raise typer.Exit(code=1)
    try:
        if dataset is not None:
            if bundle_id is not None or bundle_version is not None:
                raise FemicHydrologyError(
                    "--bundle-id/--bundle-version are only valid with a direct BUNDLE."
                )
            report = validate_registered_femic_hydrology(dataset)
        else:
            assert bundle is not None
            report = validate_femic_hydrology_bundle(
                bundle,
                expected_bundle_id=bundle_id,
                expected_bundle_version=bundle_version,
            )
    except FemicHydrologyError as error:
        print(f"[bold red]Hydrology validation failed:[/] {error}")
        raise typer.Exit(code=1) from error
    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"valid: {report.is_valid}")
        print(f"artifacts: {report.artifact_count}")
        print(f"total_bytes: {report.total_bytes}")
        for message in report.errors:
            print(f"error: {message}")
        for warning in report.warnings:
            print(f"warning: {warning}")
    if not report.is_valid:
        raise typer.Exit(code=1)


app.add_typer(lidar_app, name="lidar")
app.add_typer(hydrology_app, name="hydrology")

if __name__ == "__main__":
    app()
