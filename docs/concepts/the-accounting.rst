========================
The accounting
========================

Two clocks run at once in WS4, and confusing them is the most common source of surprise.

The **simulation clock** is the year. Treatments happen in years; growth happens in years; the state of
the forest is defined for every year.

The **accounting clock** is the period: a whole number of years, five or ten in practice. Targets are
stated against periods, because forest policy is written that way — "at least 800 000 cubic metres a
decade" — and because a per-year target on a stand-level model is usually noise.

A target names the first year of its period and the period's length (`period_width`), so
`year: 0, period_width: 10` is the first decade, covering years 0 to 9. The account value for an
additive account is the sum of its years; a target's bounds apply to that sum.

**Period 0 is special.** It is not an accounting period at all: it is the instantaneous state of the
forest *before* the simulation starts, and it exists so a schedule can refer to the state it begins
from. The accounting periods are numbered from 1; when a table says `period 1`, that is the first
decade of the run.

Not every account is additive, and that is where the accounting gets interesting. A patch account is a
snapshot of the map — how the openings are arranged in one year — so a patch target is read at the
**first year of its period** rather than summed across it. A flow target aggregates whole periods
instead. Both are described in :doc:`the-objective`.

Where to read more: :doc:`../reference/optimizer` for how periods enter the objective, and
:doc:`../howto/write-targets` for the practical consequences.
