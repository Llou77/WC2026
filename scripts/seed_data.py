# -*- coding: utf-8 -*-
"""Seed data for the 2026 World Cup predictor.
Regenerates data/teams.json and data/matches.json from scratch.
Sources: groups & schedule = Yahoo Sports / Wikipedia (2026-06-11),
Elo seeds = eloratings.net snapshots (2026-06-11 / 2026-01-19);
entries marked est=True are conservative estimates (tipp).
"""
import json, os

T = lambda code, name, grp, elo, est, players, style, note="": dict(
    code=code, name=name, group=grp, elo=elo, elo_estimated=est,
    att=1.0, deff=1.0, players=players, style=style, news=note)

TEAMS = [
 # --- A ---
 T("MEX","Mexikó","A",1800,True,["Santiago Giménez","Edson Álvarez","Luis Malagón"],
   "Hazai pályán nyomást gyakorló, labdabirtoklásra törekvő csapat; az Azteca-faktor mérhető előny."),
 T("RSA","Dél-Afrika","A",1640,True,["Ronwen Williams","Teboho Mokoena","Lyle Foster"],
   "Hugo Broos alatt stabil, szervezett blokk, gyors átmenetekkel."),
 T("KOR","Dél-Korea","A",1745,True,["Son Heung-min","Lee Kang-in","Kim Min-jae"],
   "Technikás középpálya, veszélyes kontrák; a védelem Kim Min-jaéra épül."),
 T("CZE","Csehország","A",1715,True,["Patrik Schick","Tomáš Souček","Adam Hložek"],
   "Fizikális, pontrúgásokban erős, mélyen védekező felállás."),
 # --- B ---
 T("CAN","Kanada","B",1770,True,["Alphonso Davies","Jonathan David","Stephen Eustáquio"],
   "Atletikus, intenzív letámadás; hazai közönség előtt extra lendület."),
 T("BIH","Bosznia-Hercegovina","B",1650,True,["Edin Džeko","Ermedin Demirović","Sead Kolašinac"],
   "Rutinos mag, beadásokra és Džeko fejjátékára építő támadójáték."),
 T("QAT","Katar","B",1565,True,["Akram Afif","Almoez Ali"],
   "Türelmes labdajáratás, de a felkészülését régiós feszültségek zavarták meg.",
   "A felkészülést a régiós konfliktus zavarta: elmaradt felkészülési meccs, akadozó bajnokság."),
 T("SUI","Svájc","B",1897,False,["Granit Xhaka","Breel Embolo","Dan Ndoye"],
   "Kiegyensúlyozott, taktikailag fegyelmezett; tornákon rendre felülteljesít."),
 # --- C ---
 T("BRA","Brazília","C",1991,False,["Vinícius Júnior","Raphinha","Alisson"],
   "Egyéni minőségben kiemelkedő szélső játék, Ancelotti alatt pragmatikusabb szerkezet."),
 T("MAR","Marokkó","C",1860,True,["Achraf Hakimi","Brahim Díaz","Yassine Bounou"],
   "A 2022-es elődöntős váz együtt maradt: betonvédelem, halálos kontrák."),
 T("HAI","Haiti","C",1500,True,["Duckens Nazon","Danley Jean Jacques"],
   "Lelkes, fizikális kívülálló; első VB-je 1974 óta."),
 T("SCO","Skócia","C",1745,True,["Scott McTominay","John McGinn","Andy Robertson"],
   "Középpályán letámadó, pontrúgás-erős brit stílus; 1998 óta első VB-jén."),
 # --- D ---
 T("USA","Egyesült Államok","D",1785,True,["Christian Pulisic","Weston McKennie","Matt Turner"],
   "Hazai pályán, Pochettino irányításával intenzív, vertikális futball."),
 T("PAR","Paraguay","D",1780,True,["Miguel Almirón","Julio Enciso","Antonio Sanabria"],
   "Alguacil-féle kemény, kompakt dél-amerikai iskola, erős párharcjáték."),
 T("AUS","Ausztrália","D",1725,True,["Jackson Irvine","Mathew Ryan","Craig Goodwin"],
   "Szervezett mélyvédekezés, pontrúgások és bedobás-variációk."),
 T("TUR","Törökország","D",1880,False,["Hakan Çalhanoğlu","Arda Güler","Kenan Yıldız"],
   "Montella alatt kreatív, támadószellemű generáció — a csoport sötét lova."),
 # --- E ---
 T("GER","Németország","E",1910,False,["Jamal Musiala","Florian Wirtz","Joshua Kimmich"],
   "Nagelsmann-féle pozíciós játék Musiala–Wirtz kreatív tengellyel."),
 T("CUW","Curaçao","E",1460,True,["Leandro Bacuna","Kenji Gorré"],
   "A VB-történet legkisebb országa; Dick Advocaat pragmatikus mélyvédekezése.",
   "Felemás felkészülés: 1-4 Skócia ellen, 4-0 Aruba ellen."),
 T("CIV","Elefántcsontpart","E",1730,True,["Sébastien Haller","Franck Kessié","Simon Adingra"],
   "Afrikai bajnoki rutin (2024), fizikális középpálya, gyors szélsők."),
 T("ECU","Ecuador","E",1933,False,["Moisés Caicedo","Piero Hincapié","Kendry Páez"],
   "A selejtezők egyik legjobb védelme; Caicedo köré épülő, érett csapat."),
 # --- F ---
 T("NED","Hollandia","F",1959,False,["Virgil van Dijk","Frenkie de Jong","Cody Gakpo"],
   "Strukturált felépítés hátulról, van Dijk vezérelte stabil védelem."),
 T("JPN","Japán","F",1879,False,["Takefusa Kubo","Kaoru Mitoma","Wataru Endo"],
   "Magas intenzitás, gyors szélső rotációk; nagy csapatok ellen is bizonyított."),
 T("SWE","Svédország","F",1715,True,["Viktor Gyökeres","Alexander Isak","Dejan Kulusevski"],
   "Pótselejtezőről jött, de a Gyökeres–Isak duó bármely védelmet megbonthat."),
 T("TUN","Tunézia","F",1690,True,["Hannibal Mejbri","Youssef Msakni"],
   "Fegyelmezett, mélyen védekező észak-afrikai iskola."),
 # --- G ---
 T("BEL","Belgium","G",1849,False,["Kevin De Bruyne","Jérémy Doku","Charles De Ketelaere"],
   "Generációváltás Garcia alatt: Doku-féle robbanékonyság, De Bruyne rutinja."),
 T("EGY","Egyiptom","G",1690,True,["Mohamed Salah","Omar Marmoush","Mostafa Mohamed"],
   "Salah–Marmoush támadósor, mögötte konzervatív, mélyen védekező blokk."),
 T("IRN","Irán","G",1755,True,["Mehdi Taremi","Sardar Azmoun","Alireza Beiranvand"],
   "Rutinos, kontrákra építő csapat — de a felkészülése súlyosan sérült.",
   "A felkészülés komolyan sérült: edzőtábor-áthelyezés Tijuanába, vízumproblémák az USA-ban."),
 T("NZL","Új-Zéland","G",1590,True,["Chris Wood","Liberato Cacace"],
   "Egyszerű, direkt játék Chris Wood célemberre; korlátozott mélységű keret."),
 # --- H ---
 T("ESP","Spanyolország","H",2157,False,["Lamine Yamal","Pedri","Rodri"],
   "A világranglista-vezető: Eb-címvédő, dominánsan labdabirtokló, mély rotáció."),
 T("CPV","Zöld-foki Köztársaság","H",1545,True,["Ryan Mendes","Jamiro Monteiro"],
   "Történelmi első VB-részvétel; kompakt, lelkes, kontrázó csapat."),
 T("KSA","Szaúd-Arábia","H",1620,True,["Salem Al-Dawsari","Firas Al-Buraikan"],
   "Technikás, labdabirtoklásra törekvő; nagy skalpra is képes (Argentína 2022)."),
 T("URU","Uruguay","H",1890,False,["Federico Valverde","Darwin Núñez","Ronald Araújo"],
   "Bielsa-féle intenzív letámadás, kiváló egyéni minőség minden csapatrészben."),
 # --- I ---
 T("FRA","Franciaország","I",2063,False,["Kylian Mbappé","Ousmane Dembélé","Aurélien Tchouaméni"],
   "A mezőny legmélyebb kerete; két döntő az előző két VB-n."),
 T("SEN","Szenegál","I",1869,False,["Sadio Mané","Pape Matar Sarr","Nicolas Jackson"],
   "Atletikus, átmenetekben elsöprő; Afrika legstabilabb válogatottja."),
 T("IRQ","Irak","I",1605,True,["Aymen Hussein","Ali Jasim"],
   "Interkontinentális pótselejtezőről érkezett, harcos, hazafias lendület."),
 T("NOR","Norvégia","I",1922,False,["Erling Haaland","Martin Ødegaard","Alexander Sørloth"],
   "Haaland 16 gólt lőtt a selejtezőben; direkt, gólerős gépezet, 1998 óta első VB."),
 # --- J ---
 T("ARG","Argentína","J",2115,False,["Lionel Messi","Julián Álvarez","Enzo Fernández"],
   "Címvédő; Scaloni-féle érett tornagépezet, Messi utolsó VB-táncára hangolva."),
 T("ALG","Algéria","J",1755,True,["Riyad Mahrez","Amine Gouiri","Houssem Aouar"],
   "Technikás, kreatív támadósor; tornaformája hullámzó."),
 T("AUT","Ausztria","J",1810,True,["David Alaba","Christoph Baumgartner","Marcel Sabitzer"],
   "Rangnick-pressing: a mezőny egyik legintenzívebb letámadása."),
 T("JOR","Jordánia","J",1550,True,["Mousa Al-Taamari","Yazan Al-Naimat"],
   "2024-es Ázsia-kupa-döntős; gyors ellentámadások, első VB-részvétel."),
 # --- K ---
 T("POR","Portugália","K",1989,False,["Cristiano Ronaldo","Bruno Fernandes","Rafael Leão"],
   "Nemzetek Ligája-győztes mag; Ronaldo búcsú-VB-je extra motiváció."),
 T("COD","Kongói DK","K",1610,True,["Cédric Bakambu","Yoane Wissa","Chancel Mbemba"],
   "Pótselejtező-hős; fizikális, lelkes, kontrákra veszélyes."),
 T("UZB","Üzbegisztán","K",1640,True,["Abbosbek Fayzullaev","Eldor Shomurodov","Abdukodir Khusanov"],
   "Történelmi első VB; fegyelmezett védekezés, Khusanov vezérletével."),
 T("COL","Kolumbia","K",1982,False,["Luis Díaz","James Rodríguez","Jhon Durán"],
   "Elo-alapon top-7 erő: hosszú veretlenségi sorozat, Díaz csúcsformában."),
 # --- L ---
 T("ENG","Anglia","L",2024,False,["Harry Kane","Jude Bellingham","Bukayo Saka"],
   "Tuchel alatt 100%-os selejtező, kapott gól nélkül; trófea-kényszer."),
 T("CRO","Horvátország","L",1933,False,["Luka Modrić","Joško Gvardiol","Mateo Kovačić"],
   "Az örök tornacsapat: Modrić utolsó VB-je, kontrollált középpálya."),
 T("GHA","Ghána","L",1655,True,["Mohammed Kudus","Thomas Partey","Antoine Semenyo"],
   "Premier League-minőségű egyéniségek, hullámzó szervezettség."),
 T("PAN","Panama","L",1655,True,["Adalberto Carrasquilla","José Fajardo"],
   "A CONCACAF-selejtező meglepetésgyőztese; kompakt, harcos egység."),
]

V = {
 "AZT":("Estadio Azteca, Mexikóváros","MEX"), "AKR":("Estadio Akron, Guadalajara","MEX"),
 "BBV":("Estadio BBVA, Monterrey","MEX"), "BMO":("BMO Field, Toronto","CAN"),
 "BCP":("BC Place, Vancouver","CAN"), "SOF":("SoFi Stadium, Inglewood","USA"),
 "LEV":("Levi's Stadium, Santa Clara","USA"), "LUM":("Lumen Field, Seattle","USA"),
 "MET":("MetLife Stadium, New Jersey","USA"), "GIL":("Gillette Stadium, Foxborough","USA"),
 "MBS":("Mercedes-Benz Stadium, Atlanta","USA"), "HRS":("Hard Rock Stadium, Miami","USA"),
 "LFF":("Lincoln Financial Field, Philadelphia","USA"), "NRG":("NRG Stadium, Houston","USA"),
 "ATT":("AT&T Stadium, Arlington","USA"), "ARW":("Arrowhead Stadium, Kansas City","USA"),
}

# (stage, group, home, away, date, time_ET, venue_key)
G = [
 ("A","MEX","RSA","2026-06-11","15:00","AZT"),("A","KOR","CZE","2026-06-11","22:00","AKR"),
 ("A","CZE","RSA","2026-06-18","12:00","MBS"),("A","MEX","KOR","2026-06-18","21:00","AKR"),
 ("A","CZE","MEX","2026-06-24","21:00","AZT"),("A","RSA","KOR","2026-06-24","21:00","BBV"),
 ("B","CAN","BIH","2026-06-12","15:00","BMO"),("B","QAT","SUI","2026-06-13","15:00","LEV"),
 ("B","SUI","BIH","2026-06-18","15:00","SOF"),("B","CAN","QAT","2026-06-18","18:00","BCP"),
 ("B","SUI","CAN","2026-06-24","15:00","BCP"),("B","BIH","QAT","2026-06-24","15:00","LUM"),
 ("C","BRA","MAR","2026-06-13","18:00","MET"),("C","HAI","SCO","2026-06-13","21:00","GIL"),
 ("C","SCO","MAR","2026-06-19","18:00","GIL"),("C","BRA","HAI","2026-06-19","20:30","LFF"),
 ("C","SCO","BRA","2026-06-24","18:00","HRS"),("C","MAR","HAI","2026-06-24","18:00","MBS"),
 ("D","USA","PAR","2026-06-12","21:00","SOF"),("D","AUS","TUR","2026-06-13","00:00","BCP"),
 ("D","USA","AUS","2026-06-19","15:00","LUM"),("D","TUR","PAR","2026-06-19","23:00","LEV"),
 ("D","TUR","USA","2026-06-25","22:00","SOF"),("D","PAR","AUS","2026-06-25","22:00","LEV"),
 ("E","GER","CUW","2026-06-14","13:00","NRG"),("E","CIV","ECU","2026-06-14","19:00","LFF"),
 ("E","GER","CIV","2026-06-20","16:00","BMO"),("E","ECU","CUW","2026-06-20","20:00","ARW"),
 ("E","CUW","CIV","2026-06-25","16:00","LFF"),("E","ECU","GER","2026-06-25","16:00","MET"),
 ("F","NED","JPN","2026-06-14","16:00","ATT"),("F","SWE","TUN","2026-06-14","22:00","BBV"),
 ("F","NED","SWE","2026-06-20","13:00","NRG"),("F","TUN","JPN","2026-06-21","00:00","BBV"),
 ("F","JPN","SWE","2026-06-25","19:00","ATT"),("F","TUN","NED","2026-06-25","19:00","ARW"),
 ("G","BEL","EGY","2026-06-15","15:00","LUM"),("G","IRN","NZL","2026-06-15","21:00","SOF"),
 ("G","BEL","IRN","2026-06-21","15:00","SOF"),("G","NZL","EGY","2026-06-21","21:00","BCP"),
 ("G","EGY","IRN","2026-06-26","23:00","LUM"),("G","NZL","BEL","2026-06-26","23:00","BCP"),
 ("H","ESP","CPV","2026-06-15","12:00","MBS"),("H","KSA","URU","2026-06-15","18:00","HRS"),
 ("H","ESP","KSA","2026-06-21","12:00","MBS"),("H","URU","CPV","2026-06-21","18:00","HRS"),
 ("H","CPV","KSA","2026-06-26","20:00","NRG"),("H","URU","ESP","2026-06-26","20:00","AKR"),
 ("I","FRA","SEN","2026-06-16","15:00","MET"),("I","IRQ","NOR","2026-06-16","18:00","GIL"),
 ("I","FRA","IRQ","2026-06-22","17:00","LFF"),("I","NOR","SEN","2026-06-22","20:00","MET"),
 ("I","NOR","FRA","2026-06-26","15:00","GIL"),("I","SEN","IRQ","2026-06-26","15:00","BMO"),
 ("J","ARG","ALG","2026-06-16","21:00","ARW"),("J","AUT","JOR","2026-06-17","00:00","LEV"),
 ("J","ARG","AUT","2026-06-22","13:00","ATT"),("J","JOR","ALG","2026-06-22","23:00","LEV"),
 ("J","JOR","ARG","2026-06-27","22:00","ATT"),("J","ALG","AUT","2026-06-27","22:00","ARW"),
 ("K","POR","COD","2026-06-17","13:00","NRG"),("K","UZB","COL","2026-06-17","22:00","AZT"),
 ("K","POR","UZB","2026-06-23","13:00","NRG"),("K","COL","COD","2026-06-23","22:00","AKR"),
 ("K","COL","POR","2026-06-27","19:30","HRS"),("K","COD","UZB","2026-06-27","19:30","MBS"),
 ("L","ENG","CRO","2026-06-17","16:00","ATT"),("L","GHA","PAN","2026-06-17","19:00","BMO"),
 ("L","ENG","GHA","2026-06-23","16:00","GIL"),("L","PAN","CRO","2026-06-23","19:00","BMO"),
 ("L","PAN","ENG","2026-06-27","17:00","MET"),("L","CRO","GHA","2026-06-27","17:00","LFF"),
]

# Knockout: official match numbers; slots reference group results or earlier winners.
# W=group winner, R=runner-up, T=best third (allowed groups), M=winner of match N
KO = [
 (73,"r32","R:A","R:B","2026-06-28","15:00","SOF"),
 (74,"r32","W:E","T:ABCDF","2026-06-29","16:30","GIL"),
 (75,"r32","W:F","R:C","2026-06-29","21:00","BBV"),
 (76,"r32","W:C","R:F","2026-06-29","13:00","NRG"),
 (77,"r32","W:I","T:CDFGH","2026-06-30","17:00","MET"),
 (78,"r32","R:E","R:I","2026-06-30","13:00","ATT"),
 (79,"r32","W:A","T:CEFHI","2026-06-30","21:00","AZT"),
 (80,"r32","W:L","T:EHIJK","2026-07-01","12:00","MBS"),
 (81,"r32","W:D","T:BEFIJ","2026-07-01","20:00","LEV"),
 (82,"r32","W:G","T:AEHIJ","2026-07-01","16:00","LUM"),
 (83,"r32","R:K","R:L","2026-07-02","19:00","BMO"),
 (84,"r32","W:H","R:J","2026-07-02","15:00","SOF"),
 (85,"r32","W:B","T:EFGIJ","2026-07-02","23:00","BCP"),
 (86,"r32","W:J","R:H","2026-07-03","18:00","HRS"),
 (87,"r32","W:K","T:DEIJL","2026-07-03","21:30","ARW"),
 (88,"r32","R:D","R:G","2026-07-03","14:00","ATT"),
 (89,"r16","M:74","M:77","2026-07-04","13:00","NRG"),
 (90,"r16","M:73","M:75","2026-07-04","17:00","LFF"),
 (91,"r16","M:76","M:78","2026-07-05","16:00","MET"),
 (92,"r16","M:79","M:80","2026-07-05","20:00","AZT"),
 (93,"r16","M:83","M:84","2026-07-06","15:00","ATT"),
 (94,"r16","M:81","M:82","2026-07-06","20:00","LUM"),
 (95,"r16","M:86","M:88","2026-07-07","12:00","MBS"),
 (96,"r16","M:85","M:87","2026-07-07","16:00","BCP"),
 (97,"qf","M:89","M:90","2026-07-09","16:00","GIL"),
 (98,"qf","M:93","M:94","2026-07-10","15:00","SOF"),
 (99,"qf","M:91","M:92","2026-07-11","17:00","HRS"),
 (100,"qf","M:95","M:96","2026-07-11","21:00","ARW"),
 (101,"sf","M:97","M:98","2026-07-14","15:00","ATT"),
 (102,"sf","M:99","M:100","2026-07-15","15:00","MBS"),
 (103,"third","L:101","L:102","2026-07-18","17:00","HRS"),
 (104,"final","M:101","M:102","2026-07-19","15:00","MET"),
]

def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    matches = []
    for i,(grp,h,a,d,t,v) in enumerate(G, start=1):
        matches.append(dict(id=i, stage="group", group=grp, home=h, away=a,
                            date=d, time_et=t, venue=V[v][0], venue_country=V[v][1]))
    for (mid,stage,h,a,d,t,v) in KO:
        matches.append(dict(id=mid, stage=stage, group=None, home=h, away=a,
                            date=d, time_et=t, venue=V[v][0], venue_country=V[v][1]))
    with open(os.path.join(root,"data","teams.json"),"w",encoding="utf-8") as f:
        json.dump(TEAMS,f,ensure_ascii=False,indent=1)
    with open(os.path.join(root,"data","matches.json"),"w",encoding="utf-8") as f:
        json.dump(matches,f,ensure_ascii=False,indent=1)
    print(f"OK: {len(TEAMS)} teams, {len(matches)} matches")

if __name__ == "__main__":
    main()
