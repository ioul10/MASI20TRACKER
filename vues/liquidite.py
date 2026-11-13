import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import config as C
from src import liquidite as L
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
act = db["actions"]
if act.empty:
    ui.page("Liquidité")
    st.info("Aucun bulletin de la cote importé.")
    st.stop()
p = K.panel(act, db["composition"])
m = L.mesures_jour(p, db["flux"])
li = L.indice_liquidite(m)
d = m["date"].max()
ui.page("Liquidité", "Indice de liquidité du MASI 20 : prix × volume × composants", d)

v = li.iloc[-1]
etat = "élevée" if v["indice_lisse"] >= 65 else "faible" if v["indice_lisse"] <= 35 else "habituelle"
ui.kpis([
    {"lab": "Indice de liquidité", "val": f"{nombre(v['indice_lisse'], 0)} / 100", "sub": f"liquidité {etat}", "gold": True},
    {"lab": "Volume des 20 valeurs", "val": mad(v["volume"]), "sub": f"séance du {date_courte(d)}"},
    {"lab": "Spread moyen pondéré", "val": pct(v["spread"], 2, False), "sub": "écart offre / demande à la clôture"},
    {"lab": "Impact prix (Amihud)", "val": nombre(v["amihud"] * 100, 3), "sub": "% de variation par M MAD échangé"},
    {"lab": "Grosses transactions", "val": pct(v["part_gros"], 0, False), "sub": "du volume (niveaux ≥ 5 M MAD)"},
])
if v["historique"] < 20:
    ui.note(f"L'indice est calculé sur {int(v['historique'])} séance(s) de bulletins seulement. Il compare chaque séance à "
            "l'historique disponible : il deviendra fiable après une vingtaine de séances importées.")

ui.section("Indice de liquidité et MASI 20")
st.plotly_chart(G.liquidite(li, db["masi20"]), width="stretch", config=G.CFG)

ui.section("Score de liquidité par valeur")
dates = sorted(m["date"].unique(), reverse=True)
c = st.columns([1, 1, 2])
fin = pd.Timestamp(c[0].selectbox("Jusqu'au", dates, format_func=lambda t: date_courte(pd.Timestamp(t))))
fen = c[1].selectbox("Sur", [1, 5, 20, 60], index=1, format_func=lambda n: f"{n} séance(s)")
avant = sorted(x for x in m["date"].unique() if x <= fin)
deb = avant[-min(fen, len(avant))]
if fen > len(avant):
    st.caption(f"Seulement {len(avant)} séance(s) de bulletins disponibles jusqu'à cette date.")
sc = L.score_valeurs(m, deb, fin)
c1, c2 = st.columns([1, 1.25])
with c1:
    st.plotly_chart(G.scores(sc), width="stretch", config=G.CFG)
with c2:
    tab = pd.DataFrame({"Valeur": sc["nom"], "Score": sc["score"], "Niveau": sc["niveau"].astype(str),
                        "Volume moyen": sc["volume"], "Rotation": sc["rotation"], "Spread": sc["spread"],
                        "Amihud": sc["amihud"] * 100, "Contrats / séance": sc["activite"],
                        "Concentration": sc["concentration"], "Séances traitées": sc["seances_traitees"].astype(str) + "/" + sc["seances"].astype(str)})
    st.dataframe(ui.style_table(tab, fmt={"Score": lambda v: nombre(v, 0), "Volume moyen": lambda v: mad(v),
                                          "Rotation": lambda v: pct(v, 3, False), "Spread": lambda v: pct(v, 2, False),
                                          "Amihud": lambda v: nombre(v, 3), "Contrats / séance": lambda v: nombre(v, 0),
                                          "Concentration": lambda v: pct(v, 0, False)}),
                 width="stretch", hide_index=True, height=740)

with st.expander("Méthode"):
    w = C.POIDS_LIQUIDITE
    st.markdown(f"""
**Cinq mesures par valeur et par séance**, toutes tirées du bulletin de la cote :

| Mesure | Calcul | Sens | Poids |
|---|---|---|---|
| Volume | Volume du marché central en MAD (marché de blocs exclu) | ↑ plus liquide | {w['volume']:.0%} |
| Rotation | Volume ÷ capitalisation flottante | ↑ plus liquide | {w['rotation']:.0%} |
| Amihud (impact prix) | \\|variation\\| ÷ volume en M MAD | ↓ plus liquide | {w['amihud']:.0%} |
| Spread | (offre − demande) ÷ milieu, à la clôture | ↓ plus liquide | {w['spread']:.0%} |
| Activité | Nombre de contrats | ↑ plus liquide | {w['activite']:.0%} |

**Score par valeur (0-100)** : rang de la valeur parmi les 20 pour chaque mesure, moyenne pondérée, puis deux pénalités :
volume concentré sur un seul prix (plus de 50 % du volume) et séances sans transaction.

**Indice de liquidité du MASI 20 (0-100)** : les mesures sont agrégées sur les 20 valeurs (volumes additionnés,
spread et Amihud pondérés par les poids), puis chaque séance est classée dans l'historique des 250 dernières séances.
50 = liquidité habituelle ; au-dessus, le marché est plus liquide que d'habitude. La courbe bleue est la moyenne sur 5 séances.
""".replace("%", " %"))
ui.pied()
