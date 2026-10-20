# P16.1: the bridge ranking does not survive a matched footprint

Status: the fire ranking reproduced at the fire model's own treatment area does **not** reproduce when
both sides treat the area WS4 can actually treat. The arrangement effect is inside seed noise at that
footprint.

## What was run

`scripts/landscape_spread.py` (the instance's own fire model) was reused unmodified: its
`_block_fuel_types`, `_adjacency` and `simulate` functions, 50 ignitions, 480 minutes, wind 225°,
**ROS × 0.3** (the setting that produced `bridge_{pattern}.json`; the script's 0.6 default was not used
for the published runs). Only the treated-block mask and the seed changed. The harness reproduced the
published barrier run **exactly** with the original mask and seed 1 — mean `19640.448328143004`, p90
`37637.13355349601` — which fixes the settings.

Masks: the blocks where `product.Treated.managed.FT > 0.5` after applying
`bridge_{pattern}_sched.csv` at period 0, with the dataset's duplicate product rows dropped (the 4×
defect, P16.2). Barrier 3,483 blocks / 54,368 ha; clumped 3,557 / 55,837; random 3,366 / 53,697 — about
**5.5% of the 988,816 ha** the fire model holds, against 17.9% for the published patterns.

## Mean area burned (ha), five seeds

| pattern | 1 | 2 | 3 | 4 | 5 | mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| barrier | 24,247.3 | 22,963.0 | 22,507.6 | 23,773.8 | 20,815.3 | 22,861.4 |
| clumped | 24,283.4 | 23,025.8 | 22,212.1 | 23,241.5 | 21,114.2 | 22,775.4 |
| random | 24,312.5 | 23,037.5 | 22,479.4 | 23,244.1 | 21,007.2 | 22,816.2 |

Rankings by seed (best first):

| seed | ranking |
| ---: | --- |
| 1 | barrier, clumped, random |
| 2 | barrier, clumped, random |
| 3 | **clumped, random, barrier** |
| 4 | **clumped, random, barrier** |
| 5 | barrier, random, clumped |

Over the seeds the mean ranks **clumped < random < barrier** — the *reverse* of the published order. The
largest mean difference is **86 ha, 0.38%**, while the seed-to-seed range within a single pattern is
about **3,400 ha, 15%**. The p90 orders the same way round and is equally small: barrier 40,043, clumped
39,967, random 39,558 ha.

## What it means

The published bridge result (barrier 19,640 < clumped 19,870 < random 20,298 ha, a 3% spread) was
measured with 177,088 ha treated — 17.9% of the model. At the **5.5%** WS4's FT treatment can actually
reach, the arrangement effect is smaller than the noise between seeds and does not order the patterns.

Two consequences, both stated rather than buried:

1. **The compartment account is not validated as a fire-response proxy.** P15's claim that the largest
   compartment "reproduces the fire ranking" compared a compartment computed on the WS4-treated set with
   a fire outcome produced by a 3.3× larger treatment. That comparison is withdrawn. The account remains
   a well-defined, auditable fragmentation metric; it has no demonstrated relationship to this fire
   model at the intervention WS4 can represent.
2. **The bridge finding is conditional on treatment area.** Arrangement matters at 20% treatment and is
   inside noise at 5.5%. That is consistent with the paper's own E2b diagnostic — even a near-hard stop
   moves the mean only ~4% — and it is the honest scope of the claim.

The account itself still does what it says: it measures the fragmentation of the fast-edge fuel body,
it is periodic, and it is targetable. What is withdrawn is the *validation*, not the computation.

## The account values on the corrected masks

For completeness, the compartment on the same deduplicated masks (bearing 225°, tolerance 60°):

| pattern | treated (ha) | largest compartment (ha) | area-weighted mean (ha) |
| --- | ---: | ---: | ---: |
| barrier | 54,368 | 82,874.4 | 25,696.8 |
| clumped | 55,837 | 105,020.4 | 32,250.4 |
| random | 53,697 | 196,766.6 | 50,280.8 |

The account still orders the patterns (barrier < clumped < random) with a large separation. The fire
model, at the same footprint, does not. A metric can be a clean description of the landscape and still
not predict this process; that is the finding.

## Files

- `/tmp/opencode/ft/matched_run_dedup.py` and `matched_dedup.log` (untracked, local);
- per-run JSON and `matched_summary.csv` in `/tmp/opencode/ft/matched_dedup/`;
- the thesis-side reproduction is **confirmed**: the independent rerun in
  `UBC-FRESH/femic-tsa23-instance` #11 reproduced all fifteen values to four decimals, including the
  p90 means, from a different runner and process.
