import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import config as C
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
act, flux, compo = db["actions"], db["flux"], db["composition"]
if act.empty:
    ui.page("Composants")
    st.info("Aucun bulletin de la cote importé.")
    st.stop()
dates = sorted(act["date"].unique(), reverse=True)
ui.page("Composants", "Variations, poids, contributions et volumes des valeurs du MASI 20 et du MASI", dates[0])

c = st.columns([1, 1.3, 1])
univers = c[0].segmented_control("Univers", ["MASI 20", "MASI (toutes les actions)"], default="MASI 20")
d = c[1].selectbox("Séance", dates, format_func=lambda x: date_courte(pd.Timestamp(x)))
d = pd.Timestamp(d)
fen = c[2].segmented_control("Période", ["Séance", "Semaine"], default="Séance")
debut = d - pd.Timedelta(days=d.weekday()) if fen == "Semaine" else d

if univers == "MASI 20":
    p = K.panel(act, compo, debut, d)
    b = K.bilan_periode(p, flux)
    n_s = p["date"].nunique()
    if fen == "Semaine":
        st.caption(f"Semaine du {date_courte(debut)} au {date_courte(d)} · {n_s} séance(s) de bulletins disponibles")
    pub = db["indices"]
    pub = pub[(pub["indice"] == "MASI 20") & (pub["date"] >= debut) & (pub["date"] <= d)]
    var_pub = (1 + pub["var_veille"] / 100).prod() - 1 if not pub.empty else None
    ui.kpis([
        {"lab": "Hausses / baisses", "val": f"{int((b['rendement'] > 0).sum())} / {int((b['rendement'] < 0).sum())}", "sub": "sur 20 valeurs"},
        {"lab": "Variation reconstituée", "val": pct(b["contribution"].sum()), "sens": b["contribution"].sum(),
         "sub": f"publiée : {pct(var_pub)}" if var_pub is not None else ""},
        {"lab": "Volume des 20 valeurs", "val": mad(b["volume"].sum()), "sub": "marché central"},
        {"lab": "Grosses transactions", "val": pct(b["volume_gros"].sum() / b["volume"].sum(), 0, False) if b["volume"].sum() else "–",
         "sub": "du volume (niveaux ≥ 5 M MAD)"},
        {"lab": "Marché de blocs", "val": mad(b["volume_blocs"].sum()), "sub": "exclu des volumes"},
    ])
    c1, c2 = st.columns([1.35, 1])
    with c1:
        ui.section("Carte des 20 valeurs (surface = poids, couleur = variation)")
        st.plotly_chart(G.carte_composants(b), width="stretch", config=G.CFG)
    with c2:
        ui.section("Contributions à la variation de l'indice")
        st.plotly_chart(G.contributions(b, h=520), width="stretch", config=G.CFG)
    ui.section("Détail des valeurs")
    tab = pd.DataFrame({"Valeur": b["nom"], "Secteur": b["secteur"], "Cours": b["cloture"], "Variation": b["rendement"],
                        "Poids": b["poids"], "Contrib. (pb)": b["contribution_pb"], "Volume": b["volume"],
                        "Part du volume": b["part_volume"], "Vol./poids": b["volume_sur_poids"],
                        "Haut annuel": b["haut_annuel"], "Bas annuel": b["bas_annuel"]})
    st.dataframe(ui.style_table(tab, pct_cols=["Variation"], signe_cols=["Contrib. (pb)"],
                                fmt={"Cours": lambda v: nombre(v), "Poids": lambda v: pct(v, 1, False),
                                     "Contrib. (pb)": lambda v: nombre(v, 1, True), "Volume": lambda v: mad(v),
                                     "Part du volume": lambda v: pct(v, 1, False), "Vol./poids": lambda v: nombre(v, 1) + "×",
                                     "Haut annuel": lambda v: nombre(v), "Bas annuel": lambda v: nombre(v)}),
                 width="stretch", hide_index=True, height=740)
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Par secteur")
        s = K.par_secteur(b)
        st.dataframe(ui.style_table(pd.DataFrame({"Secteur": s["secteur"], "Poids": s["poids"], "Contribution (pb)": s["contribution_pb"],
                                                  "Part du volume": s["part_volume"]}), signe_cols=["Contribution (pb)"],
                                    fmt={"Poids": lambda v: pct(v, 1, False), "Contribution (pb)": lambda v: nombre(v, 1, True),
                                         "Part du volume": lambda v: pct(v, 1, False)}), width="stretch", hide_index=True)
    with c2:
        ui.section("Où va l'argent")
        st.plotly_chart(G.volume_poids(b, h=380), width="stretch", config=G.CFG)

    with st.expander("Contrôle des poids : poids implicites calibrés sur l'indice publié"):
        st.write("Les poids affichés sont approchés : nombre de titres × cours × facteur de flottant (table de composition). "
                 "Cette calibration cherche les poids qui reproduisent le mieux les variations publiées du MASI 20 ; "
                 "elle demande au moins 15 séances de bulletins.")
        res = K.poids_implicites(K.panel(act, compo), db["masi20"])
        if res is None:
            st.info(f"Pas encore assez de séances de bulletins ({act['date'].nunique()} sur 15 nécessaires).")
        else:
            pi, rmse, n = res
            comp = b[["isin", "nom", "poids"]].merge(pi[["isin", "poids_implicite"]], on="isin")
            comp["ratio"] = comp["poids_implicite"] / comp["poids"]
            st.caption(f"Calibré sur {n} séances · erreur moyenne {nombre(rmse, 1)} pb par séance. "
                       "Un ratio nettement inférieur à 1 suggère un flottant réduit.")
            st.dataframe(comp, width="stretch", hide_index=True)
else:
    a = act[(act["date"] >= debut) & (act["date"] <= d)].copy()
    a["rendement"] = a["cours_ref_suivant"] / a["cours_ref"] - 1
    g = a.sort_values("date").groupby(["isin", "nom", "secteur_code"], as_index=False).agg(
        rendement=("rendement", lambda s: (1 + s.fillna(0)).prod() - 1), cloture=("cours_ref_suivant", "last"),
        capi=("nb_titres", "last"), cours=("cours_ref_suivant", "last"), statut=("statut", "last"))
    g["capi"] = g["capi"] * g["cours"]
    g["secteur"] = g["secteur_code"].map(C.SECTEURS).fillna(g["secteur_code"])
    v = flux[(flux["date"] >= debut) & (flux["date"] <= d) & (flux["marche"] == "central")].groupby("isin")["volume"].sum()
    g["volume"] = g["isin"].map(v).fillna(0)
    g["masi20"] = g["isin"].isin(K.composition_au(compo, d)["isin"])
    ui.kpis([{"lab": "Actions cotées", "val": str(len(g)), "sub": "dans le bulletin"},
             {"lab": "Hausses / baisses", "val": f"{int((g['rendement'] > 0).sum())} / {int((g['rendement'] < 0).sum())}",
              "sub": f"{int((g['rendement'] == 0).sum())} inchangées"},
             {"lab": "Volume (central)", "val": mad(g["volume"].sum()), "sub": "toutes actions"},
             {"lab": "Part du MASI 20", "val": pct(g.loc[g["masi20"], "volume"].sum() / g["volume"].sum(), 0, False) if g["volume"].sum() else "–",
              "sub": "du volume"}])
    ui.section("Carte du marché (surface = capitalisation, couleur = variation)")
    st.plotly_chart(G.carte_composants(g, taille="capi", h=620), width="stretch", config=G.CFG)
    ui.section("Toutes les actions")
    tab = pd.DataFrame({"Valeur": g["nom"], "MASI 20": g["masi20"].map({True: "●", False: ""}), "Secteur": g["secteur"],
                        "Cours": g["cloture"], "Variation": g["rendement"], "Capitalisation": g["capi"], "Volume": g["volume"],
                        "Statut": g["statut"]}).sort_values("Variation", ascending=False)
    st.dataframe(ui.style_table(tab, pct_cols=["Variation"], fmt={"Cours": lambda v: nombre(v), "Capitalisation": lambda v: mad(v),
                                                                  "Volume": lambda v: mad(v)}),
                 width="stretch", hide_index=True, height=700)
ui.pied()
