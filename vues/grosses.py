import numpy as np
import pandas as pd
import streamlit as st

from src import charts as G
from src import composants as K
from src import grosses as GT
from src import marche as M
from src import ui
from src.fmt import date_courte, mad, nombre, pct

db = ui.db()
act, flux, compo = db["actions"], db["flux"], db["composition"]
if act.empty:
    ui.page("Grosses transactions")
    st.info("Aucun bulletin de la cote importé.")
    st.stop()
dates = sorted(act["date"].unique(), reverse=True)
ui.page("Grosses transactions", "Quand une ou deux opérations font le volume, et le mouvement du MASI 20", dates[0])

gt = db.get("grosses", pd.DataFrame())
if gt is None or gt.empty or len(gt) < 10:
    ui.note("Peu de grosses transactions sont enregistrées. Si des bulletins ont été importés avant la mise en place de "
            "la règle, lancez une fois <b>Composition & paramètres → Recalculer les grosses transactions</b>.")

# ------------------------------------------------------------------ 1. la définition
ui.chapitre("La définition", "Ce qu’est une grosse transaction, et comment la plateforme la repère", "1")
c1, c2 = st.columns([1.25, 1])
with c1:
    st.markdown(f"""**Une grosse transaction** est un échange anormalement gros, passé par un ou quelques grands acteurs,
qui **gonfle le volume** d'une séance sans refléter l'intérêt de l'ensemble du marché.

Le bulletin donne, pour chaque action, les échanges **par prix** : montant et nombre de contrats.
Chaque prix est testé ; il est « gros » s'il passe **l'une des deux portes** :

| Porte | Montant au même prix | Montant par contrat |
|---|---|---|
| **1 · absolue** | au moins **{GT.P1_MONTANT / 1e6:.0f} M MAD** | au moins **{GT.P1_PAR_CONTRAT / 1e6:.0f} M MAD** |
| **2 · relative à la valeur** | au moins **{GT.P2_PLANCHER / 1e6:.0f} M MAD** | au moins **{GT.P2_MULTIPLE} fois** le contrat habituel de la valeur |

*Contrat habituel* = médiane du montant par contrat sur les {GT.HABITUEL_SEANCES} dernières séances de la valeur
(il en faut au moins {GT.HABITUEL_MIN} ; sinon seule la porte 1 s'applique).

**Le calcul**
- montant des grosses transactions = **somme des montants des prix « gros »** ;
- part des grosses transactions = montant des grosses transactions ÷ volume total ;
- volume courant = volume total − grosses transactions.""")
with c2:
    st.markdown(f"""**Exemple réel · Attijariwafa, 16/11/2026**

31,5 M MAD échangés à 17 prix différents. Au prix de **673,20 MAD** : **26,0 M MAD en 15 contrats**,
soit 1,7 M MAD par contrat → **gros** (portes 1 et 2). Les 16 autres prix sont normaux.

Part des grosses transactions = 26,0 ÷ 31,5 = **82 %** : sans cette opération, la séance n'aurait fait que 5,5 M MAD.

**Lecture de la part**
- moins de {pct(GT.LECTURE[0], 0, False)} : **normal**, le volume vient de nombreux échanges ordinaires ;
- de {pct(GT.LECTURE[0], 0, False)} à {pct(GT.LECTURE[1], 0, False)} : **notable** ;
- plus de {pct(GT.LECTURE[1], 0, False)} : **séance dominée** par une ou deux opérations.""")
with st.expander("Les cas particuliers"):
    st.markdown("""
1. **Valeur sans historique** (nouvelle cotation, reprise après suspension) : porte 1 seule tant qu'il n'y a pas 5 séances.
2. **Un gros ordre exécuté en plusieurs contrats** (un acheteur face à plusieurs vendeurs au même prix) : le montant par contrat baisse ; la porte 2 le voit, la porte 1 souvent pas. *CMGP, 04/11 : 26,3 M MAD en 54 contrats, 24 fois le contrat habituel.*
3. **Un gros ordre qui touche plusieurs prix** : chaque prix est jugé séparément ; les morceaux de moins de 1 M MAD restent dans le volume courant.
4. **Un gros ordre noyé parmi de petits ordres au même prix** : il n'est pas repéré, le bulletin ne détaille pas les ordres un par un. Cas rare.
5. **Un seul contrat** : même règle. *HPS, 04/11 : un contrat de 2,9 M MAD, 33 fois l'habituel.*
6. **Action au cours très élevé** (Wafa Assurance) : chaque contrat est naturellement gros ; c'est la porte 1 qui repère les opérations.
7. **Valeur très peu échangée** : le plancher de 1 M MAD évite de signaler des montants sans importance.
8. **Marché de blocs** : exclu de tous les volumes, jamais compté comme grosse transaction.
9. **Séances particulières** (révision d'indice, échéance des futures, introduction, offre publique) : les grosses transactions y sont attendues ; on le signale dans le commentaire.
10. **Séance presque entièrement « grosse »** : le volume du jour ne doit pas être lu comme un regain d'intérêt.

Détails et chiffres : fiche méthode « Les grosses transactions ».""")

# ------------------------------------------------------------------ 2. le résultat
ui.chapitre("Le résultat", "Part des grosses transactions et mouvement du MASI 20", "2")
c = st.columns([1.2, 1, 2])
d = pd.Timestamp(c[0].selectbox("Séance", dates, format_func=lambda x: date_courte(pd.Timestamp(x))))
fen = c[1].segmented_control("Période", ["Séance", "Semaine"], default="Séance") or "Séance"
debut = d - pd.Timedelta(days=d.weekday()) if fen == "Semaine" else d
lib = f"semaine du {date_courte(debut)} au {date_courte(d)}" if fen == "Semaine" else f"séance du {date_courte(d)}"

p = K.panel(act, compo, debut, d)
b = K.bilan_periode(p, flux)
x, r = M.concentration(b)
vm = M.vision_masi(db, debut, d)
g_per = gt[(gt["date"] >= debut) & (gt["date"] <= d)] if gt is not None and not gt.empty else pd.DataFrame()
g20 = g_per[g_per["isin"].isin(b["isin"])] if not g_per.empty else g_per
mixte = x.loc[x["portee"] == "Mixte", "mouvement"].sum() / r["mouvement_total_pb"] if r.get("mouvement_total_pb") else np.nan

ui.kpis([
    {"lab": "Grosses transactions · MASI 20", "val": pct(r.get("part_gros"), 0, False), "gold": True,
     "sub": f"{mad(r.get('volume_gros'))} sur {mad(r.get('volume'))} · {GT.lecture(r.get('part_gros'))}"},
    {"lab": "Grosses transactions · tout le marché", "val": pct(vm.get("part_gros"), 0, False),
     "sub": f"{mad(vm.get('volume_gros'))} sur {mad(vm.get('volume'))}"},
    {"lab": "Opérations repérées", "val": str(len(g_per)),
     "sub": f"dont {len(g20)} sur le MASI 20 · {g_per['nom'].nunique() if len(g_per) else 0} valeur(s)"},
    {"lab": "Mouvement du MASI 20 porté par des grosses transactions", "val": pct(r.get("part_mouvement_gt"), 0, False),
     "sub": f"{r.get('valeurs_gt', 0)} valeur(s) · + {pct(mixte, 0, False)} par des valeurs « mixtes »"},
])

st.markdown(f"""<div style='background:#fff;border:1px solid #E3E7EE;border-left:4px solid #C8A24A;border-radius:10px;
padding:12px 16px;line-height:1.6;margin:6px 0 10px'>{M.phrase_concentration(x, r, lib)}</div>""", unsafe_allow_html=True)

a, bt = st.columns([5, 1.3], vertical_alignment="bottom")
with a:
    ui.chapitre("Qui a fait bouger le MASI 20, et avec quel volume", lib, "3")
with bt.popover("La méthode", icon=":material/help:", width="stretch"):
    st.markdown(f"""**Pour chaque valeur du MASI 20** sur la période :
- sa **contribution** au mouvement du MASI 20 (poids × variation, en points de base) ;
- la **part de son volume** qui vient de grosses transactions.

**Classement de la valeur**
- **Grosses transactions** : au moins {pct(M.SEUIL_PORTE, 0, False)} de son volume vient de grosses transactions ;
- **Mixte** : de {pct(GT.LECTURE[0], 0, False)} à {pct(M.SEUIL_PORTE, 0, False)} ;
- **Marché** : moins de {pct(GT.LECTURE[0], 0, False)}, le mouvement est porté par des échanges ordinaires.

**Mouvement porté par des grosses transactions** = somme des |contributions| des valeurs classées
« Grosses transactions » ÷ somme des |contributions| des 20 valeurs.

Exemple : si l'indice a bougé de 100 pb au total (hausses et baisses additionnées sans le signe) et qu'une valeur
dominée par une grosse opération en a fait 30, le mouvement porté par des grosses transactions est de 30 %.""")
if x.empty:
    st.info("Pas de données de composants sur cette période.")
else:
    c1, c2 = st.columns([1, 1.15])
    with c1:
        st.plotly_chart(G.gt_mouvement(x), width="stretch", config=G.CFG)
    with c2:
        tab = pd.DataFrame({"Valeur": x["nom"].str.title(), "Contrib. (pb)": x["contribution_pb"],
                            "Part du mvt": x["part_mouvement"], "Volume": x["volume"],
                            "Part GT": x["part_gt"], "Porté par": x["portee"]})
        st.dataframe(ui.style_table(tab, signe_cols=["Contrib. (pb)"],
                                    fmt={"Contrib. (pb)": lambda v: nombre(v, 1, True), "Part du mvt": lambda v: pct(v, 0, False),
                                         "Volume": lambda v: mad(v), "Part GT": lambda v: pct(v, 0, False)}),
                     width="stretch", hide_index=True, height=38 * 21)

# ------------------------------------------------------------------ 4. évolution
ui.chapitre("Évolution, séance par séance", "Part des grosses transactions sur le MASI 20 et sur tout le marché", "4")
e = M.gt_par_seance(db)
if not e.empty:
    st.plotly_chart(G.gt_evolution(e), width="stretch", config=G.CFG)
    st.caption("Barres : part des grosses transactions dans le volume des 20 valeurs du MASI 20. Ligne : sur tout le marché.")

# ------------------------------------------------------------------ 5. la liste
ui.chapitre("La liste des grosses transactions", lib, "5")
univ = st.segmented_control("Valeurs", ["MASI 20", "Tout le marché"], default="MASI 20", key="gt_univ") or "MASI 20"
lst = g20 if univ == "MASI 20" else g_per
if lst is None or lst.empty:
    st.caption("Aucune grosse transaction repérée sur cette période.")
else:
    lst = lst.sort_values(["date", "volume"], ascending=[False, False])
    jour = flux[flux["marche"] == "central"].groupby(["date", "isin"])["volume"].sum()
    part_val = [g / jour.get((dd, i), np.nan) for dd, i, g in zip(lst["date"], lst["isin"], lst["volume"])]
    st.dataframe(ui.style_table(pd.DataFrame({
        "Séance": lst["date"].dt.strftime("%d/%m/%Y"), "Valeur": lst["nom"].str.title(), "Prix": lst["cours"],
        "Montant": lst["volume"], "Contrats": lst["nb"], "Par contrat": lst["par_contrat"], "Habituel": lst["habituel"],
        "× habituel": lst["multiple"], "Porte": lst["porte"], "Part du volume de la valeur": part_val}),
        fmt={"Prix": lambda v: nombre(v), "Montant": lambda v: mad(v), "Contrats": lambda v: nombre(v, 0),
             "Par contrat": lambda v: mad(v), "Habituel": lambda v: mad(v),
             "× habituel": lambda v: f"{nombre(v, 1)} ×", "Part du volume de la valeur": lambda v: pct(v, 0, False)}),
        width="stretch", hide_index=True, height=min(38 * (len(lst) + 1) + 4, 460))
    st.caption("Une ligne = un prix d'une action dans une séance. Habituel vide : moins de 5 séances d'historique, porte 1 seule.")
ui.pied()
