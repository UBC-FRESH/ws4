========================
The simulation
========================

WS4 simulates **one year at a time, always**. Growth, treatments, and road events are all annual, and
the step is not configurable. That single decision explains much of the tool's behaviour.

Each year, for each fragment: its age advances, its track follows its growth curve to the new age, and
any treatment the schedule places in that year is applied — which may move the fragment to another
stratum, and so onto another track, and may produce products along the way.

Growth and yield are curves over an age grid rather than formulas. A curve says what a stratum
produces at each age, and the simulator evaluates it by looking the age up, which is why a simulation
of a large estate is fast and why the curves must cover the ages your rotations reach: an age past the
end of a curve clamps to its last value.

Treatments are the only way the state changes besides growing. A treatment's age window decides when
it is *operable*, and the optimizer builds its candidate chains from exactly those operabilities — so a
window that excludes your stand ages leaves the search with nothing to choose, and a window that admits
a wide range of ages gives it a lot.

Because the step is a year and the schedule is keyed by offset, a schedule is a list of `(block,
treatment, offset)` decisions, and it is what the optimizer searches over. Offset 0 is the first
simulation year. Everything else — the account values, the patch map, the road costs — is a *view* of
the state that the simulation produces, recorded at offsets from -1 (the pre-simulation snapshot)
through ``years - 1``.

Where to read more: :doc:`../reference/simulator` for the engine and its outputs, and
:doc:`the-model` for the vocabulary above.
