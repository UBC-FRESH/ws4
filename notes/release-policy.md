# Release and patch policy (P5.5)

The release policy defines the version scheme, the cadence, and how fixes ship. It is consistent with
`CITATION.cff`, `RELEASE_NOTES.md`, and the release close-out reports.

## Version scheme

The Python package uses **semantic versioning** (`MAJOR.MINOR.PATCH`).

- While the project is pre-1.0 (`0.y.z`), a breaking change to the compiled-dataset contract, the
  recipe handling, or a public API bumps `y`; everything else is a patch (`z`).
- A change to the compiled-dataset schema version (`ws4/model/schema.py`) is a contract change and
  needs an ADR and a minor bump.
- The version lives in `pyproject.toml` and `ws4/__init__.py` and is mirrored in `CITATION.cff`.

## Cadence

- A **feature release** is tagged at the end of a build phase, as part of the phase close-out (the
  pattern used for `v0.1.0` from P4).
- **Patch releases** are cut on a needs basis from `main` when a fix should ship without waiting for
  the next feature phase.

## How a fix ships

1. The fix lands on a phase branch (`feature/p<n>-<slug>`) or, between phases, a short-lived
   `fix/<slug>` branch off `main`, with the dashboard green and CI green.
2. Merge to `main`; the merge is the evidence head. The `Docs` workflow deploys from `main`.
3. Tag `vX.Y.Z`, push the tag, and publish the GitHub release with the sdist and the wheel, built from
   a clean checkout of the tag (the commands are in `notes/reports/p4-closeout.md`).
4. Install the published artifact into a fresh environment and run the acceptance checks; confirm
   reproducibility.

## Artifacts and hosting

- Artifacts attach to the GitHub release (`ws4-<version>.tar.gz`, `ws4-<version>-py3-none-any.whl`).
- Publishing to PyPI is out of scope until an external account is approved; it would be a separate
  decision with its own credentials.

## Support

The latest release and `main` are supported. Back-ports to older releases are not planned until the
project ships a `1.0` and a maintenance window is defined.
