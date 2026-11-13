import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import liquidite as L
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
act = db["actions"]
if act.empty:
    ui.page("Liquidité")
    st.info("Aucun bulletin de la cote importé. La liquidité se calcule à partir des bulletins de la cote (BCFR).")
    st.stop()

m = L.mesures_jour(K.panel(act, db["composition"]), db["flux"])
ui.page("Liquidité", "Quelles valeurs du MASI 20 s'achètent et se vendent facilement ?", m["date"].max())

# --- Semaines pour lesquelles on a des bulletins de la cote
fins = sorted(m["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize().unique(), reverse=True)
fin = pd.Timestamp(st.selectbox(
    "Semaine", fins,
    format_func=lambda d: f"Semaine {pd.Timestamp(d).isocalendar().week} · du {date_courte(pd.Timestamp(d) - pd.Timedelta(days=4))} "
                          f"au {date_courte(pd.Timestamp(d))}"))
debut = fin - pd.Timedelta(days=4)
wk = m[(m["date"] >= debut) & (m["date"] <= fin)]
jours = sorted(wk["date"].unique())
m20 = db["masi20"]
seances_marche = m20[(m20["date"] >= debut) & (m20["date"] <= fin)]["date"]
manq = sorted(set(seances_marche) - set(jours))
txt = f"Calculé sur **{len(jours)} séance(s)** importée(s) : " + ", ".join(pd.Timestamp(d).strftime("%d/%m") for d in jours)
if manq:
    txt += f" · bulletins manquants : " + ", ".join(pd.Timestamp(d).strftime("%d/%m") for d in manq)
st.markdown(txt)

sc = L.score_valeurs(m, debut, fin)

# --- En bref
plus, moins = sc.iloc[0], sc.iloc[-1]
vol = wk.groupby("date")["volume"].sum().mean()
gros = wk["volume_gros"].sum() / wk["volume"].sum() if wk["volume"].sum() else None
ui.kpis([
    {"lab": "Volume moyen par séance", "val": mad(vol), "sub": "20 valeurs, marché central", "gold": True},
    {"lab": "La plus liquide", "val": plus["nom"].title(), "sub": f"score {plus['score']:.0f} / 100"},
    {"lab": "La moins liquide", "val": moins["nom"].title(), "sub": f"score {moins['score']:.0f} / 100"},
    {"lab": "Valeurs liquides / peu liquides", "val": f"{(sc['niveau'] == 'Liquide').sum()} / {(sc['niveau'] == 'Peu liquide').sum()}",
     "sub": "sur 20 valeurs"},
    {"lab": "Grosses transactions", "val": pct(gros, 0, False), "sub": "part du volume (≥ 5 M MAD sur un prix)"},
])

# --- Classement
ui.section("Classement des 20 valeurs : de la plus facile à la plus difficile à échanger")
c1, c2 = st.columns([1, 1.15])
with c1:
    st.plotly_chart(G.scores(sc), width="stretch", config=G.CFG)
with c2:
    tab = pd.DataFrame({
        "Valeur": sc["nom"], "Niveau": sc["niveau"], "Score": sc["score"],
        "Échangé par séance": sc["volume"],
        "Écart achat / vente": sc["spread"],
        "Variation pour 10 M MAD": sc["amihud"] * 10,
        "Séances avec échanges": sc["seances_traitees"].astype(str) + " / " + sc["seances"].astype(str)})
    sty = ui.style_table(tab, fmt={"Score": lambda v: nombre(v, 0), "Échangé par séance": lambda v: mad(v),
                                   "Écart achat / vente": lambda v: pct(v, 2, False),
                                   "Variation pour 10 M MAD": lambda v: pct(v, 2, False)})
    sty = sty.map(lambda v: f"color: {G.NIVEAUX.get(v, '')}; font-weight: 600" if v in G.NIVEAUX else "", subset=["Niveau"])
    st.dataframe(sty, width="stretch", hide_index=True, height=35 * len(tab) + 40)

with st.expander("Comment lire ce classement"):
    st.markdown("""
Une valeur **liquide** s'achète et se vend facilement : il s'en échange beaucoup, l'écart entre le prix
d'achat et le prix de vente est faible, et son cours bouge peu quand on échange.

| Colonne | Question | Bon signe |
|---|---|---|
| Échangé par séance | Combien s'échange-t-il ? | Élevé |
| Écart achat / vente | Combien coûte un aller-retour ? | Faible |
| Variation pour 10 M MAD | De combien le cours bouge-t-il quand on échange 10 M MAD ? | Faible |
| Séances avec échanges | La valeur s'échange-t-elle tous les jours ? | Toutes |

Le **score** combine ces mesures en comparant les 20 valeurs entre elles (100 = la plus liquide du lot).
Une valeur dont le volume vient surtout d'une seule grosse transaction est pénalisée, car ce volume ne se répète pas.
""")

# --- Note globale (seulement avec assez d'historique)
ui.section("Note globale du MASI 20 : la semaine est-elle plus ou moins liquide que d'habitude ?")
ok, n = L.note_disponible(m, fin)
if not ok:
    st.progress(min(n / L.SEANCES_MIN_NOTE, 1.0),
                text=f"Historique en cours de constitution : {n} / {L.SEANCES_MIN_NOTE} séances de bulletins importées")
    st.caption("La note globale compare chaque semaine aux précédentes. Elle s'affichera automatiquement après "
               f"{L.SEANCES_MIN_NOTE} séances importées (environ 4 semaines). Le classement ci-dessus, lui, est déjà fiable.")
else:
    li = L.indice_liquidite(m[m["date"] <= fin])
    li["semaine"] = li["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    h = li.groupby("semaine", as_index=False)["indice"].mean().rename(columns={"indice": "note"}).tail(26)
    h["semaine"] = h["semaine"].dt.strftime("S%V · %d/%m")
    note = float(h["note"].iloc[-1])
    lecture = ("plus liquide que d'habitude" if note >= 65 else "moins liquide que d'habitude" if note <= 35
               else "liquidité habituelle")
    ui.kpis([{"lab": "Note de la semaine", "val": f"{note:.0f} / 100", "sub": lecture, "gold": True}])
    st.plotly_chart(G.note_semaines(h), width="stretch", config=G.CFG)
ui.pied()
