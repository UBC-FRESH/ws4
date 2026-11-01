"""Public WS4 instance portal.

A single FastAPI process mounts one WS4 web application per public FEMIC instance.
Each mounted app keeps its dataset and run directory; the portal only discovers
instances and renders the landing page. Searches use the resident-state engine
(``ws4 state-watch``) on one CPU core, and the chat agent is enabled.
"""

from __future__ import annotations

import html
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ws4.web.app import create_app

ROOT = Path(__file__).resolve().parent
INSTANCES_ROOT = Path(
    os.environ.get("WS4_INSTANCES_ROOT", "/srv/shared-data/gep/ws4/femic/external")
)
RUNS_ROOT = ROOT / "runs"
CACHE_ROOT = ROOT / "cache"
RUNS_ROOT.mkdir(parents=True, exist_ok=True)
CACHE_ROOT.mkdir(parents=True, exist_ok=True)

# Curated defaults for instances that have a compiled dataset and a complete
# public state-search setup. Paths are relative to the instance directory.
SPECS: dict[str, dict[str, Any]] = {
    "femic-tsa24-instance": {
        "label": "TSA 24",
        "subtitle": "North Island TSA 24 · even-flow",
        "dataset": "build/compiled",
        "targets": "config/ws4/targets/evenflow_tsa24.yaml",
        "initial": "runtime/seed_area_control_tsa24.csv",
        "candidate_cache": "runtime/gpu-cache/candidates.pkl",
        "crs": "EPSG:3005",
    },
    "femic-tsa27-instance": {
        "label": "TSA 27",
        "subtitle": "North Island TSA 27 · even-flow",
        "dataset": "build/compiled_uwr_fixed_20261031",
        "targets": "config/ws4/targets/evenflow_no_caribou.yaml",
        "initial": "runtime/seed_oldest_first_s7.csv",
        "geometry": "data/ws4/blocks.geojson",
        "land_base": "data/ws4/land_base.geojson",
        "crs": "EPSG:3005",
    },
    "femic-tsa29-instance": {
        "label": "TSA 29",
        "subtitle": "North Island TSA 29 · even-flow",
        "dataset": "build/compiled",
        "targets": "config/ws4/targets/evenflow_tsa29.yaml",
        "initial": "runtime/seed_oldest_first_tsa29.csv",
        "candidate_cache": "runtime/gpu-cache/candidates.pkl",
        "crs": "EPSG:3005",
    },
    "femic-northisland-instance": {
        "label": "North Island",
        "subtitle": "North Island model · targets",
        "dataset": "runtime/matrix",
        "targets": "config/targets.yaml",
        "initial": "runtime/baseline/schedule.csv",
        "geometry": "runtime/fragments.geojson",
        "land_base": "runtime/land_base.geojson",
        "crs": "EPSG:3005",
    },
    "femic-mkrf-instance": {
        "label": "MKRF",
        "subtitle": "Malcolm Knapp Research Forest",
        "dataset": "ws4/runtime/matrix",
        "targets": "ws4/targets.yaml",
        "initial": None,
        "geometry": "ws4/runtime/fragments.geojson",
        "topology": "ws4/topology.csv",
        "crs": "EPSG:3005",
    },
    "femic-tsa48-instance": {
        "label": "TSA 48",
        "subtitle": "North Island TSA 48 · half-AAC even-flow",
        "dataset": "runtime/tsa48_full_calibrated/matrix",
        "targets": "config/targets.tsa48_full_half_aac.yaml",
        "initial": "runtime/tsa48_full_calibrated/schedules/half_aac_evenflow_seed.csv",
        "geometry": "runtime/tsa48_full_calibrated/fragments.geojson",
        "land_base": "runtime/tsa48_full_calibrated/land_base.geojson",
        "topology": "runtime/tsa48_full_calibrated/topology.csv",
        "crs": "EPSG:3005",
    },
    "femic-gnn-instance": {
        "label": "GNN",
        "subtitle": "GNN feasibility / risk model",
        "dataset": "runtime/gnn/matrix",
        "targets": "runtime/gnn/targets_evenflow_half_aac.yaml",
        "initial": "runtime/gnn/baseline_schedule.csv",
        "geometry": "runtime/gnn/fragments.geojson",
        "land_base": "runtime/gnn/land_base.geojson",
        "crs": "EPSG:3005",
    },
}

LABEL_OVERRIDES = {
    "femic-afrf-gavinlake-instance": ("Gavin Lake", "AFRF Gavin Lake"),
    "femic-afrf-knifecreek-instance": ("Knife Creek", "AFRF Knife Creek"),
    "femic-k3z-instance": ("K3Z", "K3Z model"),
    "femic-tfl6-instance": ("TFL 6", "Tree Farm Licence 6"),
    "femic-tsa08-instance": ("TSA 08", "North Island TSA 08"),
    "femic-tsa16-instance": ("TSA 16", "North Island TSA 16"),
    "femic-tsa29mini-instance": ("TSA 29 mini", "Small TSA 29 fixture"),
    "femic-tsa40-instance": ("TSA 40", "North Island TSA 40"),
    "femic-tsa41-instance": ("TSA 41", "North Island TSA 41"),
    "femic-tsa46-instance": ("TSA 46", "North Island TSA 46"),
    "femic-tsa47-instance": ("TSA 47", "North Island TSA 47"),
    "femic-tsa48-instance": ("TSA 48", "North Island TSA 48"),
}

app = FastAPI(title="WS4 Public Demo Portal")

_RATE_WINDOW_S = 60.0
_RATE_MAX_REQUESTS = 300
_MAX_BODY_BYTES = 64 * 1024
_request_log: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def public_guardrails(request: Request, call_next: Any) -> Any:
    """Keep the public instance portal bounded and uncached."""
    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse({"detail": "request body exceeds 64 KiB"}, status_code=413)
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _request_log[key]
    while bucket and now - bucket[0] > _RATE_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX_REQUESTS:
        return JSONResponse(
            {"detail": "public demo rate limit reached; try again in a minute."},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    bucket.append(now)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-WS4-Public-Demo"] = "experimental"
    return response


@dataclass
class Instance:
    slug: str
    label: str
    subtitle: str
    root: Path
    ready: bool
    reason: str = ""
    mount: str = ""
    spec: dict[str, Any] | None = None


def _existing(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = root / value
    return candidate if candidate.is_file() or candidate.is_dir() else None


def _resolve(slug: str, root: Path) -> Instance:
    spec = dict(SPECS.get(slug, {}))
    label, subtitle = LABEL_OVERRIDES.get(slug, (slug.removeprefix("femic-").removesuffix("-instance"), ""))
    label = str(spec.get("label", label))
    subtitle = str(spec.get("subtitle", subtitle))
    if not root.is_dir():
        return Instance(slug, label, subtitle, root, False, "instance directory missing")
    dataset = _existing(root, spec.get("dataset"))
    targets = _existing(root, spec.get("targets"))
    initial = _existing(root, spec.get("initial"))
    if dataset is None:
        # A common fallback for instances with a compiled build.
        for candidate in (root / "build" / "compiled", root / "ws4" / "runtime" / "matrix", root / "runtime" / "matrix"):
            if (candidate / "manifest.json").is_file() and (candidate / "fragments.parquet").is_file():
                dataset = candidate
                break
    if targets is None:
        for candidate in sorted(root.glob("config/**/targets*.yaml")) + sorted(root.glob("ws4/targets*.yaml")):
            if candidate.is_file():
                targets = candidate
                break
    if initial is None:
        for candidate in sorted(root.glob("runtime/seed*.csv")) + sorted(root.glob("ws4/runtime/*/schedule.csv")):
            if candidate.is_file():
                initial = candidate
                break
    if dataset is None:
        return Instance(slug, label, subtitle, root, False, "no compiled WS4 dataset")
    if not (dataset / "fragments.parquet").is_file():
        return Instance(slug, label, subtitle, root, False, "dataset is missing fragments.parquet")
    try:
        import pyarrow.parquet as pq

        partitions = pq.ParquetFile(dataset / "fragments.parquet").metadata.num_row_groups
        rows = pq.ParquetFile(dataset / "fragments.parquet").metadata.num_rows
        # The shared demo is one CPU core; keep the giant TSA instances off it.
        if rows > 200_000:
            return Instance(
                slug,
                label,
                subtitle,
                root,
                False,
                f"large instance ({rows:,} fragments); not enabled for the shared one-core demo",
            )
    except Exception:
        pass
    if targets is None:
        return Instance(slug, label, subtitle, root, False, "no targets YAML")
    # A state run can build its candidate index and seed-state cache on first use;
    # an existing candidate cache only avoids that one-time cost.
    spec.update({"dataset": str(dataset), "targets": str(targets), "initial": str(initial) if initial else None})
    return Instance(slug, label, subtitle, root, True, spec=spec)


def _build_mount(instance: Instance, mount_path: str) -> None:
    spec = instance.spec or {}
    root = instance.root
    slug = instance.slug
    runs = RUNS_ROOT / slug
    runs.mkdir(parents=True, exist_ok=True)
    cache = CACHE_ROOT / slug
    cache.mkdir(parents=True, exist_ok=True)

    candidate_cache = _existing(root, spec.get("candidate_cache"))
    candidate_index = cache / "candidates.npz"
    if candidate_cache is None and candidate_index.is_file():
        candidate_cache = None
    seed_state = cache / "seed-state.npz"
    state_config: dict[str, Any] = {
        "candidate_index": str(candidate_index),
        "candidate_cache": str(candidate_cache) if candidate_cache else None,
        "seed_state": str(seed_state),
        "initial_schedule": spec.get("initial"),
        "period_width": 10,
        "years": 200,
        "default_iterations": 1_000_000_000,
        "max_seconds": 60,
        "lns_weight": 0.2,
        "lns_destroy": 0.1,
        "lns_max_destroy": 64,
    }
    options: dict[str, Any] = {
        "dataset": root / spec["dataset"],
        "runs": runs,
        "targets": root / spec["targets"],
        "allow_runs": True,
        "allow_agent": True,
        "agent_cwd": root,
        "initial_schedule": root / spec["initial"] if spec.get("initial") else None,
        "state_config": state_config,
        "crs": spec.get("crs", "EPSG:3005"),
    }
    for key, value in (
        ("geometry", spec.get("geometry")),
        ("land_base", spec.get("land_base")),
        ("topology", spec.get("topology")),
    ):
        if value and (root / value).is_file():
            options[key] = root / value
    app.mount(mount_path, create_app(**options))


INSTANCES: list[Instance] = []
for directory in sorted(INSTANCES_ROOT.glob("femic-*-instance")):
    if not directory.is_dir():
        continue
    instance = _resolve(directory.name, directory)
    if instance.ready:
        instance.mount = f"/instance/{instance.slug}/"
        try:
            _build_mount(instance, instance.mount.rstrip("/"))
        except Exception as error:  # noqa: BLE001 - report a broken instance on the card
            instance.ready = False
            instance.reason = f"could not start WS4 UI: {error}"
    INSTANCES.append(instance)


def _landing() -> str:
    cards = []
    for instance in INSTANCES:
        if instance.ready:
            action = f'<a class="door" href="{html.escape(instance.mount)}">'
            footer = "Launch instance →"
            status = "READY"
        else:
            action = '<div class="door disabled">'
            footer = "Not currently runnable"
            status = "SETUP NEEDED"
        reason = f"<p class=\"reason\">{html.escape(instance.reason)}</p>" if instance.reason else ""
        cards.append(
            f'''{action}
              <div class="card-top"><span class="kicker">{html.escape(instance.slug)}</span><span class="badge">{status}</span></div>
              <h2>{html.escape(instance.label)}</h2>
              <p>{html.escape(instance.subtitle or "Public FEMIC instance")}</p>
              {reason}
              <div class="arrow">{footer}</div>
            </{'a' if instance.ready else 'div'}>'''
        )
    ready = sum(1 for instance in INSTANCES if instance.ready)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>WS4 Public Instance Portal</title>
<style>
  :root {{ color-scheme: light; font-family: system-ui, sans-serif; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: radial-gradient(circle at top left, #dcecdf, #f3f6f1 55%, #e7eee8); color: #17201b; }}
  main {{ width: min(1180px, calc(100vw - 36px)); padding: 40px 0; }}
  .kicker {{ color: #1f6b43; text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 700; }}
  h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.4rem); letter-spacing: -.04em; }}
  p.lead {{ max-width: 780px; margin: 0 0 30px; color: #4c5c52; font-size: 1.05rem; line-height: 1.55; }}
  .doors {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
  a.door, .door {{ display: block; min-height: 176px; padding: 20px; border-radius: 16px; text-decoration: none; color: inherit; background: #fff; box-shadow: 0 12px 36px #173d2a1c; border: 1px solid #c9d8ce; transition: transform .15s ease, box-shadow .15s ease; }}
  a.door:hover {{ transform: translateY(-3px); box-shadow: 0 16px 44px #173d2a28; }}
  .door.disabled {{ opacity: .72; background: #f7faf7; box-shadow: none; }}
  .card-top {{ display: flex; align-items: center; gap: 10px; justify-content: space-between; }}
  .badge {{ font: 700 10px system-ui; letter-spacing: .08em; border-radius: 999px; padding: 4px 8px; color: #1f6b43; background: #e6f3e8; border: 1px solid #b9dec0; }}
  .disabled .badge {{ color: #80631b; background: #fff7df; border-color: #ead9a5; }}
  h2 {{ margin: 12px 0 6px; font-size: 1.25rem; }}
  .door p {{ margin: 0; color: #52645a; line-height: 1.45; }}
  .reason {{ margin-top: 8px !important; font-size: .82rem; color: #80631b !important; }}
  .arrow {{ margin-top: 18px; color: #1f6b43; font-weight: 700; }}
  .disabled .arrow {{ color: #7d8a81; }}
  footer {{ margin-top: 22px; color: #63736a; font-size: .8rem; }}
  @media (max-width: 980px) {{ .doors {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  @media (max-width: 640px) {{ .doors {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<main>
  <div class="kicker">WS4 · public experimental demo · no login · state engine · agent enabled</div>
  <h1>Open a forest model.</h1>
  <p class="lead">Launch any public FEMIC instance in the WS4 web UI. Searches use the resident-state accelerated engine on one CPU core. Choose a model below to edit targets, run a schedule, inspect the map, reports, and the embedded assistant.</p>
  <div class="doors">{''.join(cards)}</div>
  <footer>WS4 public demo · {ready} runnable instance{'s' if ready != 1 else ''} · resident-state search · one CPU core · embedded agent enabled</footer>
</main>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    return HTMLResponse(_landing(), headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "instances": len(INSTANCES),
        "runnable": sum(1 for instance in INSTANCES if instance.ready),
        "engine": "state-watch",
        "islands": 1,
        "agent": True,
    }
