# WORKLOG
Feladat: VB2026 ML előrejelző — GitHub-repo + magyar HTML fedőoldal, napi kézi
frissítésű (fetch + update) inkrementális modellel, 1X2 % + várható eredmény +
indoklás mind a 104 meccsre.

Terv:
- [x] 1. Kutatás (csoportok, 104 meccs menetrend, Elo 2026-06-11, hírek)
- [x] 2. Repo-struktúra + seed adatok (48 csapatprofil, 104 meccs)
- [x] 3. Modell (inkrementális Elo + xG-kevert att/def, Poisson+DC, KO-továbbjutó)
- [x] 4. HTML generátor (VB26-inspirált, trikolor valószínűség-szalag)
- [x] 5. Kieséses ág automatikus feltöltése (valós / vetített)
- [x] 6. Ellenőrzés (validáció, szimulált frissítés, HTML visszaolvasás)
- [x] 7. README + zárás

Aktuális állapot: KÉSZ. Folytatáshoz: eredmények a data/observed.json-ba
(fetch_data.py vagy kézzel), majd `python update.py`.

Döntések:
[DÖNTÉS] ML-megközelítés | Inkrementális Elo+Poisson, nem batch-refit | A napi
frissítés <1 s, refit-idő probléma fogalmilag megszűnik.
[DÖNTÉS] xG-forrás törékeny | 70/30 gól/xG keverék, xG nélkül is működik | Robusztusság.
[DÖNTÉS] FIFA-arculat védett | Inspirált trikolor-dizájn, logók nélkül | Jogtisztaság.
[DÖNTÉS] Annex C (495 kombináció) | Backtracking-közelítés | A valós sorsolást a
betöltött eredmény felülírja; predikcióhoz elegendő.
[DÖNTÉS] Néhány éjféli kezdés (ET "12 a.m.") forrásban kétértelmű | AUS-TUR 06-13
00:00, TUN-JPN 06-21 00:00, AUT-JOR 06-17 00:00 | A modellt nem érinti.
[DÖNTÉS] R16/QF dátum→meccsszám hozzárendelés a forrásban nem explicit |
sorszám szerinti hozzárendelés, közelítő | Helyszín/dátum kozmetikai adat.
[DÖNTÉS] ~30 csapat Elo-ja becsült (tipp) | elo_estimated flag a teams.json-ban |
Az első fordulók frissítései gyorsan korrigálják.
