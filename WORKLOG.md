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
- [x] 27. Meglepetés-anatómia (354 VB-meccs 1990 óta): a gyenge formájú esélyes a fő bravúr-változó (23,5% vs 12,1%); jelzésként beépítve az elemzésekbe; Ecuador-Németország kérdés tisztázva (Elo: 1933 vs 1910, nem meglepetés-tipp)
- [x] 28. Szakirodalom-kutatás (Groll/Ley random forest, Zeileis hibrid, McSharry magaslat-tanulmány); magaslati előny saját adaton irány-validálva (+0.104 vs -0.193) és beépítve konzervatív 0.07 gól/1000 m meredekséggel a mexikói pályákon; piaci érték/GDP változók elvetve (Elo-redundáns + kézi adatigény)
- [x] 29. BTTS/Over2.5 kalibráció ellenőrizve (holdouton kalibrált, nincs korrekció); outsider-forma teszt: a jó formájú outsider nem teljesít felül (-0.125 vs -0.153), nincs forma-bónusz — az Elo helyesen árazza
- [x] 30. Kiírt-módusz hiba javítva: a kártyatető „várható" kijelzése is az osztály-konzisztens tip mezőt használja (104 meccsből a kiírt döntetlen 18+ -> 1); döntetlen-kalibráció ellenőrizve: modell-átlag 25,7% = tényleges ~27%, nincs torzítás
- [x] 31. Hiányzás-csatorna kiszélesítve (demonstrált hiba: a 3 valós eltiltás — Montes/Sithole/Zwane — eddig −0 Elo volt, mert nem voltak a 3 nevű kulcslistán). Most: nem-listás eltiltás −12, listás kulcsjátékos −25, kézi `out` (sérülés) csatorna a teams.json-ban (string vagy {name,elo}), játékosonkénti dedup, csapatonként −60 plafon; szöveg↔szám egyezik. Élesben tesztelve (Montes 4. meccs −1,3 pp MEX-győzelem; ESP out string+súly OK). Magnitúdók a ratings.py-ban hangolhatók, nem backtestelhetők.

- [x] 32. Élő megbízhatóság-műszer: a meccs-előtti predikciókra skill-score (uniform 0.667 + backtest-elvárás 0.589 viszonyában), log-loss, over/under-magabiztosság és magabiztossági sávonkénti reliability-bontás (performance.json + új „Megbízhatóság" fül). Zaj-tudatos kalibrációs ítélet (binomiális szóráshoz mérve) — kis mintán nincs hamis riasztás. Élő állás: 12 meccs, Brier 0.654 (skill +2%), egyelőre jól kalibrált. Mérőeszköz, a kimeneteket nem módosítja.

- [x] 33. Korrektségi audit (simulate/standings/predict): a Monte Carlo a kieséses meccseket magaslat (venue_city) nélkül mintázta, miközben a meccsenkénti KO-predikció a magaslattal számol — inkonzisztencia javítva (2 Azteca KO-meccs: R32 #79, R16 #92). Hatás: adaptált csapatok mélyebbre jutása nő (MEX negyeddöntő 23,4%->25,1%, ECU elődöntő 8,1%->9,2%). Megerősítve, hogy a knockout flag csak összegző mezőt ad (a rácsot nem), és a MC azt maga reprodukálja; az eltiltás/locked-levonás MC-ből való kihagyása szándékos és dokumentált. Más valódi hiba nem találva.

- [x] 34. Meglepetés-radar (új fül): a modell saját 1X2-eloszlásából kiemeli, hol a legélőbb a bravúr / a döntetlen / a papírforma-ellenes tipp — a predikciók módosítása NÉLKÜL. Kulcsdöntés: az 'esélytelen/favorit' a TORNA ELŐTTI (seed) Elo szerint értendő, mert egy kalibrált modell mindig a jelenlegi favoritját tippeli (élő Elóval a 'merész' lista tautologikusan üres). Felszínre hozza: Ausztrália 46% / USA 45% / Németország 38% a torna előtti favoritjuk ellen — a modell mindháromban az esélytelent tippeli. Megerősített tervezési igazság: 'izgalmasabb upset-tippek' = rosszabb kalibráció; a radar a MEGLÉVŐ jelet mutatja, nem gyárt újat.

- [x] 35. KIESÉSES BRACKET-HIBA javítva (felhasználó jelezte): a harmadik-helyek ágra sorolása backtrackinggel EGY érvényes, de nem a FIFA Annex C szerinti hozzárendelést adott -> 2 csere, 4 rossz R32-párosítás (Németország–Svédország/Franciaország–Paraguay és Belgium–Algéria/Svájc–Szenegál felcserélve). Súlyosbító: a #74 MÁR LEJÁTSZOTT (GER 3–4), és a rossz párosítás miatt az eredmény rossz csapathoz került — a modell Svédországot léptette tovább Paraguay helyett. Javítás: hivatalos Annex C tábla a tényleges kombinációra (B,D,E,F,I,J,K,L) a standings.py-ban ÉS a simulate.py MC-jében; backtracking marad tartalék. Ellenőrizve: mind a 16 R32-párosítás egyezik a hivatalos brackettel (CBS/ESPN), downstream körök és az Esélyek-fül konzisztens. Másodlagos hiba nincs.

Aktuális állapot: KÉSZ (35). Folytatáshoz: eredmények a data/observed.json-ba
(fetch_data.py vagy kézzel), kézi hiányzók a teams.json `out` mezőjébe, majd
`python update.py`.

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
