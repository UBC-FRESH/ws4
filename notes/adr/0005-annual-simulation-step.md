# ADR 0005: The simulator steps annually; periods are reporting intervals

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

Planning is usually expressed in periods (often five or ten years), while growth, treatments, and
spatial constraints (green-up, adjacency) act on an annual scale. A model that simulates at period
resolution hides within-period ordering and cannot represent annual constraints. A model that only
simulates annually loses the period framing analysts use for targets and reports.

## Decision

Step the simulator one year at a time. Periods are a reporting and target interval defined over the
annual timeline, with either fixed or variable widths. Treatments scheduled in a period are placed in a
year within it (by policy), and spatial constraints are evaluated on the annual sequence.

## Consequences

- Annual constraints (green-up, adjacency timing) are representable.
- Within-period treatment ordering becomes an explicit decision rather than an accident of aggregation.
- The annual loop runs more steps, so performance work matters.
- Reporting aggregates annual state back to periods, which must be well defined for flows and stocks.

## Alternatives considered

- **Simulate at period resolution only.** Rejected: cannot express annual spatial constraints, and
  hides ordering effects.
- **Simulate annually but report only annuals.** Rejected: analysts set and read targets by period.
