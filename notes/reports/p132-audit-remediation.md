# P132 adversarial audit remediation

Date: 2026-11-04
Parent: #809
Branch: `feature/p132-audit-remediation`
Plan: `notes/reports/p132-audit-remediation-plan.md`

## Result

The P121/P123 audit findings are closed in code, data, tests, reports, and
GitHub traceability. No Critical defect was found by the audit; the four High
findings and the Medium/Low findings are addressed below.

## Finding closure

| Finding | Closure | Evidence |
| --- | --- | --- |
| H1 AU metadata gap | Store now compares the label BEC/TSA with the plot columns | `validate_au_metadata`; `test_store_refuses_contradictory_plot_metadata` |
| H2 CCISS counts inflated | Unique relationship rows; phase aliases normalized; parent summaries removed | `bec_crosswalk_review.csv`: 183 same, 7 WS4 splits, 9 CCISS splits, 19/19 absent |
| H3 229-label overclaim | Reports and tests now say 229 rows / 213 unique labels / 16 phase rows | `test_crosswalk_normalizes_phase_aliases_and_counts_labels` |
| H4 phase inconsistency | BECdb aliases resolve `ICHmc1a`, `ICHxwa`, `SBSwk3a` to base labels | `normalize_bec_label`; phase AU tests |
| M1 PSP alias/subzone rows | `ICHmw5` normalized to `ICHwm5`; 36 subzone rows removed; 304 variant rows remain | `tsa_bec_counts.csv`, `test_ichmw5_alias_reaches_the_support_table` |
| M2 validator fail-open | `official_bec`/`retired_bec` default to packaged tables | `test_validator_defaults_refuse_a_retired_label` |
| M3 `_chat_index` crash | decimal/length cap/try-except; long and Unicode digits return None | `test_chat_index_rejects_long_and_unicode_digits` |
| M4 context prompt injection risk | Context is one escaped JSON line with an untrusted-data guard; backticks/control chars stripped | `test_chat_context_lines_are_delimited_untrusted_json` |
| M5 stale closeouts | P121/P123 merged status, head, and CI run corrected | `tests/test_workflow_reports.py` |
| M6 duplicate P123 prefix | PR #797 recorded as a concurrent shared-kernel exception in the P123 closeout | `notes/reports/p123-closeout.md` §3a |
| M7 P121 issue links | #770-#773 linked under #769; #769/#770 bodies updated | GitHub sub-issue API |
| M8 no derivation trail | `bec_sources.json` records sources, version, date, transforms, SHA-256 | `scripts/check_bec_authority.py` |
| M9 chip parser variants | case-insensitive, multiline/fenced, repeated markers; visible marker stripped | `test_split_chat_actions_handles_lowercase_multiline_and_repeated_markers` |
| L1 MHun note/version | note matching is case-insensitive; v12 note vs v13 retired table documented | `test_mhun_note_matching_is_case_insensitive` |
| L2 provenance | CCISS vs BECdb vs P121 files separated in `docs/reference/sdmd.rst` | docs diff |
| L3 frontend tests | Node harness exercises `applyChatChip` workspace, subview, period, block, toast, ask | `tests/test_web_chips_js.py` |
| L4 ws4 coverage not gated | Recorded baseline 80.95% for `ws4`; gate still measures `scripts` | this report |
| L5 old CCISS table | docs point to `bec_crosswalk_review.csv`; raw union remains as input | `docs/reference/sdmd.rst` |
| L6 exact-label wording | Official crosswalk adds `covered_by_finer` for 3 parents | `bec_official_crosswalk.csv` |

## Verification

```bash
python -m pytest tests/test_sdmd_bec.py tests/test_sdmd_au_integrity.py \
  tests/test_sdmd_api.py tests/test_web.py tests/test_web_chips_js.py \
  tests/test_bec_authority.py tests/test_workflow_reports.py -q
python scripts/check_bec_authority.py
python scripts/dashboard.py
```

Focused tests: 136 passed. BEC authority check: pass. Dashboard:
`OVERALL: GREEN`.

Measured `pytest --cov=ws4`: 80.95% total. The repository's 90% gate still
covers `scripts`, so this phase does not claim a 90% `ws4` gate; it records the
baseline rather than weakening or renaming the existing gate.

## Limits

- External BECdb and FAIB PSP sources were not re-downloaded in this phase; the
  manifest pins the files already retrieved.
- The JS harness is not a full browser test.
- Prompt injection is bounded by escaping and a guard, not proven impossible
  against a model.
- `select_block` still selects only a block present in the current run.
- The 7 CCISS WS4 splits are retired WS4 labels; they are not current coverage.

## PR

Queued separately after the branch is pushed.
