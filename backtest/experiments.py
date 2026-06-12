#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autonomous experiment runner (E1-E7).

Discipline: every selection happens on TRAIN tournaments; the HOLDOUT is
evaluated exactly once, at the very end, with the final configuration.
Metrics: Brier (1X2, primary), GoalNLL (-log P(exact score), score-model
objective), RPS (ranked probability score, reported).
Blend is DISABLED during base-model tuning, retrained at the end on the
winning config, then the full stack is measured once on holdout.
"""
import csv, itertools, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from model import ratings
from backtest import k_for, TRAIN, HOLDOUT, tkey, load_rows
from train_blend import softmax, train_softmax

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = dict(GD_SCALE=160.0, DC_DRAW_BOOST=1.15, TOTAL_GOALS_BASE=2.80,
                GD_POW=1.0, TOTAL_GD_COEF=0.45, MOV_MODE="elo",
                ATTDEF_LR=0.35, K_BASE=50, HOME_ELO_BONUS=80.0)

def full_pass(rows, params, want_features=False):
    """Chronological pass. Returns per-set records:
    (pois_probs, grid_probs_of_actual, rps, feats, y). Blend disabled."""
    ratings._BLEND = False
    for k, v in DEFAULTS.items():
        setattr(ratings, k, params.get(k, v))
    elo, recs = {}, {"train": [], "holdout": []}
    tourn_state, form = {}, {}
    softmax_train = []
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        gh, ga = int(r["home_score"]), int(r["away_score"])
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        bonus = ratings.HOME_ELO_BONUS if r["neutral"] == "FALSE" else 0.0
        dr = (eh + bonus) - ea
        y = 0 if gh > ga else (1 if gh == ga else 2)
        fdiff = (sum(form.get(h, [])[-8:]) / max(1, len(form.get(h, [])[-8:]))
                 - sum(form.get(a, [])[-8:]) / max(1, len(form.get(a, [])[-8:])))
        if want_features and r["date"] >= "1995-01-01" and r["tournament"] != "Friendly":
            softmax_train.append((r["date"], [1.0, dr/400.0, abs(dr)/400.0, fdiff/3.0], y))
        key = tkey(r)
        if key in TRAIN or key in HOLDOUT:
            st = tourn_state.setdefault(key, {})
            sh = st.setdefault(h, {"att": 1.0, "deff": 1.0})
            sa = st.setdefault(a, {"att": 1.0, "deff": 1.0})
            th = {"code": "H", "elo": eh, **sh}
            ta = {"code": "A", "elo": ea, **sa}
            vc = "H" if r["neutral"] == "FALSE" else ""
            grid, lh, la = ratings.calibrated_grid(th, ta, vc)
            n = ratings.MAX_GOALS + 1
            pw = sum(grid[i][j] for i in range(n) for j in range(n) if i > j)
            pd = sum(grid[i][i] for i in range(n))
            pl = 1 - pw - pd
            p_act = grid[min(gh, 8)][min(ga, 8)]
            cw, cd = pw, pw + pd
            ow, od = (1.0 if y == 0 else 0.0), (1.0 if y <= 1 else 0.0)
            rps = 0.5 * ((cw - ow) ** 2 + (cd - od) ** 2)
            recs["train" if key in TRAIN else "holdout"].append(
                ((pw, pd, pl), p_act, rps, [1.0, dr/400.0, abs(dr)/400.0, fdiff/3.0], y))
            ratings.apply_result(th, ta, {"gh": gh, "ga": ga}, vc)
            sh["att"], sh["deff"] = th["att"], th["deff"]
            sa["att"], sa["deff"] = ta["att"], ta["deff"]
        ev = ratings.expectancy(eh, ea, bonus)
        w = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        d = abs(gh - ga)
        g = 1.0 if d <= 1 else (1.5 if d == 2 else (11 + d) / 8.0)
        delta = k_for(r["tournament"]) * g * (w - ev)
        elo[h], elo[a] = eh + delta, ea - delta
        pts = 3 if gh > ga else (1 if gh == ga else 0)
        form.setdefault(h, []).append(pts)
        form.setdefault(a, []).append(3 - pts if gh != ga else 1)
    out = (recs, softmax_train) if want_features else recs
    return out

def metrics(recs):
    n = len(recs)
    brier = sum(sum((p[c] - (1.0 if c == y else 0.0)) ** 2 for c in range(3))
                for (p, _, _, _, y) in recs) / n
    gnll = sum(-math.log(max(1e-9, pa)) for (_, pa, _, _, _) in recs) / n
    rps = sum(r for (_, _, r, _, _) in recs) / n
    return brier, gnll, rps

def fmt(t): return f"Brier={t[0]:.4f} GoalNLL={t[1]:.4f} RPS={t[2]:.4f}"

def main():
    rows = load_rows()
    print(f"{len(rows)} meccs; TRAIN-szelekció, holdout érintetlen a végéig.\n")
    log = []

    # --- E2: ATTDEF_LR x K_BASE ---
    print("E2: tornaforma-tanulási ráta és torna-K rács (train)")
    best = (None, (9, 9, 9))
    for lr, k in itertools.product([0.0, 0.2, 0.35, 0.5, 0.7], [30, 50, 70]):
        m = metrics(full_pass(rows, dict(ATTDEF_LR=lr, K_BASE=k))["train"])
        if m[0] < best[1][0]:
            best = (dict(ATTDEF_LR=lr, K_BASE=k), m)
        print(f"  lr={lr:.2f} K={k}: {fmt(m)}")
    e2 = best[0]; print(f"  -> győztes: {e2} {fmt(best[1])}\n"); log.append(("E2", e2, best[1]))

    # --- E3: HOME_ELO_BONUS ---
    print("E3: hazai bónusz rács (train)")
    best = (None, (9, 9, 9))
    for hb in [50.0, 65.0, 80.0, 100.0, 120.0]:
        m = metrics(full_pass(rows, dict(**e2, HOME_ELO_BONUS=hb))["train"])
        if m[0] < best[1][0]:
            best = (hb, m)
        print(f"  HB={hb:.0f}: {fmt(m)}")
    e3 = best[0]; print(f"  -> győztes: HB={e3} {fmt(best[1])}\n")
    log.append(("E3", {"HOME_ELO_BONUS": e3}, best[1]))
    base = dict(**e2, HOME_ELO_BONUS=e3)

    # --- E4: gólmodell-alak GoalNLL célon ---
    print("E4: gólvárakozás-alak (cél: GoalNLL, train)")
    best = (None, (9, 9, 9))
    for gs, tp, tg, dc, tc in itertools.product(
            [140.0, 160.0, 180.0], [0.85, 1.0, 1.15], [2.6, 2.8, 3.0],
            [1.05, 1.15, 1.25], [0.30, 0.45, 0.60]):
        m = metrics(full_pass(rows, dict(**base, GD_SCALE=gs, GD_POW=tp,
                                         TOTAL_GOALS_BASE=tg, DC_DRAW_BOOST=dc,
                                         TOTAL_GD_COEF=tc))["train"])
        if m[1] < best[1][1]:
            best = (dict(GD_SCALE=gs, GD_POW=tp, TOTAL_GOALS_BASE=tg,
                         DC_DRAW_BOOST=dc, TOTAL_GD_COEF=tc), m)
    e4 = best[0]
    print(f"  -> győztes (243 kombinációból): {e4} {fmt(best[1])}\n")
    log.append(("E4", e4, best[1]))
    base = dict(**base, **e4)

    # --- E5: MOV-forma ---
    print("E5: gólkülönbség-szorzó formája az Elo-frissítésben (train)")
    best = (None, (9, 9, 9))
    for mv in ["elo", "linear", "sqrt"]:
        m = metrics(full_pass(rows, dict(**base, MOV_MODE=mv))["train"])
        if m[0] < best[1][0]:
            best = (mv, m)
        print(f"  MOV={mv}: {fmt(m)}")
    e5 = best[0]; print(f"  -> győztes: {e5}\n"); log.append(("E5", {"MOV_MODE": e5}, best[1]))
    base = dict(**base, MOV_MODE=e5)

    # --- E6: softmax featurek + idősúly, blend-keverés a trainen ---
    print("E6: blend-változatok (train-szelekció)")
    recs, sm = full_pass(rows, base, want_features=True)
    tr = recs["train"]
    variants = {}
    for name, nfeat, timew in [("alap-3f", 3, False), ("forma-4f", 4, False),
                               ("forma-4f-idosuly", 4, True)]:
        X = [f[:nfeat] for (_, f, _) in [(d, x, y) for d, x, y in sm]]
        Y = [y for (_, _, y) in sm]
        if timew:
            Wt = [math.exp((int(d[:4]) - 2026) / 12.0) for (d, _, _) in sm]
        else:
            Wt = None
        W = train_softmax_w([x[:nfeat] for (d, x, y) in sm], Y, nfeat, Wt)
        best_w, best_b = 0, 9
        for w in [i / 10 for i in range(11)]:
            b = 0.0
            for (pois, _, _, f, y) in tr:
                sp = softmax([sum(W[c][j] * f[j] for j in range(nfeat)) for c in range(3)])
                p = [(1 - w) * pois[c] + w * sp[c] for c in range(3)]
                b += sum((p[c] - (1.0 if c == y else 0.0)) ** 2 for c in range(3))
            b /= len(tr)
            if b < best_b:
                best_b, best_w = b, w
        variants[name] = (W, best_w, best_b, nfeat)
        print(f"  {name}: w={best_w} train-Brier={best_b:.4f}")
    win = min(variants, key=lambda k: variants[k][2])
    W, bw, bb, nf = variants[win]
    print(f"  -> győztes: {win}\n")
    log.append(("E6", {"variant": win, "w": bw}, (bb, 0, 0)))

    # --- E7: EGYETLEN holdout-mérés a teljes végső stackkel ---
    print("E7: VÉGSŐ holdout-mérés (egyszer)")
    ho = recs["holdout"]
    def blended(rows_, w):
        b = g = rp = 0.0
        for (pois, pact, rps_, f, y) in rows_:
            sp = softmax([sum(W[c][j] * f[j] for j in range(nf)) for c in range(3)])
            p = [(1 - w) * pois[c] + w * sp[c] for c in range(3)]
            b += sum((p[c] - (1.0 if c == y else 0.0)) ** 2 for c in range(3))
        return b / len(rows_)
    h_brier = blended(ho, bw)
    h_base = metrics(ho)
    print(f"  Holdout, csak gólmodell (új paraméterek): {fmt(h_base)}")
    print(f"  Holdout, teljes stack (új params + új blend): Brier={h_brier:.4f}")
    print(f"  Referencia (jelenleg élesben): Brier=0.5977")

    json.dump({"base_params": base, "blend_variant": win, "blend_w": bw,
               "blend_W": W, "n_features": nf,
               "holdout_brier_full": round(h_brier, 4),
               "holdout_goalnll": round(h_base[1], 4),
               "holdout_rps": round(h_base[2], 4),
               "log": [(n, p, [round(x, 4) for x in m]) for n, p, m in log]},
              open(os.path.join(HERE, "experiments_result.json"), "w"), indent=1)
    print("\nexperiments_result.json elmentve.")

def train_softmax_w(X, y, nfeat, sample_w=None, epochs=200, lr=0.6):
    W = [[0.0] * nfeat for _ in range(3)]
    n = len(X)
    sw = sample_w or [1.0] * n
    tot = sum(sw)
    for ep in range(epochs):
        grad = [[0.0] * nfeat for _ in range(3)]
        for xi, yi, wi in zip(X, y, sw):
            p = softmax([sum(W[c][j] * xi[j] for j in range(nfeat)) for c in range(3)])
            for c in range(3):
                err = (p[c] - (1.0 if c == yi else 0.0)) * wi
                for j in range(nfeat):
                    grad[c][j] += err * xi[j]
        for c in range(3):
            for j in range(nfeat):
                W[c][j] -= lr * grad[c][j] / tot
    return W

if __name__ == "__main__":
    main()
