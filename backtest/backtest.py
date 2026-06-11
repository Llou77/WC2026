#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest & calibration on real historical data (martj42/international_results).

Protocol (no leakage):
  1. Build Elo over the full history (1872->) with tournament-weighted K.
  2. TRAIN: grid-search model params on major tournaments 2010-2021
     (WC 2010/14/18, Euro 2012/16/21, Copa 2011/15/16/19/21).
  3. HOLDOUT: evaluate the chosen params on WC 2022 + Euro 2024 + Copa 2024.
  4. Penalty shootouts: estimate P(higher-Elo side wins) from shootouts.csv
     to calibrate the extra-time/penalties share used in knockout logic.

Metrics: multiclass Brier score (lower=better; uniform=0.667) and log-loss
(uniform=1.0986). In-tournament att/def updating is replicated (no xG in
historical data, so the goals-only path is what gets tested).
"""
import csv, itertools, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from model import ratings

HERE = os.path.dirname(os.path.abspath(__file__))

K_MAP = [("FIFA World Cup qualification", 40), ("FIFA World Cup", 60),
         ("UEFA Euro qualification", 40), ("UEFA Euro", 50),
         ("Copa América", 50), ("African Cup of Nations", 50),
         ("AFC Asian Cup", 50), ("CONCACAF", 40), ("Nations League", 40),
         ("Confederations", 40), ("Friendly", 20)]
def k_for(t):
    for key, k in K_MAP:
        if key in t: return k
    return 30

TRAIN = {("FIFA World Cup", 2010), ("FIFA World Cup", 2014), ("FIFA World Cup", 2018),
         ("UEFA Euro", 2012), ("UEFA Euro", 2016), ("UEFA Euro", 2021),
         ("Copa América", 2011), ("Copa América", 2015), ("Copa América", 2016),
         ("Copa América", 2019), ("Copa América", 2021)}
HOLDOUT = {("FIFA World Cup", 2022), ("UEFA Euro", 2024), ("Copa América", 2024)}

def tkey(row):
    t, y = row["tournament"], int(row["date"][:4])
    if t == "FIFA World Cup": return ("FIFA World Cup", y)
    if t == "UEFA Euro": return ("UEFA Euro", y)
    if t == "Copa América": return ("Copa América", y)
    return None

def load_rows():
    with open(os.path.join(HERE, "results.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r["home_score"] not in ("", "NA") and r["date"] < "2026-06-11"]
    return rows

def run_pass(rows, params, collect_shootouts=None):
    """One chronological pass. Returns (per-set score lists, final elo dict)."""
    for k, v in params.items():
        setattr(ratings, k, v)
    elo, scores = {}, {"train": [], "holdout": []}
    tourn_state = {}            # (tournament,year) -> {team: {att,deff}}
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        gh, ga = int(r["home_score"]), int(r["away_score"])
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        key = tkey(r)
        # in-tournament att/def state (reset per tournament)
        if key in TRAIN or key in HOLDOUT:
            st = tourn_state.setdefault(key, {})
            sh = st.setdefault(h, {"att": 1.0, "deff": 1.0})
            sa = st.setdefault(a, {"att": 1.0, "deff": 1.0})
            th = {"code": "H", "elo": eh, "att": sh["att"], "deff": sh["deff"]}
            ta = {"code": "A", "elo": ea, "att": sa["att"], "deff": sa["deff"]}
            vc = "H" if r["neutral"] == "FALSE" else ""
            p = ratings.predict(th, ta, vc)
            o = (1, 0, 0) if gh > ga else ((0, 1, 0) if gh == ga else (0, 0, 1))
            brier = (p["p1"]-o[0])**2 + (p["px"]-o[1])**2 + (p["p2"]-o[2])**2
            ll = -math.log(max(1e-9, (p["p1"], p["px"], p["p2"])[o.index(1)]))
            scores["train" if key in TRAIN else "holdout"].append((brier, ll))
            ratings.apply_result(th, ta, {"gh": gh, "ga": ga}, vc)
            sh["att"], sh["deff"] = th["att"], th["deff"]
            sa["att"], sa["deff"] = ta["att"], ta["deff"]
        if collect_shootouts is not None and gh == ga:
            collect_shootouts[(r["date"], h, a)] = (eh, ea)
        # global Elo history update (tournament-weighted K, home adv if not neutral)
        bonus = 80.0 if r["neutral"] == "FALSE" else 0.0
        ev = ratings.expectancy(eh, ea, bonus)
        w = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        d = abs(gh - ga)
        g = 1.0 if d <= 1 else (1.5 if d == 2 else (11 + d) / 8.0)
        delta = k_for(r["tournament"]) * g * (w - ev)
        elo[h], elo[a] = eh + delta, ea - delta
    return scores, elo

def avg(xs, i): return sum(x[i] for x in xs) / len(xs)

def main():
    rows = load_rows()
    print(f"{len(rows)} mérkőzés betöltve.")
    base = dict(TOTAL_GOALS_BASE=2.55, DC_DRAW_BOOST=1.08)

    # --- grid search on TRAIN ---
    grid = dict(GD_SCALE=[100.0, 115.0, 130.0, 145.0],
                DC_DRAW_BOOST=[1.00, 1.10, 1.20, 1.30],
                TOTAL_GOALS_BASE=[2.45, 2.55, 2.70])
    results = []
    for gd, dc, tg in itertools.product(*grid.values()):
        sc, _ = run_pass(rows, dict(GD_SCALE=gd, DC_DRAW_BOOST=dc, TOTAL_GOALS_BASE=tg))
        results.append((avg(sc["train"], 0), avg(sc["train"], 1), gd, dc, tg))
    results.sort()
    print("\nTop-5 paraméterkombináció (train Brier szerint):")
    for b, ll, gd, dc, tg in results[:5]:
        print(f"  gd_scale={gd:.0f} draw_boost={dc:.2f} total={tg:.2f} -> Brier={b:.4f} LL={ll:.4f}")
    best = results[0]
    bp = dict(GD_SCALE=best[2], DC_DRAW_BOOST=best[3], TOTAL_GOALS_BASE=best[4])

    # --- holdout: default vs tuned ---
    sc_def, _ = run_pass(rows, dict(GD_SCALE=120.0, **base))
    sc_tun, elo = run_pass(rows, bp)
    print(f"\nHOLDOUT (VB2022 + Eb2024 + Copa2024, {len(sc_tun['holdout'])} meccs):")
    print(f"  uniform 1/3 :  Brier=0.6667  LL=1.0986")
    print(f"  alap params :  Brier={avg(sc_def['holdout'],0):.4f}  LL={avg(sc_def['holdout'],1):.4f}")
    print(f"  hangolt     :  Brier={avg(sc_tun['holdout'],0):.4f}  LL={avg(sc_tun['holdout'],1):.4f}")
    print(f"  hangolt params: {bp}")

    # --- shootout calibration ---
    draws = {}
    run_pass(rows, bp, collect_shootouts=draws)
    higher_wins = total = 0
    with open(os.path.join(HERE, "shootouts.csv"), encoding="utf-8") as f:
        for s in csv.DictReader(f):
            k = (s["date"], s["home_team"], s["away_team"])
            if k not in draws or s["winner"] in ("", "NA"):
                continue
            eh, ea = draws[k]
            if abs(eh - ea) < 25:       # gyakorlatilag azonos erő — nem informatív
                continue
            total += 1
            higher = s["home_team"] if eh > ea else s["away_team"]
            higher_wins += (s["winner"] == higher)
    share = higher_wins / total if total else float("nan")
    print(f"\nSzétlövések: {total} értékelhető párbaj, a magasabb Elo nyert: {share:.1%}")
    # ET_SHRINK úgy, hogy átlagos KO-erőkülönbségnél (~150 Elo, E~0.70) a
    # döntetlen-ág megosztása a mért empirikus arányt adja vissza:
    # 0.5 + (0.70-0.5)*s = share  ->  s = (share-0.5)/0.20
    print(f"Javasolt ET-zsugorítás: {(share-0.5)/0.20:.2f} (jelenlegi: 0.75)")

if __name__ == "__main__":
    main()
