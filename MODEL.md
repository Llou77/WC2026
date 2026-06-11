# MODEL.md — A predikciós módszertan dokumentációja

Ez a dokumentum azt rögzíti, hogy a VB 2026 előrejelző **pontosan mi alapján
hozza meg a predikcióit**: milyen bemenetekből, milyen matematikai lépéseken
keresztül, milyen feltételezésekkel és milyen ismert korlátokkal.

---

## 1. Bemeneti adatok

| Bemenet | Forrás | Szerep |
|---|---|---|
| Kiinduló Elo-erősség (48 csapat) | eloratings.net, 2026-06-11-i snapshot; ~30 csapatnál konzervatív becslés (`elo_estimated: true`) | A csapaterősség alapmutatója |
| Mérkőzés-végeredmények | football-data.org API / kézi bevitel (`data/observed.json`) | Az inkrementális frissítés elsődleges jele |
| xG és meccsstatisztikák (opcionális) | tetszőleges forrás, overlay-fájlként | A gólszám zaját csökkentő teljesítményjel |
| Menetrend, helyszín, rendező ország | hivatalos menetrend (`data/matches.json`) | Pályaelőny és ágrajz-feloldás |
| Csapatprofilok: kulcsjátékosok, játékstílus, `news` mező | szerkeszthető (`data/teams.json`) | Az elemzésszöveg kvalitatív rétege; a `news` kézzel frissíthető |

Fontos elhatárolás: a **számszerű predikciót** (1X2, várható eredmény) kizárólag
a kvantitatív bemenetek határozzák meg (Elo, eredmények, xG, pályaelőny).
A profilszövegek és hírek az **elemzés magyarázó rétegét** adják, a
valószínűségeket közvetlenül nem módosítják — kemény hírhatás (pl. kulcsjátékos
sérülése) az Elo kézi, dokumentált korrekciójával érvényesíthető.

## 2. Csapaterősség: inkrementális Elo

Minden lejátszott mérkőzés után a két érintett csapat Elo-pontszáma frissül —
kizárólag az övék, ezért a művelet meccsenkénti költsége O(1), batch-refit nincs.

Győzelmi várakozás a meccs előtt:

```
E = 1 / (1 + 10^(−(Elo_hazai + B − Elo_vendég) / 400))
```

ahol `B = 80` pályaelőny-bónusz, kizárólag akkor, ha a rendező ország
(Mexikó / USA / Kanada) a saját országában lévő stadionban játszik.

Frissítés:

```
ΔElo = K · G · (W − E)
K = 50                         (világbajnoki súly, eloratings.net-konvenció)
W = 1 / 0.5 / 0  (győzelem / döntetlen / vereség)
G = 1   ha a gólkülönbség ≤ 1
    1.5 ha a gólkülönbség = 2
    (11 + gk) / 8  ha a gólkülönbség ≥ 3
```

A gólkülönbség-súlyozás miatt egy 4–0 jobban átrendezi az erősorrendet, mint
egy 1–0.

**Adaptív tanulási sebesség:** a becsült kiinduló Elo-jú csapatok
(`elo_estimated: true`) első 3 mérkőzésén K=85 érvényes K=50 helyett — a
bizonytalan kiindulópont így a csoportkör elején gyorsabban korrigálódik,
a megbízhatóan bemért csapatok stabilitása pedig megmarad.

## 3. Tornaforma: támadó- és védekező-szorzók (xG-kevert)

Az Elo lassan mozgó, eredményalapú mutató; a tornán mutatott *játékminőséget*
két csapatonkénti szorzó ragadja meg (`att`, `def`, kiindulás: 1.0).

Teljesítményjel meccsenkként, ha van xG:

```
perf = 0.7 · gólok + 0.3 · xG
```

xG hiányában `perf = gólok`. A 70/30 keverés célja a szerencsekomponens
tompítása: egy 1–0-s győzelem 0.3 xG-vel kevésbé erősíti a támadóértéket,
mint ugyanaz 2.5 xG-vel.

Frissítés a meccs előtti várakozáshoz képest:

```
ratio  = (perf + 0.5) / (λ_várt + 0.5)         (+0.5: kis minták simítása)
att    ← clip( att · ratio^0.35 , 0.70 , 1.40 )
def_ellenfél ← clip( def · ratio^0.21 , 0.70 , 1.40 )
```

A kitevők (tanulási ráták) szándékosan óvatosak: 1–3 meccsnyi minta áll
rendelkezésre csapatonként, a túltanulás nagyobb kockázat, mint az alultanulás.

## 4. Várható gólszámok

A meccs előtti Elo-különbségből (`dr`, pályaelőnnyel együtt):

```
várható gólkülönbség  gd    = clip(dr / 160, −2.5, +2.5)
várható összgólszám   total = 2.80 + 0.45 · |gd|
λ_hazai  = max(0.15, (total + gd) / 2) · att_hazai  · def_vendég
λ_vendég = max(0.15, (total − gd) / 2) · att_vendég · def_hazai
```

A 160-as skála és a 2.80-as gólalap **backtesten hangolt** érték (lásd 9. pont
és backtest/REPORT.md); a `0.45·|gd|` tag azt a megfigyelést kódolja, hogy a
nagy erőkülönbségű meccsek összgólszáma magasabb.

## 5. Eredmény-eloszlás: Poisson-rács Dixon–Coles-korrekcióval

A két λ-ból független Poisson-feltevéssel 9×9-es pontszám-rács készül
(0–8 gólig), majd a futballban empirikusan megfigyelt alacsony-gólszámú
korreláció miatt korrekció:

```
P(0–0), P(1–1)  × 1.15        P(1–0), P(0–1)  × 0.97
```

ezután a rács újranormálódik. Ebből származik minden kimeneti mutató:

- **1X2-valószínűségek**: a rács felső háromszöge / átlója / alsó háromszöge,
- **legvalószínűbb pontos végeredmény**: a rács módusza (top-3 megjelenítve),
- a várható gólszám-pár az elemzés indoklásában.

## 6. Kieséses szakasz

- **Ágfeltöltés**: a 73–104. mérkőzés résztvevői a tényleges tabellákból
  oldódnak fel. Amíg egy csoport nincs lezárva, a tabella *várható ponttal*
  egészül ki (`3·P(győzelem) + P(döntetlen)` a hátralévő meccsekre), és a
  párosítás **„vetített"** jelölést kap.
- **Harmadik helyezettek**: a 12 harmadikból a legjobb 8 jut tovább (pont,
  gólkülönbség, lőtt gól); ágra sorolásuk a FIFA Annex C 495 kombinációjának
  érvényes, backtracking-alapú közelítése. A tényleges FIFA-hozzárendelés
  ettől eltérhet — a betöltött valós eredmény ezt mindig felülírja.
- **Kötelező továbbjutó**: kieséses meccsen a döntetlen valószínűségi tömege
  szétosztásra kerül a két fél között a hosszabbítás/tizenegyes-fázisra
  kalibrált aránnyal:

```
ET-arány = 0.5 + (E − 0.5) · 0.33
P(továbbjutás_hazai) = P(győzelem 90 perc) + P(döntetlen) · ET-arány
```

  A 0.33-as zsugorítás 541 valós tizenegyespárbajból kalibrált érték: a
  magasabb Elo-jú fél a párbajok mindössze 53,8%-át nyeri, a hosszabbításban
  pedig mérsékelt az erőérvényesülés (részletek: backtest/REPORT.md). Így a modell döntetlen-tipp esetén is mindig megjelöli a
  továbbjutásra esélyesebb felet.

## 7. Az elemzésszöveg felépítése

Minden mérkőzéshez determinisztikusan generált, hat blokkból álló elemzés
készül: (1) erőviszony-értékelés az Elo-különbség sávja szerint,
(2) játékkép mindkét oldalról, (3) meghatározó játékosok, (4) tornaforma a
feldolgozott eredményekből, (5) csoporthelyzet / keretinformációk és
aktualitások (`news` mező), (6) modellverdikt: 1X2 %, top-3 végeredmény és a
számszerű indoklás. A sablonválasztás a mérkőzés-azonosítóhoz kötött, ezért a
kimenet reprodukálható, újrafuttatáskor nem változik.

## 8. Feltételezések és ismert korlátok

0. **Validáció**: a modell valós történelmi adaton visszamérve és hangolva —
   a 2022-es VB + 2024-es Eb/Copa független holdoutján Brier-score 0.6218
   (uniform: 0.6667), log-loss 1.0499. Protokoll és részletek:
   `backtest/REPORT.md`, újrafuttatás: `python backtest/backtest.py`.
1. **Nagy szórás**: a futballmeccs alacsony gólszámú, nagy zajú folyamat; a
   legvalószínűbb pontos eredmény tipikus valószínűsége 8–13%. A modell
   kalibrált eloszlást ad, nem determinisztikus jóslatot.
2. **Becsült kiinduló Elo-k**: az `elo_estimated: true` jelölésű csapatoknál
   a kiindulópont közelítés; az első fordulók frissítései gyorsan korrigálják.
3. **Függetlenségi feltevés**: a Poisson-rács a két csapat gólszámát a
   DC-korrekción túl függetlennek tekinti; taktikai forgatókönyveket
   (eredménytartás, emberhátrány) nem modellez.
4. **Hírek hatása**: a `news` mező csak az elemzésszövegben jelenik meg;
   számszerű hatás kézi Elo-korrekcióval vihető be.
5. **Annex C-közelítés**: a harmadikok ágra sorolása érvényes, de nem
   garantáltan a FIFA által választott hozzárendelés (lásd 6. pont).
6. **Csoportrangsor**: a sorrend pont → gólkülönbség → lőtt gól → **egymás
   elleni eredmény** (pont, gólkülönbség, lőtt gól a holtversenyben állók
   egymás elleni meccsein) a FIFA-szabálykönyv szerint; a fair play-rangsor
   mint utolsó előtti tiebreaker nincs implementálva, teljes holtversenynél
   determinisztikus (a Monte Carlóban sorsolásos) feloldás következik.

## 9. Monte Carlo tornaszimuláció

Az „Esélyek" fül értékei 10 000 teljes torna-szimulációból származnak
(`model/simulate.py`, `update.py --sims=N` paraméterrel állítható). Futásonként:
a még le nem játszott csoportmeccsek eredménye a meccs Poisson/DC-rácsából
sorsolódik, a tabellák (pont → gólkülönbség → lőtt gól → sorsolás) és a
legjobb nyolc harmadik ágra sorolása feloldódik, a kieséses kör a kalibrált
hosszabbítás/tizenegyes-modellel játszódik le. A már rögzített eredmények
minden futásban változatlanok, így a frissítésekkel az eloszlások fokozatosan
szűkülnek. A kimenet csapatonként: P(csoportgyőzelem), P(32 között),
P(nyolcaddöntő) … P(döntő), P(világbajnoki cím) — a továbbjutási
valószínűség a csoporttabellák „Tovább%" oszlopában is megjelenik. A
szimulátor emellett minden kieséses mérkőzésre rögzíti az egyes párosítások
előfordulási gyakoriságát; a vetített kártyákon ezért szerepel, hogy az adott
párosítás a szimulációk hány százalékában jön létre.
