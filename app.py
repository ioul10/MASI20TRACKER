"""MASI20TRACKER : point d'entrée de l'application Streamlit."""
import streamlit as st

st.set_page_config(page_title="MASI20TRACKER", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

pages = {
    "Marché": [
        st.Page("vues/tableau_de_bord.py", title="Tableau de bord", icon=":material/dashboard:", default=True),
        st.Page("vues/indice.py", title="Indice & technique", icon=":material/candlestick_chart:"),
        st.Page("vues/composants.py", title="Composants", icon=":material/grid_view:"),
        st.Page("vues/futures.py", title="Marché à terme", icon=":material/timeline:"),
        st.Page("vues/liquidite.py", title="Liquidité", icon=":material/water_drop:"),
    ],
    "Rapports": [
        st.Page("vues/bilan_hebdo.py", title="Bilan hebdo", icon=":material/summarize:"),
        st.Page("vues/actualites.py", title="Actualités", icon=":material/newspaper:"),
    ],
    "Données": [
        st.Page("vues/import.py", title="Import des bulletins", icon=":material/upload_file:"),
        st.Page("vues/parametres.py", title="Composition & paramètres", icon=":material/tune:"),
    ],
}
st.logo("assets/logo.svg", size="large")
st.navigation(pages).run()
