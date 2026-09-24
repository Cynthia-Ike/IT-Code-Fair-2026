# =============================================================================
# STEP 2: COMPILING / MERGING THE DATA
# Project: Reach for Help NT - the cost of disconnectivity in remote health
# CDU IT Code Fair 2026, Data Innovation Challenge
#
# Goal: turn the cleaned files (Step 1) into TWO tables:
#   communities_merged.csv - one row per remote community
#   clinics_merged.csv     - one row per clinic, with its community caseload
#
# Why this has to happen before EDA:
#   Every interesting question in this project ("does coverage relate to drive
#   time?", "which clinic serves the most communities that can't call?") needs
#   columns that currently live in different files. Merge once, here, rather
#   than re-joining files inside every EDA chart.
#
# Two kinds of join are used:
#   1. Join by NAME     - communities, routing and cyclones all list the same
#                          782 communities, so we match them by name.
#   2. Join by DISTANCE - coverage sites and clinics come from lists that
#                          don't share names with the community list, so for
#                          each community we find the NEAREST match by
#                          straight-line distance instead.
#
# How to run (from the project folder, after clean_data.py has been run):
#   python merge_data.py
# =============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

CLEAN = Path(__file__).resolve().parent / "data" / "clean"
PROCESSED = Path(__file__).resolve().parent / "data" / "processed"
print("Looking for cleaned files in:", CLEAN)   # delete this line once it works
PROCESSED.mkdir(parents=True, exist_ok=True)

# A site counts as covering a community if it is within this many kilometres.
COVERAGE_RADIUS_KM = 3


# -----------------------------------------------------------------------------
# Helper: straight-line distance in km between two points (haversine formula).
# Used to find the nearest coverage site and the nearest clinic.
# -----------------------------------------------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


# =============================================================================
# STEP A: start with the community list. This is the "spine" of the whole
# project - every other table's data gets attached onto these rows.
# =============================================================================
com = pd.read_csv(CLEAN / "communities.csv")
print(f"Starting spine: {len(com)} communities")


# =============================================================================
# STEP B: join the routing results (nearest clinic / hospital + drive times).
# NAME join - routing.csv has one row per community, same names as the spine.
# =============================================================================
routing = pd.read_csv(CLEAN / "routing.csv")

# routing.csv has its own lat/lon columns too. Keep only ONE copy of the
# coordinates or pandas silently renames both to lat_x / lat_y.
routing = routing.drop(columns=["lat", "lon"])

before = len(com)
com = com.merge(routing, on="community", how="left")
assert len(com) == before, "merge must not create extra rows"

no_match = com["clinic_minutes"].isna() & com["hospital_minutes"].isna()
print(f"Communities with no routing match at all: {int(no_match.sum())} "
      f"(genuinely isolated places, not a join error)")


# =============================================================================
# STEP C: join the cyclone exposure counts. Also a NAME join.
# =============================================================================
cyclones = pd.read_csv(CLEAN / "cyclones.csv")
com = com.merge(cyclones, on="community", how="left")
assert len(com) == before, "merge must not create extra rows"


# =============================================================================
# STEP D: join the 2022 coverage sites - DISTANCE join.
# For every community, find the nearest 2022 site. If it's within
# COVERAGE_RADIUS_KM, that site's details count as this community's coverage.
# =============================================================================
sites = pd.read_csv(CLEAN / "coverage_sites_2022.csv")

nearest_site_name, nearest_site_km = [], []
nearest_cell_type, nearest_provider, nearest_population = [], [], []

for _, community_row in com.iterrows():
    d = distance_km(community_row["lat"], community_row["lon"],
                    sites["lat"], sites["lon"])
    closest = d.idxmin()
    closest_km = d.loc[closest]

    if closest_km <= COVERAGE_RADIUS_KM:
        nearest_site_name.append(sites.loc[closest, "site_name"])
        nearest_site_km.append(round(closest_km, 2))
        nearest_cell_type.append(sites.loc[closest, "cell_type"])
        nearest_provider.append(sites.loc[closest, "provider"])
        nearest_population.append(sites.loc[closest, "population"])
    else:
        nearest_site_name.append(None)
        nearest_site_km.append(round(closest_km, 2))
        nearest_cell_type.append(None)
        nearest_provider.append(None)
        nearest_population.append(np.nan)

com["nearest_2022_site"] = nearest_site_name
com["nearest_2022_site_km"] = nearest_site_km
com["cell_type_2022"] = nearest_cell_type
com["provider_2022"] = nearest_provider
com["population_2022"] = nearest_population

covered_2022 = com["cell_type_2022"].notna().sum()
print(f"Communities matched to a 2022 coverage site within "
      f"{COVERAGE_RADIUS_KM} km: {covered_2022}")


# =============================================================================
# STEP E: combine the 2021 list and the 2022 sites into ONE coverage category.
# A macro cell (a full mobile tower) is the strongest evidence, checked first.
# This is a simple rule, not a statistical model - scoring/weighting is Step 4.
# =============================================================================
com["can_call"] = np.select(
    [com["cell_type_2022"].eq("Macro cell"),
     com["cell_type_2022"].isin(["Small cell", "Near a cell"]),
     com["coverage_2021"].eq("Has coverage"),
     com["coverage_2021"].eq("No coverage")],
    ["Macro cell nearby", "Small cell or near a cell",
     "Listed: has coverage (2021)", "Listed: no coverage"],
    default="Never recorded")

print("\ncan_call breakdown:")
print(com["can_call"].value_counts().to_string())


# =============================================================================
# STEP F: assign each community to ITS OWN nearest clinic, from clinics.csv.
#
# This is different from Step B's "nearest_clinic" (which came from
# routing.csv and can point to any destination in a much bigger national list,
# including urban GP practices). Here we deliberately restrict the search to
# only the 91 clinics we have full detail for, because that is the list the
# clinic-level file in Step G will be built from - every name this step
# produces is guaranteed to exist in clinics.csv, so that join can never fail.
#
# We get two things from the same distance search:
#   nearest_own_clinic  - which of our 91 clinics is physically closest
#   region              - that clinic's health region (clinics.csv has this;
#                         the community list itself does not)
# =============================================================================
clinics = pd.read_csv(CLEAN / "clinics.csv")

nearest_own_clinic, nearest_own_clinic_km, region_of_nearest_clinic = [], [], []

for _, community_row in com.iterrows():
    d = distance_km(community_row["lat"], community_row["lon"],
                    clinics["lat"], clinics["lon"])
    closest = d.idxmin()
    nearest_own_clinic.append(clinics.loc[closest, "clinic"])
    nearest_own_clinic_km.append(round(d.loc[closest], 1))
    region_of_nearest_clinic.append(clinics.loc[closest, "region"])

com["nearest_own_clinic"] = nearest_own_clinic
com["nearest_own_clinic_km"] = nearest_own_clinic_km
com["region"] = region_of_nearest_clinic

# The only communities with no region are the ones whose nearest clinic is one
# of the 3 we added from the national dataset in Step 1 (Papunya, Wilora,
# Ti Tree) - that source does not record a region. Left blank, not guessed.
missing_region = com["region"].isna().sum()
print(f"\nCommunities with no region: {int(missing_region)} "
      f"(nearest clinic has no region recorded - see data_quality_log.csv)")


# =============================================================================
# CHECKS before saving the communities file.
# =============================================================================
assert len(com) == before, "row count must still match the original spine"
assert com["community"].is_unique, "one row per community, no duplicates"
assert com["can_call"].isna().sum() == 0, "every community must get a category"

com.to_csv(PROCESSED / "communities_merged.csv", index=False)
print(f"\nSaved: data/processed/communities_merged.csv "
      f"({len(com)} rows, {com.shape[1]} columns)")


# =============================================================================
# STEP G: build the CLINIC-level file - one row per clinic, with the caseload
# of communities that rely on it.
#
# This answers a different question than the communities file: not "can this
# community call for help", but "how many communities is each clinic actually
# serving, and how many of THOSE can't call at all". A clinic with a large
# can't-call caseload is a strong candidate for extra investment, even if no
# single community on its own looks especially bad.
#
# We group communities_merged by nearest_own_clinic from Step F, so every
# group name is guaranteed to match a row in clinics.csv.
# =============================================================================

# "Cannot call for help" = either of the two worst can_call categories.
cannot_call = com["can_call"].isin(["Never recorded", "Listed: no coverage"])

caseload = com.groupby("nearest_own_clinic").agg(
    communities_served=("community", "count"),
    communities_cant_call=("can_call", lambda s: cannot_call.loc[s.index].sum()),
    median_drive_minutes=("clinic_minutes", "median"),
    max_drive_minutes=("clinic_minutes", "max"),
).reset_index()

clinics_out = clinics.merge(
    caseload, left_on="clinic", right_on="nearest_own_clinic", how="left")
clinics_out = clinics_out.drop(columns=["nearest_own_clinic"])

# A clinic that is nobody's nearest gets 0 communities, not a blank cell -
# "zero" and "unknown" mean different things, and zero is the true answer.
clinics_out["communities_served"] = clinics_out["communities_served"].fillna(0).astype(int)
clinics_out["communities_cant_call"] = clinics_out["communities_cant_call"].fillna(0).astype(int)

no_caseload = (clinics_out["communities_served"] == 0).sum()
print(f"\nClinics that are not the nearest own-list clinic for any community: "
      f"{int(no_caseload)}")
print(clinics_out.loc[clinics_out["communities_served"] == 0, "clinic"].tolist())

assert clinics_out["clinic"].is_unique, "one row per clinic, no duplicates"
assert len(clinics_out) == len(clinics), "must not gain or lose clinics"

clinics_out.to_csv(PROCESSED / "clinics_merged.csv", index=False)
print(f"\nSaved: data/processed/clinics_merged.csv "
      f"({len(clinics_out)} rows, {clinics_out.shape[1]} columns)")

print("\nBusiest clinics by can't-call caseload:")
print(clinics_out.sort_values("communities_cant_call", ascending=False)
      [["clinic", "region", "communities_served", "communities_cant_call"]]
      .head(10).to_string(index=False))