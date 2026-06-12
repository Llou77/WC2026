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
