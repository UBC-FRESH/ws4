# P147 diverse multi-account scaffold

Date: 2026-11-07
Status: active
Branch: `feature/p147-diverse-scaffold`
Parent issue: #865
Task issue: #866

## Summary

The first live five-account scan selected the first alphabetical area subaccounts. They
were nested and highly collinear, producing one exact front point.

The scaffold now has a **Diverse 6** preset:

- prefers representative aggregate accounts;
- includes harvest, growing stock, old-growth aggregate, and species mix when present;
- avoids direct nested accounts and families with more than two selected members;
- warns visibly when the current selection is nested or family-heavy;
- falls back to existing target minima for product accounts without account-series
  values.

## Verification

- Browser scaffold tests pass.
- Live TSA27 diverse run pending.
