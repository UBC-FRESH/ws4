# Publication and technical-report concepts for the WS4 fire regime

Status: scoping draft

This note frames publishable claims from the WS4 fire-behaviour, suppression, risk, and
estate-integration work. It is based on a rapid scoping review of peer-reviewed and grey
literature, not a PRISMA systematic review. The search covered fire-behaviour and burn-probability
models, suppression modelling, integrated fire-forest management optimization, open-source
environmental software, and reproducibility/LLM-assisted workflows. The cutoff was November 2026.

## Bottom line

The individual fire-science components are not novel:

- the Canadian FBP System, FWI, Rothermel surface fire, and crown-fire equations are established;
- process-based fire regimes and Monte Carlo burn-probability models are established;
- suppression and initial-attack submodels are established;
- integrated fire-forest management optimization is established;
- open-source fire-growth models and open-source forest estate models already exist.

The defensible contribution is the **combination and the transparency of the combination**:

1. an open, end-to-end path from public VRI/SRTM/water data through FBP fuel mapping, spatially
   explicit growth, reduced-form regional suppression/escape, succession, estate accounting, and
   optimization;
2. a reproducible regional calibration protocol with fixed data splits, seeds, residuals, and
   explicit failure reporting;
3. a full TSA24-scale case (458,708 blocks; 1,111,565 support cells) that demonstrates the
   computational path on a Linux/HPC stack;
4. an agent-operable development workflow with durable code, tests, manifests, and reproducibility
   artifacts.

The first paper should claim the integration and the calibration protocol, not new fire physics.
The phrase “unique” should be avoided until a systematic review and benchmark are complete.

A defensible portfolio is:

- **Primary paper:** the open methods/software integration (Concept 1);
- **Primary applied paper:** fire-aware estate optimization (Concept 3), after global target
  reconciliation;
- **Optional third paper:** the calibration/transferability diagnostic (Concept 2), only if the
  independent holdout supports a distinct result;
- **Immediate technical outputs:** the benchmark/reproducibility report (T1) and the BC
  practitioner guide (T2);
- **Separate technical report:** the agent workflow (T3), not a peer-reviewed novelty claim.

## What the literature already covers

### Fire growth, burn probability, and fire regimes

FSim is the reference for large-fire occurrence, growth, behaviour, and statistical containment at
continental scale. It simulates many synthetic fire seasons, uses Rothermel-based growth, and
represents suppression with a containment model and optional perimeter trimming. It reports burn
probability and fire-size distributions and has been evaluated against historical patterns across
the United States (Finney et al. 2011, DOI 10.1007/s00477-011-0462-z). The FSim best-practices
document describes the suppression module and perimeter trimming in more implementation detail
(Pyrologix 2019, grey literature).

Burn-P3 and the newer BurnP3+ package are the Canadian FBP-based counterparts. Burn-P3 has been
used for burn-probability and ignition/suppression studies; BurnP3+ is an open-source SyncroSim
package that can use Prometheus, Cell2Fire, or FireSTARR as growth engines. The Burn-P3 legacy
description and the BurnP3+ documentation are the relevant sources. The peer-reviewed review by
Parisien et al. (2019, DOI 10.1071/WF19069) describes the burn-probability modelling family and
its applications, including integration with secondary models.

Cell2Fire is an open-source, cell-based FBP growth model designed for strategic landscape
management and parallel computation (Pais et al. 2021, DOI 10.3389/ffgc.2021.692706). Its
Mediterranean adaptation, Cell2Fire_SB, is explicitly aimed at tactical forest planning and links
to growth and optimization prototypes, but the published work describes the simulator and the
integration concept rather than a complete open estate optimizer (Gonzalez-Olabarria et al. 2023,
DOI 10.3389/ffgc.2023.1071484).

LANDIS-II is a fully open-source forest landscape model. Its Dynamic Fire System extension uses
FBP-derived fire behaviour, weather, fuel, and topography, and supports size-based or duration-based
fire regimes (Sturtevant et al. 2009, DOI 10.1016/j.ecolmodel.2009.07.030). It is a landscape
succession model, not an economic estate optimizer, and its fire extension explicitly targets
long-term patterns rather than operational fire behaviour.

ELMFIRE, ForeFire, WRF-Fire, and related systems occupy the open-source fire-spread and coupled
fire-atmosphere space. They are important comparators for growth and HPC, but they are not
estate-planning systems with harvest scheduling, volume accounting, and suppression calibration.

### Suppression modelling

Duff and Tolhurst (2015, DOI 10.1071/WF15018) review operational suppression models and distinguish
initial attack, containment, resource allocation, and optimization approaches. They emphasize that
suppression models are data-hungry and that operational validation is difficult. FSim represents
large-fire suppression statistically and through perimeter trimming; Burn-P3 has been used to model
initial attack by removing fires with a containment probability, but large-fire suppression is not
modelled directly in that application (Reimer et al. 2019, DOI 10.3390/fire2040060). The systematic
review by Hai et al. (2023, DOI 10.3390/fire6110424) finds that suppression effects on fire regimes
are widely studied but that model structures and hypothesis testing are heterogeneous.

WS4 occupies a different point in this space: it is not a resource-deployment or fireline-production
model. It is a **reduced-form regional suppression/escape layer** that maps potential growth to
contained and escaped size distributions, with per-region parameters. That must be described
precisely in any paper; calling it an “operational suppression model” would be an overclaim.

### Integrated fire-forest management optimization

The “integration” idea is not new. Acuna et al. (2010, DOI 10.1139/X10-151) coupled fire occurrence,
initial attack, fire spread, a fire-protection-value heuristic, and a spatially explicit timber
harvest MILP in Alberta. They reported an 8.1% net present value increase relative to planning with
exogenous fire loss. The implementation used GAMS/CPLEX and a bespoke model; code, data, and
workflow were not open.

LSim linked FVS, FSim, and management scenarios over 50 years (Ager et al. 2020,
DOI 10.1016/j.ecolmodel.2020.108962). It is a substantial operational integration, but it is not a
general open-source estate optimizer and does not provide the BC FBP/open-data path.

Labarre et al. (2026, arXiv:2609.16865) combine fire simulation within a growth model and robust
forest-management optimization for intensive plantation forests. This is the closest recent
preprint to the management concept; it reinforces that the scientific question is live, not that
the space is empty.

WS3 is the open-source Python forest estate framework: Model I optimization, simulation, carbon
accounting, raster allocation, and reproducible case studies (Paradis 2026,
DOI 10.1016/j.ecoinf.2026.103688). It is the natural host for a fire extension, but its published
scope does not include the WS4 fire regime.

### Open science, reproducibility, and LLM-assisted development

The wildfire modelling literature still has a code-availability gap. A 2026 review of machine
learning and deep learning for wildfire prediction reported that only 7.7% of the methodological
studies analysed provided publicly accessible code. This is a different subfield, but it supports
the general point: reproducible, reusable implementations remain scarce.

The reproducibility guidance is well established: preserve data, code, and runtime; use version
control, tests, manifests, and archives (Sandve et al. 2013, DOI 10.1371/journal.pcbi.1003285;
Wilkinson et al. 2016, DOI 10.1038/sdata.2016.18). Dunn et al. (2026,
DOI 10.1016/j.patter.2026.101644) add a directly relevant rule for agent-assisted work: keep the
LLM **off the data path** where possible, preserve the generated code and artifacts, verify with
tests, record model/version/provenance, and measure determinism. That is the correct frame for the
WS4 workflow; it is not evidence of autonomous scientific discovery.

## Capability matrix

| Capability | FSim | BurnP3+ | Cell2Fire | LANDIS-II | Acuna et al. 2010 | LSim/Ager 2020 | WS3 | WS4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Canadian FBP fire behaviour | no (US system) | yes | yes | partial | yes | no (US system) | no | yes |
| Spatially explicit growth | yes | yes | yes | yes | yes | yes | no | yes |
| Suppression/containment | yes | partial (initial attack) | no | partial | yes (initial attack) | yes (FSim) | no | reduced-form regional |
| Regional empirical calibration | yes, historical | partial | case-specific | parameterized | case-specific | FSim calibration | no | yes, 24 regions, in-sample |
| Forest estate optimization | no | no | partial/static | no | yes (MILP) | partial scenarios | yes | prototype, sharded |
| Full-estate BC case | no | no | no | no | no | no | no | yes (TSA24) |
| Open-source code | not a general open package | yes | yes | yes | no | no | yes | yes |
| Open data end-to-end | no | partial | no | no | no | no | partial | yes, public BC data |
| HPC/parallel | yes | yes | yes | yes | limited | limited | yes | yes, 36-core shards |
| Agent-operable workflow | no | no | no | no | no | no | emerging | demonstrated workflow |

The matrix is a positioning device, not a scorecard. “Partial” means the capability exists but is
not the published system's central contract or is not exposed as an open, reusable path.

## Defensible gap statement

A defensible formulation is:

> We found no published, open, end-to-end implementation that couples a process-based Canadian FBP
> fire regime, regionally calibrated reduced-form suppression/escape, a spatially explicit forest
> estate optimizer, public BC data, and reproducible HPC/agent workflows at TSA scale.

This is narrower than “no one integrates fire and forest management.” Acuna et al. (2010), LSim,
Cell2Fire_SB, and Labarre et al. (2026) already integrate parts of that problem. The gap is the
**open, auditable, reproducible whole**, not the idea of integration.

What not to claim:

- not new FBP, Rothermel, FWI, or crown-fire physics;
- not operational suppression resource allocation;
- not a validated predictive fire regime outside the calibration domain;
- not a global optimum from the current sharded optimizer;
- not “autonomous science” from LLM-assisted development;
- not full TSA24 calibration if only 24 suppression regions are fitted.

## Paper concept 1: the methods/software paper

**Working title:** *An open, suppression-aware fire regime for spatially explicit forest estate
optimization*

**Core question:** Can an open, reproducible modelling stack connect public forest/terrain data to
a process-based fire regime, regional suppression calibration, and estate-scale optimization
without proprietary components?

**Gap addressed:** the integration/reproducibility gap above, not the individual fire-physics gap.

**Contribution:**

1. Architecture: layer ingestion, FBP fuel mapping, spatial growth, reduced-form suppression and
   escape, succession, estate accounting, risk targets, and optimization.
2. A regional calibration protocol with fixed splits, seeds, residual reporting, and explicit
   failure cases.
3. A TSA24 demonstration at 458,708 blocks and 1,111,565 support cells, with runtime and scaling.
4. A reproducibility package: code, data manifest, seeds, environment, and archived artifacts.

**Evidence to show:**

- the full TSA24 layer stack and support grid;
- calibration residuals against historical fire-size distributions, including the tail failures;
- five-seed risk distributions and CVaR;
- full-estate five-year evaluation;
- sharded optimizer runtime and schedule;
- comparison against a fire-blind or burn-probability baseline;
- at least one external benchmark against FSim, BurnP3+, or Cell2Fire on a shared landscape.

**Figures:**

1. system architecture and data flow;
2. capability matrix or model-comparison table;
3. observed versus simulated fire-size distributions;
4. full-estate risk distribution and CVaR;
5. runtime/scaling across workers and tiles.

**Target venues:** *Environmental Modelling & Software* (first choice), *Geoscientific Model
Development* (if the evaluation is strong), *Ecological Modelling* (backup).

**Review risk:** “This is engineering, not science.” Mitigation: frame the calibration protocol and
the transferability result as the scientific contribution; include a benchmark and independent
validation.

## Paper concept 2: the calibration/transferability paper

**Working title:** *When global suppression parameters fail: regional calibration, residuals, and
tail risk in an open FBP-based fire regime*

**Core question:** Do suppression/escape parameters calibrated globally transfer across regions,
and what is lost when they do not?

**Gap addressed:** suppression models are usually calibrated to a study area or a historical
large-fire record, but transferability, tail behavior, and uncertainty are rarely reported in an
open framework. The WS4 global gate no-go and the 24-region calibration provide a concrete case.

**Contribution:**

1. A fixed calibration/validation protocol for reduced-form suppression and escape.
2. Evidence that global parameters fail to reproduce regional fire-size distributions.
3. A regional parameter map with central-tendency gains and explicit tail underproduction.
4. A diagnostic decomposition: contained fraction, escape fraction, escape cap, weather hazard,
   and potential-growth sample.
5. A recommendation for partial pooling or hierarchical calibration, rather than independent
   per-region fits.

**Evidence to show:**

- global training/validation residuals;
- per-region fitted parameters and uncertainty;
- leave-one-region-out or spatial-block cross-validation;
- tail metrics (p90, p95, over-1,000 ha, maximum);
- sensitivity to the escape cap and potential sample;
- comparison with FSim-style containment and Burn-P3-style initial attack on shared cases.

**Target venues:** *International Journal of Wildland Fire* (first choice), *Fire* (open access),
*Natural Hazards and Earth System Sciences* (if framed as risk/uncertainty).

**Review risk:** the current calibration is in-sample and the tail is underproduced. This paper is
only credible with an independent holdout and a clear negative/diagnostic framing. It may be more
publishable as “limits of calibration” than as “a calibrated regime.”

## Paper concept 3: the management/application paper

**Working title:** *Fire-aware forest estate optimization under uncertainty: coupling a
process-based fire regime to harvest scheduling*

**Core question:** How do process-based fire risk and suppression assumptions change optimal
harvest schedules, volume, and tail risk relative to fire-blind or exogenous burn-probability
planning?

**Gap addressed:** integrated fire-estate studies exist, but open, reproducible, process-based,
suppression-aware comparisons at estate scale are scarce. The practical audience is forest
planners, not fire modellers.

**Contribution:**

1. A controlled comparison: fire-blind, burn-probability overlay, and process-based fire regime.
2. Metrics: harvested volume, NPV or volume flow, burned area, CVaR of volume loss, carbon or
   biomass side effects.
3. A scalable sharded optimization strategy with an explicit solution-quality check against a
   smaller global optimization.
4. A BC TSA24 case study with open data and code.

**Evidence to show:**

- a global or near-global baseline on a reduced estate;
- sharded versus global solution quality;
- fire-aware versus fire-blind schedules;
- uncertainty across seeds and suppression scenarios;
- sensitivity to harvest constraints, adjacency, and risk targets;
- runtime and reproducibility.

**Target venues:** *Canadian Journal of Forest Research* (first choice), *Forest Ecology and
Management*, *Forest Policy and Economics*, or *Environmental Modelling & Software* if the
algorithmic contribution dominates.

**Review risk:** the current sharded optimizer uses local harvest targets and is not a global
optimum. This paper should wait for target reconciliation or be framed explicitly as a
decomposition heuristic with a quality evaluation.

## Paper concept 4: the data/benchmark paper

**Working title:** *A reproducible TSA24 open fire-regime benchmark: layers, calibration, and
estate-scale results*

**Contribution:** a citable data/software package containing the 133-tile layer manifest, support
grid, calibration map, seeds, evaluation scripts, and benchmark outputs.

**Target venues:** *Data in Brief*, *Scientific Data*, or a *Fire* data descriptor; alternatively a
CFS/BC Wildfire technical report plus a Zenodo DOI.

**Review risk:** data papers need demonstrated reuse and clear licensing. The VRI, SRTM, and
wildfire-perimeter licences must be verified before redistribution. Large rasters should be hosted
in an archive, not Git.

## Technical and grey-literature reports

### T1: Open fire-regime benchmark and reproducibility package

A technical report aimed at researchers and research software engineers. Contents: data
provenance, tile manifest, layer QA, calibration protocol, seeds, runtime, known failures, and
reproduction commands. This is the lowest-risk, highest-leverage output because it enables every
later paper.

### T2: BC operational guide

A practitioner-oriented report for BC Wildfire Service, the Ministry of Forests, CFS, FPInnovations,
licensees, and consultants. Contents: what the model does, what it does not do, input requirements,
calibration residuals, scenario examples, runtime, and decision-use cautions. This is where the
practical open-software gap can be addressed without overclaiming peer-reviewed novelty.

### T3: Human-supervised agent workflow

A report on the actual development workflow: how agents were used, what was committed, what was
tested, how failures were caught, and how the LLM was kept off the data path. The Dunn et al. (2026)
framework is the right structure: data path, provenance, verification, determinism, and open-weight
versus closed-weight choices. This should be a technical report or a commentary, not a claim that
agents autonomously produced the science.

### T4: Software paper

A JOSS or SoftwareX paper for the reusable calibrated fire-source API
(`build_estate_fire_source`, `load_estate_grid`, `load_calibrated_regions`) is plausible once the
package has a stable release, installation path, tests, and a documented API. It should not
duplicate the methods paper; it should be a short software note.

## Recommended sequence

1. **Now:** release the data/software benchmark report and a Zenodo archive. This makes the work
   citable and gives the other agent a stable target.
2. **Next:** complete independent validation and a small external benchmark. Then submit the
   methods/software paper (Concept 1).
3. **In parallel:** write the calibration/transferability paper (Concept 2) if the holdout results
   support a diagnostic contribution. Do not submit it as a “validated regime.”
4. **After global target reconciliation:** write the management paper (Concept 3).
5. **Separately:** publish the BC operational guide and the agent-workflow report.

## Minimum evidence before submission

- an independent spatial or temporal validation split;
- a benchmark against at least one external fire-growth or burn-probability system;
- a hierarchical or partially pooled calibration, or a clear justification for independent fits;
- uncertainty intervals for fire-size and risk metrics;
- a global or near-global optimization baseline for the management paper;
- a clean open-data and open-code release with licences and manifests;
- a reproducibility test on a clean machine or container.

## References and sources

- Acuna, M. A., Palma, C. D., Cui, W., Martell, D. L., and Weintraub, A. (2010). Integrated spatial
  fire and forest management planning. *Canadian Journal of Forest Research* 40, 2370-2383.
  https://doi.org/10.1139/X10-151
- Ager, A. A., Barros, A. M. G., Houtman, R., Seli, R., and Day, M. A. (2020). Modelling the effect
  of accelerated forest management on long-term wildfire activity. *Ecological Modelling* 421,
  108962. https://doi.org/10.1016/j.ecolmodel.2020.108962
- BurnP3+ documentation. https://burnp3.github.io/BurnP3Plus
- Canadian Wildfire. Burn-P3 legacy. https://www.canadawildfire.org/burn-p3-english
- Duff, T. J., and Tolhurst, K. G. (2015). Operational wildfire suppression modelling: a review.
  *International Journal of Wildland Fire* 24, 735-748. https://doi.org/10.1071/WF15018
- Galván Lara, K. M., Miquelajauregui, Y., Enriquez Ocaña, L. F., Meling-López, A. E., and Neger,
  C. (2026). Machine learning and deep learning for wildfire prediction: a systematic and
  bibliometric review of methods, data practices, and reproducibility (2020-2025). *Fire* 9, 204.
  https://doi.org/10.3390/fire9050204
- Dunn, C. W., Schultz, D. T., and Musser, J. M. (2026). Designing reproducible
  large-language-model-assisted scientific analyses. *Patterns* 7, 101644.
  https://doi.org/10.1016/j.patter.2026.101644
- Finney, M. A., McHugh, C. W., Grenfell, I. C., Riley, K. L., and Short, K. C. (2011). A simulation
  of probabilistic wildfire risk components for the continental United States. *Stochastic
  Environmental Research and Risk Assessment* 25, 973-1000.
  https://doi.org/10.1007/s00477-011-0462-z
- Gonzalez-Olabarria, J. R., Carrasco, J., Pais, C., Garcia-Gonzalo, J., Palacios-Meneses, D.,
  Mahaluf-Recasens, R., Porkhum, O., and Weintraub, A. (2023). A fire spread simulator to support
  tactical management decisions for Mediterranean landscapes. *Frontiers in Forests and Global
  Change* 6, 1071484. https://doi.org/10.3389/ffgc.2023.1071484
- Hai, J., Zhang, L., Gao, C., Wang, H., and Wu, J. (2023). How does fire suppression alter the
  wildfire regime? A systematic review. *Fire* 6, 424. https://doi.org/10.3390/fire6110424
- Labarre, C., Loustau, D., Domec, J.-C., Kindu, M., and Knoke, T. (2026). Integrating wildfire
  risk into robust forest management optimization. arXiv:2609.16865.
  https://doi.org/10.48550/arXiv.2609.16865
- Pais, C., Carrasco, J., Martell, D. L., Weintraub, A., and Woodruff, D. L. (2021). Cell2Fire: a
  cell-based forest fire growth model to support strategic landscape management planning.
  *Frontiers in Forests and Global Change* 4, 692706. https://doi.org/10.3389/ffgc.2021.692706
- Paradis, G. (2026). WS3: an open-source Python framework for integrated simulation and
  optimization of forest landscape and wood supply systems. *Ecological Informatics* 103688.
  https://doi.org/10.1016/j.ecoinf.2026.103688
- Parisien, M.-A., Dawe, D. A., Miller, C., Stockdale, C. A., and Armitage, O. B. (2019).
  Applications of simulation-based burn probability modelling: a review. *International Journal of
  Wildland Fire* 28, 913-926. https://doi.org/10.1071/WF19069
- Parisien, M.-A., Kafka, V., Hirsch, K., Todd, J., Lavoie, S., and Maczek, P. (2005). Mapping
  wildfire susceptibility with the BURN-P3 simulation model. Natural Resources Canada, Canadian
  Forest Service, Northern Forestry Centre, Information Report NOR-X-405.
- Pyrologix (2019). *FSim best practices*. Technical report.
  https://pyrologix.com/wp-content/uploads/2019/11/FSimBestPractices_0.3.1.pdf
- Reimer, J., Thompson, D. K., and Povak, N. (2019). Measuring initial attack suppression
  effectiveness through burn probability. *Fire* 2, 60. https://doi.org/10.3390/fire2040060
- Sandve, G. K., Nekrutenko, A., Taylor, J., and Hovig, E. (2013). Ten simple rules for
  reproducible computational research. *PLoS Computational Biology* 9, e1003285.
  https://doi.org/10.1371/journal.pcbi.1003285
- Sturtevant, B. R., Scheller, R. M., Miranda, B. R., Shinneman, D., and Syphard, A. (2009).
  Simulating dynamic and mixed-severity fire regimes: a process-based fire extension for LANDIS-II.
  *Ecological Modelling* 220, 3380-3393. https://doi.org/10.1016/j.ecolmodel.2009.07.030
- Wilkinson, M. D., et al. (2016). The FAIR guiding principles for scientific data management and
  stewardship. *Scientific Data* 3, 160018. https://doi.org/10.1038/sdata.2016.18
- U.S. Forest Service. FSim wildfire risk simulation.
  https://research.fs.usda.gov/firelab/products/dataandtools/fsim-wildfire-risk-simulation
- LANDIS-II. https://www.landis-ii.org
- ELMFIRE. https://elmfire.io
- ForeFire. https://github.com/forefireAPI/forefire
