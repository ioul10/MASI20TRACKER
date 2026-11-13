"""MASI20TRACKER : point d'entrée de l'application Streamlit."""
import streamlit as st

st.set_page_config(page_title="MASI20TRACKER", page_icon="📈", layout="wide", initial_sidebar_state="expanded")


def acces_autorise() -> bool:
    """Code d'accès : défini dans les secrets Streamlit (APP_PASSWORD).
    Sans secret défini, l'application reste ouverte."""
    import hmac
    try:
        code = st.secrets.get("APP_PASSWORD")
    except Exception:
        code = None
    if not code or st.session_state.get("acces_ok"):
        return True
    st.markdown(
        "<div style='max-width:420px;margin:12vh auto 0;text-align:center'>"
        "<div style='font-size:1.9rem;font-weight:700;color:#0B2447'>MASI<span style='color:#C9A227'>20</span>TRACKER</div>"
        "<div style='color:#5B6577;margin:6px 0 22px'>Accès réservé. Saisissez le code d'accès.</div></div>",
        unsafe_allow_html=True)
    _, c, _ = st.columns([1, 1.2, 1])
    with c.form("acces"):
        saisi = st.text_input("Code d'accès", type="password")
        if st.form_submit_button("Entrer", type="primary", width="stretch"):
            if hmac.compare_digest(saisi.encode(), str(code).encode()):
                st.session_state["acces_ok"] = True
                st.rerun()
            st.error("Code incorrect.")
    return False


if not acces_autorise():
    st.stop()

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
