# P136.1–P136.2 exact solution-space payload and 3D explorer

Date: 2026-11-05
Status: active; PR #829
Branch: `feature/p136-pareto-explorer`
Parent issue: #827
Task issue: #828

## Summary

The existing target-weight portfolio already writes one optimizer run per weight vector
and seed. This change turns those runs into an exact, inspectable solution-space payload
and adds a dedicated 3D workspace over it.

The important correction is that the explorer does **not** use the capacity-limited
schedule archive as its candidate set. It rebuilds the nondominated front from every
successful member, so a member that was trimmed from the archive is still available as a
trade-off in the response surface.

## Files

- `ws4/opt/solution_space.py` — exact full-member front, normalization, objective
  dimension, near-front distance.
- `ws4/opt/portfolio.py` — the report's `front` is now computed from every successful
  member rather than the bounded archive.
- `ws4/web/app.py` — `GET /api/search/{name}/space?near_front=...`, with artifact-relative
  path sanitization.
- `ws4/web/static/app.js` — Pareto workspace, orbit controls, dimension mappings,
  dominance/filter controls, selection, pin/compare, schedule link.
- `ws4/web/static/index.html`, `ws4/web/static/style.css` — workspace and controls.
- `ws4/web/static/vendor/three/` — vendored Three.js and OrbitControls (MIT).
- `tests/test_solution_space.py`, `tests/test_portfolio.py`,
  `tests/test_web.py`, `tests/test_pareto_browser.py`.

## Data contract

The payload contains:

- `dimensions`: the declared outcome metrics plus the scalar objective.
- `directions`: `min` or `max` per dimension.
- `ideal` / `nadir`: raw best and worst values in the sample.
- `points`: every successful member with raw metrics, normalized coordinates, factors,
  objective, front/near-front flags, distance to front, and safe schedule path.
- `front` / `near_front`: exact and labelled near-front keys.
- `front_size`, `near_front_size`, `near_front_epsilon`, `failed`.

A metric is normalized to `0 = worst`, `1 = best`. The exact front uses outcome metrics
only; the scalar objective is an optional dimension and is always minimized. Near-front
members are retained for sample density but are never labelled Pareto.

## Verification

Focused tests:

```bash
python -m pytest tests/test_solution_space.py tests/test_portfolio.py \
  tests/test_web.py::test_search_solution_space_recomputes_and_sanitizes \
  tests/test_pareto_browser.py -q --no-cov
```

Result: 19 passed (the browser test launches a real uvicorn app and Chromium).

Local browser smoke against a 12-member artifact:

```text
12 members · 10 exact front · 0 failed
front mode: 10 visible
filter volume >= 0.50: 5 visible
3D canvas visible after viewport resize
```

The browser test asserts the workspace, canvas, artifact load, exact-front mode, filter,
axis/colour/size/opacity controls, and no page errors.

## Limits

- A finite weight grid and a stochastic search define the sample; the surface is advisory.
- Normalization is relative to the sample.
- Near-front is a display label.
- P136.3 (bounded parallel weight scans and a guided 5-7 dimension scan builder) remains
  queued.
