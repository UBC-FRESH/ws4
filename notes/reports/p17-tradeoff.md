# P17.6: the road/haul trade-off — a model difference, not an accounting one

With the period accounting matched (P17.2/P17.5), the remaining difference between WS4 and the
reference on the 2026 sample is **which roads are chosen**, not how they are counted. Period 1,
`destination.MILL1`:

| quantity | WS4 | reference | ratio |
| --- | ---: | ---: | ---: |
| `LENGTH` (distinct road, m) | 882,027 | 1,149,647 | 0.77 |
| `BUILTLENGTH` (m) | 386,352 | 732,073 | 0.53 |
| `BUILD_EXPENSE` | 1,931,761 | 3,660,367 | 0.53 |
| `HAUL_EXPENSE` | 6,294,644 | 11,174,512 | 0.56 |
| `MAINTAIN_EXPENSE` | 1,052,489 | 1,126,465 | 0.93 |
| `VOLUME` | 1,024,809 | 1,029,670 | 0.995 |
| `AVERAGEHAULDIST` (km) | 61.38 | 50.34 | 1.22 |
| `AVERAGEHAULCOST` (per unit) | 6.14 | 10.85 | 0.56 |
| `AVERAGEBUILDCOST` (per unit) | 1.885 | 3.555 | 0.53 |

## The decomposition

- **Build is a quantity difference, not a rate.** `BUILD_EXPENSE / BUILTLENGTH` is **5.00 per metre on
  both sides**. The reference builds 1.9× the length; it does not price the metre differently.
- **Haul is a route-cost difference, not a distance difference.** WS4 hauls **22% farther** (61.4 km
  against 50.3 km) but on roads whose cost is **0.46× per unit-km** (0.100 against 0.216): a longer,
  cheaper path. The net haul is 0.56×.
- **Road use and maintenance are close** (0.77 and 0.93), so the two models put wood over a comparable
  amount of road; they disagree about *which* road and how much to build.

## What causes it

WS4 routes each block to the least-haul destination over the roads that exist, and opens a planned path
only when nothing reaches the block. Its route choice prices **haul only**. The reference's solve
chooses the road set and the block-to-mill assignment **together**, under its targets, so it accepts a
shorter, more expensive haul and builds more road where its objective values it. Neither is an error in
the other's accounting; they optimise different things.

This is consistent with the earlier finding that the reference's own solution set is nearly the whole
zero-build network (22,901 of 24,273 segments): the difference is not availability, and not the
per-metre rates.

## Decision

- **Record the divergence by name** rather than adding an uncalibrated road price. The parity mode
  already has a `divergences` mechanism; this becomes the second named entry (after maintenance):
  *road selection and haul routing* — WS4 minimises haul over the existing/open roads, the reference
  solves the road set jointly under its targets — with the ratios above as the measurement.
- **Do not add a road-cost weight as a default.** A weight fitted to one period would be a tuning
  artifact, not the reference's objective. If the paper or a future phase wants the reference's road
  behaviour, the honest route is a joint road/harvest solve with the weights stated and calibrated
  against this table.

## Reporting fix included

`AVERAGEHAULDIST` was written in **metres** while the reference reports **kilometres** (61,375 against
50.34 — the 1,219× in the raw columns). The report now divides by 1,000, so the columns are comparable:
61.38 km against 50.34 km. The model still routes in metres; only the report's unit changed. This closes
the last P13 item ("the route report's distance unit").

## Files

- `notes/reports/p17-opened-roads.md` — the dated-road mechanism and the period accounting.
- `tests/test_roads.py` — the period-fold test asserts the km unit and the once-per-period maintenance.
- `tmp/parity2025/run-dated3` — the run behind the table (untracked).
