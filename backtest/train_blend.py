#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meta-learner experiment (adapted from the NFL project's layer-3 idea).

A tiny softmax classifier (a single-layer neural net, pure stdlib) is trained
on ~25k competitive historical matches to predict 1X2 directly from the Elo
gap. Its output is then BLENDED with the Poisson model's 1X2 probabilities;
the blend weight is chosen on the TRAIN tournaments and the verdict is made
on the untouched HOLDOUT. Ship only if the holdout improves.

Output (if it wins): data/blend.json with softmax weights + blend share.
"""
import csv, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from model import ratings
from backtest import K_MAP, k_for, TRAIN, HOLDOUT, tkey, load_rows

HERE = os.path.dirname(os.path.abspath(__file__))

def softmax(z):
    m = max(z); e = [math.exp(v - m) for v in z]; s = sum(e)
    return [v / s for v in e]

def feats(dr):
    return [1.0, dr / 400.0, abs(dr) / 400.0]

def collect():
    """Chronological Elo pass; collect (features, outcome) for competitive
    matches 1995+, and (poisson_probs, features, outcome) for train/holdout."""
    rows = load_rows()
    elo, train_X, train_y = {}, [], []
    ev_sets = {"train": [], "holdout": []}
    tourn_state = {}
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        gh, ga = int(r["home_score"]), int(r["away_score"])
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        bonus = 80.0 if r["neutral"] == "FALSE" else 0.0
        dr = (eh + bonus) - ea
        y = 0 if gh > ga else (1 if gh == ga else 2)
        if r["date"] >= "1995-01-01" and r["tournament"] != "Friendly":
            train_X.append(feats(dr)); train_y.append(y)
        key = tkey(r)
        if key in TRAIN or key in HOLDOUT:
            st = tourn_state.setdefault(key, {})
            sh = st.setdefault(h, {"att": 1.0, "deff": 1.0})
            sa = st.setdefault(a, {"att": 1.0, "deff": 1.0})
            th = {"code": "H", "elo": eh, **sh}
            ta = {"code": "A", "elo": ea, **sa}
            vc = "H" if r["neutral"] == "FALSE" else ""
            p = ratings.predict(th, ta, vc)
            ev_sets["train" if key in TRAIN else "holdout"].append(
                ((p["p1"], p["px"], p["p2"]), feats(dr), y))
            ratings.apply_result(th, ta, {"gh": gh, "ga": ga}, vc)
            sh["att"], sh["deff"] = th["att"], th["deff"]
            sa["att"], sa["deff"] = ta["att"], ta["deff"]
        ev = ratings.expectancy(eh, ea, bonus)
        w = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        d = abs(gh - ga)
        g = 1.0 if d <= 1 else (1.5 if d == 2 else (11 + d) / 8.0)
        delta = k_for(r["tournament"]) * g * (w - ev)
        elo[h], elo[a] = eh + delta, ea - delta
    return train_X, train_y, ev_sets

def train_softmax(X, y, epochs=250, lr=0.6):
    W = [[0.0, 0.0, 0.0] for _ in range(3)]
    n = len(X)
    for ep in range(epochs):
        grad = [[0.0] * 3 for _ in range(3)]
        for xi, yi in zip(X, y):
            p = softmax([sum(W[c][j] * xi[j] for j in range(3)) for c in range(3)])
            for c in range(3):
                err = p[c] - (1.0 if c == yi else 0.0)
                for j in range(3):
                    grad[c][j] += err * xi[j]
        for c in range(3):
            for j in range(3):
                W[c][j] -= lr * grad[c][j] / n
    return W

def brier(p, y):
    return sum((p[c] - (1.0 if c == y else 0.0)) ** 2 for c in range(3))

def main():
    print("Adatgyűjtés + Elo-felépítés...")
    X, y, ev = collect()
    print(f"Softmax-tanítóminta: {len(X)} tétmeccs (1995–)")
    W = train_softmax(X, y)
    print("Softmax betanítva. Keverési súly keresése a TRAIN tornákon...")
    def blended_brier(rows, w):
        tot = 0.0
        for pois, f, yy in rows:
            soft = softmax([sum(W[c][j] * f[j] for j in range(3)) for c in range(3)])
            p = [(1 - w) * pois[c] + w * soft[c] for c in range(3)]
            tot += brier(p, yy)
        return tot / len(rows)
    ws = [i / 10 for i in range(11)]
    tr = {w: blended_brier(ev["train"], w) for w in ws}
    best_w = min(tr, key=tr.get)
    print("  w -> train Brier:", {w: round(b, 4) for w, b in tr.items()})
    h0 = blended_brier(ev["holdout"], 0.0)
    hb = blended_brier(ev["holdout"], best_w)
    print(f"\nVálasztott keverés (train alapján): w={best_w}")
    print(f"HOLDOUT: csak Poisson Brier={h0:.4f} | keverék Brier={hb:.4f} "
          f"({'JAVÍT' if hb < h0 - 0.0005 else 'NEM JAVÍT érdemben'})")
    if hb < h0 - 0.0005 and best_w > 0:
        out = {"W": W, "w": best_w}
        with open(os.path.join(HERE, "..", "data", "blend.json"), "w") as f:
            json.dump(out, f, indent=1)
        print("data/blend.json elmentve — a predict() automatikusan használja.")
    else:
        print("Nem kerül élesítésre (a holdout nem igazolta).")

if __name__ == "__main__":
    main()
