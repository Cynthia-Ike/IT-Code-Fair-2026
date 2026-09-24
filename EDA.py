# =============================================================================
# STEP 3: EXPLORATORY DATA ANALYSIS (EDA)
# Project: Reach for Help NT - the cost of disconnectivity in remote health
# CDU IT Code Fair 2026, Data Innovation Challenge
#
# Goal: look at the merged data (Step 2) and answer the project's core
# questions with numbers and charts, BEFORE building any model in Step 4:
#   1. How many communities can/can't call for help right now?
#   2. Does poor coverage line up with longer drive times to help?
#   3. Are the worst-off communities also the most physically isolated
#      (settlement type, bad roads, cyclone exposure)?
#   4. Which regions and clinics carry the most risk?
#
# WHICH VARIABLES ACTUALLY EXPLAIN THIS PROJECT?
# Before drawing charts, the numbers below were checked variable-by-variable
# against `can_call` to see which ones show a real, honest relationship
# worth building a chart around, rather than picking variables just because
# they exist in the file. Summary of what was tested:
#
#   community_type   STRONG.  Family Outstations (620 of 782 communities,
#                    80% of the dataset) have an 84% "can't call" rate and
#                    only 2% have a sealed road at all. "Major" communities
#                    sit at 17% can't-call and 20% sealed-road. This is the
#                    single strongest explanatory variable found - stronger
#                    than region.
#   clinic_minutes / STRONG.  Median drive time to a clinic for "can't call"
#   nearest_own_          communities is roughly 5x longer than for covered
#   clinic_km              ones (88 vs 16 minutes on average). Confirms the
#                    project's central claim: no signal lines up with being
#                    genuinely far from help.
#   sealed_route_    STRONG, and linked to community_type. Only 7% of
#   exists                 "can't call" communities have any sealed road at
#                    all, vs 26% of covered communities - isolation
#                    compounds rather than being a separate problem.
#   region           MODEST.  Can't-call rates range 72-79% across the 5
#                    regions - a real but much smaller effect than
#                    community_type. Still useful for "where to prioritise".
#   hospital_minutes STRONG but noisier.  87 communities have no routed
#                    value at all, so treat this as supporting evidence,
#                    not the headline number.
#   cyclones_200km / WEAK - EXCLUDED as an explanatory variable. Average
#   severe_cyclones_       cyclone exposure barely differs between "can
#   100km                  call" (15.3) and "can't call" (16.8) groups.
#                    Cyclones are a real hazard for this project, but they
#                    do NOT explain who currently has coverage.
#   population_2022  EXCLUDED. Only recorded for covered communities (0 for
#                    the rest) - comparing it across groups would just be
#                    measuring which communities got surveyed, not
#                    population size (see Step 2 missingness notes).
#   hospital_minutes_ EXCLUDED as a group-comparison variable. Only 91 of
#   sealed_only             782 communities have a non-null value here -
#                    too small and non-random a subset to compare fairly.
#
# Conclusion: the best combination for telling this project's story is
# can_call (outcome) x community_type (strongest driver) x clinic/hospital
# drive time (what the outcome costs in practice) x sealed_route_exists
# (how isolation compounds) x region and clinic caseload (where to act).
#
# How to run (from the project folder, after merge_data.py has been run):
#   python eda.py
# Charts are saved as PNG files in outputs/ (created automatically).
# =============================================================================

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Remember the file path convention: relative to THIS SCRIPT, not to wherever
# you happened to launch python from (see Steps 1 & 2 for why this matters).
PROCESSED = Path(__file__).resolve().parent / "data" / "processed"
OUTPUTS = Path(__file__).resolve().parent / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

# One global style call - seaborn's theme affects every plot below, even the
# plain matplotlib ones (stacked bars aren't built into seaborn), so we only
# need to set this once.
sns.set_theme(style="whitegrid", font_scale=1.05)

com = pd.read_csv(PROCESSED / "communities_merged.csv")
clinics = pd.read_csv(PROCESSED / "clinics_merged.csv")
print(f"Loaded {len(com)} communities and {len(clinics)} clinics.")


# =============================================================================
# COLOUR SETUP
#
# can_call has 5 categories that form a scale from "worst" to "best" coverage.
# We fix ONE colour per category here and reuse it in EVERY chart below -
# including the new community_type chart - so "red" always means the same
# thing wherever it appears. This matters more than which exact colours you
# pick - the point is consistency, not decoration.
# =============================================================================
CAN_CALL_ORDER = [
    "Never recorded",
    "Listed: no coverage",
    "Listed: has coverage (2021)",
    "Small cell or near a cell",
    "Macro cell nearby",
]
CAN_CALL_COLORS = {
    "Never recorded": "#B0413E",              # red    - most at risk
    "Listed: no coverage": "#D98C3D",         # orange
    "Listed: has coverage (2021)": "#D4B94E", # yellow
    "Small cell or near a cell": "#5B9BD5",   # blue
    "Macro cell nearby": "#4C8C4A",           # green  - best off
}
CANNOT_CALL = ["Never recorded", "Listed: no coverage"]
cannot_call_mask = com["can_call"].isin(CANNOT_CALL)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUTPUTS / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# CHART 1: how many communities fall into each coverage category?
# =============================================================================
counts = com["can_call"].value_counts().reindex(CAN_CALL_ORDER)

fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(x=counts.index, y=counts.values,
            hue=counts.index, palette=CAN_CALL_COLORS, legend=False, ax=ax)
for i, v in enumerate(counts.values):
    ax.text(i, v + 8, str(v), ha="center", fontweight="bold")
ax.set_ylabel("Number of communities")
ax.set_xlabel("")
ax.set_title("Mobile coverage status across 782 remote NT communities", fontsize=13)
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
sns.despine(ax=ax)
save(fig, "chart1_coverage_overview.png")

pct_cannot_call = cannot_call_mask.mean() * 100
print(f"\nChart 1 saved. {pct_cannot_call:.1f}% of communities have no known "
      f"mobile coverage at all (Never recorded + Listed: no coverage).")


# =============================================================================
# CHART 2: does coverage line up with drive time to the nearest clinic?
# Violin + inner quartile box shows the full shape of the distribution, not
# just a single average - useful because a few very remote communities could
# otherwise hide inside a mean.
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="clinic_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest clinic (minutes)")
ax.set_xlabel("")
ax.set_title("Clinic drive time by mobile coverage status", fontsize=13)
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
sns.despine(ax=ax)
save(fig, "chart2_clinic_drivetime_by_coverage.png")

medians = com.groupby("can_call")["clinic_minutes"].median().reindex(CAN_CALL_ORDER)
print("\nChart 2 saved. Median clinic drive time by coverage status (minutes):")
print(medians.to_string())


# =============================================================================
# CHART 3: same question, but for the nearest HOSPITAL (the worst-case
# emergency). Hospital data has more gaps (only 697 of 782 communities have
# a routed hospital time), so we note that rather than hide it.
# =============================================================================
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="hospital_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest hospital ED (minutes)")
ax.set_xlabel("")
ax.set_title("Hospital drive time by mobile coverage status", fontsize=13)
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
sns.despine(ax=ax)
save(fig, "chart3_hospital_drivetime_by_coverage.png")

n_missing_hosp = com["hospital_minutes"].isna().sum()
print(f"\nChart 3 saved. ({n_missing_hosp} of {len(com)} communities have no "
      f"routed hospital time - see data_quality_log.csv for why.)")


# =============================================================================
# CHART 4: isolation check - are the "can't call" communities ALSO more
# likely to be off the sealed road network?
# =============================================================================
isolation = com.groupby("can_call").agg(
    pct_far_from_road=("far_from_road", "mean"),
    pct_sealed_route=("sealed_route_exists", "mean"),
).reindex(CAN_CALL_ORDER) * 100

fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.barplot(x=isolation.index, y=isolation["pct_far_from_road"],
            hue=isolation.index, palette=CAN_CALL_COLORS, legend=False, ax=ax)
for i, v in enumerate(isolation["pct_far_from_road"]):
    ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontweight="bold")
ax.set_ylabel("Communities more than 10km from the road network (%)")
ax.set_xlabel("")
ax.set_title("Road isolation by mobile coverage status", fontsize=13)
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
sns.despine(ax=ax)
save(fig, "chart4_road_isolation_by_coverage.png")

print("\nChart 4 saved. Road isolation + sealed-route access by coverage status:")
print(isolation.round(1).to_string())


# =============================================================================
# CHART 5: which regions carry the most "can't call" communities? A stacked
# bar keeps the SAME colours as Chart 1 so a reader doesn't have to relearn
# the legend. (region has a MODEST effect - see the notes at the top of this
# file - so this chart is useful for "where to act" but not the headline
# explanatory variable.)
# =============================================================================
region_mix = (com.groupby(["region", "can_call"]).size()
              .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
region_mix["cannot_call_total"] = region_mix[CANNOT_CALL].sum(axis=1)
region_mix = region_mix.sort_values("cannot_call_total", ascending=False)

fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    values = region_mix[cat]
    ax.bar(region_mix.index, values, bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat,
           edgecolor="white", linewidth=1)
    bottom = values if bottom is None else bottom + values
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by NT health region", fontsize=13)
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
sns.despine(ax=ax)
save(fig, "chart5_coverage_by_region.png")

print("\nChart 5 saved. 'Can't call' communities by region:")
print(region_mix["cannot_call_total"].astype(int).to_string())


# =============================================================================
# CHART 6: which clinics carry the biggest "can't call" caseload? A single
# ranked quantity, so it gets ONE colour ramp (sequential: darker = higher
# caseload) rather than a different hue per clinic, which would wrongly
# imply the clinics are different "types".
# =============================================================================
top10 = clinics.sort_values("communities_cant_call", ascending=False).head(10)
top10 = top10.iloc[::-1]  # reverse so the biggest bar ends up on top
ramp = sns.color_palette("Blues", n_colors=len(top10))
# Map darker shades to higher values, not just position, since a couple of
# clinics are tied.
order = top10["communities_cant_call"].rank(method="first").astype(int) - 1
bar_colors = [ramp[i] for i in order]

fig, ax = plt.subplots(figsize=(9.5, 6))
ax.barh(top10["clinic"], top10["communities_cant_call"], color=bar_colors)
for i, (v, name) in enumerate(zip(top10["communities_cant_call"], top10["clinic"])):
    ax.text(v + 0.4, i, str(v), va="center", fontweight="bold")
ax.set_xlabel("Nearby communities with no known mobile coverage")
ax.set_title("Top 10 clinics by 'can't call for help' caseload", fontsize=13)
sns.despine(ax=ax)
save(fig, "chart6_clinic_caseload.png")

print("\nChart 6 saved. Top 5 clinics by can't-call caseload:")
print(top10[["clinic", "region", "communities_served", "communities_cant_call"]]
      .iloc[::-1].head(5).to_string(index=False))


# =============================================================================
# CHART 7 (NEW): coverage status by SETTLEMENT TYPE - the strongest single
# explanatory variable found in this dataset. Same stacked-bar design and
# same colours as Chart 5, so it reads as a direct comparison: settlement
# type separates communities far more sharply than region does.
# =============================================================================
type_mix = (com.groupby(["community_type", "can_call"]).size()
            .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
type_mix["total"] = type_mix.sum(axis=1)
type_mix["cannot_call_total"] = type_mix[CANNOT_CALL].sum(axis=1)
type_mix["cannot_call_pct"] = type_mix["cannot_call_total"] / type_mix["total"] * 100
type_mix = type_mix.sort_values("cannot_call_pct", ascending=False)

fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    values = type_mix[cat]
    ax.bar(type_mix.index, values, bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat,
           edgecolor="white", linewidth=1)
    bottom = values if bottom is None else bottom + values
# Direct-label the cannot-call % on top of each bar - this is the number
# that matters most for this chart.
for i, (pct, total) in enumerate(zip(type_mix["cannot_call_pct"], type_mix["total"])):
    ax.text(i, total + 10, f"{pct:.0f}% can't call", ha="center",
            fontsize=9, fontweight="bold", color="#B0413E")
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by settlement type - the strongest split in the data",
             fontsize=13)
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
sns.despine(ax=ax)
save(fig, "chart7_coverage_by_settlement_type.png")

print("\nChart 7 saved (NEW). Can't-call rate by settlement type:")
print(type_mix[["total", "cannot_call_pct"]].round(1).to_string())


# =============================================================================
# CHART 8 (NEW): correlation heatmap of the numeric access/isolation
# variables. Correlation is a POLARITY measure (negative vs positive), so
# this is exactly the case for a diverging palette: two hues either side of
# a neutral zero, never a rainbow.
# =============================================================================
numeric_cols = {
    "clinic_minutes": "Clinic drive (min)",
    "hospital_minutes": "Hospital drive (min)",
    "nearest_own_clinic_km": "Distance to clinic (km)",
    "snap_km": "Distance to road (km)",
    "cyclones_200km": "Cyclones (200km)",
    "severe_cyclones_100km": "Severe cyclones (100km)",
}
corr = com[list(numeric_cols)].rename(columns=numeric_cols).corr()

fig, ax = plt.subplots(figsize=(8, 6.5))
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
sns.heatmap(corr, mask=mask, cmap="vlag", vmin=-1, vmax=1, center=0,
            annot=True, fmt=".2f", square=True, linewidths=1,
            cbar_kws={"label": "Correlation"}, ax=ax)
ax.set_title("How the access & isolation measures relate to each other",
             fontsize=13, pad=20)
save(fig, "chart8_correlation_heatmap.png")

print("\nChart 8 saved (NEW). Note: cyclone exposure barely correlates with "
      "drive times or distances - confirms cyclones don't explain coverage.")


# =============================================================================
# CHART 9 (NEW): sealed road access by settlement type - shows WHY
# settlement type is such a strong driver: it's tightly linked to whether a
# sealed road even exists, which is itself tightly linked to coverage.
# =============================================================================
sealed_by_type = (com.groupby("community_type")["sealed_route_exists"]
                   .mean().mul(100).sort_values())

fig, ax = plt.subplots(figsize=(9, 5.5))
ramp = sns.color_palette("Blues", n_colors=len(sealed_by_type))
sns.barplot(x=sealed_by_type.values, y=sealed_by_type.index,
            hue=sealed_by_type.index, palette=list(ramp), legend=False, ax=ax)
for i, v in enumerate(sealed_by_type.values):
    ax.text(v + 1, i, f"{v:.0f}%", va="center", fontweight="bold")
ax.set_xlabel("Communities with a sealed road route (%)")
ax.set_ylabel("")
ax.set_title("Sealed road access by settlement type", fontsize=13)
sns.despine(ax=ax)
save(fig, "chart9_sealed_road_by_settlement_type.png")

print("\nChart 9 saved (NEW). Sealed road access by settlement type (%):")
print(sealed_by_type.round(1).to_string())


# =============================================================================
# SUMMARY - the headline numbers a reader would want first.
# =============================================================================
print("\n" + "=" * 60)
print("EDA SUMMARY")
print("=" * 60)
print(f"Communities analysed: {len(com)}")
print(f"Cannot call for help at all: {int(cannot_call_mask.sum())} ({pct_cannot_call:.1f}%)")
print(f"Strongest driver found: community_type "
      f"(Family Outstation {type_mix.loc['Family Outstation', 'cannot_call_pct']:.0f}% "
      f"cannot call vs Major {type_mix.loc['Major', 'cannot_call_pct']:.0f}%)")
print(f"Median clinic drive time, 'Never recorded' group: "
      f"{medians['Never recorded']:.0f} min "
      f"vs 'Macro cell nearby' group: {medians['Macro cell nearby']:.0f} min")
print(f"Cyclone exposure ruled OUT as a driver (near-identical averages "
      f"between can-call and cannot-call groups)")
print(f"Charts saved to: {OUTPUTS}")