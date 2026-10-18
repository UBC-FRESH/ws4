========================
The model
========================

A forest estate model answers questions about a whole estate over time: which stands to cut, when, and
what that leaves behind. WS4 represents the estate as four kinds of thing, and it is worth knowing
which is which because the command line and the API both speak in their names.

The decision unit is the **fragment**: a piece of land that behaves the same way — the same species,
the same site, the same age. Fragments are what get compiled, and there are usually many of them.

A **block** is an operational grouping: the thing a forester actually treats, made of one or more
fragments. WS4 keeps blocks as a runtime view rather than a compiled fact, so one compiled dataset can
serve several block layouts, and so a schedule can name blocks while the growth is computed on
fragments.

A **stratum** is a state: the combination of the values that decide how the land grows. If a model
tracks species and management status, then "conifer, unmanaged" and "conifer, managed" are two strata.
Each fragment sits in exactly one stratum at any moment.

A **track** is a trajectory through those states: what happens to a stratum as the decades pass with no
intervention. Growth and yield curves hang off tracks, because what a stand produces depends on where
it is in its succession.

A **treatment** is an intervention. It has a label, an age window in which it is operable, and a
*transition*: the state it moves the treated area to. A clearcut that moves "unmanaged" to "managed" is
a treatment; so is a thinning that leaves the state alone but resets the age.

Put together: fragments compile into strata and tracks; a schedule assigns treatments to blocks in
years; the simulator moves land between strata as the treatments and the growth curves dictate. A
**rotation** is simply a block being treated more than once, and WS4's candidate chains include
rotations because a treatment whose transition returns the strand to a treatable state can be applied
again.

Where to read more: :doc:`../reference/compiled-dataset` for the compiled tables, and
:doc:`../reference/forestmodelxml` for how a model is described in a recipe.
