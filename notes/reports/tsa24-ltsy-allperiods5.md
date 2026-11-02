# TSA24 all-period ±5% even flow with a final stock floor

Date: 2026-11-02
Status: scenario formulation and 5,000-generation probe accepted; 20,000-generation confirmation not planned

This is a candidate LTSY scenario. It combines an all-period ±5% even-flow band with a
final managed-growing-stock floor at 90% of the initial stock.

## Formulation

- Flow: `product.HarvestedVolume.managed.Total.CC`, periods 1–20, reference period 1,
  ±5%, weight 10,000, non-linear.
- Level aspirations: `product.HarvestedVolume.managed.Total.CC`, periods 11–20,
  minimum 100,000,000 m³ per period, weight 100, normalized.
- Stock floor: `feature.Yield.managed.Total`, period 20, minimum
  **370,403,185.80 m³**, weight 10, normalized.
- Initial managed stock: **411,559,095.33 m³** at offset 0.
- The stock floor is a soft aspiration, not a hard constraint.

Exact target file, runner scripts, and output schedule:

[`archive/tsa24-ltsy-allperiods5-20261102/`](../../../archive/tsa24-ltsy-allperiods5-20261102/)

## 5,000-generation probe

```text
evaluations: 320,064
search loop: 216.0 s
wall:        234.17 s including hot-cache start
objective:   2,751.96
penalty:     459,472,816.01
```

Harvest, m³ per 10-year period:

```text
51.5M  48.8M  48.7M  48.9M  49.0M
48.9M  49.4M  49.6M  53.9M  53.8M
54.0M  54.0M  54.0M  54.0M  54.1M
54.2M  54.0M  53.9M  54.1M  54.1M
```

Relative to the 51.5M period-1 reference, the ±5% band is roughly 48.9–54.1M. The
profile is nearly flat; periods 3 and 16 are just outside.

Managed growing stock at period 20: **477M m³**, above the **370M m³** floor.

The periods 11–20 harvest level is about **54M m³ per period**, well below the 100M level
aspiration. The remaining objective is dominated by that level shortfall, not flow
instability.

## Reproducibility and decision

The rerun produced the same 5,000-generation schedule bit-for-bit:

```text
SHA-256 44bdba7a6cf95a056410ccda4ab86ed74d144fd5c72e63e9430323060440eb1b
```

A 20,000-generation confirmation is not planned. The 5,000-generation probe is accepted
as evidence that the all-period ±5% flow band and the 90% stock floor can coexist. The
next review should be age-class, ending-inventory, and policy-focused, not another run of
the same search.

## Post-run replay

The accepted schedule was replayed through the simulator (82.54 s, 13.4 GB peak RSS):

| State at offset 199 | Value |
|---|---:|
| Managed growing stock | **477,487,194.22 m3** |
| Unmanaged growing stock | 521,061,508.61 m3 |
| Total growing stock | 998,548,702.83 m3 |
| Final age classes represented | 64 |
| Age-class evenness | 0.920 |

Age-class shares, initial -> final:

| Class | Initial | Final |
|---|---:|---:|
| <40 years | 22.4% | **12.5%** |
| 40-199 years | 62.6% | **39.0%** |
| >=200 years | 15.0% | **48.4%** |

The stock floor is met, but the margin comes from a large shift toward old forest. The
oldest classes rise from 15% to 48% of the area while young area halves. That is an
important policy caveat: the scenario is not automatically desirable just because the
stock floor is satisfied.

Replay artifacts are under `postrun/`: `account_values.csv`, `product_values.csv`,
`ending_inventory` rows in `account_values.csv`, `age_class_initial.csv`,
`age_class_final.csv`, and `postrun_summary.json`.

## Managed/unmanaged age-class split

The aggregate old-area number is misleading. Splitting by IFM status:

| IFM | State | Area | <40 | 40-199 | >=200 |
|---|---|---:|---:|---:|---:|
| managed | initial | 3.060M ha | 32.8% | 60.0% | 7.2% |
| managed | final | 3.060M ha | **24.2%** | **75.2%** | **0.6%** |
| unmanaged | initial | 2.839M ha | 11.2% | 65.4% | 23.4% |
| unmanaged | final | 2.839M ha | **0.0%** | **0.0%** | **100.0%** |

The aggregate final >=200 share of 48.4% is almost entirely the unmanaged estate aging
for 200 years. Managed old forest falls from 7.2% to 0.6% of managed area, while managed
mature forest rises to 75.2%. The stock floor is therefore met, but this scenario does
**not** protect managed old-seral structure.

Policy questions for the next review:

- Does LTSY require a managed old-seral or retention area target beyond the total stock
  floor?
- Is the unmanaged 100% >=200 result expected, or should some unmanaged area be active?
- Is the stock target correctly scoped to managed stock, or should it be managed plus
  unmanaged?

The detailed split is in `postrun/age_class_by_ifm.csv`; initial and final fragment
snapshots are `postrun/fragments_initial.parquet` and `postrun/fragments_final.parquet`.

## Interpretation

This is a good LTSY formulation candidate because:

- all-period ±5% flow is nearly attainable;
- the stock floor is satisfied with a wide margin;
- the high level aspiration exposes the actual harvest ceiling instead of being hidden
  by a late-start flow transition.

It is not a production result. The probe is short, uses one seed, and still needs
age-class, ending-inventory, and policy review.

## Run

```bash
cd /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance

PLAIN=1 \
  TARGETS=config/ws4/targets/evenflow_tsa24_allperiods5_stock90.yaml \
  SCHEDULE_OUT=runtime/tsa24-allperiods5-stock90-5000.csv \
  ./run_ltsy_watch.sh 5000
```
