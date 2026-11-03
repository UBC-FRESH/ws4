# P108 profile-run report package

Date: 2026-11-03
Status: complete; PR #744

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

## Map geometry

The compiled dataset does not carry polygons; TSA 24 now supplies the source
`tsa24-blocks.geojson` layer documented in P115. Report generation is
independent of the map layer.

## Pull request

PR #744 contains the report writer integration, summary ending inventory, and docs.
