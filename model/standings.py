# -*- coding: utf-8 -*-
"""Group standings (real + projected) and knockout-bracket resolution."""
from . import ratings

def group_standings(matches, observed, teams, group):
    """Returns ranked list of dicts. Unplayed matches contribute *expected*
    points/goals so the table doubles as a projection."""
    rows = {t["code"]: dict(code=t["code"], pts=0.0, gf=0.0, ga=0.0,
                            played=0, real_pts=0, projected=False)
            for t in teams.values() if t["group"] == group}
    for m in matches:
        if m["stage"] != "group" or m["group"] != group:
            continue
        key = str(m["id"])
        th, ta = teams[m["home"]], teams[m["away"]]
        if key in observed:
            r = observed[key]
            gh, ga = r["gh"], r["ga"]
            rows[m["home"]]["pts"] += 3 if gh > ga else (1 if gh == ga else 0)
            rows[m["away"]]["pts"] += 3 if ga > gh else (1 if gh == ga else 0)
            rows[m["home"]]["real_pts"] = rows[m["home"]]["pts"]
            rows[m["away"]]["real_pts"] = rows[m["away"]]["pts"]
            rows[m["home"]]["gf"] += gh; rows[m["home"]]["ga"] += ga
            rows[m["away"]]["gf"] += ga; rows[m["away"]]["ga"] += gh
            rows[m["home"]]["played"] += 1; rows[m["away"]]["played"] += 1
        else:
            p = ratings.predict(th, ta, m["venue_country"])
            rows[m["home"]]["pts"] += 3 * p["p1"] + p["px"]
            rows[m["away"]]["pts"] += 3 * p["p2"] + p["px"]
            rows[m["home"]]["gf"] += p["lh"]; rows[m["home"]]["ga"] += p["la"]
            rows[m["away"]]["gf"] += p["la"]; rows[m["away"]]["ga"] += p["lh"]
            rows[m["home"]]["projected"] = rows[m["away"]]["projected"] = True
    out = sorted(rows.values(),
                 key=lambda r: (r["pts"], r["gf"] - r["ga"], r["gf"]), reverse=True)
    for i, r in enumerate(out):
        r["rank"] = i + 1
        r["gd"] = round(r["gf"] - r["ga"], 1)
        r["pts"] = round(r["pts"], 1); r["gf"] = round(r["gf"],1); r["ga"] = round(r["ga"],1)
    return out

GROUPS = list("ABCDEFGHIJKL")

def resolve_bracket(matches, observed, teams):
    """Returns {match_id: (home_code, away_code, projected_bool)} for KO matches.
    Third-place slots are filled with a constraint-satisfying assignment
    (approximation of FIFA Annex C; documented in README)."""
    tables = {g: group_standings(matches, observed, teams, g) for g in GROUPS}
    projected_groups = {g: any(r["projected"] for r in tables[g]) for g in GROUPS}
    thirds = sorted((dict(tables[g][2], group=g) for g in GROUPS),
                    key=lambda r: (r["pts"], r["gd"], r["gf"]), reverse=True)
    best8 = thirds[:8]
    third_slots = {m["id"]: set(m["away"].split(":")[1]) for m in matches
                   if m["stage"] == "r32" and m["away"].startswith("T:")}
    assign = _assign_thirds(sorted(third_slots.items()),
                            {t["group"]: t["code"] for t in best8})
    resolved, proj_flag = {}, {}
    ko = sorted((m for m in matches if m["stage"] != "group"), key=lambda m: m["id"])
    for m in ko:
        sides, proj = [], False
        for spec in (m["home"], m["away"]):
            kind, ref = spec.split(":")
            if kind == "W":
                sides.append(tables[ref][0]["code"]); proj |= projected_groups[ref]
            elif kind == "R":
                sides.append(tables[ref][1]["code"]); proj |= projected_groups[ref]
            elif kind == "T":
                g = assign.get(m["id"])
                sides.append({t["group"]: t["code"] for t in best8}.get(g))
                proj |= any(projected_groups.values())
            elif kind in ("M", "L"):
                ref = int(ref)
                prev = resolved.get(ref)
                if prev is None:
                    sides.append(None); proj = True; continue
                ph, pa, pproj = prev
                key = str(ref)
                if key in observed:           # real knockout result
                    r = observed[key]
                    win = ph if _winner_is_home(r) else pa
                    lose = pa if win == ph else ph
                else:                          # model favorite advances
                    p = ratings.predict(teams[ph], teams[pa],
                                        _venue(matches, ref), knockout=True)
                    win, lose = (ph, pa) if p["favorite"] == ph else (pa, ph)
                    pproj = True
                sides.append(win if kind == "M" else lose); proj |= pproj
        resolved[m["id"]] = (sides[0], sides[1], proj)
    return resolved

def _winner_is_home(r):
    if r["gh"] != r["ga"]:
        return r["gh"] > r["ga"]
    return r.get("winner_home", True)   # ET/pens winner flag from ingest

def _venue(matches, mid):
    return next(m["venue_country"] for m in matches if m["id"] == mid)

def _assign_thirds(slots, group_to_code):
    """Backtracking: assign each qualified third-place group to one slot whose
    allowed-group set contains it. slots: [(match_id, allowed_set)]."""
    groups = list(group_to_code.keys())
    res = {}
    def bt(i, used):
        if i == len(slots):
            return True
        mid, allowed = slots[i]
        for g in groups:
            if g in used or g not in allowed:
                continue
            res[mid] = g; used.add(g)
            if bt(i + 1, used):
                return True
            used.discard(g); res.pop(mid, None)
        return False
    bt(0, set())
    return res
