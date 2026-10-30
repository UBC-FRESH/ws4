# Four-TSA HWP sensitivity: low, default, high

Date: 2026-10-30
Status: exact full-landscape sensitivity complete
Scope: TSA08/16/40/41; 50-year all-block schedules; three public HWP assumptions

## Scenarios

| Scenario | Solid half-life | Solid displacement | Paper half-life |
| --- | ---: | ---: | ---: |
| low | 35 y | 0.45 | 2 y |
| default | 100 y | 1.0 | 2 y |
| high | 200 y | 2.4 | 2 y |

All scenarios use 85% utilization, a 50/50 paper/solid split, zero paper displacement,
exact annual survival, and decay to atmosphere. Ecosystem carbon is unchanged by the HWP
scenario; the sensitivity is entirely in product storage and displacement.

## Results at offset 50

| TSA | Scenario | Ecosystem (tC) | HWP (tC) | System (tC) | Cumulative emissions (tCO2e) |
| --- | --- | ---: | ---: | ---: | ---: |
| 08 | low | 844,189,238 | 20,365,976 | 864,555,214 | 807,908,736 |
| 08 | default | 844,189,238 | 38,268,593 | 882,457,831 | 633,877,787 |
| 08 | high | 844,189,238 | 45,351,832 | 889,541,070 | 332,009,131 |
| 16 | low | 404,510,934 | 12,785,284 | 417,296,218 | 779,049,703 |
| 16 | default | 404,510,934 | 24,024,128 | 428,535,063 | 669,797,139 |
| 16 | high | 404,510,934 | 28,470,821 | 432,981,755 | 480,291,048 |
| 40 | low | 379,138,290 | 12,447,445 | 391,585,735 | 652,664,034 |
| 40 | default | 379,138,290 | 23,389,313 | 402,527,604 | 546,298,366 |
| 40 | high | 379,138,290 | 27,718,506 | 406,856,796 | 361,799,795 |
| 41 | low | 282,497,147 | 11,121,687 | 293,618,834 | 565,332,384 |
| 41 | default | 282,497,147 | 20,898,154 | 303,395,301 | 470,295,556 |
| 41 | high | 282,497,147 | 24,766,251 | 307,263,398 | 305,447,639 |

## Reading

- HWP storage is 2.4–3.8% of system carbon in the low scenario, 4.3–6.9% in the default,
  and 5.1–8.1% in the high scenario.
- Cumulative emissions vary by roughly **1.6–2.4×** across the low-to-high range.
  TSA08 is the most sensitive (332–808 MtCO2e); TSA16 the least (480–779).
- The TSA ranking is not fully stable:
  - low: TSA41 < TSA40 < TSA16 < TSA08
  - default: TSA41 < TSA40 < TSA08 < TSA16
  - high: TSA41 < TSA08 < TSA40 < TSA16
  TSA41 and TSA16 remain the low and high ends; TSA08 and TSA40 swap.
- A single default HWP run is therefore not enough for a cross-TSA comparison. Report the
  range or the scenario pair, not just the central value.

## Verification

- All 12 exact runs completed with exit 0 (default from the prior sweep, plus eight new).
- 51 offsets, 1,326 account rows per run, zero non-finite values, no warnings.
- Ecosystem carbon is bit-identical across scenarios at every offset.
- `system = ecosystem + HWP` exactly.
- Runs: low 361–744 s, high 355–734 s depending on TSA.

## Artifacts

- `carbon-handoff/ws4-tsaXX-full-50y-hwp/`
- `carbon-handoff/ws4-tsaXX-full-50y-hwp-low/`
- `carbon-handoff/ws4-tsaXX-full-50y-hwp-high/`
- `carbon-handoff/ws4-hwp-sens-4tsa-report.md`
