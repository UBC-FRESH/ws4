# P85 close-out: GPU acceleration and interactive target cache

Date: 2026-11-01
Parent issue: #618
Branch: `feature/p85-gpu-acceleration`
Pull request: pending

## Result

The TSA24 GPU population path now launches and runs fast enough to be useful for
iteration, and target edits can re-price the resident population without restarting the
search.

Measured on the local NVIDIA RTX PRO 6000 Blackwell, TSA24, 20,000 generations:

| Metric | Result |
|---|---:|
| Hot launch | **11.9 s** |
| 2k PLAIN search | **17.16 s** |
| 2k PLAIN throughput | **7,463 eval/s** |
| 20k PLAIN search | **152.60 s** |
| 20k PLAIN throughput | **8,388 eval/s** |
| 20k wall | **164.9 s** |
| Throttled live 2k throughput | **6,247 eval/s** |
| Old live path | 755 eval/s |

The old live path repainted every generation. The live path now paints at the configured
refresh interval and target polling is bounded to once per second.

## Tasks

- P85.1 (#619): compact candidate cache, vectorized option map, base-total and parsed-
  schedule sidecars. Complete.
- P85.2 (#620): priority-tier pricing, resident target re-pricing, mtime target reload,
  and live-render throttle. Complete.
- P85.3 (#621): explicit effect-cell basis, persisted `basis_accounts`, missing-cell
  validation, and lazy `EffectTable.extend_cells`. Complete.
- P85.4 (#622): portable runner paths and bundle packer. The WS4-side runner changes are
  in this branch. The TSA24-instance packaging scripts are in the FEMIC instance working
  tree and are not committed in this repository; this task is deferred to that repository
  rather than claimed complete here.

## Verification

```text
pytest tests/test_gpu_ga.py tests/test_gpu_effects.py tests/test_gpu_search.py -q --no-cov
37 passed

ruff check (changed files)
All checks passed

mypy --strict (changed files)
Success: no issues found

python scripts/check_workflow.py
0 error(s), 0 warning(s)
```

Full evidence is in `notes/reports/gpu-acceleration-tsa24.md`, and the cache design is in
`notes/design/gpu-effect-cache-interactivity.md`.

## Known limits

- The existing TSA24 effect table predates the cell-basis builder. It is still target-cell
  coupled until rebuilt with a watchable basis.
- Lazy extension is in memory; extending a table for a new account is not persisted yet.
- The target file and model caches live outside this repository; the cloud bundle document
  lists them but they are not versioned in git.
- Interactive target reload handles price changes and basis-covered cells; a new account
  can trigger a potentially expensive lazy extension.
- This is an acceleration/benchmark result, not a claim about every landscape instance.

## Closeout

The phase pull request is queued for maintainer approval. Do not merge, tag, release, or
change settings without approval.
