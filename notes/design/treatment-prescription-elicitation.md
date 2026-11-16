# Treatment-prescription expert elicitation

Status: pre-discussion note. Not evidence, not a model, not an operational recommendation.

## Decision this informs

Should WS4 add an explicit post-treatment FBP conversion for BC stands, and if so, which
conversion is defensible?

The current prescription contract requires the caller to supply the post-treatment FBP fuel
type. Without that input, treatment scenarios stop at a stand-level preview.

## What is already established

Open data:

- BC VRI 2025 Rank 1: open stand geometry and attributes.
- National Fire and Fire Surrogate (FFS) study: public measured pre/post treatment data.
- BC Wildfire CRI Fuel Treatments: **Access Only**, not open; not used.

Measured FFS medians:

| Treatment | Canopy cover | Live basal area | Surface fuel |
| --- | ---: | ---: | ---: |
| burn-only | −3.1% | −0.8% | −45.2% |
| thin-only | −10.8% | −28.5% | +50.6% |
| thin-burn | −22.9% | −29.0% | −3.5% |

Controlled BC VRI result:

- MKRF C2 stands, 100 m grid, fixed weather, flat terrain;
- thin-burn canopy change only: −22.9%;
- control and treated both burned 228.0 ha, 7,000 m perimeter, 16.149 m/min head ROS;
- **no effect**. Crown closure alone is insufficient in C2.

## Why elicit

The missing step is a judgement, not a computation:

1. Which post-treatment FBP fuel type represents each treatment in each BC fuel class?
2. How should the measured surface-fuel change be represented in FBP?
3. Which FFS results transfer to BC, and with what uncertainty?
4. How should treatment age reduce the effect?
5. Is the correct answer a no-go for some fuel classes?

Do not ask experts to “validate the model.” Ask for the prescription and its uncertainty.

## Suggested participants

- BC fire-behaviour specialist;
- fuels-management specialist;
- silviculture / stand-structure specialist;
- operational suppression or aerial-treatment specialist (if available).

A smaller group is acceptable. Record disagreement rather than forcing consensus.

## Pre-read

- this note;
- `notes/reports/ffs-treatment-effects.md`;
- `notes/reports/vri-treatment-preview.md`;
- `notes/reports/vri-canopy-scenario.md`;
- `docs/reference/fire-treatment-prescription.rst`.

## Questions

Answer individually before discussion.

### A. Fuel-class conversion

For each relevant BC base fuel class (at least C2, C3, C4, C7, M1/M2), and each treatment
(burn-only, thin-only, thin-burn):

- What post-treatment FBP fuel type should be used?
- If no FBP type is defensible, answer **no-go** and say why.
- Does the answer depend on stand age, species, crown closure, or treatment severity?

### B. Surface fuel

- Should the FFS surface-fuel change be represented as a different FBP type, a custom surface
  fuel load, or not represented?
- If custom load is required, what is the acceptable range?
- What is the minimum defensible representation for a scenario, not a forecast?

### C. Canopy

- Should the FFS canopy-cover median be applied directly to VRI crown closure?
- What are the plausible P10/P50/P90 changes for BC, not just the US median?
- Does the canopy change matter without a surface-fuel change?

### D. Time

- How should efficacy decay with treatment age?
- Is the FFS “greater than 10 years = 28% severity reduction” transferable?
- What maintenance assumption should be stated?

### E. Transferability and confidence

- Which FFS sites or forest types are usable analogues for BC?
- Which are not?
- Give a confidence level: low / medium / high, with one sentence of basis.

### F. Decision use

- Which treatment rankings are stable enough to inform planning?
- Which comparisons should remain no-go?
- What result would change your answer?

## Response form

Complete one row per base fuel × treatment. Use ranges, not only medians.

| Base fuel | Treatment | Post FBP type or no-go | Canopy Δ P10/P50/P90 | Surface-fuel Δ P10/P50/P90 | Confidence | Basis / caveat |
| --- | --- | --- | --- | --- | --- | --- |
| C2 | burn-only |  |  |  |  |  |
| C2 | thin-only |  |  |  |  |  |
| C2 | thin-burn |  |  |  |  |  |
| C3 | burn-only |  |  |  |  |  |
| C3 | thin-only |  |  |  |  |  |
| C3 | thin-burn |  |  |  |  |  |
| C4 | burn-only |  |  |  |  |  |
| C4 | thin-only |  |  |  |  |  |
| C4 | thin-burn |  |  |  |  |  |
| C7 | burn-only |  |  |  |  |  |
| C7 | thin-only |  |  |  |  |  |
| C7 | thin-burn |  |  |  |  |  |

Add rows for M1/M2 or other fuel classes as needed. Leave blank where the answer is no-go; write
“no-go” explicitly.

## Protocol

1. Send the pre-read and form separately to each expert.
2. Collect independent written responses before any group discussion.
3. Hold one 60–90 minute discussion focused on disagreements and missing evidence.
4. Ask each expert to confirm or revise their form after the discussion.
5. Report the distribution of answers, not a forced consensus.
6. Do not average incompatible fuel classes or treatment definitions.

## Analysis and record

For each row, record:

- number of responses;
- median and range for each numeric input;
- number of no-go responses;
- confidence distribution;
- the specific evidence cited;
- unresolved disagreements.

Do not convert “no-go” into a default conversion. Do not fill missing rows by interpolation.

## Decision rules

- If a fuel class has no defensible post-treatment FBP type, that class remains no-go.
- If experts support a conversion for some classes only, implement only those classes.
- If surface-fuel change cannot be represented, state that the fire scenario is canopy-only and
  do not claim a full treatment effect.
- If the group cannot agree, stop treatment validation and publish the disagreement.

## Output

A single record:

- completed forms (anonymized if needed);
- summary table with medians/ranges/no-go counts;
- confidence notes;
- one of: implement mapping, restrict mapping, or no-go;
- next data request, if any.

This note is the input to that discussion. It is not the answer.
