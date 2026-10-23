# Synthetic landscape for the WS4 prototype.

Two fragments on two blocks, both on the natural track:

- fragment 1: block 1, 3.0 ha, age 40
- fragment 2: block 2, 2.0 ha, age 60

`recipe.xml` defines the natural track (curve 1) and the managed track (curve 2),
one clearcut treatment (`CC`) that moves a fragment from the natural track to the
managed track, a `feature.Volume` feature on the natural track, and a
`product.Volume` product.

Expected `feature.Volume` with no schedule. Offset 0 is the first simulation year, and the
simulator also records the pre-simulation snapshot at offset -1:

- offset -1 (snapshot): 3.0 * curve1(40) + 2.0 * curve1(60) = 3.0 * 120 + 2.0 * 170 = 700.0
- offset 0: 3.0 * curve1(40) + 2.0 * curve1(60) = 3.0 * 120 + 2.0 * 170 = 700.0
- offset 1: 3.0 * curve1(41) + 2.0 * curve1(61) = 3.0 * 122.5 + 2.0 * 172.5 = 712.5

With `CC` on block 1 at offset 0, fragment 1 moves to the managed track, so the
natural-track `feature.Volume` at offset 0 is 2.0 * curve1(60) = 340.0.
