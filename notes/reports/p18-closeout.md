# Phase close-out report: P18 A graphical web front end

Phase: P18 A graphical web front end
Parent issue: #146
Pull requests: #151 (service, shell and targets), #152 (live player, reports and skins), #153 (SSE and
review fixes), #154 (comparison), #155 (layer tree), #156 (block polygons and patterns), #157 (source
base colours), #158 (active targets and reports), #159 (source roads), and the documentation pull
request that adds this report
Evidence head: `d439172`, plus the report commit
Date: 2026-10-20
Status: closing.

## Recommendation

1. Close parent issue #146 with a closeout comment citing the pull requests above and this report.
2. Record the model-derived spatial layers, the MapLibre swap and the stability stopping criterion as
   follow-ups rather than pretending they shipped: the source polygons, compartments and access roads
   are real presentation layers, but they are not the run's used-road subset or the spread-connectivity
   compartment membership.
3. No settings changes, tags or releases. The embedded assistant is a local-operator capability and
   must stay behind `--allow-agent` and a trusted, loopback/proxied service.
4. Return to the thesis bridge follow-ups (#8, #14) alongside the model-layer backlog; the spread
   account itself was independently reproduced on the thesis side and #13 is closed.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A session loads the dataset and a run and moves through the horizon | service plus browser checks on `run-dated3` and `run-harvested-flow`; year control and live target windows | met |
| The map shows the layer families | current/cumulative treatments, patch classes, source polygons, source compartments and source access roads; the run's used-road subset and model spread membership are named follow-ups | met for the source-layered first cut; model layers deferred |
| A target edit round-trips and a re-solve uses the CLI's penalty | YAML save through `load_targets`; `active` flag skipped by the objective and incremental evaluator; web-start runs use the same service command | met |
| A report renders from the run's CSV | named standard reports, CSV previews and the account/year builder with CSV export | met |
| The reviewer skin cannot edit | manifest loader and browser check; read-only disables target edits | met |
| The CLI is unchanged without the extra | `web` is an optional extra; `serve` only behind the extra; optimizer/CLI tests unchanged | met |
| The dashboard is green | `python scripts/dashboard.py`: `OVERALL: GREEN` on all seven gates | met |
| The design is recorded before the first UI line | `notes/design/ws4-web-frontend.md`, `docs/reference/web.rst` | met |

## 2. What shipped

- **Service (P18.1).** Optional `ws4[web]` FastAPI service over the compiled dataset, runs, targets,
  schedules, account values, reports and geometry. SSE progress/targets/schedule, a polled player
  (`run`/`pause`/`stop`), optional web-started searches, optional spatial run inputs, and an explicit
  embedded-agent permission.
- **Map and layer tree (P18.2).** Simplified source block polygons (12,567 features, 5 m tolerance),
  boundary strokes, current/cumulative treatment fills and hatch, patch membership classes, source
  base colours (compartment, THEME2, THEME5, MartStrata, LMU), and an optional source access-road
  overlay. Geometry is parsed once; live schedules update only changed blocks.
- **Targets (P18.3).** Editable bounds/weights/periods, YAML round-trip and validation, realized
  values, watched cards over the full horizon, met/below/above/inactive status, an On/off active flag
  written to the YAML, and the Play/Pause/Stop player with parallel islands.
- **Reports (P18.4).** Named standard reports, full file tree, CSV previews, HTML/PNG links, and a
  Build a report form over accounts and years with CSV export.
- **Skins (P18.5).** Four checked manifests, panel/layer hiding, read-only enforcement, comparison
  panel in every skin.
- **Comparison (P18.6).** Two-run map diff, target status and per-account deltas, filterable.
- **Additional, not a roadmap task.** The lower-left embedded OpenCode assistant behind
  `--allow-agent`; it uses the local CLI's own login and can run tools. It is documented as a
  local-operator feature, not a shared-service feature.

## 3. Verification

- Live browser checks: polygons at 12,567 paths (first render ~1.3 s), live updates 0 → 224 treated
  blocks; cumulative 16 current + 1,155 earlier; 30 compartment and 10 THEME5 base colours; 36,721
  source road lines; comparison 15 A-only, 47 B-only, 1 both; active target saved, reported
  `inactive`, watched badge `off`; report builder 10 rows with a CSV download.
- API tests cover the service, targets (including active), maps (treatments, cumulative, patches,
  polygons, source compartments), layers, roads, runs, SSE, skins, reports, comparison inputs and the
  geometry cache.
- CI was green on each merged pull request; the dashboard is green on the close-out head.
- The spread-connectivity account was independently reproduced on the thesis side (issue #13, closed)
  against the deduplicated masks: 3,483 / 3,557 / 3,366 treated blocks and 82,874.4 / 105,020.4 /
  196,766.6 ha largest compartments for barrier/clumped/random.

## 4. Workflow compliance

- Parent issue #146 existed before the UI work; each task was committed on its own branch and merged to
  `main` after green CI.
- The roadmap, changelog, design note, docs and issue/pull-request descriptions are in step.
- No settings, tag, release or external account changes.

## 5. Deviations and corrections

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Watched cards initially showed only target periods | the card was built from target rows, not the run's full account series | cards now span the horizon and use the live yearly series |
| The first web runs used one island and the live counter lagged | `--starts` was not passed; one parent writer handled all telemetry | islands are selectable (default 8); per-worker telemetry files merged after the run; live stream follows the best island |
| A finished run left 342 SSE connections behind a buffering proxy | EventSource retried a short completed stream | finished runs return 204; live streams reconnect after ten minutes; the status poll remains the fallback |
| The first map was a centroid point layer | the configured geometry was points | switched to simplified source block polygons; points remain supported |
| Source access roads and source compartments can be mistaken for model layers | the run does not write used-road geometry or a compartment membership | source overlays are labelled; the model-derived layers and MapLibre are named follow-ups |
| Two Codex review findings (skin initialization, report-name markup) | merged-review findings | fixed in #153 with browser and unit checks |

## 6. CI evidence

| Head | Conclusion |
| --- | --- |
| #151 `c9efec6` | green |
| #152 `8094638` | green |
| #153 `f98f096` | green |
| #154 `c04f481` | green |
| #155 `d949694` | green |
| #156 `54d2f14` | green |
| #157 `a41a17d` | green |
| #158 `8189c5a` | green |
| #159 `d439172` | green before and after merge |
| close-out head (this report) | dashboard and CI green |

## 7. Follow-ups not shipped

1. **Model-derived spread-compartment membership.** The source `COMPART` field gives a compartment
   base colour, but not the per-year spread-connectivity components the #13 account measures. A
   `spread_membership.csv` artifact and a `compartments` map layer are the follow-up.
2. **The run's used-road subset.** The source access overlay is not the route model's opened/used
   roads. A segment-geometry/use artifact would let the UI show the run's road set.
3. **MapLibre and a basemap** when polygon counts or raster layers need it.
4. **A stability stopping criterion** (stop after N iterations without improvement); the player
   presently offers iterations and time.
5. **Embedded assistant deployment guidance.** It is local-operator only; a shared deployment needs
   authentication and a deliberate decision about shell/filesystem access.

The follow-ups are also recorded in `notes/backlog.md`.

## 8. Next phase

No next phase is activated by this closeout. The recommendation is a small follow-up phase or backlog
entry for the model spatial layers and MapLibre, run alongside the thesis bridge work. Parent issue #146
should be closed after this report merges.

## 9. Decision

- [x] Approve as written (maintainer, 2026-10-20).
- [ ] Approve with changes (list them).
