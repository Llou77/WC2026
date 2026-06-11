#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch finished World Cup results (and optional match stats) into
data/observed.json. Manual trigger; designed to run on your own machine or in
GitHub Actions where the network is open.

Primary source : football-data.org v4 (free API key; set FOOTBALL_DATA_TOKEN)
Stats overlay  : optional JSON file with xG/shots per match (see --stats)
Manual fallback: edit data/observed.json by hand — one object per match id.
Supported per-match stat fields (all optional, any subset works):
    gh, ga          final score (required)
    xg_h, xg_a      expected goals — the strongest signal, use when available
    sot_h, sot_a    shots on target  -> shot-based xG proxy when xG is missing
    shots_h, shots_a  total shots     -> refines the proxy
    red_h, red_a    true if the side received a red card (discounts the result)
    winner_home     knockout only: ET/pens winner when the score is level
Example: "5": {"gh":2,"ga":1,"sot_h":7,"sot_a":3,"shots_h":15,"shots_a":9,"red_a":true}

Usage:
    FOOTBALL_DATA_TOKEN=... python scripts/fetch_data.py
    python scripts/fetch_data.py --stats data/stats_overlay.json
    python scripts/fetch_data.py --dry-run     # show what would change
"""
import argparse, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"

# football-data.org English names -> our team codes
NAME2CODE = {
 "Mexico":"MEX","South Africa":"RSA","South Korea":"KOR","Korea Republic":"KOR",
 "Czechia":"CZE","Czech Republic":"CZE","Canada":"CAN","Bosnia and Herzegovina":"BIH",
 "Qatar":"QAT","Switzerland":"SUI","Brazil":"BRA","Morocco":"MAR","Haiti":"HAI",
 "Scotland":"SCO","United States":"USA","USA":"USA","Paraguay":"PAR","Australia":"AUS",
 "Turkey":"TUR","Türkiye":"TUR","Germany":"GER","Curaçao":"CUW","Curacao":"CUW",
 "Ivory Coast":"CIV","Côte d'Ivoire":"CIV","Ecuador":"ECU","Netherlands":"NED",
 "Japan":"JPN","Sweden":"SWE","Tunisia":"TUN","Belgium":"BEL","Egypt":"EGY",
 "Iran":"IRN","New Zealand":"NZL","Spain":"ESP","Cape Verde":"CPV","Cabo Verde":"CPV",
 "Saudi Arabia":"KSA","Uruguay":"URU","France":"FRA","Senegal":"SEN","Iraq":"IRQ",
 "Norway":"NOR","Argentina":"ARG","Algeria":"ALG","Austria":"AUT","Jordan":"JOR",
 "Portugal":"POR","DR Congo":"COD","Congo DR":"COD","Uzbekistan":"UZB",
 "Colombia":"COL","England":"ENG","Croatia":"CRO","Ghana":"GHA","Panama":"PAN",
}

def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)

def match_id_for(matches, code_h, code_a, date):
    """Match API result to our schedule by teams + UTC date (±1 day for TZ)."""
    for m in matches:
        if m["stage"] != "group":
            continue
        if {m["home"], m["away"]} == {code_h, code_a}:
            d0 = m["date"]
            if abs(_doy(d0) - _doy(date)) <= 1:
                return m["id"], m["home"] == code_h
    # knockout: teams aren't in the schedule; match purely by date proximity
    for m in matches:
        if m["stage"] == "group":
            continue
        if abs(_doy(m["date"]) - _doy(date)) <= 1:
            return m["id"], None   # caller stores as-is; update.py resolves sides
    return None, None

def _doy(d):
    y, m, day = map(int, d[:10].split("-"))
    return m * 31 + day

def fetch_api(token):
    req = urllib.request.Request(API, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", help="JSON overlay: {match_id: {xg_h, xg_a, ...}}")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    matches = load("matches.json")
    path = os.path.join(ROOT, "data", "observed.json")
    observed = load("observed.json")
    before = len(observed)

    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if token:
        data = fetch_api(token)
        for fm in data.get("matches", []):
            hn, an = fm["homeTeam"]["name"], fm["awayTeam"]["name"]
            ch, ca = NAME2CODE.get(hn), NAME2CODE.get(an)
            if not ch or not ca:
                print(f"  ! ismeretlen csapatnév: {hn} / {an} — kihagyva", file=sys.stderr)
                continue
            mid, home_is_h = match_id_for(matches, ch, ca, fm["utcDate"])
            if mid is None:
                print(f"  ! nem párosítható meccs: {hn}–{an} {fm['utcDate']}", file=sys.stderr)
                continue
            ft = fm["score"]["fullTime"]
            gh, ga = ft["home"], ft["away"]
            if home_is_h is False:           # API sides swapped vs our schedule
                gh, ga = ga, gh
            rec = {"gh": gh, "ga": ga}
            w = fm["score"].get("winner")
            if w in ("HOME_TEAM", "AWAY_TEAM") and gh == ga:   # decided in ET/pens
                rec["winner_home"] = (w == "HOME_TEAM") == (home_is_h is not False)
            observed[str(mid)] = observed.get(str(mid), {}) | rec
    else:
        print("FOOTBALL_DATA_TOKEN nincs beállítva — API-lekérés kihagyva, "
              "csak a kézi/overlay adatok frissülnek.")

    if args.stats:
        with open(args.stats, encoding="utf-8") as f:
            overlay = json.load(f)
        for mid, st in overlay.items():
            observed[str(mid)] = observed.get(str(mid), {}) | st

    print(f"Eredmények: {before} -> {len(observed)}")
    if args.dry_run:
        print(json.dumps(observed, ensure_ascii=False, indent=1))
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(observed, f, ensure_ascii=False, indent=1)
    print("data/observed.json frissítve. Következő lépés: python update.py")

if __name__ == "__main__":
    main()
