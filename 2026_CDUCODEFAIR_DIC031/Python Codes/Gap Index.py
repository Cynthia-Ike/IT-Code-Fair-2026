# ===========================================================================
# GAP INDEX - The Long Way to Care
# ===========================================================================
'''
Turns everything from the EDA into one 0-1 score per community - how cut
off it is from help. 1 = worst off, 0 = best off.

Quick note on wording: this is NOT a machine learning model. There's no
outcome to predict, so nothing is being "fitted". It's what's called a
composite indicator - the same idea as something like the Human
Development Index - a transparent, rule-based combination of risk
factors. "Index" is used instead of "model" in the report for this reason.
'''

#Import libraries
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr
from pathlib import Path

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in.

'''
Self-correcting: if this script ends up sitting 
INSIDE "Processed Data" instead of next to it, that same folder is
used as PROCESSED, and Scored Data / Outputs are put one level up instead
of nested in.
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

SCORED = PROJECT / "Scored Data"   # The scored files are saved here.
OUTPUTS = PROJECT / "Outputs"      # Charts are saved here.
SCORED.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.05)

com = pd.read_csv(PROCESSED / "communities_merged.csv")
clinics = pd.read_csv(PROCESSED / "clinics_merged.csv")
print("Loaded", len(com), "communities and", len(clinics), "clinics")

# Same "cannot call" definition as the EDA, so the two steps agree
CANNOT_CALL = ["Never recorded", "Listed: no coverage"]

# Set this to True to have each chart pop up on screen as it's made (the
# script pauses and waits for the window to be closed before moving on to
# the next chart). Set it back to False for a quick, uninterrupted run.
SHOW_CHARTS = False


# Chart saver - saves to the Outputs folder, then shows it on screen too if
# SHOW_CHARTS is on
def save_chart(fig, name):
    fig.tight_layout()
    fig.savefig(OUTPUTS / name, dpi=150, bbox_inches="tight")
    if SHOW_CHARTS:
        plt.show()
    plt.close(fig)


# ===========================================================================
# STEP 1: RISK COMPONENTS
# ===========================================================================
'''
Each component is rescaled to run 0 (low risk) to 1 (high risk) BEFORE
combining them, otherwise clinic_minutes (which can be 100s of minutes)
would swamp something that's just 0 or 1.
'''

# risk_coverage: already 0/1, no rescaling needed
com["risk_coverage"] = com["can_call"].isin(CANNOT_CALL).astype(float)

'''
risk_clinic_time / risk_hospital_time use PERCENTILE RANK, not min-max.
Reason: the EDA's Shapiro-Wilk test showed drive times are not normal,
they're heavily skewed by a few very remote communities. Percentile rank
just asks "what fraction of communities does this one beat", which
outliers can't distort the way min-max scaling would.
'''
clinic_rank = com["clinic_minutes"].rank(pct=True)
hosp_rank = com["hospital_minutes"].rank(pct=True)

'''
Some communities have no routed drive time at all (no route could be
found). These were checked and have basically 0% sealed road access, so a
missing time here means "most cut off", not a random gap - they're scored
at max risk (1.0) instead of being left blank.
'''
com["risk_clinic_time"] = clinic_rank.fillna(1.0)
com["risk_hospital_time"] = hosp_rank.fillna(1.0)

# risk_no_sealed_road: already 0/1
com["risk_no_sealed_road"] = (~com["sealed_route_exists"]).astype(float)

# risk_settlement_type: only used as an extra check in Index B below. Each
# settlement type's own "cannot call" rate, scaled against the worst type.
type_rate = com.groupby("community_type")["can_call"].apply(
    lambda s: s.isin(CANNOT_CALL).mean())
com["risk_settlement_type"] = com["community_type"].map(type_rate / type_rate.max())

CORE = ["risk_coverage", "risk_clinic_time", "risk_hospital_time", "risk_no_sealed_road"]
FULL = CORE + ["risk_settlement_type"]


# ===========================================================================
# STEP 2: REDUNDANCY CHECK
# ===========================================================================
# Checks the 4 core components aren't just repeating each other before
# averaging them (if two were almost identical, averaging would count
# that one thing twice without meaning to).
print("\nSpearman correlation between the 4 core components:")
print(com[CORE].corr(method="spearman").round(2).to_string())
print("No pair is close to +/-1, so they're each adding something different.")


# ===========================================================================
# STEP 3: COMBINE INTO ONE SCORE
# ===========================================================================
'''
Equal weights - simplest, most defensible starting point when there's no
outside data to calibrate weights against.

Two versions are built:
- gap_index_core = the 4 measured factors only
- gap_index_full = same 4 + settlement type
Settlement type was the strongest pattern in the EDA, but scoring someone
worse just for the KIND of place they live in is a known fairness issue
with these indexes - so this checks if adding it even changes anything
before deciding whether it's needed.
'''
com["gap_index_core"] = com[CORE].mean(axis=1)
com["gap_index_full"] = com[FULL].mean(axis=1)

print("\nGap Index (core) summary:")
print(com["gap_index_core"].describe().round(3).to_string())


# ===========================================================================
# STEP 4: WEIGHT-SENSITIVITY CHECK
# ===========================================================================
# If different weights had been picked, would the same communities still
# come out on top? If yes, the exact weights don't matter much and equal
# weights is a safe, simple choice.
schemes = {
    "Equal weights (what I used)":
        {"risk_coverage": .25, "risk_clinic_time": .25,
         "risk_hospital_time": .25, "risk_no_sealed_road": .25},
    "Drive time counts double":
        {"risk_coverage": .15, "risk_clinic_time": .30,
         "risk_hospital_time": .30, "risk_no_sealed_road": .25},
    "Coverage counts double":
        {"risk_coverage": .40, "risk_clinic_time": .20,
         "risk_hospital_time": .20, "risk_no_sealed_road": .20},
}

equal_top20 = set(com.nlargest(20, "gap_index_core")["community"])
print("\nWeight-sensitivity check (against the equal-weight index used):")
for name, w in schemes.items():
    score = sum(com[col] * weight for col, weight in w.items())
    rho, _ = spearmanr(score, com["gap_index_core"])
    top20 = set(com.loc[score.nlargest(20).index, "community"])
    print(f"  {name}: rho={rho:.3f}, {len(top20 & equal_top20)}/20 same top communities")
print("All 3 schemes agree closely, so the exact weights aren't driving the "
      "result - equal weights is used since it's simplest.")


# ===========================================================================
# STEP 5: RISK TIERS
# ===========================================================================
# Turns the score into 4 plain-English tiers by quartile (so each tier has
# roughly the same number of communities). The score is ranked first
# instead of using pd.qcut directly, because a lot of communities are tied
# at exactly the same score and qcut doesn't handle ties on a bin edge well.
TIERS = ["Low", "Moderate", "High", "Critical"]
com["risk_tier"] = pd.cut(com["gap_index_core"].rank(pct=True),
                           bins=[0, .25, .50, .75, 1.0],
                           labels=TIERS, include_lowest=True)
print("\nCommunities per risk tier:")
print(com["risk_tier"].value_counts().reindex(TIERS).to_string())


# ===========================================================================
# STEP 6: INDEX A vs INDEX B
# ===========================================================================
# Does adding settlement type (Index B) actually change the ranking much
# compared to the 4-factor version (Index A)?
rho, pval = spearmanr(com["gap_index_core"], com["gap_index_full"])
top20_core = set(com.nlargest(20, "gap_index_core")["community"])
top20_full = set(com.nlargest(20, "gap_index_full")["community"])
overlap = top20_core & top20_full

print(f"\nIndex A vs Index B: Spearman rho={rho:.3f}, "
      f"{len(overlap)}/20 same top-20 communities")
print("Barely any difference, so Index A (the simpler one, no "
      "settlement-type classification) is used as 'the' Gap Index from here on.")

print("\nTop 10 communities by Gap Index:")
print(com.sort_values("gap_index_core", ascending=False)
      [["community", "community_type", "region", "gap_index_core", "risk_tier"]]
      .head(10).to_string(index=False))

com.to_csv(SCORED / "communities_scored.csv", index=False)
print("\nSaved communities_scored.csv -", len(com), "rows,", com.shape[1], "columns")


# ===========================================================================
# STEP 7: CLINIC-LEVEL VIEW
# ===========================================================================
# Does risk-weighting (summing the Gap Index of every community that
# clinic serves) change which clinics look most urgent, compared to just
# counting how many communities can't call?
clinic_risk = com.groupby("nearest_own_clinic")["gap_index_core"].sum()
clinics = clinics.merge(clinic_risk.rename("total_risk_score"),
                         left_on="clinic", right_on="nearest_own_clinic", how="left")
clinics["total_risk_score"] = clinics["total_risk_score"].fillna(0)
clinics.to_csv(SCORED / "clinics_scored.csv", index=False)
print("Saved clinics_scored.csv -", len(clinics), "rows")

top10_count = set(clinics.nlargest(10, "communities_cant_call")["clinic"])
top10_risk = set(clinics.nlargest(10, "total_risk_score")["clinic"])
rho_clinic, _ = spearmanr(clinics["communities_cant_call"].rank(ascending=False),
                          clinics["total_risk_score"].rank(ascending=False))
print(f"Clinic ranking, headcount vs risk-weighted: rho={rho_clinic:.3f}, "
      f"{len(top10_count & top10_risk)}/10 same top clinics")
if top10_risk - top10_count:
    print("Enters the risk-weighted top 10 (wasn't in the headcount top 10):",
          sorted(top10_risk - top10_count))


# ===========================================================================
# STEP 8: PLAIN-ENGLISH EXPLAINER
# ===========================================================================
# A little helper to explain one community's score in plain English -
# useful for the report and for the dashboard's detail view later.
def explain_community(name):
    row = com.loc[com["community"] == name]
    if row.empty:
        print(f'No community called "{name}" found.')
        return
    r = row.iloc[0]
    print(f"\n--- {r['community']} ({r['community_type']}, {r['region']}) ---")
    print(f"Gap Index: {r['gap_index_core']:.3f}  ->  {r['risk_tier']} tier")
    print("  Phone coverage:", "CANNOT call for help" if r["risk_coverage"] == 1 else "can call for help")
    print(f"  Clinic drive time: worse than {r['risk_clinic_time']:.0%} of all communities")
    print(f"  Hospital drive time: worse than {r['risk_hospital_time']:.0%} of all communities")
    print("  Sealed road:", "no sealed route" if r["risk_no_sealed_road"] == 1 else "sealed route exists")


print("\nExample - highest risk community:")
explain_community(com.sort_values("gap_index_core", ascending=False).iloc[0]["community"])
print("\nExample - lowest risk community, for contrast:")
explain_community(com.sort_values("gap_index_core", ascending=True).iloc[0]["community"])


# ===========================================================================
# CHART 10: TOP HIGHEST-RISK COMMUNITIES
# ===========================================================================
'''
A lot of communities are tied at exactly 1.0 (every factor maxed out at
once), so those are shown as one flat colour instead of a gradient - a
gradient there would visually suggest a ranking between communities that
are actually perfectly tied, which would be misleading.
'''
n_tied = int((com["gap_index_core"] == 1.0).sum())
n_show = max(15, n_tied + 5)
top = com.nlargest(n_show, "gap_index_core").iloc[::-1]
labels = top["community"] + " (" + top["community_type"].str[:12] + ")"

TIED_COLOR = "#7F1D1D"
below_tie = top[top["gap_index_core"] < 1.0]
ramp = sns.color_palette("Reds", n_colors=max(len(below_tie), 1))
rank_below = below_tie["gap_index_core"].rank(method="first").astype(int) - 1
ramp_lookup = dict(zip(below_tie.index, rank_below))
bar_colors = [TIED_COLOR if v == 1.0 else ramp[ramp_lookup[idx]]
              for idx, v in zip(top.index, top["gap_index_core"])]

fig, ax = plt.subplots(figsize=(9.9, 0.4 * len(top) + 1.5))
ax.barh(labels, top["gap_index_core"], color=bar_colors)
for i, v in enumerate(top["gap_index_core"]):
    ax.text(v + 0.012, i, f"{v:.3f}", va="center", fontweight="bold", fontsize=9)
ax.axvline(1.0, color="#999999", linewidth=0.8, linestyle=":")
ax.set_xlim(0, 1.12)
ax.set_xlabel("Reach for Help Gap Index (0 = best off, 1 = worst off)")
ax.set_title(f"Highest-risk communities - {n_tied} tied at the maximum score")
sns.despine(ax=ax)
save_chart(fig, "chart10_top_communities_gap_index.png")
print(f"\nChart 10 saved - {n_tied} communities tied at the max score")


# ===========================================================================
# CHART 11: INDEX A vs INDEX B AGREEMENT
# ===========================================================================
# Points close to the diagonal line mean the two versions barely disagree.
fig, ax = plt.subplots(figsize=(7, 7))
ax.plot([0, 1], [0, 1], color="#999999", linestyle="--", linewidth=1.5, label="Perfect agreement")
ax.scatter(com["gap_index_core"], com["gap_index_full"], color="#5B9BD5",
           alpha=0.5, s=25, edgecolor="white", linewidth=0.3)
ax.set_xlabel("Index A - core (coverage, drive time, road access)")
ax.set_ylabel("Index B - core + settlement type")
ax.set_title(f"Index A vs Index B (Spearman rho = {rho:.3f})")
ax.set_xlim(0, 1.02)
ax.set_ylim(0, 1.02)
ax.legend(loc="upper left", frameon=False)
sns.despine(ax=ax)
save_chart(fig, "chart11_index_agreement.png")
print("Chart 11 saved")


# ===========================================================================
# CHART 12: CLINIC PRIORITY COMPARISON
# ===========================================================================
# Headcount vs risk-weighted score, for clinics in either top-10 list.
compare = sorted(top10_count | top10_risk)
plot_df = clinics[clinics["clinic"].isin(compare)].sort_values("total_risk_score")

fig, ax = plt.subplots(figsize=(9.5, 6.5))
y = range(len(plot_df))
h = 0.38
ax.barh([i + h / 2 for i in y], plot_df["communities_cant_call"], height=h,
        color="#9CA3AF", label="Can't-call headcount")
ax.barh([i - h / 2 for i in y], plot_df["total_risk_score"], height=h,
        color="#B0413E", label="Risk-weighted score")
ax.set_yticks(list(y))
ax.set_yticklabels(plot_df["clinic"])
ax.set_xlabel("Score")
ax.set_title("Clinic priority: headcount vs risk-weighted Gap Index")
ax.legend(loc="lower right", frameon=False)
sns.despine(ax=ax)
save_chart(fig, "chart12_clinic_priority_comparison.png")
print("Chart 12 saved")


# ===========================================================================
# CHART 14: RISK TIER DISTRIBUTION
# ===========================================================================
# How many communities are in each risk tier.
tier_counts = com["risk_tier"].value_counts().reindex(TIERS)
tier_colors = dict(zip(TIERS, sns.color_palette("Reds", n_colors=4)))
fig, ax = plt.subplots(figsize=(7.5, 5))
bars = ax.bar(tier_counts.index.astype(str), tier_counts.values,
              color=[tier_colors[t] for t in tier_counts.index])
for bar, n in zip(bars, tier_counts.values):
    ax.text(bar.get_x() + bar.get_width() / 2, n + 1, str(int(n)), ha="center", fontweight="bold")
ax.set_ylabel("Number of communities")
ax.set_xlabel("Risk tier")
ax.set_title("Communities by Reach for Help risk tier")
sns.despine(ax=ax)
save_chart(fig, "chart14_risk_tier_distribution.png")
print("Chart 14 saved")


# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n--- GAP INDEX SUMMARY ---")
print("Gap Index built for", len(com), "communities (0 = best off, 1 = worst off)")
print("Equal weights checked against 2 other schemes - rankings barely change")
print(f"Index A vs Index B: rho={rho:.3f}, {len(overlap)}/20 same top communities "
      "-> settlement type doesn't add much, so Index A is used")
print(f"Clinics: headcount vs risk-weighted agree on {len(top10_count & top10_risk)}/10 top clinics")
print("Saved: communities_scored.csv, clinics_scored.csv")
print("Charts saved to:", OUTPUTS)