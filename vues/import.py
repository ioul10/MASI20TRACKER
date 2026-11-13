import pandas as pd
import streamlit as st

from src import importer, store, ui
from src.fmt import date_courte

ui.page("Import des bulletins", "Déposez les bulletins du jour : ils sont lus, contrôlés, puis enregistrés")

if store.github_actif():
    st.success("Sauvegarde GitHub active : chaque import est enregistré dans le repo.", icon=":material/cloud_done:")
else:
    ui.note("Sauvegarde GitHub non configurée : les imports restent sur ce serveur et seront perdus au prochain redémarrage "
            "de Streamlit Cloud. Ajoutez GITHUB_TOKEN et GITHUB_REPO dans les secrets (voir le README).")

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
