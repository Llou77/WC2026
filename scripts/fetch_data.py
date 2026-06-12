#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch finished World Cup results (and optional match stats) into
data/observed.json. Manual trigger; designed to run on your own machine or in
GitHub Actions where the network is open.

Primary source : football-data.org v4 (free API key; set FOOTBALL_DATA_TOKEN)
xG source      : API-Football v3 (optional; free key at dashboard.api-football.com,
                 set API_FOOTBALL_KEY) — fills xg_h/xg_a automatically
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
import argparse, csv, io, json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"
DETAIL = "https://api.football-data.org/v4/matches/{}"

# football-data.org statistics tömb -> observed.json mezők (corners-projekt mintájára)
STAT_MAP = {"SHOTS": "shots", "SHOTS_ON_GOAL": "sot", "CORNER_KICKS": "corners"}

GITHUB_CSV = ("https://raw.githubusercontent.com/martj42/"
              "international_results/master/results.csv")

def fetch_results_github(matches, observed):
    """Keyless fallback: daily-updated community results CSV. Fills only
    matches that are still missing; never overrides API data."""
    try:
        with urllib.request.urlopen(GITHUB_CSV, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"::warning::GitHub CSV-tartalék nem elérhető: {e}", file=sys.stderr)
        return 0
    added = 0
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("tournament") != "FIFA World Cup" or row["date"] < "2026-06-11":
            continue
        if row["home_score"] in ("", "NA"):
            continue
        ch, ca = NAME2CODE.get(row["home_team"]), NAME2CODE.get(row["away_team"])
        if not ch or not ca:
            continue
        mid, home_is_h = match_id_for(matches, ch, ca, row["date"])
        if mid is None or str(mid) in observed:
            continue
        gh, ga = int(row["home_score"]), int(row["away_score"])
        if home_is_h is False:
            gh, ga = ga, gh
        observed[str(mid)] = {"gh": gh, "ga": ga}
        added += 1
    if added:
        print(f"GitHub CSV-tartalék: {added} hiányzó eredmény pótolva.")
    return added

AF_FIXTURES = "https://v3.football.api-sports.io/fixtures?league=1&season=2026&status=FT"
AF_STATS = "https://v3.football.api-sports.io/fixtures/statistics?fixture={}"
AF_PLAYERS = "https://v3.football.api-sports.io/fixtures/players?fixture={}"
AF_EVENTS = "https://v3.football.api-sports.io/fixtures/events?fixture={}"

def fetch_cards_apifootball(matches, observed, key):
    """Per-player card events -> data/cards.json {mid: [{team,player,type}]}.
    Drives automatic suspension tracking in update.py. Fail-safe."""
    path = os.path.join(ROOT, "data", "cards.json")
    try:
        with open(path, encoding="utf-8") as f:
            cards = json.load(f)
    except OSError:
        cards = {}
    try:
        fixtures = _af_get(AF_FIXTURES, key).get("response", [])
    except Exception as e:
        print(f"! API-Football kártyaadat nem elérhető: {e}", file=sys.stderr)
        return
    for fx in fixtures:
        try:
            ch = NAME2CODE.get(fx["teams"]["home"]["name"])
            ca = NAME2CODE.get(fx["teams"]["away"]["name"])
            if not ch or not ca:
                continue
            mid, _ = match_id_for(matches, ch, ca, fx["fixture"]["date"][:10])
            if mid is None or str(mid) in cards or str(mid) not in observed:
                continue
            resp = _af_get(AF_EVENTS.format(fx["fixture"]["id"]), key).get("response", [])
            time.sleep(6.5)
            evs = []
            for ev in resp:
                if ev.get("type") != "Card":
                    continue
                t = NAME2CODE.get(ev.get("team", {}).get("name"))
                pl = (ev.get("player") or {}).get("name")
                det = (ev.get("detail") or "").lower()
                typ = "red" if "red" in det else ("yellow" if "yellow" in det else None)
                if t and pl and typ:
                    evs.append({"team": t, "player": pl, "type": typ})
            cards[str(mid)] = evs
        except Exception as e:
            print(f"  ! kártyaadat-hiba (átugorva): {e}", file=sys.stderr)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print(f"Kártya-események: {len(cards)} meccshez van adat.")

def fetch_players_apifootball(matches, observed, key):
    """Optional: per-fixture player ratings -> data/player_form.json
    (cumulative average rating per player; each team's current top performer).
    Fail-safe; skips fixtures already harvested."""
    path = os.path.join(ROOT, "data", "player_form.json")
    raw_path = os.path.join(ROOT, "data", "player_ratings_raw.json")
    try:
        with open(raw_path, encoding="utf-8") as f:
            raw = json.load(f)
    except OSError:
        raw = {"fixtures_done": [], "players": {}}
    try:
        fixtures = _af_get(AF_FIXTURES, key).get("response", [])
    except Exception as e:
        print(f"! API-Football játékosadat nem elérhető: {e}", file=sys.stderr)
        return
    for fx in fixtures:
        try:
            fid = fx["fixture"]["id"]
            if fid in raw["fixtures_done"]:
                continue
            hn = NAME2CODE.get(fx["teams"]["home"]["name"])
            an = NAME2CODE.get(fx["teams"]["away"]["name"])
            if not hn or not an:
                continue
            resp = _af_get(AF_PLAYERS.format(fid), key).get("response", [])
            time.sleep(6.5)
            for side in resp:
                code = NAME2CODE.get(side.get("team", {}).get("name"))
                if not code:
                    continue
                for pl in side.get("players", []):
                    st = (pl.get("statistics") or [{}])[0].get("games", {})
                    rating = st.get("rating")
                    if rating is None:
                        continue
                    pid = f"{code}:{pl['player']['name']}"
                    rec = raw["players"].setdefault(pid, {"sum": 0.0, "n": 0,
                                                          "name": pl["player"]["name"],
                                                          "team": code})
                    rec["sum"] += float(rating); rec["n"] += 1
            raw["fixtures_done"].append(fid)
        except Exception as e:
            print(f"  ! játékosadat-hiba (átugorva): {e}", file=sys.stderr)
    best = {}
    for rec in raw["players"].values():
        avg = rec["sum"] / rec["n"]
        cur = best.get(rec["team"])
        if cur is None or avg > cur["rating"]:
            best[rec["team"]] = {"name": rec["name"], "rating": round(avg, 2), "n": rec["n"]}
    for p, data_ in ((raw_path, raw), (path, best)):
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data_, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    print(f"Játékos-értékelések: {len(best)} csapathoz van adat.")

def _af_get(url, key):
    req = urllib.request.Request(url, headers={"x-apisports-key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def fetch_xg_apifootball(matches, observed, key):
    """Optional second pass: fill missing xg_h/xg_a from API-Football.
    Fully fail-safe — any error skips quietly, nothing else is touched."""
    try:
        fixtures = _af_get(AF_FIXTURES, key).get("response", [])
    except Exception as e:
        print(f"! API-Football nem elérhető, xG kimaradt: {e}", file=sys.stderr)
        return
    filled = 0
    for fx in fixtures:
        try:
            hn = fx["teams"]["home"]["name"]; an = fx["teams"]["away"]["name"]
            ch, ca = NAME2CODE.get(hn), NAME2CODE.get(an)
            if not ch or not ca:
                continue
            mid, home_is_h = match_id_for(matches, ch, ca, fx["fixture"]["date"][:10])
            if mid is None or observed.get(str(mid), {}).get("xg_h") is not None:
                continue
            if str(mid) not in observed:
                continue                      # eredmény még nincs meg -> majd legközelebb
            stats = _af_get(AF_STATS.format(fx["fixture"]["id"]), key).get("response", [])
            time.sleep(6.5)
            xg = {}
            for side in stats:
                tname = side.get("team", {}).get("name")
                for st in side.get("statistics", []):
                    if st.get("type") == "expected_goals" and st.get("value") is not None:
                        xg[NAME2CODE.get(tname)] = float(st["value"])
            if ch in xg and ca in xg:
                rec = {"xg_h": xg[ch], "xg_a": xg[ca]}
                if home_is_h is False:
                    rec = {"xg_h": xg[ca], "xg_a": xg[ch]}
                observed[str(mid)] |= rec
                filled += 1
        except Exception as e:
            print(f"  ! xG-feldolgozási hiba (átugorva): {e}", file=sys.stderr)
    print(f"API-Football xG: {filled} meccs kiegészítve.")

def fetch_match_stats(api_id, token, swap):
    """Per-match statistics from the match-detail endpoint. Returns {} on miss."""
    try:
        req = urllib.request.Request(DETAIL.format(api_id), headers={"X-Auth-Token": token})
        with urllib.request.urlopen(req, timeout=30) as r:
            detail = json.load(r)
    except Exception as e:
        print(f"  ! statisztika nem elérhető (#{api_id}): {e}", file=sys.stderr)
        return {}
    out = {}
    for st in (detail.get("statistics") or []):
        key = STAT_MAP.get(st.get("type"))
        h, a = st.get("home"), st.get("away")
        if key and h is not None and a is not None:
            if swap: h, a = a, h
            out[f"{key}_h"], out[f"{key}_a"] = h, a
        if st.get("type") == "RED_CARDS" and st.get("home") is not None:
            rh, ra = st["home"], st["away"]
            if swap: rh, ra = ra, rh
            if rh: out["red_h"] = True
            if ra: out["red_a"] = True
    return out

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
    ap.add_argument("--stats", default=os.path.join(ROOT, "data", "stats_overlay.json"),
                    help="JSON overlay: {match_id: {xg_h, xg_a, ...}} — alapból a "
                         "data/stats_overlay.json, hiányzó/üres fájl némán átugorva")
    ap.add_argument("--no-details", action="store_true",
                    help="csak végeredmények, meccs-statisztikák letöltése nélkül")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    matches = load("matches.json")
    path = os.path.join(ROOT, "data", "observed.json")
    observed = load("observed.json")
    before = len(observed)

    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if token:
        try:
            data = fetch_api(token)
        except Exception as e:
            print(f"! API-hiba, az eredmény-letöltés kimaradt ebből a futásból: {e}",
                  file=sys.stderr)
            data = {"matches": []}
        for fm in data.get("matches", []):
          try:
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
            # meccs-statisztikák automatikus betöltése (csak ha még nincsenek meg)
            if not args.no_details and "sot_h" not in observed.get(str(mid), {}):
                rec |= fetch_match_stats(fm.get("id"), token, swap=(home_is_h is False))
                time.sleep(6.5)      # free tier: 10 kérés/perc
            if fm["score"].get("duration") in ("EXTRA_TIME", "PENALTY_SHOOTOUT"):
                rec["et"] = True       # 120 perc -> fáradtság-jel a pihenőszámításhoz
            w = fm["score"].get("winner")
            if w in ("HOME_TEAM", "AWAY_TEAM") and gh == ga:   # decided in ET/pens
                rec["winner_home"] = (w == "HOME_TEAM") == (home_is_h is not False)
            observed[str(mid)] = observed.get(str(mid), {}) | rec
          except Exception as e:
            print(f"  ! meccs-feldolgozási hiba (átugorva): {e}", file=sys.stderr)
    else:
        print("::warning::FOOTBALL_DATA_TOKEN nincs beállítva — az elsődleges "
              "eredményforrás kimaradt! (Settings -> Secrets -> Actions)")

    # kulcs nélküli tartalék-forrás minden futáskor
    fetch_results_github(matches, observed)

    af_key = os.environ.get("API_FOOTBALL_KEY")
    if af_key:
        fetch_xg_apifootball(matches, observed, af_key)
        fetch_players_apifootball(matches, observed, af_key)
        fetch_cards_apifootball(matches, observed, af_key)
    else:
        print("API_FOOTBALL_KEY nincs beállítva — automatikus xG kihagyva "
              "(opcionális; ingyenes kulcs: dashboard.api-football.com).")

    if args.stats and os.path.exists(args.stats):
        try:
            with open(args.stats, encoding="utf-8") as f:
                overlay = json.load(f)
            applied = 0
            for mid, st in overlay.items():
                if isinstance(st, dict):
                    observed[str(mid)] = observed.get(str(mid), {}) | st
                    applied += 1
            if applied:
                print(f"Overlay: {applied} meccs statisztikája beépítve.")
        except Exception as e:
            print(f"! Overlay-fájl hibás, kihagyva: {e}", file=sys.stderr)

    print(f"Eredmények: {before} -> {len(observed)}")
    if len(observed) == before and not token:
        print("::warning::Ebben a futásban nem érkezett új eredmény, és nincs "
              "API-token — ellenőrizd a secreteket.")
    if args.dry_run:
        print(json.dumps(observed, ensure_ascii=False, indent=1))
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(observed, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)        # atomi csere: félbeszakadt írás nem ront fájlt
    print("data/observed.json frissítve. Következő lépés: python update.py")

if __name__ == "__main__":
    main()
