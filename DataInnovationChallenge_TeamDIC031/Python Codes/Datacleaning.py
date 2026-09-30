# ===========================================================================
# DATA CLEANING - Reach for Help NT
# ===========================================================================
'''
There are 15 raw data files; 11 separate datasets,
plus 4 mobile tower datasets (one per carrier) combined to form the 2025 mobile coverage dataset.
Mobile coverage, clinics, hospitals, and other datasets are cleaned 
and saved to the Clean Data folder. 
The cleaning is done on a one by one basis. One file is cleaned at a time.
'''

#Import libraries
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in. 

if BASE.name == "Raw Data":
    RAW = BASE
    PROJECT = BASE.parent
else:
    RAW = BASE / "Raw Data"
    PROJECT = BASE

if not RAW.exists():
    raise FileNotFoundError(
        f"Can't find a 'Raw Data' folder. Looked for it at:\n  {RAW}\n"
        )

CLEAN = PROJECT / "Clean Data" # The cleaned files are saved here.
CLEAN.mkdir(parents=True, exist_ok=True)


# File finder - looks for a file ending in the given name inside the Raw Data folder
def find_file(name):
    matches = list(RAW.glob(f"*{name}")) 
    if not matches:
        raise FileNotFoundError(
            f"Can't find a file ending in '{name}' inside:\n  {RAW}\n"
            f"Check that 'Raw Data' actually holds all 15 source files.")
    return matches[0]

'''
Distance_km function calculates the straight-line distance between two points in km, used later to check if
a facility's coordinates are near where they should be
'''
# Distance calculator - Haversine formula, returns distance in km
def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


# ===========================================================================
# 1. REMOTE COMMUNITIES 2021 DATASET
# ===========================================================================
com = pd.read_excel(find_file("ntg_remote_communities_mobile_2021.xlsx"),
                     sheet_name="Communities")

com = com.dropna(how="all") # drop any completely blank rows (there are a few at the bottom of the sheet)

# Renames columns to be more readable and consistent with other datasets 
com = com.rename(columns={"COMMUNITY_NAME": "community",
                          "COMMUNITY_TYPE": "community_type",
                          "LATITUDE": "lat", "LONGITUDE": "lon",
                          "MOBILE_PHONE": "mobile_2021"})
com["community"] = com["community"].astype(str).str.strip().str.title()

'''
Y = has coverage
N = no coverage
Blank = never recorded
Note: Blank should NOT be treated the same as "no coverage"
'''

com["coverage_2021"] = com["mobile_2021"].map(
    {"Y": "Has coverage", "N": "No coverage"}).fillna("Never recorded")

# check the second sheet, which lists communities with mobile access
with_mobile = pd.read_excel(find_file("ntg_remote_communities_mobile_2021.xlsx"),
                             sheet_name="Communities with Mobile")
listed = set(with_mobile["COMMUNITY_NAME"].astype(str).str.strip().str.title())
com["on_mobile_sheet"] = com["community"].isin(listed)

com = com[["community", "community_type", "lat", "lon",
           "coverage_2021", "on_mobile_sheet"]]
com.to_csv(CLEAN / "communities.csv", index=False)
print("1. communities.csv saved -", len(com), "rows")


# ===========================================================================
# 2. MOBILE COVERAGE SITES 2022
# ===========================================================================
'''Only lists places that HAVE some coverage, with tower type'''

cov = pd.read_excel(find_file("ntg_mobile_coverage_remote_areas_2022.xlsx"),
                     header=4)  # real headings start on row 5
cov.columns = cov.columns.str.lower().str.replace(" ", "_")
cov = cov.rename(columns={"latitude": "lat", "longitude": "lon"})
cov["site_name"] = cov["site_name"].astype(str).str.strip().str.title()

# These columns are "YES" or blank - blank means False here
for col in ["macro_cell", "small_cell", "proximity_to_cell"]:
    cov[col] = cov[col].eq("YES")

# turn the 3 yes/no columns into one label (macro cell is strongest, checked first)
cov["cell_type"] = np.select(
    [cov["macro_cell"], cov["small_cell"], cov["proximity_to_cell"]],
    ["Macro cell", "Small cell", "Near a cell"],
    default="Not stated")

cov = cov[["site_name", "site_type", "population", "cell_type",
           "provider", "lat", "lon"]]
cov.to_csv(CLEAN / "coverage_sites_2022.csv", index=False)
print("2. coverage_sites_2022.csv saved -", len(cov), "rows")


# ===========================================================================
# 3. MOBILE NETWORK SITES 2025
# ===========================================================================
'''
Carriers are listed in separate files; Telstra, optus, tpg, and optus-tpg MOCN have separate files. Each file has a row for each tower, and columns for each frequency band the tower uses.
Real tower locations, one file per carrier. 
These files cover the WHOLE of Australia, so we have to cut them down to just the NT first.
'''
site_files = {
    "Optus": "mobile-sites-optus-2025.csv",
    "Optus-TPG MOCN": "mobile-sites-optus-tpg-mocn-2025.csv",
    "Telstra": "mobile-sites-telstra-2025.csv",
    "TPG": "mobile-sites-tpg-2025.csv",
}

#Filters to just the NT, using a bounding box
NT_LAT = (-26.5, -10.5)
NT_LON = (128.5, 138.5)

# Works out the best signal type a site offers, from its band columns
def best_generation(row, band_cols):
    has = lambda p: any(row.get(c) == "Y" for c in band_cols if c.startswith(p))
    if has("NR"):
        return "5G"
    if has("LTE"):
        return "4G"
    if has("UMTS") or has("GSM"):
        return "3G/2G"
    return "IoT-only"

all_sites = []
for carrier, fname in site_files.items():
    raw = pd.read_csv(find_file(fname))

    # the Optus-TPG file doesn't have these two columns at all - add them blank
    for col in ["Co_funded", "Round"]:
        if col not in raw.columns:
            raw[col] = np.nan

    # keeps only rows inside the NT
    in_nt = raw["Latitude"].between(*NT_LAT) & raw["Longitude"].between(*NT_LON)
    nt = raw.loc[in_nt].copy()

    # every column that isn't location/id info is a frequency band column
    other_cols = ["Year", "MNO", "RFNSA ID", "Latitude", "Longitude",
                  "Co_funded", "Co_contribution_program", "Round"]
    band_cols = [c for c in raw.columns if c not in other_cols]
    nt["generation"] = nt.apply(lambda r: best_generation(r, band_cols), axis=1)
    nt["carrier"] = carrier

    nt = nt.rename(columns={"RFNSA ID": "rfnsa_id", "Latitude": "lat",
                            "Longitude": "lon", "Co_funded": "co_funded",
                            "Round": "round"})
    all_sites.append(nt[["carrier", "rfnsa_id", "lat", "lon",
                         "generation", "co_funded", "round"]])

sites_2025 = pd.concat(all_sites, ignore_index=True)

'''
One tower can show up more than once in a file (one row per antenna
direction), so group by carrier + tower ID and keep one row per tower
'''

gen_order = {"5G": 0, "4G": 1, "3G/2G": 2, "IoT-only": 3}

def combine(group):
    best = min(group["generation"], key=lambda g: gen_order[g])
    return pd.Series({
        "lat": group["lat"].mean(),
        "lon": group["lon"].mean(),
        "generation": best,
        "co_funded": "Y" if (group["co_funded"] == "Y").any() else np.nan,
    })

sites_2025 = (sites_2025.groupby(["carrier", "rfnsa_id"])
                        .apply(combine, include_groups=False)
                        .reset_index())

sites_2025.to_csv(CLEAN / "mobile_sites_2025.csv", index=False)
print("3. mobile_sites_2025.csv saved -", len(sites_2025), "towers in the NT")

# ===========================================================================
# 4. REMOTE HEALTH CLINICS 2026
# ===========================================================================
cl = pd.read_csv(find_file("ntg_remote_health_clinics_2026.csv"))
cl = cl.rename(columns={"location": "clinic", "opening_hours": "hours"})

cl["emergency_24_7"] = cl["emergency_24_7"].map({"Y": True, "N": False})

# Fixing a few typos in the operator names, so they match the national dataset
cl["operator"] = cl["operator"].replace("NTHealth", "NT Health")

# Fixing a few typos in the opening hours, so they match the national dataset
# Opening hours lose their line breaks, so days run together
# e.g. "8:30am to 12:00pmThursday" -> add a "; " in between
cl["hours"] = cl["hours"].str.replace(r"(?<=[ap]m)(?=[A-Z0-9])", "; ", regex=True)

# Checks phone numbers are 10 digits (Australian landline with area code)
cl["phone_first"] = cl["phone"].str.split(" or ").str[0]
digits = cl["phone_first"].str.replace(r"\D", "", regex=True)
cl["phone_valid"] = digits.str.len() == 10

#Merge in the geocoded coordinates from the national dataset 
# So that there is lat/lon for every clinic
# Built by geocoding each clinic to its community

geo = pd.read_csv(find_file("clinics_geocoded.csv"))
cl = cl.merge(geo[["clinic", "lat", "lon", "geocode"]], on="clinic", how="left")

#Add in the GA clinics that are missing from the NTG dataset, so that the final list is complete.
extra = geo[geo["source"].str.startswith("GA")].copy()
extra["emergency_24_7"] = False   # unknown -> assume no 24/7, safer default
extra["phone_first"] = np.nan
extra["phone_valid"] = False
cl = pd.concat([cl, extra[cl.columns]], ignore_index=True)

cl.to_csv(CLEAN / "clinics.csv", index=False)
print("4. clinics.csv saved -", len(cl), "rows")


# ===========================================================================
# 5. HOSPITAL EMERGENCY DEPARTMENTS

# ===========================================================================
#Hospitals in NT
hosp = pd.read_csv(find_file("hospitals_ed_nt.csv"))
hosp.to_csv(CLEAN / "hospitals.csv", index=False)
print("5. hospitals.csv saved -", len(hosp), "rows")


# ===========================================================================
# 6. NATIONAL HEALTHDIRECT FACILITIES
# ===========================================================================
# Double check the GA dataset, because it has some errors in it 
# (e.g. a couple of rows labelled "Hospital" that aren't really hospitals)
ga = pd.read_csv(find_file("ga_healthdirect_facilities_nt_2025.csv"))

# 2 rows are labelled "Hospital" but are not really hospitals
not_hosp = (ga["organisation_name"].isin(["Tkc Production",
                                          "Imanpa Community Health Centre"])
            & (ga["ga_class"] == "Hospital"))
ga = ga[~not_hosp]

# Checks each facility isn't miles away from the suburb it says it's in
places = com[["community", "lat", "lon"]].rename(
    columns={"community": "suburb", "lat": "c_lat", "lon": "c_lon"})
ga["suburb"] = ga["suburb"].astype(str).str.strip().str.title()
ga = ga.merge(places, on="suburb", how="left")
ga["km_from_suburb"] = distance_km(ga["latitude"], ga["longitude"],
                                   ga["c_lat"], ga["c_lon"]).round(0)

ga = ga.drop(columns=["c_lat", "c_lon"])
ga.to_csv(CLEAN / "ga_facilities.csv", index=False)
print("6. ga_facilities.csv saved -", len(ga), "rows")


# ===========================================================================
# 7. ROAD ROUTING RESULTS
# ===========================================================================
'''
The road routing results are a set of pre-calculated drive times
and distances from each community to the nearest clinic and hospital.
Calculated on the real road network.
'''
rt = pd.read_csv(find_file("road_routing_results.csv"))
rt = rt.rename(columns={"community_name": "community"})
rt["community"] = rt["community"].astype(str).str.strip().str.title()

# -1 is a code meaning "no road route found" - not a real number, so blank it
route_cols = ["clinic_road_km", "clinic_minutes", "hospital_road_km",
              "hospital_minutes", "hospital_minutes_sealed_only"]
rt[route_cols] = rt[route_cols].replace(-1, np.nan)

#If there's no road to hospital at all, unsealed_km should be blank too,
# Not 0 (0 looks like "fully sealed", which is wrong)
rt.loc[rt["hospital_minutes"].isna(), "hospital_unsealed_km"] = np.nan

# blank sealed-only time is a real answer ("can't get there on sealed roads
# alone"), so turn it into a flag instead of leaving it looking like missing data
rt["sealed_route_exists"] = rt["hospital_minutes_sealed_only"].notna()

# two different places are both called "Brumby Plains" (one is a 2022 site),
# so rename one of them or the join in the next step would break
dupe = (rt["community"] == "Brumby Plains") & (rt["lat"].round(3) == -17.053)
rt.loc[dupe, "community"] = "Brumby Plains (2022 Site)"

# flag communities far from any mapped road - their drive time is less certain
rt["far_from_road"] = rt["snap_km"] > 10

rt = rt.drop(columns=["idx", "road_component_nodes", "clinic_dest_idx",
                      "hospital_idx"])
rt.to_csv(CLEAN / "routing.csv", index=False)
print("7. routing.csv saved -", len(rt), "rows")


# ===========================================================================
# 8. CYCLONE EXPOSURE
# ===========================================================================
# How many cyclone tracks have passed near each community since 2000.
tc = pd.read_csv(find_file("bom_cyclone_exposure_communities.csv"))
tc = tc.rename(columns={"community_name": "community",
                        "tc_systems_within_200km_2000on": "cyclones_200km",
                        "severe_tc_within_100km_2000on": "severe_cyclones_100km"})
tc["community"] = tc["community"].astype(str).str.strip().str.title()

dupe = (tc["community"] == "Brumby Plains") & (tc["lat"].round(3) == -17.053)
tc.loc[dupe, "community"] = "Brumby Plains (2022 Site)"

tc = tc[["community", "cyclones_200km", "severe_cyclones_100km"]]
tc.to_csv(CLEAN / "cyclones.csv", index=False)
print("8. cyclones.csv saved -", len(tc), "rows")


# ===========================================================================
# 9. ROAD NETWORK SUMMARY
# ===========================================================================
#Total km of road in the NT, split by type and surface.
roads = pd.read_csv(find_file("road_network_summary.csv"))
roads["hierarchy"] = roads["hierarchy"].str.title()
roads["surface"] = roads["surface"].replace("(not recorded)", "Not recorded").str.title()
roads["pct_of_km"] = (roads["km"] / roads["km"].sum() * 100).round(1)
roads.to_csv(CLEAN / "road_summary.csv", index=False)
print("9. road_summary.csv saved -", len(roads), "rows")


# ===========================================================================
# 10. PREVENTABLE HOSPITALISATIONS (AIHW)
# ===========================================================================
# Context data: the health cost of poor access to care.
pph = pd.read_csv(find_file("aihw_pph_context.csv"))
pph["start_year"] = pph["year"].str[:4].astype(int)  # "2023-24" -> 2023
pph = pph.rename(columns={"asr_per_100k": "rate_per_100k"})
pph.to_csv(CLEAN / "pph.csv", index=False)
print("10. pph.csv saved -", len(pph), "rows")


# ===========================================================================
# 11. DIGITAL INCLUSION INDEX (ADII)
# ===========================================================================
# The ADII is a score out of 100, with a gap to the national average.
raw = pd.read_excel(find_file("adii_first_nations_scores.xlsx"),
                     header=None, names=["group", "score", "gap"])

rows, section = [], None
for group, score, gap in raw.itertuples(index=False):
    if pd.isna(group):
        continue                # spacer row, skip it
    if pd.isna(score):
        section = group         # this row is a heading, note it
        continue
    rows.append({"section": section, "group": group,
                 "adii_score": round(score, 1),
                 "gap": None if pd.isna(gap) else round(gap, 1)})

adii = pd.DataFrame(rows)
adii.to_csv(CLEAN / "adii.csv", index=False)
print("11. adii.csv saved -", len(adii), "rows")

print("\nAll 15 raw files cleaned and saved to", CLEAN)