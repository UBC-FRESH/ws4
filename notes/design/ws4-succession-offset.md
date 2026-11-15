# Five-year succession offset

Status: implemented (P235)
Phase: P235 (#1340)
Date: 2026-11-15
Related: `notes/design/ws4-compiled-curves.md`

## 1. Purpose

P234 compared a single harvest. P235 compares a five-year no-schedule trajectory using the LANDIS
succession process and the compiled natural yield curve.

## 2. Offset convention

- Estate `simulate(..., years=5)` writes offsets 0–4. The final offset is 4 and ages are 44/64.
- The process engine's `horizon_years` counts annual transitions.
- Four process transitions reach ages 44/64 and match the estate final offset.
- Five transitions reach ages 45/65 and are one step ahead.

## 3. Exact results

| Process transitions | Estate final | Process final | Difference |
| --- | --- | --- | --- |
| 4 | 750 | 750 | 0 |
| 5 | 750 | 762.5 | +12.5 (1.667%) |

## 4. Evidence

- `tests/test_landis_succession_offset.py`: 1 passed.
- Four-transition comparison is zero.
- Five-transition difference is exactly one age step at both fragments.

## 5. Limits

- No fire, harvest, or regeneration.
- Single species and one compiled curve.
- The offset is a convention finding, not calibration.
