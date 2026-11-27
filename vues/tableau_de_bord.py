import pandas as pd
import streamlit as st

from src import charts as G
from src import futures as F
from src import grosses as GT
from src import bilan as B
from src import marche as M
from src import seance as S
from src import ui, vue_semaine
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
if db["masi20"].empty:
    ui.page("Tableau de bord")
    st.info("La base est vide. Commencez par importer des bulletins (Données → Import des bulletins).")
    st.stop()
o = S.resume(db)
ui.page("Tableau de bord", "La dernière séance en un coup d'œil, et le bilan de la semaine", o["date"])

onglet_seance, onglet_semaine = st.tabs(["Dernière séance", "Bilan de la semaine (Word)"])

with onglet_seance:
    # ---------------------------------------------------------------- l'essentiel
    ui.chapitre("L’essentiel de la séance", f"Séance du {date_courte(o['date'])}")
    ui.encadre(o["phrase"])

    # ---------------------------------------------------------------- MASI · tout le marché
    if "masi" in o:
        dm = o["masi"]["date"]
        jour_m = M.vision_masi(db, dm, dm)
        sem_m = M.vision_masi(db, dm - pd.Timedelta(days=dm.weekday()), dm)
        ui.chapitre("Le marché (MASI)", f"Toute la cote · séance du {date_courte(dm)}", "1")
        ui.kpis([
            {"lab": "MASI", "val": nombre(jour_m.get("valeur")), "sub": f"{pct(jour_m.get('var_jour'))} sur la séance",
             "sens": jour_m.get("var_jour"), "gold": True},
            {"lab": "Semaine en cours", "val": pct(sem_m.get("var")), "sens": sem_m.get("var"),
             "sub": f"MASI 20 : {pct(sem_m.get('var_masi20_publie'))}"},
            {"lab": "Depuis le 31/12", "val": pct(jour_m.get("var_ytd")), "sens": jour_m.get("var_ytd")},
            {"lab": "Hausses / baisses", "val": f"{jour_m.get('hausses', 0)} / {jour_m.get('baisses', 0)}",
             "sub": f"sur {jour_m.get('actions', 0)} actions cotées"},
            {"lab": "Volume du marché", "val": mad(jour_m.get("volume")),
             "sub": (f"{nombre(jour_m['volume_vs'], 1)} × l'habituel · " if pd.notna(jour_m.get("volume_vs")) else "")
                    + f"MASI 20 : {pct(jour_m.get('part_masi20'), 0, False)}"},
        ])
        c1, c2 = st.columns([1, 1])
        with c1:
            b100 = B.base100(db)
            if not b100.empty:
                ui.section("MASI et MASI 20 · base 100")
                st.plotly_chart(G.base100_masi(b100, h=380), width="stretch", config=G.CFG)
        with c2:
            sect = jour_m.get("secteurs", pd.DataFrame())
            if sect is not None and not sect.empty:
                ui.section("Indices sectoriels · séance")
                s2 = pd.concat([sect.head(6), sect.tail(6)]).drop_duplicates("indice")
                st.plotly_chart(G.secteurs_barres(s2, h=380), width="stretch", config=G.CFG)

    # ---------------------------------------------------------------- MASI 20
    ui.chapitre("Le MASI 20", f"Séance du {date_courte(o['date'])}", "2")
    items = [{"lab": f"MASI 20 · {date_courte(o['date'])}", "val": nombre(o["masi20"]), "sub": f"{pct(o['var'])} sur la séance",
              "sens": o["var"], "gold": True},
             {"lab": "Semaine en cours", "val": pct(o["var_semaine"]), "sub": "depuis la clôture de la semaine précédente",
              "sens": o["var_semaine"]},
             {"lab": "Depuis le 1er janvier", "val": pct(o["var_ytd"]), "sens": o["var_ytd"]}]
    if "composants" in o:
        items += [{"lab": "Hausses / baisses", "val": f"{o['hausses']} / {o['baisses']}", "sub": "sur les 20 valeurs"},
                  {"lab": "Volume des 20 valeurs", "val": mad(o["volume20"]),
                   "sub": (f"{nombre(o['volume20_vs'], 1)} × la moyenne 5 séances" if pd.notna(o.get("volume20_vs"))
                           else f"{pct(o['part_marche'], 0, False)} du marché central")},
                  {"lab": "Grosses transactions", "val": pct(o["part_gros"], 0, False), "sub": GT.lecture(o["part_gros"])}]
    ui.kpis(items)
    if "cote_date" in o and o["cote_date"] != o["date"]:
        ui.note(f"Dernier bulletin de la cote importé : {date_courte(o['cote_date'])}. Les composants et les volumes portent "
                f"sur cette séance ; l'indice va jusqu'au {date_courte(o['date'])}.")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        ui.section("MASI 20 · 3 derniers mois")
        st.plotly_chart(G.indice_moyennes(o["tech"].tail(63), periodes=(20, 40), h=360), width="stretch", config=G.CFG)
    with c2:
        if "composants" in o:
            ui.section(f"Qui a fait bouger le MASI 20 · {date_courte(o['cote_date'])}")
            b = o["composants"]
            top = pd.concat([b.head(5), b.tail(5)]).drop_duplicates("isin")
            st.plotly_chart(G.contributions(top, h=360), width="stretch", config=G.CFG)

    if "composants" in o:
        c1, c2 = st.columns(2)
        b = o["composants"]
        with c1:
            ui.section("Où va l'argent · 5 plus gros volumes")
            v = b.sort_values("volume", ascending=False).head(5)
            st.dataframe(ui.style_table(pd.DataFrame({
                "Valeur": v["nom"].str.title(), "Var.": v["rendement"], "Volume": v["volume"],
                "Part des 20": v["part_volume"], "Grosses trans.": v["volume_gros"] / v["volume"].where(v["volume"] > 0)}),
                pct_cols=["Var."], fmt={"Volume": lambda x: mad(x), "Part des 20": lambda x: pct(x, 0, False),
                                        "Grosses trans.": lambda x: pct(x, 0, False)}),
                width="stretch", hide_index=True)
        with c2:
            ui.section("Grosses transactions de la séance")
            g = o.get("grosses", pd.DataFrame())
            if g is None or g.empty:
                st.caption("Aucune grosse transaction repérée sur cette séance.")
            else:
                st.dataframe(ui.style_table(pd.DataFrame({
                    "Valeur": g["nom"].str.title(), "Prix": g["cours"], "Montant": g["volume"], "Contrats": g["nb"],
                    "× habituel": g["multiple"]}).head(8),
                    fmt={"Prix": lambda x: nombre(x), "Montant": lambda x: mad(x), "Contrats": lambda x: nombre(x, 0),
                         "× habituel": lambda x: f"{nombre(x, 1)} ×"}),
                    width="stretch", hide_index=True)
    # ---------------------------------------------------------------- technique
    z = o["z"]
    ui.section("Technique")
    au = sum(z["cloture"] > z[f"mm{k}"] for k in (5, 10, 20, 40) if pd.notna(z[f"mm{k}"]))
    ui.kpis([{"lab": "Moyennes mobiles", "val": f"{au} / 4", "sub": "moyennes sous l'indice (5, 10, 20, 40)"},
             {"lab": "RSI 14", "val": nombre(z["rsi14"], 0),
              "sub": "surachat" if z["rsi14"] >= 70 else "survente" if z["rsi14"] <= 30 else "zone neutre"},
             {"lab": "ATR 14", "val": f"{nombre(z['atr14'], 1)} pts", "sub": f"{pct(z['atr14_pct'], 2, False)} de l'indice"},
             {"lab": "Variation 5 séances", "val": pct(z["var_5j"]), "sub": f"régime {z['regime'] or '–'}", "sens": z["var_5j"]}])
    st.caption("Détails et explications : page Indice & technique.")

    # ---------------------------------------------------------------- futures
    if "futures" in o:
        x = o["futures"]
        ui.chapitre("Le marché à terme", f"Futures sur le MASI 20 · séance du {date_courte(o['futures_date'])}", "3")
        items = []
        for _, r in x.iterrows():
            items.append({"lab": F.libelle(r["ticker"]), "val": f"{nombre(r['cloture'])} pts",
                          "sub": f"{pct(r['var'])} · base {pct(r['base_pct'], 1)}"
                                 + (f" · {r['lecture'].lower()}" if r["lecture"] != "Indéterminé" else ""), "sens": r["var"]})
        items += [{"lab": "Positions ouvertes", "val": nombre(x["open_interest"].sum(), 0),
                   "sub": f"{nombre(x['delta_oi'].sum(), 0, True)} sur la séance", "sens": x["delta_oi"].sum()},
                  {"lab": "Volume", "val": mad(x["volume"].sum()) if x["volume"].sum() > 0 else "Aucun échange",
                   "sub": f"{nombre(x['transactions'].sum(), 0)} transaction(s)"}]
        ui.kpis(items)
        if o["futures_date"] != o["date"]:
            st.caption(f"Le dernier bulletin du marché à terme importé est celui du {date_courte(o['futures_date'])}.")


with onglet_semaine:
    vue_semaine.afficher(db)

ui.pied()
