# Dependency and security maintenance (P5.3)

Dependencies are kept current on a cadence, and security advisories are handled out of cadence.

## Automated updates

`.github/dependabot.yml` opens weekly pull requests for:

- the **pip** ecosystem (the runtime and dev dependencies in `pyproject.toml` and
  `requirements-dev.txt`), labelled `chore` and `priority: medium`;
- **github-actions** (the workflow actions), labelled `chore` and `area: tooling`.

## Review cadence

- Update pull requests are reviewed at the weekly triage (see `notes/triage.md`), and merged when the
  dashboard and CI are green. A major-version bump that changes behavior is scheduled, not merged
  blindly.
- The dev toolchain (`ruff`, `mypy`, `pytest`, `sphinx`) is part of the same flow.
- A failing dependency update is investigated, not ignored; if it cannot be fixed promptly, it is
  pinned to the last good version with a note in `notes/backlog.md`.

## Security advisories

- A `security` advisory (a Dependabot alert or an external report) is triaged **out of cadence**.
- A fix is a `priority: high` patch: a small change on a `feature/p<n>` branch or, between phases, a
  patch release per `notes/release-policy.md`.
- The triage records the advisory, the affected versions, the fix, and the release it ships in.

## Supported versions

The latest release and `main` are supported. There is no back-porting to older releases until the
release policy says otherwise (`notes/release-policy.md`).
