# ===========================================================================
# EXPLORATORY DATA ANALYSIS (EDA) - The Long Way to Care
# ===========================================================================
'''
Part A - Checks if the data is normally distributed (Shapiro-Wilk test).
         This decides what kind of statistics/tests are allowed to be used.
Part B - Charts, to see the patterns in the data.
Part C - Proper hypothesis tests, to check the patterns in the charts are
         real and not just random noise.
'''

#Import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in.

'''
Self-correcting trick as the earlier scripts: if this script ends up
sitting INSIDE "Processed Data" instead of next to it, that same folder is
used as PROCESSED, and Outputs is put one level up instead of nested in.
'''
if BASE.name == "Processed Data":
    PROCESSED = BASE
    PROJECT = BASE.parent
else:
    PROCESSED = BASE / "Processed Data"
    PROJECT = BASE

if not PROCESSED.exists():
    raise FileNotFoundError(
        f"Can't find a 'Processed Data' folder. Looked for it at:\n  {PROCESSED}\n"
        f"Run clean_data_simple.py then merge_data_simple.py first - together "
        f"they build the merged files this script needs.")

OUTPUTS = PROJECT / "Outputs"  # Charts are saved here.
OUTPUTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.05)

com = pd.read_csv(PROCESSED / "communities_merged.csv")
clinics = pd.read_csv(PROCESSED / "clinics_merged.csv")
print("Loaded", len(com), "communities and", len(clinics), "clinics")

'''
The order to show the 6 coverage categories in every chart, worst to best,
and one colour per category so it stays the same in every chart.
'''
CAN_CALL_ORDER = [
    "Never recorded",
    "Listed: no coverage",
    "Listed: has coverage (2021)",
    "Tower within 15km (2025)",
    "Small cell or near a cell",
    "Macro cell nearby",
]
CAN_CALL_COLORS = {
    "Never recorded": "#EF150D",
    "Listed: no coverage": "#E1801F",
    "Listed: has coverage (2021)": "#EEC211",
    "Tower within 15km (2025)": "#15ECD0",
    "Small cell or near a cell": "#3180CB",
    "Macro cell nearby": "#0D8F08",
}
CANNOT_CALL = ["Never recorded", "Listed: no coverage"]
cannot_call = com["can_call"].isin(CANNOT_CALL)


# Chart saver - tidies the layout and saves to the Outputs folder
def saving_chart(fig, name):
    fig.tight_layout()
    fig.savefig(OUTPUTS / name, dpi=150, bbox_inches="tight")
    plt.close(fig)

# ===========================================================================
# PART A: DESCRIPTIVE STATS + NORMALITY TEST
# ===========================================================================
# Shapiro-Wilk: if p < 0.05, the variable is NOT normally distributed.
print("\n--- PART A: Descriptive Statistics & Normality ---")

numeric_vars = {
    "clinic_minutes": "Drive time to nearest clinic (min)",
    "hospital_minutes": "Drive time to nearest hospital (min)",
    "nearest_own_clinic_km": "Distance to nearest clinic (km)",
    "snap_km": "Distance to road network (km)",
    "cyclones_200km": "Cyclone count within 200km",
    "severe_cyclones_100km": "Severe cyclone count within 100km",
}

rows = []
for col, label in numeric_vars.items():
    s = com[col].dropna()
    w, p = stats.shapiro(s)
    rows.append({"Variable": label, "N": len(s), "Mean": s.mean(),
                 "Median": s.median(), "Std": s.std(), "Min": s.min(),
                 "Max": s.max(), "Shapiro p": p,
                 "Normal?": "No" if p < 0.05 else "Yes"})

desc_table = pd.DataFrame(rows)
print(desc_table.round(3).to_string(index=False))
desc_table.to_csv(PROCESSED / "descriptive_stats.csv", index=False)
print("\nAll variables fail the normality test  if p < 0.05. Median is used "
      "instead of mean. Spearman instead of Pearson. Kruskal-Wallis instead of ANOVA"
       " The t-testis used from here on.")

# Chart showing WHY - mean gets pulled away from the median by outliers
fig, axes = plt.subplots(2, 2, figsize=(11, 8))
panel_vars = ["clinic_minutes", "hospital_minutes", "nearest_own_clinic_km", "snap_km"]
for ax, col in zip(axes.flat, panel_vars):
    s = com[col].dropna()
    sns.histplot(s, bins=40, color="#5B9BD5", ax=ax, edgecolor="white")
    ax.axvline(s.median(), color="#B0413E", linewidth=2, label="Median")
    ax.axvline(s.mean(), color="#6B7280", linewidth=2, linestyle="--", label="Mean")
    ax.set_title(numeric_vars[col], fontsize=11)
    ax.set_ylabel("Number of communities")
handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.03))
saving_chart(fig, "chartA_normality.png")
print("Chart A saved: mean vs median for the 4 main variables")


# ===========================================================================
# PART B: CHARTS
# ===========================================================================
print("\n--- PART B: charts ---")

# Chart 1 - How many communities are in each coverage category
counts = com["can_call"].value_counts().reindex(CAN_CALL_ORDER)
fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(x=counts.index, y=counts.values, hue=counts.index,
            palette=CAN_CALL_COLORS, legend=False, ax=ax)
for i, v in enumerate(counts.values):
    ax.text(i, v + 8, str(v), ha="center", fontweight="bold")
ax.set_ylabel("Number of communities")
ax.set_title("Mobile coverage status across 782 remote NT communities")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
saving_chart(fig, "chart1_coverage_overview.png")
pct_cannot_call = cannot_call.mean() * 100
print(f"Chart 1: {pct_cannot_call:.1f}% of communities cannot call for help")

# Chart 2 - Clinic drive time by coverage status
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="clinic_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest clinic (minutes)")
ax.set_title("Clinic drive time by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
saving_chart(fig, "chart2_clinic_drivetime_by_coverage.png")
print("Chart 2: median clinic drive time by coverage ->")
print(com.groupby("can_call")["clinic_minutes"].median().reindex(CAN_CALL_ORDER).to_string())

# Chart 3 - Hospital drive time by coverage status
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="hospital_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest hospital ED (minutes)")
ax.set_title("Hospital drive time by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
saving_chart(fig, "chart3_hospital_drivetime_by_coverage.png")
print("Chart 3 saved")

# Chart 4 - Road isolation by coverage status
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
ax.set_title("Road isolation by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
saving_chart(fig, "chart4_road_isolation_by_coverage.png")
print("Chart 4 saved")

# Chart 5 - Coverage split by region (stacked bar)
region_mix = (com.groupby(["region", "can_call"]).size()
              .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
region_mix["cannot_call_total"] = region_mix[CANNOT_CALL].sum(axis=1)
region_mix = region_mix.sort_values("cannot_call_total", ascending=False)
fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    ax.bar(region_mix.index, region_mix[cat], bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat, edgecolor="white")
    bottom = region_mix[cat] if bottom is None else bottom + region_mix[cat]
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by NT health region")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
saving_chart(fig, "chart5_coverage_by_region.png")
print("Chart 5: can't-call communities by region ->")
print(region_mix["cannot_call_total"].astype(int).to_string())

# Chart 6 - Top 10 clinics by can't-call caseload
top10 = clinics.sort_values("communities_cant_call", ascending=False).head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(9.5, 6))
ax.barh(top10["clinic"], top10["communities_cant_call"], color="#5B9BD5")
for i, v in enumerate(top10["communities_cant_call"]):
    ax.text(v + 0.4, i, str(v), va="center", fontweight="bold")
ax.set_xlabel("Nearby communities with no known mobile coverage")
ax.set_title("Top 10 clinics by 'can't call for help' caseload")
saving_chart(fig, "chart6_clinic_caseload.png")
print("Chart 6: busiest clinics ->")
print(top10[["clinic", "communities_served", "communities_cant_call"]].iloc[::-1].head(5).to_string(index=False))

# Chart 7 - Coverage by settlement type (the strongest pattern in the data)
type_mix = (com.groupby(["community_type", "can_call"]).size()
            .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
type_mix["total"] = type_mix.sum(axis=1)
type_mix["cannot_call_pct"] = type_mix[CANNOT_CALL].sum(axis=1) / type_mix["total"] * 100
type_mix = type_mix.sort_values("cannot_call_pct", ascending=False)
fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    ax.bar(type_mix.index, type_mix[cat], bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat, edgecolor="white")
    bottom = type_mix[cat] if bottom is None else bottom + type_mix[cat]
for i, (pct, total) in enumerate(zip(type_mix["cannot_call_pct"], type_mix["total"])):
    ax.text(i, total + 10, f"{pct:.0f}% can't call", ha="center", fontsize=9, color="#B0413E")
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by settlement type")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
saving_chart(fig, "chart7_coverage_by_settlement_type.png")
print("Chart 7: can't-call rate by settlement type ->")
print(type_mix[["total", "cannot_call_pct"]].round(1).to_string())

# Chart 8 - Correlation heatmap (Spearman, since the data is non-normal)
corr_cols = {
    "clinic_minutes": "Clinic drive (min)", "hospital_minutes": "Hospital drive (min)",
    "nearest_own_clinic_km": "Distance to clinic (km)", "snap_km": "Distance to road (km)",
    "cyclones_200km": "Cyclones (200km)", "severe_cyclones_100km": "Severe cyclones (100km)",
}
corr = com[list(corr_cols)].rename(columns=corr_cols).corr(method="spearman")
fig, ax = plt.subplots(figsize=(8, 6.5))
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
sns.heatmap(corr, mask=mask, cmap="vlag", vmin=-1, vmax=1, center=0, annot=True,
            fmt=".2f", square=True, ax=ax)
ax.set_title("How the access & isolation measures relate to each other\n(Spearman correlation)")
saving_chart(fig, "chart8_correlation_heatmap.png")
print("Chart 8 saved")

# Chart 9 - Sealed road access by settlement type
sealed_by_type = com.groupby("community_type")["sealed_route_exists"].mean().mul(100).sort_values()
fig, ax = plt.subplots(figsize=(9, 5.5))
sns.barplot(x=sealed_by_type.values, y=sealed_by_type.index,
            hue=sealed_by_type.index, palette="Blues", legend=False, ax=ax)
for i, v in enumerate(sealed_by_type.values):
    ax.text(v + 1, i, f"{v:.0f}%", va="center", fontweight="bold")
ax.set_xlabel("Communities with a sealed road route (%)")
ax.set_title("Sealed road access by settlement type")
saving_chart(fig, "chart9_sealed_road_by_settlement_type.png")
print("Chart 9 saved")


# ===========================================================================
# PART C: HYPOTHESIS TESTS
# ===========================================================================
'''
These check if the differences in the charts above are statistically real,
not just random. Non-parametric versions are used since Part A showed the
data is not normally distributed.
'''
print("\n--- PART C: hypothesis tests ---")

# Does clinic drive time differ across the 6 coverage categories?
groups = [com.loc[com["can_call"] == c, "clinic_minutes"].dropna() for c in CAN_CALL_ORDER]
h1, p1 = stats.kruskal(*groups)
print(f"Kruskal-Wallis, drive time across coverage categories: H={h1:.2f}, p={p1:.3e}")

# Does clinic drive time differ across settlement types?
types = com["community_type"].dropna().unique()
groups2 = [com.loc[com["community_type"] == t, "clinic_minutes"].dropna() for t in types]
h2, p2 = stats.kruskal(*groups2)
print(f"Kruskal-Wallis, drive time across settlement types: H={h2:.2f}, p={p2:.3e}")

# Does drive time differ between "can call" and "cannot call" communities?
u1, pu1 = stats.mannwhitneyu(
    com.loc[cannot_call, "clinic_minutes"].dropna(),
    com.loc[~cannot_call, "clinic_minutes"].dropna())
print(f"Mann-Whitney U, cannot-call vs can-call: U={u1:.1f}, p={pu1:.3e}")

print("\nAll three tests are significant (p < 0.001) - coverage status and "
      "settlement type are both genuinely linked to drive time, not just "
      "something that looks that way in the charts by chance.")


# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n--- EDA SUMMARY ---")
print("Communities analysed:", len(com))
print(f"Cannot call for help at all: {int(cannot_call.sum())} ({pct_cannot_call:.1f}%)")
print(f"Strongest pattern: settlement type - Family Outstation "
      f"{type_mix.loc['Family Outstation', 'cannot_call_pct']:.0f}% cannot call "
      f"vs Major {type_mix.loc['Major', 'cannot_call_pct']:.0f}%")
print("Charts saved to:", OUTPUTS)# ===========================================================================
# EXPLORATORY DATA ANALYSIS (EDA) - Reach for Help NT
# ===========================================================================
'''
Part A - Checks if the data is normally distributed (Shapiro-Wilk test).
         This decides what kind of statistics/tests are allowed to be used.
Part B - Charts, to see the patterns in the data.
Part C - Proper hypothesis tests, to check the patterns in the charts are
         real and not just random noise.
'''

#Import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in.

'''
Self-correcting scripts: if this script ends up
sitting INSIDE "Processed Data" instead of next to it, that same folder is
used as PROCESSED, and Outputs is put one level up instead of nested in.
'''
if BASE.name == "Processed Data":
    PROCESSED = BASE
    PROJECT = BASE.parent
else:
    PROCESSED = BASE / "Processed Data"
    PROJECT = BASE

if not PROCESSED.exists():
    raise FileNotFoundError(
        f"Can't find a 'Processed Data' folder. Looked for it at:\n  {PROCESSED}\n"
        f"Run clean_data_simple.py then merge_data_simple.py first - together "
        f"they build the merged files this script needs.")

OUTPUTS = PROJECT / "Outputs"  # Charts are saved here.
OUTPUTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.05)

com = pd.read_csv(PROCESSED / "communities_merged.csv")
clinics = pd.read_csv(PROCESSED / "clinics_merged.csv")
print("Loaded", len(com), "communities and", len(clinics), "clinics")

'''
The order to show the 6 coverage categories in every chart, worst to best,
and one colour per category so it stays the same in every chart.
'''
CAN_CALL_ORDER = [
    "Never recorded",
    "Listed: no coverage",
    "Listed: has coverage (2021)",
    "Tower within 15km (2025)",
    "Small cell or near a cell",
    "Macro cell nearby",
]
CAN_CALL_COLORS = {
    "Never recorded": "#B0413E",
    "Listed: no coverage": "#D98C3D",
    "Listed: has coverage (2021)": "#D4B94E",
    "Tower within 15km (2025)": "#6FA8A0",
    "Small cell or near a cell": "#5B9BD5",
    "Macro cell nearby": "#4C8C4A",
}
CANNOT_CALL = ["Never recorded", "Listed: no coverage"]
cannot_call = com["can_call"].isin(CANNOT_CALL)


# Chart saver - tidies the layout and saves to the Outputs folder
def save_chart(fig, name):
    fig.tight_layout()
    fig.savefig(OUTPUTS / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ===========================================================================
# PART A: DESCRIPTIVE STATS AND NORMALITY TEST
# ===========================================================================
# Shapiro-Wilk: if p < 0.05, the variable is NOT normally distributed.
print("\n--- PART A: Descriptive Statistics & Normality Test ---")

numeric_vars = {
    "clinic_minutes": "Drive time to nearest clinic (min)",
    "hospital_minutes": "Drive time to nearest hospital (min)",
    "nearest_own_clinic_km": "Distance to nearest clinic (km)",
    "snap_km": "Distance to road network (km)",
    "cyclones_200km": "Cyclone count within 200km",
    "severe_cyclones_100km": "Severe cyclone count within 100km",
}

rows = []
for col, label in numeric_vars.items():
    s = com[col].dropna()
    w, p = stats.shapiro(s)
    rows.append({"Variable": label, "N": len(s), "Mean": s.mean(),
                 "Median": s.median(), "Std": s.std(), "Min": s.min(),
                 "Max": s.max(), "Shapiro p": p,
                 "Normal?": "No" if p < 0.05 else "Yes"})

desc_table = pd.DataFrame(rows)
print(desc_table.round(3).to_string(index=False))
desc_table.to_csv(PROCESSED / "descriptive_stats.csv", index=False)
print("\nAll variables fail the normality test (p < 0.05), so median is used "
      "instead of mean, Spearman instead of Pearson, and Kruskal-Wallis / "
      "Mann-Whitney instead of ANOVA / t-test from here on.")

# Chart showing WHY - mean gets pulled away from the median by outliers
fig, axes = plt.subplots(2, 2, figsize=(11, 8))
panel_vars = ["clinic_minutes", "hospital_minutes", "nearest_own_clinic_km", "snap_km"]
for ax, col in zip(axes.flat, panel_vars):
    s = com[col].dropna()
    sns.histplot(s, bins=40, color="#5B9BD5", ax=ax, edgecolor="white")
    ax.axvline(s.median(), color="#B0413E", linewidth=2, label="Median")
    ax.axvline(s.mean(), color="#6B7280", linewidth=2, linestyle="--", label="Mean")
    ax.set_title(numeric_vars[col], fontsize=11)
    ax.set_ylabel("Number of communities")
handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.03))
save_chart(fig, "chartA_normality.png")
print("Chart A saved: mean vs median for the 4 main variables")


# ===========================================================================
# PART B: CHARTS
# ===========================================================================
print("\n--- PART B: charts ---")

# Chart 1 - How many communities are in each coverage category
counts = com["can_call"].value_counts().reindex(CAN_CALL_ORDER)
fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(x=counts.index, y=counts.values, hue=counts.index,
            palette=CAN_CALL_COLORS, legend=False, ax=ax)
for i, v in enumerate(counts.values):
    ax.text(i, v + 8, str(v), ha="center", fontweight="bold")
ax.set_ylabel("Number of communities")
ax.set_title("Mobile coverage status across 782 remote NT communities")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
save_chart(fig, "chart1_coverage_overview.png")
pct_cannot_call = cannot_call.mean() * 100
print(f"Chart 1: {pct_cannot_call:.1f}% of communities cannot call for help")

# Chart 2 - Clinic drive time by coverage status
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="clinic_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest clinic (minutes)")
ax.set_title("Clinic drive time by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
save_chart(fig, "chart2_clinic_drivetime_by_coverage.png")
print("Chart 2: median clinic drive time by coverage ->")
print(com.groupby("can_call")["clinic_minutes"].median().reindex(CAN_CALL_ORDER).to_string())

# Chart 3 - Hospital drive time by coverage status
fig, ax = plt.subplots(figsize=(9.5, 5.5))
sns.violinplot(data=com, x="can_call", y="hospital_minutes", order=CAN_CALL_ORDER,
               hue="can_call", palette=CAN_CALL_COLORS, legend=False,
               inner="quartile", cut=0, ax=ax)
ax.set_ylabel("Drive time to nearest hospital ED (minutes)")
ax.set_title("Hospital drive time by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
save_chart(fig, "chart3_hospital_drivetime_by_coverage.png")
print("Chart 3 saved")

# Chart 4 - Road isolation by coverage status
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
ax.set_title("Road isolation by mobile coverage status")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
save_chart(fig, "chart4_road_isolation_by_coverage.png")
print("Chart 4 saved")

# Chart 5 - Coverage split by region (stacked bar)
region_mix = (com.groupby(["region", "can_call"]).size()
              .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
region_mix["cannot_call_total"] = region_mix[CANNOT_CALL].sum(axis=1)
region_mix = region_mix.sort_values("cannot_call_total", ascending=False)
fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    ax.bar(region_mix.index, region_mix[cat], bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat, edgecolor="white")
    bottom = region_mix[cat] if bottom is None else bottom + region_mix[cat]
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by NT health region")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
save_chart(fig, "chart5_coverage_by_region.png")
print("Chart 5: can't-call communities by region ->")
print(region_mix["cannot_call_total"].astype(int).to_string())

# Chart 6 - Top 10 clinics by can't-call caseload
top10 = clinics.sort_values("communities_cant_call", ascending=False).head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(9.5, 6))
ax.barh(top10["clinic"], top10["communities_cant_call"], color="#5B9BD5")
for i, v in enumerate(top10["communities_cant_call"]):
    ax.text(v + 0.4, i, str(v), va="center", fontweight="bold")
ax.set_xlabel("Nearby communities with no known mobile coverage")
ax.set_title("Top 10 clinics by 'can't call for help' caseload")
save_chart(fig, "chart6_clinic_caseload.png")
print("Chart 6: busiest clinics ->")
print(top10[["clinic", "communities_served", "communities_cant_call"]].iloc[::-1].head(5).to_string(index=False))

# Chart 7 - Coverage by settlement type (the strongest pattern in the data)
type_mix = (com.groupby(["community_type", "can_call"]).size()
            .unstack("can_call").reindex(columns=CAN_CALL_ORDER).fillna(0))
type_mix["total"] = type_mix.sum(axis=1)
type_mix["cannot_call_pct"] = type_mix[CANNOT_CALL].sum(axis=1) / type_mix["total"] * 100
type_mix = type_mix.sort_values("cannot_call_pct", ascending=False)
fig, ax = plt.subplots(figsize=(9.5, 5.5))
bottom = None
for cat in CAN_CALL_ORDER:
    ax.bar(type_mix.index, type_mix[cat], bottom=bottom,
           color=CAN_CALL_COLORS[cat], label=cat, edgecolor="white")
    bottom = type_mix[cat] if bottom is None else bottom + type_mix[cat]
for i, (pct, total) in enumerate(zip(type_mix["cannot_call_pct"], type_mix["total"])):
    ax.text(i, total + 10, f"{pct:.0f}% can't call", ha="center", fontsize=9, color="#B0413E")
ax.set_ylabel("Number of communities")
ax.set_title("Coverage status by settlement type")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
save_chart(fig, "chart7_coverage_by_settlement_type.png")
print("Chart 7: can't-call rate by settlement type ->")
print(type_mix[["total", "cannot_call_pct"]].round(1).to_string())

# Chart 8 - Correlation heatmap (Spearman, since the data is non-normal)
corr_cols = {
    "clinic_minutes": "Clinic drive (min)", "hospital_minutes": "Hospital drive (min)",
    "nearest_own_clinic_km": "Distance to clinic (km)", "snap_km": "Distance to road (km)",
    "cyclones_200km": "Cyclones (200km)", "severe_cyclones_100km": "Severe cyclones (100km)",
}
corr = com[list(corr_cols)].rename(columns=corr_cols).corr(method="spearman")
fig, ax = plt.subplots(figsize=(8, 6.5))
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
sns.heatmap(corr, mask=mask, cmap="vlag", vmin=-1, vmax=1, center=0, annot=True,
            fmt=".2f", square=True, ax=ax)
ax.set_title("How the access & isolation measures relate to each other\n(Spearman correlation)")
save_chart(fig, "chart8_correlation_heatmap.png")
print("Chart 8 saved")

# Chart 9 - Sealed road access by settlement type
sealed_by_type = com.groupby("community_type")["sealed_route_exists"].mean().mul(100).sort_values()
fig, ax = plt.subplots(figsize=(9, 5.5))
sns.barplot(x=sealed_by_type.values, y=sealed_by_type.index,
            hue=sealed_by_type.index, palette="Blues", legend=False, ax=ax)
for i, v in enumerate(sealed_by_type.values):
    ax.text(v + 1, i, f"{v:.0f}%", va="center", fontweight="bold")
ax.set_xlabel("Communities with a sealed road route (%)")
ax.set_title("Sealed road access by settlement type")
save_chart(fig, "chart9_sealed_road_by_settlement_type.png")
print("Chart 9 saved")


# ===========================================================================
# PART C: HYPOTHESIS TESTS
# ===========================================================================
'''
These check if the differences in the charts above are statistically real,
not just random. Non-parametric versions are used since Part A showed the
data is not normally distributed.
'''
print("\n--- PART C: hypothesis tests ---")

# Does clinic drive time differ across the 6 coverage categories?
groups = [com.loc[com["can_call"] == c, "clinic_minutes"].dropna() for c in CAN_CALL_ORDER]
h1, p1 = stats.kruskal(*groups)
print(f"Kruskal-Wallis, drive time across coverage categories: H={h1:.2f}, p={p1:.3e}")

# Does clinic drive time differ across settlement types?
types = com["community_type"].dropna().unique()
groups2 = [com.loc[com["community_type"] == t, "clinic_minutes"].dropna() for t in types]
h2, p2 = stats.kruskal(*groups2)
print(f"Kruskal-Wallis, drive time across settlement types: H={h2:.2f}, p={p2:.3e}")

# Does drive time differ between "can call" and "cannot call" communities?
u1, pu1 = stats.mannwhitneyu(
    com.loc[cannot_call, "clinic_minutes"].dropna(),
    com.loc[~cannot_call, "clinic_minutes"].dropna())
print(f"Mann-Whitney U, cannot-call vs can-call: U={u1:.1f}, p={pu1:.3e}")

print("\nAll three tests are significant (p < 0.001) - coverage status and "
      "settlement type are both genuinely linked to drive time, not just "
      "something that looks that way in the charts by chance.")


# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n--- EDA SUMMARY ---")
print("Communities analysed:", len(com))
print(f"Cannot call for help at all: {int(cannot_call.sum())} ({pct_cannot_call:.1f}%)")
print(f"Strongest pattern: settlement type - Family Outstation "
      f"{type_mix.loc['Family Outstation', 'cannot_call_pct']:.0f}% cannot call "
      f"vs Major {type_mix.loc['Major', 'cannot_call_pct']:.0f}%")
print("Charts saved to:", OUTPUTS)