# P137 overlay and coverage findings

Date: 2026-11-06
Status: **digitization is incomplete**

The corrected overlays show that top height, QMD, competition, and self-thinning
follow the source well for most curves, but the digitization is not complete.

## Top-height/QMD count audit

Printed labels vs stored curve counts:

| Diagram | Top height printed/stored | QMD printed/stored |
| --- | --- | --- |
| `fdcn` | 11 / 11 | 10 / 10 |
| `fdcp` | 10 / 10 | 9 / 10 |
| `ssn` | 8 / 10 | 10 / 11 |
| `ssp` | 5 / 7 | 8 / 10 |
| `hwn` | 11 / 12 | 10 / 10 |
| `hwp` | 6 / 10 | 9 / 9 |
| `cwn` | 11 / 11 | 10 / 11 |
| `cwp` | 7 / 11 | 10 / 10 |
| `swn` | 9 / 9 | 6 / 9 |
| `swp` | 9 / 9 | 8 / 8 |

The extra stored curves are likely TASS curves or other dotted paths misclassified
as top height/QMD. The missing curves are real gaps. This is not acceptable for a
complete diagram.

## Curves not represented in the schema

The current `SdmdDiagram` model has only:

- `top_height`
- `qmd`
- `crown_closure`
- `competition`
- `self_thinning`

It has no representation for:

- the pale **TASS predicted mortality** curves
- the filled grey **density range for maximizing CAI** band

Those were omitted by design in the original schema. That design is not sufficient
for source-complete digitization, and the overlay packet should not claim parity.

## Crown closure

The raster-traced `crown_closure` curve does not follow the source dotted curve.
It must be replaced by the correct source path or re-traced.

## Verdict

The current 10 diagrams are **incomplete**, not approved. The next work is:

1. extend the diagram model for TASS curves and the CAI band,
2. assign every printed top-height/QMD label to exactly one source path,
3. replace crown closure with the correct path/trace,
4. re-overlay and recount,
5. only then ask for sign-off.
