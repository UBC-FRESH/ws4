# GBR dataset provenance records

The P26 `data_quality` block reads a `data_quality.yaml` sidecar beside the compiled
`manifest.json`. The two Great Bear Rainforest instance matrices carry the following records. Managed curves are
the TSR-consistent BatchTIPSY lane; the dated VDYP-transform runs are comparison backups. The
values that the source material does not state are `null`; the report keeps them unknown.

Evidence:

- `femic-tsa46-instance/config/run_profile.tsa46_full.yaml`
- `femic-tsa46-instance/notes/reference/ws4-build.md`
- `femic-tsa46-instance/notes/reference/tipsy-curves.md`
- `femic-tsa46-instance/notes/reference/tipsy-validation.md`
- `femic-tsa46-instance/data/source/public_data_manifest.json`
- `femic-tsa46-instance/docs/limitations.rst`
- the TSA 47 equivalents under `femic-tsa47-instance`

## TSA 46

```yaml
schema_version: 1
inventory:
  vintage: "2025"
  source: "BC VRI 2025 (VEG_COMP_LYR_R1_POLY_2025.gdb)"
  imputation_share: null
  coverage: null
curves:
  source: "BatchTIPSY 4.7, TSR-consistent managed-curve lane"
  accepted_tipsy: true
  notes: "Natural curves are VDYP; managed curves are predecessor-TSR assumptions, not a reviewed GBR yield table."
thlb:
  source: "predecessor-derived THLB calibration"
  reviewed_gbr_netdown: false
  target_ha: 268970
limitations_url: "https://ubc-fresh.github.io/femic-tsa46-instance/limitations.html"
limitations:
  - "Natural curves are VDYP; managed curves are TSR-consistent BatchTIPSY output under predecessor-TSR assumptions, not a reviewed GBR yield table."
  - "THLB is predecessor-derived, not a reviewed GBR netdown."
  - "Imputation share and coverage are not recorded in the source manifest."
  - "The AAC is a model ceiling, not an operational guarantee."
  - "The opening-first schedule is a deterministic seed, not an optimized or operatively feasible plan."
  - "Instance limitations: https://ubc-fresh.github.io/femic-tsa46-instance/limitations.html"
```

THLB is the North Coast 145,808 ha plus the Mid Coast 123,162 ha calibration target.

## TSA 47

The same schema, with the TSA 47 values:

```yaml
schema_version: 1
inventory:
  vintage: "2025"
  source: "BC VRI 2025 (VEG_COMP_LYR_R1_POLY_2025.gdb)"
  imputation_share: null
  coverage: null
curves:
  source: "BatchTIPSY 4.7, TSR-consistent managed-curve lane"
  accepted_tipsy: true
  notes: "Natural curves are VDYP; managed curves are predecessor-TSR assumptions, not a reviewed GBR yield table."
thlb:
  source: "predecessor-derived THLB calibration"
  reviewed_gbr_netdown: false
  target_ha: 145256
limitations_url: "https://ubc-fresh.github.io/femic-tsa47-instance/limitations.html"
limitations:
  - "Natural curves are VDYP; managed curves are TSR-consistent BatchTIPSY output under predecessor-TSR assumptions, not a reviewed GBR yield table."
  - "THLB is predecessor-derived, not a reviewed GBR netdown."
  - "Imputation share and coverage are not recorded in the source manifest."
  - "The AAC is a model ceiling, not an operational guarantee."
  - "The opening-first schedule is a deterministic seed, not an optimized or operatively feasible plan."
  - "Instance limitations: https://ubc-fresh.github.io/femic-tsa47-instance/limitations.html"
```

THLB is 60.08% of the Kingcome 186,914 ha plus 20.23% of the Strathcona 162,873 ha.

## Verification

With the sidecar present:

```bash
ws4 quality --dataset runtime/tsa46_full/matrix --check
ws4 quality --dataset runtime/tsa47_full/matrix --check
```

reports `status: ok`, `provenance_supplied: true`, and `provenance: ok` for both matrices.
The imputation and coverage fields remain `null` and are named in the limitations list.
