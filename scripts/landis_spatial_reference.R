## Small spatial Biomass_core reference run.
## Requires WS4_R_LIB (isolated library) and BIOMASS_CORE_DIR (module parent) to be set.
## Output is written to P200_OUT (default: current directory).
.libPaths(c(Sys.getenv("WS4_R_LIB"), .libPaths()))
suppressPackageStartupMessages({
  library(SpaDES.core); library(LandR); library(terra); library(data.table)
})
options(reproducible.useCache = FALSE, spades.useRequire = FALSE, LandR.verbose = 1)

lib <- Sys.getenv("WS4_R_LIB")
module_parent <- Sys.getenv("BIOMASS_CORE_DIR")
out_dir <- Sys.getenv("P200_OUT", ".")
if (!nzchar(lib) || !nzchar(module_parent)) {
  stop("set WS4_R_LIB and BIOMASS_CORE_DIR")
}
dir.create(file.path(out_dir, "inputs"), showWarnings = FALSE, recursive = TRUE)
dir.create(file.path(out_dir, "outputs"), showWarnings = FALSE, recursive = TRUE)
dir.create(file.path(out_dir, "cache"), showWarnings = FALSE, recursive = TRUE)

rtm <- rast(
  nrows = 10, ncols = 10, xmin = 0, xmax = 1000, ymin = 0, ymax = 1000,
  crs = "+proj=lcc +lat_0=0 +lon_0=-95 +lat_1=49 +lat_2=77 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs",
  vals = 1
)
sa <- as.polygons(rtm, dissolve = TRUE)
species <- data.table(
  species = c("Pice_Gla", "Popu_Tre"), Area = factor("Acadian"),
  longevity = c(200L, 150L), sexualmature = c(30L, 20L),
  shadetolerance = c(3L, 1L), firetolerance = c(2L, 2L),
  seeddistance_eff = c(100L, 1000L), seeddistance_max = c(303L, 5000L),
  resproutprob = c(0, 0.9), mortalityshape = c(15L, 25L),
  growthcurve = c(0.25, 0.25), resproutage_min = c(0L, 10L),
  resproutage_max = c(0L, 150L), postfireregen = factor(c("none", "resprout")),
  wooddecayrate = c(0.02, 0.07), leaflongevity = c(3L, 1L),
  leafLignin = c(0.2, 0.1), hardsoft = factor(c("soft", "hard"))
)
species[, speciesCode := factor(species)]
speciesEcoregion <- data.table(
  ecoregionGroup = factor(rep("1", 2)),
  speciesCode = factor(c("Pice_Gla", "Popu_Tre")),
  establishprob = c(0.5, 0.5), maxB = c(30000L, 30000L),
  maxANPP = c(1000, 1000), year = 0L
)
ecoregion <- data.table(active = "yes", ecoregionGroup = factor("1"))
minRelativeB <- data.table(
  ecoregionGroup = factor("1"), X1 = 0.15, X2 = 0.25, X3 = 0.35, X4 = 0.45, X5 = 0.55
)
ecoregionMap <- rtm
values(ecoregionMap) <- 1
levels(ecoregionMap) <- data.frame(value = 1, ecoregionGroup = "1")
pixelGroupMap <- rtm
values(pixelGroupMap) <- rep(c(1, 2), length.out = ncell(rtm))
biomassMap <- rtm
values(biomassMap) <- 2000
speciesLayers <- c(rtm, rtm)
names(speciesLayers) <- c("Pice_Gla", "Popu_Tre")
values(speciesLayers) <- 0.5
cohortData <- data.table(
  pixelGroup = rep(1:2, each = 2), ecoregionGroup = factor(rep("1", 4)),
  speciesCode = factor(rep(c("Pice_Gla", "Popu_Tre"), 2)),
  age = c(20L, 30L, 20L, 30L), B = c(1000L, 1000L, 1000L, 1000L)
)
sppEquiv <- data.table(
  LandR = c("Pice_Gla", "Popu_Tre"), Boreal = c("Pice_Gla", "Popu_Tre"),
  speciesCode = factor(c("Pice_Gla", "Popu_Tre")),
  Type = factor(c("Conifer", "Broadleaf"))
)
sppColorVect <- c(Pice_Gla = "#1b9e77", Popu_Tre = "#d95f02", Mixed = "#7570b3")
treedFire <- data.table(pixelIndex = integer(), pixelGroup = integer(), burnTime = numeric())

set.seed(20261114)
sim <- simInitAndSpades(
  times = list(start = 0, end = 10),
  modules = list("Biomass_core"),
  params = list(Biomass_core = list(
    sppEquivCol = "LandR", successionTimestep = 10, .plots = NA,
    .useCache = FALSE, .useParallel = 1, initialB = 10, minCohortBiomass = 9
  )),
  objects = list(
    studyArea = sa, studyAreaReporting = sa, rasterToMatch = rtm, species = species,
    speciesEcoregion = speciesEcoregion, ecoregion = ecoregion,
    ecoregionMap = ecoregionMap, pixelGroupMap = pixelGroupMap, biomassMap = biomassMap,
    speciesLayers = speciesLayers, cohortData = cohortData, lastReg = 0,
    minRelativeB = minRelativeB, sppEquiv = sppEquiv, sppColorVect = sppColorVect,
    treedFirePixelTableSinceLastDisp = treedFire,
    columnsForPixelGroups = LandR::columnsForPixelGroups()
  ),
  paths = list(
    modulePath = module_parent, inputPath = file.path(out_dir, "inputs"),
    outputPath = file.path(out_dir, "outputs"), cachePath = file.path(out_dir, "cache")
  ),
  outputs = data.frame(objectName = "simulationOutput", saveTime = c(0, 10), eventPriority = 1),
  debug = FALSE
)
write.csv(as.data.frame(sim$simulationOutput), file.path(out_dir, "simulationOutput.csv"), row.names = FALSE)
writeLines(capture.output(sessionInfo()), file.path(out_dir, "sessionInfo.txt"))
