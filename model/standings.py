# -*- coding: utf-8 -*-
"""Group standings (real + projected) and knockout-bracket resolution."""
from . import ratings

def matchday_map(matches):
    """{match_id: 1|2|3} for group matches, by per-team match order."""
    cnt, out = {}, {}
    for m in sorted((m for m in matches if m["stage"] == "group"),
                    key=lambda x: (x["date"], x["time_et"])):
        md = cnt.get(m["home"], 0) + 1
        out[m["id"]] = md
        cnt[m["home"]] = cnt.get(m["home"], 0) + 1
        cnt[m["away"]] = cnt.get(m["away"], 0) + 1
    return out

def group_standings(matches, observed, teams, group, md_map=None):
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
            p = ratings.predict(th, ta, m["venue_country"],
                                md=(md_map or {}).get(m["id"]))
            rows[m["home"]]["pts"] += 3 * p["p1"] + p["px"]
            rows[m["away"]]["pts"] += 3 * p["p2"] + p["px"]
            rows[m["home"]]["gf"] += p["lh"]; rows[m["home"]]["ga"] += p["la"]
            rows[m["away"]]["gf"] += p["la"]; rows[m["away"]]["ga"] += p["lh"]
            rows[m["home"]]["projected"] = rows[m["away"]]["projected"] = True
    out = sorted(rows.values(),
                 key=lambda r: (r["pts"], r["gf"] - r["ga"], r["gf"]), reverse=True)
    _h2h_rerank(out, matches, observed, group)
    for i, r in enumerate(out):
        r["rank"] = i + 1
        r["gd"] = round(r["gf"] - r["ga"], 1)
        r["pts"] = round(r["pts"], 1); r["gf"] = round(r["gf"],1); r["ga"] = round(r["ga"],1)
    return out

def _h2h_rerank(out, matches, observed, group):
    """FIFA tiebreaker: teams level on points, GD and GF are re-ranked by their
    head-to-head record (points, GD, GF) from played matches; deterministic
    code-order as the final fallback."""
    i = 0
    key = lambda r: (round(r["pts"], 2), round(r["gf"] - r["ga"], 2), round(r["gf"], 2))
    while i < len(out):
        j = i + 1
        while j < len(out) and key(out[j]) == key(out[i]):
            j += 1
        if j - i >= 2:
            codes = {r["code"] for r in out[i:j]}
            mini = {c: [0, 0, 0] for c in codes}
            for m in matches:
                if (m["stage"] == "group" and m["group"] == group
                        and str(m["id"]) in observed
                        and m["home"] in codes and m["away"] in codes):
                    r = observed[str(m["id"])]
                    gh, ga = r["gh"], r["ga"]
                    mini[m["home"]][0] += 3 if gh > ga else (1 if gh == ga else 0)
                    mini[m["away"]][0] += 3 if ga > gh else (1 if gh == ga else 0)
                    mini[m["home"]][1] += gh; mini[m["home"]][2] += ga
                    mini[m["away"]][1] += ga; mini[m["away"]][2] += gh
            out[i:j] = sorted(out[i:j], key=lambda r: (
                mini[r["code"]][0], mini[r["code"]][1] - mini[r["code"]][2],
                mini[r["code"]][1], r["code"]), reverse=True)
        i = j

GROUPS = list("ABCDEFGHIJKL")

# FIFA 2026 Annex C — official mapping of qualified third-place GROUPS to the
# eight R32 third-place slots, keyed first by the SET of the eight groups whose
# thirds qualified, then by each slot's allowed-group set. Only combinations
# actually needed are tabulated; an untabulated combination falls back to a
# constraint-satisfying approximation (_assign_thirds). Source: FIFA regulations
# Annex C (cross-checked against the published R32 bracket).
_ANNEX_C = {
    # thirds qualified from groups B, D, E, F, I, J, K, L (2026 actual)
    frozenset("BDEFIJKL"): {
        frozenset("ABCDF"): "D", frozenset("CDFGH"): "F",
        frozenset("CEFHI"): "E", frozenset("EHIJK"): "K",
        frozenset("BEFIJ"): "B", frozenset("AEHIJ"): "I",
        frozenset("EFGIJ"): "J", frozenset("DEIJL"): "L",
    },
}

def _annex_c_assign(qualified, third_slots):
    """Return {match_id: group} from the official Annex C table, or None if the
    qualified-thirds combination (or a slot within it) is not tabulated."""
    table = _ANNEX_C.get(qualified)
    if not table:
        return None
    out = {}
    for mid, allowed in third_slots.items():
        g = table.get(frozenset(allowed))
        if g is None:
            return None
        out[mid] = g
    return out

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
    qualified = frozenset(t["group"] for t in best8)
    assign = _annex_c_assign(qualified, third_slots)     # official FIFA table
    if assign is None:                                   # untabulated -> approximate
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
