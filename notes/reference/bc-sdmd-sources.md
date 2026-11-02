# BC stand density management diagram sources

Retrieved: 2026-11-02.
Index page: <https://www2.gov.bc.ca/gov/content/industry/forestry/managing-our-forest-resources/silviculture/silvicultural-systems/silvicultural-interventions/stand-density-management>

The BC Ministry of Forests publishes the complete public set as one-page PDFs:
**14 diagrams covering 7 species, each in a natural and a planted version**. The
machine-readable catalog is `ws4/sdmd/data/sdmd/source_catalog.json`; the BEC
zone/subzone/variant coverage is `ws4/sdmd/data/sdmd/bec_variants.csv`
(229 rows).

## What is published

| Diagram | Species | Origin | Version / date | BEC main | BEC rare |
| --- | --- | --- | --- | --- | --- |
| `fdcn` | Coastal Douglas-fir | natural | unversioned, 1996-05-31 | CDF, CWH | - |
| `fdcp` | Coastal Douglas-fir | planted | unversioned, 1996-05-31 | CDF, CWH | - |
| `fdin` | Interior Douglas-fir | natural | 1.10, 1996-02-26 | IDF, ICH, MS, SBS | SBPS, PP, BG, ESSF, MH |
| `fdip` | Interior Douglas-fir | planted | 1.10, 1996-02-26 | IDF, ICH, MS, SBS | SBPS, PP, BG, ESSF, MH |
| `pln` | Lodgepole pine | natural | 1.20, 1996-02-26 | ESSF, MS, BWBS, SBS, SBPS, IDF, ICH | MH, SWB, PP, CDF, CWH |
| `plp` | Lodgepole pine | planted | 1.20, 1996-02-26 | ESSF, MS, BWBS, SBS, SBPS, IDF, ICH | MH, SWB, PP, CDF, CWH |
| `ssn` | Sitka spruce | natural | unversioned, 1996-05-31 | CWH, MH | BWBS, ICH, CDF |
| `ssp` | Sitka spruce | planted | unversioned, 1996-05-31 | CWH, MH | BWBS, ICH, CDF |
| `hwn` | Western hemlock | natural | unversioned, 1996-05-31 | CWH, ICH, MH | SBS, IDF, CDF |
| `hwp` | Western hemlock | planted | unversioned, 1996-05-31 | CWH, ICH, MH | SBS, IDF, CDF |
| `cwn` | Western redcedar | natural | unversioned, 1996-05-31 | IDF, ICH, CDF, CWH | MH, ESSF, SBS, MS, PP |
| `cwp` | Western redcedar | planted | unversioned, 1996-05-31 | IDF, ICH, CDF, CWH | MH, ESSF, SBS, MS, PP |
| `swn` | White spruce | natural | 1.30, 1996-02-26 | SWB, MS, BWBS, SBS, SBPS | ESSF, IDF, ICH, CWH |
| `swp` | White spruce | planted | 1.30, 1996-02-26 | SWB, MS, BWBS, SBS, SBPS | ESSF, IDF, ICH, CWH |

The catalog records the exact URL, file name, byte size, SHA-256, and page count
for every diagram. Downloading the PDFs is not required to use the catalog; the
URLs are the provenance.

## BEC zone coverage

The diagrams are **species- and origin-based, not BEC-variant-based**. The BC set
does not publish a separate diagram for each BEC zone/subzone/variant. The table
below is the zone-level applicability inferred from the BC Tree Species
Compendium; the variant CSV expands it to all 229 BEC rows.

| BEC zone | Main diagrams | Rare / marginal |
| --- | --- | --- |
| BG | - | `fdin`, `fdip` |
| BWBS | `pln`, `plp`, `swn`, `swp` | `ssn`, `ssp` |
| CDF | `fdcn`, `fdcp`, `cwn`, `cwp` | `pln`, `plp`, `ssn`, `ssp`, `hwn`, `hwp` |
| CWH | `fdcn`, `fdcp`, `ssn`, `ssp`, `hwn`, `hwp`, `cwn`, `cwp` | `pln`, `plp`, `swn`, `swp` |
| ESSF | `pln`, `plp` | `fdin`, `fdip`, `cwn`, `cwp`, `swn`, `swp` |
| ICH | `fdin`, `fdip`, `pln`, `plp`, `hwn`, `hwp`, `cwn`, `cwp` | `ssn`, `ssp`, `swn`, `swp` |
| IDF | `fdin`, `fdip`, `pln`, `plp`, `cwn`, `cwp` | `hwn`, `hwp`, `swn`, `swp` |
| MH | `ssn`, `ssp`, `hwn`, `hwp` | `fdin`, `fdip`, `pln`, `plp`, `cwn`, `cwp` |
| MS | `fdin`, `fdip`, `pln`, `plp`, `swn`, `swp` | `cwn`, `cwp` |
| PP | - | `fdin`, `fdip`, `pln`, `plp`, `cwn`, `cwp` |
| SBPS | `pln`, `plp`, `swn`, `swp` | `fdin`, `fdip` |
| SBS | `fdin`, `fdip`, `pln`, `plp`, `swn`, `swp` | `hwn`, `hwp`, `cwn`, `cwp` |
| SWB | `swn`, `swp` | `pln`, `plp` |

`bec_variants.csv` has one row per zone/subzone/variant, with `sdmd_main`,
`sdmd_rare`, and a `basis` column. It is a zone-level inference, not a claim
printed on the diagrams.

The pilot AU `IDFdk3` resolves to `fdin` or `fdip` (Interior Douglas-fir, natural
or planted), with `pln`/`plp` and `cwn`/`cwp` as main associates and
`hwn`/`hwp` and `swn`/`swp` as rare associates.

## Caveats

- **White spruce, not white pine.** The BC index page labels `swn`/`swp` as
  "White pine". The PDFs themselves say "WHITE SPRUCE", version 1.30. The catalog
  records both: `page_label` is the index-page label, `pdf_title` is the PDF title,
  and `swn`/`swp` carry "White pine" as an alias.
- **Shore pine is not lodgepole pine.** The `CDF` and `CWH` occurrences for
  lodgepole pine are shore pine (*Pinus contorta* var. *contorta*). The `pln`/`plp`
  diagrams describe the interior variety (*var. latifolia*). Do not use them for
  shore pine.
- **Site-index independent, not site-specific.** The diagrams use top-height
  isopleths, so one diagram serves a range of site indices; the user reads the
  stand's top height and density onto it.
- **Even-aged, single-species, healthy.** The diagrams assume even-aged,
  monospecific, untreated development. They do not describe selection systems,
  mixed stands, damage, or repression.
- **The BEC matrix is an inference.** The Tree Species Compendium gives zone-level
  occurrence with qualifiers such as "southern" and "lower". Subzone and variant
  rows inherit the zone-level result. A forester must confirm the leading species,
  stand origin, and variant before use.

## Supporting publications

| Guide | Published | URL |
| --- | --- | --- |
| How to Use a Stand Density Management Diagram: Getting the Stand and Site Data | 1997 | `sdmd_get.pdf` |
| How to Use a Stand Density Management Diagram: Yield Predictions for a Spacing Prescription | 1997 | `sdmd_yld.pdf` |
| Using Stand Density Management Diagrams to Develop Commercial Thinning Regimes | 2001 | `using_sdmds_to_plan_commercial_thinning_regimes.pdf` |
| Spacing to Increase Diversity within Stands | 2001 | `sp_div.pdf` |
| Guidelines for Developing Stand Density Management Regimes | 1999 | `developingstanddensitymanagementregimes.pdf` |

The methods report is Farnden, C. 1996. *Stand density management diagrams for
lodgepole pine, white spruce and interior Douglas-fir*. Pacific Forestry Centre
Information Report BC-X-360, 41 pp. The catalog records its public URL and
SHA-256.

All URLs are under `www2.gov.bc.ca` or `resources.sipexchangebc.com`; the exact
paths are in `source_catalog.json`. The PDFs are not copied into the repository.
