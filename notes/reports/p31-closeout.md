# Phase close-out report: P31 Comparison map over MVT

Phase: P31, Comparison map over MVT
Parent issue: #257
Pull request: #259, merged as `3a3306c`
Evidence head: `3a3306c`
Date: 2026-10-25
Status: merged and closed; parent #257 closed.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Compare requests MVT tiles, not the full A/B GeoJSON. | c5 requested `/compare-tiles/...`; the map used the existing vector source. | Met |
| A-only, B-only, and both use the compare colors. | The tile carries `compare`; the vector paint maps a/b/both to red/blue/purple. | Met |
| The summary counts come from compare-stats. | c5: A only 3, B only 1, both 0, neither 12,563. | Met |
| `python scripts/dashboard.py` is green. | Green at `3a3306c`. | Met |

## 2. Deviations

- Compare tiles are memory-cached only; durable disk caching is not part of P31.
- The first compare request builds the geometry cache; later tiles are warm.

## 3. Settings

No settings, tags, releases, or external accounts changed.
