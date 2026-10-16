# Faster matrix builder (performance spike)

Status: **spike**. Branch `spike/builder-perf`, off P6 head `a00b255`. Checkpoint tag
`p6-builder-checkpoint` for one-command rollback.

Related: `notes/design/ws4-matrix-builder-and-interop.md`, `notes/performance.md`.

## 1. Motivation and evidence

The matrix builder is the largest wall-clock cost for a rich recipe: the canonical MKRF recipe
(1 763 fragments, 7 048 strata) compiles in ~3 min. cProfile on 200 fragments (34 s):

| Hot spot | Cost |
| --- | ---: |
| `expressions._as_number` (12 785 436 calls) | 11.3 s |
| `expressions._lookup_table` (301 745 calls) | 10.8 s |
| `str.strip` (31 715 851 calls) | 3.3 s |
| `str.split` (603 668 calls) | 1.2 s |
| `compiler._expand_tokens` (82 131 calls) | 1.4 s cum |

The recipe's expressions are dominated by huge constant `lookupTable(...)` literals. `_lookup_table`
**re-splits and re-strips the literal tables on every call**, then scans them with `_as_number` per
entry. The same literal is evaluated once per stratum per attribute, so the same megabytes are
re-parsed hundreds of thousands of times.

## 2. Hypothesis

A `lookupTable` literal is constant, and its evaluates come from the same cached parse tree, so the
same Python `str` objects are passed on every call. Parsing it once (keyed by object identity, with an
identity check to guard `id` reuse) turns each call into one or two dict lookups.

## 3. Design

- **A — parse the literal once.** Cache `_lookup_table`'s parsed form (`{key_string: value}` plus a
  `{float_key: value}` index) in a module-level dict keyed by `id(keys_text)`, storing the strings to
  keep them alive and verifying identity on hit. Match numerically when the key parses as a number, else
  by string — the same rule as today, without the per-entry `_as_number` scan.
- **B — skip token expansion when there is no token.** `_expand_tokens` scans the whole (megabyte)
  expression; add an early `if "%" not in text: return text`.
- **C — evaluate each stratum's selects once.** `expand_strata` calls `matching_selects` twice per
  stratum (transition discovery and the final mapping); cache the result per key.

Scope: `ws4/io/expressions.py` (A), `ws4/build/compiler.py` (B), `ws4/build/expansion.py` (C). No change
to recipe semantics or the compiled dataset.

## 4. Correctness plan

- The evaluator's results must be unchanged: the existing expression tests, the nine core acceptance
  variants, and the full MKRF canonical comparison are the gate.
- A new unit test asserts `lookupTable` still matches numeric and string keys, duplicate/absent keys,
  and that a repeated call (same literal object) returns the same value.
- The builder output for the canonical recipe must be unchanged (acceptance).

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| MKRF build, 200-fragment slice | ~34 s | < 10 s |
| Canonical MKRF build (full) | ~3 min | < 1 min |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| `id` reuse gives a stale table | Store the strings and verify object identity on hit |
| Numeric vs string matching changes | Unit test for both, plus the acceptance variants |
| Caching memory | One entry per distinct literal; bounded by the recipe's literals |

## 7. Milestones

- **M1** A (parsed-table cache) + unit test; measure.
- **M2** B and C; measure.
- **M3** A/B vs `p6-builder-checkpoint` (200-fragment slice and the full canonical build); docs and
  decision.

## 8. Decision and rollback

- **Adopt** if the 200-fragment slice drops below 10 s with identical output.
- **Abandon** otherwise: `git checkout feature/p6-performance`.

## 9. Log

- 2026-10-16: plan written; profiling done (section 1). Starting M1.
