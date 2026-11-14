# WS4 drop-depth and dispatch contract

Status: design contract only. No code in P207.

## Purpose

Define the boundary between the FBP benchmark kernel and a proper water/retardant suppression
layer. P203–P206 demonstrated explicit closure, rain stopping, construction rate and temporary wet
cells. They did not model drop depth, coverage, decay, tanker payload, refill or dispatch.

## Drop event

One drop is a time-stamped footprint:

```text
DropEvent
  id
  suppressant          water | retardant
  center_x, center_y   projected CRS metres
  length_m, width_m    effective contour axes
  orientation_deg      clockwise from north
  volume_l             delivered volume
  coverage_l_m2        nominal application rate
  start_min, end_min   release interval
  decay_min            effective hold/decay duration
  canopy_penetration   0..1
  source_id
```

Units are SI except hectares for area and minutes for time. The CRS must match the fire grid.
Defaults must be explicit; no silent unit conversion.

## Rasterized wetness

The drop footprint is rasterized to the fire grid as a coverage fraction per cell. Cell mean depth:

```text
depth_mm = coverage_fraction * nominal_depth_mm * canopy_penetration * decay(time)
```

The required suppression depth is a parameter (default 0.75 mm for the diagnostic). A cell is
suppressed while its combined depth from all drops is at or above the threshold.

Overlaps are additive in depth, capped only for display. Re-wetting resets or adds depth according
to the event schedule. The model must report per-cell depth at fire arrival.

## Effect model

Initial integration is a threshold: a suppressed target does not ignite while depth is above the
threshold. A later pilot may test a bounded ROS factor, but that is a separate hypothesis.
No global FBP multiplier is allowed.

## Dispatch contract

```text
SuppressionResource
  id, kind              tanker | helicopter | crew
  payload_l             for aircraft
  cycle_min             scoop/load, transit, drop, return
  water_source_id
  available_start_min, available_end_min

WaterSource
  id, x, y, capacity_l, refill_l_min

DispatchTask
  resource_id, drop_event_id, start_min, end_min
```

The dispatch layer must expose queue wait, refill, travel, payload and failure states. It must not
change the fire kernel unless a drop event is delivered.

## Integration boundary

- `GrowthConfig` may receive a time-dependent wetness field or drop schedule.
- Free-burn default is unchanged.
- Target and intermediate-cell checks use the wetness at arrival.
- The kernel must not be tuned to an observed perimeter.
- Drop and dispatch artifacts must be reproducible and public-data only.

## Evidence

- Wheatley 2024: ROS reduction, intensity reduction and hold ranges.
- McFayden et al. 2023: drop-depth contours, stacking and breach criteria.
- Van Wagner & Taylor 2022: theoretical water depth.
- Existing P179/P182 artifacts remain the evidence-bounded implementation.

## Pilot go/no-go

A pilot is worth running only if:

1. drop geometry and volume produce a documented cell-depth field;
2. the wetness interval is consistent with the evidence range;
3. the dispatch schedule is explicit and reproducible;
4. the treatment can fail or be bypassed;
5. final area is not the only endpoint.

## Non-goals

- operational tanker dispatch;
- field-validated suppression prediction;
- tuning FBP parameters;
- replacing the FBP benchmark path.
