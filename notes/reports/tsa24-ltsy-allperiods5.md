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
