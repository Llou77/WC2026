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
| Lövés, kapura lövés, piros lap, szöglet | football-data.org match-detail endpoint — **automatikusan letöltődik** a fetch lépésben | xG-proxy és eredmény-diszkont |
| xG (opcionális) | tetszőleges forrás, overlay-fájlként | A legerősebb teljesítményjel, felülírja a proxyt |
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

ahol `B = 65` pályaelőny-bónusz (backtesten hangolt), kizárólag akkor, ha a rendező ország
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

Teljesítményjel meccsenkként, jelhierarchiával:

```
exg  = xG, ha elérhető
       0.30 · kaput eltaláló lövés + 0.03 · mellé menő lövés, ha csak lövésadat van
perf = 0.7 · gólok + 0.3 · exg        (statisztika híján: perf = gólok)
```

A 70/30 keverés célja a szerencsekomponens tompítása: egy 1–0-s győzelem
0.3 xG-vel kevésbé erősíti a támadóértéket, mint ugyanaz 2.5 xG-vel. A
lövésalapú proxy súlyai szakirodalmi átlagok (≈0.30 gól/kapura lövés) —
történelmi lövésadat híján backtesten nem validálhatók, ezért becslésként
kezelendők. Piros lapos mérkőzésnél az Elo-frissítés gólkülönbség-szorzója
0.8-szorosára csökken: az emberelőnyben kialakult eredmény kevésbé
informatív a valós erőviszonyokról. A labdabirtoklást tudatosan **nem**
használja a modell: a lövésadatok mellett a birtoklás prediktív többletértéke
a kutatások szerint elhanyagolható, esetenként félrevezető.

Frissítés a meccs előtti várakozáshoz képest — **kizárólag akkor, ha van
xG-szerű jel** (valódi xG vagy lövés-proxy):

```
ratio  = (perf + 0.5) / (λ_várt + 0.5)         (+0.5: kis minták simítása)
att    ← clip( att · ratio^0.25 , 0.70 , 1.40 )
def_ellenfél ← clip( def · ratio^0.15 , 0.70 , 1.40 )
```

A csak-gól-alapú adaptáció a v2 kísérletsorozatban (backtest/REPORT.md, E2)
mérhetően rontotta a pontosságot, ezért ki van kapcsolva: statisztika nélkül a
meccs hatása kizárólag az Elo-frissítésen át érvényesül. Az xG-úton a réteg
konzervatív rátával él tovább (történelmi xG híján ez az ág nem mérhető).

## 4. Várható gólszámok

A meccs előtti Elo-különbségből (`dr`, pályaelőnnyel együtt):

```
várható gólkülönbség  gd    = clip( sign(dr) · |dr/200|^0.85 , −2.5, +2.5 )
várható összgólszám   total = 2.5 + 0.2 · |gd|
λ_hazai  = max(0.15, (total + gd) / 2) · att_hazai  · def_vendég
λ_vendég = max(0.15, (total − gd) / 2) · att_vendég · def_hazai
```

A szublineáris (0.85 kitevős) leképezés és minden együttható **backtesten hangolt v2** érték (lásd a 8. pont
validációs blokkját és a backtest/REPORT.md-t); a `0.45·|gd|` tag azt a megfigyelést kódolja, hogy a
nagy erőkülönbségű meccsek összgólszáma magasabb.

## 5. Eredmény-eloszlás: Poisson-rács Dixon–Coles-korrekcióval

A két λ-ból független Poisson-feltevéssel 9×9-es pontszám-rács készül
(0–8 gólig), majd a futballban empirikusan megfigyelt alacsony-gólszámú
korreláció miatt korrekció:

```
P(0–0), P(1–1)  × 1.25        P(1–0), P(0–1)  × 0.97
```

ezután a rács újranormálódik. (A szabályos, ρ-paraméteres Dixon–Coles-tau
formát is megmértük: a train/holdout metrikákon zajon belül azonos a flat
korrekcióval — backtest/REPORT.md —, ezért az egyszerűbb, holdouton hajszállal
jobb flat változat maradt élesben; a `DC_RHO` paraméter a kódban elérhető.)

**Megjegyzés a kivezetett meta-learnerről:** a v1 modell egy softmax-blend
rekalibráló réteget használt (0.6218→0.5977 holdout-javulással). A v2
kísérletsorozat kimutatta, hogy az újrahangolt gólmodell mellett a keverék már
semmit nem ad hozzá (a nyereség a gyengébb alapparaméterek kompenzációja volt),
ezért a réteg ki lett vezetve — a kód (`calibrated_grid`) megtartja a
fogadókészséget, ha a `data/blend.json` valaha visszakerülne. Részletek:
backtest/REPORT.md. A rácsból származik minden kimeneti mutató (kiegészítve a „mindkét csapat szerez gólt" és a 2,5 gól feletti
összgólszám valószínűségével):

- **1X2-valószínűségek**: a rács felső háromszöge / átlója / alsó háromszöge,
- **tipp (várható végeredmény)**: a legvalószínűbb 1X2-kimenetel, és **azon
  belül** a legvalószínűbb pontos eredmény. Ez tudatos szemantikai döntés: a
  rács nyers módusza egy ~60%-os esélyesnél is gyakran 1–1, mert a
  győzelem-tömeg sok eredmény közt oszlik szét, a döntetlené kevés közt — a
  kimenetel-osztállyal konzisztens tipp ezt a félrevezető összegzést szünteti
  meg. Az eloszlás top-3 cellája (a nyers módusszal) az elemzésben továbbra is
  szerepel,
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

Minden mérkőzéshez determinisztikusan generált, nyolc blokkból álló elemzés
készül: (1) erőviszony-értékelés az Elo-különbség sávja szerint,
(2) játékkép mindkét oldalról, (3) meghatározó játékosok, (3b) előzmények és
felkészülés — a teljes történelmi adattárból (backtest/results.csv)
automatikusan számolt egymás elleni mérleg (utolsó találkozóval) és a torna
előtti 8 mérkőzés formája —, (4) párharc-kép
(vonal-aszimmetria, tornán mért csatorna-statisztikák, a torna legjobbra
értékelt játékosai — lásd 9. pont), (5) tornaforma a feldolgozott
eredményekből, (6) csoporthelyzet / keretinformációk és aktualitások
(`news` mező), (7) modellverdikt: 1X2 %, top-3 végeredmény és a számszerű
indoklás. A sablonválasztás a mérkőzés-azonosítóhoz kötött, ezért a
kimenet reprodukálható, újrafuttatáskor nem változik.

## 8. Feltételezések és ismert korlátok

0. **Validáció**: a modell valós történelmi adaton visszamérve és kétkörösen
   hangolva — a 2022-es VB + 2024-es Eb/Copa holdoutján a v2 modell
   Brier-score-ja **0.5894** (v1: 0.5977, uniform: 0.6667), a pontos
   eredmények GoalNLL-je **2.77** (v1 gólmodell: ~2.89). A torna-K és a
   gólkülönbség-súlyozás formája a harness szerkezete miatt nem validálható —
   ezek konvenció szerinti értéken állnak. Protokoll és részletek:
   `backtest/REPORT.md`, újrafuttatás: `python backtest/backtest.py`.
1. **Nagy szórás**: a futballmeccs alacsony gólszámú, nagy zajú folyamat; a
   legvalószínűbb pontos eredmény tipikus valószínűsége 8–13%. A modell
   kalibrált eloszlást ad, nem determinisztikus jóslatot.
2. **Becsült kiinduló Elo-k**: az `elo_estimated: true` jelölésű csapatoknál
   a kiindulópont közelítés; az első fordulók frissítései gyorsan korrigálják.
3. **Függetlenségi feltevés**: a Poisson-rács a két csapat gólszámát a
   DC-korrekción túl függetlennek tekinti; taktikai forgatókönyveket
   (eredménytartás, emberhátrány) nem modellez.
4. **Hírek hatása**: a `news` mező szabad szövege csak az elemzésben jelenik
   meg. Strukturált, számszerű hiányzás-hatás a `teams.json` `out` mezőjén át
   vihető be (lásd 8b — eltiltás/hiányzás-csatorna).
5. **Annex C-közelítés**: a harmadikok ágra sorolása érvényes, de nem
   garantáltan a FIFA által választott hozzárendelés (lásd 6. pont).
6. **Csoportrangsor**: a sorrend pont → gólkülönbség → lőtt gól → **egymás
   elleni eredmény** (pont, gólkülönbség, lőtt gól a holtversenyben állók
   egymás elleni meccsein) a FIFA-szabálykönyv szerint; a fair play-rangsor
   mint utolsó előtti tiebreaker nincs implementálva, teljes holtversenynél
   determinisztikus (a Monte Carlóban sorsolásos) feloldás következik.

## 8b. Fordulóprofil, „biztos sors", eltiltás-követés

**Fordulóprofil:** a csoportmeccsek gólvárakozása fordulófüggő offszetet kap
(1. forduló −0.35, 2. −0.05, 3. −0.25) — a nagytornák nyitófordulói mérten
óvatosabbak (backtest/REPORT.md, E9). A kieséses meccsek offszet nélkül futnak.

**„Biztos sors"-levonás:** a 3. forduló előtt pont-alapú kimerítéses
vizsgálat dönti el, kinek biztos már a top-2 helye vagy a kiesése; az ilyen
csapatok 25 Elo-pontos levonást kapnak az adott meccsre (mért rotációs/
motivációs hatás, E8). Az elemzés jelzi, ha a levonás aktív.

**Magaslati előny:** a Mexikóvárosban (2240 m) és Guadalajarában (1566 m)
játszott meccseken a magaslathoz szokott válogatottak (Mexikó, Ecuador,
Kolumbia, Bolívia, Peru) akklimatizációs előnyt kapnak tengerszinti
ellenfelükkel szemben (McSharry, BMJ 2007). A mérték a saját adatunkon mért
konzervatív +0.07 gól/1000 m (a backtest/REPORT.md részletezi, miért nem az
irodalmi +0.5-öt használjuk); az előny a gólvárakozásban jelenik meg, és csak
akkor aktív, ha a két csapat magaslati adaptáltsága eltér.

**Automatikus eltiltás-követés + kézi hiányzás-csatorna:** a kártya-események
játékos-szinten töltődnek (API-Football, `data/cards.json`); piros lap, illetve
két halmozott sárga a következő mérkőzésre eltiltást jelent (egyszerűsített
FIFA-szabály; a sárgák negyeddöntő utáni törlése kézzel kezelendő). Az
eltiltottak/hiányzók listája az elemzésbe kerül, **és a valószínűségeket is
mozgatja** Elo-levonáson keresztül:

- eltiltott **kulcsjátékos** (a `players` listában): −25 Elo;
- eltiltott, de **nem listás** játékos: −12 Elo (korábban 0 volt — egy
  eltiltott kezdő sem „ingyenes");
- **kézi hiányzás** a `teams.json` `out` mezőjéből (sérülés, késői kiesés):
  `"out": ["Név"]` → default −25 Elo, vagy `{"name":"Név","elo":30}` explicit
  súllyal; ez nem függ a kulcsjátékos-listától.

A levonások játékosonként összegződnek (egy játékos több ok esetén sem
duplázódik — a legnagyobb súly számít), csapatonként legfeljebb −60 Elo-ig.
Mindezek heurisztikus, egy helyen (`ratings.py`) hangolható értékek: a torna
előtti adatban nincs per-játékos hiányzás-címke, így a harness-ben **nem
backtestelhetők** — a lefedettséget és a szöveg↔szám konzisztenciát javítják,
nem a hitelesített kalibrációt.

## 9. Párharc-réteg és játékos-szintű adatok

**Pozicionális erősség-mátrix** (`data/lineups.json`, szerkeszthető becslések):
csapatonként [kapus, védelem, középpálya, támadósor] 1–10 skálán. A modell
minden csapat vonalait a **saját átlagához centírozza**, így kizárólag a
profil-aszimmetria számít — az össz-erőt az Elo árazza, a kettős számolás így
kizárt. A gólvárakozás-korrekció: `1 + 0.035 · (támadósor′ − (védelem′+kapus′)/2
+ 0.3·középpálya-különbség′)`, **±10%-ra sapkázva**. Történelmi vonal-adat
híján ez a réteg backtesten nem validálható; az együtthatók konzervatív
heurisztikák, az effektus szándékosan korlátos.

**Csatorna-profilok (automatikus):** a betöltött meccs-statisztikákból
csapatonként tornaátlag képződik (kapura lövés és szöglet, mindkét irányban);
ez az elemzések „Párharc-kép" bekezdését táplálja, a számokat közvetlenül nem
mozgatja — 1–3 meccses mintán numerikus súlyt adni neki túlilleszkedés lenne.

**Játékos-szintű értékelések (automatikus, opcionális):** API-Football-kulccsal
a fetch meccsenkként letölti a játékos-osztályzatokat, halmozott átlagot vezet
(`data/player_ratings_raw.json`), és csapatonként a torna legjobbra értékelt
játékosát az elemzésbe emeli (`data/player_form.json`). Numerikus hatása nincs
— a tornaminta ehhez túl kicsi —, a kvalitatív réteg viszont meccsre lebontva
frissül.

## 10. Megbízhatósági címkék, pihenőnap-hatás, önellenőrzés

**Megbízhatóság (confidence):** minden előrejelzés címkét kap (MAGAS / KÖZEPES /
ALACSONY) — az NFL-predikciós projektből adaptált pontszám alapján:
`0.55 · jel-erősség (a két legvalószínűbb kimenet közti rés) + 0.30 ·
adatminőség (büntetés, ha valamelyik fél Elo-ja még becsült és <3 meccses) +
0.15 · tornaminta (a két csapat lejátszott meccseinek száma)`. A címke nem
módosítja a valószínűségeket, hanem azt jelzi, mennyire stabil lábakon állnak.

**Pihenőnap-differencia (kieséses szakasz):** a két csapat előző mérkőzése óta
eltelt napok különbsége kis Elo-korrekciót ad (8 pont/nap, ±24 pontra vágva) —
heurisztikus együttható, a csoportkörben nem aktív, mert ott a terhelés
kiegyenlített. **Hosszabbítás-fáradtság:** ha egy csapat előző kieséses meccse
120 percig tartott (a fetch a `duration` mezőből jelöli, tartalékként a
döntetlen végeredmény jelzi), az effektív pihenője egy nappal csökken — a
+30 perc terhelés tapasztalati ökölszabály szerinti beárazása.

**Önellenőrzés:** minden lejátszott meccsnél eltárolódik a meccs előtti
predikció, és a frissítés futtatja a visszamérést: 1X2-találati arány, pontos
eredmény-találat, átlagos Brier (`data/performance.json` + a fejléc
összefoglaló sora). Így a torna alatt folyamatosan látszik, hogyan teljesít a
modell éles adaton — a corners-projekt eredmény-ellenőrző mintájára.

## 11. Monte Carlo tornaszimuláció

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
