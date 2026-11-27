import pandas as pd
import streamlit as st

from src import importer, store, ui
from src.fmt import date_courte, nombre

ui.page("Import des bulletins", "Déposez les bulletins du jour : ils sont lus, contrôlés, puis enregistrés")

if store.github_actif():
    st.success("Sauvegarde GitHub configurée : chaque import est enregistré dans le repo.", icon=":material/cloud_done:")
    with st.expander("Tester la sauvegarde GitHub"):
        if st.button("Lancer le test"):
            with st.spinner("Vérification…"):
                ok, etapes = store.diagnostic_github()
            for e in etapes:
                st.markdown(e)
            (st.success if ok else st.error)("Tout est en ordre." if ok else "Corrigez le point marqué ❌ dans les secrets, puis relancez le test.")
else:
    ui.note("Sauvegarde GitHub non configurée : les imports restent sur ce serveur et seront perdus au prochain redémarrage "
            "de Streamlit Cloud. Ajoutez GITHUB_TOKEN et GITHUB_REPO dans les secrets (voir le README).")

onglet_bulletins, onglet_hb = st.tabs(["Bulletins du jour", "Historiques Investing : MASI 20 et MASI"])

# Cet onglet est rempli en premier : l'onglet des bulletins peut s'arrêter (st.stop) quand aucun fichier n'est déposé.
with onglet_hb:
    m20 = ui.db()["masi20"].sort_values("date")
    manque = m20[m20["plus_haut"].isna() | m20["plus_bas"].isna()]
    st.markdown("Le bulletin de la Bourse ne publie que la **clôture** de l'indice. Le plus haut et le plus bas de la séance "
                "servent à l'**ATR** (sans eux, il est estimé à partir des clôtures, donc sous-estimé). "
                "Deux façons de les compléter :")
    if manque.empty:
        st.success("Toutes les séances de la base ont un plus haut et un plus bas.", icon=":material/check_circle:")
    ui.section(f"1 · Saisie rapide des séances incomplètes ({len(manque)})")
    if not manque.empty:
        grille = pd.DataFrame({"Date": manque["date"].dt.date, "Clôture": manque["cloture"],
                               "Plus haut": manque["plus_haut"].astype(float), "Plus bas": manque["plus_bas"].astype(float)}).iloc[::-1]
        saisie = st.data_editor(grille, hide_index=True, width="stretch", key="grille_hb",
                                disabled=["Date", "Clôture"],
                                column_config={"Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                               "Clôture": st.column_config.NumberColumn(format="%.2f"),
                                               "Plus haut": st.column_config.NumberColumn(format="%.2f", min_value=0),
                                               "Plus bas": st.column_config.NumberColumn(format="%.2f", min_value=0)})
        if st.button("Enregistrer la saisie", type="primary", key="ok_grille"):
            x = saisie.rename(columns={"Date": "date", "Plus haut": "plus_haut", "Plus bas": "plus_bas"})
            ok, rejets = importer.controler_hauts_bas(x[["date", "plus_haut", "plus_bas"]], m20)
            n = importer.enregistrer_hauts_bas(ok)
            ui.vider_cache()
            if n:
                st.success(f"{n} séance(s) complétée(s). L'ATR est recalculé.")
            for _, r in rejets.iterrows():
                if r["motif"] != "plus haut ou plus bas manquant":
                    st.error(f"{date_courte(r['date'])} : {r['motif']}.")
            if not n and rejets.empty:
                st.info("Rien à enregistrer : remplissez au moins une ligne (plus haut et plus bas).")

    ui.section("2 · Import en masse depuis un fichier (Investing, Excel ou CSV)")
    st.caption("Formats reconnus : l'export « Historical Data » d'Investing.com (Date, Price, Open, High, Low, Vol., "
               "Change %), sa version française (Date, Dernier, Ouv., Plus Haut, Plus Bas…), ou tout fichier avec les "
               "colonnes Date, Plus haut, Plus bas (par exemple la feuille MASI20INDEX). La clôture du bulletin reste la "
               "référence : une ligne est rejetée si elle n'est pas comprise entre le plus bas et le plus haut. "
               "Une séance absente de la base est ajoutée avec la clôture du fichier ; le bulletin, importé plus tard, "
               "la remplacera en gardant le plus haut, le plus bas et l'ouverture.")
    fic = st.file_uploader("Fichier de l'historique du MASI 20", type=["xlsx", "xls", "csv"], key="fic_hb")
    if fic is not None:
        try:
            lu = importer.lire_hauts_bas(fic, fic.name)
            ok, rejets = importer.controler_hauts_bas(lu, m20)
            nouv = int(ok["nouvelle"].sum()) if not ok.empty else 0
            c = st.columns(4)
            c[0].metric("Lignes lues", len(lu),
                        help=f"du {date_courte(lu['date'].min())} au {date_courte(lu['date'].max())}" if len(lu) else None)
            c[1].metric("Séances complétées", len(ok) - nouv, help="déjà en base : plus haut, plus bas (et ouverture) ajoutés")
            c[2].metric("Nouvelles séances", nouv, help="absentes de la base : ajoutées avec la clôture du fichier")
            c[3].metric("Rejetées", len(rejets))
            if not ok.empty:
                ecart = ok["ecart_cloture"].abs()
                if (ecart > 0.05).any():
                    st.warning(f"{int((ecart > 0.05).sum())} séance(s) où la clôture du fichier diffère de celle du "
                               f"bulletin de plus de 0,05 pt (écart max {nombre(ecart.max(), 2)} pt). La clôture du "
                               "bulletin est conservée.")
                with st.expander("Aperçu des séances valides"):
                    st.dataframe(pd.DataFrame({"Date": ok["date"].dt.strftime("%d/%m/%Y"),
                                               "Clôture retenue": ok["cloture"], "Ouverture": ok["ouverture"],
                                               "Plus haut": ok["plus_haut"], "Plus bas": ok["plus_bas"],
                                               "Statut": ["nouvelle séance" if n else "complétée" for n in ok["nouvelle"]]}),
                                 hide_index=True, width="stretch")
            if not rejets.empty:
                with st.expander(f"Voir les {len(rejets)} ligne(s) rejetée(s)"):
                    st.dataframe(pd.DataFrame({"Date": rejets["date"].dt.strftime("%d/%m/%Y"), "Clôture": rejets["cloture"],
                                               "Plus haut": rejets["plus_haut"], "Plus bas": rejets["plus_bas"],
                                               "Motif": rejets["motif"]}), hide_index=True, width="stretch")
            if not ok.empty and st.button(f"Enregistrer les {len(ok)} séance(s) valides", type="primary", key="ok_fic"):
                n = importer.enregistrer_hauts_bas(ok)
                ui.vider_cache()
                st.success(f"{n} séance(s) enregistrée(s).")
        except Exception as e:
            st.error(f"Lecture impossible : {e}")

    ui.section("3 · Historique du MASI (indice large) depuis Investing")
    st.caption("Le bulletin ne donne le MASI que pour les séances importées. Pour un historique plus long (base 100 MASI / "
               "MASI 20, bilan hebdo), déposez l'export « Historical Data » du MASI d'Investing.com (mêmes colonnes que pour "
               "le MASI 20). Seules les séances absentes de la base sont ajoutées : la valeur du bulletin reste la référence.")
    fic_m = st.file_uploader("Fichier de l'historique du MASI", type=["xlsx", "xls", "csv"], key="fic_masi")
    if fic_m is not None:
        try:
            lu_m = importer.lire_hauts_bas(fic_m, fic_m.name)
            rows_m, res_m = importer.preparer_masi(lu_m, ui.db()["indices"])
            c = st.columns(4)
            c[0].metric("Lignes lues", res_m["lues"])
            c[1].metric("Séances ajoutées", res_m["nouvelles"],
                        help=f"du {date_courte(res_m['debut'])} au {date_courte(res_m['fin'])}" if res_m["nouvelles"] else None)
            c[2].metric("Déjà dans la base", res_m["deja"], help="séances des bulletins, non modifiées")
            c[3].metric("Rejetées", res_m["incoherentes"], help="clôture hors de l'intervalle plus bas – plus haut")
            if res_m["deja"] and res_m["ecart_max"] > 0.5:
                st.warning(f"Sur les séances communes, la clôture du fichier diffère du bulletin de {nombre(res_m['ecart_max'], 2)} pt "
                           "au maximum : vérifiez qu'il s'agit bien du MASI (et non du MASI 20 ou d'un autre indice).")
            if res_m["nouvelles"] and st.button(f"Ajouter les {res_m['nouvelles']} séance(s) du MASI", type="primary", key="ok_masi"):
                n = importer.enregistrer_masi(rows_m)
                ui.vider_cache()
                st.success(f"{n} séance(s) du MASI ajoutée(s).")
        except Exception as e:
            st.error(f"Lecture impossible : {e}")

with onglet_bulletins:
    fichiers = st.file_uploader("Bulletins PDF (cote BCFR_AAAAMMJJ et/ou futures BCFR_D_AAAAMMJJ)", type="pdf",
                                accept_multiple_files=True)
    if not fichiers:
        ui.section("Routine quotidienne")
        st.markdown("""
1. Téléchargez les deux bulletins du jour sur le site de la Bourse de Casablanca : **la cote** et **le marché à terme**.
2. Déposez-les ici (plusieurs fichiers à la fois, dans n'importe quel ordre).
3. Vérifiez les contrôles, saisissez si vous le souhaitez le plus haut et le plus bas du MASI 20, puis validez.

Les contrôles vérifient que les 20 valeurs du MASI 20 sont retrouvées **par code ISIN**, comparent la variation
reconstituée à la variation publiée, signalent les doublons et les variations anormales.
""")
        m20 = ui.db()["masi20"]
        if not m20.empty:
            ui.section("État de la base")
            db = ui.db()
            etat = pd.DataFrame([
                {"Table": "MASI 20", "Séances": m20["date"].nunique(), "Du": m20["date"].min(), "Au": m20["date"].max()},
                {"Table": "Bulletins de la cote", "Séances": db["actions"]["date"].nunique() if not db["actions"].empty else 0,
                 "Du": db["actions"]["date"].min() if not db["actions"].empty else None,
                 "Au": db["actions"]["date"].max() if not db["actions"].empty else None},
                {"Table": "Futures", "Séances": db["futures"]["date"].nunique(), "Du": db["futures"]["date"].min(),
                 "Au": db["futures"]["date"].max()}])
            etat["Du"] = etat["Du"].map(lambda d: date_courte(d) if pd.notna(d) else "–")
            etat["Au"] = etat["Au"].map(lambda d: date_courte(d) if pd.notna(d) else "–")
            st.dataframe(etat, width="stretch", hide_index=True)
        st.stop()

    rapports = []
    for f in fichiers:
        contenu = f.getvalue()
        try:
            rep = importer.analyser(contenu, f.name)
            rapports.append((f, contenu, rep))
        except Exception as e:
            st.error(f"**{f.name}** : {e}")

    rapports.sort(key=lambda t: (t[2].seance, t[2].type))
    valider = {}
    for f, contenu, rep in rapports:
        titre = "Bulletin de la cote" if rep.type == "cote" else "Marché à terme"
        with st.container(border=True):
            st.markdown(f"**{titre} · séance du {date_courte(rep.seance)}** · `{f.name}`")
            st.dataframe(pd.DataFrame([{"Contrôle": k, "Résultat": str(v)} for k, v in rep.resume.items()]),
                         width="stretch", hide_index=True)
            for a in rep.alertes:
                st.warning(a, icon=":material/warning:")
            for i in rep.infos:
                st.info(i, icon=":material/info:")
            h = b = None
            if rep.type == "cote":
                c = st.columns(3)
                h = c[0].number_input("Plus haut MASI 20 (facultatif)", value=None, step=0.01, key=f"h{f.name}")
                b = c[1].number_input("Plus bas MASI 20 (facultatif)", value=None, step=0.01, key=f"b{f.name}")
            ok = st.checkbox("Enregistrer ce bulletin", value=not rep.alertes, key=f"ok{f.name}",
                             help="Décoché par défaut quand une alerte demande votre vérification.")
            valider[f.name] = (ok, contenu, rep, h, b)

    if st.button("Valider l'import", type="primary"):
        n = 0
        with st.spinner("Enregistrement…"):
            for nom, (ok, contenu, rep, h, b) in valider.items():
                if ok:
                    importer.enregistrer(rep, contenu, f"{rep.type}_{rep.seance:%Y%m%d}.pdf", h, b)
                    n += 1
        ui.vider_cache()
        st.success(f"{n} bulletin(s) enregistré(s). Les indicateurs sont recalculés automatiquement.")
        if store.ERREURS_GITHUB:
            st.warning("Les données sont enregistrées sur le serveur, mais **pas sauvegardées sur GitHub** "
                       "(elles seront perdues au prochain redémarrage) :\n\n- " + "\n- ".join(store.ERREURS_GITHUB) +
                       "\n\nUtilisez « Tester la sauvegarde GitHub » en haut de la page pour trouver la cause.")
            store.ERREURS_GITHUB.clear()
