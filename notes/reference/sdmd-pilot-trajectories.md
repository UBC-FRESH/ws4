# Pilot SDMD trajectories from FVS-BC

The four pilot trajectory files in `ws4/sdmd/data/trajectories/` are **method runs**,
not real AU projections.

## What was run

- Model: `fresh-fvsbc` 0.1.0, FVS BC variant.
- Input: the synthetic tree lists in `tests/fixtures/sdmd/trees.csv` for `PLOT-A01`
  and `PLOT-B01`, replicated to the stand TPH in `stands.csv` and split into plots of
  at most 999 trees.
- Site: `SITECODE FD,60` for the FDI AU and `PL,50` for the PLI AU.
- Horizon: 8 cycles of 10 years.
- No-cut and CT60: a `THINBBA` block at `AGE EQ 60` removing 60% of basal area.
- Seed: `RANNSEED 1`.

Each run wrote `summary.csv`, the FVS database, and `provenance.json` in its own
directory. The stored files contain only the converted `(TPH, mean tree volume)`
points and their source strings.

## Results

| AU | Regime | Points | Envelope |
| --- | --- | --- | --- |
| AU-IDFdk3-FDI | `REG-A-UNTREATED` | 9 | extrapolated |
| AU-IDFdk3-FDI | `REG-A-CT60` | 9 | extrapolated |
| AU-IDFdk3-PLI | `REG-B-UNTREATED` | 9 | inside |
| AU-IDFdk3-PLI | `REG-B-CT60` | 9 | extrapolated |

The FDI no-cut path leaves the observed envelope because the synthetic FVS tree list
is a different stand from the synthetic PSP points. That is a real finding about the
input mismatch, not a defect in the assessment.

## Limits

- The tree lists are **synthetic**. The pilot AU has no real PSP or FVS input yet.
- The site index is a single FVS site code, not a measured site series.
- The CT60 treatment is one `THINBBA` block; it is not a full regime library run.
- The trajectories are `provisional`. They must not be presented as real AU yield
  evidence.
- The PSP observed check now requires a reviewed PSP plot at the point age and a
  tree list. The current envelope is built from the fixture points that pass that
  test; the synthetic point is excluded and named. The fixture labels are still not
  a real PSP extract.

P95.2 remains open until a real PSP input is available. The public FAIB PSP
header has no `IDFdk3` sites in TSA 24, so the pilot label is synthetic; TSA 23
has 145 `IDFdk3` sites. See `notes/reports/p95-pilot-evidence.md`.
