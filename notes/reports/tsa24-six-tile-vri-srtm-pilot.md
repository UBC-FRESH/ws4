# TSA24 six-tile VRI and SRTM pilot

This pilot fetches real VRI fuel/crown and SRTM terrain for six 30 km tiles spread across the
full TSA24 block extent. Each tile runs the same 240-minute FBP fire twice: once with real
layers and once with homogeneous C2 on flat terrain.

## Tiles

Bounds are EPSG:3005.

| Tile | minx | miny | maxx | maxy |
| --- | ---: | ---: | ---: | ---: |
| central-west | 1,156,607 | 991,274 | 1,186,607 | 1,021,274 |
| south-east | 1,242,227 | 941,971 | 1,272,227 | 971,971 |
| far-east | 1,333,475 | 981,150 | 1,363,475 | 1,011,150 |
| north-west | 1,080,960 | 1,081,070 | 1,110,960 | 1,111,070 |
| far-north | 988,590 | 1,172,639 | 1,018,590 | 1,202,639 |
| central-east | 1,233,204 | 1,013,247 | 1,263,204 | 1,043,247 |

| Tile | VRI features | Forest cells | Water cells | Wet cells |
| --- | ---: | ---: | ---: | ---: |
| central-west | 10,736 | 12,767 | 619 | 1,131 |
| south-east | 7,680 | 13,706 | 223 | 399 |
| far-east | 8,929 | 11,358 | 186 | 423 |
| north-west | 8,716 | 12,233 | 1,288 | 759 |
| far-north | 11,131 | 12,544 | 735 | 311 |
| central-east | 8,733 | 12,997 | 545 | 605 |

The VRI fetch split requests when a tile exceeded the 10,000-feature response cap.

## Fire comparison

All cases used FFMC 93.8, BUI 108.2, wind 6.8 km/h at 270 degrees, and 240 minutes. The
homogeneous case used C2 fuel and flat terrain with the same burnable and wet mask.

| Tile | Real burned | Homogeneous burned | Real head ROS |
| --- | ---: | ---: | ---: |
| central-west | 318.75 ha | 1,650.00 ha | 8.81 m/min |
| south-east | 1,287.50 ha | 1,331.25 ha | 11.12 m/min |
| far-east | 1,650.00 ha | 2,562.50 ha | 7.87 m/min |
| north-west | 187.50 ha | 1,418.75 ha | 9.80 m/min |
| far-north | 131.25 ha | 2,637.50 ha | 10.09 m/min |
| central-east | 1,043.75 ha | 1,225.00 ha | 10.19 m/min |

Real VRI/SRTM/water layers reduced burned area in every tile. The reduction ranged from
about 3% in the south-east to more than 90% in the far-north. Homogeneous C2 head ROS was
15.66 m/min in every tile, while real head ROS ranged from 7.87 to 11.12 m/min.

The fuel mixes are not homogeneous: the tiles contain C1, C2, C3, C4, C7, D1, M1, M2, M3, and
M4, with the mix changing substantially by tile. Wet edges and terrain also differ.

## Boundary

Each tile has one 240-minute fire, one hot weather state, and no suppression or spotting.
Missing crown-closure values are treated as zero, and stands whose species cannot be mapped are
skipped. The six tiles are a spatial pilot, not the full 5.9 M ha fire regime.
