# P165 close-out: public fire corpus

Date: 2026-11-11
Phase: P165 (#985)
Branch: `feature/p165-public-fire-corpus`
Pull request: #990
Design: `notes/design/ws4-public-fire-corpus.md`
Registry: `ws4/fire/corpus.py`
Daily corpus: `ws4/fire/daily_corpus.py`

## Outcome

P165 replaced the unspoken "two fires are enough" assumption with two explicit evidence tiers.

### Depth - hourly/FBP

- 2 cases are usable with documented limits: Dogrib (licence/review limit) and Hay River
  (saturation and reconstructed ignition).
- 0 cases are fully ready.
- The depth gate is **blocked**: 0 of 3.
- CFSDS `2023_321` was reviewed and rejected for depth because it is a 53-day, 433,036 ha,
  ~105 km event with daily weather only. One regional station cannot represent hourly weather
  across that footprint.
- No third depth case was invented or relabelled from daily data.

### Breadth - daily CFSDS

- 20 ready daily cases.
- 3 years: 2003, 2009, 2023.
- 4 ecozones.
- Final areas 510.3 to 49,765.6 ha.
- Durations 2 to 75 days.
- The breadth coverage gate **passes**.

The breadth corpus is **observation-only**. It checks daily-summary/raster agreement, daily
weather completeness, fuel/terrain coverage, and independent identifiers. It does not run WS4
and does not establish hourly/FBP model skill.

### Model-only

FireSTARR and BurnP3 remain model-only evidence and are excluded from observed-corpus counts.

## What was added

- `ws4/fire/corpus.py` - tier/status contract, candidate registry, and observed gate.
- `scripts/build_fire_corpus_manifest.py` - registry manifest and inventory.
- `ws4/fire/daily_corpus.py` - daily CFSDS selection and integrity checks.
- `scripts/build_daily_fire_corpus.py` - daily corpus manifest.
- `docs/reference/fire-corpus.rst` - tier and gate documentation.
- 20-case daily manifest and inventory artifacts.
- Tests for the registry, gate, daily selection, and manifest scripts.

## Decision

P165 is a **partial success with an explicit depth block**:

- breadth: 20 observation-only daily cases, gate passes;
- depth: 2 limited cases, gate blocked;
- P164.3 burn-probability calibration remains **paused**.

The two-fire problem is now separated from the corpus problem. We have a real daily sample, but
it is not model-ready hourly evidence.

## Next decision

Before P164.3 can resume, one of these must happen:

1. add a daily WS4 driver and run the 20-case daily corpus as a daily event check; or
2. acquire at least one independent hourly/FBP depth case; or
3. define a probabilistic calibration approach that does not require either, with its own
   validation contract.

Option 1 is the shortest path from this corpus to model evidence. Option 2 is the stronger
process validation. Option 3 should not be used to bypass the first two without a new design
note.

## Limits

- One fuel/terrain tile (UTM 11N), not national coverage.
- Three CFSDS years, not a continuous record.
- Daily weather and satellite-derived perimeters.
- No WS4 simulation on the 20 daily cases.
- No burn-probability, treatment-effect, or tree-mortality validation.

## Verification

- Dashboard: **GREEN**.
- Registry tests: green.
- Daily corpus tests: green.
- No merge without maintainer approval.
