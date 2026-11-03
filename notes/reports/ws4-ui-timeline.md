# P122 run timeline and interaction uplift

Date: 2026-11-03
Status: complete; PR #783

## Change

- Reports gains a run snapshot card grid from `summary.json`.
- The header period control gains a Play/Pause control.
- Results gains a Timeline subview built from the run's `schedule.csv`.
- A toast surface provides save/apply/run feedback.
- A native help dialog and keyboard shortcuts cover `/`, `?`, `m`, `j`/`k`,
  arrows, and `Esc`.
- Schedule and snapshot empty states are explicit and actionable.

## Sources

The interaction patterns were selected from the FRESH lab UI review in
`notes/design/ws4-ui-port-plan.md`.

## Verification

- Focused web tests cover the new shell affordances and timeline loader.
- `node --check` covers the browser script.
- Dashboard result: `OVERALL: GREEN` on all seven gates. Browser smoke: 10 snapshot cards; a TSA27 timeline with 8,276 events; playback advanced period 1 to 2; help dialog opened. `node --check` passed.
