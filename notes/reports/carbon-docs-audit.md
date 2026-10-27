# Carbon documentation audit and remediation

Date: 2026-10-27
Scope: WS4 and FEMIC carbon-related notes/Sphinx docs, plus the HWP and carbon-curve
documentation requested for system-level carbon optimization
Status: local documentation and implementation pass complete; WS4 dashboard and both
Sphinx builds are green

## Audit standard

The standard is the UBC-FRESH dev workflow: docs are the RTFM surface, stable page paths
are a contract, `docs/llms.txt` is the machine-readable entry point, task guides and
reference pages have distinct jobs, and the same pages must be readable by humans in
several roles. The audit checked five axes:

1. **Completeness** — does the page state the contract, the task, and the evidence?
2. **Cross-reference graph** — can a reader move producer ↔ consumer ↔ evidence?
3. **Organization** — is task knowledge separate from mechanism and from provenance?
4. **Accessibility** — are there role paths, plain-language boundaries, and examples?
5. **Findability** — are stable pages in the toctree, in `llms.txt`, and linked from
   `AGENTS.md` or the relevant index?

## Findings and remediation

| Surface | Finding | Action |
| --- | --- | --- |
| WS4 `docs/llms.txt` | Carbon reference and task guide were absent from the agent entry point. | Added both; expanded descriptions to include HWP and curves. |
| WS4 `docs/reference/carbon.rst` | Titled "Carbon Package Contract" but also covered runtime, targets, fertilization, GCBM, and web; stale "next step" text; stale GCBM prerequisite; incomplete failure-code table. | Retitled as a carbon map, added role paths, data-flow diagram, source-of-truth table, HWP and curve sections, updated status/GCBM/validation text, and completed the code table. |
| WS4 `docs/howto/` | No end-to-end carbon task guide. | Added `run-carbon.rst`; linked from the how-to index and `llms.txt`. |
| WS4 `docs/index.rst` | Role list did not name researchers/policy analysts; no carbon quick path. | Added role paths, instructor/student path, agent pointer to `llms.txt`, and a carbon quick-nav row. |
| WS4 installation | Optional `carbon` extra was undocumented. | Added the extra row and the task-guide link. |
| WS4 limitations | No carbon section; GCBM parity and ledger exactness could be over-read. | Added carbon, HWP, curve, and GCBM boundaries. |
| WS4 troubleshooting / FAQ | Carbon symptoms missing. | Added install, track join, defaults mismatch, target guard, ledger/exact, HWP, and GCBM entries. |
| WS4 `notes/design/ws4-carbon.md` | Draft status; said carbon was out of scope; wrong yield source; stale GCBM/parity and open questions. | Marked historical, linked the current contract, corrected the yield source, GCBM boundary, and current-state list. |
| WS4 `notes/reports/` | P120 production evidence lived only outside the repo; no carbon docs audit record. | Added `p120-multi-boundary.md` and this audit. |
| FEMIC `docs/llms.txt` | Missing entirely. | Added an agent-facing index and `html_extra_path` in `docs/conf.py`. |
| FEMIC carbon guides | No producer-side landing page; export, fertilization, HWP, and GCBM were disconnected. | Added `carbon-overview.rst` and `hwp-lifecycle.rst`; linked all four pages. |
| FEMIC `carbon-domain.rst` | Said multi-boundary needed a later extension; said WS4 rejected fertilization; no reader paths. | Updated to implemented multi-boundary and fertilization runtime; added reader paths and cross-repo links. |
| FEMIC `carbon-export.rst` | Stale caveat: one boundary per package; stale P58 task references. | Updated to multi-boundary support, package-authoritative yield, and WS4 task links. |
| FEMIC `fertilization-audit.rst` | "Current boundary" said runtime wiring was separate. | Updated to the merged WS4 curve/recovery/ledger path and kept the assumption caveat. |
| FEMIC `gcbm-export.rst` | Boundary text implied a simple one-boundary project; no parity caveat. | Updated boundary handling and stated bridge-not-parity. |
| FEMIC `AGENTS.md` | Carbon docs absent from the compact source-of-truth list. | Added the carbon overview, export, fertilization, HWP, GCBM, and domain contract. |
| HWP lifecycle | The docs did not say how product split, half-life, displacement, or EOL emissions are counted. | Added the FEMIC HWP guide, public config, WS4 accounts, and target syntax. |
| Carbon yield curves | The "simulated clearcut" hack was not documented or exposed in WS4. | Added `ws4 carbon-curves`, the curve module, and method/boundary docs. |

## Pages reviewed

WS4 Sphinx:

- `docs/reference/carbon.rst`, `docs/reference/index.rst`, `docs/reference/web.rst`
- `docs/howto/run-carbon.rst`, `docs/howto/index.rst`, `docs/howto/faq.rst`
- `docs/guides/limitations-and-boundaries.rst`, `docs/guides/troubleshooting.rst`
- `docs/getting-started/installation.rst`, `docs/getting-started/architecture.rst`
- `docs/index.rst`, `docs/llms.txt`

WS4 notes:

- `notes/design/ws4-carbon.md`
- `notes/reports/p58-closeout.md`, `p58-fertilization-runtime.md`, `p585-parity.md`,
  `p587-carbon-optimizer.md`, `p588-carbon-validation.md`, `p589-gcbm-results.md`
- new: `p120-multi-boundary.md`, `carbon-docs-audit.md`

FEMIC Sphinx:

- `docs/guides/carbon-overview.rst` (new), `carbon-export.rst`,
  `fertilization-audit.rst`, `hwp-lifecycle.rst` (new), `gcbm-export.rst`
- `docs/reference/contracts/carbon-domain.rst`, `docs/guides/index.rst`,
  `docs/index.rst`, `docs/llms.txt` (new)
- `docs/conf.py` (`llms.txt` copy), `config/carbon/README.md`, `config/carbon/hwp.bc.yaml`

FEMIC notes:

- `notes/reports/p115-closeout.md`, `p1151-crosswalk-review.md`,
  `p1154-gcbm-export.md`, `p1155-handoff-parity.md`
- new: `notes/reports/p120-multi-boundary.md`

## What the graph now looks like

- **Producer map:** FEMIC `carbon-overview` → `carbon-export` → `carbon-domain` →
  `fertilization-audit` / `hwp-lifecycle` / `gcbm-export`.
- **Consumer map:** WS4 `reference/carbon` → `howto/run-carbon` → limitations,
  troubleshooting, FAQ, web.
- **Evidence map:** WS4 `p58-*`, `p120-multi-boundary`, and the FEMIC P115 reports.
- **Method references:** the thesis and `fresh-yan` are cited from both sides, not copied.

## Implementation added in the same pass

- `ws4/carbon/hwp.py` — public HWP lifecycle: utilization, paper/solid split, exact
  survival, decay, EOL emissions, displacement, and system accounts.
- `ws4 carbon --hwp-config`, `ws4 optimize --carbon-hwp`, and HWP target guards.
- `ws4/carbon/curves.py` and `ws4 carbon-curves` — stock and emission curves from
  single-stand libcbm runs with the simulated-clearcut method.
- `config/carbon/hwp.bc.yaml` — a WS4 runnable mirror of FEMIC's public assumptions.
- `femic/config/carbon/hwp.bc.yaml` — the canonical, scenario-level HWP assumptions.
- Tests: `tests/test_carbon_hwp.py`, `tests/test_carbon_curves.py`, and HWP
  target/guard tests in `tests/test_carbon_ledger.py`.

## Review fixes

The pre-PR review found and this pass fixed: the HWP path test did not exercise the
telescoping identity, `carbon.displacement.total` was emitted in tCO2e under a tC prefix,
a multi-year `period_length` could silently mis-scale an annual libcbm run, the curve
table needed an explicit CBM-`Products` caveat, the how-to had a stale fertilization
config path, and WS4 had no runnable copy of the HWP config.

## Verification

- WS4 `python scripts/dashboard.py`: **GREEN** on lint, format, strict types, tests with
  the coverage gate, validator, docs, and docstrings.
- WS4 targeted
  `pytest tests/test_carbon_hwp.py tests/test_carbon_curves.py tests/test_carbon_ledger.py -q --no-cov`:
  16 passed.
- WS4 `sphinx-build -b html docs _build/html -W`: build succeeded, no warnings.
- FEMIC `sphinx-build -b html docs _build/html -W`: build succeeded, no warnings.

## Remaining gaps / next review

1. The HWP decay is immediate EOL to atmosphere. Landfill and inert long-lived pools need
   a later contract if the policy question requires them.
2. The curve artifact is not yet the optimizer's surrogate. A reduced LP or curve-based
   search must be labelled and verified against the exact block ledger.
3. Species-resolved curves, intensity-specific `ct`, and MPB severity remain package
   science refinements, not documentation gaps.
4. GCBM remains a bridge; do not reopen numerical parity as a docs/validation goal.
