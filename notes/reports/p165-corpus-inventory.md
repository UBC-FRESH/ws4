# P165.1 corpus inventory

Date: 2026-11-11
Phase: P165 (#985)
Task: P165.1 (#986)
Registry: `ws4/fire/corpus.py`
Manifest: `notes/reports/p165-corpus-manifest.json`
Inventory: `notes/reports/p165-corpus-inventory.csv`
Design: `notes/design/ws4-public-fire-corpus.md`

## Result

The public inventory has **7 cases** and **6 independent cases**:

- 3 depth candidates;
- 2 breadth candidates (1 candidate, 1 rejected duplicate);
- 2 model-only cases.

The observed-corpus gate is **blocked**:

| Gate | Required | Fully ready | With limit |
|---|---:|---:|---:|
| Depth | 3 | 0 | 2 |
| Breadth | 20 | 0 | 0 |

## Cases

| Case | Tier | Status | Missing inputs |
| --- | --- | --- | --- |
| Dogrib Scenario 2b | depth | ready_with_limit | licence documentation |
| Hay River 2023_320 | depth | ready_with_limit | none |
| CFSDS 2023_321 | breadth | candidate | not acquired |
| CFSDS 2023_320 daily | breadth | rejected duplicate | none |
| WildfireAV US | depth | blocked | ignition, FBP fuel, licence |
| FireSTARR | model-only | model_only | n/a |
| BurnP3 | model-only | model_only | n/a |

## Interpretation

- Two depth cases are usable with documented limits, but neither is fully ready.
- No breadth case is fully ready.
- The two depth cases are the same cases used in P164.2. They do not become a benchmark by
  adding metadata.
- Model-only outputs remain outside the observed-corpus count.
- The gate is deliberately strict: a `ready_with_limit` case does not count toward the minimum.

## Next

- P165.2: acquire or reject an independent hourly/FBP depth case.
- P165.3: build the 20-case daily CFSDS breadth corpus, or record a no-go.
- P164.3 remains paused until the corpus gate passes.
