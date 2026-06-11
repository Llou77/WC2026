# -*- coding: utf-8 -*-
"""Incremental rating model + Poisson match prediction.

Design goals:
- NO refitting. Ratings update incrementally per observed match (O(1)/match),
  so a full daily recompute over the whole tournament takes < 1 second.
- Ratings are always rebuilt deterministically from the seed + the full
  observed-results list, so the pipeline is idempotent and restartable.
- Richer post-match data (xG, shots) is blended into the attack/defence
  multipliers when available; plain scores are enough as a fallback.
"""
import json, math, os

HOME_ELO_BONUS = 80        # host nation playing in its own country
K_BASE = 50                # World Cup importance (eloratings.net convention)
K_PROVISIONAL = 85         # faster learning while a seed Elo is only an estimate
PROVISIONAL_GAMES = 3      # provisional K applies to the first N matches
TOTAL_GOALS_BASE = 2.80    # backtest-tuned (see backtest/REPORT.md)
ATTDEF_LR = 0.35           # learning rate for attack/defence multipliers
ATTDEF_CLIP = (0.70, 1.40)
DC_DRAW_BOOST = 1.15       # backtest-tuned draw inflation
GD_SCALE = 160.0           # backtest-tuned Elo pts per goal of expected diff
ET_SHRINK = 0.33           # ET+pens edge shrink; pens alone ~0.19 (541 shootouts)
MAX_GOALS = 8

# shot-based pseudo-xG weights (literature averages: ~0.30 goal/shot on target,
# ~0.03 for off-target attempts); used only when true xG is not supplied
SOT_XG, OFF_XG = 0.30, 0.03
RED_CARD_DISCOUNT = 0.80   # a result shaped by a red card is less informative

def effective_xg(res, side):
    """Best available xG-like signal for one side: true xG > shot-based proxy > None."""
    xg = res.get(f"xg_{side}")
    if xg is not None:
        return float(xg)
    sot = res.get(f"sot_{side}")
    if sot is not None:
        shots = res.get(f"shots_{side}")
        off = (shots - sot) if shots is not None else sot * 1.5
        return SOT_XG * sot + OFF_XG * max(0.0, off)
    return None

def _k(team):
    """Per-team K: estimated-seed teams learn faster for their first games."""
    if team.get("elo_estimated") and team.get("played", 0) < PROVISIONAL_GAMES:
        return K_PROVISIONAL
    return K_BASE

_BLEND = None
def _load_blend():
    """Lazy-load the trained 1X2 recalibration (backtest/train_blend.py)."""
    global _BLEND
    if _BLEND is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "data", "blend.json")
        try:
            with open(path) as f:
                _BLEND = json.load(f)
        except OSError:
            _BLEND = False
    return _BLEND

def _softmax(z):
    m = max(z); e = [math.exp(v - m) for v in z]; t = sum(e)
    return [v / t for v in e]

def _bonus(team_h, team_a, venue_country, extra=0.0):
    b = extra
    b += HOME_ELO_BONUS if team_h["code"] == venue_country else 0.0
    b -= HOME_ELO_BONUS if team_a["code"] == venue_country else 0.0
    return b

def calibrated_grid(team_h, team_a, venue_country, extra_h_bonus=0.0):
    """Poisson/DC grid, class-rescaled to the blended (softmax-mixed) 1X2.
    Used by predict() AND the Monte Carlo sampler, so the two stay consistent."""
    lh, la = lambdas(team_h, team_a, venue_country, extra_h_bonus)
    grid = score_grid(lh, la)
    b = _load_blend()
    if b:
        n = MAX_GOALS + 1
        pw = sum(grid[i][j] for i in range(n) for j in range(n) if i > j)
        pd = sum(grid[i][i] for i in range(n))
        pl = 1.0 - pw - pd
        dr = (team_h["elo"] + _bonus(team_h, team_a, venue_country, extra_h_bonus)
              - team_a["elo"])
        x = [1.0, dr / 400.0, abs(dr) / 400.0]
        soft = _softmax([sum(b["W"][c][k] * x[k] for k in range(3)) for c in range(3)])
        w = b["w"]
        tgt = [(1 - w) * p + w * s for p, s in zip((pw, pd, pl), soft)]
        t = sum(tgt); tgt = [v / t for v in tgt]
        sc = [tgt[0] / max(pw, 1e-9), tgt[1] / max(pd, 1e-9), tgt[2] / max(pl, 1e-9)]
        for i in range(n):
            for j in range(n):
                grid[i][j] *= sc[0] if i > j else (sc[1] if i == j else sc[2])
    return grid, lh, la

def expectancy(elo_h, elo_a, home_bonus=0.0):
    return 1.0 / (1.0 + 10 ** (-((elo_h + home_bonus) - elo_a) / 400.0))

def lambdas(team_h, team_a, venue_country, extra_h_bonus=0.0):
    """Expected goals for both sides from Elo gap + att/def multipliers."""
    bonus = extra_h_bonus
    bonus += HOME_ELO_BONUS if team_h["code"] == venue_country else 0.0
    bonus -= HOME_ELO_BONUS if team_a["code"] == venue_country else 0.0
    dr = (team_h["elo"] + bonus) - team_a["elo"]
    gd = max(-2.5, min(2.5, dr / GD_SCALE))        # expected goal difference
    total = TOTAL_GOALS_BASE + 0.45 * abs(gd)      # mismatches -> more goals
    lh = max(0.15, (total + gd) / 2.0) * team_h["att"] * team_a["deff"]
    la = max(0.15, (total - gd) / 2.0) * team_a["att"] * team_h["deff"]
    return lh, la

def _pois(lmb, k):
    return math.exp(-lmb) * lmb ** k / math.factorial(k)

def score_grid(lh, la):
    grid = [[_pois(lh, i) * _pois(la, j) for j in range(MAX_GOALS + 1)]
            for i in range(MAX_GOALS + 1)]
    # Dixon-Coles-lite correction on low scores
    for (i, j, f) in [(0,0,DC_DRAW_BOOST),(1,1,DC_DRAW_BOOST),(1,0,0.97),(0,1,0.97)]:
        grid[i][j] *= f
    s = sum(sum(r) for r in grid)
    return [[v / s for v in row] for row in grid]

REST_ELO_PER_DAY = 8       # knockout rest-day differential (capped; heuristic)
REST_CAP = 24

def predict(team_h, team_a, venue_country, knockout=False, rest_diff_days=0):
    extra = max(-REST_CAP, min(REST_CAP, REST_ELO_PER_DAY * rest_diff_days)) if knockout else 0.0
    grid, lh, la = calibrated_grid(team_h, team_a, venue_country, extra)
    pw = sum(grid[i][j] for i in range(MAX_GOALS+1) for j in range(MAX_GOALS+1) if i > j)
    pd = sum(grid[i][i] for i in range(MAX_GOALS+1))
    pl = 1.0 - pw - pd
    scores = sorted(((grid[i][j], i, j) for i in range(MAX_GOALS+1)
                     for j in range(MAX_GOALS+1)), reverse=True)
    top = [dict(h=i, a=j, p=round(p, 4)) for p, i, j in scores[:3]]
    out = dict(lh=round(lh,2), la=round(la,2),
               p1=round(pw,4), px=round(pd,4), p2=round(pl,4), top_scores=top)
    if knockout:
        # if 90' ends level, extra time / penalties: split the draw mass by
        # Elo expectancy (pens slightly closer to 50-50)
        ev = expectancy(team_h["elo"], team_a["elo"])
        et_share = 0.5 + (ev - 0.5) * ET_SHRINK
        adv_h = pw + pd * et_share
        out["adv_h"] = round(adv_h, 4)
        out["adv_a"] = round(1 - adv_h, 4)
        out["favorite"] = team_h["code"] if adv_h >= 0.5 else team_a["code"]
    return out

def apply_result(team_h, team_a, res, venue_country):
    """Incrementally update Elo + att/def from one observed match.
    res: dict with gh, ga and optionally xg_h, xg_a (floats)."""
    gh, ga = res["gh"], res["ga"]
    # pre-match expectation MUST be computed before the Elo update,
    # otherwise the winner's attack rating is systematically biased down
    lh, la = lambdas(team_h, team_a, venue_country)
    # --- Elo update (goal-difference weighted K, eloratings.net style) ---
    bonus = HOME_ELO_BONUS if team_h["code"] == venue_country else 0.0
    bonus -= HOME_ELO_BONUS if team_a["code"] == venue_country else 0.0
    ev = expectancy(team_h["elo"], team_a["elo"], bonus)
    w = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
    d = abs(gh - ga)
    g = 1.0 if d <= 1 else (1.5 if d == 2 else (11 + d) / 8.0)
    if res.get("red_h") or res.get("red_a"):
        g *= RED_CARD_DISCOUNT
    team_h["elo"] = round(team_h["elo"] + _k(team_h) * g * (w - ev), 1)
    team_a["elo"] = round(team_a["elo"] - _k(team_a) * g * (w - ev), 1)
    team_h["played"] = team_h.get("played", 0) + 1
    team_a["played"] = team_a.get("played", 0) + 1
    # --- attack/defence multipliers, xG-blended when available ---
    exg_h, exg_a = effective_xg(res, "h"), effective_xg(res, "a")
    perf_h = 0.7 * gh + 0.3 * exg_h if exg_h is not None else float(gh)
    perf_a = 0.7 * ga + 0.3 * exg_a if exg_a is not None else float(ga)
    lo, hi = ATTDEF_CLIP
    for team, perf, exp, opp in ((team_h, perf_h, lh, team_a), (team_a, perf_a, la, team_h)):
        ratio = (perf + 0.5) / (exp + 0.5)
        team["att"] = min(hi, max(lo, team["att"] * ratio ** ATTDEF_LR))
        opp["deff"] = min(hi, max(lo, opp["deff"] * ratio ** (ATTDEF_LR * 0.6)))
