# P164.8 data licence and attribution audit

Status: archive preparation

This audit records the licence position for inputs used by the calibrated fire-regime package. It
is not legal advice. Re-check the source pages before a public archive release.

## Summary

| Input | Licence / terms | Redistribution | Required action |
| --- | --- | --- | --- |
| BC VRI | Open Government Licence - British Columbia (OGL-BC 2.0) | permitted with attribution | include OGL-BC attribution and licence link |
| BC Wildfire perimeters | OGL-BC 2.0 | permitted with attribution | include BC Wildfire Service attribution |
| BC Wildfire incidents | OGL-BC 2.0 | permitted with attribution | include BC Wildfire Service attribution |
| SRTM 1 arc-second | public domain / NASA open data | permitted | cite NASA JPL SRTM DOI and acknowledge NASA/USGS |
| Open-Meteo weather | data under CC BY 4.0 | permitted with attribution | credit Open-Meteo and note modifications |
| TSA24 compiled inventory | project/public artifact | depends on source terms | keep existing provenance; do not relicense |
| Dogrib sample data | Prometheus sample archive; no explicit licence file found | unclear | do not redistribute raw Dogrib data; publish derived metrics only |
| WS4 code | Apache-2.0 | permitted | retain licence and notices |
| FireSTARR/Cell2Fire binaries | their own licences | do not bundle | cite upstream projects; link, do not redistribute |

## VRI

The BC Data Catalogue lists the VRI Forest Vegetation Composite Rank 1 Layer under the Open
Government Licence - British Columbia. The licence permits copying, modification, distribution,
and commercial use with attribution. Where no specific attribution statement is supplied, use:

> Contains information licensed under the Open Government Licence - British Columbia.

Source: https://catalogue.data.gov.bc.ca/dataset/vri-2025-forest-vegetation-composite-rank-1-layer-r1-

Licence: https://pub.data.gov.bc.ca/license/OGL-vbc2.0.pdf

## BC Wildfire perimeters and incidents

The BC fire perimeter metadata identifies the BC Ministry of Forests / BC Wildfire Service data as
licensed under the Open Government Licence - British Columbia. The current and historical perimeter
services and the incident service are the operational sources used in the calibration. Attribute:

> Fire perimeter and incident data: BC Wildfire Service, licensed under the Open Government Licence
> - British Columbia.

Source examples:

- https://open.canada.ca/data/en/dataset/cdfc2d7b-c046-4bf0-90ac-4897232619e1
- https://www.arcgis.com/home/item.html?id=fc8ed463499845d2915981764fd39f9e

## SRTM

NASA LP DAAC distributes SRTM data without restrictions on reuse and requests citation. The NASA
Earthdata guidance treats NASA-led mission data as CC0 unless marked otherwise. Cite:

> NASA JPL (2013). NASA Shuttle Radar Topography Mission Global 1 arc second [Data set]. NASA
> EOSDIS Land Processes DAAC. https://doi.org/10.5067/MEaSUREs/SRTM/SRTMGL1.003

Source: https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance

## Open-Meteo

Open-Meteo API data are offered under CC BY 4.0. The free endpoint is for non-commercial use and
has rate limits; commercial use requires a subscription. This project used the free endpoint for
public research. Attribute:

> Weather data by Open-Meteo.com (https://open-meteo.com/), licensed under CC BY 4.0; data were
> transformed into FWI inputs and fire-weather samples.

Source: https://open-meteo.com/en/license

Citation requested by Open-Meteo:

> Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo.
> https://doi.org/10.5281/ZENODO.7970649

## Dogrib sample data

The Dogrib benchmark uses the Prometheus sample archive. The local metadata records the source and
notes that no explicit licence file was found. The raw data should not be redistributed in the
repository or archive. Publish:

- the derived comparison table;
- the model versions and run configuration;
- a link to the original public sample archive;
- a statement that the raw Dogrib data are not redistributed.

Source: Prometheus Dogrib sample dataset, `Dogrib_v624.zip`, as recorded in
`notes/reports/p157-dogrib-summary.json`.

## Software

WS4 is Apache-2.0. FireSTARR, Cell2Fire, BurnP3+, SyncroSim, and Prometheus have their own licences
and should be cited and linked, not bundled into the WS4 archive. The FireSTARR benchmark used a
released binary; the binary is not redistributed here.

## Release actions

- [ ] Add the OGL-BC attribution to the layer manifest and data README.
- [ ] Add BC Wildfire Service attribution to the perimeter/incident provenance.
- [ ] Add the NASA SRTM citation and DOI.
- [ ] Add the Open-Meteo attribution and CC BY 4.0 link.
- [ ] Add the Open-Meteo software citation.
- [ ] Keep raw Dogrib data out of the release; publish derived metrics only.
- [ ] Confirm the TSA24 compiled-inventory terms with the data owner.
- [ ] Include the WS4 Apache-2.0 licence and third-party notices.
- [ ] Re-check all source pages immediately before archive submission.

## Effect on the paper

The paper can state that the public BC data are OGL-BC, SRTM is public domain/CC0, and Open-Meteo is
CC BY 4.0. It should state that the Dogrib raw sample is not redistributed because its licence is
unclear, while the derived benchmark metrics are reported. The layer archive should carry an
attribution file, not just the numerical manifest.
