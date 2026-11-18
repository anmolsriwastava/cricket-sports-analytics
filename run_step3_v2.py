# ══════════════════════════════════════════════════════════════════════════
# Full pipeline: Cells 1–7 (with v2 changes) + Step 3 (v2)
# ══════════════════════════════════════════════════════════════════════════

# ── Cell 1: Setup ─────────────────────────────────────────────────────────
import gc
import numpy as np
import pandas as pd
from pathlib import Path
import psutil

DATA = Path(r"C:\Users\Anmol Sriwastava\Desktop\RR_Analytics\data")
OUT  = Path(r"C:\Users\Anmol Sriwastava\Desktop\RR_Analytics\Analysis_v2")   # ← v2 change
OUT.mkdir(exist_ok=True)

p = psutil.Process()
print("RAM used MB:", round(p.memory_info().rss/1e6))
print("RAM avail MB:", round(psutil.virtual_memory().available/1e6))
print("DATA ok:", DATA.exists())
print(sorted(x.name for x in DATA.glob("*.csv")))

# ── Cell 2: Load ball-by-ball ─────────────────────────────────────────────
keep = ["match_id","innings","overid","innings_ball_num",
        "batting_team_id","bowling_team_id",
        "striker_id","striker_name","bowler_id","bowler_name",
        "runs","is_wicket","dismissal_type","dismissed_player_id",
        "extras_type","extras_2_runs",
        "pace_or_spin"]                                                      # ← v2 change: added pace_or_spin

bbb = pd.read_csv(DATA/"ball_by_ball.csv", usecols=keep)
bbb = bbb[bbb["innings"].isin([1,2])].copy()
print(bbb.shape)
print(round(psutil.Process().memory_info().rss/1e6), "MB")
gc.collect()

# ── Cell 3: Merge matches/competitions ────────────────────────────────────
matches = pd.read_csv(DATA/"matches.csv",
    usecols=["match_id","comp_id","match_date","stage","knock_out",
             "revised_target","first_inn_revised_overs",
             "second_inn_revised_overs","venue_id","win_team_id"])
comps = pd.read_csv(DATA/"competitions.csv",
    usecols=["comp_id","match_format","season"])

df = bbb.merge(matches, on="match_id", how="left")
df = df.merge(comps, on="comp_id", how="left")
del bbb; gc.collect()

df = df.sort_values(["match_id","innings","innings_ball_num"]).reset_index(drop=True)
print(df.shape, round(psutil.Process().memory_info().rss/1e6), "MB")

# ── Cell 4: Derived columns ──────────────────────────────────────────────
df["extra_run"]   = df["extras_type"].isin(["wide","Overstep"]).astype(int)
df["approx_runs"] = (df["runs"].fillna(0) + df["extra_run"] + df["extras_2_runs"].fillna(0)
                     + df["extras_type"].isin(["byes","legbyes"]).astype(int))   # ← v2 change: add byes/legbyes
df["legal_ball"]  = ~df["extras_type"].isin(["wide","Overstep"])

df["bowler_runs"] = df["runs"].fillna(0) + df["extra_run"] + df["extras_2_runs"].fillna(0)
df.loc[df["extras_type"].isin(["byes","legbyes"]), "bowler_runs"] = 0

df["striker_out"] = df["is_wicket"] & (df["dismissed_player_id"] == df["striker_id"])
non_bowl = ["RunOut","Retire Out","Obstructing the field","Obstracting"]
df["bowler_wkt"]  = df["is_wicket"] & (~df["dismissal_type"].isin(non_bowl))

# runs_bat needed by SAVE list in Step 3
df["runs_bat"] = df["runs"].fillna(0).astype(int)

print(round(psutil.Process().memory_info().rss/1e6), "MB")

# ── Cell 5: State columns ────────────────────────────────────────────────
df["inn_total_balls"] = 120

r1 = df["first_inn_revised_overs"]
r2 = df["second_inn_revised_overs"]
ok1 = (df["innings"]==1) & r1.between(1,20)
ok2 = (df["innings"]==2) & r2.between(1,20)
df.loc[ok1,"inn_total_balls"] = (r1[ok1]*6).round().astype(int)
df.loc[ok2,"inn_total_balls"] = (r2[ok2]*6).round().astype(int)

g = df.groupby(["match_id","innings"], sort=False)
df["score_before"] = g["approx_runs"].cumsum() - df["approx_runs"]
df["wkts_before"]  = g["is_wicket"].cumsum()   - df["is_wicket"].astype(int)
df["legal_before"] = g["legal_ball"].cumsum()  - df["legal_ball"].astype(int)
del g; gc.collect()

df["balls_left_before"] = (df["inn_total_balls"] - df["legal_before"]).clip(lower=0)

# ── Cell 6: Target / chase columns ───────────────────────────────────────
first_total = (df[df["innings"]==1]
               .groupby("match_id")["approx_runs"].sum()
               .reset_index()
               .rename(columns={"approx_runs":"first_total"}))
df = df.merge(first_total, on="match_id", how="left")

df["target"] = df["first_total"] + 1
df.loc[df["revised_target"].notna(), "target"] = df["revised_target"]
df.loc[df["innings"]==1, "target"] = np.nan

df["runs_needed_before"] = df["target"] - df["score_before"]
df["req_rate_before"] = np.where(
    (df["innings"]==2) & (df["balls_left_before"]>0),
    df["runs_needed_before"]*6/df["balls_left_before"], np.nan)
gc.collect()

# ── Cell 7: After-ball state + flags ─────────────────────────────────────
df["score_after"] = df["score_before"] + df["approx_runs"]
df["wkts_after"]  = df["wkts_before"]  + df["is_wicket"].astype(int)
df["legal_after"] = df["legal_before"] + df["legal_ball"].astype(int)
df["balls_left_after"] = (df["inn_total_balls"] - df["legal_after"]).clip(lower=0)

df["runs_needed_after"] = df["target"] - df["score_after"]
df["req_rate_after"] = np.where(
    (df["innings"]==2) & (df["balls_left_after"]>0),
    df["runs_needed_after"]*6/df["balls_left_after"], np.nan)

df["is_t20i"] = (df["match_format"]=="T20I").astype(int)
df["bat_team_won"] = (df["win_team_id"]==df["batting_team_id"]).astype(int)
df.loc[df["win_team_id"].isna(), "bat_team_won"] = np.nan

print("done", round(psutil.Process().memory_info().rss/1e6), "MB")
gc.collect()

# ── Save state.pkl ────────────────────────────────────────────────────────
df.to_pickle(OUT/"state.pkl")
print("saved", round((OUT/"state.pkl").stat().st_size/1e6), "MB")

# ══════════════════════════════════════════════════════════════════════════
# Step 3 (v2) — Win-probability model, out-of-fold by match, EXPECTED leverage
# Replaces BOTH old cells 8 and 9.
# ══════════════════════════════════════════════════════════════════════════
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, log_loss

d0 = df[(df["balls_left_before"] > 0) & df["bat_team_won"].notna()].copy()
d0["phase"] = pd.cut(d0["overid"], [0, 6, 15, 20], labels=[0, 1, 2]).astype(int)   # PP / middle / death

# 1) What can happen on the next legal ball, by phase (empirical frequencies)
lg = d0[d0["legal_ball"]]
oc = np.where(lg["is_wicket"].astype(bool), "W", lg["runs_bat"].clip(upper=6).replace({5: 4}).astype(str))
P_OUT = lg.assign(o=oc).groupby("phase")["o"].value_counts(normalize=True).unstack().fillna(0)
OUTS = [("W", 0, 1)] + [(str(r), r, 0) for r in [0, 1, 2, 3, 4, 6]]      # (name, runs, wicket)

# 2) One model per innings (chosen on a time-based holdout: simple beats complex here)
CFG = {
    1: dict(feat=["score_before", "wkts_before", "balls_left_before", "overid", "is_t20i"],
            mk=lambda: HGB(max_depth=2, max_iter=120, learning_rate=0.05, random_state=42)),
    2: dict(feat=["runs_needed_before", "wkts_before", "balls_left_before", "is_t20i"],
            mk=lambda: HGB(max_iter=250, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=200,
                           l2_regularization=1.0, monotonic_cst=[-1, -1, 0, 0], random_state=0)),
}
def shift_state(X, i, r, w, bl_drop):
    N = X.copy()
    if i == 1: N[:, 0] += r          # score up
    else:      N[:, 0] -= r          # runs needed down
    N[:, 1] += w                     # wickets
    N[:, 2] = np.clip(N[:, 2] - bl_drop, 0, None)   # balls left
    return N
def terminal(wp, N, i):              # chase won / lost is certain
    if i == 2:
        wp = np.where(N[:, 0] <= 0, 1.0, wp)
        wp = np.where((N[:, 1] >= 10) | ((N[:, 2] <= 0) & (N[:, 0] > 0)), 0.0, wp)
    return wp

SAVE = ["match_id", "innings", "innings_ball_num", "striker_id", "striker_name", "bowler_id", "bowler_name",
        "runs_bat", "approx_runs", "legal_ball", "is_wicket", "striker_out", "bowler_wkt", "bowler_runs",
        "batting_team_id", "extras_type", "overid", "phase", "wkts_before", "score_before", "runs_needed_before",
        "balls_left_before", "pace_or_spin", "is_t20i", "wp_before", "wp_after", "leverage", "exp_dwp"]
for i in (1, 2):
    d = d0[d0["innings"] == i].copy()
    X = d[CFG[i]["feat"]].astype(float).values; y = d["bat_team_won"].astype(int).values
    wp_b, wp_a, lev, edw = (np.zeros(len(d)) for _ in range(4))
    for tr, te in GroupKFold(5).split(X, y, d["match_id"]):        # every match is test exactly once
        mdl = CFG[i]["mk"]().fit(X[tr], y[tr]); Xt = X[te]; T = d.iloc[te]
        p0 = mdl.predict_proba(Xt)[:, 1]
        Na = shift_state(Xt, i, T["approx_runs"].values, T["is_wicket"].astype(int).values, T["legal_ball"].astype(int).values)
        wp_a[te] = terminal(mdl.predict_proba(Na)[:, 1], Na, i)    # what actually happened
        L = np.zeros(len(te)); E = np.zeros(len(te))
        for name, r, w in OUTS:                                    # what COULD happen (pre-ball, outcome-free)
            Nh = shift_state(Xt, i, r, w, 1); p1 = terminal(mdl.predict_proba(Nh)[:, 1], Nh, i)
            pr = T["phase"].map(P_OUT[name]).values
            L += pr * np.abs(p1 - p0); E += pr * (p1 - p0)
        wp_b[te], lev[te], edw[te] = p0, L, E
    d["wp_before"], d["wp_after"], d["leverage"], d["exp_dwp"] = wp_b, wp_a, lev, edw
    print(f"Innings {i}: out-of-fold AUC {roc_auc_score(y, wp_b):.3f} | logloss {log_loss(y, wp_b):.3f} (naive 0.693)")
    cal = (pd.DataFrame({"pred": wp_b, "actual": y, "bin": pd.cut(wp_b, np.linspace(0, 1, 11), include_lowest=True)})
           .groupby("bin", observed=True).agg(pred=("pred", "mean"), actual=("actual", "mean"), n=("actual", "size")).round(3))
    print(cal.to_string()); print(d["leverage"].describe().round(4).to_string())
    d[SAVE].to_pickle(OUT / f"inn{i}_wp.pkl")
    del d; gc.collect()
print("✓ Step 3 (v2) complete")
