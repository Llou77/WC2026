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
    try:
        lines = load("lineups.json").get("lines", {})
        for c, ln in lines.items():
            if c in teams and isinstance(ln, list) and len(ln) == 4:
                teams[c]["lines"] = ln
    except Exception as e:
        print(f"! lineups.json nem tölthető (párharc-réteg kikapcsolva): {e}")
    try:
        player_form = load("player_form.json")
    except Exception:
        player_form = {}
    matches = load("matches.json")
    observed = load("observed.json")   # {"<match_id>": {gh, ga, xg_h?, xg_a?, winner_home?}}
    mby = {m["id"]: m for m in matches}
    # érvénytelen bejegyzések kiszűrése — rossz adat ne törje a futást
    clean = {}
    for k, v in observed.items():
        try:
            if int(k) in mby and isinstance(v, dict) \
                    and isinstance(v.get("gh"), int) and isinstance(v.get("ga"), int):
                clean[k] = v
            else:
                print(f"! observed.json: érvénytelen bejegyzés átugorva: {k!r}")
        except (ValueError, TypeError):
            print(f"! observed.json: érvénytelen kulcs átugorva: {k!r}")
    observed = clean

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
        if h is None or a is None:
            print(f"! #{m['id']}: a résztvevők még nem feloldhatók, eredmény későbbre halasztva")
            continue
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
            team_dates.setdefault(c, []).append((m["date"], m["id"], m["stage"]))

    def rest_diff(mdate, h, a):
        def last_before(c):
            prev = [t for t in team_dates.get(c, []) if t[0] < mdate]
            return prev[-1] if prev else None
        def eff_rest(c):
            t = last_before(c)
            if not t:
                return None
            d, mid, stage = t
            days = lambda x: int(x[8:10]) + (0 if x[5:7] == "06" else 30)
            rest = days(mdate) - days(d)
            o = observed.get(str(mid))
            went_et = bool(o and stage != "group"
                           and (o.get("et") or o["gh"] == o["ga"]))
            return rest - (1 if went_et else 0)   # 120 perc ~ egy nappal kevesebb pihenő
        rh, ra = eff_rest(h), eff_rest(a)
        if rh is None or ra is None:
            return 0
        return rh - ra

    # tornán gyűlő csatorna-profilok az elemzésekhez (lövés/szöglet oda-vissza)
    channels = {}
    for key2, r2 in observed.items():
        m2 = mby[int(key2)]
        if m2["stage"] == "group":
            sides2 = ((m2["home"], "h", "a"), (m2["away"], "a", "h"))
        else:
            bs = bracket_seen.get(m2["id"])
            if not bs:
                continue
            sides2 = ((bs[0], "h", "a"), (bs[1], "a", "h"))
        for c2, me, opp in sides2:
            st = channels.setdefault(c2, {"n": 0, "sot_f": 0.0, "sot_a": 0.0,
                                          "cor_f": 0.0, "cor_a": 0.0})
            if r2.get(f"sot_{me}") is None:
                continue
            st["n"] += 1
            st["sot_f"] += r2[f"sot_{me}"]; st["sot_a"] += r2[f"sot_{opp}"]
            st["cor_f"] += r2.get(f"corners_{me}", 0); st["cor_a"] += r2.get(f"corners_{opp}", 0)
    for st in channels.values():
        if st["n"]:
            for k2 in ("sot_f", "sot_a", "cor_f", "cor_a"):
                st[k2] = st[k2] / st["n"]

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
                ts0 = p.get("tip") or p["top_scores"][0]
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
            e["analysis"] = analysis.build(m, pred, th, ta, ctx, form, projected=proj,
                                           channels=channels, player_form=player_form)
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
    out_path = os.path.join(ROOT, "index.html")
    with open(out_path + ".tmp", "w", encoding="utf-8") as f:
        f.write(html_out)
    os.replace(out_path + ".tmp", out_path)
    with open(os.path.join(ROOT, "data", "predictions.json"), "w", encoding="utf-8") as f:
        json.dump(dict(matches=[{k: v for k, v in e.items() if k != "match"} |
                                {"id": e["match"]["id"]} for e in entries],
                       monte_carlo=dict(runs=sims, probabilities=mc)),
                  f, ensure_ascii=False, indent=1)
    print(f"OK — {applied} eredmény feldolgozva, {len(entries)} meccs renderelve -> index.html")

if __name__ == "__main__":
    main()
