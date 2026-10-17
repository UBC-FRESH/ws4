# The sample estate

A small, self-contained estate for the how-to guides and the notebooks: 64 blocks on an 8 x 8 grid,
one clearcut treatment that can be applied more than once (so a rotation is possible), a seral feature
that marks fresh openings, and a road network with two mills.

It is deliberately small enough to compile, simulate and search in seconds, and rich enough to use
every part of the model: volume targets, patch size distributions, routing to more than one
destination, and multi-rotation schedules.

## The files

| File | What it holds |
| --- | --- |
| `recipe.xml` | The model: two lanes (`natural` and `regen`), one clearcut treatment operable from age 40, the volume curves, a seral curve that is 1 while an opening is under 40 years old, and the product a cut produces. |
| `fragments.csv` | 64 blocks, 8-12 ha each, ages 0-100, all starting in the natural lane. |
| `topology.csv` | The grid adjacency (4-neighbour, distance 0), which is what makes patches of adjacent openings possible. |
| `vertices.csv`, `segments.csv`, `destinations.csv`, `linkages.csv` | The road network: one access vertex per grid row, a road along them, and two mills — `destination.MILL1` at the west end and `destination.MILL2` at the east end, so the least-haul-cost destination differs across the estate. |
| `eligibility.csv` | Both mills accept the product. |
| `route.yaml` | The route configuration: the four tables, the eligibility table, the route accounts (haul and volume per mill, and a total haul), and the duplicate accounts that build the total. |
| `patches.yaml` | A patch account over fresh openings, with size classes 0-10, 10-50, 50-150, 150-400 and 400+ ha. |

## What it is for

```bash
ws4 build --xml examples/estate/recipe.xml --fragments examples/estate/fragments.csv --out tmp/estate/compiled
ws4 validate --dataset tmp/estate/compiled

# simulate a schedule, with the spatial metrics and the route accounts
ws4 simulate --dataset tmp/estate/compiled --schedule tmp/estate/schedule.csv --years 60 \
             --topology examples/estate/topology.csv \
             --route-config examples/estate/route.yaml --out tmp/estate/run

# search with a patch size-distribution target and the shape-aware operators
ws4 optimize --dataset tmp/estate/compiled --targets tmp/estate/targets.yaml --years 100 \
             --iterations 20000 --topology examples/estate/topology.csv \
             --patch-accounts examples/estate/patches.yaml \
             --merge-weight 0.5 --split-weight 0.2 --cluster-weight 0.3 \
             --threads 1 --out tmp/estate/patch-run
```

`fragments.csv` is the only file you are expected to edit to make your own variation: change the ages
and the areas and everything else still applies. A schedule is a CSV of `block_id`, `treatment`,
`period`, for example `1,CC,0` to clearcut block 1 at year 0.

Guides that use this estate: `docs/howto/route-products.rst` and `docs/howto/patch-targets.rst`.

One thing to know if you target patch size classes in a search: the search's own view of the patch
accounts can differ from a simulation of the same schedule. The report at the end of a run is what to
trust, and a correction is queued. Simulating the schedule and reading `patch_metrics.csv` is the way
to see the openings themselves.
