# ADR 0013: The SDMD layer is diagnostic and a constraint source

Status: accepted
Date: 2026-11-01
Issues: #628, #629

## Context

WS4 can compile an estate, grow it with FVS-BC, and optimise a schedule against
targets, but an analyst cannot yet ask a density question: what stand density
does an AU's evidence support, where do the observed plots sit, where does a
regime path cross the diagram, and which treatment sequences are therefore
plausible? The published stand density management diagram (SDMD) tradition
answers the first three questions visually for even-aged stands. It does not
supply a growth model, and it does not describe selection systems.

The project needs a boundary before it adds data, charts, or solver rules. The
risks are that a diagram becomes an oracle, that digitisation error is hidden,
that canopy-only LiDAR is mistaken for total density, or that the optimizer
silently drops a prescription it should keep.

## Decision

Add a stand density management layer, `ws4.sdmd`, whose job is diagnosis and
constraint generation. It defines six tables: plots, tree lists, stand
summaries, SDMD points, regimes, and AU constraints. Each row carries a source
and a review status. The schema is the stable contract; ingestion, compilation,
the API, the web tab, and the solver read it.

Store a diagram as ordered vector isopleths with metadata, never as a raster
alone. Record the diagram's species group, region, source, version, and the
reviewer who accepted the digitisation. A point outside the observed or
digitised envelope is flagged, not accepted silently. The diagram applies to
even-aged, healthy, untreated development; selection regimes are marked as
outside it.

The solver may choose only regimes that an AU constraint allows, and must
respect the entry-age window, the maximum entries, the minimum interval, the
removal fraction, and the required SDMD zone. The solver reports the option
space before and after filtering so the reduction is measurable.

## Consequences

- The layer cannot become a second growth model. FVS-BC and PSP remain the
  growth evidence.
- Ingestion must label synthetic gap-fill rows and must refuse canopy-only LiDAR
  as total TPH, because the schema requires provenance.
- A diagram cannot be used in a report until a named reviewer — normally the
  maintainer, or an RPF the maintainer designates — has accepted the digitisation.
  The review status and the reviewer are first-class fields.
- Uneven-aged regimes need a different diagram or a different account; they are
  out of scope rather than forced onto an even-aged diagram.
- The optimizer gains a smaller, better-posed option space, but the acceptance
  test is a measured reduction with no loss of allowed prescriptions.
- The provincial atlas remains out of scope. One region and a small AU set come
  first, and unsupported AUs are reported rather than filled.

## Alternatives considered

- **A raster diagram.** Rejected: a raster cannot be interrogated, cannot carry
  an envelope, and hides digitisation error.
- **A new growth model.** Rejected: the project already has FVS-BC, PSP, and a
  compiled dataset; a second model would create a competing truth.
- **Calibrating the diagram to AFRF immediately.** Rejected: the pilot AU set
  does not have enough plots for a defensible calibration. The gap is recorded.
- **Letting the optimizer infer constraints from the diagram.** Rejected: an
  explicit, reviewable AU constraint table is auditable; an inferred rule is
  not.
- **Treating selection regimes as valid SDMD paths.** Rejected: the diagram's
  assumptions do not hold for uneven-aged stands, so the layer flags them.
