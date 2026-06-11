# -*- coding: utf-8 -*-
"""Static site renderer: builds index.html from the computed predictions."""
import html, json
from model.analysis import STAGE_HU

CSS = """
:root{--red:#D6173A;--green:#0E7C3F;--blue:#1D4ED8;--ink:#10142E;--paper:#F6F5F0;
--card:#FFFFFF;--mut:#6B7080;--line:#E4E2DA;--gold:#C9A227}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Barlow',system-ui,sans-serif;background:var(--paper);color:var(--ink)}
.disp{font-family:'Barlow Condensed','Arial Narrow',sans-serif;text-transform:uppercase;
letter-spacing:.02em}
header{background:var(--ink);color:#fff;padding:34px 20px 26px;position:relative;overflow:hidden}
header::before{content:"";position:absolute;inset:0;
background:linear-gradient(115deg,var(--red) 0 4px,transparent 4px 0) left/33.4% 100% no-repeat,
linear-gradient(115deg,var(--green) 0 4px,transparent 4px 0) center/33.4% 100% no-repeat,
linear-gradient(115deg,var(--blue) 0 4px,transparent 4px 0) right/33.4% 100% no-repeat;opacity:.9}
header h1{font-size:clamp(30px,5vw,52px);font-weight:800;line-height:.95}
header h1 span{display:block;font-size:.42em;font-weight:500;letter-spacing:.22em;color:var(--gold)}
header p{margin-top:10px;max-width:760px;color:#C7CADB;font-size:14.5px}
.tri{display:inline-flex;height:10px;width:84px;margin-bottom:14px}
.tri i{flex:1}.tri i:nth-child(1){background:var(--red)}.tri i:nth-child(2){background:var(--green)}
.tri i:nth-child(3){background:var(--blue)}
nav{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid var(--line);
display:flex;gap:6px;overflow-x:auto;padding:10px 16px}
nav button{font:600 14px 'Barlow Condensed';text-transform:uppercase;letter-spacing:.06em;
border:1px solid var(--line);background:#fff;padding:7px 13px;border-radius:999px;cursor:pointer;
white-space:nowrap;color:var(--ink)}
nav button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
main{max-width:1060px;margin:0 auto;padding:26px 16px 70px}
.sect{display:none}.sect.on{display:block}
h2.gh{font-size:30px;margin:26px 0 4px;display:flex;align-items:baseline;gap:10px}
h2.gh small{font-size:13px;color:var(--mut);font-family:'Barlow';text-transform:none;
letter-spacing:0;font-weight:500}
table.st{width:100%;border-collapse:collapse;background:var(--card);margin:10px 0 18px;
font-size:14px;border:1px solid var(--line)}
table.st th{font:600 12px 'Barlow Condensed';text-transform:uppercase;letter-spacing:.08em;
color:var(--mut);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
table.st td{padding:7px 10px;border-bottom:1px solid var(--line)}
table.st tr.q td:first-child{box-shadow:inset 3px 0 0 var(--green)}
table.st tr.t3 td:first-child{box-shadow:inset 3px 0 0 var(--gold)}
.card{background:var(--card);border:1px solid var(--line);margin:12px 0;overflow:hidden}
.head{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:8px;
padding:14px 16px 6px;cursor:pointer}
.tname{font:700 21px 'Barlow Condensed';text-transform:uppercase}
.tname.a{text-align:right}
.score{font:800 24px 'Barlow Condensed';padding:2px 12px;text-align:center;min-width:84px}
.score b{color:var(--mut);font-size:12px;display:block;font-weight:500;
font-family:'Barlow';text-transform:none;letter-spacing:0}
.meta{display:flex;flex-wrap:wrap;gap:5px 14px;padding:0 16px 10px;color:var(--mut);
font-size:12.5px;cursor:pointer}
.ribbon{display:flex;height:14px;margin:0 16px 4px;border-radius:3px;overflow:hidden;cursor:pointer}
.ribbon i{display:flex;align-items:center;justify-content:center;color:#fff;
font:700 10px 'Barlow';min-width:0;overflow:hidden}
.ribbon .w1{background:var(--red)}.ribbon .wx{background:#8A8F9E}.ribbon .w2{background:var(--blue)}
.legend{display:flex;justify-content:space-between;padding:0 16px 12px;font-size:11.5px;color:var(--mut)}
.body{display:none;border-top:1px dashed var(--line);padding:14px 16px;font-size:14.5px;line-height:1.55}
.card.open .body{display:block}
.body p{margin:0 0 10px}
.tag{display:inline-block;font:700 10.5px 'Barlow';letter-spacing:.05em;text-transform:uppercase;
padding:2px 7px;border-radius:3px;background:var(--ink);color:#fff;margin-right:6px}
.tag.proj{background:var(--gold);color:var(--ink)}
.tag.done{background:var(--green)}
.note{font-size:12.5px;color:var(--mut);margin:14px 0}
footer{border-top:1px solid var(--line);color:var(--mut);font-size:12.5px;
padding:22px 16px;max-width:1060px;margin:0 auto}
@media(max-width:560px){.tname{font-size:16px}.score{min-width:64px;font-size:19px}}
"""

JS = """
function tab(id,btn){document.querySelectorAll('.sect').forEach(s=>s.classList.remove('on'));
document.getElementById(id).classList.add('on');
document.querySelectorAll('nav button').forEach(b=>b.classList.remove('on'));btn.classList.add('on');
window.scrollTo({top:0});}
document.querySelectorAll('.card').forEach(c=>{
 c.querySelectorAll('.head,.ribbon,.meta').forEach(el=>el.addEventListener('click',
   ()=>c.classList.toggle('open')));});
"""

def _bp_time(date, t):
    h, mi = map(int, t.split(":"))
    h += 6
    d = date
    if h >= 24:
        h -= 24
        y, mo, da = map(int, date.split("-"))
        da += 1  # tournament dates never cross month boundary except 6/30->7/1
        if (mo == 6 and da > 30):
            mo, da = 7, 1
        d = f"{y:04d}-{mo:02d}-{da:02d}"
    return d, f"{h:02d}:{mi:02d}"

def _ribbon(p):
    seg = ""
    for cls, val, lab in (("w1", p["p1"], "1"), ("wx", p["px"], "X"), ("w2", p["p2"], "2")):
        pct = val * 100
        txt = f"{pct:.0f}%" if pct >= 12 else ""
        seg += f'<i class="{cls}" style="flex:{val:.4f}">{txt}</i>'
    return f'<div class="ribbon">{seg}</div>'

def _card(entry):
    m, p = entry["match"], entry.get("pred")
    th, ta = entry["home_name"], entry["away_name"]
    bdate, btime = _bp_time(m["date"], m["time_et"])
    status = entry["status"]
    tag = {"done": '<span class="tag done">Lejátszva</span>',
           "proj": '<span class="tag proj">Vetített párosítás</span>',
           "tbd": '<span class="tag proj">Résztvevők később</span>'}.get(status, "")
    if status == "done":
        r = entry["result"]
        mid = f'<div class="score">{r["gh"]}–{r["ga"]}<b>végeredmény</b></div>'
    elif p:
        ts = p["top_scores"][0]
        mid = f'<div class="score">{ts["h"]}–{ts["a"]}<b>várható ({ts["p"]*100:.0f}%)</b></div>'
    else:
        mid = '<div class="score">–<b>n/a</b></div>'
    h = f'''<div class="card">
<div class="head"><div class="tname">{html.escape(th)}</div>{mid}
<div class="tname a">{html.escape(ta)}</div></div>'''
    if p and status != "done":
        h += _ribbon(p)
        h += (f'<div class="legend"><span>{html.escape(th)} győz</span>'
              f'<span>döntetlen</span><span>{html.escape(ta)} győz</span></div>')
    pair = entry.get("pair_share")
    pair_txt = (f'<span>a szimulációk {pair*100:.0f}%-ában ez a párosítás</span>'
                if pair else "")
    h += (f'<div class="meta">{tag}{pair_txt}<span>{STAGE_HU[m["stage"]]}'
          + (f' — {m["group"]} csoport' if m["group"] else "")
          + f'</span><span>{m["date"]} {m["time_et"]} ET'
          f' (Bp: {bdate} {btime})</span><span>{html.escape(m["venue"])}</span>'
          f'<span>#{m["id"]}. mérkőzés — kattints az elemzésért</span></div>')
    body = "".join(f"<p>{html.escape(x)}</p>" for x in entry.get("analysis", []))
    if status == "done" and p:
        body = (f'<p><span class="tag">Modell a meccs előtt</span> 1: {p["p1"]*100:.0f}% · '
                f'X: {p["px"]*100:.0f}% · 2: {p["p2"]*100:.0f}% — tipp: '
                f'{p["top_scores"][0]["h"]}–{p["top_scores"][0]["a"]}</p>') + body
    h += f'<div class="body">{body}</div></div>'
    return h

def _standings_table(rows, teams, mc=None):
    tr = ""
    for r in rows:
        cls = "q" if r["rank"] <= 2 else ("t3" if r["rank"] == 3 else "")
        adv = f'{mc[r["code"]]["r32"]*100:.0f}%' if mc else "–"
        tr += (f'<tr class="{cls}"><td>{r["rank"]}.</td>'
               f'<td>{html.escape(teams[r["code"]]["name"])}</td>'
               f'<td>{r["played"]}</td><td>{r["gf"]}</td><td>{r["ga"]}</td>'
               f'<td>{r["gd"]}</td><td><b>{r["pts"]}</b></td><td>{adv}</td></tr>')
    return ('<table class="st"><tr><th>#</th><th>Csapat</th><th>LM</th><th>LG</th>'
            '<th>KG</th><th>GK</th><th>Pont*</th><th>Tovább%</th></tr>' + tr + "</table>"
            '<div class="note">* A még le nem játszott meccsek <i>várható</i> ponttal '
            'szerepelnek (3·P(győzelem)+P(döntetlen)) — a tabella egyben projekció is. '
            'A Tovább% oszlop a Monte Carlo-szimulációból származó továbbjutási valószínűség. '
            'Zöld sáv: továbbjutó helyek; arany: 3. hely (a 8 legjobb harmadik jut tovább).</div>')

def _mc_section(mc, teams, sims):
    rows = sorted(mc.items(), key=lambda kv: (kv[1]["champion"], kv[1]["final"],
                                              kv[1]["sf"]), reverse=True)
    tr = ""
    for code, p in rows:
        bar = (f'<div style="background:#EDEBE4;height:10px;border-radius:3px;overflow:hidden">'
               f'<div style="width:{max(0.6, p["champion"]*100):.1f}%;height:100%;'
               f'background:linear-gradient(90deg,var(--red),var(--green),var(--blue))"></div></div>')
        tr += (f'<tr><td>{html.escape(teams[code]["name"])}</td>'
               f'<td>{p["group_win"]*100:.0f}%</td><td>{p["r32"]*100:.0f}%</td>'
               f'<td>{p["r16"]*100:.0f}%</td><td>{p["qf"]*100:.0f}%</td>'
               f'<td>{p["sf"]*100:.0f}%</td><td>{p["final"]*100:.0f}%</td>'
               f'<td><b>{p["champion"]*100:.1f}%</b>{bar}</td></tr>')
    return (f'<section class="sect" id="mc"><h2 class="gh disp">Esélyek'
            f'<small>{sims:,} szimulált torna eredménye</small></h2>'
            '<table class="st"><tr><th>Csapat</th><th>Csoport-1.</th><th>32 között</th>'
            '<th>Nyolcaddöntő</th><th>Negyeddöntő</th><th>Elődöntő</th><th>Döntő</th>'
            '<th>Világbajnok</th></tr>' + tr + '</table>'
            '<div class="note">Monte Carlo-szimuláció: minden futás a teljes hátralévő '
            'tornát lejátssza — a csoportmeccsek eredményét a meccsenkénti '
            'valószínűség-eloszlásból sorsolja, a tabellákat és a harmadikok ágra '
            'sorolását futásonként feloldja, kieséses döntetlennél a kalibrált '
            'hosszabbítás/tizenegyes-modellt alkalmazza. A már lejátszott mérkőzések '
            'eredménye rögzített. Részletek: MODEL.md.</div></section>')

def render(entries, tables, teams, generated_at, applied_count, mc=None, sims=0):
    groups = "ABCDEFGHIJKL"
    nav = '<button class="on" onclick="tab(\'today\',this)">Aktuális</button>'
    nav += "".join(f'<button onclick="tab(\'g{g}\',this)">{g} csoport</button>' for g in groups)
    nav += '<button onclick="tab(\'ko\',this)">Kieséses szakasz</button>'
    nav += '<button onclick="tab(\'mc\',this)">Esélyek</button>'

    by_group = {g: [] for g in groups}
    ko, upcoming = [], []
    for e in entries:
        m = e["match"]
        if m["stage"] == "group":
            by_group[m["group"]].append(e)
        else:
            ko.append(e)
        if e["status"] != "done":
            upcoming.append(e)
    upcoming.sort(key=lambda e: (e["match"]["date"], e["match"]["time_et"]))

    sects = '<section class="sect on" id="today"><h2 class="gh disp">Következő mérkőzések'
    sects += '<small>a soron következő 10 meccs előrejelzése</small></h2>'
    sects += "".join(_card(e) for e in upcoming[:10]) + "</section>"

    for g in groups:
        sects += (f'<section class="sect" id="g{g}"><h2 class="gh disp">{g} csoport'
                  f'<small>tabella + mind a 6 mérkőzés</small></h2>'
                  + _standings_table(tables[g], teams, mc)
                  + "".join(_card(e) for e in by_group[g]) + "</section>")

    stage_order = ["r32", "r16", "qf", "sf", "third", "final"]
    sects += '<section class="sect" id="ko">'
    for st in stage_order:
        es = [e for e in ko if e["match"]["stage"] == st]
        if es:
            sects += f'<h2 class="gh disp">{STAGE_HU[st]}</h2>' + "".join(_card(e) for e in es)
    sects += ('<div class="note">A harmadik helyezettek ágra sorolása a FIFA Annex C '
              '495 kombinációjának közelítése (érvényes, de nem feltétlenül az általuk '
              'kiválasztott hozzárendelés) — a végleges párosítást a frissítés a valós '
              'eredmények alapján rögzíti.</div></section>')
    if mc:
        sects += _mc_section(mc, teams, sims)

    return f"""<!DOCTYPE html><html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VB 2026 — ML előrejelző</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div class="tri"><i></i><i></i><i></i></div>
<h1 class="disp">VB 2026 előrejelző<span>Kanada · Mexikó · USA — 104 mérkőzés</span></h1>
<p>Elo + Poisson alapú, naponta inkrementálisan frissülő modell. Minden meccshez:
1X2-valószínűségek, a legvalószínűbb végeredmény és részletes magyar nyelvű indoklás.
Utolsó frissítés: {generated_at} · feldolgozott eredmények: {applied_count} mérkőzés.</p></header>
<nav>{nav}</nav><main>{sects}</main>
<footer>Nem hivatalos, rajongói elemzőoldal — nem áll kapcsolatban a FIFA-val.
A valószínűségek modellbecslések, nem garanciák; szerencsejátékhoz nem ajánlott
döntési alapnak tekinteni. Forrásadatok: eloratings.net, football-data.org, nyilvános
menetrend.</footer>
<script>{JS}</script></body></html>"""
