# -*- coding: utf-8 -*-
"""Hungarian match-analysis text generation — professional analyst register.
Deterministic but varied: template choice is keyed to the match id, so the 72
group analyses don't read identically, yet every regeneration is reproducible.
"""

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

def build(m, pred, th, ta, table_ctx, observed_form, projected=False):
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
    if table_ctx:
        paras.append(table_ctx)

    news = []
    if th.get("news"): news.append(f"{th['name']}: {th['news']}")
    if ta.get("news"): news.append(f"{ta['name']}: {ta['news']}")
    if news:
        paras.append("Keretinformációk, aktualitások — " + " ".join(news))

    ts = pred["top_scores"]
    verdict = (f"Modellverdikt: {th['name']} győzelmi valószínűsége {pred['p1']*100:.0f}%, "
               f"a döntetlené {pred['px']*100:.0f}%, {ta['name']} győzelméé {pred['p2']*100:.0f}%. "
               f"A legvalószínűbb végeredmény {ts[0]['h']}–{ts[0]['a']} "
               f"({ts[0]['p']*100:.1f}%); a következő legvalószínűbb kimenetelek "
               f"{ts[1]['h']}–{ts[1]['a']} ({ts[1]['p']*100:.1f}%) és "
               f"{ts[2]['h']}–{ts[2]['a']} ({ts[2]['p']*100:.1f}%). "
               f"Indoklás: a becslés alapja a várható gólszám-pár ({pred['lh']:.2f}, "
               f"illetve {pred['la']:.2f}), amelyet az aktuális Elo-erőkülönbség, a tornán "
               f"mért támadó- és védekezőteljesítmény, valamint a pályaelőny együttesen "
               f"határoz meg; a pontos eredmény egy nagy szórású eloszlás móduszaként "
               f"értelmezendő, nem determinisztikus előrejelzésként.")
    if m["stage"] != "group" and "favorite" in pred:
        favt = th if pred["favorite"] == th["code"] else ta
        p = pred["adv_h"] if pred["favorite"] == th["code"] else pred["adv_a"]
        verdict += (f" Egyenes kieséses mérkőzés lévén döntetlen állás esetén hosszabbítás, "
                    f"illetve tizenegyespárbaj következik; ezek figyelembevételével a "
                    f"továbbjutásra esélyesebb fél {favt['name']} ({p*100:.0f}%).")
    paras.append(verdict)
    return paras
