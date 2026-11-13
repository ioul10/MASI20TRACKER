import pandas as pd
import streamlit as st

from src import config as C
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
| Grosse transaction | niveau de prix ≥ 5 M MAD et ≥ 1 M MAD par contrat |
| Alerte de variation de l'indice | ± {C.SEUIL_ALERTE_VAR:.0%} sur une séance |
| Tolérance du contrôle des poids | ± {C.TOLERANCE_CONTROLE_PB} pb |
| Pondération du score de liquidité | {", ".join(f"{k} {v:.0%}" for k, v in C.POIDS_LIQUIDITE.items())} |

Ces paramètres se modifient dans `src/config.py`.
""".replace("%", " %"))
