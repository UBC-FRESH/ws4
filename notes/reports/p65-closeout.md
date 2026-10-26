# Phase close-out report: P65 Editable target charts

Phase: P65, Editable target charts
Parent issue: #464
Pull request: #469
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P65 pull request and delete `feature/p65-editable-targets`.
2. Close tasks #465/#466/#467 and parent #464.
3. Keep direct drag-editing of weights/priority out; the table remains that editor.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Activate/deactivate an account from its chart. | First c5 chart toggled inactive, saved, reloaded; the inactive card remains. | Met |
| Set one period minimum/maximum by exact input. | c5 min set to 1,234.5; save/reload readout and table show 1,234.5. | Met |
| Set one period by dragging. | Dragging P3 of the product chart set min to 3,749.4 and marked the chart dirty. | Met |
| Apply one value to all periods. | c5 min 3,000 applied to all 5 periods; API returned five bounded rows; save persisted. | Met |
| Create missing period rows and clear a bound. | A period without a row gained one at the correct period/year; clear leaves an indicator. | Met |
| Save updates targets, chart, and table. | POST/GET round trip; target table minimum input and readout both show the saved value. | Met |
| Live convergence remains. | P64's live SSE path is unchanged; achieved series updates while charts are editable. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Evidence

c5:

- first chart product target: min 1,234.5 saved and reloaded;
- all-period min 3,000 created rows for P1-P5;
- drag on P3 set min 3,749.4;
- inactive toggle saved all rows for the account inactive.

TSA 46:

- 10-period product target edited at P2 to min 8,030,500; save/reload readout shows
  `min 8,030,500 · max 8,031,000`;
- active toggle saved and reloaded an inactive card.

The check is `scripts/check_target_editing.py`; it is opt-in and destructive to the service's
temporary targets file. It exits 0 on c5 and TSA 46.

## Deviations and limits

- Weights, normalization, priority, and notes remain table-only; dragging them is deferred.
- "All periods" is a scope selector, not a separate confirmation dialog; the button label and
  scope are explicit and the save step still validates the resulting rows.
- Flow targets use the same account-period chart editing; a dedicated flow-window editor is
  deferred.
- No phone support.
