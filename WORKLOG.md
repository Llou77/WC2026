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
- [x] 8. Hangnem-professzionalizálás + MODEL.md módszertan-dokumentum
- [x] 9. Backtest valós történelmi adaton (49 405 meccs; holdout Brier 0.6218) — paraméterek hangolva
- [x] 10. Monte Carlo szimuláció (10k torna, ~3 s) + „Esélyek" fül
- [x] 11. Adaptív K a becsült Elo-jú csapatokra (első 3 meccs: K=85)
- [x] 12. Egymás elleni FIFA-tiebreaker (valós tabella + MC)
- [x] 13. MC-integráció az oldalon: Tovább% oszlop + párosítás-valószínűség a KO-kártyákon
- [x] 14. Meccsstatisztika-réteg: lövésalapú xG-proxy, piroslap-diszkont, bővített observed-séma
- [x] 15. Corners/NFL-repók elemzése; áthozva: auto-statisztika fetch (corners), confidence-címkék (NFL), önellenőrzés (corners), pihenőnap-korrekció (NFL)
- [x] 16. Meta-learner rekalibráció (softmax-blend, holdout Brier 0.6218 -> 0.5977) + ET-fáradtság a pihenőszámításban
- [x] 17. Hibabiztosítás: API/overlay/rossz-adat védelem, atomi fájlírás, automatikus overlay a workflow-ban, concurrency-védelem, performance.json commitolása
- [x] 18. Automatikus xG-forrás (API-Football, opcionális kulccsal, hibabiztos)
- [x] 19. Párharc-réteg (centírozott vonal-mátrix ±10% sapkával), csatorna-profilok, játékos-értékelés betöltés + „Párharc-kép" elemzés-bekezdés
- [x] 20. Teljes körű audit: kód zöld (10 fájl fordul, 3 E2E, 104 meccs konzisztens); README újraírva, MODEL.md hivatkozás+7-blokk javítva, REPORT.md blend-szakasszal bővítve
- [x] 21. Autonóm kísérletsorozat (E1-E7, 400+ konfiguráció): gól-alapú att/def kikapcsolva (mérten ártott), gólmodell v2 (szublineáris, gs=200), hazai bónusz 65, blend kivezetve
- [x] 22. v2 élesítve — holdout Brier 0.5977 -> 0.5894, GoalNLL 2.89 -> 2.77; nem mérhető elemek (torna-K, MOV, xG-út, párharc-réteg) dokumentáltan változatlanok
- [x] 23. Tipp-szemantika javítva (osztály-konzisztens módusz; DC-tau mérten ekvivalens, flat maradt); 2026.06.11-i eredmények beírva (MEX 2-0 RSA, KOR 2-1 CZE) + eltiltás-hírek; kulcs nélküli GitHub CSV-tartalékforrás + hangos workflow-jelzések
- [x] 24. Kalibrációs audit a torzítás-bejelentésre: döntetlen modell 26,4% vs tény 27,9% (holdout), várt gól 2,73 vs tény ~2,45 — torzítás nem igazolódott; az érzet forrása a régi deployolt build + alacsony módusz-eredmények; várható-gólszám kijelzés hozzáadva
- [x] 25. E8-E9 mérve és élesítve: fordulóprofil-offszetek (MD1 -0.35) + locked-levonás (25 Elo); F1 automatikus eltiltás-követés (kártya-események, sárga-halmozódás); F2 BTTS/over2.5 a verdiktben
- [x] 26. WhoScored-elemzés; átemelve: egymás elleni mérleg + torna előtti forma (automatikus, a saját történelmi adattárból; WhoScored-számokkal keresztvalidálva); elvetve: várható kezdők (nincs megbízható ingyenes forrás napokkal előre), klub-statisztika-összevetés (válogatottakra üres náluk is), odds-megjelenítés (tudatos no-market irányelv)

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
