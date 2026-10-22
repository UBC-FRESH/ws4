===============
Troubleshooting
===============

Symptom first. Each entry says what it usually means and what to do; the how-to guides carry the
detail.

Installation
------------

**``ModuleNotFoundError: geopandas`` when building from a shapefile.**
Install the ``geo`` extra: ``python -m pip install -e ".[geo]"``. CSV and Parquet inventories need
nothing extra, so this is worth avoiding if you can.

**``ws4`` not found after installing.**
The editable install places the console script beside the interpreter it was installed into. Confirm
you are in the same environment (``python -c "import ws4; print(ws4.__file__)"``), or run the module
directly (``python -m ws4.cli --help``).

**The mixed-integer bound complains about ``scipy``.**
``ws4 optimize --mip-bound`` needs the ``opt`` extra: ``python -m pip install -e ".[opt]"``.

Building a dataset
------------------

**``validate`` reports a table or a column.**
The dataset is a contract and is checked on the way in. Fix the recipe or the inventory and recompile
rather than editing Parquet: the manifest records the inputs' digests, and downstream commands trust
it.

**Blocks or fragments are missing from the simulation.**
Look at ``fragments.parquet``: an age outside the curves' domain, a zero area, or a block id that
appears in no topology row are the usual causes. ``ws4 validate`` names them.

**Nothing is operable.**
Check ``treatments.parquet``. ``begin`` and ``end`` come from the recipe's ``minage`` and ``maxage``,
and ``end`` of zero or less means no upper bound. If the age windows exclude your stands, the search
has nothing to choose.

Simulating
----------

**A simulation is fast but the accounts are flat.**
Check the schedule's ``offset`` column: it is the number of years after the start of the simulation
(offset 0 is the first simulation year), not an accounting-period index. A schedule written in period
indices treats the wrong offsets, and a ``period`` column is rejected outright.

**The treatment was applied but no product appeared.**
The product belongs to the stratum the treatment moves the fragment **to**, so a treatment whose
transition assigns no new track produces on the track it left. Check the recipe's ``transition``
assigns.

Optimizing
----------

**The objective is zero but the answer is wrong.**
``0.0`` means every target is met. An unconstrained year or account is therefore free, and the search
will spend it arbitrarily. Add the targets you actually care about
(:doc:`../howto/write-targets`).

**The search barely moves from its starting point.**
Weights are unbalanced: one term is so expensive that every move is worse. Run ``ws4 calibrate``, or
lower that term's weight, or switch ``shape`` to ``linear`` for a term that should be a soft pull.

**A target is always ``below``.**
Test it alone. If it is still below, the estate cannot deliver it in those years: loosen the floor,
move it to a later period, or extend the horizon.

**The run takes far longer than the horizon suggests.**
A patch target keeps one patch state per targeted period; a route **build** account, a duplicate
account, or an edge-contrast element makes every evaluation a whole-schedule pass. Narrow the
windows, keep those out while tuning, or use ``--time-limit`` deliberately rather than as a safety
net.

**A run is not reproducible.**
Pin the whole configuration: seed, horizon, targets file, weights, topology, patch accounts, and the
parallel settings. A different ``workers`` or ``islands`` value is a different search.

Watching
--------

**The live view shows nothing.**
It needs a terminal; piping to a file buffers until exit. Use ``--plain`` for a single frame.

**An account has no window.**
The name does not match a target. Account names are exact and case-sensitive.

Patch targets
-------------

**``KeyError`` on a ``patch.*`` account.**
The class label comes from ``size_classes``; bounds ``10, 50, 150`` produce ``0_10``, ``10_50``,
``50_150``. A label you never defined cannot be targeted.

**Every patch is one block.**
``search_distance`` defaults to ``0``, which joins only blocks whose polygons touch. Raise it if your
topology's blocks are separated by real gaps you want treated as touching.

Routing
-------

**Everything is surplus, or haul cost is zero.**
No eligible destination is reachable from the block's linkage vertex. Check the eligibility table and
the linkages file.

**Build cost appears in one period only.**
That is the model: build once, maintain while used.

Getting help
------------

If the symptom is not here, the reference page for the subsystem is the next stop
(:doc:`../reference/index`), and the repository's ``notes/`` directory records the measurements and
the decisions behind the behaviour. For a bug, the issue tracker; include the ``summary.json``, the
``report_targets.csv``, and the command line you ran.
