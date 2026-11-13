import pandas as pd
import streamlit as st

from src import charts as G
from src import technique as T
from src import ui
from src.fmt import date_courte, nombre, pct

db = ui.db()
m20 = db["masi20"].sort_values("date")
if m20.empty:
    ui.page("Indice & technique")
    st.info("Aucune donnée. Importez des bulletins.")
    st.stop()
tech = T.indicateurs(m20)
ui.page("Indice & technique", "Le MASI 20 et ses indicateurs, recalculés à chaque séance importée", tech["date"].iloc[-1])

c = st.columns([2.2, 1, 1, 1, 1])
periode = c[0].segmented_control("Période", ["1 mois", "3 mois", "6 mois", "1 an", "Tout"], default="6 mois")
ema = c[1].toggle("EMA 20 / 40", True)
boll = c[2].toggle("Bollinger", False)
fibo = c[3].toggle("Fibonacci", False)
rsi = c[4].toggle("RSI", True)
n = {"1 mois": 21, "3 mois": 63, "6 mois": 126, "1 an": 250}.get(periode or "6 mois", len(tech))
vue = tech.tail(n)
fib = T.fibonacci(tech, fenetre=min(120, len(tech))) if fibo and len(tech) > 20 else None
st.plotly_chart(G.indice(vue, ema=ema, bollinger=boll, fib=fib, rsi=rsi), width="stretch", config=G.CFG)
manq = vue["plus_haut"].isna().sum() if "plus_haut" in vue else len(vue)
if manq:
    ui.note(f"{manq} séance(s) sans plus haut ni plus bas (absents du bulletin) : l'ATR utilise alors l'écart de clôture à clôture. "
            "Vous pouvez les saisir dans la page Import.")

c1, c2 = st.columns([1.3, 1])
with c1:
    ui.section("Lecture technique")
    sig = pd.DataFrame(T.signaux(tech))
    st.dataframe(sig, width="stretch", hide_index=True)
    if len(tech) > 20:
        fb = T.fibonacci(tech, fenetre=min(120, len(tech)))
        (r_s, v_s), (r_r, v_r) = T.niveaux_proches(tech["cloture"].iloc[-1], fb)
        ui.kpis([
            {"lab": "Support Fibonacci", "val": nombre(v_s, 0) if v_s else "–",
             "sub": f"niveau {nombre(r_s * 100, 1)} %" if r_s is not None else ""},
            {"lab": "Résistance Fibonacci", "val": nombre(v_r, 0) if v_r else "–",
             "sub": f"niveau {nombre(r_r * 100, 1)} %" if r_r is not None else ""},
            {"lab": "Plus haut / plus bas (120 s.)", "val": f"{nombre(fb['haut'], 0)} / {nombre(fb['bas'], 0)}",
             "sub": f"tendance {fb['tendance']}"},
        ])
with c2:
    ui.section("Bougies hebdomadaires")
    st.plotly_chart(G.bougies_hebdo(T.hebdo(tech).tail(26)), width="stretch", config=G.CFG)

ui.section("Dernières séances")
x = tech.tail(15).iloc[::-1]
tab = pd.DataFrame({"Date": x["date"].dt.strftime("%d/%m/%Y"), "Clôture": x["cloture"], "Var.": x["var"],
                    "Plus haut": x["plus_haut"], "Plus bas": x["plus_bas"], "RSI 14": x["rsi14"],
                    "EMA 20": x["ema20"], "ATR 14": x["atr14"], "%B": x["bb_pctb"], "Régime": x["regime"],
                    "Source": x.get("source")})
st.dataframe(ui.style_table(tab, pct_cols=["Var."], fmt={k: (lambda v: nombre(v)) for k in
                                                          ["Clôture", "Plus haut", "Plus bas", "EMA 20", "ATR 14", "%B"]}
                            | {"RSI 14": lambda v: nombre(v, 0)}), width="stretch", hide_index=True)

ind = db["indices"]
if not ind.empty:
    d = ind["date"].max()
    ui.section(f"Tous les indices de la Bourse · séance du {date_courte(d)}")
    y = ind[ind["date"] == d]
    st.dataframe(ui.style_table(pd.DataFrame({"Indice": y["indice"], "Valeur": y["valeur"],
                                              "Var. veille": y["var_veille"] / 100, "Depuis le 31/12": y["var_ytd"] / 100}),
                                pct_cols=["Var. veille", "Depuis le 31/12"], fmt={"Valeur": lambda v: nombre(v)}),
                 width="stretch", hide_index=True, height=420)
ui.pied()
