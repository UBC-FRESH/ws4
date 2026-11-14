# P178 close-out: free-burn weather ensemble

Date: 2026-11-11
Phase: P178 (#1051)
Branch: `feature/p178-freeburn-ensemble`
Pull request: #1055

## Outcome

Ran four large free-burn cases with five weather members each.

## Result

- 20 runs;
- zero spread in final area and IoU;
- every member for a case produces the same final extent;
- time to observed area varies by 2,040–6,600 minutes within a case;
- the model fills the burnable basin.

## Decision

P178 is complete. The weather ensemble is degenerate and cannot be used as a risk
distribution. Add containment/stopping or a defensible burnable-area constraint. P164.3 remains
paused.

## Limits

- Four large fires at 500 m.
- Weather perturbations are a sensitivity envelope, not a calibrated ensemble.
- Reanalysis weather and daily perimeters.
- No small suppressed fires.

## Verification

- Dashboard: GREEN.
- Ensemble runner test green.
- No merge without maintainer approval.
