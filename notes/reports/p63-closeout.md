# Phase close-out report: P63 UI foundation

Phase: P63, UI foundation for desktop and iPad landscape
Parent issue: #442
Pull request: this P63 PR
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P63 pull request and delete `feature/p63-ui-foundation`.
2. Close tasks #443/#444/#445/#446 and parent #442.
3. Move the deferred visual work (map palette, LiDAR scale, carbon chart, target/table
   redesign) to the next UI increment.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Four workspaces and nested Results/Data sections. | Map, Plan, Results, Data; Reports/Compare/Search and Dataset/LiDAR/Carbon. | Met |
| iPad landscape fits without horizontal page scroll. | Playwright: 1024×768, 1194×834, 1366×1024, 1500×1000; `body.scrollWidth` equals viewport at all four. | Met |
| Map keeps usable width. | 690 px at 1024, 806 px at 1194, 923 px at 1366, 1014 px at 1500. | Met |
| Accessible navigation and URL state. | `role=tablist/tab/tabpanel`, `aria-selected/controls`, Arrow/Home/End; URL restore and back/forward tested. | Met |
| Unavailable LiDAR/Carbon are not dead ends. | c5 Data shows Dataset only; carbon run shows Dataset/Carbon; LiDAR dataset shows Dataset/LiDAR. | Met |
| Map cold-load has an explicit state. | TSA 46 shows a loading overlay from the first run-load frame until the MVT layer is ready. | Met |
| Existing smokes still pass. | LiDAR, Carbon, Compare, and Target smokes exit 0 after navigation updates. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Verification evidence

Shell check, `scripts/check_ui_shell.py`:

| Viewport | Body width | Map width | Workspaces | URL/keyboard |
| --- | ---: | ---: | --- | --- |
| 1500×1000 | 1500 | 1014 | Map/Plan/Results/Data | pass |
| 1366×1024 | 1366 | 923 | Map/Plan/Results/Data | pass |
| 1194×834 | 1194 | 806 | Map/Plan/Results/Data | pass |
| 1024×768 | 1024 | 690 | Map/Plan/Results/Data | pass |

The script exits 0. It also checks URL restore (`view=data`, `sub=dataset`, `period=0`) and
keyboard ArrowRight from Map to Plan.

Browser smokes:

- `check_lidar_browser.py` — Data → LiDAR; field selection, map requests, legend, block
  detail; exit 0.
- `check_carbon_browser.py` — Data → Carbon on the real TSA24 run; accounts, chart,
  composition, files; exit 0.
- `check_compare_browser.py` — Results → Compare; 9 compare tiles, target Kind column,
  ending rows; exit 0.
- `check_target_browser.py` — Plan on TSA 46; add/remove target; exit 0.
- `check_ui_shell.py` — all four sizes; exit 0.

## What changed

- Four primary workspaces with proper nested sub-navigation.
- Viewport-aware sidebar width (`clamp(20rem, 32vw, 30rem)`) and clamped saved widths.
- Two-row header at ≤1200 px so Run/Period/status do not clip on iPad landscape.
- Dataset panel with manifest summary and provenance note.
- Capability-aware Data navigation (Dataset always; LiDAR/Carbon only when available).
- Map loading overlay and run-context loading state.
- Document title includes dataset and run.
- Larger workspace tab targets and minimum 12 px metadata hints.

## Deferred, explicitly

- Phone layouts are not supported.
- Map colour hierarchy, selected-block highlight, and on-map legend.
- LiDAR coverage badge, global scale, and colour-blind-safe palette.
- Carbon chart axes/tooltips and account human names.
- Targets list/detail redesign and shared table primitives.
- Skin/map-engine controls still live in their current locations.

Those are the next UI increment, not hidden in this one.
