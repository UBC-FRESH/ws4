> **SUPERSEDED 2026-11-25.** This portfolio note predates the unique-fire calibration, the
> post-2018 comparison, and the FireSTARR TSA24 checks. Use `p164-9-retention-model.md` and the
> current archive manifest. The 58-file hash count and failed-FireSTARR statements are historical.

# P164 manuscript portfolio

Status: **one canonical paper plus one reproducibility archive.**

The four-draft portfolio was retired after the 2026-11-23 adversarial review. The review found that
the drafts overlapped almost completely, that the event test was in-sample, that the optimizer was
harvest-only, and that the benchmark was neither public nor a TSA24 benchmark. Writing four papers
from one model and one evidence set would be salami slicing.

## Canonical paper

Repository: `UBC-FRESH/fresh_ws4_fire_regime_manuscript` (private draft).

Working title: *An open, auditable fire-regime layer for forest estate risk: integration and
negative calibration, transfer, and event diagnostics on TSA24.*

Target: *Environmental Modelling & Software*; backup *Geoscientific Model Development*.

The single paper contains:

- the open WS4 fire/ecosystem integration;
- the compiled TSA24 data path and support-map boundary;
- the pre-registered global calibration no-go, including validation failures;
- the 23-region in-sample calibration and its tail residuals;
- the training-only transfer test, bootstrap uncertainty, and ridge diagnostic;
- the in-sample point-ignition reconstruction and its limitations;
- the five-seed risk ensemble and five-year fixed-schedule case;
- the 112-tile harvest-feasibility search, fire-blind null, and decision-space boundary;
- the Dogrib growth check and the failed TSA24 FireSTARR attempt;
- the archive/reproducibility boundary and the unresolved licences/DOI.

It does **not** claim independent validation, fire-aware optimization, a global optimum, a TSA24
external benchmark, operational forecasting, or open data end-to-end.

## Retired drafts

These repositories are retained only for audit and history. Each has a `STATUS.md` and a README
banner saying **not for submission**.

| Repository | Disposition |
| --- | --- |
| `fresh_ws4_fire_calibration_manuscript` | Merged into the canonical paper; calibration/transfer is a section, not a separate paper. |
| `fresh_ws4_fire_optimization_manuscript` | Merged as a feasibility/null result; no fire-aware optimization exists. |
| `fresh_ws4_fire_benchmark_manuscript` | Merged as data/software evidence; not a public benchmark or data descriptor. |

Do not submit, DOI, or cite the retired repositories as separate contributions.

## Archive

`https://github.com/UBC-FRESH/fresh_ws4_fire_regime_repro` (private).

The archive is partial: the 133 full-estate layers are regenerated, while the support map and 24
named calibration tiles remain frozen derived inputs. It has a 58-file hash manifest and staged
scripts, but no clean-host raw-to-result run or DOI. The canonical paper reports this status
directly.

## Remaining submission blockers

- Public archive with DOI, clean-host run, environment lock, and licence sign-off.
- Derived support map and regenerated 24 named calibration tiles.
- A genuinely independent temporal/spatial validation, if the paper is to make a validation claim.
- A fire-risk objective and near-global baseline, if a separate optimization paper is revived.
- A TSA24 external benchmark; the Dogrib fire is not one.
- Final author list, funding, data-provider credit, and competing-interest statement.
- Target-journal length, reference, and figure compliance.

## Rule for future work

No new manuscript is opened from this project unless it answers a question the canonical paper does
not, uses independent evidence, and has a distinct claim boundary. The default is to extend the
canonical paper and archive, not to split it.
