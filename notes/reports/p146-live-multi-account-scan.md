# P146 live multi-account TSA27 scan

Date: 2026-11-07
Status: complete
Branch: `feature/p146-live-multi-account-scan`
Parent issue: #862
Task issue: #863
Merge commit: `65c5daf`

## Result

The live browser scaffold launched a real five-account TSA27 portfolio:

```text
artifact: portfolio-20261107-180709
members: 8
exact front: 1
failures: 0
targets: targets-scaffold.yaml
```

The run used five account/period target rows, five weight dimensions, random sampling,
2,000 iterations, four workers, and a 200-year horizon. It did not modify the live target
file.

## Bug found and fixed

`api()` ignored its options argument, so **Run portfolio** and **Stop** were sent as GET
requests. The live run failed with:

```text
no search artifact named 'portfolio' under .../runs/femic-tsa27-instance
```

P146.1 made `api()` merge fetch options and headers correctly. The rerun then produced the
portfolio above.

## Browser verification

- Pareto opens `portfolio-20261107-180709` by default.
- Eight members, one exact front, zero failures.
- Front member `member-007:001` was selected.
- **Open on map** promoted it to:
  `pareto-portfolio-20261107-180709-member-007-001`.
- Map loaded with no page errors.

## Note

The front is small because all five targets are areas with similarly shaped current-value
minima. The run proves the five-account path; it does not claim the target levels are a
calibrated multi-account policy.
