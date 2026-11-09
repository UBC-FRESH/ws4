# P158.2 Plan named scenarios and target diffs

Date: 2026-11-08
Status: active
Branch: `feature/p158-scenarios`
Parent issue: #928
Task issue: #933

## Summary

Plan now has a scenario library separate from the live target file.

- **Save as scenario** validates the current editor rows and stores them under
  `runs/scenarios/<slug>/targets.yaml` with `scenario.json` metadata.
- **Load into editor** restores a saved target set without modifying live targets.
- **Reload live** discards the editor state and reloads the live target file.
- **Delete** removes a saved scenario.
- The target diff compares the editor rows with the live target file and reports
  added, removed, and changed fields. Loading a scenario is therefore reviewable before
  it is published.

## Verification

- API tests: save/list/load/delete a scenario; live targets byte-identical; invalid names
  and incomplete target documents rejected.
- Browser test: change a bound, save as scenario, verify live targets unchanged, reload
  live to clear the diff, load the scenario, and confirm the changed bound returns.
- No browser page errors.
- Dashboard: `OVERALL: GREEN`.

## Limits

- Loading a scenario is a draft in the editor, not an automatic live write. Publishing
  still requires **Save targets**.
- Scenario metadata currently records name, description, creation time, target count, and
  source; richer provenance/versioning can follow in P158.4.
