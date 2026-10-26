# P58.7 carbon targets in the optimizer

Date: 2026-10-25
Phase: P58
Task: P58.6 and P58.7
Related: `notes/design/ws4-carbon.md`, `docs/reference/carbon.rst`

## 1. What was added

- `CarbonLedger` (`ws4/carbon/ledger.py`) runs one block's treatment chain at a time,
  caches its carbon accounts, and sums the blocks for a schedule.
- `Optimizer` accepts `--carbon-package`. The ledger supplies the empty-schedule base and
  every block's chain delta to the incremental objective, so a `carbon.*` target is priced
  by exact CBM output and by per-move deltas.
- The final optimization run writes the carbon accounts into `account_values.csv` and
  `report_accounts.csv`, and records `carbon_ledger.json` beside the run.
- A `carbon.*` target without a package is rejected before the search.

## 2. Ledger exactness

The ledger was compared with a full-schedule `build_sit_tables` + `run_libcbm` run on the
synthetic two-block fixture. Every carbon account cell matched with `max_abs = 0.0`
(within the test's 1e-6 assertion). The empty-schedule base also matched a full empty run
exactly. The ledger cache is keyed by `(block, chain)`.

## 3. Optimizer smoke

Dataset: the WS4 quickstart compiled dataset (two blocks, one track with a clearcut
transition). Package: a two-track CBM package with `Spruce` as the species classifier.
Target:

```yaml
targets:
  - account: carbon.ecosystem.total
    period: 2
    maximum: 200.0
    max_weight: 1.0
```

Run: 10 years, 100 iterations, SA, seed 1, no warm start.

Result:

- Empty-schedule objective: **1003.25**.
- Optimized objective: **887.08**.
- The search chose `CC` on block 1 at offset 0.
- Ecosystem carbon at offset 1 fell from **1203.25 tC** to **1087.08 tC**.
- `account_values.csv` and `report_accounts.csv` contain the `carbon.*` accounts.
- `carbon_ledger.json` records that the block-level ledger priced the run.

The target maximum of 200 tC was not reachable on this two-block toy dataset, so the
smoke demonstrates the mechanism and direction, not a satisfied carbon goal. P58.8 runs
the real TSA24 and MKRF scenarios with a defensible target level.

## 4. Caveats

- The ledger launches a CBM run per `(block, chain)` and caches it. The cache is exact but
  its size grows with the number of distinct chains; a production run needs a cache budget
  or a precomputed single-treatment set.
- The optimizer's per-move delta path includes carbon only when `--carbon-package` is set.
  Without it, a carbon target is rejected rather than silently priced at zero.
- The final carbon ledger is a block-level sum of CBM runs. The final reporting run should
  still be verified with `ws4 carbon` on the incumbent schedule when a formal result is
  published.
