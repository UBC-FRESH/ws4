==========================
Limitations and boundaries
==========================

Every model has edges. This page names WS4's, so a study is not built on a guess. Each entry says
what the boundary is, why, and what to do instead.

The model
---------

**Treatments move a stand through a matrix; they are not arbitrary actions.** A treatment applies to
a stratum, resets state variables, and moves the area to the resulting stratum's track. Effects a
treatment has *beyond* that transition — an unsupported ``succession`` or ``produce`` semantic — are
not modelled. If your model needs one, express it as a state the transition reaches, or keep it out
of the simulation.

**Growth and yield come from curves over an age grid.** Ages above the curve's maximum clamp to its
last value, matching linear interpolation. A curve that ends before your rotations do will silently
flatten, so extend the curves in the recipe instead.

**The expression library is finite.** Select statements are evaluated by WS4's own expression
evaluator, which implements the comparisons, the boolean and arithmetic operators, and the function
set listed in :doc:`../reference/forestmodelxml`. An expression it cannot parse falls back to a term
matcher that skips the terms it does not understand, so a compile is **best-effort** for a model that
uses an unsupported function. Check the compiled strata if a select looks wrong.

Space
-----

**A patch is what a criterion says it is.** Patch membership is a feature curve plus a threshold, so
"patch" is only as meaningful as the criterion you choose: a recent-opening criterion gives openings,
a seral-stage criterion gives bands of young forest. There is exactly one criterion per patch account;
a rule that depends on several cannot be expressed as a patch account.

**Adjacency comes from a topology file, and distance is real.** ``search_distance`` defaults to ``0``,
which joins only blocks whose polygons touch. The topology's distance column is the true gap, so
raising the threshold admits roads, creeks, and right-of-ways into patches. That is a modelling
choice, and the default keeps it out.

**Patch statistics are kept only at the years a target reads.** This is deliberate — it is what makes
a patch search affordable — and it means a patch target's period is a snapshot at its first year, not
an average over the period. A patch target on every period of a long horizon costs accordingly.

Roads
-----

**Routing is inside the objective, and most of it is incremental.** Haul, maintenance, and volume
route accounts are additive over blocks, so a move is priced by a route delta. Three things are not
additive and force a whole-schedule evaluation per step: a route account of kind ``build``, a
duplicate account, and any edge-contrast element. Keep those out while you tune the rest of a study
on a large estate.

**Destination choice is exclusive.** One destination per product per block, the least-haul-cost
reachable eligible one. A split between two mills is not expressible, and a product with no reachable
eligible destination is recorded as surplus.

Optimization
------------

**The search finds good schedules, not optimal ones.** The solvers are metaheuristics plus exact
per-move deltas. ``--mip-bound`` records a penalty **lower bound** for an option-selection relaxation,
and ``ws4 solve-mip`` solves that bounded model exactly for a small instance or subset. Neither is a
certificate of optimality for the full spatial problem: green-up, core area, patch distribution,
routes, and spread connectivity are outside the option model.

**Priority tiers are a large multiplier, not a lexicographic proof.** ``priority`` makes a
higher-priority tier dominate lower tiers in the scalar objective, but a sufficiently large
lower-tier penalty can still compete. The report keeps every raw and normalized target penalty
visible so a review can inspect that trade-off.

**Reproducibility is per configuration.** The same inputs, seed, and code path give the same result;
changing ``workers`` or ``islands`` is a different search.

Tooling and platform
--------------------

**Linux only, in practice.** WS4 is developed and measured on Linux. Nothing in the runtime is
platform-specific, but macOS and Windows are unverified, and the documentation build uses a symlink
in the repository layout.

**One host.** Parallelism is process-level on a single machine (worker processes, islands). There is
no distributed execution.

**No sample estate ships with the repository.** The examples use a small synthetic landscape so the
arithmetic stays checkable. Load your own model to see realistic behaviour.

**A weights file is not applied.** ``ws4 optimize`` accepts ``--weights`` for compatibility and does
not read it: the weights that apply are each target's ``min_weight`` and ``max_weight``. Applying a
per-account factor file is a capability nobody has asked for yet; the option is optional, so the
trap of a required no-op flag is gone. One settings gap remains tracked: ``threads`` is documented
but not applied.

Dataset provenance
------------------

**The compiled matrix does not know where its inventory came from.** A dataset may carry a
``data_quality.yaml`` provenance sidecar with inventory vintage, imputation share, coverage, curve
provenance, and THLB provenance. When the sidecar is absent, ``ws4 quality`` and the P26
``data_quality`` block report the field as **unknown**, not as a pass.

**The Great Bear Rainforest instances are not reviewed GBR yield tables.** Their natural curves use
VDYP, and their managed curves use BatchTIPSY 4.7 under predecessor-TSR assumptions. Their THLB is
predecessor-derived rather than a reviewed GBR netdown. Their imputation share and coverage are not
recorded in the source manifest. Treat the AAC as a model ceiling, not an operational guarantee.

**A schedule is not an operability, market, fire, or access guarantee.** The model prices the
targets and constraints it is given; it does not certify that a block can be harvested, sold, or
treated, or that a landscape will resist fire. State those assumptions in the study record.

Documentation
-------------

**No textbook section yet.** The reference pages explain mechanism, the how-to guides explain tasks,
and the notebooks show runs end to end, but WS4 does not yet ship a teaching text equivalent to the
conceptual material a new analyst may want alongside it.

What is tracked
---------------

The repository's ``notes/backlog.md`` is the live list of known gaps and deferred work, and
``notes/design/`` holds the measurements and decisions behind the boundaries above. When something
here changes, those notes change first.
