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
import csv as _csv

def load_history(code_of):
    """H2H + pre-tournament form from the historical dataset shipped in
    backtest/. Returns (h2h, preform); both empty on any failure (fail-safe)."""
    path = os.path.join(ROOT, "backtest", "results.csv")
    h2h, recent = {}, {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in _csv.DictReader(f):
                if r["home_score"] in ("", "NA") or r["date"] >= "2026-06-11":
                    continue
                ch, ca = code_of.get(r["home_team"]), code_of.get(r["away_team"])
                if ch:
                    recent.setdefault(ch, []).append(
                        (r["date"], int(r["home_score"]), int(r["away_score"]), r["tournament"]))
                if ca:
                    recent.setdefault(ca, []).append(
                        (r["date"], int(r["away_score"]), int(r["home_score"]), r["tournament"]))
                if ch and ca:
                    h2h.setdefault(frozenset((ch, ca)), []).append(
                        (r["date"], ch, int(r["home_score"]), int(r["away_score"]),
                         r["tournament"]))
    except Exception as e:
        print(f"! történelmi adattár nem olvasható (H2H/forma kihagyva): {e}")
        return {}, {}
    preform = {}
    for c, ms in recent.items():
        last8 = sorted(ms)[-8:]
        w = sum(1 for _, gf, ga, _ in last8 if gf > ga)
        d = sum(1 for _, gf, ga, _ in last8 if gf == ga)
        preform[c] = dict(n=len(last8), w=w, d=d, l=len(last8) - w - d,
                          gf=sum(m[1] for m in last8), ga=sum(m[2] for m in last8))
    return h2h, preform
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
    try:
        from scripts.fetch_data import NAME2CODE
        h2h_db, preform = load_history(NAME2CODE)
    except Exception as e:
        print(f"! H2H/forma réteg kihagyva: {e}")
        h2h_db, preform = {}, {}
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
    md_map = standings.matchday_map(matches)
    tables = {g: standings.group_standings(matches, observed, teams, g, md_map)
              for g in standings.GROUPS}

    # locked group fate before MD3 (points-only enumeration of the two
    # remaining fixtures; ties treated as not locked -> conservative)
    locked = set()
    for g in standings.GROUPS:
        gms = [m for m in matches if m["stage"] == "group" and m["group"] == g]
        md3 = [m for m in gms if md_map[m["id"]] == 3 and str(m["id"]) not in observed]
        played = [m for m in gms if str(m["id"]) in observed]
        if len(played) != 4 or len(md3) != 2:
            continue
        pts = {}
        for m in played:
            r = observed[str(m["id"])]
            ph = 3 if r["gh"] > r["ga"] else (1 if r["gh"] == r["ga"] else 0)
            pts[m["home"]] = pts.get(m["home"], 0) + ph
            pts[m["away"]] = pts.get(m["away"], 0) + (3 - ph if r["gh"] != r["ga"] else 1)
        (m1, m2) = md3
        for t in (m1["home"], m1["away"], m2["home"], m2["away"]):
            top = out = True
            for r1 in ((3, 0), (1, 1), (0, 3)):
                for r2 in ((3, 0), (1, 1), (0, 3)):
                    f = dict(pts)
                    f[m1["home"]] = f.get(m1["home"], 0) + r1[0]
                    f[m1["away"]] = f.get(m1["away"], 0) + r1[1]
                    f[m2["home"]] = f.get(m2["home"], 0) + r2[0]
                    f[m2["away"]] = f.get(m2["away"], 0) + r2[1]
                    if sum(1 for x in f if x != t and f[x] >= f[t]) > 1:
                        top = False
                    if sum(1 for x in f if x != t and f[x] > f[t]) < 2:
                        out = False
            if top or out:
                locked.add(t)

    # F1: automatic suspensions from per-player card events (data/cards.json)
    try:
        cards = load("cards.json")
    except Exception:
        cards = {}
    suspended = {}      # team -> [player, ...] banned for their NEXT match
    ycount = {}
    order_pl = sorted((k for k in observed), key=lambda k: (mby[int(k)]["date"],
                                                            mby[int(k)]["time_et"]))
    last_played = {}
    for k in order_pl:
        for ev in cards.get(k, []):
            t, pl, typ = ev.get("team"), ev.get("player"), ev.get("type")
            if not t or not pl:
                continue
            key2 = (t, pl)
            if typ == "yellow":
                ycount[key2] = ycount.get(key2, 0) + 1
            last_played.setdefault(t, k)
            last_played[t] = k
    for k in order_pl:
        for ev in cards.get(k, []):
            t, pl, typ = ev.get("team"), ev.get("player"), ev.get("type")
            if not t or not pl or last_played.get(t) != k:
                continue   # csak az utolsó lejátszott meccs lapjai tiltanak a következőre
            if typ == "red" or (typ == "yellow" and ycount.get((t, pl), 0) >= 2):
                suspended.setdefault(t, [])
                if pl not in suspended[t]:
                    suspended[t].append(pl)
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
            def susp_adj(team):
                bans = suspended.get(team["code"], [])
                key_bans = [p for p in bans if p in team.get("players", [])]
                return -25.0 * min(2, len(key_bans)), bans
            adj_h, bans_h = susp_adj(th)
            adj_a, bans_a = susp_adj(ta)
            if m["stage"] == "group" and md_map.get(m["id"]) == 3:
                if h in locked: adj_h -= ratings.LOCKED_ELO_PENALTY
                if a in locked: adj_a -= ratings.LOCKED_ELO_PENALTY
            pred = ratings.predict(th, ta, m["venue_country"],
                                   knockout=(m["stage"] != "group"),
                                   rest_diff_days=rest_diff(m["date"], h, a)
                                   if m["stage"] != "group" else 0,
                                   md=md_map.get(m["id"]),
                                   elo_adj_h=adj_h, elo_adj_a=adj_a)
            e["pred"] = pred
            e["conf_score"], e["conf_label"] = analysis.confidence(pred, th, ta)
            e["status"] = "proj" if proj else "sched"
            if m["stage"] != "group":
                e["pair_share"] = round(pair_share.get(m["id"], {}).get((h, a), 0.0), 4)
            ctx_extra = []
            for team, bans in ((th, bans_h), (ta, bans_a)):
                if bans:
                    ctx_extra.append(f"{team['name']} eltiltottjai erre a mérkőzésre: "
                                     f"{', '.join(bans)}.")
            for team in (th, ta):
                if m["stage"] == "group" and md_map.get(m["id"]) == 3 \
                        and team["code"] in locked:
                    ctx_extra.append(f"{team['name']} csoportbeli sorsa már eldőlt — a "
                                     f"modell rotációs/motivációs levonással számol.")
            ctx = None
            if m["stage"] == "group":
                row_h = next(r for r in tables[m["group"]] if r["code"] == h)
                row_a = next(r for r in tables[m["group"]] if r["code"] == a)
                ctx = (f"Csoporthelyzet ({m['group']}): {th['name']} jelenleg/várhatóan "
                       f"{row_h['rank']}. ({row_h['pts']} pont), {ta['name']} "
                       f"{row_a['rank']}. ({row_a['pts']} pont).")
            if ctx_extra:
                ctx = (ctx + " " if ctx else "") + " ".join(ctx_extra)
            e["analysis"] = analysis.build(m, pred, th, ta, ctx, form, projected=proj,
                                           channels=channels, player_form=player_form,
                                           h2h=h2h_db.get(frozenset((h, a))),
                                           preform=preform)
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
