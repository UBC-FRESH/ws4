# P129 GPU profile current targets and budget

Date: 2026-11-03
Status: complete; PR #801

## Change

- `gpu_profile_run` accepts `--targets` to override the profile target file.
- It accepts `--max-seconds` and stops the search at the wall-clock budget.
- The web profile command passes the editable target file and the Solve
  `time_limit`.
- Run profile saves current chart/table edits first; it no longer applies the
  profile target library.
- Load profile remains the action that loads a profile's target file.

## Verification

- Focused web test asserts the profile worker command includes `--targets` and
  `--max-seconds 30.0`.
- Dashboard and live browser smoke are recorded at closeout.
