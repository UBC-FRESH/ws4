# P127 target chart edits and Solve semantics

Date: 2026-11-03
Status: complete

## Bugs found in the browser

- The target chart applied a minimum/maximum edit to the first target row in a
  period. For periods with an even-flow row, that was the flow row, not the
  level row. The visible level did not change, and saving could fail validation.
- The public-demo checkout implicitly switched Solve into profile mode whenever
  a profile was selected. That bypassed the edited target file and the Solve
  time budget, running the profile's original targets instead.

## Change

- Chart minimum/maximum edits now select the non-flow level row.
- Public-demo Solve always posts the standard run body with the configured
  `time_limit`.
- Run profile remains the explicit action for a profile's own targets.
- The profile bar now explains the distinction.

## Verification

- Browser chart edit: period 1 level saved as `4,000,000`; the even-flow row
  remained `-5..5`.
- Solve request body:
  `{"iterations":0,"patience":0,"time_limit":"00:05:00","seed":1,"years":50,"islands":1}`
- No profile field was sent by Solve.
- Dashboard and focused tests pass.
