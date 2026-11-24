"""Vision hebdomadaire (spot + marché à terme) et export du bilan Word / HTML.
Affichée dans le tableau de bord (onglet « Semaine ») et dans la page Bilan hebdo."""
import pandas as pd
import streamlit as st

from . import charts as G
from . import hebdo as H
from . import marche as M
from . import report, report_word
from . import ui
from .fmt import date_courte, mad, nombre, pct


def afficher(db: dict) -> None:
    sem = H.semaines(db["masi20"])
    if not sem:
        st.info("Aucune donnée.")
        return
    c = st.columns([1.2, 2])
    fin = c[0].selectbox("Semaine", sem, format_func=lambda d: f"Semaine {d.isocalendar().week} · du {date_courte(d - pd.Timedelta(days=4))} au {date_courte(d)}")
    o = H.bilan(db, fin)
    if not o:
        st.warning("Aucune séance sur cette semaine.")
        return

    # --- En-tête
    fu = o.get("futures") or {}
    tab = fu.get("tableau", pd.DataFrame())
    items = [{"lab": "MASI 20", "val": f"{nombre(o['masi20'])} pts", "sub": f"{pct(o['masi20_var'])} sur la semaine",
              "sens": o["masi20_var"], "gold": True}]
    for _, r in tab.iterrows():
        items.append({"lab": r["contrat"], "val": f"{nombre(r['cloture'])} pts", "sub": f"{pct(r['var_semaine'])} · base {pct(r['base_pct'], 1)}",
                      "sens": r["var_semaine"]})
    ui.kpis(items)
    st.caption(f"Variations calculées depuis la clôture du {date_courte(o['masi20_ref_date'])} "
               f"(dernière séance de la semaine précédente) · {len(o['seances'])} séances : "
               + ", ".join(d.strftime("%d/%m") for d in o["seances"]))

    ui.section("Vision générale")
    g = [{"lab": "État de marché", "val": o["etat_marche"], "sens": o["masi20_var"]}]
    if "masi_var" in o:
        g.append({"lab": "MASI", "val": pct(o["masi_var"]), "sub": "indice large", "sens": o["masi_var"]})
    if fu:
        g += [{"lab": "Positions ouvertes", "val": nombre(fu["oi_total"], 0), "sub": f"{nombre(fu['delta_oi_total'], 0, True)} sur la semaine",
               "sens": fu["delta_oi_total"]},
              {"lab": "Volume futures", "val": mad(fu["volume_semaine"]), "sub": f"{fu['seances_sans_transaction']} séance(s) sans transaction"},
              {"lab": "Depuis le lancement", "val": f"{fu['seances_depuis_lancement']} séances", "sub": mad(fu["volume_depuis_lancement"])}]
    ui.kpis(g)

    mv = o.get("masi_vision") or {}
    if mv.get("valeur") is not None:
        ui.section("MASI · tout le marché")
        ui.kpis([
            {"lab": "MASI", "val": f"{nombre(mv['valeur'])} pts", "sub": f"{pct(mv.get('var'))} sur la semaine",
             "sens": mv.get("var"), "gold": True},
            {"lab": "Depuis le 31/12", "val": pct(mv.get("var_ytd")), "sens": mv.get("var_ytd")},
            {"lab": "Hausses / baisses", "val": f"{mv.get('hausses', 0)} / {mv.get('baisses', 0)}",
             "sub": f"sur {mv.get('actions', 0)} actions cotées"},
            {"lab": "Volume du marché", "val": mad(mv.get("volume")),
             "sub": (f"{nombre(mv['volume_vs'], 1)} × l'habituel par séance" if pd.notna(mv.get("volume_vs")) else "marché central")},
            {"lab": "Part du MASI 20", "val": pct(mv.get("part_masi20"), 0, False), "sub": "du volume du marché"},
        ])
        c1, c2 = st.columns(2)
        with c1:
            b100 = M.base100(db)
            b100 = b100[b100["date"] <= fin] if not b100.empty else b100
            if len(b100) > 1:
                st.markdown("**MASI et MASI 20 · base 100**")
                st.plotly_chart(G.base100_masi(b100, h=400), width="stretch", config=G.CFG)
        with c2:
            sect = mv.get("secteurs")
            if sect is not None and not sect.empty:
                st.markdown("**Indices sectoriels · variation de la semaine**")
                st.plotly_chart(G.secteurs_barres(sect, h=max(400, 22 * len(sect) + 60)), width="stretch", config=G.CFG)

    if fu:
        ui.section("Marché à terme")
        c1, c2 = st.columns([1.15, 1])
        with c1:
            t = pd.DataFrame({"Contrat": tab["contrat"], "Clôture": tab["cloture"], "Var. sem.": tab["var_semaine"],
                              "OI": tab["open_interest"], "Δ OI": tab["delta_oi"], "Volume": tab["volume"],
                              "Base": tab["base_pct"], "Lecture prix × OI": tab["signal"]})
            st.dataframe(ui.style_table(t, pct_cols=["Var. sem.", "Base"], signe_cols=["Δ OI"],
                                        fmt={"Clôture": lambda v: nombre(v), "OI": lambda v: nombre(v, 0),
                                             "Δ OI": lambda v: nombre(v, 0, True), "Volume": lambda v: mad(v, 2)}),
                         width="stretch", hide_index=True)
        with c2:
            st.plotly_chart(G.futures_semaine(o["futures_jours"], h=300), width="stretch", config=G.CFG)

    if o.get("composants_dispo"):
        b = o["composants"]
        if o.get("bulletins_manquants"):
            ui.note("Bulletins de la cote manquants pour cette semaine : " + ", ".join(o["bulletins_manquants"]) +
                    ". Les contributions et volumes ne portent que sur les séances disponibles "
                    f"({o['seances_composants']} sur {len(o['seances'])}).")
        ui.section("Composants : chiffres clés")
        ui.kpis([{"lab": "Hausses / baisses", "val": f"{o['hausses']} / {o['baisses']}", "sub": "sur 20 valeurs"},
                 {"lab": "Volume des 20 valeurs", "val": mad(o["volume_masi20"]), "sub": f"{pct(o['part_marche'], 0, False)} du marché central"},
                 {"lab": "Grosses transactions", "val": pct(o["part_gros"], 0, False), "sub": "du volume de l'indice"},
                 {"lab": "Contrôle des poids", "val": pct(o["controle_recon"]), "sub": f"reconstitué ({nombre(o['controle_pb'], 0, True)} pb)"},
                 {"lab": "Qualité du mouvement", "val": pct(o["qualite_hausse"], 0, False) if pd.notna(o["qualite_hausse"]) else "–",
                  "sub": "de la contribution positive avec volume en hausse"}])
        ui.section("Indice et volume, séance par séance")
        st.plotly_chart(G.semaine_indice_volume(o), width="stretch", config=G.CFG)
        c1, c2 = st.columns(2)
        with c1:
            ui.section("Qui a fait bouger l'indice")
            st.plotly_chart(G.contributions(b), width="stretch", config=G.CFG)
        with c2:
            ui.section("Où va l'argent")
            st.plotly_chart(G.volume_poids(b, h=26 * len(b) + 60), width="stretch", config=G.CFG)
        ui.section("Détail des 20 valeurs")
        t = pd.DataFrame({"Valeur": b["nom"], "Poids": b["poids"], "Var. sem.": b["rendement"], "Contrib. (pb)": b["contribution_pb"],
                          "Volume": b["volume"], "Vol./poids": b["volume_sur_poids"], "Tend. vol.": b["tendance_volume"],
                          "Signal": b["qualite"]})
        st.dataframe(ui.style_table(t, pct_cols=["Var. sem."], signe_cols=["Contrib. (pb)"],
                                    fmt={"Poids": lambda v: pct(v, 1, False), "Contrib. (pb)": lambda v: nombre(v, 1, True),
                                         "Volume": lambda v: mad(v), "Vol./poids": lambda v: nombre(v, 1) + "×",
                                         "Tend. vol.": lambda v: nombre(v, 2) + "×"}),
                     width="stretch", hide_index=True, height=740)
        c1, c2 = st.columns(2)
        with c1:
            ui.section("Par secteur")
            s = o["secteurs"]
            st.dataframe(ui.style_table(pd.DataFrame({"Secteur": s["secteur"], "Poids": s["poids"], "Contribution (pb)": s["contribution_pb"],
                                                      "Part du volume": s.get("part_volume")}), signe_cols=["Contribution (pb)"],
                                        fmt={"Poids": lambda v: pct(v, 1, False), "Contribution (pb)": lambda v: nombre(v, 1, True),
                                             "Part du volume": lambda v: pct(v, 1, False)}), width="stretch", hide_index=True)
        with c2:
            ui.section("À surveiller la semaine prochaine")
            for x in o["a_surveiller"] or ["Rien de particulier."]:
                st.markdown(f"- {x}")
    else:
        ui.note("Aucun bulletin de la cote pour cette semaine : la partie composants et volumes n'est pas disponible.")

    ui.section("Analyse technique du MASI 20")
    st.dataframe(pd.DataFrame(o["signaux"]).rename(columns={"Famille": "Méthode"}), width="stretch", hide_index=True,
                 column_config={"Lecture": st.column_config.TextColumn(width="large")})
    t = o["technique"].tail(90)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Indice et moyennes mobiles 5 · 10 · 20 · 40**")
        st.plotly_chart(G.indice_moyennes(t, h=320), width="stretch", config=G.CFG)
        st.markdown("**ATR 14**")
        st.plotly_chart(G.atr_barres(t, 14, h=300), width="stretch", config=G.CFG)
    with c2:
        st.markdown("**RSI 14**")
        st.plotly_chart(G.rsi_barres(t, 14, h=320), width="stretch", config=G.CFG)
        st.markdown("**Variation sur 5 séances**")
        st.plotly_chart(G.var5_barres(t, h=300), width="stretch", config=G.CFG)
    st.caption("Méthodes et lecture détaillées : page Indice & technique.")

    ui.section("Avis DRF")
    cle = f"avis_{fin:%Y%m%d}"
    avis = st.text_area("Proposition générée à partir des chiffres : relisez et corrigez avant l'export.", value=o["avis"], height=150, key=cle)
    auteur = st.text_input("Signature (facultatif)", value="DRF")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Télécharger le bilan Word (.docx)", report_word.docx_bilan(o, avis, auteur),
                           file_name=f"MASI20TRACKER_bilan_{fin:%Y%m%d}.docx", type="primary", width="stretch",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.caption("Modifiable dans Word : textes, tableaux et graphiques (en images).")
    with c2:
        st.download_button("Télécharger le bilan HTML (à imprimer en PDF)", report.html_bilan(o, avis, auteur).encode("utf-8"),
                           file_name=f"MASI20TRACKER_bilan_{fin:%Y%m%d}.html", mime="text/html", width="stretch")
        st.caption("Graphiques interactifs. Pour le PDF : ouvrir dans le navigateur, puis Ctrl+P (A4 paysage).")

