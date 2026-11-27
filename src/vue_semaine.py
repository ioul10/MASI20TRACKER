"""Bilan de la semaine (MASI et MASI 20) à l'écran, et export Word.
Affiché dans le tableau de bord (onglet « Semaine ») et dans la page Bilan hebdo.
Même plan que le Word : l'essentiel · 1 le marché (MASI) · 2 le MASI 20 · 3 le marché à terme · 4 avis DRF."""
import numpy as np
import pandas as pd
import streamlit as st

from . import bilan as B
from . import charts as G
from . import hebdo as H
from . import marche as M
from . import ui
from .fmt import date_courte, mad, nombre, pct


def _cell(v):
    return v[0] if isinstance(v, tuple) else v


def afficher(db: dict) -> None:
    sem = H.semaines(db["masi20"])
    if not sem:
        st.info("Aucune donnée.")
        return
    c = st.columns([1.4, 2])
    fin = c[0].selectbox("Semaine", sem, key="semaine_bilan",
                         format_func=lambda d: f"Semaine {d.isocalendar().week} · du {date_courte(d - pd.Timedelta(days=4))} au {date_courte(d)}")
    with st.spinner("Calcul du bilan de la semaine…"):
        d = B.donnees(db, fin)
    if not d:
        st.warning("Aucune séance sur cette semaine.")
        return
    o, mv = d["o"], d["mv"]

    # ------------------------------------------------------------------ l'essentiel
    ui.chapitre("La semaine en un coup d’œil", f"{d['seances']} séance(s) · du {date_courte(d['debut'])} au {date_courte(d['fin'])}")
    ui.encadre("".join(f"<li>{s}</li>" for s in d["essentiel"]), liste=True)
    c1, c2 = st.columns([1.05, 1])
    with c1:
        ui.section("MASI, MASI 20 et reste du marché")
        face = pd.DataFrame([[_cell(x) for x in r] for r in B.face_a_face(d)],
                            columns=["", "MASI (tout le marché)", "MASI 20", "Hors MASI 20"])
        st.dataframe(face, hide_index=True, width="stretch", height=35 * (len(face) + 1) + 3)
        st.caption("Hors MASI 20 : les autres actions de la cote, variation pondérée par la capitalisation. Volumes : marché central.")
    with c2:
        ui.section("MASI et MASI 20 · base 100")
        if len(d["base100"]) > 1:
            st.plotly_chart(G.base100_masi(d["base100"], h=330), width="stretch", config=G.CFG)
            if "ecart" in d:
                st.caption(f"Écart MASI 20 − MASI sur la semaine : {pct(d['ecart'])}. Historique du MASI : importez-le depuis "
                           "Investing (Import des bulletins) pour une courbe plus longue.")
        else:
            st.info("Pas assez de séances communes MASI / MASI 20.")

    # ------------------------------------------------------------------ 1. le marché
    ui.chapitre("Le marché (MASI)", "Secteurs, actions, volumes et grosses transactions de toute la cote", "1")
    sect = mv.get("secteurs")
    if "actions" in d:
        g = d["actions"].sort_values("rendement", ascending=False)
        c1, c2 = st.columns([1.1, 1])
        with c1:
            ui.section("1.1 · Les secteurs")
            if sect is not None and not sect.empty:
                st.plotly_chart(G.secteurs_barres(sect, h=max(420, 22 * len(sect) + 60)), width="stretch", config=G.CFG)
        with c2:
            ui.section("1.2 · Les actions de la semaine")
            top, flop = g.head(5), g.tail(5).iloc[::-1]
            st.dataframe(ui.style_table(pd.DataFrame({"Meilleures": top["nom"].str.title().values, "Var.": top["rendement"].values,
                                                      "Moins bonnes": flop["nom"].str.title().values, "Var. ": flop["rendement"].values}),
                                        pct_cols=["Var.", "Var. "]), hide_index=True, width="stretch")
            ui.section("1.3 · Les volumes")
            vs = d["vs"]["marche"]
            st.markdown(f"Le marché a échangé **{mad(mv.get('volume'))}**"
                        + (f", soit **{nombre(vs, 1)} ×** son volume habituel par séance" if not pd.isna(vs) else "")
                        + f". Le MASI 20 en représente **{pct(mv.get('part_masi20'), 0, False)}**.")
            gv = g.sort_values("volume", ascending=False).head(5)
            tv = g["volume"].sum()
            st.dataframe(ui.style_table(pd.DataFrame({"Actions les plus échangées": gv["nom"].str.title(), "Volume": gv["volume"],
                                                      "Part du marché": gv["volume"] / tv, "Part GT": gv["volume_gros"] / gv["volume"],
                                                      "Indice": np.where(gv["m20"], "MASI 20", "")}),
                                        fmt={"Volume": lambda v: mad(v), "Part du marché": lambda v: pct(v, 1, False),
                                             "Part GT": lambda v: pct(v, 0, False)}), hide_index=True, width="stretch")
        ui.section("1.4 · Les grosses transactions")
        gt = d["gt"]
        st.markdown(f"**{len(gt)}** grosse(s) transaction(s) sur la semaine ; elles font **{pct(mv.get('part_gros'), 0, False)}** "
                    "du volume du marché. Détail et méthode : page *Grosses transactions*.")
        if not gt.empty:
            st.dataframe(pd.DataFrame(B._gt_lignes(gt.head(8)), columns=["Séance", "Valeur", "Prix", "Montant", "Contrats",
                                                                         "Par contrat", "Test"]),
                         hide_index=True, width="stretch")

    # ------------------------------------------------------------------ 2. le MASI 20
    ui.chapitre("Le MASI 20", f"Clôture {nombre(o['masi20'])} pts · {pct(o['masi20_var'])} sur la semaine", "2")
    if "b" in d:
        b = d["b"]
        c1, c2 = st.columns([1, 1.05])
        with c1:
            ui.section("2.1 · Qui a fait bouger l’indice")
            bt = b.sort_values("contribution_pb", ascending=False)
            t3, f3 = bt.head(3), bt.tail(3).iloc[::-1]
            st.dataframe(ui.style_table(pd.DataFrame({"Tirent l’indice": t3["nom"].str.title().values, "pb": t3["contribution_pb"].values,
                                                      "Freinent l’indice": f3["nom"].str.title().values, "pb ": f3["contribution_pb"].values}),
                                        signe_cols=["pb", "pb "], fmt={"pb": lambda v: nombre(v, 1, True), "pb ": lambda v: nombre(v, 1, True)}),
                         hide_index=True, width="stretch")
            x, _ = M.concentration(b)
            st.plotly_chart(G.gt_mouvement(x, h=560), width="stretch", config=G.CFG)
        with c2:
            ui.section("2.2 · Les volumes des 20 valeurs")
            cc = d["conc"]
            st.markdown(f"Les grosses transactions font **{pct(cc.get('part_gros'), 0, False)}** du volume des 20 valeurs ; "
                        f"**{pct(cc.get('part_mouvement_gt'), 0, False)} du mouvement** du MASI 20 vient de "
                        f"{cc.get('valeurs_gt', 0)} valeur(s) dominée(s) par des grosses transactions.")
            bv = b.sort_values("volume", ascending=False)
            st.dataframe(ui.style_table(pd.DataFrame({"Valeur": bv["nom"].str.title(), "Var.": bv["rendement"], "Volume": bv["volume"],
                                                      "Vol./poids": bv["volume_sur_poids"], "vs habituel": bv["vs"],
                                                      "Part GT": bv["part_gt"]}),
                                        pct_cols=["Var."], fmt={"Volume": lambda v: mad(v), "Vol./poids": lambda v: nombre(v, 1) + " ×",
                                                                "vs habituel": lambda v: nombre(v, 1) + " ×", "Part GT": lambda v: pct(v, 0, False)}),
                         hide_index=True, width="stretch", height=38 * 21)
    ui.section("2.3 · La technique")
    st.dataframe(pd.DataFrame(o["signaux"]).rename(columns={"Famille": "Méthode"}), width="stretch", hide_index=True,
                 column_config={"Lecture": st.column_config.TextColumn(width="large")})
    t = o["technique"].tail(90)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(G.indice_moyennes(t, h=300), width="stretch", config=G.CFG)
        st.plotly_chart(G.atr_barres(t, 14, h=280), width="stretch", config=G.CFG)
    with c2:
        st.plotly_chart(G.rsi_barres(t, 14, h=300), width="stretch", config=G.CFG)
        st.plotly_chart(G.var5_barres(t, h=280), width="stretch", config=G.CFG)

    # ------------------------------------------------------------------ 3. le marché à terme
    ui.chapitre("Le marché à terme", "Futures sur l’indice MASI 20", "3")
    fu = o.get("futures") or {}
    tab = fu.get("tableau", pd.DataFrame())
    if tab is None or tab.empty:
        st.info("Aucun bulletin du marché à terme sur la semaine.")
    else:
        st.dataframe(ui.style_table(pd.DataFrame({
            "Échéance": tab["contrat"], "Clôture": tab["cloture"], "Var. sem.": tab["var_semaine"], "Base": tab["base_pct"],
            "Positions": tab["open_interest"], "Δ positions": tab["delta_oi"],
            "Volume": [mad(v) if v else "Aucun échange" for v in tab["volume"]],
            "Lecture": [s if s != "Indéterminé" else "Pas de signal" for s in tab["signal"]]}),
            pct_cols=["Var. sem."], signe_cols=["Δ positions"],
            fmt={"Clôture": lambda v: nombre(v), "Base": lambda v: pct(v), "Positions": lambda v: nombre(v, 0),
                 "Δ positions": lambda v: nombre(v, 0, True)}), hide_index=True, width="stretch")
        if not fu.get("volume_semaine"):
            st.caption("Aucune transaction sur la semaine : positions ouvertes inchangées.")

    # ------------------------------------------------------------------ 4. avis DRF et export
    ui.chapitre("Avis DRF", "Modifiable avant l’export : le texte ci-dessous part tel quel dans le Word", "4")
    avis = st.text_area("Avis DRF", value=o.get("avis", ""), height=170, key=f"avis_{fin:%Y%m%d}")
    points = st.text_area("Points à surveiller la semaine prochaine (un par ligne)", value="", height=90,
                          key=f"points_{fin:%Y%m%d}", placeholder="Ex. : tenue des mines après la chute de Managem")
    auteur = st.text_input("Signature (facultatif)", value="", key="auteur_bilan")
    if st.button("Préparer le bilan Word", type="primary", icon=":material/description:"):
        with st.spinner("Construction du document Word…"):
            st.session_state["bilan_docx"] = (fin, B.docx(d, avis, points, auteur))
    prep = st.session_state.get("bilan_docx")
    if prep and prep[0] == fin:
        st.download_button("Télécharger le bilan Word", data=prep[1], icon=":material/download:",
                           file_name=f"Bilan_hebdo_MASI_MASI20_{fin:%Y%m%d}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.caption("Le document s’ouvre dans Word ; Fichier › Enregistrer sous › PDF pour une version figée.")
