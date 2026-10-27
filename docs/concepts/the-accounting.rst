========================
The accounting
========================

Two clocks run at once in WS4, and confusing them is the most common source of surprise.

The **simulation clock** is the *offset*: the number of years after the start of the simulation.
Offset 0 is the first simulation year, offset 1 the second, and so on. A schedule is keyed by offset,
not by period: a treatment written ``block_id,treatment,offset`` with ``offset 0`` happens in the
first simulation year.

The **accounting clock** is the period: a whole number of years, five or ten in practice. Targets are
stated against periods, because forest policy is written that way — "at least 800 000 cubic metres a
decade" — and because a per-year target on a stand-level model is usually noise.

A target names its period and the period's length (`period_width`). Period ``p >= 1`` covers the
offsets ``(p - 1) * period_width`` through ``p * period_width - 1``, so a target at ``period: 1`` with
``period_width: 10`` reads offsets 0 to 9. The **year** is a display label only: it is ``offset + 1``,
so that same period displays as the decade ending in year 10. The acceptance comparison checks WS4's
periods against the reference's own. The value of an accumulating account — a ``product.`` account,
something produced during the period — is the sum of its offsets; a target's bounds apply to that sum.
Everything else is a *level* and is read at the period's end offset, because a state of the map does
not accumulate: a feature target on a ten-year period is the feature at the period's last offset, not
ten years of it added together.

**Period 0 is special.** It is not an accounting period at all: it is the instantaneous state of the
forest *before* the simulation starts, and it is the zero-length period at offset ``-1``. The
simulator records a snapshot there, before any treatment is applied, so a schedule can refer to the
state it begins from. The accounting periods are numbered from 1; when a table says ``period 1``, that
is the first decade of the run, covering offsets 0 to 9.

Not every account is additive, and that is where the accounting gets interesting. A patch account is a
snapshot of the map — how the openings are arranged in one offset — so a patch target is read at the
**end offset of its period** rather than summed across it. A flow target aggregates whole periods
instead. Both are described in :doc:`the-objective`.

Carbon accounts follow the same clock. Ecosystem pools are levels; HWP decay and system emissions are
per-period flows; the system stock adds product pools to the ecosystem level. The HWP lifecycle is a
sidecar account layer, not a dataset column; see :doc:`../reference/carbon`.

Where to read more: :doc:`../reference/optimizer` for how periods enter the objective, and
:doc:`../howto/write-targets` for the practical consequences.
