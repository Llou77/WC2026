#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily update pipeline (manual trigger).

    python update.py            # recompute everything + regenerate index.html

Idempotent and fast: ratings are rebuilt from the seed + all observed results
in chronological order (incremental Elo/att-def, no refitting), then every
remaining match is re-predicted and the site is regenerated. Typical runtime
is well under one second.
"""
import copy, json, os, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import ratings, standings, analysis, simulate
from render.render_site import render

ROOT = os.path.dirname(os.path.abspath(__file__))

def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)

def main():
    sims = 10000
    for a_ in sys.argv[1:]:
        if a_.startswith("--sims="):
            sims = int(a_.split("=")[1])
    teams = {t["code"]: copy.deepcopy(t) for t in load("teams.json")}
    matches = load("matches.json")
    observed = load("observed.json")   # {"<match_id>": {gh, ga, xg_h?, xg_a?, winner_home?}}
    mby = {m["id"]: m for m in matches}

    # 1) incremental rating pass over observed results, chronological order
    form = {}
    applied = 0
    bracket_seen = {}
    order = sorted(observed.keys(), key=lambda k: (mby[int(k)]["date"], mby[int(k)]["time_et"]))
    pre_match_pred = {}
    for key in order:
        m = mby[int(key)]
        if m["stage"] == "group":
            h, a = m["home"], m["away"]
        else:
            # knockout participants: resolve from observed bracket so far
            res = standings.resolve_bracket(matches, {k: observed[k] for k in order
                                                      if order.index(k) < order.index(key)},
                                            teams)
            h, a, _ = res[m["id"]]
        bracket_seen[m["id"]] = (h, a)
        r = observed[key]
        pre_match_pred[m["id"]] = ratings.predict(
            teams[h], teams[a], m["venue_country"], knockout=(m["stage"] != "group"))
        ratings.apply_result(teams[h], teams[a], r, m["venue_country"])
        wdl_h = "W" if r["gh"] > r["ga"] else ("D" if r["gh"] == r["ga"] else "L")
        wdl_a = {"W": "L", "L": "W", "D": "D"}[wdl_h]
        form.setdefault(h, []).append(wdl_h)
        form.setdefault(a, []).append(wdl_a)
        applied += 1

    # 2) tables + bracket on the post-update ratings
    tables = {g: standings.group_standings(matches, observed, teams, g)
              for g in standings.GROUPS}
    bracket = standings.resolve_bracket(matches, observed, teams)

    # 3) Monte Carlo tournament simulation (needed for pairing probabilities)
    mc, pair_share = simulate.Simulator(teams, matches, observed).run(sims)

    # 4) per-match predictions + Hungarian analysis
    # rest-day map: each team's last match date (observed or scheduled, resolved bracket)
    last_date = {}
    team_dates = {}
    for m in sorted(matches, key=lambda x: (x["date"], x["time_et"])):
        if m["stage"] == "group":
            sides = (m["home"], m["away"])
        else:
            hh, aa, _ = bracket.get(m["id"], (None, None, True))
            sides = tuple(x for x in (hh, aa) if x)
        for c in sides:
            team_dates.setdefault(c, []).append(m["date"])

    def rest_diff(mdate, h, a):
        def last_before(c):
            prev = [d for d in team_dates.get(c, []) if d < mdate]
            return prev[-1] if prev else None
        lh_, la_ = last_before(h), last_before(a)
        if not lh_ or not la_:
            return 0
        days = lambda d: int(d[8:10]) + (0 if d[5:7] == "06" else 30)
        return (days(mdate) - days(lh_)) - (days(mdate) - days(la_))

    perf = {"evaluated": 0, "hit_1x2": 0, "hit_exact": 0, "brier_sum": 0.0}
    entries = []
    for m in matches:
        e = {"match": m}
        if m["stage"] == "group":
            h, a, proj = m["home"], m["away"], False
        else:
            h, a, proj = bracket[m["id"]]
            if str(m["id"]) in observed:
                h, a = bracket_seen.get(m["id"], (h, a))
        if h is None or a is None:
            e.update(status="tbd", home_name="– (később dől el)",
                     away_name="– (később dől el)", analysis=[])
            entries.append(e); continue
        th, ta = teams[h], teams[a]
        e["home_name"], e["away_name"] = th["name"], ta["name"]
        key = str(m["id"])
        if key in observed:
            e["status"] = "done"
            e["result"] = observed[key]
            e["pred"] = pre_match_pred.get(m["id"])
            p = e["pred"]
            if p:
                r = observed[key]
                o = (1, 0, 0) if r["gh"] > r["ga"] else \
                    ((0, 1, 0) if r["gh"] == r["ga"] else (0, 0, 1))
                probs = (p["p1"], p["px"], p["p2"])
                perf["evaluated"] += 1
                perf["hit_1x2"] += probs.index(max(probs)) == o.index(1)
                ts0 = p["top_scores"][0]
                perf["hit_exact"] += (ts0["h"], ts0["a"]) == (r["gh"], r["ga"])
                perf["brier_sum"] += sum((pp - oo) ** 2 for pp, oo in zip(probs, o))
            e["analysis"] = [f"Végeredmény: {th['name']} {observed[key]['gh']}–"
                             f"{observed[key]['ga']} {ta['name']}. Az eredmény beépült a "
                             f"modellbe (Elo- és támadó/védő-frissítés)."]
        else:
            pred = ratings.predict(th, ta, m["venue_country"],
                                   knockout=(m["stage"] != "group"),
                                   rest_diff_days=rest_diff(m["date"], h, a)
                                   if m["stage"] != "group" else 0)
            e["pred"] = pred
            e["conf_score"], e["conf_label"] = analysis.confidence(pred, th, ta)
            e["status"] = "proj" if proj else "sched"
            if m["stage"] != "group":
                e["pair_share"] = round(pair_share.get(m["id"], {}).get((h, a), 0.0), 4)
            ctx = None
            if m["stage"] == "group":
                row_h = next(r for r in tables[m["group"]] if r["code"] == h)
                row_a = next(r for r in tables[m["group"]] if r["code"] == a)
                ctx = (f"Csoporthelyzet ({m['group']}): {th['name']} jelenleg/várhatóan "
                       f"{row_h['rank']}. ({row_h['pts']} pont), {ta['name']} "
                       f"{row_a['rank']}. ({row_a['pts']} pont).")
            e["analysis"] = analysis.build(m, pred, th, ta, ctx, form, projected=proj)
        entries.append(e)

    if perf["evaluated"]:
        perf["hit_1x2_rate"] = round(perf["hit_1x2"] / perf["evaluated"], 3)
        perf["hit_exact_rate"] = round(perf["hit_exact"] / perf["evaluated"], 3)
        perf["avg_brier"] = round(perf["brier_sum"] / perf["evaluated"], 4)
    with open(os.path.join(ROOT, "data", "performance.json"), "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=1)

    # 5) render
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_out = render(entries, tables, teams, now, applied, mc, sims, perf)
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_out)
    with open(os.path.join(ROOT, "data", "predictions.json"), "w", encoding="utf-8") as f:
        json.dump(dict(matches=[{k: v for k, v in e.items() if k != "match"} |
                                {"id": e["match"]["id"]} for e in entries],
                       monte_carlo=dict(runs=sims, probabilities=mc)),
                  f, ensure_ascii=False, indent=1)
    print(f"OK — {applied} eredmény feldolgozva, {len(entries)} meccs renderelve -> index.html")

if __name__ == "__main__":
    main()
