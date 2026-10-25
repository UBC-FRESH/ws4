# GBR dataset provenance records

The P26 `data_quality` block reads a `data_quality.yaml` sidecar beside the compiled
`manifest.json`. The two Great Bear Rainforest instance matrices carry the following records.
The values that the source material does not state are `null`; the report keeps them unknown.

Evidence:

- `femic-tsa46-instance/config/run_profile.tsa46_full.yaml`
- `femic-tsa46-instance/notes/reference/ws4-build.md`
- `femic-tsa46-instance/notes/reference/vdyp-runtime.md`
- `femic-tsa46-instance/data/source/public_data_manifest.json`
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
  source: "VDYP7 transform (managed_curve_mode: vdyp_transform)"
  accepted_tipsy: false
thlb:
  source: "predecessor-derived THLB calibration"
  reviewed_gbr_netdown: false
  target_ha: 268970
limitations:
  - "Managed curves are a VDYP transform, not accepted TIPSY output."
  - "THLB is predecessor-derived, not a reviewed GBR netdown."
  - "Imputation share and coverage are not recorded in the source manifest."
  - "The AAC is a model ceiling, not an operational guarantee."
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
  source: "VDYP7 transform (managed_curve_mode: vdyp_transform)"
  accepted_tipsy: false
thlb:
  source: "predecessor-derived THLB calibration"
  reviewed_gbr_netdown: false
  target_ha: 145256
limitations:
  - "Managed curves are a VDYP transform, not accepted TIPSY output."
  - "THLB is predecessor-derived, not a reviewed GBR netdown."
  - "Imputation share and coverage are not recorded in the source manifest."
  - "The AAC is a model ceiling, not an operational guarantee."
```

THLB is 60.08% of the Kingcome 186,914 ha plus 20.23% of the Strathcona 162,873 ha.

## Verification

With the sidecar present:

```bash
ws4 quality --dataset runtime/tsa46_full_vdyp_20261023/matrix --check
ws4 quality --dataset runtime/tsa47_full_vdyp_20261023/matrix --check
```

reports `status: ok`, `provenance_supplied: true`, and `provenance: ok` for both matrices.
The imputation and coverage fields remain `null` and are named in the limitations list.
