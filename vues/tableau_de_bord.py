import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import futures as F
from src import liquidite as L
from src import technique as T
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
m20 = db["masi20"].sort_values("date")
if m20.empty:
    ui.page("Tableau de bord")
    st.info("La base est vide. Commencez par importer des bulletins (menu Données → Import des bulletins).")
    st.stop()

tech = T.indicateurs(m20)
z = tech.iloc[-1]
ui.page("Tableau de bord", date_ref=z["date"])

# --- Chiffres clés
debut_annee = m20[m20["date"].dt.year < z["date"].year]
ytd = z["cloture"] / debut_annee["cloture"].iloc[-1] - 1 if not debut_annee.empty else None
semaine = m20[m20["date"] < z["date"] - pd.Timedelta(days=z["date"].weekday())]
wtd = z["cloture"] / semaine["cloture"].iloc[-1] - 1 if not semaine.empty else None
ind = db["indices"]
masi = ind[ind["indice"] == "MASI"].sort_values("date") if not ind.empty else pd.DataFrame()
items = [
    {"lab": "MASI 20", "val": nombre(z["cloture"]), "sub": f"{pct(z['var'])} sur la séance", "sens": z["var"], "gold": True},
    {"lab": "Semaine en cours", "val": pct(wtd), "sub": "depuis la clôture de vendredi", "sens": wtd},
    {"lab": "Depuis le 1er janvier", "val": pct(ytd), "sub": f"référence {date_courte(debut_annee['date'].iloc[-1])}" if ytd is not None else "", "sens": ytd},
    {"lab": "RSI 14", "val": nombre(z["rsi14"], 0), "sub": "surachat" if z["rsi14"] >= 70 else "survente" if z["rsi14"] <= 30 else "zone neutre"},
    {"lab": "Régime (5 séances)", "val": z["regime"] or "–", "sub": pct(z["var_5j"]), "sens": z["var_5j"]},
]
if not masi.empty:
    mz = masi.iloc[-1]
    items.append({"lab": "MASI", "val": nombre(mz["valeur"]), "sub": f"{nombre(mz['var_veille'], signe=True)} % · {date_courte(mz['date'])}",
                  "sens": mz["var_veille"]})
ui.kpis(items)

c1, c2 = st.columns([1.6, 1])
with c1:
    ui.section("MASI 20 · 6 derniers mois")
    st.plotly_chart(G.indice(tech.tail(125), ema=True, rsi=False, h=380), width="stretch", config=G.CFG)
with c2:
    ui.section("Marché à terme · dernière séance")
    f = F.avec_base(F.preparer(db["futures"], db["futures_trades"]), m20)
    if f.empty:
        st.caption("Aucune donnée futures.")
    else:
        d = f["date"].max()
        x = f[f["date"] == d].sort_values("mois_echeance")
        tab = pd.DataFrame({"Contrat": x["ticker"].map(F.libelle), "Clôture": x["cloture"], "Var.": x["var"],
                            "OI": x["open_interest"], "Δ OI": x["delta_oi"], "Base": x["base_pct"]})
        st.caption(f"Séance du {date_courte(d)} · volume {mad(x['volume'].sum())} · {int(x['open_interest'].sum())} positions ouvertes")
        st.dataframe(ui.style_table(tab, pct_cols=["Var.", "Base"], signe_cols=["Δ OI"],
                                    fmt={"Clôture": lambda v: nombre(v), "OI": lambda v: nombre(v, 0),
                                         "Δ OI": lambda v: nombre(v, 0, True)}),
                     width="stretch", hide_index=True)
        ui.section("Signaux techniques")
        for s in T.signaux(tech):
            cls = {"Haussier": "up", "Baissier": "down", "BOOM": "up", "SLUMP": "down"}.get(s["Verdict"], "flat")
            st.markdown(f"<span class='m20-pill {cls}'>{s['Verdict']}</span> **{s['Famille']}** · {s['Lecture']}",
                        unsafe_allow_html=True)

# --- Composants du dernier bulletin
act = db["actions"]
if not act.empty:
    dcote = act["date"].max()
    p = K.panel(act, db["composition"], dcote, dcote)
    if not p.empty:
        ui.section(f"Composants du MASI 20 · séance du {date_courte(dcote)}")
        if dcote < z["date"]:
            ui.note(f"Dernier bulletin de la cote importé : {date_courte(dcote)}. L'indice va jusqu'au {date_courte(z['date'])}.")
        c1, c2 = st.columns([1.4, 1])
        with c1:
            st.plotly_chart(G.carte_composants(p.assign(cloture=p["cours_ref_suivant"]), h=420), width="stretch", config=G.CFG)
        with c2:
            top = p.sort_values("contribution", ascending=False)
            for titre, d in (("Ont tiré l'indice vers le haut", top.head(5)), ("Vers le bas", top.tail(5).iloc[::-1])):
                st.markdown(f"**{titre}**")
                st.dataframe(ui.style_table(pd.DataFrame({"Valeur": d["nom"], "Var.": d["rendement"],
                                                          "Contrib. (pb)": d["contribution"] * 1e4}),
                                            pct_cols=["Var."], signe_cols=["Contrib. (pb)"],
                                            fmt={"Contrib. (pb)": lambda v: nombre(v, 1, True)}),
                             width="stretch", hide_index=True)
        m = L.mesures_jour(K.panel(act, db["composition"]), db["flux"])
        li = L.indice_liquidite(m)
        if not li.empty:
            v = li.iloc[-1]
            ok, n = L.note_disponible(m)
            sc = L.score_valeurs(m, dcote, dcote)
            ui.kpis([{"lab": "Note de liquidité MASI 20", "val": f"{nombre(v['indice_lisse'], 0)} / 100" if ok else "En constitution",
                      "sub": "vs séances précédentes" if ok else f"{n} / {L.SEANCES_MIN_NOTE} séances importées", "gold": True},
                     {"lab": "Valeur la plus liquide", "val": sc.iloc[0]["nom"].title(), "sub": f"score {sc.iloc[0]['score']:.0f} / 100"},
                     {"lab": "Volume des 20 valeurs", "val": mad(m[m['date'] == dcote]['volume'].sum()), "sub": "marché central"},
                     {"lab": "Hausses / baisses", "val": f"{int((p['rendement'] > 0).sum())} / {int((p['rendement'] < 0).sum())}",
                      "sub": "sur 20 valeurs"}])
ui.pied()
