import pandas as pd
import streamlit as st

from src import config as C
from src import news
from src import ui
from src.composants import composition_au

ui.page("Actualités", "La presse financière marocaine, filtrée sur le MASI 20, ses valeurs et le marché à terme")
db = ui.db()
compo = composition_au(db["composition"], pd.Timestamp.today())


@st.cache_data(ttl=1800, show_spinner="Lecture des flux d'actualités…")
def charger():
    return news.lire_flux(C.FLUX_NEWS)


c = st.columns([1.3, 1.3, 1, 0.6])
df, etat = charger()
df = news.filtrer(df, news.mots_cles(compo))
filtre = c[0].segmented_control("Afficher", ["MASI 20 & marché", "Tout"], default="MASI 20 & marché")
valeur = c[1].selectbox("Valeur", ["Toutes"] + sorted(compo["nom"]))
cherche = c[2].text_input("Recherche", "")
if c[3].button("Actualiser", width="stretch"):
    charger.clear()
    st.rerun()

x = df
if filtre == "MASI 20 & marché":
    x = x[x["valeurs"].map(len).gt(0) | x["marche"]]
if valeur != "Toutes":
    x = x[x["valeurs"].map(lambda v: valeur in v)]
if cherche:
    x = x[(x["titre"] + " " + x["resume"]).str.contains(cherche, case=False, na=False)]

st.caption(f"{len(x)} article(s) · sources : " + " · ".join(f"{k} ({v})" for k, v in etat.items()))
if x.empty:
    st.info("Aucun article ne correspond. Si toutes les sources sont « indisponibles », vérifiez les adresses des flux "
            "dans src/config.py (FLUX_NEWS).")
for _, r in x.head(60).iterrows():
    tags = "".join(f"<span class='m20-pill flat' style='margin-right:4px'>{v.title()}</span>" for v in r["valeurs"])
    if r["marche"]:
        tags += "<span class='m20-pill up'>Marché</span>"
    quand = r["date"].strftime("%d/%m/%Y %H:%M") if pd.notna(r["date"]) else ""
    st.markdown(f"""<div style="background:#fff;border:1px solid #E3E7EF;border-radius:10px;padding:12px 16px;margin-bottom:10px">
<div style="font-size:.78rem;color:#5B6577">{r['source']} · {quand}</div>
<div style="font-weight:600;font-size:1rem;margin:3px 0"><a href="{r['lien']}" target="_blank" style="color:#0B2447;text-decoration:none">{r['titre']}</a></div>
<div style="font-size:.86rem;color:#3A4458">{r['resume'][:260]}{'…' if len(r['resume']) > 260 else ''}</div>
<div style="margin-top:6px">{tags}</div></div>""", unsafe_allow_html=True)
ui.pied()
