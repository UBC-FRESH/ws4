VRI to FBP fuel-type mapping
============================

Purpose
-------

VRI attributes describe a stand; they are not a fuel model. ``ws4.fire.vri`` maps a
VRI-style description to a Canadian FBP fuel type and records why. The mapping is a
deterministic WS4 modelling decision, not a measurement, and every assignment carries its
rule, version, source fields, and confidence.

Input contract
--------------

``VriStand`` carries:

- ``stand_id``;
- ``leading_species`` as a BC species code or common name, such as ``Pl`` or
  ``Lodgepole pine``;
- ``conifer_fraction`` and ``deciduous_fraction`` in [0, 1];
- ``crown_closure_percent`` in [0, 100];
- optional ``age_years`` and ``height_m``;
- ``land_cover`` (default ``forest``);
- optional explicit ``fuel_type``;
- optional ``treatment`` such as ``slash`` or ``matted grass``.

Species aliases are normalized to two-letter codes. A slash-separated label such as
``Pl/Sx`` uses the first code. An unknown species raises rather than guessing.

Rule order
----------

The rules are applied in this order. The first match wins.

.. list-table::
   :header-rows: 1

   * - Rule id
     - Condition
     - FBP type
   * - ``explicit-fbp``
     - The stand carries an explicit FBP fuel type.
     - That type.
   * - ``explicit-non-fuel``
     - The explicit type is ``NF`` or ``WA``.
     - None.
   * - ``land-cover-non-fuel``
     - Land cover is non-forest, water, urban, rock, or ice.
     - None.
   * - ``wetland-conifer`` / ``wetland-non-fuel``
     - Wetland with at least 50 percent conifer / otherwise.
     - ``C2`` / None.
   * - ``land-cover-slash``
     - Land cover is slash.
     - ``S2``.
   * - ``land-cover-grass-matted`` / ``land-cover-grass-standing``
     - Grass, shrub, or agriculture, with or without a matted treatment.
     - ``O1A`` / ``O1B``.
   * - ``treatment-slash``
     - A forest stand carries a slash treatment.
     - ``S2``.
   * - ``sparse-cover``
     - Crown closure below 5 percent or total tree cover below 5 percent.
     - None.
   * - ``mixedwood-immature``
     - Conifer and deciduous fractions are both at least 30 percent and the stand is young
       or short.
     - ``M3`` if conifer is below 50 percent, otherwise ``M4``.
   * - ``mixedwood``
     - Conifer and deciduous fractions are both at least 30 percent.
     - ``M1`` if conifer is below 50 percent, otherwise ``M2``.
   * - ``deciduous``
     - The leading species is deciduous, or deciduous cover is at least 70 percent with
       conifer below 30 percent.
     - ``D1``.
   * - ``pine-mature`` / ``pine-immature``
     - Pine leading, age at least 40 years / younger or unknown.
     - ``C3`` / ``C4``.
   * - ``douglas-fir``
     - Douglas-fir leading.
     - ``C7``.
   * - ``larch``
     - Larch leading.
     - ``C3`` as a conservative proxy.
   * - ``spruce-open`` / ``spruce-closed``
     - Spruce, fir, cedar, or hemlock leading, crown closure below 40 percent / at least
       40 percent.
     - ``C1`` / ``C2``.

An unmapped leading species raises ``VriError``. A forest stand with no leading species
also raises. The mapping never silently invents a fuel type.

Provenance
----------

``FbpFuelAssignment`` records:

- ``fuel_type``: the canonical FBP type, or None for an explicit non-fuel stand;
- ``rule_id``: the first rule that matched;
- ``version``: ``ws4.vri-fbp.v1``;
- ``confidence``: a rule-level value in [0, 1];
- ``source_fields``: the VRI fields the rule used;
- ``notes``: a short explanation.

``map_vri_table`` returns one row per stand with the same fields and an ``is_burnable``
flag.

Example
-------

.. code-block:: python

   from ws4.fire.vri import VriStand, map_vri_stand

   stand = VriStand(
       stand_id="stand-1",
       leading_species="Pl",
       conifer_fraction=0.9,
       deciduous_fraction=0.1,
       crown_closure_percent=55.0,
       age_years=75,
       height_m=22.0,
   )
   assignment = map_vri_stand(stand)
   print(assignment.fuel_type, assignment.rule_id, assignment.confidence)
   # C3 pine-mature 0.8

Validation
----------

The fixture ``tests/fixtures/fire/vri_fbp_stands.csv`` contains representative stands for
pine, Douglas-fir, spruce, deciduous, mixedwood, grass, slash, explicit fuel types, non-fuel,
and an unknown species. The tests assert the expected type and rule for every record, the
provenance fields, the unknown-species failure, and the table output.

The fixture is synthetic and representative. It is not a copy of a private VRI inventory.

Limits
------

- The mapping is not a regional calibration. The rules are transparent defaults, and a
  regional fuel map should replace or tune them with local evidence.
- Species codes and rule thresholds are BC-oriented.
- Crown fire and growth consume the mapped type but do not feed back into the mapping.
- A non-fuel assignment returns None; it must not be passed to the FBP kernel.
- Confidence is a rule-level indicator, not a probability calibrated against observed fire
  behaviour.

Cross-references
----------------

- :doc:`fire-fbp`
- :doc:`fire-growth`
- :doc:`fire-behaviour`
