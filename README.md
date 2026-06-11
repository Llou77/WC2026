# VB 2026 — ML előrejelző · World Cup 2026 Predictor

Magyar nyelvű, statikus HTML fedőoldal a 2026-os világbajnokság mind a 104
mérkőzésének előrejelzésével: 1X2-valószínűségek, a legvalószínűbb pontos
végeredmény és részletes elemzés/indoklás minden meccshez. A modell naponta,
kézi indításra, **inkrementálisan** frissül a lejátszott meccsek adataival —
a teljes újraszámolás < 1 másodperc, refit nincs.

## Gyors indítás

```bash
python update.py          # előrejelzések + index.html újragenerálása
open index.html           # (vagy GitHub Pages, lásd lent)
```

## Napi frissítési workflow (két kézi lépés)

**1. lépés — adatok betöltése** (`scripts/fetch_data.py`):

```bash
export FOOTBALL_DATA_TOKEN=...   # ingyenes kulcs: football-data.org
python scripts/fetch_data.py
# opcionális statisztika-overlay (xG, lövések) bármely forrásból:
python scripts/fetch_data.py --stats data/stats_overlay.json
```

A letöltött végeredmények (és ha van, xG) a `data/observed.json`-ba kerülnek.
Kézi szerkesztés is teljes értékű fallback — séma meccsazonosítónként:

```json
{ "1": {"gh": 2, "ga": 0, "xg_h": 1.9, "xg_a": 0.4} }
```

(A meccsazonosítók a `data/matches.json`-ban; 1–72 csoportkör, 73–104 kieséses
szakasz a hivatalos FIFA-számozással. Kieséses meccsnél döntetlen
végeredemény + hosszabbításos/tizenegyeses továbbjutó: `"winner_home": true/false`.)

**2. lépés — újraszámolás + render** (`update.py`):

```bash
python update.py
```

GitHubon ugyanez a két lépés a **Actions** fül alatt kézzel indítható
(`workflow_dispatch`): *„1 - Adatok betoltese"* majd *„2 - Modell
ujraszamolas + oldal"*. A `FOOTBALL_DATA_TOKEN`-t repo secretként kell
felvenni. GitHub Pages-t a repo gyökerére irányítva az `index.html` azonnal
publikus.

## Hogyan számol a modell?

Részletes módszertan: **[MODEL.md](MODEL.md)** — bemenetek, képletek, feltételezések, korlátok. Rövid összefoglaló:

- **Erősség**: csapatonkénti Elo (kiindulás: eloratings.net, 2026-06-11),
  meccsenkénti inkrementális frissítéssel (K=50, gólkülönbség-súlyozott),
  plusz hazai bónusz a rendező országoknak saját helyszínen.
- **Forma-finomhangolás**: támadó/védő szorzók, amelyek a tornán mutatott
  teljesítményből tanulnak — ha van xG, a gólok és az xG 70/30 keveréke a
  jel, így egy szerencsés 1-0 kevésbé torzít.
- **Eredmény-eloszlás**: a várható gólszámokból Poisson-rács (Dixon–Coles
  jellegű döntetlen-korrekcióval) → 1X2 % és a legvalószínűbb pontos eredmények.
- **Kieséses szakasz**: a párosítások a valós tabellákból töltődnek fel; amíg
  egy csoport nincs lezárva, *vetített* (várható pont alapú) résztvevők
  szerepelnek, megjelölve. Döntetlen-tipp esetén a modell hosszabbítás +
  tizenegyesek figyelembevételével **mindig kijelöl továbbjutó-esélyest**.
- A harmadik helyezettek ágra sorolása a FIFA Annex C (495 kombináció)
  érvényes közelítése; a valós sorsolási tábla ettől eltérhet, a tényleges
  párosítást az eredmény-betöltés úgyis rögzíti.

## Fájlszerkezet

```
index.html              ← a generált fedőoldal (GitHub Pages-kész)
update.py               ← 2. lépés: újraszámolás + render
scripts/fetch_data.py   ← 1. lépés: eredmények betöltése
scripts/seed_data.py    ← kiinduló adatok újragenerálása (csak ha elromlana)
data/teams.json         ← 48 csapatprofil (Elo, játékosok, stílus, "news" mező)
data/matches.json       ← 104 meccs menetrendje
data/observed.json      ← lejátszott meccsek adatai (a fetch írja / kézzel is)
data/predictions.json   ← gépi olvasásra szánt kimenet
model/ , render/        ← modell és oldalgenerátor
.github/workflows/      ← a két kézi indítású GitHub Action
```

**Napi hír beépítése:** a `data/teams.json` adott csapatának `news` mezőjébe
írt szöveg (sérülés, eltiltás, öltözői hír) a következő `update.py` futáskor
automatikusan bekerül az érintett meccsek elemzésébe. A keményebb hatást
(pl. kulcsjátékos kiesése) az Elo kézi, kommentált módosításával lehet
érvényesíteni.

## Korlátok — őszintén

- A futball nagy szórású: a "legvalószínűbb pontos eredmény" tipikusan
  8–13% valószínűségű. A modell kalibrált esélyeket ad, nem jóslatot.
- A becsültként jelölt (`elo_estimated: true`) kiinduló Elo-értékek
  konzervatív közelítések; az első 1–2 forduló után a frissítések gyorsan
  korrigálják őket.
- Nem hivatalos rajongói projekt, a FIFA-tól független; szerencsejáték-célú
  felhasználásra nem alkalmas.
