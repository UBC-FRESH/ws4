Containment boundary and validation protocol
============================================

Containment contract
--------------------

The observed-fire runner accepts an optional boolean containment mask:

- ``False`` cells are normal fuel.
- ``True`` cells are contained/non-burnable, such as a firebreak or suppression line.
- The default is ``None``, preserving free-burn behavior.
- The mask must match the grid and leave burnable cells.

The mask is a **management scenario input**, not a fitted calibration parameter.

Validation protocol
-------------------

P176 showed that the model fills the connected burnable basin:

- median simulated area / basin: 0.995;
- median observed area / basin: 0.130;
- 8 of 12 simulations fill at least 95% of the basin.

Therefore:

- use **large/free-burn fires** for ROS and event skill;
- use **small/suppressed fires** only for potential-growth or containment scenarios;
- do not tune ROS to suppressed small fires.

P164.3 calibration remains paused until the protocol is applied to free-burn evidence.
