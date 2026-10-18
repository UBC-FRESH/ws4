========================
The accounting
========================

Two clocks run at once in WS4, and confusing them is the most common source of surprise.

The **simulation clock** is the year. Treatments happen in years; growth happens in years; the state of
the forest is defined for every year.

The **accounting clock** is the period: a whole number of years, five or ten in practice. Targets are
stated against periods, because forest policy is written that way — "at least 800 000 cubic metres a
decade" — and because a per-year target on a stand-level model is usually noise.

A target names the year its period **ends** on and the period's length (`period_width`), so
`year: 10, period_width: 10` is the first decade, covering years 1 to 10. This is the reference
implementation's convention, and the acceptance comparison checks WS4's periods against its own. The
value of an accumulating account — a ``product.`` account, something produced during the period — is
the sum of its years; a target's bounds apply to that sum. Everything else is a *level* and is read at
the period's end year, because a state of the map does not accumulate: a `year: 10, period_width: 10`
target on a feature is the feature at year 10, not ten years of it added together.

**Period 0 is special.** It is not an accounting period at all: it is the instantaneous state of the
forest *before* the simulation starts, and it exists so a schedule can refer to the state it begins
from. The accounting periods are numbered from 1; when a table says `period 1`, that is the first
decade of the run.

Not every account is additive, and that is where the accounting gets interesting. A patch account is a
snapshot of the map — how the openings are arranged in one year — so a patch target is read at the
**end year of its period** rather than summed across it. A flow target aggregates whole periods
instead. Both are described in :doc:`the-objective`.

Where to read more: :doc:`../reference/optimizer` for how periods enter the objective, and
:doc:`../howto/write-targets` for the practical consequences.
