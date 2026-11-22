import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import config as C
from src import grosses as GT
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

onglet_seance, onglet_volumes = st.tabs(["Séance / semaine", "Évolution des volumes"])

with onglet_seance:
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
             "sub": "du volume · " + GT.lecture(b["volume_gros"].sum() / b["volume"].sum() if b["volume"].sum() else None)},
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

with onglet_volumes:
    compo_act = K.composition_au(compo, dates[0])
    noms = dict(zip(compo_act["isin"], compo_act["nom"]))
    fl = flux
    n_s = fl["date"].nunique()
    c = st.columns([2, 1.2, 1.2])
    choix = c[0].selectbox("Valeurs", ["Les 20 valeurs du MASI 20", "Tout le marché (toutes les actions)"] + list(noms),
                           format_func=lambda k: noms.get(k, k).title() if k in noms else k)
    pas = c[1].segmented_control("Pas", ["Séance", "Semaine"], default="Séance", key="pas_vol")
    if choix == "Tout le marché (toutes les actions)":
        v = K.volumes_jour(fl)
    elif choix in noms:
        v = K.volumes_jour(fl, [choix])
    else:
        v = K.volumes_jour(fl, compo_act["isin"])
    if pas == "Semaine":
        nbj = v.set_index("date")["volume"].resample("W-FRI").count()
        v = v.set_index("date")[["volume", "volume_gros", "nb"]].resample("W-FRI").sum()
        v["seances"] = nbj
        v = v[v["seances"] > 0].reset_index()
        v["moyenne"] = v["volume"].rolling(4, min_periods=1).mean()
        v.attrs.update({"hebdo": True, "lib_moyenne": "Moyenne 4 semaines"})
    else:
        v["moyenne"] = v["volume"].rolling(5, min_periods=1).mean()
        v.attrs["lib_moyenne"] = "Moyenne 5 séances"
    lib = noms.get(choix, choix).title() if choix in noms else choix
    moy = v["volume"].mean()
    rec = v["volume"].tail(5 if pas != "Semaine" else 1).mean()
    part_gros = v["volume_gros"].sum() / v["volume"].sum() if v["volume"].sum() else float("nan")
    dern = v.iloc[-1]
    part_dern = dern["volume_gros"] / dern["volume"] if dern["volume"] else float("nan")
    ui.kpis([{"lab": "Période des données", "val": f"{n_s} séances",
              "sub": f"du {date_courte(fl['date'].min())} au {date_courte(fl['date'].max())}"},
             {"lab": "Volume total", "val": mad(v["volume"].sum()), "sub": "marché central"},
             {"lab": f"Moyenne par {'semaine' if pas == 'Semaine' else 'séance'}", "val": mad(moy),
              "sub": f"volume courant : {mad((v['volume'] - v['volume_gros']).mean())}"},
             {"lab": "5 dernières séances" if pas != "Semaine" else "Dernière semaine", "val": mad(rec),
              "sub": f"{pct(rec / moy - 1, 0) if moy else '–'} vs moyenne de la période", "sens": rec - moy},
             {"lab": "Part des grosses transactions", "val": pct(part_gros, 0, False), "gold": True,
              "sub": f"sur la période · {'dernière semaine' if pas == 'Semaine' else 'dernière séance'} : "
                     f"{pct(part_dern, 0, False)} ({GT.lecture(part_dern)})"}])
    a, b = st.columns([5, 1.3], vertical_alignment="bottom")
    with a:
        ui.section(f"Volume échangé · {lib}")
    with b.popover("Grosse transaction ?", icon=":material/help:", width="stretch"):
        st.markdown(f"""**Une grosse transaction** est un échange anormalement gros, passé par un ou quelques grands acteurs,
qui gonfle le volume d'une séance sans refléter l'intérêt de l'ensemble du marché.

**La règle** : chaque prix auquel une action s'est échangée dans la séance est testé. Il est « gros » s'il passe **l'une des deux portes** :
- **porte 1** : au moins **{GT.P1_MONTANT / 1e6:.0f} M MAD** au même prix **et** au moins **{GT.P1_PAR_CONTRAT / 1e6:.0f} M MAD par contrat** ;
- **porte 2** : au moins **{GT.P2_PLANCHER / 1e6:.0f} M MAD** au même prix **et** des contrats **{GT.P2_MULTIPLE} fois plus gros** que d'habitude pour cette valeur
  (habituel = médiane du montant par contrat sur ses {GT.HABITUEL_SEANCES} dernières séances ; il en faut au moins {GT.HABITUEL_MIN}).

**Le calcul**
- montant des grosses transactions = **somme des montants des prix « gros »** ;
- part des grosses transactions = montant des grosses transactions ÷ volume total ;
- volume courant = volume total − grosses transactions.

**Exemple réel** : Attijariwafa, 16/11/2026, 31,5 M MAD échangés à 17 prix. Au prix de 673,20 MAD : 26,0 M MAD en 15 contrats,
soit 1,7 M MAD par contrat → gros. Les 16 autres prix sont normaux. Part des grosses transactions = 26,0 ÷ 31,5 = **82 %**.

**Lecture** : moins de {pct(GT.LECTURE[0], 0, False)} = normal · de {pct(GT.LECTURE[0], 0, False)} à {pct(GT.LECTURE[1], 0, False)} = notable ·
plus de {pct(GT.LECTURE[1], 0, False)} = séance dominée par une ou deux opérations.

Détails et cas particuliers : fiche méthode « Les grosses transactions ».""")
    st.plotly_chart(G.volumes_evolution(v, db["masi20"]), width="stretch", config=G.CFG)
    st.caption("Marché central uniquement (le marché de blocs est exclu). En or : les grosses transactions. "
               "Ligne foncée = MASI 20 (axe de droite). Seules les séances dont le bulletin est importé apparaissent.")

    ui.section("Les grosses transactions repérées")
    gt = db.get("grosses", pd.DataFrame())
    if gt is None or gt.empty:
        st.info("Aucune grosse transaction enregistrée. Si des bulletins sont déjà importés, lancez le recalcul dans "
                "Composition & paramètres → « Recalculer les grosses transactions ».", icon=":material/info:")
    else:
        if choix in noms:
            gt = gt[gt["isin"] == choix]
        elif choix != "Tout le marché (toutes les actions)":
            gt = gt[gt["isin"].isin(compo_act["isin"])]
        gt = gt.sort_values(["date", "volume"], ascending=[False, False])
        jour = flux[flux["marche"] == "central"].groupby(["date", "isin"])["volume"].sum()
        part_val = [g / jour.get((d, i), float("nan")) for d, i, g in zip(gt["date"], gt["isin"], gt["volume"])]
        st.caption(f"{len(gt)} prix « gros » · {mad(gt['volume'].sum())} au total. Une ligne = un prix d'une action dans une séance.")
        st.dataframe(ui.style_table(pd.DataFrame({
            "Séance": gt["date"].dt.strftime("%d/%m/%Y"), "Valeur": gt["nom"].str.title(), "Prix": gt["cours"],
            "Montant": gt["volume"], "Contrats": gt["nb"], "Par contrat": gt["par_contrat"], "Habituel": gt["habituel"],
            "× habituel": gt["multiple"], "Porte": gt["porte"], "Part du volume de la valeur": part_val}),
            fmt={"Prix": lambda x: nombre(x), "Montant": lambda x: mad(x), "Contrats": lambda x: nombre(x, 0),
                 "Par contrat": lambda x: mad(x), "Habituel": lambda x: mad(x),
                 "× habituel": lambda x: f"{nombre(x, 1)} ×", "Part du volume de la valeur": lambda x: pct(x, 0, False)}),
            width="stretch", hide_index=True, height=min(38 * (len(gt) + 1) + 4, 420))
        st.caption("Habituel vide : moins de 5 séances d'historique pour la valeur, seule la porte 1 s'applique.")

    ui.section("Les 20 valeurs sur toute la période")
    pv = K.volumes_par_valeur(fl, compo_act)
    tab = pd.DataFrame({"Valeur": pv["nom"].str.title(), "Volume total": pv["volume"], "Part": pv["part"],
                        "Moyenne / séance": pv["moyen"], "5 dern. séances": pv["recent"], "Évolution": pv["evolution"],
                        "Séances échangées": [f"{int(s)} / {pv.attrs['seances']}" for s in pv["seances_echangees"]],
                        "Part grosses trans.": pv["gros"] / pv["volume"].replace(0, float("nan")),
                        "Volume par semaine (M MAD)": pv["semaines"]})
    st.dataframe(ui.style_table(tab, pct_cols=["Évolution"],
                                fmt={"Volume total": lambda x: mad(x), "Part": lambda x: pct(x, 1, False),
                                     "Moyenne / séance": lambda x: mad(x), "5 dern. séances": lambda x: mad(x),
                                     "Part grosses trans.": lambda x: pct(x, 0, False)}),
                 width="stretch", hide_index=True, height=38 * 21,
                 column_config={"Volume par semaine (M MAD)": st.column_config.BarChartColumn(
                     "Volume par semaine (M MAD)", help="Une barre par semaine, de la plus ancienne à la plus récente", y_min=0)})
    st.caption("Évolution = moyenne des 5 dernières séances comparée à la moyenne par séance de toute la période.")

ui.pied()
