BC VRI treatment prescription
=============================

Purpose
-------

``ws4.fire.prescription`` applies an explicit stand treatment to an open BC VRI stand and maps
the before/after FBP fuel assignment.

Contract
--------

The caller must supply:

- the treatment name;
- the post-treatment FBP fuel type;
- the declared canopy-cover, live-basal-area, and surface-fuel changes;
- the evidence source.

The helper ``prescription_from_ffs`` supplies the open FFS median deltas but still requires the
caller to choose the post-treatment FBP fuel type.

Worked preview
--------------

The MKRF VRI AOI has three complete stands. A thin-burn prescription with explicit ``C2``
changes canopy closure from 70/60/55% to 53.97/46.26/42.41%. The VRI→FBP mapper assigns C2
before and after; its rules do not use basal area or surface fuel and are insensitive to
closure above the sparse-cover threshold.

Decision
--------

**Go** for the explicit prescription contract.

**No-go** for automatic fuel-type conversion or a fire-effect claim. The FBP conversion remains
an expert input, and the closed BC CRI layer is excluded.

Report: ``notes/reports/vri-treatment-preview.md``.
