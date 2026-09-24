# =============================================================================
# STEP 1: DATA CLEANING
# Project: Reach for Help NT - the cost of disconnectivity in remote health
# CDU IT Code Fair 2026, Data Innovation Challenge
#
# The question the whole project answers, for every NT remote community:
#   1. Can you call for help from here?           (mobile coverage)
#   2. How long does it take to reach care?       (road travel to clinic / ED)
#   3. How likely is it to be cut off?            (unsealed roads, cyclones)
#
# What this script does:
#   Reads each raw file from data/raw/, fixes its problems, and saves a clean
#   copy to data/clean/. It also writes a data-quality log listing every
#   problem found, which goes in the report appendix.
#
# What this script does NOT do:
#   It does not join the files together (that is Step 2) and it does not
#   analyse anything (that is Step 3). Keeping cleaning separate means that if
#   a source is updated, only this script needs to be run again.
#
# Three rules we follow:
#   - Never change the files in data/raw/.
#   - Never invent a value. If something is missing, it stays missing.
#   - Write down every fix in the log, so a marker can check our decisions.
#
# How to run (from the project folder):   python clean_data.py
# =============================================================================

from pathlib import Path

import numpy as np
import pandas as pd
RAW = Path(r"D:\CodeFair\Raw Data")   # your files are here
CLEAN = Path(__file__).resolve().parent / "data" / "clean" # saves next to the script, wherever you run it from
CLEAN.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Helper 1: find a raw file even if its name has an extra prefix
# (for example "1790132463807_adii_first_nations_scores.xlsx")
# -----------------------------------------------------------------------------
def raw_file(name):
    matches = list(RAW.glob(f"*{name}"))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} in {RAW}/")
    return matches[0]


# -----------------------------------------------------------------------------
# Helper 2: the data-quality log. Every problem we find is added here.
# -----------------------------------------------------------------------------
issues = []

def log(file, problem, rows, fix):
    issues.append({"file": file, "problem": problem,
                   "rows_affected": rows, "what_we_did": fix})


# -----------------------------------------------------------------------------
# Helper 3: make community names consistent across files.
# The NT Government writes names in CAPITALS ("YUENDUMU"); other files use
# Title Case. Joining files on name only works if every file uses the same
# style, so we convert everything to Title Case ("Yuendumu").
# -----------------------------------------------------------------------------
def tidy_name(series):
    return series.astype(str).str.strip().str.title()


# -----------------------------------------------------------------------------
# Helper 4: straight-line distance in km between two points (haversine).
# Used to check whether a facility's coordinates are where they should be.
# -----------------------------------------------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


# =============================================================================
# 1. REMOTE COMMUNITIES 2021 (NT Government)
#    One row per remote community, with its location and coverage status.
#    This is the main list every other file joins onto.
# =============================================================================
file = "ntg_remote_communities_mobile_2021.xlsx"
com = pd.read_excel(raw_file(file), sheet_name="Communities")

# Problem: one row in the sheet is completely empty.
blank_rows = com.isna().all(axis=1).sum()
com = com.dropna(how="all")
log(file, "a completely empty row inside the table", int(blank_rows),
    "removed (it has no name, location or status)")

# Rename columns to short lowercase names that are easier to type.
com = com.rename(columns={"COMMUNITY_NAME": "community",
                          "COMMUNITY_TYPE": "community_type",
                          "LATITUDE": "lat", "LONGITUDE": "lon",
                          "MOBILE_PHONE": "mobile_2021"})
com["community"] = tidy_name(com["community"])

# Problem: the coverage column has THREE values, not two.
#   Y            = listed as having mobile coverage
#   N            = listed as having no coverage
#   Not recorded = nobody recorded it either way
# "Not recorded" is NOT the same as "no coverage", so we keep it separate.
com["coverage_2021"] = com["mobile_2021"].map(
    {"Y": "Has coverage", "N": "No coverage"}).fillna("Never recorded")
log(file, "coverage is 'Not recorded' for most communities",
    int((com["coverage_2021"] == "Never recorded").sum()),
    "kept as its own category 'Never recorded' - not treated as 'no coverage'")

# Problem: the workbook's two sheets disagree about who has coverage.
# The 'Communities with Mobile' sheet should match the 'Y' rows, but it doesn't.
with_mobile = pd.read_excel(raw_file(file), sheet_name="Communities with Mobile")
listed = set(tidy_name(with_mobile["COMMUNITY_NAME"]))
flagged_y = set(com.loc[com["mobile_2021"] == "Y", "community"])
only_sheet = sorted(listed - flagged_y)
only_y = sorted(flagged_y - listed)
log(file, f"on the 'with mobile' sheet but not 'Y' on the main sheet: {only_sheet}",
    len(only_sheet), "kept the main sheet's value; added column on_mobile_sheet")
log(file, f"'Y' on the main sheet but missing from the 'with mobile' sheet: {only_y}",
    len(only_y), "kept the main sheet's value; reported as a data-quality finding")
com["on_mobile_sheet"] = com["community"].isin(listed)

# Keep only the columns we need, and check the result.
com = com[["community", "community_type", "lat", "lon",
           "coverage_2021", "on_mobile_sheet"]]
assert com["community"].is_unique, "community names must be unique to join on"
com.to_csv(CLEAN / "communities.csv", index=False)


# =============================================================================
# 2. MOBILE COVERAGE SITES 2022 (NT Government)
#    Places that HAVE coverage, with the type of tower and population.
# =============================================================================
file = "ntg_mobile_coverage_remote_areas_2022.xlsx"

# Problem: the real column headings are on row 5 of the sheet. Rows 1-4 hold
# an explanation note, so we tell pandas to skip them with header=4.
cov = pd.read_excel(raw_file(file), header=4)
cov.columns = cov.columns.str.lower().str.replace(" ", "_")
cov = cov.rename(columns={"latitude": "lat", "longitude": "lon"})
cov["site_name"] = tidy_name(cov["site_name"])

# Problem: tower type is written as "YES" or left blank. A blank here means
# "no", not "unknown", so we turn these into True/False columns.
for col in ["macro_cell", "small_cell", "proximity_to_cell"]:
    cov[col] = cov[col].eq("YES")

# Combine the three True/False columns into one readable label.
# A macro cell (full tower) is the most reliable, so it is checked first.
cov["cell_type"] = np.select(
    [cov["macro_cell"], cov["small_cell"], cov["proximity_to_cell"]],
    ["Macro cell", "Small cell", "Near a cell"],
    default="Not stated")

# Problem: population is blank for some sites.
log(file, "population is blank for some covered sites",
    int(cov["population"].isna().sum()),
    "left blank - we never guess a population")

# Important limitation: this list only contains places WITH coverage.
log(file, "the list only includes places with coverage, and the NT Government "
          "calls it 'a guide only'", len(cov),
    "absence from this list is NOT treated as proof of no coverage")

cov = cov[["site_name", "site_type", "population", "cell_type",
           "provider", "lat", "lon"]]
cov.to_csv(CLEAN / "coverage_sites_2022.csv", index=False)


# =============================================================================
# 3. REMOTE HEALTH CLINICS 2026 (nt.gov.au)
#    The clinic list: phone number, opening hours, 24/7 emergency service.
#    These details are shown to the public in the Help Finder, so mistakes
#    here are a safety issue, not just a tidiness issue.
# =============================================================================
file = "ntg_remote_health_clinics_2026.csv"
cl = pd.read_csv(raw_file(file))
cl = cl.rename(columns={"location": "clinic", "opening_hours": "hours"})

# Problem: Y/N text -> True/False, so we can count and filter it.
cl["emergency_24_7"] = cl["emergency_24_7"].map({"Y": True, "N": False})
assert cl["emergency_24_7"].notna().all(), "found a value that is not Y or N"

# Problem: the same operator is spelled two ways ("NT Health" / "NTHealth").
bad_spelling = (cl["operator"] == "NTHealth").sum()
cl["operator"] = cl["operator"].replace("NTHealth", "NT Health")
log(file, "operator written as 'NTHealth' instead of 'NT Health'",
    int(bad_spelling), "corrected spelling")

# Problem: opening hours lose their line breaks, so days run together:
#   "8:30am to 12:00pmThursday 1:00pm"  ->  "8:30am to 12:00pm; Thursday 1:00pm"
# The rule: after "am" or "pm", if a capital letter or digit follows
# immediately, insert "; " between them.
run_on = cl["hours"].str.contains(r"[ap]m[A-Z0-9]", na=False).sum()
cl["hours"] = cl["hours"].str.replace(r"(?<=[ap]m)(?=[A-Z0-9])", "; ", regex=True)
log(file, "opening hours with days run together (e.g. '4:00pmThursday')",
    int(run_on), "inserted '; ' between the joined parts")

# Problem: missing phone numbers and missing opening hours.
log(file, "phone number missing", int(cl["phone"].isna().sum()),
    "left blank - the Help Finder tells people to call 000 instead")
log(file, "opening hours missing", int(cl["hours"].isna().sum()),
    "left blank - shown as 'hours not listed'")

# Problem: some phone numbers are the wrong length. An Australian landline
# with area code has exactly 10 digits (e.g. 08 8956 4030).
# One cell also holds two numbers ("08 8956 7433 or 08 8951 6040").
cl["phone_first"] = cl["phone"].str.split(" or ").str[0]
digits = cl["phone_first"].str.replace(r"\D", "", regex=True)
cl["phone_valid"] = digits.str.len() == 10
bad_phones = cl.loc[cl["phone"].notna() & ~cl["phone_valid"], ["clinic", "phone"]]
log(file, f"phone numbers that are not 10 digits: {bad_phones.values.tolist()}",
    len(bad_phones),
    "NOT corrected (we cannot know the right number) - flagged phone_valid=False "
    "so the app can warn users; to be reported to NT Health")
log(file, "one cell contains two phone numbers joined by 'or'",
    int(cl["phone"].str.contains(" or ", na=False).sum()),
    "kept the full text; phone_first holds the first number for the 'call' button")

# Add map coordinates. The nt.gov.au list has no coordinates, so each clinic
# was matched to its community's coordinates in an earlier step
# (clinics_geocoded.csv). We join them on the clinic name.
geo = pd.read_csv(raw_file("clinics_geocoded.csv"))
cl = cl.merge(geo[["clinic", "lat", "lon", "geocode"]], on="clinic", how="left")
assert cl["lat"].notna().all(), "every clinic should have coordinates"

# Three health centres appear in the national Healthdirect data but are missing
# from the nt.gov.au list. We add them so no community loses its nearest clinic.
extra = geo[geo["source"].str.startswith("GA")].copy()
# Their 24/7 status is unknown. We use the SAFE assumption, "no 24/7 service",
# so the Help Finder tells people to call 000 rather than promising a nurse.
extra["emergency_24_7"] = False
extra["phone_first"] = np.nan
extra["phone_valid"] = False
cl = pd.concat([cl, extra[cl.columns]], ignore_index=True)
log(file, f"health centres missing from the nt.gov.au list: "
          f"{extra['clinic'].tolist()}", len(extra),
    "added from GA Healthdirect; 24/7 status unknown, so set to False (safe choice)")

cl.to_csv(CLEAN / "clinics.csv", index=False)


# =============================================================================
# 4. HOSPITAL EMERGENCY DEPARTMENTS
#    The six public hospital EDs in the NT. Small file, so we just check it.
# =============================================================================
file = "hospitals_ed_nt.csv"
hosp = pd.read_csv(raw_file(file))
assert len(hosp) == 6 and hosp.notna().all().all(), "expected 6 complete rows"
hosp.to_csv(CLEAN / "hospitals.csv", index=False)


# =============================================================================
# 5. NATIONAL HEALTHDIRECT FACILITIES (Geoscience Australia)
#    Used to check the clinic list. We found several errors in it.
# =============================================================================
file = "ga_healthdirect_facilities_nt_2025.csv"
ga = pd.read_csv(raw_file(file))

# Problem: two entries labelled "Hospital" are not hospitals.
not_hosp = ga["organisation_name"].isin(["Tkc Production",
                                          "Imanpa Community Health Centre"])
not_hosp = not_hosp & (ga["ga_class"] == "Hospital")
log(file, f"labelled as hospitals but are not: "
          f"{ga.loc[not_hosp, 'organisation_name'].tolist()}",
    int(not_hosp.sum()),
    "excluded from the hospital list (Imanpa is a remote clinic)")
ga = ga[~not_hosp]

# Problem: some facilities are in the wrong place. We check each facility
# against the community named in its 'suburb' column and flag any more than
# 50 km apart. A human then decides which of the two is wrong.
places = com[["community", "lat", "lon"]].rename(
    columns={"community": "suburb", "lat": "c_lat", "lon": "c_lon"})
ga["suburb"] = tidy_name(ga["suburb"])
ga = ga.merge(places, on="suburb", how="left")
ga["km_from_suburb"] = distance_km(ga["latitude"], ga["longitude"],
                                   ga["c_lat"], ga["c_lon"]).round(0)
far = ga[ga["km_from_suburb"] > 50]
log(file, f"coordinates more than 50 km from the named suburb: "
          f"{far[['organisation_name', 'km_from_suburb']].values.tolist()}",
    len(far),
    "flagged. Mutitjulu: the coordinates are wrong (570 km away). The rest "
    "list 'Katherine' as a postal suburb; their coordinates are at the right "
    "community, except Manyallaluk (next row)")

# Found by comparing coordinates by eye: Manyallaluk is placed at Barunga.
log(file, "Manyallaluk Health Centre has almost the same coordinates as "
          "Barunga clinic, about 28 km from Manyallaluk", 1,
    "flagged; the project uses NT community coordinates for clinics instead")

# Problem: the same clinic listed twice.
dups = ga["organisation_name"].duplicated(keep=False)
log(file, f"listed twice: "
          f"{ga.loc[dups, 'organisation_name'].unique().tolist()}",
    int(dups.sum()), "kept both (they are separate services at one clinic)")

ga = ga.drop(columns=["c_lat", "c_lon"])
ga.to_csv(CLEAN / "ga_facilities.csv", index=False)


# =============================================================================
# 6. ROAD ROUTING RESULTS
#    For each community: road distance and drive time to the nearest clinic
#    and nearest hospital ED, calculated on the national road network.
# =============================================================================
file = "road_routing_results.csv"
rt = pd.read_csv(raw_file(file))
rt = rt.rename(columns={"community_name": "community"})
rt["community"] = tidy_name(rt["community"])

# Problem: -1 is used as a code for "no road route found". If we left it,
# averages would include -1 minutes. We replace it with a proper blank (NaN),
# only in the columns that use this code.
no_clinic = (rt["clinic_minutes"] == -1).sum()
no_hosp = (rt["hospital_minutes"] == -1).sum()
route_cols = ["clinic_road_km", "clinic_minutes", "hospital_road_km",
              "hospital_minutes", "hospital_minutes_sealed_only"]
rt[route_cols] = rt[route_cols].replace(-1, np.nan)
log(file, "-1 used as a code for 'no road route to a clinic'", int(no_clinic),
    "replaced with blank (NaN)")
log(file, "-1 used as a code for 'no road route to a hospital ED' "
          "(mostly islands)", int(no_hosp), "replaced with blank (NaN)")

# Problem: if there is no road to hospital, 'unsealed km' was recorded as 0,
# which wrongly looks like "a fully sealed road". It should be blank.
no_route = rt["hospital_minutes"].isna()
rt.loc[no_route, "hospital_unsealed_km"] = np.nan
log(file, "unsealed km recorded as 0 where there is no road at all",
    int(no_route.sum()), "set to blank")

# The sealed-only column is blank when you cannot reach hospital on sealed
# roads alone. That is a real answer, not missing data, so we make it a flag.
rt["sealed_route_exists"] = rt["hospital_minutes_sealed_only"].notna()

# Problem: one row is a site from the 2022 coverage list with the same name as
# a different community in the 2021 list (about 14 km apart). Two rows with one
# name would break the join in Step 2, so we rename the 2022 one. We find it by
# its latitude, so the fix works even if the row order changes.
site_2022 = (rt["community"] == "Brumby Plains") & (rt["lat"].round(3) == -17.053)
rt.loc[site_2022, "community"] = "Brumby Plains (2022 Site)"
log(file, "two different places both named 'Brumby Plains' (about 14 km apart)",
    1, "renamed the 2022 site to 'Brumby Plains (2022 Site)'")

# Warning, not a fix: some communities are far from any mapped road, so their
# travel time depends mostly on the 30 km/h off-road assumption.
far_road = (rt["snap_km"] > 10).sum()
rt["far_from_road"] = rt["snap_km"] > 10
log(file, "communities more than 10 km from the nearest mapped road",
    int(far_road), "flagged far_from_road; their travel times are less certain")

# Drop helper columns that only the routing algorithm needed.
rt = rt.drop(columns=["idx", "road_component_nodes", "clinic_dest_idx",
                      "hospital_idx"])
assert rt["community"].is_unique
rt.to_csv(CLEAN / "routing.csv", index=False)


# =============================================================================
# 7. CYCLONE EXPOSURE (Bureau of Meteorology tracks, counted per community)
# =============================================================================
file = "bom_cyclone_exposure_communities.csv"
tc = pd.read_csv(raw_file(file))
tc = tc.rename(columns={"community_name": "community",
                        "tc_systems_within_200km_2000on": "cyclones_200km",
                        "severe_tc_within_100km_2000on": "severe_cyclones_100km"})
tc["community"] = tidy_name(tc["community"])

# Same Brumby Plains fix as the routing file, found the same way.
site_2022 = (tc["community"] == "Brumby Plains") & (tc["lat"].round(3) == -17.053)
tc.loc[site_2022, "community"] = "Brumby Plains (2022 Site)"

# Counts can never be negative. Check, rather than assume.
assert (tc[["cyclones_200km", "severe_cyclones_100km"]] >= 0).all().all()
assert tc["community"].is_unique
tc = tc[["community", "cyclones_200km", "severe_cyclones_100km"]]
tc.to_csv(CLEAN / "cyclones.csv", index=False)


# =============================================================================
# 8. ROAD NETWORK SUMMARY (GA National Roads, NT)
# =============================================================================
file = "road_network_summary.csv"
roads = pd.read_csv(raw_file(file))
roads["hierarchy"] = roads["hierarchy"].str.title()
roads["surface"] = roads["surface"].replace("(not recorded)", "Not recorded").str.title()
log(file, "road surface '(not recorded)'",
    int((roads["surface"] == "Not Recorded").sum()),
    "renamed to 'Not recorded'; kept (only 210 km of 126,000 km)")

# Add each row's share of all road kilometres, for the report.
roads["pct_of_km"] = (roads["km"] / roads["km"].sum() * 100).round(1)
roads.to_csv(CLEAN / "road_summary.csv", index=False)


# =============================================================================
# 9. PREVENTABLE HOSPITALISATIONS (AIHW)
#    Used as context: the health cost of poor access to care.
# =============================================================================
file = "aihw_pph_context.csv"
pph = pd.read_csv(raw_file(file))

# Problem: years are text like "2023–24". For a trend chart we need a number,
# so we take the first four characters as the start year.
pph["start_year"] = pph["year"].str[:4].astype(int)
pph = pph.rename(columns={"asr_per_100k": "rate_per_100k"})
pph.to_csv(CLEAN / "pph.csv", index=False)


# =============================================================================
# 10. DIGITAL INCLUSION INDEX, FIRST NATIONS (ADII)
#     The export is laid out like a report: headings, then rows of numbers.
#     We walk down the sheet, remember the latest heading, and give each number
#     row that heading as its 'section'.
# =============================================================================
file = "adii_first_nations_scores.xlsx"
raw = pd.read_excel(raw_file(file), header=None, names=["group", "score", "gap"])

rows, section = [], None
for group, score, gap in raw.itertuples(index=False):
    if pd.isna(group):
        continue                    # spacer row
    if pd.isna(score):
        section = group             # a heading row - remember it
        continue
    rows.append({"section": section, "group": group,
                 "adii_score": round(score, 1),
                 "gap": None if pd.isna(gap) else round(gap, 1)})
adii = pd.DataFrame(rows)
log(file, "report-style layout with headings and blank spacer rows", len(raw),
    "turned into a table with one row per group and a 'section' column")
adii.to_csv(CLEAN / "adii.csv", index=False)


# =============================================================================
# SAVE THE LOG AND PRINT A SUMMARY
# =============================================================================
pd.DataFrame(issues).to_csv(CLEAN / "data_quality_log.csv", index=False)

print("Cleaned files saved in data/clean/:")
for f in sorted(CLEAN.glob("*.csv")):
    df = pd.read_csv(f)
    print(f"  {f.name:<24} {len(df):>4} rows   blanks: {int(df.isna().sum().sum())}")
print(f"\n{len(issues)} problems written to data/clean/data_quality_log.csv")
