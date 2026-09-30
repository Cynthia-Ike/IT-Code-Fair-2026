# ===========================================================================
# DASHBOARD - The Long Way to Care
# ===========================================================================
'''
Turns the scored data from the Gap Index step into ONE offline HTML file:
a search box for any community or clinic, headline numbers, a map, a
region-by-region view of risk, a clinic load chart and a coverage-gap
report form.

It has to work with NO internet connection, since that's the whole point
of the project, so every chart, every phone number and even the fonts are
baked straight into the file (no CDN, no web fonts, no server).

Note on comment style below: the HTML/CSS/JS part gets shorter comments
than the Python scripts. A big front-end file like this normally gets
brief section labels rather than a comment on every line, so that's the
style kept here too.
'''

#Import libraries
import json
import base64
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent  # BASE is the folder this script itself is sitting in.

'''
Same self-correcting trick as the earlier scripts: if this script ends up
sitting INSIDE "Scored Data" instead of next to it, that same folder is
used as SCORED, and Outputs is put one level up instead of nested in.
'''
if BASE.name == "Scored Data":
    SCORED = BASE
    PROJECT = BASE.parent
else:
    SCORED = BASE / "Scored Data"
    PROJECT = BASE

if not SCORED.exists():
    raise FileNotFoundError(
        f"Can't find a 'Scored Data' folder. Looked for it at:\n  {SCORED}\n"
        f"Run model_simple.py first - it builds the scored files this "
        f"script needs.")

OUTPUTS = PROJECT / "Outputs"  # The dashboard HTML file is saved here.
OUTPUTS.mkdir(parents=True, exist_ok=True)

FONTS = PROJECT / "Fonts"  # Optional - Inter and Source Serif 4 font files.

com = pd.read_csv(SCORED / "communities_scored.csv")
clinics = pd.read_csv(SCORED / "clinics_scored.csv")
print("Loaded", len(com), "scored communities and", len(clinics), "scored clinics")

CANNOT_CALL = ["Never recorded", "Listed: no coverage"]
TIERS = ["Low", "Moderate", "High", "Critical"]


# ===========================================================================
# STEP 1: FONTS
# ===========================================================================
'''
The fonts are read from the Fonts folder and turned into text (base64) so
they can live INSIDE the HTML file - that way the dashboard looks the same
on every computer, even one that has never been online.

If the Fonts folder is missing, nothing breaks: the page just falls back
to fonts already on the computer (Segoe UI and Cambria on Windows).
'''
def font_face(family, file_name, weight):
    path = FONTS / file_name
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f"@font-face{{font-family:'{family}';"
            f"src:url(data:font/woff2;base64,{encoded}) format('woff2');"
            f"font-weight:{weight};font-style:normal;font-display:swap;}}\n")

FONT_CSS = (font_face("Inter", "Inter.woff2", "100 900")
            + font_face("Source Serif 4", "SourceSerif4-SemiBold.woff2", "600"))

if FONT_CSS:
    print("Fonts embedded from", FONTS)
else:
    print("No Fonts folder found - using the computer's own fonts instead")


# ===========================================================================
# STEP 2: DATA PAYLOAD
# ===========================================================================
'''
Builds a compact data payload for the page. Short key names (n, t, r, etc.)
just keep the embedded data smaller - the JavaScript below spells each one
back out, so nothing is hidden, just shortened.
'''

# Turns a pandas value into something JSON can hold (NaN becomes null)
def clean(value, digits=None):
    if pd.isna(value):
        return None
    if digits is not None:
        return round(float(value), digits)
    return value

def region_name(value):
    return value if pd.notna(value) else "No region listed"

clinic_lookup = clinics.set_index("clinic")[
    ["phone", "hours", "emergency_24_7", "phone_valid"]].to_dict(orient="index")

'''
Two different "nearest clinic" columns exist, and they answer different
questions:
- nearest_clinic comes from the road routing - the health service you can
  DRIVE to fastest (drawn from a wider list of clinics and GP services).
- nearest_own_clinic is the closest of the 91 listed remote clinics - the
  one whose phone number and hours are on file.
Both are kept, and the dashboard labels them separately so a drive time is
never shown next to the wrong clinic's name.
'''
community_records = []
for _, r in com.iterrows():
    info = clinic_lookup.get(r["nearest_own_clinic"], {})
    community_records.append({
        "n": r["community"], "t": r["community_type"], "r": region_name(r["region"]),
        "la": round(float(r["lat"]), 4), "lo": round(float(r["lon"]), 4),
        "cc": r["can_call"], "gi": round(float(r["gap_index_core"]), 3),
        "tier": r["risk_tier"],
        "rc": clean(r["nearest_clinic"]),                  # Routed nearest health service
        "cm": clean(r["clinic_minutes"], 0),
        "ck": clean(r["clinic_road_km"], 0),
        "hn": clean(r["nearest_hospital_ed"]),
        "hm": clean(r["hospital_minutes"], 0),
        "hk": clean(r["hospital_road_km"], 0),
        "uk": clean(r["hospital_unsealed_km"], 0),
        "sr": bool(r["sealed_route_exists"]),
        "cl": r["nearest_own_clinic"],                     # Listed remote clinic
        "cp": clean(info.get("phone")), "ch": clean(info.get("hours")),
        "ce": bool(info.get("emergency_24_7", False)),
        "cv": bool(info.get("phone_valid", True)),
    })

# Full clinic directory - all 91, so any clinic can be searched by name
clinic_records = []
for _, r in clinics.iterrows():
    clinic_records.append({
        "n": r["clinic"], "r": region_name(r["region"]),
        "op": clean(r["operator"]),
        "phone": clean(r["phone"]), "pv": bool(r["phone_valid"]),
        "hours": clean(r["hours"]), "e24": bool(r["emergency_24_7"]),
        "served": int(r["communities_served"]) if pd.notna(r["communities_served"]) else 0,
        "cantCall": int(r["communities_cant_call"]) if pd.notna(r["communities_cant_call"]) else 0,
        "risk": clean(r["total_risk_score"], 2) or 0,
        "la": clean(r["lat"], 4), "lo": clean(r["lon"], 4),
    })

# Top 20 communities by Gap Index, for the priority table beside the map
top20 = com.sort_values("gap_index_core", ascending=False).head(20)
priority_records = [{
    "n": row["community"], "r": region_name(row["region"]),
    "gi": round(float(row["gap_index_core"]), 3), "tier": row["risk_tier"],
} for _, row in top20.iterrows()]

'''
Region summary - for each region, how its communities split across the
four risk tiers, what share can't call for help, and the average Gap
Index. Sorted so the region with the highest average risk comes first.
'''
com["cannot_call"] = com["can_call"].isin(CANNOT_CALL)
region_records = []
for region, group in com.groupby(com["region"].fillna("No region listed")):
    tiers = group["risk_tier"].value_counts().reindex(TIERS).fillna(0).astype(int)
    region_records.append({
        "r": region, "n": len(group),
        "tiers": {t: int(tiers[t]) for t in TIERS},
        "cantCallPct": round(group["cannot_call"].mean() * 100, 1),
        "meanGap": round(group["gap_index_core"].mean(), 3),
    })
region_records.sort(key=lambda x: (x["r"] == "No region listed", -x["meanGap"]))

'''
The six public hospitals with an emergency department, placed on the map
as landmarks. Coordinates are town-level (good enough for a territory-wide
map, not for navigation).
'''
hospital_records = [
    {"n": "Royal Darwin Hospital", "la": -12.356, "lo": 130.879, "label": "Darwin"},
    {"n": "Palmerston Regional Hospital", "la": -12.502, "lo": 131.010, "label": ""},
    {"n": "Katherine Hospital", "la": -14.460, "lo": 132.262, "label": "Katherine"},
    {"n": "Gove District Hospital", "la": -12.189, "lo": 136.782, "label": "Nhulunbuy"},
    {"n": "Tennant Creek Hospital", "la": -19.646, "lo": 134.188, "label": "Tennant Creek"},
    {"n": "Alice Springs Hospital", "la": -23.702, "lo": 133.878, "label": "Alice Springs"},
]

# Headline numbers for the row of tiles under the search box
n_total = len(com)
n_cannot_call = int(com["cannot_call"].sum())
pct_cannot_call = round(com["cannot_call"].mean() * 100, 1)
median_hospital_min = int(com["hospital_minutes"].median())
over_4h = int((com["hospital_minutes"] > 240).sum())
no_road = int(com["hospital_minutes"].isna().sum())
no_247 = int((~clinics["emergency_24_7"].astype(bool)).sum())

kpis = {
    "total": n_total, "cannotCall": n_cannot_call, "pctCannotCall": pct_cannot_call,
    "medianHospitalMin": median_hospital_min, "over4h": over_4h, "noRoad": no_road,
    "no247": no_247, "clinics": len(clinics), "hospitals": len(hospital_records),
    "tierCounts": {t: int((com["risk_tier"] == t).sum()) for t in TIERS},
}
print(f"KPIs: {n_cannot_call} of {n_total} can't call ({pct_cannot_call}%), "
      f"median hospital drive {median_hospital_min} min, {no_road} with no road, "
      f"{no_247} of {len(clinics)} clinics without 24/7")

DATA_JS = "\n".join([
    "const COMMUNITIES = " + json.dumps(community_records, separators=(",", ":")) + ";",
    "const CLINICS = " + json.dumps(clinic_records, separators=(",", ":")) + ";",
    "const PRIORITY = " + json.dumps(priority_records, separators=(",", ":")) + ";",
    "const REGIONS = " + json.dumps(region_records, separators=(",", ":")) + ";",
    "const HOSPITALS = " + json.dumps(hospital_records, separators=(",", ":")) + ";",
    "const KPI = " + json.dumps(kpis, separators=(",", ":")) + ";",
])


# ===========================================================================
# STEP 3: THE PAGE ITSELF
# ===========================================================================
# One HTML file - styling, data and script all included.
TITLE = "The Long Way to Care"

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<style>
__FONT_CSS__
/* ---------- Colour tokens (light, then dark) ---------- */
:root{
  color-scheme:light;
  --page:#f5f3ee; --card:#ffffff; --card-2:#f8f7f3; --inset:#f1efe9;
  --line:#e3e0d8; --line-strong:#cfcbc1;
  --ink:#15191c; --ink-2:#4b5156; --ink-3:#7b8186;
  --band:#10262d; --band-2:#163641; --band-ink:#f3f0e8; --band-ink-2:#b9c7c9;
  --accent:#0e6b7a; --accent-ink:#ffffff; --accent-soft:#e3f0f1;
  --map-bg:#fcfcfb; --map-border:#b9b5aa;
  /* Risk tiers - one warm hue, light to dark (validated ordinal ramp) */
  --t1:#e39a4a; --t2:#d4692f; --t3:#ab3d21; --t4:#712410;
  --t1-ink:#15191c; --t2-ink:#15191c; --t3-ink:#ffffff; --t4-ink:#ffffff;
  /* Phone coverage - warm (none) / grey midpoint (partial) / blue (strong) */
  --c-none:#c4502a; --c-part:#8b8984; --c-strong:#256abf;
  --series:#2a78d6;
  --good:#0a7d0a; --warn-bg:#fbeee7; --warn-line:#e2b8a3; --ok-bg:#eaf4ea; --ok-line:#b4d4b4;
  --shadow:0 1px 2px rgba(16,38,45,.06), 0 8px 24px rgba(16,38,45,.06);
  --radius:14px;
  --serif:"Source Serif 4", "Iowan Old Style", Cambria, Georgia, serif;
  --sans:"Inter", "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    color-scheme:dark;
    --page:#0f1315; --card:#171c1f; --card-2:#1b2124; --inset:#20272a;
    --line:#2b3337; --line-strong:#3a4449;
    --ink:#f1efe9; --ink-2:#b8bfbf; --ink-3:#8a9294;
    --band:#0b1b20; --band-2:#10272e; --band-ink:#f3f0e8; --band-ink-2:#a9babd;
    --accent:#5cc0cf; --accent-ink:#0b1b20; --accent-soft:#16343a;
    --map-bg:#171b1e; --map-border:#4a5458;
    --t1:#7d3a1e; --t2:#b24c24; --t3:#e2683a; --t4:#ff9a6b;
    --t1-ink:#ffffff; --t2-ink:#ffffff; --t3-ink:#15191c; --t4-ink:#15191c;
    --c-none:#e2683a; --c-part:#7a7973; --c-strong:#3987e5;
    --series:#3987e5;
    --good:#4cc24c; --warn-bg:#2b1c16; --warn-line:#6b3a26; --ok-bg:#15261a; --ok-line:#2f5a36;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.25);
  }
}

/* ---------- Base ---------- */
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
@media (prefers-reduced-motion: reduce){ html{scroll-behavior:auto;} }
body{
  margin:0; background:var(--page); color:var(--ink);
  font-family:var(--sans); font-size:15.5px; line-height:1.55;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
}
.wrap{max-width:1200px; margin:0 auto; padding:0 16px;}
h1,h2,h3{font-family:var(--serif); font-weight:600; letter-spacing:-.01em; text-wrap:balance; margin:0;}
a{color:var(--accent);}
button{font:inherit;}
:focus-visible{outline:3px solid var(--accent); outline-offset:2px;}
.num{font-variant-numeric:tabular-nums;}
.sr-only{position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap;}

/* ---------- Masthead + search ---------- */
.masthead{
  background:radial-gradient(1200px 400px at 85% -20%, var(--band-2), transparent 70%), var(--band);
  color:var(--band-ink); padding:34px 0 30px;
}
.topline{display:flex; flex-wrap:wrap; gap:10px 18px; align-items:center; justify-content:space-between; margin-bottom:26px;}
@media (max-width:600px){ .topline{justify-content:center; text-align:center;} }
.eyebrow{font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--band-ink-2); font-weight:600;}
.offline{
  display:inline-flex; align-items:center; gap:8px; font-size:12.5px; font-weight:500;
  border:1px solid rgba(255,255,255,.22); border-radius:999px; padding:5px 12px; color:var(--band-ink);
}
.offline::before{content:""; width:8px; height:8px; border-radius:50%; background:#4cc24c; box-shadow:0 0 0 3px rgba(76,194,76,.2);}
.masthead h1{font-size:clamp(34px, 5.2vw, 56px); line-height:1.05; color:#fff; text-align:center;}
.questions{margin:16px auto 0; text-align:center;}
.dek{font-family:var(--serif); font-size:clamp(18px, 2.2vw, 23px); line-height:1.35; color:var(--band-ink); margin:0 auto;}
.dek + .dek{margin-top:4px; color:var(--band-ink-2);}
.intro{color:var(--band-ink-2); font-size:15px; max-width:68ch; margin:18px auto 0; text-align:center;}
.intro b{color:var(--band-ink); font-weight:600;}

.search{position:relative; margin:28px auto 0; max-width:760px;}
.search label{display:block; font-size:13px; font-weight:600; color:var(--band-ink); margin-bottom:8px; text-align:center;}
.search-box{position:relative;}
.search-box svg{position:absolute; left:16px; top:50%; transform:translateY(-50%); width:20px; height:20px; color:#6b7479; pointer-events:none;}
#q{
  width:100%; font:inherit; font-size:17px; color:#15191c; background:#fff;
  border:0; border-radius:12px; padding:16px 44px 16px 48px;
  box-shadow:0 0 0 1px rgba(255,255,255,.15), 0 10px 30px rgba(0,0,0,.25);
}
#q::placeholder{color:#7b8186;}
#q:focus{outline:3px solid #5cc0cf; outline-offset:2px;}
#clearQ{
  position:absolute; right:10px; top:50%; transform:translateY(-50%); border:0; background:transparent;
  color:#6b7479; font-size:22px; line-height:1; width:32px; height:32px; border-radius:8px; cursor:pointer; display:none;
}
#clearQ:hover{background:#f1efe9;}
.suggest{
  position:absolute; left:0; right:0; top:calc(100% + 6px); z-index:40; list-style:none; margin:0; padding:6px;
  background:#fff; color:#15191c; border-radius:12px; box-shadow:0 18px 40px rgba(0,0,0,.28); max-height:360px; overflow:auto;
}
.suggest[hidden]{display:none;}
.suggest li{display:flex; align-items:center; justify-content:space-between; gap:12px; padding:10px 12px; border-radius:8px; cursor:pointer;}
.suggest li[aria-selected="true"], .suggest li:hover{background:#eef4f5;}
.suggest .s-name{font-weight:600;}
.suggest .s-name mark{background:transparent; color:#0e6b7a; font-weight:700;}
.suggest .s-sub{font-size:12.5px; color:#6b7479; white-space:nowrap;}
.suggest .s-type{font-size:11px; font-weight:600; letter-spacing:.04em; text-transform:uppercase; padding:2px 7px; border-radius:6px; margin-right:6px;}
.s-type.community{background:#f6e7dc; color:#8a3a18;}
.s-type.clinic{background:#dff0f2; color:#0b5a67;}
.suggest .s-empty{color:#6b7479; cursor:default;}
.try{margin-top:12px; font-size:13px; color:var(--band-ink-2); display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:center;}
.try button{
  border:1px solid rgba(255,255,255,.22); background:rgba(255,255,255,.06); color:var(--band-ink);
  border-radius:999px; padding:4px 12px; font-size:13px; cursor:pointer;
}
.try button:hover{background:rgba(255,255,255,.14);}

/* ---------- Result card ---------- */
#result{margin-top:-6px;}
#result:empty{display:none;}
.result{
  background:var(--card); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow);
  margin:24px 0 0; padding:22px 24px; scroll-margin-top:16px;
}
.r-head{display:flex; flex-wrap:wrap; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:16px;}
.r-head h2{font-size:28px; line-height:1.15;}
.r-sub{color:var(--ink-2); font-size:14px; margin-top:4px;}
.r-actions{display:flex; gap:8px; flex-wrap:wrap;}
.btn{
  display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line-strong); background:var(--card);
  color:var(--ink); border-radius:9px; padding:7px 12px; font-size:13.5px; font-weight:500; cursor:pointer; text-decoration:none;
}
.btn:hover{background:var(--inset);}
.btn.primary{background:var(--accent); color:var(--accent-ink); border-color:var(--accent);}
.btn.primary:hover{filter:brightness(1.08);}
.r-grid{display:grid; grid-template-columns:1.05fr 1fr; gap:18px;}
@media (max-width:860px){ .r-grid{grid-template-columns:1fr;} }
.callout{border-radius:12px; padding:16px 18px; border:1px solid;}
.callout.warn{background:var(--warn-bg); border-color:var(--warn-line);}
.callout.ok{background:var(--ok-bg); border-color:var(--ok-line);}
.callout h3{font-family:var(--sans); font-size:16px; font-weight:700; margin:0 0 6px; letter-spacing:0;}
.callout p{margin:0 0 8px; font-size:14px; color:var(--ink-2);}
.callout ul{margin:6px 0 0; padding-left:18px; font-size:14px; color:var(--ink-2);}
.callout li{margin:3px 0;}
.callout .cov{font-size:12.5px; color:var(--ink-3); margin:10px 0 0;}
.panel{border:1px solid var(--line); border-radius:12px; padding:14px 16px; background:var(--card-2);}
.panel + .panel{margin-top:12px;}
.panel .p-label{font-size:11.5px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); margin-bottom:8px;}
.trip{display:grid; grid-template-columns:auto 1fr; gap:4px 14px; align-items:baseline; padding:8px 0; border-top:1px solid var(--line);}
.trip:first-of-type{border-top:0; padding-top:0;}
.trip .t-time{font-size:22px; font-weight:650; font-variant-numeric:tabular-nums; white-space:nowrap;}
.trip .t-what{font-size:14px; color:var(--ink-2);}
.trip .t-what b{color:var(--ink); font-weight:600;}
.phone{font-size:22px; font-weight:650; font-variant-numeric:tabular-nums; text-decoration:none; color:var(--accent);}
.phone:hover{text-decoration:underline;}
.meta{font-size:13.5px; color:var(--ink-2); margin-top:4px;}
.badge{display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600; padding:3px 9px; border-radius:999px; border:1px solid var(--line-strong); color:var(--ink-2);}
.badge.yes{border-color:var(--ok-line); background:var(--ok-bg); color:var(--good);}
.flag{font-size:12.5px; color:var(--ink-3); margin-top:6px;}
.gauge{margin-top:4px;}
.gauge-track{position:relative; height:10px; border-radius:6px; background:linear-gradient(90deg, var(--t1), var(--t2), var(--t3), var(--t4));}
.gauge-mark{position:absolute; top:-4px; width:4px; height:18px; border-radius:2px; background:var(--ink); box-shadow:0 0 0 2px var(--card); transform:translateX(-2px);}
.gauge-scale{display:flex; justify-content:space-between; font-size:11.5px; color:var(--ink-3); margin-top:6px;}
.stat-row{display:flex; gap:22px; flex-wrap:wrap;}
.stat-row div{min-width:120px;}
.stat-row .v{font-size:24px; font-weight:650; font-variant-numeric:tabular-nums;}
.stat-row .l{font-size:13px; color:var(--ink-2);}

.tier-chip{display:inline-flex; align-items:center; gap:7px; font-size:12.5px; font-weight:600; padding:3px 10px 3px 8px; border-radius:999px; background:var(--inset); color:var(--ink); white-space:nowrap;}
.tier-chip i{width:10px; height:10px; border-radius:50%; display:inline-block;}

/* ---------- Sections ---------- */
main{padding-bottom:40px;}
.lead{margin-top:40px;}
.lead h2{font-size:28px; line-height:1.15;}
.lead p{color:var(--ink-2); margin:8px 0 0; font-size:15px;}
.kpis{display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin-top:18px;}
@media (max-width:900px){ .kpis{grid-template-columns:repeat(2, 1fr);} }
@media (max-width:480px){ .kpis{grid-template-columns:1fr;} }
.kpi{background:var(--card); border:1px solid var(--line); border-radius:var(--radius); padding:18px 18px 16px; box-shadow:var(--shadow);}
.kpi .v{font-size:34px; font-weight:650; line-height:1.05; letter-spacing:-.02em;}
.kpi .v small{font-size:18px; font-weight:600; color:var(--ink-2); letter-spacing:0;}
.kpi .l{font-size:14px; color:var(--ink); margin-top:8px; font-weight:500;}
.kpi .s{font-size:12.5px; color:var(--ink-3); margin-top:4px;}
.scope{font-size:13px; color:var(--ink-3); margin:12px 2px 0;}

section.block{margin-top:44px;}
.s-head{margin-bottom:16px; max-width:78ch;}
.s-head h2{font-size:28px; line-height:1.15;}
.s-head p{color:var(--ink-2); margin:8px 0 0; font-size:15px;}
.card{background:var(--card); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); padding:18px;}

/* ---------- Map ---------- */
.map-layout{display:grid; grid-template-columns:minmax(0, 1.08fr) minmax(0, 1fr); gap:18px; align-items:start;}
@media (max-width:900px){ .map-layout{grid-template-columns:1fr;} }
.controls{display:flex; flex-wrap:wrap; gap:10px 14px; align-items:center; justify-content:space-between; margin-bottom:12px;}
.seg{display:inline-flex; background:var(--inset); border-radius:10px; padding:3px;}
.seg button{border:0; background:transparent; color:var(--ink-2); font-size:13px; font-weight:600; padding:6px 12px; border-radius:8px; cursor:pointer;}
.seg button[aria-pressed="true"]{background:var(--card); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,.12);}
.chips{display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px;}
.chip{
  display:inline-flex; align-items:center; gap:7px; border:1px solid var(--line-strong); background:var(--card);
  color:var(--ink); border-radius:999px; padding:4px 11px 4px 9px; font-size:12.5px; font-weight:500; cursor:pointer;
}
.chip i{width:10px; height:10px; border-radius:50%;}
.chip .c-n{color:var(--ink-3); font-variant-numeric:tabular-nums;}
.chip[aria-pressed="false"]{opacity:.55; border-style:dashed;}
.chip[aria-pressed="false"] i{background:transparent !important; box-shadow:inset 0 0 0 1.5px var(--ink-3);}
.map-frame{position:relative; border-radius:10px; overflow:hidden; background:var(--map-bg); border:1px solid var(--line);}
#map{display:block; width:100%; height:auto; touch-action:manipulation;}
#map .border{stroke:var(--map-border); stroke-width:1; stroke-dasharray:4 4; fill:none;}
#map .state{fill:var(--ink-3); font-size:10px; letter-spacing:.14em; font-family:var(--sans); font-weight:600;}
#map .dot{stroke:var(--map-bg); stroke-width:.8;}
#map .dot.off{opacity:.1;}
#map .hosp{fill:var(--ink); stroke:var(--map-bg); stroke-width:1.5;}
#map .hosp-label{fill:var(--ink); font-size:11px; font-weight:600; font-family:var(--sans); paint-order:stroke; stroke:var(--map-bg); stroke-width:3px; stroke-linejoin:round;}
#map .sel-ring{fill:none; stroke:var(--ink); stroke-width:2;}
#map .sel-label{fill:var(--ink); font-size:12.5px; font-weight:700; font-family:var(--sans); paint-order:stroke; stroke:var(--map-bg); stroke-width:4px; stroke-linejoin:round;}
#map .clinic-mark{fill:var(--accent); stroke:var(--map-bg); stroke-width:2;}
#map .hover-ring{fill:none; stroke:var(--ink); stroke-width:1.5;}
.map-note{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:12.5px; color:var(--ink-3); margin-top:10px;}
.map-note span{display:inline-flex; align-items:center; gap:6px;}
.map-note .diamond{width:9px; height:9px; background:var(--ink); transform:rotate(45deg); display:inline-block;}
#selNote{margin-top:10px; font-size:13px; color:var(--ink-2); display:flex; align-items:center; gap:10px; flex-wrap:wrap;}
#selNote[hidden]{display:none;}
.tooltip{
  position:fixed; z-index:60; pointer-events:none; background:#15191c; color:#f3f0e8; border-radius:10px;
  padding:10px 12px; font-size:12.5px; line-height:1.45; max-width:260px; box-shadow:0 10px 28px rgba(0,0,0,.3);
  opacity:0; transition:opacity .08s;
}
.tooltip.show{opacity:1;}
.tooltip b{display:block; font-size:13.5px; margin-bottom:2px;}
.tooltip .tt-sub{color:#b9c7c9;}
.tooltip .tt-row{display:flex; justify-content:space-between; gap:14px; margin-top:3px;}
.tooltip .tt-row span:last-child{font-weight:600; font-variant-numeric:tabular-nums; text-align:right;}
.tooltip .tt-hint{color:#8fb3b8; margin-top:6px; font-size:11.5px;}

/* ---------- Tables ---------- */
table{width:100%; border-collapse:collapse; font-size:14px;}
caption{text-align:left; font-family:var(--serif); font-weight:600; font-size:18px; padding:0 0 10px;}
th{text-align:left; font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600; padding:0 8px 8px; border-bottom:1px solid var(--line-strong);}
td{padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:middle;}
tbody tr:last-child td{border-bottom:0;}
th.r, td.r{text-align:right; font-variant-numeric:tabular-nums;}
td .sub{font-size:12px; color:var(--ink-3);}
tr.pick{cursor:pointer;}
tr.pick:hover td{background:var(--card-2);}
.rank{color:var(--ink-3); font-variant-numeric:tabular-nums; width:28px;}
.linkish{border:0; background:none; padding:0; color:var(--ink); font-weight:600; cursor:pointer; text-align:left;}
.linkish:hover{color:var(--accent); text-decoration:underline;}

/* ---------- Region chart ---------- */
.legend{display:flex; flex-wrap:wrap; gap:6px 18px; font-size:13px; color:var(--ink-2); margin-bottom:14px;}
.legend span{display:inline-flex; align-items:center; gap:7px;}
.legend i{width:12px; height:12px; border-radius:3px; display:inline-block;}
.rrow{display:grid; grid-template-columns:170px minmax(0, 1fr) 100px 120px; gap:14px; align-items:center; padding:9px 0; border-top:1px solid var(--line);}
.rrow.head{border-top:0; padding-top:0; white-space:nowrap; font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600;}
.rrow .rn{font-weight:600; font-size:14.5px;}
.rrow .rn .sub{display:block; font-weight:400; font-size:12px; color:var(--ink-3);}
.rrow .rv{text-align:right; font-variant-numeric:tabular-nums; font-size:14.5px;}
.rrow.head .rv, .crow.head .rv{font-size:11.5px;}
.stack{display:flex; gap:2px; height:26px;}
.stack .seg-bar{display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; font-variant-numeric:tabular-nums; min-width:3px; overflow:hidden;}
.stack .seg-bar:first-child{border-radius:4px 0 0 4px;}
.stack .seg-bar:last-child{border-radius:0 4px 4px 0;}
@media (max-width:700px){
  .rrow{grid-template-columns:110px minmax(0, 1fr) 64px;}
  .rrow.head, .crow.head{white-space:normal;}
  .rrow .hide-sm{display:none;}
}

/* ---------- Clinic chart ---------- */
.crow{display:grid; grid-template-columns:200px minmax(0, 1fr) 70px 110px; gap:14px; align-items:center; padding:8px 0; border-top:1px solid var(--line);}
.crow.head{border-top:0; padding-top:0; white-space:nowrap; font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600;}
.crow .sub{font-size:12px; color:var(--ink-3);}
.cbar{display:flex; align-items:center; gap:8px;}
.cbar .fill{height:14px; background:var(--series); border-radius:0 4px 4px 0; min-width:2px;}
.cbar .val{font-size:13.5px; font-weight:600; font-variant-numeric:tabular-nums;}
.crow .rv{text-align:right; font-variant-numeric:tabular-nums; font-size:14px;}
@media (max-width:700px){
  .crow{grid-template-columns:120px minmax(0, 1fr) 54px;}
  .crow.head{white-space:normal;}
  .crow .hide-sm{display:none;}
}

/* ---------- Report form ---------- */
.report-grid{display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start;}
@media (max-width:860px){ .report-grid{grid-template-columns:1fr;} }
form .field{margin-bottom:12px;}
form label{display:block; font-size:13px; font-weight:600; margin-bottom:5px;}
form input, form select{
  width:100%; font:inherit; font-size:15px; padding:10px 12px; border-radius:9px;
  border:1px solid var(--line-strong); background:var(--card); color:var(--ink);
}
.form-status{font-size:13.5px; color:var(--ink-2); min-height:1.4em; margin:8px 0 0;}
.report{border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin-bottom:8px; background:var(--card-2);}
.report-top{display:flex; flex-wrap:wrap; gap:8px; align-items:center;}
.report-top b{font-size:14px;}
.report-time{margin-left:auto; color:var(--ink-3); font-size:12px;}
.report-note{font-size:13px; color:var(--ink-2); margin-top:4px;}
.report-actions{display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:8px;}
.report-actions code{font-size:12px; background:var(--inset); padding:2px 7px; border-radius:6px; color:var(--ink-2);}
.mini{border:1px solid var(--line-strong); background:var(--card); color:var(--ink-2); border-radius:7px; padding:3px 9px; font-size:12px; cursor:pointer;}
.mini:hover{color:var(--ink);}
.empty{color:var(--ink-3); font-size:14px;}

/* ---------- About + footer ---------- */
details.about{background:var(--card); border:1px solid var(--line); border-radius:var(--radius); padding:0 20px;}
details.about summary{cursor:pointer; list-style:none; padding:16px 0; font-family:var(--serif); font-weight:600; font-size:19px; display:flex; justify-content:space-between; align-items:center;}
details.about summary::-webkit-details-marker{display:none;}
details.about summary::after{content:"+"; font-family:var(--sans); font-size:22px; color:var(--ink-3);}
details.about[open] summary::after{content:"\2212";}
.about-grid{display:grid; grid-template-columns:repeat(3, 1fr); gap:24px; padding:0 0 20px;}
@media (max-width:860px){ .about-grid{grid-template-columns:1fr;} }
.about-grid h3{font-family:var(--sans); font-size:12.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); margin-bottom:8px;}
.about-grid ul{margin:0; padding-left:18px; font-size:14px; color:var(--ink-2);}
.about-grid li{margin:5px 0;}
footer{border-top:1px solid var(--line); margin-top:40px; padding:22px 0 36px; color:var(--ink-3); font-size:13px;}
footer b{color:var(--ink-2); font-weight:600;}
</style>
</head>
<body>

<!-- ============ Masthead, introduction and search ============ -->
<header class="masthead">
  <div class="wrap">
    <div class="topline">
      <span class="eyebrow">CDU IT Code Fair 2026 &middot; Data Innovation Challenge</span>
      <span class="offline">Works with no internet connection</span>
    </div>
    <h1>The Long Way to Care</h1>
    <div class="questions">
      <p class="dek">Can you call for help from a remote Northern Territory community?</p>
      <p class="dek">And how far away is the nearest care?</p>
    </div>
    <p class="intro"><b>Mobile coverage records</b>, <b>road-network drive times</b> and <b>clinic contact details</b> for
      <b class="num" id="introCount">782</b> remote communities, brought together in one place. Search any community to see whether
      a call for help is likely to connect, how long the drive is to a clinic and a hospital, and who to phone. Search a clinic to get
      its number and hours directly.</p>

    <div class="search" role="search">
      <label for="q">Find a community or clinic</label>
      <div class="search-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="q" type="text" autocomplete="off" spellcheck="false" placeholder="Start typing a name, e.g. Kintore or Maningrida"
               role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="suggest">
        <button id="clearQ" type="button" aria-label="Clear search">&times;</button>
        <ul id="suggest" class="suggest" role="listbox" hidden></ul>
      </div>
      <div class="try" id="tryRow"><span>Try:</span></div>
    </div>
  </div>
</header>

<main class="wrap">

  <div id="result" aria-live="polite"></div>

  <!-- ============ Headline numbers ============ -->
  <div class="lead">
    <h2>The picture across the Territory</h2>
    <p>The numbers, map and charts below show where the gaps are widest, using the project's Gap Index.</p>
  </div>
  <div class="kpis" id="kpis"></div>
  <p class="scope" id="scope"></p>

  <!-- ============ Map ============ -->
  <section class="block" id="mapSection">
    <div class="s-head">
      <h2>Where the gaps are</h2>
      <p>Every community sits at its real location. Colour shows its risk tier from the Gap Index, or switch to raw phone coverage.
         Hover a point for details, click it for the full picture, or use the chips to show only some groups.</p>
    </div>
    <div class="map-layout">
      <div class="card">
        <div class="controls">
          <div class="seg" role="group" aria-label="Colour the map by">
            <button type="button" data-mode="tier" aria-pressed="true">Risk tier</button>
            <button type="button" data-mode="coverage" aria-pressed="false">Phone coverage</button>
          </div>
          <span class="scope" style="margin:0;" id="modeHint">Dot size also grows with risk tier</span>
        </div>
        <div class="chips" id="chips" role="group" aria-label="Show or hide groups on the map"></div>
        <div class="map-frame">
          <svg id="map" role="img" aria-label="Map of remote communities in the Northern Territory, coloured by risk"></svg>
        </div>
        <div class="map-note">
          <span><i class="diamond"></i>Public hospital with an emergency department</span>
          <span>Dashed lines: NT borders with WA, SA and Queensland</span>
        </div>
        <div id="selNote" hidden></div>
      </div>
      <div class="card">
        <table>
          <caption>Top 20 highest-risk communities</caption>
          <thead><tr><th></th><th>Community</th><th>Tier</th><th class="r">Gap Index</th></tr></thead>
          <tbody id="priority"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ============ Region chart ============ -->
  <section class="block" id="regionSection">
    <div class="s-head">
      <h2>Risk, region by region</h2>
      <p>How each region's communities split across the four risk tiers. Tiers are quartiles of the Gap Index across the whole NT,
         so a region with more dark segments carries more than its share of the highest-risk places.</p>
    </div>
    <div class="card">
      <div class="legend" id="regionLegend"></div>
      <div id="regions"></div>
    </div>
  </section>

  <!-- ============ Clinic chart ============ -->
  <section class="block" id="clinicSection">
    <div class="s-head">
      <h2>Clinics carrying the heaviest load</h2>
      <p>The listed remote clinics with the most nearby communities that have no recorded way to call for help. These clinics are the
         ones people may have to reach in person. Click a clinic to see its contact details and the communities around it.</p>
    </div>
    <div class="card">
      <div id="clinics"></div>
    </div>
  </section>

  <!-- ============ Report a coverage gap ============ -->
  <section class="block" id="reportSection">
    <div class="s-head">
      <h2>Report a coverage gap</h2>
      <p>Know somewhere the records get wrong? Log it here. Reports are anonymous and place-only, and they are saved on this device,
         so logging works with no signal at all. Each report gets a short code that can be texted or read out once you are back in coverage.</p>
    </div>
    <div class="report-grid">
      <div class="card">
        <form id="reportForm">
          <div class="field">
            <label for="rCommunity">Community</label>
            <input id="rCommunity" list="communityNames" autocomplete="off" required placeholder="Community name">
            <datalist id="communityNames"></datalist>
          </div>
          <div class="field">
            <label for="rType">What did you find?</label>
            <select id="rType">
              <option value="no_signal">No signal at all (dead zone)</option>
              <option value="weak_signal">Signal is there but weak or drops out</option>
              <option value="signal_restored">Signal has returned or improved</option>
            </select>
          </div>
          <div class="field">
            <label for="rNote">Note (optional)</label>
            <input id="rNote" maxlength="140" placeholder="e.g. no signal past the creek crossing">
          </div>
          <button class="btn primary" type="submit">Save report on this device</button>
          <p class="form-status" id="formStatus" role="status"></p>
        </form>
      </div>
      <div class="card">
        <h3 style="font-size:18px; margin-bottom:10px;">Reports saved on this device</h3>
        <div id="reports"></div>
      </div>
    </div>
  </section>

  <!-- ============ About ============ -->
  <section class="block">
    <details class="about">
      <summary>About this data: method, limits and ethics</summary>
      <div class="about-grid">
        <div>
          <h3>How the numbers were built</h3>
          <ul>
            <li>Coverage combines a 2021 community list, a 2022 list of covered sites and 2025 tower registers from all four carriers. The most direct and recent evidence wins.</li>
            <li>Drive times come from a routing pass over Geoscience Australia's national road network (48,391 road segments), supplied to this project as input data.</li>
            <li>The Gap Index is the equal-weighted average of four percentile-ranked risks: no confirmed coverage, clinic drive time, hospital drive time and no sealed road.</li>
            <li>A community with no mapped road is scored as maximum risk, not dropped. It is the exact case the index exists to surface.</li>
            <li>Risk tiers are quartiles of the Gap Index. Alternative weightings were tested and flag the same top 20 communities.</li>
          </ul>
        </div>
        <div>
          <h3>What this can't prove</h3>
          <ul>
            <li>"Never recorded" means no list found a signal there, not that there is none. The NT Government calls its lists a guide only.</li>
            <li>"Tower within 15 km" is a modelling assumption about a macro cell's reach on flat land, so it is kept as its own category.</li>
            <li>Drive times assume dry-season roads. Wet-season closures make trips longer or impossible.</li>
            <li>The fastest drive may be to a different health service than the listed remote clinic whose phone number is shown. The result card names both.</li>
            <li>This is a class prototype built on public data, not an emergency service. In an emergency, call 000.</li>
          </ul>
        </div>
        <div>
          <h3>Ethics and community</h3>
          <ul>
            <li>No personal or health records are used. Every score describes a place's access to services, not the people who live there.</li>
            <li>Outstations are homelands on Country. The gap measured is in the infrastructure that reaches them, not in the communities.</li>
            <li>Missing data is shown as missing, never quietly filled in.</li>
            <li>Coverage reports collect a place, a status and an optional note. No names or contact details, and nothing leaves this device unless you send the code yourself.</li>
          </ul>
        </div>
      </div>
    </details>
  </section>

  <footer>
    <b>The Long Way to Care</b> &middot; CDU IT Code Fair 2026, Data Innovation Challenge &middot; Team: Chepngenoh Chepkwony and Cynthia Ebele Ikegbunam.
    Sources: NT Government, ACCC, Geoscience Australia, Healthdirect, Bureau of Meteorology.
  </footer>
</main>

<div class="tooltip" id="tip" role="tooltip"></div>

<script>
__DATA_JS__

// ---------- Shared helpers ----------
const TIERS = ["Low","Moderate","High","Critical"];
const TIER_VAR = {Low:"var(--t1)", Moderate:"var(--t2)", High:"var(--t3)", Critical:"var(--t4)"};
const TIER_INK = {Low:"var(--t1-ink)", Moderate:"var(--t2-ink)", High:"var(--t3-ink)", Critical:"var(--t4-ink)"};
const TIER_R = {Low:2.5, Moderate:3.0, High:3.5, Critical:4.1};
const CANNOT = new Set(["Never recorded","Listed: no coverage"]);
const COV_GROUP = c => CANNOT.has(c) ? "none" : (c === "Macro cell nearby" ? "strong" : "part");
const COV_GROUPS = [
  {k:"none", label:"No recorded coverage", color:"var(--c-none)"},
  {k:"part", label:"Partial or likely coverage", color:"var(--c-part)"},
  {k:"strong", label:"Strong coverage", color:"var(--c-strong)"},
];
const COV_LABEL = {
  "Never recorded":"Never recorded on any coverage list",
  "Listed: no coverage":"Listed as having no coverage",
  "Listed: has coverage (2021)":"Listed as covered (2021 list only)",
  "Tower within 15km (2025)":"A 2025 tower within 15 km (likely, not confirmed)",
  "Small cell or near a cell":"Small cell, or near a covered site",
  "Macro cell nearby":"Macro cell or tower within 3 km",
};
const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const fmtMin = m => {
  if (m == null) return null;
  if (m < 60) return m + " min";
  const h = Math.floor(m / 60), r = m % 60;
  return h + " h" + (r ? " " + r + " min" : "");
};
const telHref = p => "tel:" + String(p).replace(/[^0-9+]/g, "");
// Lower-cases, drops accents and apostrophes, so "galiwinku" also finds "Galiwin'ku"
const norm = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/['\u2019`]/g, "").toLowerCase();

// ---------- Headline numbers ----------
document.getElementById("introCount").textContent = KPI.total.toLocaleString();
const kpiTiles = [
  {v: KPI.cannotCall.toLocaleString(), l:"communities with no recorded way to call for help", s: KPI.pctCannotCall + "% of all " + KPI.total + " communities"},
  {v: fmtMin(KPI.medianHospitalMin).replace(" min", "<small> min</small>").replace(" h", "<small> h</small>"), l:"median drive to a hospital emergency department", s: KPI.over4h + " communities are more than 4 hours away"},
  {v: KPI.noRoad, l:"communities with no mapped road to any hospital", s:"Mostly islands, reached by air or sea"},
  {v: KPI.no247 + "<small> of " + KPI.clinics + "</small>", l:"remote clinics with no listed 24/7 emergency service", s:"After hours, the nearest help may be much further"},
];
document.getElementById("kpis").innerHTML = kpiTiles.map(k =>
  `<div class="kpi"><div class="v num">${k.v}</div><div class="l">${k.l}</div><div class="s">${k.s}</div></div>`).join("");
document.getElementById("scope").textContent =
  `${KPI.total} remote communities, outstations and town camps · ${KPI.clinics} listed remote clinics · ${KPI.hospitals} public hospital emergency departments`;

// ---------- Search (community or clinic) ----------
const ENTRIES = [
  ...COMMUNITIES.map((c, i) => ({kind:"community", i, name:c.n, sub:c.t + " · " + c.r, key:norm(c.n)})),
  ...CLINICS.map((c, i) => ({kind:"clinic", i, name:c.n, sub:c.r, key:norm(c.n)})),
];
const q = document.getElementById("q");
const list = document.getElementById("suggest");
const clearQ = document.getElementById("clearQ");
let matches = [], active = -1;

function findMatches(text){
  const t = norm(text.trim());
  if (!t) return [];
  const scored = [];
  for (const e of ENTRIES){
    const pos = e.key.indexOf(t);
    if (pos < 0) continue;
    const wordStart = pos === 0 || /[\s(\-']/.test(e.key[pos - 1]);
    scored.push({e, score: pos === 0 ? 0 : (wordStart ? 1 : 2)});
  }
  scored.sort((a, b) => a.score - b.score || a.e.name.localeCompare(b.e.name) || (a.e.kind === "community" ? -1 : 1));
  return scored.slice(0, 8).map(s => s.e);
}
function highlight(name, text){
  const t = norm(text.trim());
  if (!t) return esc(name);
  // Maps each character of the normalised name back to the original name
  const chars = [...name], map = [];
  let flat = "";
  chars.forEach((ch, idx) => { for (const c of norm(ch)){ flat += c; map.push(idx); } });
  const i = flat.indexOf(t);
  if (i < 0) return esc(name);
  const a = map[i], z = map[i + t.length - 1] + 1;
  return esc(chars.slice(0, a).join("")) + "<mark>" + esc(chars.slice(a, z).join("")) + "</mark>" + esc(chars.slice(z).join(""));
}
function renderSuggest(){
  const text = q.value;
  clearQ.style.display = text ? "block" : "none";
  matches = findMatches(text);
  active = matches.length ? 0 : -1;
  if (!text.trim()){ closeSuggest(); return; }
  list.innerHTML = matches.length
    ? matches.map((m, idx) => `<li role="option" id="opt${idx}" data-idx="${idx}" aria-selected="${idx === active}">
        <span class="s-name"><span class="s-type ${m.kind}">${m.kind}</span>${highlight(m.name, text)}</span>
        <span class="s-sub">${esc(m.sub)}</span></li>`).join("")
    : `<li class="s-empty" aria-disabled="true">No community or clinic matches &ldquo;${esc(text)}&rdquo;</li>`;
  list.hidden = false;
  q.setAttribute("aria-expanded", "true");
  q.setAttribute("aria-activedescendant", active >= 0 ? "opt" + active : "");
}
function closeSuggest(){
  list.hidden = true;
  q.setAttribute("aria-expanded", "false");
  q.removeAttribute("aria-activedescendant");
}
function moveActive(step){
  if (!matches.length) return;
  active = (active + step + matches.length) % matches.length;
  list.querySelectorAll("li[role=option]").forEach((li, idx) => li.setAttribute("aria-selected", idx === active));
  q.setAttribute("aria-activedescendant", "opt" + active);
  const el = document.getElementById("opt" + active);
  if (el) el.scrollIntoView({block:"nearest"});
}
q.addEventListener("input", renderSuggest);
q.addEventListener("focus", () => { if (q.value.trim()) renderSuggest(); });
q.addEventListener("keydown", e => {
  if (e.key === "ArrowDown"){ e.preventDefault(); if (list.hidden) renderSuggest(); else moveActive(1); }
  else if (e.key === "ArrowUp"){ e.preventDefault(); moveActive(-1); }
  else if (e.key === "Enter"){ e.preventDefault(); if (matches[active]) choose(matches[active]); }
  else if (e.key === "Escape"){ closeSuggest(); }
});
list.addEventListener("mousedown", e => {
  const li = e.target.closest("li[data-idx]");
  if (!li) return;
  e.preventDefault();
  choose(matches[Number(li.dataset.idx)]);
});
document.addEventListener("click", e => { if (!e.target.closest(".search")) closeSuggest(); });
clearQ.addEventListener("click", () => { q.value = ""; renderSuggest(); clearSelection(); q.focus(); });

function choose(entry, scroll = true){
  q.value = entry.name;
  clearQ.style.display = "block";
  closeSuggest();
  if (entry.kind === "clinic") showClinic(entry.i); else showCommunity(entry.i);
  if (scroll) document.getElementById("result").firstElementChild?.scrollIntoView({block:"start"});
}

// "Try" examples - picked from the data so they always exist
const tryPicks = [
  ENTRIES.find(e => e.kind === "community" && e.name === "Kintore"),
  ENTRIES.find(e => e.kind === "community" && e.name === "Galiwinku"),
  ENTRIES.find(e => e.kind === "clinic" && e.name === "Maningrida"),
].filter(Boolean);
const tryRow = document.getElementById("tryRow");
tryPicks.forEach(p => {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = p.name + (p.kind === "clinic" ? " clinic" : "");
  b.addEventListener("click", () => choose(p));
  tryRow.appendChild(b);
});

// ---------- Result cards ----------
const result = document.getElementById("result");

function tierChip(tier){
  return `<span class="tier-chip"><i style="background:${TIER_VAR[tier]}"></i>${tier} risk</span>`;
}
function callAdvice(c){
  if (!CANNOT.has(c.cc)){
    return `<div class="callout ok">
      <h3>A call for help should usually connect here</h3>
      <p>Dial <b>000</b>. If you have any signal from any carrier, the call will use it.</p>
      <p class="cov">Coverage record: ${esc(COV_LABEL[c.cc])}</p></div>`;
  }
  return `<div class="callout warn">
    <h3>No mobile coverage has been recorded here</h3>
    <p>That means no list has found a signal, not that a signal is proven absent. If a call for help cannot connect:</p>
    <ul>
      <li>Try <b>000</b> anyway. If any carrier's signal reaches you, the call will use it.</li>
      <li>Use a landline, satellite phone, or a phone with emergency SOS by satellite if one is available.</li>
      <li>Carry a personal locator beacon (PLB) when travelling on remote roads.</li>
      <li>The Emergency+ app shows your GPS coordinates without mobile data, ready to read out once you reach coverage.</li>
    </ul>
    <p class="cov">Coverage record: ${esc(COV_LABEL[c.cc])}</p></div>`;
}
function tripRows(c){
  const rows = [];
  if (c.cm === 0) rows.push(`<div class="trip"><div class="t-time">On site</div><div class="t-what">A health service is in the community: <b>${esc(c.rc)}</b></div></div>`);
  else if (c.cm != null) rows.push(`<div class="trip"><div class="t-time">${fmtMin(c.cm)}</div><div class="t-what">drive to the nearest clinic or health service, <b>${esc(c.rc)}</b>${c.ck != null ? " (" + c.ck + " km)" : ""}</div></div>`);
  else rows.push(`<div class="trip"><div class="t-time">No road</div><div class="t-what">No mapped road route to a clinic was found</div></div>`);
  if (c.hm != null){
    const unsealed = c.uk ? `, ${c.uk} km of it unsealed` : ", all sealed";
    rows.push(`<div class="trip"><div class="t-time">${fmtMin(c.hm)}</div><div class="t-what">drive to the nearest hospital emergency department, <b>${esc(c.hn)}</b> (${c.hk} km${unsealed})</div></div>`);
  } else {
    rows.push(`<div class="trip"><div class="t-time">No road</div><div class="t-what">No mapped road to any hospital emergency department. Emergencies rely on air or sea evacuation.</div></div>`);
  }
  return rows.join("");
}
function phoneBlock(phone, valid, hours, e24){
  const num = phone
    ? `<a class="phone" href="${telHref(phone)}">${esc(phone)}</a>`
    : `<span class="meta">Phone number not on file</span>`;
  const flag = phone && !valid ? `<div class="flag">This number looks incomplete in the source list. Check it on nt.gov.au before relying on it.</div>` : "";
  const badge = e24 ? `<span class="badge yes">24/7 emergency service listed</span>` : `<span class="badge">No 24/7 emergency service listed</span>`;
  return `${num}${flag}<div class="meta">${esc(hours || "Opening hours not on file")}</div><div style="margin-top:8px;">${badge}</div>`;
}
function gauge(gi){
  return `<div class="gauge" aria-label="Gap Index ${gi.toFixed(3)} out of 1">
    <div class="gauge-track"><div class="gauge-mark" style="left:${(gi * 100).toFixed(1)}%"></div></div>
    <div class="gauge-scale"><span>0 · best connected</span><span>1 · hardest to reach help</span></div></div>`;
}

function showCommunity(i){
  const c = COMMUNITIES[i];
  result.innerHTML = `<article class="result">
    <div class="r-head">
      <div><h2>${esc(c.n)}</h2><div class="r-sub">${esc(c.t)} · ${esc(c.r)} region</div></div>
      <div class="r-actions">${tierChip(c.tier)}<button class="btn" type="button" data-act="map">Show on map</button></div>
    </div>
    <div class="r-grid">
      <div>
        ${callAdvice(c)}
        <div class="panel" style="margin-top:12px;">
          <div class="p-label">Gap Index · ${c.gi.toFixed(3)}</div>
          ${gauge(c.gi)}
        </div>
      </div>
      <div>
        <div class="panel"><div class="p-label">Getting to care</div>${tripRows(c)}
          <div class="meta" style="margin-top:6px;">${c.sr ? "A sealed road route exists from here." : "No sealed road connects this community."}</div></div>
        <div class="panel"><div class="p-label">Nearest listed remote clinic · ${esc(c.cl)}</div>${phoneBlock(c.cp, c.cv, c.ch, c.ce)}</div>
      </div>
    </div></article>`;
  result.querySelector("[data-act=map]").addEventListener("click", () => document.getElementById("mapSection").scrollIntoView({block:"start"}));
  setSelection({kind:"community", i});
}

function showClinic(i){
  const k = CLINICS[i];
  result.innerHTML = `<article class="result">
    <div class="r-head">
      <div><h2>${esc(k.n)}</h2><div class="r-sub">Remote clinic · ${esc(k.r)} region${k.op ? " · " + esc(k.op) : ""}</div></div>
      <div class="r-actions"><button class="btn" type="button" data-act="map">Show its communities on the map</button></div>
    </div>
    <div class="r-grid">
      <div class="panel"><div class="p-label">Contact this clinic</div>${phoneBlock(k.phone, k.pv, k.hours, k.e24)}</div>
      <div class="panel"><div class="p-label">Communities around this clinic</div>
        <div class="stat-row">
          <div><div class="v">${k.served}</div><div class="l">communities have this as their nearest listed clinic</div></div>
          <div><div class="v">${k.cantCall}</div><div class="l">of them have no recorded way to call for help</div></div>
        </div></div>
    </div></article>`;
  result.querySelector("[data-act=map]").addEventListener("click", () => document.getElementById("mapSection").scrollIntoView({block:"start"}));
  setSelection({kind:"clinic", i});
}

// ---------- Map ----------
/*
  Equirectangular projection, cosine-corrected so the NT keeps its true
  shape. The SVG's height is worked out from the data's own proportions,
  so the points fill the whole frame instead of sitting to one side.
*/
const svg = document.getElementById("map");
const NS = "http://www.w3.org/2000/svg";
const B = {lonMin:129, lonMax:138, latMin:-26, latMax:-10.85};
const PAD = {l:26, r:30, t:16, b:26};
const MAP_W = 620;
const kx = Math.cos((B.latMin + B.latMax) / 2 * Math.PI / 180);
const SCALE = (MAP_W - PAD.l - PAD.r) / ((B.lonMax - B.lonMin) * kx);
const MAP_H = Math.round(PAD.t + PAD.b + (B.latMax - B.latMin) * SCALE);
svg.setAttribute("viewBox", `0 0 ${MAP_W} ${MAP_H}`);
const px = lon => PAD.l + (lon - B.lonMin) * kx * SCALE;
const py = lat => PAD.t + (B.latMax - lat) * SCALE;
COMMUNITIES.forEach(c => { c.x = px(c.lo); c.y = py(c.la); c.g = COV_GROUP(c.cc); });

let mode = "tier";
const shown = {tier: new Set(TIERS), coverage: new Set(COV_GROUPS.map(g => g.k))};
let selection = null;

const el = (tag, attrs, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
};
const gBase = el("g", {}, svg), gDots = el("g", {}, svg), gHosp = el("g", {}, svg), gSel = el("g", {}, svg), gHover = el("g", {}, svg);

// Borders with WA (129°E), SA (26°S) and Queensland (138°E), plus labels
el("path", {class:"border", d:`M${px(129)},${py(-14.9)} L${px(129)},${py(-26)} L${px(138)},${py(-26)} L${px(138)},${py(-16.0)}`}, gBase);
const stateLabel = (txt, x, y, rot) => {
  const t = el("text", {class:"state", x, y, "text-anchor":"middle", transform: rot ? `rotate(${rot} ${x} ${y})` : ""}, gBase);
  t.textContent = txt;
};
stateLabel("WESTERN AUSTRALIA", px(129) - 10, py(-21), -90);
stateLabel("QUEENSLAND", px(138) + 12, py(-21), 90);
stateLabel("SOUTH AUSTRALIA", px(133.5), py(-26) + 17, 0);

// Hospitals
HOSPITALS.forEach(h => {
  const x = px(h.lo), y = py(h.la);
  const d = el("rect", {class:"hosp", x:x - 4.2, y:y - 4.2, width:8.4, height:8.4, transform:`rotate(45 ${x} ${y})`}, gHosp);
  const title = el("title", {}, d); title.textContent = h.n;
  if (h.label){
    // Nhulunbuy sits near the right edge, so its label goes underneath
    const below = h.label === "Nhulunbuy";
    const t = el("text", {class:"hosp-label", x: below ? x : x + 9, y: below ? y + 18 : y + 4, "text-anchor": below ? "middle" : "start"}, gHosp);
    t.textContent = h.label;
  }
});

function colourOf(c){
  return mode === "tier" ? TIER_VAR[c.tier] : COV_GROUPS.find(g => g.k === c.g).color;
}
function isShown(c){
  if (mode === "tier" ? !shown.tier.has(c.tier) : !shown.coverage.has(c.g)) return false;
  if (selection && selection.kind === "clinic") return c.cl === CLINICS[selection.i].n;
  return true;
}
function drawOrder(){
  // Higher-risk points are drawn last so they sit on top
  const rank = mode === "tier"
    ? c => TIERS.indexOf(c.tier)
    : c => ({strong:0, part:1, none:2}[c.g]);
  return COMMUNITIES.map((c, i) => i).sort((a, b) => rank(COMMUNITIES[a]) - rank(COMMUNITIES[b]));
}
function renderDots(){
  gDots.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (const i of drawOrder()){
    const c = COMMUNITIES[i];
    const dot = document.createElementNS(NS, "circle");
    dot.setAttribute("class", "dot" + (isShown(c) ? "" : " off"));
    dot.setAttribute("cx", c.x.toFixed(1));
    dot.setAttribute("cy", c.y.toFixed(1));
    dot.setAttribute("r", mode === "tier" ? TIER_R[c.tier] : 3.2);
    dot.setAttribute("fill", colourOf(c));
    frag.appendChild(dot);
  }
  gDots.appendChild(frag);
}
function renderChips(){
  const box = document.getElementById("chips");
  const items = mode === "tier"
    ? TIERS.map(t => ({k:t, label:t, color:TIER_VAR[t], n:KPI.tierCounts[t]}))
    : COV_GROUPS.map(g => ({k:g.k, label:g.label, color:g.color, n:COMMUNITIES.filter(c => c.g === g.k).length}));
  box.innerHTML = items.map(it => `<button type="button" class="chip" data-k="${it.k}" aria-pressed="${shown[mode].has(it.k)}">
      <i style="background:${it.color}"></i>${it.label} <span class="c-n">${it.n}</span></button>`).join("");
  box.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => {
    const set = shown[mode], k = b.dataset.k;
    if (set.has(k)) set.delete(k); else set.add(k);
    b.setAttribute("aria-pressed", set.has(k));
    renderDots();
  }));
  document.getElementById("modeHint").textContent = mode === "tier" ? "Dot size also grows with risk tier" : "Grey is the midpoint: some evidence, not confirmed";
}
document.querySelectorAll(".seg button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".seg button").forEach(x => x.setAttribute("aria-pressed", x === b));
  mode = b.dataset.mode;
  svg.setAttribute("aria-label", "Map of remote communities in the Northern Territory, coloured by " + (mode === "tier" ? "risk tier" : "phone coverage"));
  renderChips(); renderDots();
}));

function renderSelection(){
  gSel.innerHTML = "";
  const note = document.getElementById("selNote");
  if (!selection){ note.hidden = true; return; }
  if (selection.kind === "community"){
    const c = COMMUNITIES[selection.i];
    el("circle", {class:"sel-ring", cx:c.x, cy:c.y, r:9}, gSel);
    const right = c.x < MAP_W - 150;
    const t = el("text", {class:"sel-label", x: right ? c.x + 13 : c.x - 13, y:c.y + 4, "text-anchor": right ? "start" : "end"}, gSel);
    t.textContent = c.n;
    note.innerHTML = `Showing <b>${esc(c.n)}</b> on the map. <button class="mini" type="button" id="clearSel">Clear</button>`;
  } else {
    const k = CLINICS[selection.i];
    if (k.la != null){
      const x = px(k.lo), y = py(k.la);
      el("circle", {class:"clinic-mark", cx:x, cy:y, r:6}, gSel);
      const right = x < MAP_W - 150;
      const t = el("text", {class:"sel-label", x: right ? x + 11 : x - 11, y:y + 4, "text-anchor": right ? "start" : "end"}, gSel);
      t.textContent = k.n + " clinic";
    }
    note.innerHTML = `Showing only the ${k.served} communities whose nearest listed clinic is <b>${esc(k.n)}</b>. <button class="mini" type="button" id="clearSel">Show all</button>`;
  }
  note.hidden = false;
  document.getElementById("clearSel").addEventListener("click", clearSelection);
}
function setSelection(s){ selection = s; renderDots(); renderSelection(); }
function clearSelection(){ selection = null; result.innerHTML = ""; renderDots(); renderSelection(); }

// Hover - finds the nearest visible point, so small dots are easy to hit
const tip = document.getElementById("tip");
function svgPoint(e){
  const p = svg.createSVGPoint();
  p.x = e.clientX; p.y = e.clientY;
  return p.matrixTransform(svg.getScreenCTM().inverse());
}
function nearest(e){
  const p = svgPoint(e);
  let best = -1, bestD = 12 * 12;
  COMMUNITIES.forEach((c, i) => {
    if (!isShown(c)) return;
    const d = (c.x - p.x) ** 2 + (c.y - p.y) ** 2;
    if (d < bestD){ bestD = d; best = i; }
  });
  return best;
}
function placeTip(e){
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + w > window.innerWidth - 8) x = e.clientX - w - pad;
  if (y + h > window.innerHeight - 8) y = e.clientY - h - pad;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
svg.addEventListener("pointermove", e => {
  const i = nearest(e);
  gHover.innerHTML = "";
  if (i < 0){ tip.classList.remove("show"); svg.style.cursor = "default"; return; }
  const c = COMMUNITIES[i];
  el("circle", {class:"hover-ring", cx:c.x, cy:c.y, r:(mode === "tier" ? TIER_R[c.tier] : 3.2) + 3}, gHover);
  tip.innerHTML = `<b>${esc(c.n)}</b><div class="tt-sub">${esc(c.t)} · ${esc(c.r)}</div>
    <div class="tt-row"><span>Risk tier</span><span>${c.tier} (${c.gi.toFixed(3)})</span></div>
    <div class="tt-row"><span>Coverage</span><span>${CANNOT.has(c.cc) ? "None recorded" : (c.g === "strong" ? "Strong" : "Partial / likely")}</span></div>
    <div class="tt-row"><span>To a clinic</span><span>${c.cm === 0 ? "On site" : (fmtMin(c.cm) || "No road")}</span></div>
    <div class="tt-row"><span>To a hospital</span><span>${fmtMin(c.hm) || "No road"}</span></div>
    <div class="tt-hint">Click for full details</div>`;
  tip.classList.add("show");
  placeTip(e);
  svg.style.cursor = "pointer";
});
svg.addEventListener("pointerleave", () => { tip.classList.remove("show"); gHover.innerHTML = ""; });
svg.addEventListener("click", e => {
  const i = nearest(e);
  if (i < 0) return;
  tip.classList.remove("show");
  choose({kind:"community", i, name:COMMUNITIES[i].n});
});

renderChips(); renderDots();

// ---------- Top 20 table ----------
const commIndex = Object.fromEntries(COMMUNITIES.map((c, i) => [c.n, i]));
document.getElementById("priority").innerHTML = PRIORITY.map((p, n) => `
  <tr class="pick" data-name="${esc(p.n)}">
    <td class="rank">${n + 1}</td>
    <td><button class="linkish" type="button">${esc(p.n)}</button><div class="sub">${esc(p.r)}</div></td>
    <td>${tierChip(p.tier).replace(" risk", "")}</td>
    <td class="r">${p.gi.toFixed(3)}</td>
  </tr>`).join("");
document.querySelectorAll("#priority tr").forEach(tr => tr.addEventListener("click", () => {
  const i = commIndex[tr.dataset.name];
  if (i != null) choose({kind:"community", i, name:tr.dataset.name});
}));

// ---------- Region chart ----------
document.getElementById("regionLegend").innerHTML = TIERS.map(t =>
  `<span><i style="background:${TIER_VAR[t]}"></i>${t}</span>`).join("") + `<span style="color:var(--ink-3)">Lightest to darkest = lowest to highest risk</span>`;
document.getElementById("regions").innerHTML =
  `<div class="rrow head"><span>Region</span><span>Communities by risk tier</span><span class="rv">Can't call</span><span class="rv hide-sm">Avg Gap Index</span></div>`
  + REGIONS.map(r => {
    const segs = TIERS.map(t => {
      const n = r.tiers[t], pct = n / r.n * 100;
      if (!n) return "";
      const label = pct >= 7 ? n : "";
      return `<div class="seg-bar" style="width:${pct}%; background:${TIER_VAR[t]}; color:${TIER_INK[t]}" title="${esc(r.r)}: ${n} ${t} (${pct.toFixed(0)}%)">${label}</div>`;
    }).join("");
    return `<div class="rrow">
      <span class="rn">${esc(r.r)}<span class="sub">${r.n} communities</span></span>
      <div class="stack" role="img" aria-label="${esc(r.r)}: ${TIERS.map(t => r.tiers[t] + " " + t).join(", ")}">${segs}</div>
      <span class="rv">${r.cantCallPct}%</span>
      <span class="rv hide-sm">${r.meanGap.toFixed(3)}</span></div>`;
  }).join("");

// ---------- Clinic chart ----------
const topClinics = CLINICS.map((k, i) => ({...k, i}))
  .sort((a, b) => b.cantCall - a.cantCall || b.risk - a.risk).slice(0, 12);
const maxCant = Math.max(...topClinics.map(k => k.cantCall));
document.getElementById("clinics").innerHTML =
  `<div class="crow head"><span>Clinic</span><span>Nearby communities with no recorded coverage</span><span class="rv">Served</span><span class="hide-sm">Emergency</span></div>`
  + topClinics.map(k => `<div class="crow">
      <span><button class="linkish" type="button" data-i="${k.i}">${esc(k.n)}</button><div class="sub">${esc(k.r)}</div></span>
      <div class="cbar"><div class="fill" style="width:${(k.cantCall / maxCant * 88).toFixed(1)}%"></div><span class="val">${k.cantCall}</span></div>
      <span class="rv">${k.served}</span>
      <span class="hide-sm">${k.e24 ? '<span class="badge yes">24/7</span>' : '<span class="badge">No 24/7</span>'}</span></div>`).join("");
document.querySelectorAll("#clinics [data-i]").forEach(b => b.addEventListener("click", () => {
  const i = Number(b.dataset.i);
  choose({kind:"clinic", i, name:CLINICS[i].n});
}));

// ---------- Report a coverage gap (saved on this device only) ----------
const RTYPES = {
  no_signal:{label:"No signal", code:"NS"},
  weak_signal:{label:"Weak signal", code:"WS"},
  signal_restored:{label:"Signal restored", code:"SR"},
};
const RKEY = "longWayToCareReports_v1";
document.getElementById("communityNames").innerHTML = COMMUNITIES.map(c => `<option value="${esc(c.n)}">`).join("");
const loadReports = () => { try { return JSON.parse(localStorage.getItem(RKEY) || "[]"); } catch(e){ return []; } };
const saveReports = list => { try { localStorage.setItem(RKEY, JSON.stringify(list)); return true; } catch(e){ return false; } };
function reportCode(r){
  const d = new Date(r.ts), p = n => String(n).padStart(2, "0");
  return `LWC1|${r.community}|${RTYPES[r.type].code}|${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}${p(d.getUTCHours())}${p(d.getUTCMinutes())}`;
}
function copy(text, btn){
  const done = () => { const o = btn.textContent; btn.textContent = "Copied"; setTimeout(() => btn.textContent = o, 1300); };
  if (navigator.clipboard && window.isSecureContext){ navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done)); }
  else fallbackCopy(text, done);
}
function fallbackCopy(text, done){
  const ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); } catch(e){}
  document.body.removeChild(ta); done();
}
function renderReports(){
  const list = loadReports(), box = document.getElementById("reports");
  if (!list.length){ box.innerHTML = '<p class="empty">No reports saved on this device yet.</p>'; return; }
  box.innerHTML = list.map((r, i) => ({r, i})).reverse().map(({r, i}) => `<div class="report">
      <div class="report-top"><span class="badge">${RTYPES[r.type].label}</span><b>${esc(r.community)}</b>
        <span class="report-time">${new Date(r.ts).toLocaleString()}</span></div>
      ${r.note ? `<div class="report-note">${esc(r.note)}</div>` : ""}
      <div class="report-actions"><code>${esc(reportCode(r))}</code>
        <button class="mini" type="button" data-copy="${i}">Copy code</button>
        <button class="mini" type="button" data-del="${i}">Remove</button></div></div>`).join("");
  box.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", () => copy(reportCode(list[Number(b.dataset.copy)]), b)));
  box.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", () => {
    const cur = loadReports(); cur.splice(Number(b.dataset.del), 1); saveReports(cur); renderReports();
  }));
}
document.getElementById("reportForm").addEventListener("submit", e => {
  e.preventDefault();
  const community = document.getElementById("rCommunity").value.trim();
  const status = document.getElementById("formStatus");
  if (!community){ status.textContent = "Enter a community name first."; return; }
  const report = {community, type:document.getElementById("rType").value,
                  note:document.getElementById("rNote").value.trim().slice(0, 140), ts:new Date().toISOString()};
  const list = loadReports(); list.push(report);
  status.textContent = saveReports(list)
    ? "Saved on this device. Copy the code below to send it when you have signal."
    : "This browser blocked saving, so the report will only last until the page is closed.";
  e.target.reset();
  renderReports();
});
renderReports();
</script>
</body>
</html>
"""

PAGE = (PAGE.replace("__TITLE__", TITLE)
            .replace("__FONT_CSS__", FONT_CSS)
            .replace("__DATA_JS__", DATA_JS))

out_path = OUTPUTS / "dashboard_offline.html"
out_path.write_text(PAGE, encoding="utf-8")
print(f"\nSaved {out_path.name} ({out_path.stat().st_size / 1024:.0f} KB) - "
      "double click it or drag it into any browser, no internet needed")