# CCISS data mining for species and BEC evidence

Date: 2026-11-02
Scope: public CCISS code and data behind `https://bcgov-ffec.ca/cciss-docs/`
Status: reconnaissance and derived extracts. No CCISS code or documentation is
copied into WS4.

## 1. Repositories found

| Repository | Purpose | Licence |
| --- | --- | --- |
| `https://github.com/bcgov/CCISS` | Workflow scripts and subprojects | Apache-2.0 |
| `https://github.com/bcgov/CCISS_ShinyApp` | Shiny application and species summaries | Apache-2.0 |
| `https://github.com/bcgov/ccissr` | R package, data tables, and silvics tables | Apache-2.0 |

The public data catalogue record is *CCISS Western North America BEC Tables*
(`https://open.canada.ca/data/en/dataset/0aae92b4-3e0b-4b52-948e-caeb17baf37e`).

## 2. Useful files

| File | What it holds | Use |
| --- | --- | --- |
| `data-raw/data_tables/Tree speciesand codes_2.0_25Aug2021.csv` | BC tree species codes, names, plant symbols | Species catalog and code mapping |
| `data/silvics_mature.rda` | Mature-stand traits: longevity, productivity, crown, light | Regime eligibility and interpretation |
| `data/silvics_regen.rda` | Regeneration, seed dispersal, early growth | Regime feasibility |
| `data/silvics_tol.rda` | Light, frost, heat, drought, surplus, nitrogen tolerance | Species suitability |
| `data/silvics_resist.rda` | Snow, wind, fire, insect, and fungi risk classes | Risk flags |
| `data-raw/data_tables/StockingStds/StockStands_v13_1.csv` | Preferred, acceptable, and not-preferred species by BEC/site series | Species choice and AU validation |
| `data-raw/data_tables/StockingStds/StockingInfo_v13.csv` | Target and minimum stocking, delay, assessment window | Regime density bounds |
| `data/S1.rda` | 15,074 species feasibility rows by BEC/site series | Feasibility checks |
| `data/SIBEC.rda` | 9,708 mean site-index rows by species/site series | Site-index choice |
| `data/E1.rda` | 15,354 edatopic positions by site series | Site-series context |
| `data/SS.rda`, `data/N1.rda` | 3,012 site-series codes; 2,541 long names | Site-series labels |
| `data/stocking_standards.rda` | 11,018 rows of preferred/acceptable species | Species choice |
| `data/stocking_info.rda` | 1,549 rows of target/minimum stocking and windows | Regime density bounds |
| `data/stocking_height.rda` | 8,071 rows of free-growing height by standard/species | Regeneration checks |
| `data/cfrg_rules.rda` | 384 species feasibility and preferred/acceptable rules | Rule review |
| `data/models_info.rda` | Climate and BGC model versions | Provenance |
| `data-raw/data_tables/WNA_BGCs_Info_v12_15.csv` | BGC labels and names for Western North America | BEC crosswalk |
| `data-raw/data_tables/SiteSeries_names_v12_15.csv` | Site-series names | Report labels |

## 3. Extracts added to WS4

All files are in `ws4/sdmd/data/sdmd/` and carry `source` and `licence` columns
where the rows come from CCISS.

| File | Rows | Content |
| --- | --- | --- |
| `tree_species.csv` | 37 | Non-excluded BC tree species with code, life form, English and scientific names |
| `species_traits.csv` | 6 | Traits for the six species in the public SDMD set: Cw, Fd, Hw, Pl, Ss, Sw |
| `idfdk3_stocking.csv` | 9 | IDFdk3 site series, target/minimum stems, preferred/acceptable/not-preferred species, edatopic codes, stocking delay, assessment window |
| `idfdk3_suitability.csv` | 38 | Species feasibility ratings by IDFdk3 site series, including the `Ro` non-forested row |
| `idfdk3_sibec.csv` | 32 | Mean SIBEC site index by IDFdk3 site series and species |
| `bec_crosswalk.csv` | 247 | Union of the WS4 BEC labels and the CCISS BC BGC labels, with both/only flags |

## 4. What the data says

### Lodgepole pine in IDFdk3

`Pl` is preferred on eight of the nine IDFdk3 site series and acceptable on the
ninth. That supports a real PLI AU in IDFdk3. The stocking target is 800-1200
stems/ha and the minimum is 500-700 stems/ha across the nine site series.

The real TSA 23 PSP points in `pilot-tsa23-idfdk3` have 740-1590 stems/ha,
inside the published stocking window. The CT60 and untreated paths remain above
the minimum for most of the projection. SIBEC gives IDFdk3 `Pl` a mean site
index of 15.7-19.9 m and `Fd` 13.3-20.7 m; the real PSP points span 12.1-20.6 m.

### IDFdk3 species feasibility

`S1` rates `Pl` at 1-4 across the nine site series and `Fd` at 1-3. `Lw` is
out of range on two site series; `Sx` is rated 1-3. The edatopic positions range
from dry `A1`/`B1` on site series 02 to wet `E7` on site series 09. This is the
layer to use when deciding which species can share an AU, not a replacement for
the SDMD diagram.

### Species traits

Examples from the six-species extract:

| Species | Low-light tolerance | Water-deficit tolerance | Fire risk |
| --- | --- | --- | --- |
| Cw | H | M | L-H |
| Fd | L-H | M | M-H |
| Hw | H | L | L-H |
| Pl | L | H | H |
| Ss | M | L | L |
| Sw | M | M | H |

`Pl` is shade-intolerant and drought/fire-tolerant; `Cw` and `Hw` are shade
tolerant with lower drought tolerance. These classes are candidates for
`eligibility_expr` and for interpreting regime paths, not for changing the SDMD
equations.

### BEC crosswalk

The WS4 229-row inference and the CCISS BC list agree on 183 labels. The
crosswalk has 30 WS4-only labels and 34 CCISS-only labels. Examples of the
difference:

- WS4-only: `BWBSdk1`, `BWBSdk2`, `BWBSmw1`, `CWHvm3`, `ESSFwc5`, `MSdk1`.
- CCISS-only: `BWBSdk`, `BWBSmk`, `CWHvh3`, `ESSFdh1`, `ICHdw4`, `SBSwk3a`.

These are version and aggregation differences, not proof that either list is
wrong. The crosswalk is the place to resolve them; do not overwrite
`bec_variants.csv` from CCISS without a version note.

## 5. What is not there

CCISS does **not** provide SDMD isopleths or stand-density-management diagrams.
It cannot replace the missing lodgepole pine diagram, and it does not supply the
digitised `pln`/`plp` curves. The published Farnden PDFs remain the source for
that work.

CCISS also does not provide FVS trajectories or PSP tree lists. It supplies
species suitability, silvics, and stocking standards, not growth projections.

## 6. Leads for WS4

1. Use `idfdk3_stocking.csv` to set per-site-series density floors and ceilings
   for the real PLI AU and for regime constraints; use `idfdk3_suitability.csv`
   and `idfdk3_sibec.csv` to choose species and site index.
2. Use `species_traits.csv` to populate eligibility rules such as shade-tolerant
   selection regimes and drought/fire risk flags.
3. Use `suitability.csv` and `Feasibility_v13_7.csv` to validate species/BEC
   pairs before an AU is added, instead of relying on name matching alone.
4. Use `bec_crosswalk.csv` to resolve the 30 WS4-only and 34 CCISS-only BEC
   labels, then update `bec_variants.csv` with a version note.
5. Digitise the published `pln`/`plp` lodgepole pine diagrams if the PLI AU is to
   have a real SDMD fit. CCISS supports the species choice but not the diagram.
6. Build a real PLI PSP extract from TSA 23 / IDFdk3 / Pl-leading clusters; the
   stocking table already says Pl is a preferred species there.

## 7. Licence and attribution

`ccissr` and `CCISS_ShinyApp` declare Apache-2.0. The BC data catalogue record
for the BEC tables is open data. The derived WS4 files keep a `source` and
`licence` column, and this note cites the repositories and catalogue record.
No CCISS source code or prose is copied into the repository.

## 8. Reproduction

```bash
git clone --depth 1 https://github.com/bcgov/ccissr.git
git clone --depth 1 https://github.com/bcgov/CCISS_ShinyApp.git
```

The extracts were built from the `ccissr` files named above with pandas and
Rscript (for the `.rda` tables). The packaged `.rda` tables were used for the
IDFdk3 feasibility, SIBEC, edatopic, and stocking extracts; the raw CSVs were
used for the species catalog and the BEC crosswalk. The selection and aggregation
rules are described in sections 3 and 4; the test file is
`tests/test_sdmd_cciss.py`.
