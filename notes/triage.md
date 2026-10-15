# Issue triage (P5.2)

Triage keeps the issue tracker useful: every open issue has a type, an area, and a priority, and
nothing sits unlabelled. Triage rides the review cadence (`notes/review-cadence.md`).

## Labels

**Type** (exactly one):

- `bug` — something is broken.
- `enhancement` — a new capability.
- `documentation` — docs only.
- `performance` — speed, scale, or resource use.
- `security` — a security or dependency advisory.
- `chore` — routine maintenance.

**Area** (one or more):

- `area: builder`, `area: simulator`, `area: optimizer`, `area: spatial`, `area: roads`,
  `area: docs`, `area: performance`, `area: tooling`.

**Priority** (exactly one for anything that will be worked):

- `priority: high` — do next.
- `priority: medium` — schedule soon.
- `priority: low` — nice to have.

**Workflow:**

- `phase` — a roadmap phase parent issue.
- `task` — a roadmap task child issue.
- `good first issue`, `help wanted` — newcomer-friendly markers.

## Routing rules

- A new issue gets a type and an area within one cadence; a priority when it is accepted for work.
- Security advisories and broken releases are triaged out of cadence (see the review cadence).
- A gap discovered during work is recorded in `notes/backlog.md` with a target phase, and, if it is a
  sizeable effort, an issue.
- Ideas that are out of scope are closed with a short reason and kept searchable (not deleted).

## Cadence

Weekly triage on the same day as the monthly review (monthly when the queue is short). The triager is
the maintainer. The output of a triage pass is: every open issue labelled, priorities set, and stale
issues either scheduled or closed with a reason.
