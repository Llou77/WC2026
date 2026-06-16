# -*- coding: utf-8 -*-
"""Monte Carlo tournament simulation.

Simulates the full remaining tournament N times (default 10,000) on top of the
already-observed results: group scorelines are sampled from each match's
Poisson/DC grid, standings and the third-place bracket assignment are resolved
per run, knockout draws are settled with the calibrated ET/pens share. Output:
per-team probabilities of group win, reaching each round, and the title.

Pure stdlib; ~10k runs complete in a few seconds (grids are cached per pairing).
"""
import bisect, random
from . import ratings, standings

def _h2h_int(order, rows, h2h, rng):
    """Head-to-head re-rank for fully tied (pts, gd, gf) clusters; random lots last."""
    out, i = list(order), 0
    key = lambda c: (rows[c][0], rows[c][1] - rows[c][2], rows[c][1])
    while i < len(out):
        j = i + 1
        while j < len(out) and key(out[j]) == key(out[i]):
            j += 1
        if j - i >= 2:
            codes = set(out[i:j])
            mini = {c: [0, 0, 0] for c in codes}
            for (h, a), (gh, ga) in h2h.items():
                if h in codes and a in codes:
                    mini[h][0] += 3 if gh > ga else (1 if gh == ga else 0)
                    mini[a][0] += 3 if ga > gh else (1 if gh == ga else 0)
                    mini[h][1] += gh; mini[h][2] += ga
                    mini[a][1] += ga; mini[a][2] += gh
            out[i:j] = sorted(out[i:j], key=lambda c: (
                mini[c][0], mini[c][1] - mini[c][2], mini[c][1], rng.random()),
                reverse=True)
        i = j
    return out

ROUNDS = ["r32", "r16", "qf", "sf", "final", "champion", "group_win"]

def _cdf(grid):
    flat, cum, acc = [], [], 0.0
    for i, row in enumerate(grid):
        for j, p in enumerate(row):
            acc += p; flat.append((i, j)); cum.append(acc)
    return flat, cum

class Simulator:
    def __init__(self, teams, matches, observed, seed=2026):
        self.teams, self.matches, self.observed = teams, matches, observed
        self.rng = random.Random(seed)
        self._grids = {}
        self.group_matches = {g: [m for m in matches if m["stage"] == "group"
                                  and m["group"] == g] for g in standings.GROUPS}
        self.ko = sorted((m for m in matches if m["stage"] not in ("group", "third")),
                         key=lambda m: m["id"])
        self.md_map = standings.matchday_map(matches)
        self.third_slots = sorted((m["id"], set(m["away"].split(":")[1]))
                                  for m in matches
                                  if m["stage"] == "r32" and m["away"].startswith("T:"))

    def _grid(self, h, a, vc, md=None, city=None):
        key = (h, a, vc, md, city)
        if key not in self._grids:
            p = ratings.predict(self.teams[h], self.teams[a], vc, md=md, venue_city=city)
            # rebuild a sampling grid from the (altitude-adjusted) lambdas
            grid = ratings.score_grid(p["lh"], p["la"])
            self._grids[key] = _cdf(grid)
        return self._grids[key]

    def _sample(self, h, a, vc, md=None, city=None):
        flat, cum = self._grid(h, a, vc, md, city)
        return flat[bisect.bisect(cum, self.rng.random() * cum[-1])]

    def run(self, n=10000):
        counts = {c: {r: 0 for r in ROUNDS} for c in self.teams}
        pairs = {m["id"]: {} for m in self.ko}
        for _ in range(n):
            self._one(counts, pairs)
        probs = {c: {r: counts[c][r] / n for r in ROUNDS} for c in counts}
        pair_share = {mid: {k: v / n for k, v in d.items()} for mid, d in pairs.items()}
        return probs, pair_share

    def _one(self, counts, pairs):
        rng = self.rng
        # --- group stage ---
        tables = {}
        for g, ms in self.group_matches.items():
            rows, h2h = {}, {}
            for m in ms:
                for c in (m["home"], m["away"]):
                    rows.setdefault(c, [0, 0, 0])      # pts, gf, ga
                o = self.observed.get(str(m["id"]))
                gh, ga = (o["gh"], o["ga"]) if o else \
                    self._sample(m["home"], m["away"], m["venue_country"],
                                 self.md_map.get(m["id"]), m.get("venue"))
                h2h[(m["home"], m["away"])] = (gh, ga)
                rows[m["home"]][0] += 3 if gh > ga else (1 if gh == ga else 0)
                rows[m["away"]][0] += 3 if ga > gh else (1 if gh == ga else 0)
                rows[m["home"]][1] += gh; rows[m["home"]][2] += ga
                rows[m["away"]][1] += ga; rows[m["away"]][2] += gh
            order = sorted(rows, key=lambda c: (rows[c][0], rows[c][1] - rows[c][2],
                                                rows[c][1]), reverse=True)
            order = _h2h_int(order, rows, h2h, rng)
            tables[g] = (order, rows)
            counts[order[0]]["group_win"] += 1
        # --- best 8 thirds + slot assignment ---
        thirds = sorted(((tables[g][1][tables[g][0][2]], g, tables[g][0][2])
                         for g in standings.GROUPS),
                        key=lambda x: (x[0][0], x[0][1] - x[0][2], x[0][1],
                                       rng.random()), reverse=True)
        best8 = {g: c for _, g, c in thirds[:8]}
        assign = standings._assign_thirds(self.third_slots, best8)
        # --- knockout ---
        winners, losers = {}, {}
        for m in self.ko:
            sides = []
            for spec in (m["home"], m["away"]):
                kind, ref = spec.split(":")
                if kind == "W":   sides.append(tables[ref][0][0])
                elif kind == "R": sides.append(tables[ref][0][1])
                elif kind == "T": sides.append(best8[assign[m["id"]]])
                elif kind == "M": sides.append(winners[int(ref)])
                else:             sides.append(losers[int(ref)])
            h, a = sides
            pairs[m["id"]][(h, a)] = pairs[m["id"]].get((h, a), 0) + 1
            counts[h][m["stage"]] += 1; counts[a][m["stage"]] += 1
            o = self.observed.get(str(m["id"]))
            if o:
                gh, ga = o["gh"], o["ga"]
                hw = gh > ga or (gh == ga and o.get("winner_home", True))
            else:
                # altitude must match the per-match KO prediction: pass the
                # venue city (e.g. Estadio Azteca, 2240 m) so adapted sides keep
                # their edge in the sim too. Deliberately NOT passed: per-match
                # suspension/injury elo_adj (one-match, short-lived — wrong to
                # apply across a full-tournament run) and the MD3 "locked-fate"
                # penalty (endogenous to each simulated table).
                gh, ga = self._sample(h, a, m["venue_country"], None, m.get("venue"))
                if gh != ga:
                    hw = gh > ga
                else:
                    ev = ratings.expectancy(self.teams[h]["elo"], self.teams[a]["elo"])
                    hw = rng.random() < 0.5 + (ev - 0.5) * ratings.ET_SHRINK
            winners[m["id"]] = h if hw else a
            losers[m["id"]] = a if hw else h
        counts[winners[104]]["champion"] += 1
