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
