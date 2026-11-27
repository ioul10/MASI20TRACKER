import numpy as np
import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import config as C
from src import grosses as GT
from src import marche as M
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
act, flux, compo = db["actions"], db["flux"], db["composition"]
if act.empty:
    ui.page("Composants", theme="bourse")
    st.info("Aucun bulletin de la cote importé.")
    st.stop()
dates = sorted(act["date"].unique(), reverse=True)
ui.page("Composants", "Indices et volumes des valeurs du MASI 20 et de tout le marché", dates[0], theme="bourse")

# ------------------------------------------------------------------ choix communs aux deux onglets
vue = st.segmented_control("Vue", ["Indices", "Volumes"], default="Indices", key="vue_compo",
                           label_visibility="collapsed") or "Indices"
c = st.columns([1.3, 1.2, 1])
univers = c[0].segmented_control("Univers", ["MASI 20", "MASI (toutes les actions)"], default="MASI 20", key="univ_compo") or "MASI 20"
d = pd.Timestamp(c[1].selectbox("Séance", dates, format_func=lambda x: date_courte(pd.Timestamp(x)), key="seance_compo"))
fen = c[2].segmented_control("Période", ["Séance", "Semaine"], default="Séance", key="periode_compo") or "Séance"
debut = d - pd.Timedelta(days=d.weekday()) if fen == "Semaine" else d
libelle_periode = (f"semaine du {date_courte(debut)} au {date_courte(d)}" if fen == "Semaine"
                   else f"séance du {date_courte(d)}")
est20 = univers == "MASI 20"

p = K.panel(act, compo, debut, d)
b = K.bilan_periode(p, flux)
vm = M.vision_masi(db, debut, d)
if fen == "Semaine":
    st.caption(f"Semaine du {date_courte(debut)} au {date_courte(d)} · {p['date'].nunique()} séance(s) de bulletins disponibles")

# toutes les actions sur la période (univers MASI)
a = act[(act["date"] >= debut) & (act["date"] <= d)].copy()
a["rendement"] = a["cours_ref_suivant"] / a["cours_ref"] - 1
toutes = a.sort_values("date").groupby(["isin", "nom", "secteur_code"], as_index=False).agg(
    rendement=("rendement", lambda s: (1 + s.fillna(0)).prod() - 1), cloture=("cours_ref_suivant", "last"),
    nb_titres=("nb_titres", "last"), statut=("statut", "last"))
toutes["capi"] = toutes["nb_titres"] * toutes["cloture"]
toutes["secteur"] = toutes["secteur_code"].map(C.SECTEURS).fillna(toutes["secteur_code"])
cen = flux[(flux["date"] >= debut) & (flux["date"] <= d) & (flux["marche"] == "central")]
vol = cen.groupby("isin").agg(volume=("volume", "sum"), volume_gros=("volume_gros", "sum"), nb=("nb", "sum"))
toutes = toutes.merge(vol, on="isin", how="left").fillna({"volume": 0, "volume_gros": 0, "nb": 0})
toutes["masi20"] = toutes["isin"].isin(K.composition_au(compo, d)["isin"])

# ================================================================== INDICES
if vue == "Indices":
    if est20:
        pub = db["indices"]
        pub = pub[(pub["indice"] == "MASI 20") & (pub["date"] >= debut) & (pub["date"] <= d)]
        var_pub = vm.get("var_masi20_publie")
        ui.kpis([
            {"lab": f"MASI 20 · {fen.lower()}", "val": pct(var_pub), "sens": var_pub, "gold": True,
             "sub": f"reconstituée : {pct(b['contribution'].sum())}"},
            {"lab": f"MASI · {fen.lower()}", "val": pct(vm.get("var")), "sens": vm.get("var"),
             "sub": f"depuis le 31/12 : {pct(vm.get('var_ytd'))}"},
            {"lab": "Hausses / baisses", "val": f"{int((b['rendement'] > 0).sum())} / {int((b['rendement'] < 0).sum())}",
             "sub": "sur les 20 valeurs"},
            {"lab": "Tire l'indice", "val": b.iloc[0]["nom"].title(), "sub": f"{nombre(b.iloc[0]['contribution_pb'], 1, True)} pb"},
            {"lab": "Freine l'indice", "val": b.iloc[-1]["nom"].title(), "sub": f"{nombre(b.iloc[-1]['contribution_pb'], 1, True)} pb"},
        ])
        c1, c2 = st.columns([1.35, 1])
        with c1:
            ui.section("Carte des 20 valeurs (surface = poids, couleur = variation)")
            st.plotly_chart(G.carte_composants(b), width="stretch", config=G.CFG)
        with c2:
            ui.section("Contributions à la variation de l'indice")
            st.plotly_chart(G.contributions(b, h=520), width="stretch", config=G.CFG)
        ui.section(f"Variation des 20 valeurs · {libelle_periode}")
        tab = pd.DataFrame({"Valeur": b["nom"].str.title(), "Secteur": b["secteur"], "Cours": b["cloture"],
                            "Variation": b["rendement"], "Poids": b["poids"], "Contrib. (pb)": b["contribution_pb"],
                            "Haut annuel": b["haut_annuel"], "Bas annuel": b["bas_annuel"],
                            "Écart au haut annuel": b["cloture"] / b["haut_annuel"] - 1})
        st.dataframe(ui.style_table(tab, pct_cols=["Variation", "Écart au haut annuel"], signe_cols=["Contrib. (pb)"],
                                    fmt={"Cours": lambda v: nombre(v), "Poids": lambda v: pct(v, 1, False),
                                         "Contrib. (pb)": lambda v: nombre(v, 1, True),
                                         "Haut annuel": lambda v: nombre(v), "Bas annuel": lambda v: nombre(v)}),
                     width="stretch", hide_index=True, height=38 * 21)
        ui.section("Les secteurs dans le MASI 20")
        s = K.par_secteur(b)
        st.dataframe(ui.style_table(pd.DataFrame({"Secteur": s["secteur"], "Poids": s["poids"],
                                                  "Contribution (pb)": s["contribution_pb"]}), signe_cols=["Contribution (pb)"],
                                    fmt={"Poids": lambda v: pct(v, 1, False), "Contribution (pb)": lambda v: nombre(v, 1, True)}),
                     width="stretch", hide_index=True)
    else:
        ui.kpis([{"lab": f"MASI · {fen.lower()}", "val": pct(vm.get("var")), "sens": vm.get("var"), "gold": True,
                  "sub": f"{nombre(vm.get('valeur'))} pts · depuis le 31/12 : {pct(vm.get('var_ytd'))}"},
                 {"lab": f"MASI 20 · {fen.lower()}", "val": pct(vm.get("var_masi20_publie")), "sens": vm.get("var_masi20_publie")},
                 {"lab": "Actions cotées", "val": str(len(toutes)), "sub": "dans le bulletin"},
                 {"lab": "Hausses / baisses", "val": f"{int((toutes['rendement'] > 0).sum())} / {int((toutes['rendement'] < 0).sum())}",
                  "sub": f"{int((toutes['rendement'] == 0).sum())} inchangées"}])
        ui.section("Carte du marché (surface = capitalisation, couleur = variation)")
        st.plotly_chart(G.carte_composants(toutes, taille="capi", h=620), width="stretch", config=G.CFG)
        ui.section(f"Toutes les actions · {libelle_periode}")
        tab = pd.DataFrame({"Valeur": toutes["nom"], "MASI 20": toutes["masi20"].map({True: "●", False: ""}),
                            "Secteur": toutes["secteur"], "Cours": toutes["cloture"], "Variation": toutes["rendement"],
                            "Capitalisation": toutes["capi"], "Statut": toutes["statut"]}).sort_values("Variation", ascending=False)
        st.dataframe(ui.style_table(tab, pct_cols=["Variation"], fmt={"Cours": lambda v: nombre(v), "Capitalisation": lambda v: mad(v)}),
                     width="stretch", hide_index=True, height=600)

    # indices sectoriels publiés (les mêmes pour les deux univers)
    sect = vm.get("secteurs", pd.DataFrame())
    ui.section(f"Indices sectoriels · {libelle_periode}")
    if sect is None or sect.empty:
        st.info("Aucun indice sectoriel dans les bulletins importés.")
    else:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.plotly_chart(G.secteurs_barres(sect), width="stretch", config=G.CFG)
        with c2:
            st.dataframe(ui.style_table(pd.DataFrame({"Secteur": sect["secteur"], "Valeur": sect["valeur"],
                                                      fen: sect["var"], "Depuis le 31/12": sect["var_ytd"]}),
                                        pct_cols=[fen, "Depuis le 31/12"], fmt={"Valeur": lambda v: nombre(v)}),
                         width="stretch", hide_index=True, height=24 * len(sect) + 80)
        st.caption("Indices sectoriels publiés par la Bourse de Casablanca dans le bulletin de la cote.")

    if est20:
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

# ================================================================== VOLUMES
else:
    # volume habituel : moyenne par séance des 20 séances précédant la période
    tous_jours = sorted(flux.loc[flux["marche"] == "central", "date"].unique())
    avant = [x for x in tous_jours if x < debut][-20:]
    n_per = cen["date"].nunique()
    prec = flux[(flux["marche"] == "central") & flux["date"].isin(avant)].groupby("isin")["volume"].sum() / max(len(avant), 1)

    if est20:
        base = b.copy()
        base["volume_gros"] = base["volume_gros"].fillna(0)
        v20, g20 = base["volume"].sum(), base["volume_gros"].sum()
        prec20 = prec.reindex(base["isin"]).fillna(0).sum()
        vs = (v20 / n_per) / prec20 if prec20 and n_per else np.nan
        ui.kpis([
            {"lab": f"Volume des 20 valeurs · {fen.lower()}", "val": mad(v20), "gold": True,
             "sub": f"{pct(v20 / vm['volume'], 0, False)} du marché central" if vm.get("volume") else "marché central"},
            {"lab": "Par rapport à l'habituel", "val": f"{nombre(vs, 1)} ×" if pd.notna(vs) else "–",
             "sub": f"volume par séance vs moyenne des {len(avant)} séances précédentes"},
            {"lab": "Volume courant", "val": mad(v20 - g20), "sub": "hors grosses transactions"},
            {"lab": "Grosses transactions", "val": pct(g20 / v20, 0, False) if v20 else "–",
             "sub": GT.lecture(g20 / v20 if v20 else None) + " · détail : page Grosses transactions"},
            {"lab": "Marché de blocs", "val": mad(base["volume_blocs"].sum()), "sub": "exclu des volumes"},
        ])
    else:
        vs = vm.get("volume_vs")
        ui.kpis([
            {"lab": f"Volume du marché · {fen.lower()}", "val": mad(vm.get("volume")), "gold": True, "sub": "marché central, toutes les actions"},
            {"lab": "Par rapport à l'habituel", "val": f"{nombre(vs, 1)} ×" if pd.notna(vs) else "–",
             "sub": "volume par séance vs moyenne des 20 séances précédentes"},
            {"lab": "Part du MASI 20", "val": pct(vm.get("part_masi20"), 0, False), "sub": "du volume du marché"},
            {"lab": "Grosses transactions", "val": pct(vm.get("part_gros"), 0, False), "sub": GT.lecture(vm.get("part_gros"))},
            {"lab": "Actions échangées", "val": f"{int((toutes['volume'] > 0).sum())} / {len(toutes)}", "sub": "au moins un échange"},
        ])

    # ---- évolution sur toute la période des données
    compo_act = K.composition_au(compo, dates[0])
    noms = dict(zip(compo_act["isin"], compo_act["nom"]))
    defaut = "Les 20 valeurs du MASI 20" if est20 else "Tout le marché (toutes les actions)"
    options = [defaut] + [o for o in ["Les 20 valeurs du MASI 20", "Tout le marché (toutes les actions)"] if o != defaut] + list(noms)
    a1, a2 = st.columns([3, 2], vertical_alignment="bottom")
    with a1:
        ui.section("Évolution du volume sur toute la période des données")
    choix = a2.selectbox("Valeurs", options, format_func=lambda k: noms.get(k, k).title() if k in noms else k,
                         label_visibility="collapsed")
    if choix == "Tout le marché (toutes les actions)":
        v = K.volumes_jour(flux)
    elif choix in noms:
        v = K.volumes_jour(flux, [choix])
    else:
        v = K.volumes_jour(flux, compo_act["isin"])
    if fen == "Semaine":
        nbj = v.set_index("date")["volume"].resample("W-FRI").count()
        v = v.set_index("date")[["volume", "volume_gros", "nb"]].resample("W-FRI").sum()
        v["seances"] = nbj
        v = v[v["seances"] > 0].reset_index()
        v["moyenne"] = v["volume"].rolling(4, min_periods=1).mean()
        v.attrs.update({"hebdo": True, "lib_moyenne": "Moyenne 4 semaines"})
    else:
        v["moyenne"] = v["volume"].rolling(5, min_periods=1).mean()
        v.attrs["lib_moyenne"] = "Moyenne 5 séances"
    st.plotly_chart(G.volumes_evolution(v, db["masi20"]), width="stretch", config=G.CFG)
    st.caption(f"Une barre par {'semaine' if fen == 'Semaine' else 'séance'} · marché central (blocs exclus) · "
               "en or : les grosses transactions · ligne foncée : MASI 20 (axe de droite).")

    # ---- par valeur sur la période choisie
    if est20:
        ui.section(f"Volume par valeur · {libelle_periode}")
        x = base.sort_values("volume", ascending=False)
        x["habituel"] = x["isin"].map(prec).fillna(0)
        x["vs"] = np.where(x["habituel"] > 0, (x["volume"] / max(n_per, 1)) / x["habituel"].where(x["habituel"] > 0), np.nan)
        pv = K.volumes_par_valeur(flux, compo_act).set_index("isin")["semaines"]
        tab = pd.DataFrame({"Valeur": x["nom"].str.title(), "Variation": x["rendement"], "Volume": x["volume"],
                            "Part des 20": x["part_volume"], "Poids": x["poids"], "Vol./poids": x["volume_sur_poids"],
                            "vs habituel": x["vs"], "Grosses trans.": x["volume_gros"] / x["volume"].where(x["volume"] > 0),
                            "Contrats": x["nb"], "Volume par semaine (M MAD)": x["isin"].map(pv)})
        st.dataframe(ui.style_table(tab, pct_cols=["Variation"],
                                    fmt={"Volume": lambda v: mad(v), "Part des 20": lambda v: pct(v, 1, False),
                                         "Poids": lambda v: pct(v, 1, False), "Vol./poids": lambda v: nombre(v, 1) + " ×",
                                         "vs habituel": lambda v: nombre(v, 1) + " ×",
                                         "Grosses trans.": lambda v: pct(v, 0, False), "Contrats": lambda v: nombre(v, 0)}),
                     width="stretch", hide_index=True, height=38 * 21,
                     column_config={"Volume par semaine (M MAD)": st.column_config.BarChartColumn(
                         "Volume par semaine (M MAD)", help="Toute la période des données, une barre par semaine", y_min=0)})
        st.caption("Vol./poids = part du volume ÷ poids dans l'indice (1 × = la valeur s'échange en proportion de son poids). "
                   f"vs habituel = volume par séance de la période ÷ moyenne par séance des {len(avant)} séances précédentes.")
        c1, c2 = st.columns(2)
        with c1:
            ui.section("Où va l'argent : volume et poids")
            st.plotly_chart(G.volume_poids(base, h=400), width="stretch", config=G.CFG)
        with c2:
            ui.section("Volume par secteur")
            s = K.par_secteur(base)
            st.dataframe(ui.style_table(pd.DataFrame({"Secteur": s["secteur"], "Poids": s["poids"],
                                                      "Part du volume": s["part_volume"]}),
                                        fmt={"Poids": lambda v: pct(v, 1, False), "Part du volume": lambda v: pct(v, 1, False)}),
                         width="stretch", hide_index=True)
    else:
        ui.section(f"Les actions les plus échangées · {libelle_periode}")
        x = toutes.sort_values("volume", ascending=False)
        x = x[x["volume"] > 0]
        tot = x["volume"].sum()
        x["habituel"] = x["isin"].map(prec).fillna(0)
        x["vs"] = np.where(x["habituel"] > 0, (x["volume"] / max(n_per, 1)) / x["habituel"].where(x["habituel"] > 0), np.nan)
        tab = pd.DataFrame({"Valeur": x["nom"].str.title(), "MASI 20": x["masi20"].map({True: "●", False: ""}),
                            "Secteur": x["secteur"], "Variation": x["rendement"], "Volume": x["volume"],
                            "Part du marché": x["volume"] / tot if tot else np.nan, "vs habituel": x["vs"],
                            "Grosses trans.": x["volume_gros"] / x["volume"], "Contrats": x["nb"]})
        st.dataframe(ui.style_table(tab, pct_cols=["Variation"],
                                    fmt={"Volume": lambda v: mad(v), "Part du marché": lambda v: pct(v, 1, False),
                                         "vs habituel": lambda v: nombre(v, 1) + " ×", "Grosses trans.": lambda v: pct(v, 0, False),
                                         "Contrats": lambda v: nombre(v, 0)}),
                     width="stretch", hide_index=True, height=600)
        ui.section("Volume par secteur (toutes les actions)")
        sv = x.groupby("secteur", as_index=False).agg(volume=("volume", "sum"), valeurs=("isin", "count")).sort_values("volume", ascending=False)
        sv["part"] = sv["volume"] / tot if tot else np.nan
        st.dataframe(ui.style_table(pd.DataFrame({"Secteur": sv["secteur"], "Volume": sv["volume"], "Part du marché": sv["part"],
                                                  "Actions échangées": sv["valeurs"]}),
                                    fmt={"Volume": lambda v: mad(v), "Part du marché": lambda v: pct(v, 1, False)}),
                     width="stretch", hide_index=True)

ui.pied()
