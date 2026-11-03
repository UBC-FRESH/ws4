# P108 profile-run report package

Date: 2026-11-03
Status: complete

## Change

After the profile-run simulator replay, the worker now calls the standard report writer:

- `report_accounts.csv`
- `report_targets.csv`
- `ending_inventory.csv`
- any DHI/structure/resilience reports available in the dataset

The exact summary also carries the ending-inventory offset and account values.

## Smoke

Base profile, population 8, zero generations, replay enabled:

- exact replay: **true**
- report files written
- ending inventory accounts: 78
- wall: 108.5 s

## Limit

The run still has no map geometry because the TSA24 compiled dataset has no
`--geometry` layer; this is a data/configuration gap, not a report bug.
