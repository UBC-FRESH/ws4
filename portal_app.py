"""Public WS4 instance portal.

A single FastAPI process mounts one WS4 web application per public FEMIC instance.
Each mounted app keeps its dataset and run directory; the portal only discovers
instances and renders the landing page. Searches use the resident-state engine
(``ws4 state-watch``) on one CPU core, and the chat agent is enabled.
"""

from __future__ import annotations

import html
import os
import shutil
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
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
        "targets": "config/ws4/targets/evenflow_tsa24_allperiods5_stock90.yaml",
        "scenario_profiles": "config/ws4/profiles/ltsy.yaml",
        "initial": "runtime/seed_area_control_tsa24.csv",
        "candidate_cache": "runtime/gpu-cache/candidates.pkl",
        "geometry": "runtime/geometry/tsa24-blocks.geojson",
        "geometry_overview": "runtime/geometry/tsa24-blocks-overview.geojson",
        "crs": "EPSG:3005",
    },
    "femic-tsa27-instance": {
        "label": "TSA 27",
        "subtitle": "North Island TSA 27 · even-flow",
        "dataset": "build/compiled",
        "targets": "config/ws4/targets/evenflow_no_caribou.yaml",
        "scenario_profiles": "config/ws4/profiles/gpu.yaml",
        "initial": "runtime/seed_oldest_first_s8.csv",
        "candidate_cache": "runtime/gpu-cache/s8/candidates.pkl",
        "geometry": "data/ws4/blocks.geojson",
        "land_base": "data/ws4/land_base.geojson",
        "crs": "EPSG:3005",
    },
    "femic-tsa29-instance": {
        "label": "TSA 29",
        "subtitle": "North Island TSA 29 · even-flow",
        "dataset": "build/compiled",
        "targets": "config/ws4/targets/evenflow_tsa29.yaml",
        "scenario_profiles": "config/ws4/profiles/gpu.yaml",
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
        "targets": "config/targets.gnn.yaml",
        "initial": "runtime/gnn/runs/opening_first_block_gate/schedule.csv",
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
    gpu: dict[str, Any] = field(default_factory=dict)


def _existing(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = root / value
    return candidate if candidate.is_file() or candidate.is_dir() else None


def _gpu_readiness(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Classify an instance's GPU artifacts without starting a GPU run.

    ``profile`` means the portal can launch a profile-aware GPU worker. ``cli``
    means effect tables exist, but no profile library is wired into the portal.
    ``cpu`` means the public state engine is the only available search path.
    """
    effects_dir = root / "runtime" / "gpu-effects"
    effects = sorted(
        path.name
        for path in effects_dir.glob("*.pt")
        if path.is_file() and not path.name.endswith(".base.pt")
    )
    factorized_dir = root / "runtime" / "factorized"
    factorized = sorted(path.name for path in factorized_dir.glob("*") if path.is_file())

    profiles: list[str] = []
    profile_ready = False
    profile_path = _existing(root, spec.get("scenario_profiles"))
    if profile_path is not None and profile_path.is_file():
        try:
            from ws4.opt.scenario_profiles import load_profiles

            library = load_profiles(profile_path)
            profiles = sorted(library)
            profile_ready = any(
                all(getattr(profile, name, None) for name in ("table", "cache_dir"))
                for profile in library.values()
            )
        except Exception:
            profile_ready = False

    if profile_ready:
        mode = "profile"
    elif effects:
        mode = "cli"
    else:
        mode = "cpu"
    return {
        "mode": mode,
        "profiles": profiles,
        "effect_tables": effects,
        "factorized": factorized,
    }


def _gpu_label(gpu: dict[str, Any]) -> tuple[str, str]:
    """Return a short human label and detail for a GPU-readiness record."""
    mode = str(gpu.get("mode", "cpu"))
    if mode == "profile":
        names = ", ".join(str(name) for name in gpu.get("profiles", []))
        return "GPU profile", names or "profile library"
    if mode == "cli":
        count = len(gpu.get("effect_tables", []))
        return "GPU artifacts · CLI", f"{count} effect table{'s' if count != 1 else ''}"
    return "CPU state-watch", "resident state engine"


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
    # Every public instance is launchable by default. The shared demo runs on one
    # CPU core, so a size cap can still be enforced by setting WS4_MAX_FRAGMENTS
    # (0 or unset means no limit).
    max_fragments = int(os.environ.get("WS4_MAX_FRAGMENTS", "0") or 0)
    if max_fragments:
        try:
            import pyarrow.parquet as pq

            rows = pq.ParquetFile(dataset / "fragments.parquet").metadata.num_rows
            if rows > max_fragments:
                return Instance(
                    slug,
                    label,
                    subtitle,
                    root,
                    False,
                    f"large instance ({rows:,} fragments); excluded by WS4_MAX_FRAGMENTS",
                )
        except Exception:
            pass
    if targets is None:
        return Instance(slug, label, subtitle, root, False, "no targets YAML")
    # A state run can build its candidate index and seed-state cache on first use;
    # an existing candidate cache only avoids that one-time cost.
    spec.update({"dataset": str(dataset), "targets": str(targets), "initial": str(initial) if initial else None})
    gpu = _gpu_readiness(root, spec)
    spec["gpu"] = gpu
    return Instance(slug, label, subtitle, root, True, spec=spec, gpu=gpu)


def _writable_copy(source: Path, destination: Path) -> Path:
    """Return a writable copy of a read-only instance file.

    The shared instance tree is mounted read-only for this service, so the web
    editor cannot write beside the original YAML or schedule. Keep a per-instance
    copy under the portal cache and let writes land there.

    Parameters
    ----------
    source : pathlib.Path
        Original file in the instance directory.
    destination : pathlib.Path
        Cached copy to create on first use.

    Returns
    -------
    pathlib.Path
        The cached copy, or the original when the copy cannot be made.
    """
    if not destination.is_file():
        try:
            shutil.copyfile(source, destination)
        except OSError:
            return source
    return destination


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
    targets = _writable_copy(root / str(spec["targets"]), cache / "targets.yaml")
    initial = (
        _writable_copy(root / str(spec["initial"]), cache / "initial-schedule.csv")
        if spec.get("initial")
        else None
    )
    state_config: dict[str, Any] = {
        "candidate_index": str(candidate_index),
        "candidate_cache": str(candidate_cache) if candidate_cache else None,
        "seed_state": str(seed_state),
        "initial_schedule": str(initial) if initial else None,
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
        "targets": targets,
        "allow_runs": True,
        "allow_agent": True,
        "agent_cwd": root,
        "initial_schedule": initial,
        "state_config": state_config,
        "tile_cache_dir": cache / "tiles",
        "crs": spec.get("crs", "EPSG:3005"),
    }
    for key, value in (
        ("scenario_profiles", spec.get("scenario_profiles")),
        ("geometry", spec.get("geometry")),
        ("geometry_overview", spec.get("geometry_overview")),
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
        if instance.ready:
            gpu_label, gpu_detail = _gpu_label(instance.gpu)
            gpu_class = f"gpu-{instance.gpu.get('mode', 'cpu')}"
        else:
            gpu_label, gpu_detail = "GPU unavailable", "no runnable dataset"
            gpu_class = "gpu-unavailable"
        gpu_line = (
            f'<p class="gpu {gpu_class}"><span class="gpu-dot"></span>'
            f"<strong>{html.escape(gpu_label)}</strong> · {html.escape(gpu_detail)}</p>"
        )
        reason = f"<p class=\"reason\">{html.escape(instance.reason)}</p>" if instance.reason else ""
        cards.append(
            f'''{action}
              <div class="card-top"><span class="kicker">{html.escape(instance.slug)}</span><span class="badge">{status}</span></div>
              <h2>{html.escape(instance.label)}</h2>
              <p>{html.escape(instance.subtitle or "Public FEMIC instance")}</p>
              {gpu_line}
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
  .gpu {{ margin-top: 10px !important; font-size: .76rem; color: #52645a !important; }}
  .gpu strong {{ color: #1f6b43; }}
  .gpu-dot {{ display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: #829087; vertical-align: middle; }}
  .gpu-profile .gpu-dot {{ background: #1f6b43; }}
  .gpu-cli .gpu-dot {{ background: #b07b16; }}
  .gpu-unavailable .gpu-dot {{ background: #a48f6b; }}
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
  <p class="lead">Launch any public FEMIC instance in the WS4 web UI. Normal searches use the resident-state engine on one CPU core; the card badges show which instances have additional GPU profile runs or CLI-only GPU artifacts. Choose a model below to edit targets, run a schedule, inspect the map, reports, and the embedded assistant.</p>
  <div class="doors">{''.join(cards)}</div>
  <footer>WS4 public demo · {ready} runnable instance{'s' if ready != 1 else ''} · resident-state search · GPU readiness shown per instance · embedded agent enabled</footer>
</main>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    return HTMLResponse(_landing(), headers={"Cache-Control": "no-store"})


@app.get("/api/instances")
def instance_readiness() -> list[dict[str, Any]]:
    """Return launch status and GPU readiness for every discovered instance."""
    return [
        {
            "slug": instance.slug,
            "label": instance.label,
            "ready": instance.ready,
            "mount": instance.mount or None,
            "reason": instance.reason or None,
            "gpu": instance.gpu or {"mode": "unavailable"},
        }
        for instance in INSTANCES
    ]


@app.get("/health")
def health() -> dict[str, Any]:
    modes: dict[str, int] = defaultdict(int)
    for instance in INSTANCES:
        modes[str(instance.gpu.get("mode", "unavailable"))] += 1
    return {
        "status": "ok",
        "instances": len(INSTANCES),
        "runnable": sum(1 for instance in INSTANCES if instance.ready),
        "engine": "state-watch",
        "gpu": {
            "profile": modes["profile"],
            "cli": modes["cli"],
            "cpu": modes["cpu"],
            "unavailable": modes["unavailable"],
        },
        "islands": 1,
        "agent": True,
    }
