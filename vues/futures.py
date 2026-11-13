import pandas as pd
import streamlit as st

from src import charts as G
from src import config as C
from src import futures as F
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
m20 = db["masi20"].sort_values("date")
f = F.avec_base(F.preparer(db["futures"], db["futures_trades"]), m20)
if f.empty:
    ui.page("Marché à terme")
    st.info("Aucune donnée futures. Importez un bulletin du marché à terme (BCFR_D).")
    st.stop()
d = f["date"].max()
ui.page("Marché à terme", "Futures sur indice MASI 20 : cours, base, courbe, positions ouvertes et volumes", d)
x = f[f["date"] == d].sort_values("mois_echeance")

items = [{"lab": "MASI 20 (spot)", "val": nombre(x["spot"].iloc[0]) if x["spot"].notna().any() else "–", "sub": date_courte(d), "gold": True}]
for _, r in x.iterrows():
    items.append({"lab": F.libelle(r["ticker"]), "val": nombre(r["cloture"]),
                  "sub": f"{pct(r['var'])} · base {pct(r['base_pct'], 2)}", "sens": r["var"]})
ui.kpis(items)
ui.kpis([{"lab": "Positions ouvertes", "val": nombre(x["open_interest"].sum(), 0),
          "sub": f"{nombre(x['delta_oi'].sum(), 0, True)} sur la séance", "sens": x["delta_oi"].sum()},
         {"lab": "Volume de la séance", "val": mad(x["volume"].sum()), "sub": f"{int(x['transactions'].sum())} transactions"},
         {"lab": "Séances depuis le lancement", "val": str(f["date"].nunique()), "sub": f"depuis le {date_courte(f['date'].min())}"},
         {"lab": "Volume cumulé", "val": mad(f["volume"].sum()), "sub": "depuis le lancement"}])

onglets = st.tabs(["Cours & base", "Courbe des échéances", "Positions ouvertes & volumes", "Transactions", "Calculateur"])
with onglets[0]:
    c = st.columns([1, 1, 2])
    col = c[0].radio("Prix", ["Clôture", "Compensation"], horizontal=True)
    jours = c[1].selectbox("Fenêtre", [20, 60, 120, 250], index=1, format_func=lambda n: f"{n} séances")
    dd = sorted(f["date"].unique())[-jours:]
    fv = f[f["date"].isin(dd)]
    st.plotly_chart(G.futures_cours(fv, m20, "cloture" if col == "Clôture" else "compensation"), width="stretch", config=G.CFG)
    ui.section("Base (future − MASI 20, en % du spot)")
    st.plotly_chart(G.base_series(fv), width="stretch", config=G.CFG)
    st.caption("Base négative = déport (le future cote sous l'indice). À l'approche de l'échéance, la base converge vers zéro.")
with onglets[1]:
    toutes = sorted(f["date"].unique(), reverse=True)
    defaut = [toutes[0]] + [t for t in toutes if t <= toutes[0] - pd.Timedelta(days=7)][:1] + \
             [t for t in toutes if t <= toutes[0] - pd.Timedelta(days=28)][:1]
    choix = st.multiselect("Séances à comparer (4 au maximum)", toutes, default=defaut, max_selections=4,
                           format_func=lambda t: date_courte(pd.Timestamp(t)))
    st.plotly_chart(G.courbe_terme(f, [pd.Timestamp(t) for t in choix], m20), width="stretch", config=G.CFG)
    st.caption("Courbe croissante = report (contango) ; décroissante = déport (backwardation).")
with onglets[2]:
    jours = st.selectbox("Fenêtre ", [20, 60, 120, 250], index=1, format_func=lambda n: f"{n} séances")
    dd = sorted(f["date"].unique())[-jours:]
    st.plotly_chart(G.oi_volumes(f[f["date"].isin(dd)]), width="stretch", config=G.CFG)
    ui.section("Lecture prix × positions ouvertes (dernière séance)")
    lec = pd.DataFrame([{"Contrat": F.libelle(r["ticker"]), "Var.": r["var"], "Δ OI": r["delta_oi"],
                         "Lecture": " · ".join(F.lecture_prix_oi(r["var"], r["delta_oi"]))} for _, r in x.iterrows()])
    st.dataframe(ui.style_table(lec, pct_cols=["Var."], signe_cols=["Δ OI"], fmt={"Δ OI": lambda v: nombre(v, 0, True)}),
                 width="stretch", hide_index=True)
    with st.expander("Comment lire prix × positions ouvertes"):
        st.markdown("| Prix | Positions ouvertes | Lecture |\n|---|---|---|\n"
                    "| ↑ | ↑ | Nouvelles positions acheteuses : hausse **confirmée** |\n"
                    "| ↑ | ↓ | Rachats de positions vendeuses : hausse **fragile** |\n"
                    "| ↓ | ↑ | Nouvelles positions vendeuses : baisse **confirmée** |\n"
                    "| ↓ | ↓ | Liquidation de positions acheteuses : baisse **en fin de course** |")
with onglets[3]:
    tr = db["futures_trades"]
    dd = st.selectbox("Séance", sorted(tr["date"].unique(), reverse=True), format_func=lambda t: date_courte(pd.Timestamp(t)))
    t = tr[tr["date"] == dd]
    st.dataframe(ui.style_table(pd.DataFrame({"Contrat": t["ticker"].map(F.libelle), "Carnet": t["carnet"], "Cours": t["cours"],
                                              "Quantité": t["quantite"], "Volume": t["volume"], "Transactions": t["nb"]}),
                                fmt={"Cours": lambda v: nombre(v), "Quantité": lambda v: nombre(v, 0), "Volume": lambda v: mad(v, 2),
                                     "Transactions": lambda v: nombre(v, 0)}), width="stretch", hide_index=True)
    if t.empty:
        st.caption("Aucune transaction sur cette séance.")
with onglets[4]:
    c1, c2 = st.columns(2)
    with c1:
        ui.section("Position sur future")
        tk = st.selectbox("Contrat", list(x["ticker"]), format_func=F.libelle)
        prix = float(x.loc[x["ticker"] == tk, "cloture"].iloc[0])
        n = st.number_input("Nombre de contrats (négatif = vente)", value=10, step=1)
        entree = st.number_input("Prix d'entrée", value=prix, step=1.0)
        sortie = st.number_input("Prix de sortie / actuel", value=prix, step=1.0)
        depot = st.number_input("Dépôt de garantie par contrat (MAD)", value=1500.0, step=100.0)
        notion = abs(n) * prix * C.MULTIPLICATEUR
        pnl = n * (sortie - entree) * C.MULTIPLICATEUR
        ui.kpis([{"lab": "Notionnel", "val": mad(notion, 2)}, {"lab": "Résultat", "val": mad(pnl, 0), "sens": pnl},
                 {"lab": "Dépôt total", "val": mad(abs(n) * depot, 0)},
                 {"lab": "Levier", "val": f"{nombre(notion / (abs(n) * depot), 1)}×" if n and depot else "–"}])
        st.caption(f"1 point = {C.MULTIPLICATEUR} MAD par contrat. Frais et appels de marge non inclus.")
    with c2:
        ui.section("Couverture d'un portefeuille actions")
        val = st.number_input("Valeur du portefeuille (MAD)", value=10_000_000.0, step=500_000.0)
        beta = st.number_input("Bêta du portefeuille vs MASI 20", value=1.0, step=0.05)
        tk2 = st.selectbox("Contrat de couverture", list(x["ticker"]), format_func=F.libelle, key="cv")
        p2 = float(x.loc[x["ticker"] == tk2, "cloture"].iloc[0])
        nb = val * beta / (p2 * C.MULTIPLICATEUR)
        ui.kpis([{"lab": "Contrats à vendre", "val": nombre(round(nb), 0), "sub": f"calcul exact : {nombre(nb, 1)}", "gold": True},
                 {"lab": "Notionnel couvert", "val": mad(round(nb) * p2 * C.MULTIPLICATEUR, 2)}])
        st.caption("Nombre de contrats = valeur × bêta ÷ (prix du future × 10).")
ui.pied()
