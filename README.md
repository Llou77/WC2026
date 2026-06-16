# VB 2026 — ML előrejelző · World Cup 2026 Predictor

Magyar nyelvű, statikus HTML fedőoldal a 2026-os világbajnokság mind a 104
mérkőzésének előrejelzésével: 1X2-valószínűségek, a legvalószínűbb pontos
végeredmény, Monte Carlo-tornaesélyek és részletes elemzés minden meccshez.
A modell két kézi gombnyomásra (fetch → update) frissül; minden adatbetöltés,
számítás és publikálás automatikus és hibabiztos. A teljes újraszámolás
10 000 tornaszimulációval együtt ~3 másodperc.

**Pontosság (független holdouton — VB 2022 + Eb/Copa 2024):** Brier 0.5894
(uniform tipp: 0.6667). Részletek: [backtest/REPORT.md](backtest/REPORT.md).

## Napi munkafolyamat (2 gombnyomás)

GitHubon: **Actions → „1 - Adatok betoltese (kezi)"** → lefutás után
**„2 - Modell ujraszamolas + oldal (kezi)"**. Lokálisan ugyanez:

```bash
python scripts/fetch_data.py   # eredmények + statisztikák + xG + játékosadatok
python update.py               # újraszámolás + index.html (+ --sims=N opció)
```

A workflow-k hibabiztosak: API-kimaradás, hibás adat vagy hiányzó fájl
figyelmeztetést ad, de a futás zölden végigmegy a meglévő adatokkal.

## Egyszeri beállítás

1. **Secretek** (Settings → Secrets and variables → Actions):
   - `FOOTBALL_DATA_TOKEN` — kötelező; ingyenes kulcs: football-data.org.
     Eredmények + lövés/szöglet/piroslap statisztikák forrása.
   - `API_FOOTBALL_KEY` — opcionális; ingyenes kulcs: dashboard.api-football.com.
     Automatikus xG és játékos-értékelések forrása. Nélküle ezek a rétegek
     némán kimaradnak, minden más változatlanul működik.
2. **GitHub Pages**: Settings → Pages → Deploy from a branch → main / (root).

## Mi mit csinál (adatfolyam)

```
fetch_data.py
 ├─ football-data.org ─ végeredmények, ET/tizenegyes-továbbjutó
 ├─ football-data.org match-detail ─ lövés, kapura lövés, szöglet, piros lap
 ├─ API-Football ─ xG + játékosonkénti osztályzatok (opcionális kulccsal)
 └─ data/stats_overlay.json ─ kézi felülíró réteg (pl. pontosított xG)
        ↓  data/observed.json (+ player_form.json, player_ratings_raw.json)
update.py
 ├─ inkrementális Elo (adaptív K a becsült csapatoknál) + xG-kevert att/def
 ├─ Poisson-rács + Dixon–Coles (v2, backtesten hangolt alak)
 ├─ párharc-réteg (data/lineups.json, centírozott, ±10% sapka)
 ├─ tabellák (FIFA-tiebreakerekkel) + kieséses ág feloldása
 ├─ 10 000 Monte Carlo-tornaszimuláció (Esélyek fül, Tovább%, párosítás-%)
 ├─ önellenőrzés (data/performance.json + fejléc-sor)
 └─ index.html újragenerálása
```

A teljes módszertan képletekkel, validációval és korlátokkal:
**[MODEL.md](MODEL.md)**.

## Kézi adatbevitel (opcionális rétegek)

**Eredmény/statisztika kézzel** — `data/observed.json`, meccsazonosítónként
(1–72 csoportkör, 73–104 kieséses, FIFA-számozás):

```json
"5": {"gh":2, "ga":1, "xg_h":1.8, "xg_a":0.9, "sot_h":7, "sot_a":3,
      "shots_h":15, "shots_a":9, "red_a":true, "et":true, "winner_home":true}
```

Minden mező opcionális a `gh`/`ga` páron kívül; `et` = 120 percig tartott
(fáradtság-jel), `winner_home` = döntetlen utáni továbbjutó kieséses meccsen.

**xG-pontosítás** — `data/stats_overlay.json` ugyanezzel a sémával; a fetch
minden futáskor automatikusan ráteríti az API-adatokra.

**Hírek + hiányzók** — `data/teams.json`:
- `news` (szabad szöveg): az elemzésekbe kerül, számot nem mozdít.
- `out` (strukturált hiányzás — sérülés, késői kiesés): **a valószínűségeket
  is mozgatja**. Formátum: `"out": ["Pedri"]` (default −25 Elo) vagy súllyal
  `"out": [{"name":"Pedri","elo":40}]`. Az eltiltások a `cards.json`-ból
  automatikusan jönnek; az `out` a kártyával nem detektálható hiányzásokra van.
  Csapatonkénti plafon −60 Elo; a magnitúdók a `model/ratings.py` tetején
  hangolhatók (nem backtestelt heurisztika).

**Erősség-profilok** — `data/lineups.json`: csapatonként
[kapus, védelem, középpálya, támadás] 1–10; becslések, szabadon átírhatók.

## Fájlszerkezet

```
index.html                  ← a generált oldal (GitHub Pages-kész)
update.py                   ← 2. lépés: újraszámolás + render
scripts/fetch_data.py       ← 1. lépés: adatbetöltés (3 forrás + overlay)
scripts/seed_data.py        ← kiinduló adatok újragenerálása (vész esetére;
                              felülírja a teams/matches fájlokat!)
data/teams.json             ← 48 csapatprofil (Elo, játékosok, news)
data/lineups.json           ← pozicionális erősség-mátrix (szerkeszthető)
data/matches.json           ← 104 meccs menetrendje
data/observed.json          ← lejátszott meccsek adatai (generált + kézi)
data/stats_overlay.json     ← kézi statisztika-felülírás
data/predictions.json       ← gépi kimenet (predikciók + Monte Carlo)
data/performance.json       ← élő megbízhatóság (Brier, skill, log-loss, kalibráció)
data/player_form.json       ← csapatonkénti legjobb játékos (generált)
model/ render/              ← modell és oldalgenerátor
backtest/                   ← validáció + kalibráció (REPORT.md, újrafuttatható)
.github/workflows/          ← a két kézi indítású Action
```

## Korlátok — őszintén

A futball nagy szórású: a legvalószínűbb pontos eredmény tipikusan 8–13%
valószínűségű; a modell kalibrált eloszlást ad, nem jóslatot. A párharc-réteg
és a pihenő/fáradtság-korrekciók heurisztikák (backtesten nem validálhatók),
hatásuk szándékosan sapkázott. Nem hivatalos rajongói projekt, a FIFA-tól
független; szerencsejáték-célú felhasználásra nem alkalmas.
