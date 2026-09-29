# IT-Code-Fair-2026

# The Long Way to Care

**Mobile coverage and access to health care in remote Northern Territory communities**

# CDU IT Code Fair 2026: Data Innovation Challenge
# Team: *Chepngenoh Chepkwony and Cynthia Ebele Ikegbunam*

In an emergency, you need to be able to *call* for help and *reach* care. This project joins mobile coverage records, road-network drive times, and clinic contact details for **782 remote NT communities, outstations, and town camps**, and shows where the gaps overlap. It produces a transparent **Gap Index (0–1)**, four risk tiers (Low / Moderate / High / Critical), and a single-file **offline dashboard** where anyone can search a community or clinic and see whether a call for help is likely to connect, how far care is, and who to phone.

---

## Try it and see results in 30 seconds

Open **`Outputs/dashboard_offline.html`** in any web browser. It is one self-contained file: no internet, server, or installation is needed.

- Search a **community** to see its coverage status, drive time to the nearest clinic and hospital, and what to do if there is no signal.
- Search a **clinic** to get its phone number, hours and 24/7 status.
- The map, region chart, and clinic-load chart show where the gaps are widest.
- The "Report a coverage gap" form saves a report on the device, with no signal needed.

## Rebuilding everything from the raw data

You need Python 3.11 or newer.

```bash
pip install -r requirements.txt

python datacleaning.py     # Raw Data/        -> Clean Data/
python dmerging.py         # Clean Data/      -> Processed Data/
python eda.py              # Processed Data/  -> Outputs/ (charts) + Processed Data/ (descriptive_statistics.csv)
python "gap index.py"      # Processed Data/  -> Scored Data/ + Outputs/ (more charts)
python dashboard.py        # Scored Data/     -> Outputs/dashboard_offline.html
```

Run the scripts in that order, from the project folder. Each takes seconds.

## Folder layout

```
CodeFair/
├── datacleaning.py         step 1: clean each raw source
├── dmerging.py             step 2: join the sources into one table per place
├── eda.py                  step 3: exploratory analysis and charts
├── gap index.py            step 4: Gap Index, risk tiers, clinic risk load
├── dashboard.py            step 5: build the offline dashboard
├── requirements.txt        tested library versions
├── Fonts/                  Inter and Source Serif 4 (SIL Open Font Licence), embedded in the dashboard
├── Raw Data/               the source files (downloaded, or built from downloads: see "Data sources")
├── Clean Data/             output of step 1
├── Processed Data/         output of steps 2 and 3
├── Scored Data/            output of step 4: communities_scored.csv, clinics_scored.csv
└── Outputs/                charts and dashboard_offline.html
```

If `Fonts/` is missing, the dashboard still works and falls back to the computer's own fonts. Each script also works if it is accidentally placed inside its input folder instead of beside it.

---

## Key findings

- **429 of 782** communities (54.9%) have no confirmed way to call for help: 423 were never recorded in the NT Government list and 6 are listed as having none.
- The median road time from a remote place to a hospital emergency department is **3 h 56 min**, and **340 places** are more than 4 hours away. **85 places** have no mapped road to any hospital.
- **469 places** have 20 km or more of unsealed road on their fastest route to hospital, which puts them at risk of wet-season cut-off.
- **49 of 91** remote clinics list no 24/7 emergency service. **210 communities** that cannot call for help have, as their nearest own clinic, one without a listed 24/7 service.
- The Critical tier is dominated by small, kin-based homelands: **98%** of Critical-tier communities are Family Outstations.

The methodology, full findings and recommendations are in the project report. Every figure above is computed by the scripts from `Raw Data/`.

## Data sources

All sources were retrieved on 22 September 2026. "Downloaded" files are kept as published, apart from renaming. "Built" files were prepared by the team from the source named, because the source publishes no downloadable file or only a wider dataset.

| # | Dataset | Publisher | Link | Raw Data file | Used for |
|---|---|---|---|---|---|
| 1 | Mobile Phone Coverage in Remote Areas of the NT 2022 | NT Government Open Data | [dataset](https://data.nt.gov.au/dataset/mobile-phone-coverage-in-remote-areas-of-the-nt) · [file](https://data.nt.gov.au/dataset/f39b9805-e333-4ce3-abae-d3a7e56284fa/resource/65a7e5d8-ac73-44e8-b87c-d691653d86b3/download/mobile-coverage-all-sites.xlsx) | `ntg_mobile_coverage_remote_areas_2022.xlsx` (downloaded) | Covered sites, cell type, providers |
| 2 | Remote Communities with 3G/4G Mobile Coverage 2021 | NT Government Open Data | [dataset](https://data.nt.gov.au/dataset/remote-communities-with-mobile-coverage) · [file](https://data.nt.gov.au/dataset/0f192908-d6ff-40ec-b12d-3a4ca8090a33/resource/51f89385-b9d4-468e-b271-8fba918d6975/download/communities-with-mobile-coverage.xlsx) | `ntg_remote_communities_mobile_2021.xlsx` (downloaded) | The 782 places, with coordinates and coverage status |
| 3 | 2025 mobile network site registers (Telstra, Optus, Optus–TPG MOCN, TPG) | ACCC Mobile Infrastructure Report | [data release](https://data.gov.au/data/dataset/accc-mobile-infrastructure-report-data-release) · [report](https://www.accc.gov.au/by-industry/telecommunications-and-internet/mobile-services-regulation/mobile-infrastructure-report) | `mobile-sites-telstra-2025.csv`, `mobile-sites-optus-2025.csv`, `mobile-sites-tpg-2025.csv`, `mobile-sites-optus-tpg-mocn-2025.csv` (downloaded) | Coverage gained since 2021/2022 |
| 4 | Remote health services contact list | NT Government (nt.gov.au) | [page](https://nt.gov.au/wellbeing/remote-health/remote-health-services) | `ntg_remote_health_clinics_2026.csv` (built from the page's tables), `clinics_geocoded.csv` (built: the clinic list plus coordinates) | 91 clinics: phone, hours, 24/7 emergency |
| 5 | National Healthdirect Health Facilities | Geoscience Australia | [landing page](https://researchdata.edu.au/national-healthdirect-health-facilities/3425583) · [CSV](https://d28rz98at9flks.cloudfront.net/149331/149331_01_1.csv) | `ga_healthdirect_facilities_nt_2025.csv` (NT rows only), `hospitals_ed_nt.csv` (built: six hospital emergency departments) | Clinic and hospital coordinates |
| 6 | National Roads | Geoscape, hosted on the Digital Atlas of Australia | [dataset](https://digital.atlas.gov.au/datasets/national-roads-2) · [about](https://digital.atlas.gov.au/datasets/national-roads-2/about) | `road_routing_results.csv`, `road_network_summary.csv` (built from the road network) | Road network and pre-computed drive times |
| 7 | Database of past tropical cyclone tracks | Bureau of Meteorology | [page](https://www.bom.gov.au/cyclone/tropical-cyclone-knowledge-centre/databases/) · [CSV](https://www.bom.gov.au/clim_data/IDCKMSTM0S.csv) | `bom_cyclone_exposure_communities.csv` (built: track counts near each community) | Cyclone exposure per place since 2000 |
| 8 | Potentially preventable hospitalisations 2017–18 to 2023–24 | AIHW, CC BY 4.0 | [report data page](https://www.aihw.gov.au/reports/primary-health-care/potentially-preventable-hospitalisations-2017-2024/data) | `aihw_pph_context.csv` (built: figures taken from the report) | Health-outcome context |
| 9 | First Nations Digital Inclusion (ADII) | RMIT, Swinburne, Telstra, ADM+S | [landing page](https://www.digitalinclusionindex.org.au/first-nations-digital-inclusion/) | `adii_first_nations_scores.xlsx` (exported from the ADII 2025 outcomes report) | Digital inclusion by remoteness |

Sources 8 and 9 are cited as external context and are not part of the Gap Index.

## How the Gap Index works

Four risk components are rank-normalised to a 0–1 scale (0 is best-off, 1 is worst-off): whether a community has a confirmed way to call for help, drive time to the nearest clinic, drive time to the nearest hospital, and whether a sealed road connects it. The **Gap Index is their equal-weighted mean**, and communities are split into risk tiers by quartile (about 195–196 per tier).

A drive time that cannot be calculated, almost always because the place is too remote to be routed, is scored as maximum risk instead of being dropped. Alternative weightings and a fifth input were tested, and all agreed on the same top-20 communities (Spearman ρ ≥ 0.99), so the simple equal weighting is used. The variables are not normally distributed, so the analysis uses non-parametric statistics throughout (medians, Spearman correlation, Kruskal–Wallis, Mann–Whitney).

## Reproducibility

The whole pipeline rebuilds from `Raw Data/` alone, with no internet connection, API key or manual step.

- **Deterministic.** No random sampling, no seeds and no timestamps in the outputs. Running the five scripts twice from a clean copy produced byte-for-byte identical files: all 31 outputs matched.
- **Portable.** Every path is relative to the script's own location, so it runs the same on Windows, macOS or Linux.
- **Pinned.** `requirements.txt` lists the tested versions: Python 3.11, pandas 3.0.2, numpy 2.4.4, scipy 1.17.1, matplotlib 3.10.9, seaborn 0.13.2, openpyxl 3.1.5.
- **One exception.** Drive times were computed once from the National Roads network (48,391 segments, 125,978 km) and are supplied as inputs (`road_routing_results.csv`, `road_network_summary.csv`). The scripts read and join that routing; they do not recompute the road graph. Regenerating it would need a separate graph-building step that is not included.

## Prototype scope

The dashboard is a working, interactive proof of concept, not a deployed service.

- **Works today:** search, map filtering, clinic phone numbers and hours, what-to-do guidance for places with no recorded coverage, and an on-device coverage-gap report form.
- **Not yet:** reports stay in one browser on one device and reach nobody until a person passes on the report code. The data is a fixed snapshot and does not refresh.
- **Next steps:** a shared reporting channel (such as SMS or a health-service inbox), a refresh step when source lists change, distribution through remote health services and Aboriginal community-controlled health organizations, and wet-season road-closure data.

## Limitations

- The 2021/2022 coverage lists are a "guide only", even with the 2025 tower registers added. "Never recorded" does not prove there is no signal; it means nobody recorded one.
- Drive times assume the dry season. Some small outstation tracks are not in the national roads data, so a "no mapped road" place may still have a local track.
- A few hub clinics that serve several outstations are geocoded to a community coordinate.
- No patient-level data is used. The preventable-hospitalization figures are area-level context, not an estimate of harm per place.
- The population is published only for covered sites, so people living without coverage cannot be counted from official data.

## Ethics, culture, and community

No personal or health records are used. The unit of analysis is a place's access to help, not a person. Outstations are treated as homelands on Country, where the service gap follows people home. Missing data are scored as maximum risk rather than dropped or silently imputed, and data-quality problems found in official sources are reported rather than quietly corrected. The results are meant to be taken *to* communities, land councils, and health services for verification and co-design, not used as a verdict on any community.

## Credits

Data belongs to its publishers, under the licenses noted above. Fonts are Inter and Source Serif 4, licensed under the SIL Open Font License (license files are in `Fonts/`).
