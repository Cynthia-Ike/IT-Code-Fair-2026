# ===========================================================================
# DATA MERGING - The Long Way to Care
# ===========================================================================
'''
Takes the cleaned files ((Data Cleaning Process) from step 1 and puts everything into ONE table,
with one row per community. 

Note: EDA and Gap Index steps after this will actually use the merged dataset.

Two ways files get joined together here:
- By NAME: communities, routing and cyclones all use the same 782
  community names, so pandas can match them up directly.
- By DISTANCE: the coverage sites (2022 and 2025) and the clinics are
  separate lists of places, not communities, so for each community the
  nearest one is found, and checked how close it actually is.
'''

#Import libraries
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in.

'''
Self-correcting trick as the earlier scripts: if this script ends up
sitting INSIDE "Clean Data" instead of next to it, that same folder is
used as CLEAN, and Processed Data is put one level up instead of nested in.
'''
if BASE.name == "Clean Data":
    CLEAN = BASE
    PROJECT = BASE.parent
else:
    CLEAN = BASE / "Clean Data"
    PROJECT = BASE

if not CLEAN.exists():
    raise FileNotFoundError(
        f"Can't find a 'Clean Data' folder. Looked for it at:\n  {CLEAN}\n"
        f"Run clean_data_simple.py first - it creates this folder and fills "
        f"it with the 11 cleaned files this script needs.")

PROCESSED = PROJECT / "Processed Data"  # The merged files are saved here.
PROCESSED.mkdir(parents=True, exist_ok=True)

# How close a 2022/2021 site has to be to count as "covering" a community
COVERAGE_RADIUS_KM = 3

'''
For the 2025 tower data (real coordinates, not a named-place guess):
CONFIRMED = basically right there, LIKELY = a normal macro cell's rough
range on flat remote land. LIKELY is a judgement call, not a hard fact,
which is why it gets its own separate category below instead of being
lumped in with "confirmed".
'''
TOWER_CONFIRMED_KM = 3
TOWER_LIKELY_KM = 15


# Distance calculator - Haversine formula, returns distance in km
def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


'''
Nearest-neighbour finder - finds the closest row in `places` to each row
in `df`, and returns the distance plus whichever columns from `places`
are asked for.
'''
def nearest(df, places, cols):
    out = {c: [] for c in cols}
    out["distance_km"] = []
    for _, row in df.iterrows():
        d = distance_km(row["lat"], row["lon"], places["lat"], places["lon"])
        closest = d.idxmin()
        out["distance_km"].append(round(d.loc[closest], 2))
        for c in cols:
            out[c].append(places.loc[closest, c])
    return out


# ===========================================================================
# STEP A: COMMUNITY LIST
# ===========================================================================
# Every other table joins onto this one.
com = pd.read_csv(CLEAN / "communities.csv")
print("Starting with", len(com), "communities")


# ===========================================================================
# STEP B: DRIVE TIMES
# ===========================================================================
# Joined by community name.
routing = pd.read_csv(CLEAN / "routing.csv")
routing = routing.drop(columns=["lat", "lon"])  # Already have these on com
com = com.merge(routing, on="community", how="left")


# ===========================================================================
# STEP C: CYCLONE COUNTS
# ===========================================================================
# Joined by community name.
cyclones = pd.read_csv(CLEAN / "cyclones.csv")
com = com.merge(cyclones, on="community", how="left")


# ===========================================================================
# STEP D: 2022 COVERAGE SITES
# ===========================================================================
# Joined by distance - the nearest site to each community is found.
sites_2022 = pd.read_csv(CLEAN / "coverage_sites_2022.csv")
result = nearest(com, sites_2022, ["site_name", "cell_type", "provider", "population"])

com["nearest_2022_site_km"] = result["distance_km"]
com["nearest_2022_site"] = result["site_name"]
com["cell_type_2022"] = result["cell_type"]
com["provider_2022"] = result["provider"]
com["population_2022"] = result["population"]

# If the nearest site is further than the radius, it doesn't really "cover"
# this community, so those columns get blanked out instead of keeping a bad match
too_far = com["nearest_2022_site_km"] > COVERAGE_RADIUS_KM
com.loc[too_far, ["nearest_2022_site", "cell_type_2022",
                  "provider_2022", "population_2022"]] = None

print("Communities within", COVERAGE_RADIUS_KM, "km of a 2022 site:",
      com["cell_type_2022"].notna().sum())


# ===========================================================================
# STEP E: 2025 TOWER DATA
# ===========================================================================
# Joined by distance, same idea as step D.
sites_2025 = pd.read_csv(CLEAN / "mobile_sites_2025.csv")
result = nearest(com, sites_2025, ["carrier", "generation"])

com["nearest_2025_site_km"] = result["distance_km"]
com["nearest_2025_carrier"] = result["carrier"]
com["nearest_2025_gen"] = result["generation"]

print("Communities within", TOWER_CONFIRMED_KM, "km of a real 2025 tower:",
      (com["nearest_2025_site_km"] <= TOWER_CONFIRMED_KM).sum())
print("Communities within", TOWER_LIKELY_KM, "km of a real 2025 tower:",
      (com["nearest_2025_site_km"] <= TOWER_LIKELY_KM).sum())


# ===========================================================================
# STEP F: COMBINED COVERAGE STATUS
# ===========================================================================
'''
Combines all 3 coverage sources (2021 + 2022 + 2025) into one column,
can_call. Checked in order from strongest evidence to weakest.
'''
com["can_call"] = np.select(
    [
        (com["nearest_2025_site_km"] <= TOWER_CONFIRMED_KM)
            | (com["cell_type_2022"] == "Macro cell"),
        com["nearest_2025_site_km"] <= TOWER_LIKELY_KM,
        com["cell_type_2022"].isin(["Small cell", "Near a cell"]),
        com["coverage_2021"] == "Has coverage",
        com["coverage_2021"] == "No coverage",
    ],
    [
        "Macro cell nearby",
        f"Tower within {TOWER_LIKELY_KM}km (2025)",
        "Small cell or near a cell",
        "Listed: has coverage (2021)",
        "Listed: no coverage",
    ],
    default="Never recorded")

print("\ncan_call breakdown:")
print(com["can_call"].value_counts().to_string())


# ===========================================================================
# STEP G: NEAREST CLINIC
# ===========================================================================
'''
Matches each community to its own nearest clinic (joined by distance).
This is a smaller, specific list of 91 clinics, different from the
nearest_clinic column that came from the routing file in step B.
'''
clinics = pd.read_csv(CLEAN / "clinics.csv")
result = nearest(com, clinics, ["clinic", "region"])

com["nearest_own_clinic"] = result["clinic"]
com["nearest_own_clinic_km"] = result["distance_km"]
com["region"] = result["region"]

com.to_csv(PROCESSED / "communities_merged.csv", index=False)
print("\nSaved communities_merged.csv -", len(com), "rows,", com.shape[1], "columns")


# ===========================================================================
# STEP H: CLINIC-LEVEL SUMMARY
# ===========================================================================
# For each clinic, how many communities depend on it, and how many of
# those can't call for help at all.
cannot_call = com["can_call"].isin(["Never recorded", "Listed: no coverage"])

caseload = com.groupby("nearest_own_clinic").agg(
    communities_served=("community", "count"),
    communities_cant_call=("can_call", lambda s: cannot_call.loc[s.index].sum()),
    median_drive_minutes=("clinic_minutes", "median"),
).reset_index()

clinics_out = clinics.merge(caseload, left_on="clinic",
                            right_on="nearest_own_clinic", how="left")
clinics_out = clinics_out.drop(columns=["nearest_own_clinic"])
clinics_out["communities_served"] = clinics_out["communities_served"].fillna(0).astype(int)
clinics_out["communities_cant_call"] = clinics_out["communities_cant_call"].fillna(0).astype(int)

clinics_out.to_csv(PROCESSED / "clinics_merged.csv", index=False)
print("Saved clinics_merged.csv -", len(clinics_out), "rows")

print("\nBusiest clinics (most communities that can't call):")
print(clinics_out.sort_values("communities_cant_call", ascending=False)
      [["clinic", "communities_served", "communities_cant_call"]]
      .head(10).to_string(index=False))