import pandas as pd
import streamlit as st

from src import config as C
from src import grosses as GT
from src import store, ui

ui.page("Composition & paramètres", "Composition du MASI 20 (par code ISIN), flottant et plafonnement")

compo = store.load("composition")
ui.section("Composition du MASI 20")
st.markdown("""
Une ligne par valeur et par période. **À chaque révision annuelle** : renseignez la *date de fin* des valeurs qui sortent,
et ajoutez les valeurs qui entrent avec leur *date de début*. Le rapprochement se fait par **code ISIN** : le nom n'est
qu'un libellé (la Bourse le modifie parfois, par exemple « TGCC S.A » devenu « TGCC »).

- **Facteur de flottant** : part du capital réellement négociable (1 = 100 %). À reprendre de la publication de la Bourse
  lors de la révision ; à défaut, laissez 1 (poids approchés).
- **Plafond** : poids maximum d'une valeur dans l'indice (1 = pas de plafond).
""")
edit = st.data_editor(
    compo, num_rows="dynamic", width="stretch", hide_index=True,
    column_config={
        "isin": st.column_config.TextColumn("Code ISIN", required=True),
        "nom": st.column_config.TextColumn("Nom"),
        "secteur_code": st.column_config.SelectboxColumn("Secteur", options=list(C.SECTEURS)),
        "date_debut": st.column_config.DateColumn("Début", format="DD/MM/YYYY", required=True),
        "date_fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),
        "facteur_flottant": st.column_config.NumberColumn("Flottant", min_value=0.01, max_value=1.0, step=0.01, format="%.2f"),
        "plafond": st.column_config.NumberColumn("Plafond", min_value=0.01, max_value=1.0, step=0.01, format="%.2f"),
    })
actifs = edit[edit["date_fin"].isna()] if "date_fin" in edit else edit
st.caption(f"{len(actifs)} valeurs actives (sans date de fin).")
if st.button("Enregistrer la composition", type="primary"):
    if len(actifs) != 20:
        st.warning(f"Attention : {len(actifs)} valeurs actives au lieu de 20.")
    store.save("composition", edit, "MAJ composition MASI 20")
    ui.vider_cache()
    st.success("Composition enregistrée.")

ui.section("Paramètres de calcul")
st.markdown(f"""
| Paramètre | Valeur |
|---|---|
| Multiplicateur des futures | {C.MULTIPLICATEUR} MAD par point |
| Grosse transaction · porte 1 | au moins {GT.P1_MONTANT / 1e6:.0f} M MAD au même prix et {GT.P1_PAR_CONTRAT / 1e6:.0f} M MAD par contrat |
| Grosse transaction · porte 2 | au moins {GT.P2_PLANCHER / 1e6:.0f} M MAD au même prix et {GT.P2_MULTIPLE} × le montant habituel par contrat |
| Montant habituel par contrat | médiane sur les {GT.HABITUEL_SEANCES} dernières séances échangées (au moins {GT.HABITUEL_MIN}) |
| Lecture de la part des grosses transactions | normal < {GT.LECTURE[0]:.0%} · notable · séance dominée ≥ {GT.LECTURE[1]:.0%} |
| Alerte de variation de l'indice | ± {C.SEUIL_ALERTE_VAR:.0%} sur une séance |
| Tolérance du contrôle des poids | ± {C.TOLERANCE_CONTROLE_PB} pb |

Ces paramètres se modifient dans `src/config.py`.
""".replace("%", " %"))

ui.section("Recalculer les grosses transactions")
st.markdown("Applique la règle actuelle (portes 1 et 2) à **tous les bulletins de la cote déjà importés** "
            "(dossier data/bulletins), dans l'ordre des dates. À lancer une fois après une mise à jour de la règle "
            "ou de ses paramètres. Compter environ 3 secondes par bulletin.")
if st.button("Recalculer les grosses transactions", icon=":material/refresh:"):
    from src import importer
    barre = st.progress(0.0, text="Lecture des bulletins…")
    res = importer.recalculer_grosses(lambda x, nom: barre.progress(min(x, 1.0), text=f"Lecture de {nom}"))
    barre.empty()
    ui.vider_cache()
    if res["bulletins"]:
        st.success(f"{res['bulletins']} bulletin(s) relu(s) · {res['niveaux']} grosse(s) transaction(s) repérée(s).")
    else:
        st.warning("Aucun bulletin de la cote trouvé dans data/bulletins.")
