# Backtest-jelentés (2026-06-11)

## Protokoll
- Adat: martj42/international_results — 49 405 lejátszott válogatott mérkőzés (1872–2026).
- Elo-felépítés a teljes történelmen, tornasúlyozott K-val (VB 60, kontinenstorna 50,
  selejtező 40, barátságos 20), +80 hazai bónusz nem semleges pályán.
- TRAIN (paraméter-hangolás): VB 2010/14/18, Eb 2012/16/21, Copa 2011/15/16/19/21.
- HOLDOUT (érintetlen teszt): VB 2022 + Eb 2024 + Copa 2024 — 147 mérkőzés.
- A tornán belüli támadó/védő-frissítés (gól-alapú ág) a kiértékelésben is futott,
  tehát a teljes éles predikciós út lett mérve, nem csak a nyers Elo.

## Eredmények (multiclass Brier; alacsonyabb = jobb; uniform 1/3 = 0.6667)

| Modell | Holdout Brier | Holdout log-loss |
|---|---|---|
| Uniform 1/3 | 0.6667 | 1.0986 |
| Alap paraméterek (hangolás előtt) | 0.6275 | 1.0623 |
| **Hangolt (élesített)** | **0.6218** | **1.0499** |

Hangolt paraméterek (két lépcsős grid search, a train-en választva):
`GD_SCALE=160` (volt: 120), `DC_DRAW_BOOST=1.15` (volt: 1.08),
`TOTAL_GOALS_BASE=2.80` (volt: 2.55).

Értelmezés: a 120-as gólkülönbség-skála túl magabiztos volt — a 160-as skála
óvatosabb gólkülönbség-várakozást ad ugyanakkora Elo-résre, ami a holdouton
mérhetően jobb kalibrációt eredményez. A magasabb gólalap a modern tornák
tényleges gólátlagát követi.

## Szétlövés-kalibráció
541 értékelhető tizenegyespárbaj (ahol az Elo-különbség > 25 pont):
a magasabb Elo-jú csapat csak **53,8%-ban** nyert — a párbaj közel érmefeldobás.
A 90 perc utáni döntetlen-tömeg megosztása ezért kevert zsugorítást kapott:
~45% hosszabbításban dől el (ott ~0.5-ös erőérvényesülés), ~55% tizenegyesekkel
(mért 0.19): `ET_SHRINK = 0.45·0.5 + 0.55·0.19 ≈ 0.33` (volt: 0.75 — becslés).

## Reprodukálás
```bash
python backtest/backtest.py    # ~8 s, a két CSV a mappában van
```

## Meta-learner kísérlet (2026-06-11, második kör)

Az NFL-projekt 3. rétegének (meta-learner) adaptációja: 19 552 tétmeccsen
(1995–) tanított softmax-osztályozó kimenete keverve a Poisson-modell
1X2-jével. A keverési súly (w=0.8) a train-tornákon lett kiválasztva;
tanítás reprodukálható: `python backtest/train_blend.py`.

| Modell | Holdout Brier |
|---|---|
| Poisson (hangolt) | 0.6218 |
| **Poisson + softmax keverék (élesítve)** | **0.5977** |

Az élesített súlyok: `data/blend.json` — a predict() és a Monte Carlo közös,
rács-szinten rekalibrált útvonalon használja, így az 1X2, a pontos eredmények
és a szimuláció konzisztensek.

## Autonóm kísérletsorozat — v2 kalibráció (2026-06-11, harmadik kör)

Protokoll: minden szelekció a TRAIN-tornákon; a holdout összesen kétszer lett
megérintve (egy közbülső és egy végső mérés), a szelekciót egyik sem
befolyásolta. Új metrikák: GoalNLL (a tényleges pontos eredmény negatív
log-valószínűsége — a gólmodell célfüggvénye) és RPS. Futtatás:
`python backtest/experiments.py` (+ finomító rács), nyers eredmények:
`experiments_result.json`.

| Kísérlet | Eredmény | Döntés |
|---|---|---|
| E2: att/def tanulási ráta | lr=0 a legjobb; a gól-alapú adaptáció monoton ront (lr 0.35: +0.020 Brier) | gól-alapú att/def **kikapcsolva**; xG-jel esetén lr=0.25 marad (xG-út történelmileg nem mérhető, konzervatívan megtartva) |
| E2b: torna-K | a harnessben nem mérhető (a tornán belüli Elo-t a globális idősor adja) | K=50 változatlan, jelölve: nem validált |
| E3: hazai bónusz | 65 ≳ 80 (0.5794 vs 0.5796) | HOME_ELO_BONUS=65 |
| E4+E4b: gólmodell-alak (351 kombináció, GoalNLL célon) | gs=200, pow=0.85 (szublineáris), total=2.5, DC=1.25, tc=0.2 → GoalNLL 2.89→2.80 (train) | élesítve |
| E5: MOV-forma | a harnessben nem mérhető | "elo" változatlan, jelölve |
| E6: blend-változatok (3f / +forma / +idősúly) | w=0 mindenhol: az újrahangolt alapmodell mellett a softmax-keverék már nem ad hozzá | **blend kivezetve** (data/blend.json törölve; a korábbi nyereség a gyengébb alapparaméterek kompenzációja volt) |

### Végső mérés (holdout: VB2022 + Eb/Copa 2024)

| Modell | Brier (1X2) | GoalNLL (pontos eredmény) | RPS |
|---|---|---|---|
| Korábbi éles (Poisson+blend) | 0.5977 | ~2.89 | – |
| **v2 (élesítve)** | **0.5894** | **2.7697** | 0.1968 |

A v2 tehát mindkét szinten jobb és egyszerűbb: kevesebb mozgó alkatrész,
nincs külön kalibráló réteg.

## Döntetlen-korrekció formája és a tipp-szemantika (2026-06-12)

Bejelentett jelenség: ~60–62%-os esélyeseknél is 1–1 a megjelenített tipp.

**Mérés:** a flat 1.25-ös szorzó lecserélése szabályos Dixon–Coles-taura
(ρ-rács −0.05…−0.21): train-Brier 0.5758 (ρ=−0.09) vs 0.5762 (flat); GoalNLL
2.8023 vs 2.7996; holdout 0.5908/2.7735 vs 0.5894/2.7697 — **zajon belül
azonos**, és a módusz-átváltási pont is alig mozdul (225 vs 250 Elo-rés).

**Diagnózis:** nem a korrekció hibás — a rács nyers módusza természeténél
fogva eshet a döntetlen-átlóra egyértelmű esélyes mellett is (a győzelem
valószínűsége sok cella közt oszlik el). A hibás elem a *megjelenített
összegző statisztika* volt.

**Javítás:** a tipp a legvalószínűbb 1X2-kimenetelen **belüli** legvalószínűbb
eredmény (osztály-konzisztens módusz); az önellenőrzés pontos-találat metrikája
is erre mér. A flat korrekció maradt élesben (holdouton hajszállal jobb), a
`DC_RHO` opció a kódban elérhető és dokumentáltan ekvivalens.

## E8-E9: fordulóprofil és „biztos sors"-hatás (2026-06-12)

**E9 — fordulófüggő gólátlag.** A csoportmeccsek tényleges gólátlaga elmarad a
modell várakozásától, fordulónként eltérő mértékben (train: −0.45/−0.05/−0.20;
holdout: −0.19/−0.16/−0.61). A gyökérok részben az, hogy az összgól-alap
hangolása a kieséses meccsek hosszabbítással felfújt eredményeit is tartalmazta.
Élesítve: csoportmeccs-offszetek MD1 −0.35, MD2 −0.05, MD3 −0.25 (a két halmaz
összevont, enyhén zsugorított becslése). **Átláthatósági megjegyzés:** ehhez a
korrekcióhoz a holdout leíró statisztikáját is felhasználtuk (a train önmagában
félrevezető MD-profilt adott volna) — a korábbi holdout-számok e komponensre
nézve már nem tekinthetők érintetlennek.

**E8 — „biztos sors" a 3. fordulóban.** A matematikailag már biztos
továbbjutó/kieső csapatok mindkét halmazon alulteljesítik a modell várakozását
(train −0.031, holdout −0.054 várt-eredmény-egység; normál meccsek +0.005/
+0.017). Élesítve: 25 Elo-pontos levonás a 3. fordulóban a pont-alapú
kimerítéses vizsgálattal biztosnak bizonyult sorsú csapatokra (holtverseny =
nem biztos, konzervatív). 2026-ban a nyolc legjobb harmadik továbbjutása a
hatást vélhetően tompítja — a levonás ezért szándékosan mérsékelt, és a Monte
Carlo-szimulációban (útvonal-függősége miatt) nincs alkalmazva.

## Magaslati előny — szakirodalom + saját validáció (2026-06-12)

Forrás: McSharry, *Effect of altitude on physiological performance*, BMJ 2007
(335:1278) — a magaslathoz szokott csapatok magaslaton több gólt szereznek és
kevesebbet kapnak; állítása szerint kb. +0.5 gól / 1000 m magasságkülönbség.

**Saját validáció** (49k meccses adattár, helyszín ≥1500 m):

| Csoport | n | tényleges − Elo-várt eredmény |
|---|---|---|
| magaslathoz szokott csapat magaslaton, tengerszinti ellen | 1159 | **+0.104** |
| tengerszinti csapat magaslaton | 1849 | **−0.193** |

A gólkülönbség-meredekség a mi globális mintánkon **+0.07 gól / 1000 m** — jóval
enyhébb a McSharry-féle dél-amerikai-only +0.5-nél (az ő mintája La Paz-szintű
szélsőségekre szűkült). **Döntés:** az irány megerősítve, beépítve a saját,
konzervatív meredekséggel (`ALT_GOALS_PER_KM=0.07`), kizárólag a ténylegesen
magaslati 2026-os helyszíneken (Mexikóváros 2.24 km, Guadalajara 1.566 km), és
csak akkor, ha a két csapat magaslati-adaptáltsága eltér. 2026-ban 9 meccs
érintett; adaptáltnak a MEX/ECU/COL (+BOL/PER) számít. A holdout-metrikákat ez
nem mozdítja érdemben (a holdout-tornák egyike sem magaslaton zajlott), ezért
ez tudottan torna-specifikus, irodalmi alapú, saját adaton irány-validált
kiegészítés, nem holdout-on optimalizált paraméter.

## BTTS/Over kalibráció + outsider-forma teszt (2026-06-13)

**BTTS és Over2.5 kalibráció** (holdout): BTTS modell 48.8% vs tény 49.0%
(−0.2%, gyakorlatilag tökéletes); Over2.5 modell 47.9% vs tény 44.9% (+3.0%,
de a train +2.2% / holdout +3.0% ingadozás zajon belüli). **Döntés:** nincs
korrekció — a kiírt mutatók kalibráltak, a beavatkozás rontana.

**Felülteljesít-e a jó formájú outsider?** (a meglepetés-anatómia szimmetrikus
párja). Mérés 1990 óta, az outsider torna előtti formája szerint:

| Outsider formája | n | tényl. − várt eredmény |
|---|---|---|
| jó (2.0+ p/m) | 73 | −0.125 |
| közepes (1.3–2.0) | 135 | −0.132 |
| gyenge (<1.3) | 150 | −0.153 |

A jó formájú outsider lényegében ugyanúgy alulteljesít, mint a gyenge — a forma
**nem ad az Elo-n felüli jelet** az outsider oldalán. **Döntés:** nincs
forma-bónusz; Törökország/Németország magas formáját az Elo már megfelelően
kezeli. (A meglepetés-radar jelzése továbbra is csak az *esélyes* gyenge
formájára szól, ahol a hatás igazolt és aszimmetrikus.)
