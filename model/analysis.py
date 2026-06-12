# -*- coding: utf-8 -*-
"""Hungarian match-analysis text generation — professional analyst register.
Deterministic but varied: template choice is keyed to the match id, so the 72
group analyses don't read identically, yet every regeneration is reproducible.
"""

# --- Confidence (NFL projektből adaptálva: jel-erősség + adatminőség + minta) ---
W_MARGIN, W_DATA, W_SAMPLE = 0.55, 0.30, 0.15
CONF_LABELS = [(0.62, "MAGAS"), (0.45, "KÖZEPES"), (0.0, "ALACSONY")]

def confidence(pred, th, ta):
    ps = sorted((pred["p1"], pred["px"], pred["p2"]), reverse=True)
    margin = min(1.0, (ps[0] - ps[1]) / 0.45)
    data = 1.0
    for t in (th, ta):
        if t.get("elo_estimated") and t.get("played", 0) < 3:
            data -= 0.35
    sample = min(1.0, (th.get("played", 0) + ta.get("played", 0)) / 6.0)
    score = W_MARGIN * margin + W_DATA * max(0.0, data) + W_SAMPLE * sample
    label = next(l for thr, l in CONF_LABELS if score >= thr)
    return round(score, 3), label

STAGE_HU = {"group":"Csoportkör","r32":"Nyolcaddöntő-selejtező (32 között)",
            "r16":"Nyolcaddöntő","qf":"Negyeddöntő","sf":"Elődöntő",
            "third":"Bronzmérkőzés","final":"DÖNTŐ"}

def _gap_phrase(d, h, a, k):
    opts = [
        [f"Erőviszonyok: a mérkőzés kimenetele szempontjából jelentős, 250 Elo-pontot meghaladó különbség áll fenn {h} javára; {a} pontszerzése statisztikai értelemben kivételes kimenetelnek számítana.",
         f"Erőviszonyok: {h} kiemelt esélyesként lép pályára; az aktuális erősorrend alapján {a} eredményes szereplése jelentős meglepetést jelentene."],
        [f"Erőviszonyok: {h} mérhető, de nem behozhatatlan előnnyel rendelkezik; {a} szervezett teljesítménnyel reális eséllyel pályázhat pontszerzésre.",
         f"Erőviszonyok: az erősorrend {h} felé billen, a különbség azonban abban a tartományban van, ahol a napi forma és a taktikai felkészültség érdemben módosíthatja a kimenetelt."],
        [f"Erőviszonyok: a két csapat aktuális erőssége közel azonos; a mérkőzést várhatóan a részletek — pontrúgás-hatékonyság, a cserepad minősége, egyéni megoldások — döntik el.",
         f"Erőviszonyok: kiegyenlített párosítás, amelyben egyik fél sem rendelkezik statisztikailag meghatározó előnnyel; a modell kimeneti eloszlása ennek megfelelően széles."],
    ]
    tier = 0 if d >= 250 else (1 if d >= 100 else 2)
    return opts[tier][k % 2]

def _form_phrase(code, name, observed_for_team):
    res = observed_for_team.get(code, [])
    if not res:
        return None
    w = sum(1 for r in res if r == "W"); d = sum(1 for r in res if r == "D")
    l = len(res) - w - d
    return (f"{name} tornán mutatott mérlege: {w} győzelem, {d} döntetlen, "
            f"{l} vereség — ez a teljesítmény a frissített erősség-mutatókban már szerepel.")

LINE_HU = ["kapusposzt", "védelem", "középpálya", "támadósor"]

def _matchup_para(th, ta, channels, player_form):
    parts = []
    ch, ca = th.get("lines"), ta.get("lines")
    if ch and ca:
        c = lambda ln: [v - sum(ln) / 4.0 for v in ln]
        h_c, a_c = c(ch), c(ca)
        edges = [(h_c[3] - (a_c[1] + a_c[0]) / 2, f"{th['name']} támadósora a(z) {ta['name']}-védelem ellen"),
                 (a_c[3] - (h_c[1] + h_c[0]) / 2, f"{ta['name']} támadósora a(z) {th['name']}-védelem ellen"),
                 (h_c[2] - a_c[2], f"a középpálya-csata {th['name']} javára"),
                 (a_c[2] - h_c[2], f"a középpálya-csata {ta['name']} javára")]
        best = max(edges, key=lambda e: e[0])
        if best[0] >= 1.0:
            parts.append(f"A profil-összevetés legnagyobb aszimmetriája: {best[1]} "
                         f"(+{best[0]:.1f} centírozott vonal-pont) — a modell ezt a "
                         f"gólvárakozásban korlátozott mértékben árazza.")
        else:
            parts.append("A két csapat erősség-profilja kiegyenlített, kiugró "
                         "vonal-aszimmetria nélkül.")
    for t in (th, ta):
        st = (channels or {}).get(t["code"])
        if st and st["n"] >= 1:
            parts.append(f"{t['name']} tornaátlaga: {st['sot_f']:.1f} kapura lövés és "
                         f"{st['cor_f']:.1f} szöglet meccsenkként, miközben {st['sot_a']:.1f} "
                         f"kapura lövést enged.")
        pf = (player_form or {}).get(t["code"])
        if pf:
            parts.append(f"{t['name']} eddigi legjobbra értékelt játékosa a tornán: "
                         f"{pf['name']} ({pf['rating']:.2f}).")
    return " ".join(parts) if parts else None

def build(m, pred, th, ta, table_ctx, observed_form, projected=False,
          channels=None, player_form=None):
    k = m["id"]
    d = abs(th["elo"] - ta["elo"])
    fav = th if pred["p1"] >= pred["p2"] else ta
    dog = ta if fav is th else th
    paras = []

    intro = _gap_phrase(d, fav["name"], dog["name"], k)
    if projected:
        intro = ("Megjegyzés: vetített párosítás — a végleges résztvevőket a korábbi "
                 "körök tényleges eredményei határozzák meg. ") + intro
    paras.append(intro)

    paras.append(f"Játékkép — {th['name']}: {th['style']} {ta['name']}: {ta['style']}")

    paras.append(f"Meghatározó játékosok — {th['name']}: {', '.join(th['players'])}; "
                 f"{ta['name']}: {', '.join(ta['players'])}.")

    forms = [f for f in (_form_phrase(th["code"], th["name"], observed_form),
                         _form_phrase(ta["code"], ta["name"], observed_form)) if f]
    if forms:
        paras.append(" ".join(forms))
    mp = _matchup_para(th, ta, channels, player_form)
    if mp:
        paras.append("Párharc-kép — " + mp)
    if table_ctx:
        paras.append(table_ctx)

    news = []
    if th.get("news"): news.append(f"{th['name']}: {th['news']}")
    if ta.get("news"): news.append(f"{ta['name']}: {ta['news']}")
    if news:
        paras.append("Keretinformációk, aktualitások — " + " ".join(news))

    ts = pred["top_scores"]
    tip = pred.get("tip", ts[0])
    cls_p = max(pred["p1"], pred["px"], pred["p2"])
    cls_txt = (f"{th['name']} győzelme" if cls_p == pred["p1"] else
               ("döntetlen" if cls_p == pred["px"] else f"{ta['name']} győzelme"))
    verdict = (f"Modellverdikt: {th['name']} győzelmi valószínűsége {pred['p1']*100:.0f}%, "
               f"a döntetlené {pred['px']*100:.0f}%, {ta['name']} győzelméé {pred['p2']*100:.0f}%. "
               f"A legvalószínűbb kimenetel {cls_txt} ({cls_p*100:.0f}%), ezen belül a "
               f"legvalószínűbb végeredmény {tip['h']}–{tip['a']} ({tip['p']*100:.1f}%). "
               f"Az eloszlás egészének legsűrűbb pontjai: "
               f"{ts[0]['h']}–{ts[0]['a']} ({ts[0]['p']*100:.1f}%), "
               f"{ts[1]['h']}–{ts[1]['a']} ({ts[1]['p']*100:.1f}%), "
               f"{ts[2]['h']}–{ts[2]['a']} ({ts[2]['p']*100:.1f}%). "
               f"Indoklás: a becslés alapja a várható gólszám-pár ({pred['lh']:.2f}, "
               f"illetve {pred['la']:.2f}), amelyet az aktuális Elo-erőkülönbség, a tornán "
               f"mért támadó- és védekezőteljesítmény, valamint a pályaelőny együttesen "
               f"határoz meg; a pontos eredmény egy nagy szórású eloszlás móduszaként "
               f"értelmezendő, nem determinisztikus előrejelzésként. További eloszlási "
               f"mutatók: mindkét csapat szerez gólt {pred.get('btts',0)*100:.0f}%, "
               f"2,5 gól feletti összgólszám {pred.get('over25',0)*100:.0f}%.")
    if m["stage"] != "group" and "favorite" in pred:
        favt = th if pred["favorite"] == th["code"] else ta
        p = pred["adv_h"] if pred["favorite"] == th["code"] else pred["adv_a"]
        verdict += (f" Egyenes kieséses mérkőzés lévén döntetlen állás esetén hosszabbítás, "
                    f"illetve tizenegyespárbaj következik; ezek figyelembevételével a "
                    f"továbbjutásra esélyesebb fél {favt['name']} ({p*100:.0f}%).")
    paras.append(verdict)
    return paras
